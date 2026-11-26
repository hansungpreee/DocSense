"""엔진 단위 테스트 (API 호출 없음). 실행: python -m pytest tests -q"""
import json
import re
from types import SimpleNamespace

import pymupdf
import pytest
from PIL import Image

from src.engine.classify import Classifier, main
from src.engine.guardrail import NewCodeAllocator, ParseError, finalize, parse_response, validate
from src.engine.pages import load_pages
from src.engine.prompt import PAIR_GUIDE, build_messages, build_system_prompt
from src.engine.taxonomy import ETC_CODE, add_minor, format_taxonomy, load_taxonomy, taxonomy_path


@pytest.fixture(scope="module")
def tax():
    return load_taxonomy()


def ok_response(**over):
    base = {
        "major": "재무/회계",
        "minor_code": "FIN-03",
        "minor_name": "손익계산서",
        "confidence": 0.93,
        "reasons": ["상단 제목이 '손익계산서'"],
        "evidence": [{"page": 1, "bbox_2d": [120, 40, 480, 90], "label": "문서 제목"}],
        "new_class_proposal": None,
    }
    base.update(over)
    return base


# 1. YAML 키 구조 ---------------------------------------------------------------
def test_load_structure(tax):
    assert len(tax.majors) == 7  # 대분류 6 + 기타
    assert len(tax.classifiable_items) == 100  # 기존 25 + 신규 75 (config/taxonomy.yaml)
    assert tax.is_valid_code(ETC_CODE)
    assert tax.major_of("LEG-01") == "법무/총무"


# 2. v1 / v2 분리 ---------------------------------------------------------------
def test_v1_has_no_definition(tax):
    v1 = format_taxonomy(tax, include_definition=False)
    v2 = format_taxonomy(tax, include_definition=True)
    assert "- FIN-03 손익계산서" in v1
    assert "영업손익" not in v1          # 정의 문구가 v1에 새면 안 됨
    assert "영업손익" in v2
    assert "영업손익" not in build_system_prompt(tax, "v1")
    assert "영업손익" in build_system_prompt(tax, "v2")


def test_v3_is_v2_plus_pair_guide(tax):
    # 버전마다 한 가지 변경만: v3에서 가이드를 빼면 v2와 같아야 한다
    v2 = build_system_prompt(tax, "v2")
    v3 = build_system_prompt(tax, "v3")
    assert PAIR_GUIDE not in v2
    assert v3.replace(f"\n{PAIR_GUIDE}\n", "", 1) == v2


def test_vfinal_is_v2_with_content_first_order(tax):
    # vFinal은 v2에서 판단 순서 문단(내용 중심 + 예외 규칙)만 바뀐다
    from src.engine.prompt import PROMPT_VERSIONS, JUDGE_TITLE_FIRST, judge_order
    v2 = build_system_prompt(tax, "v2")
    vf = build_system_prompt(tax, "vFinal")
    vf_judge = judge_order(PROMPT_VERSIONS["vFinal"], 0.7)
    assert JUDGE_TITLE_FIRST in v2 and vf_judge in vf
    assert vf.replace(vf_judge, JUDGE_TITLE_FIRST, 1) == v2
    assert PAIR_GUIDE not in vf


def test_vfinal_exception_rules_have_no_codes_and_use_threshold(tax):
    # 예외 규칙은 일반 원칙이라 특정 소분류 코드를 적지 않는다. 확신도 기준은 설정값을 따른다
    from src.engine.prompt import EXCEPTION_RULES
    assert not re.findall(r"[A-Z]+-\d\d", EXCEPTION_RULES)
    assert "미만으로 준다" in build_system_prompt(tax, "vFinal", threshold=0.8)
    assert "0.8 미만" in build_system_prompt(tax, "vFinal", threshold=0.8)


def test_pair_guide_codes_exist(tax):
    codes = re.findall(r"[A-Z]+-\d\d", PAIR_GUIDE)
    assert codes
    assert all(tax.is_valid_code(c) for c in codes)


def test_pair_guide_names_match_taxonomy_and_no_quotes(tax):
    # 가이드에 적은 소분류 이름이 taxonomy와 같아야 모델이 minor_name을 그대로 옮겨 쓴다
    for code in re.findall(r"[A-Z]+-\d\d", PAIR_GUIDE):
        assert tax.get(code).name in PAIR_GUIDE
    # 따옴표가 있으면 모델이 근거에 \' 같은 이스케이프를 쓰는 일이 있었다 (v3_clean_r2)
    assert "'" not in PAIR_GUIDE and '"' not in PAIR_GUIDE


def test_unknown_version(tax):
    with pytest.raises(KeyError):
        build_system_prompt(tax, "v9")


def test_prompt_lists_every_code(tax):
    prompt = build_system_prompt(tax, "v1")
    assert all(f"- {it.code} {it.name}" in prompt for it in tax.items)  # taxonomy.yaml 목록이 그대로 들어감
    assert f'major를 "{tax.major_of(ETC_CODE)}"로' in prompt


# 다중 페이지 입력 -----------------------------------------------------------------
def make_pdf(path, n):
    doc = pymupdf.open()
    for i in range(n):
        doc.new_page().insert_text((72, 72), f"page {i + 1}")
    doc.save(path)
    return path


def test_pdf_to_pages(tmp_path):
    pages = load_pages(make_pdf(tmp_path / "doc.pdf", 3))
    assert len(pages) == 3
    assert all(p.mode == "RGB" and p.size == (1240, 1755) for p in pages)  # A4, 150 DPI


def test_unreadable_file(tmp_path):
    bad = tmp_path / "memo.png"
    bad.write_text("이미지가 아님", encoding="utf-8")
    with pytest.raises(ValueError, match="읽을 수 없는"):
        load_pages(bad)


def test_messages_number_pages(tax):
    pages = [Image.new("RGB", (10, 10), "white")] * 2
    content = build_messages(pages, tax)[1]["content"]
    kinds = [c["text"] if c["type"] == "text" else "IMG" for c in content]
    assert kinds == ["[1페이지]", "IMG", "[2페이지]", "IMG", "이 문서(2페이지)를 분류하라."]


# 3. 「기타」 → NEW-xx -------------------------------------------------------------
def test_etc_with_existing_name_is_retried(tax):
    # q37_v3_r2: 제목 '감사 보고서'를 읽고도 「기타」로 답하며 같은 이름을 신규 제안
    data = ok_response(
        major="기타",
        minor_code=ETC_CODE,
        minor_name="분류불가",
        confidence=0.95,
        new_class_proposal={"proposed_name": "감사 보고서", "proposed_major": "기타", "reason": "해당 소분류 없음"},
    )
    errors = validate(data, tax)
    assert len(errors) == 1 and "FIN-09" in errors[0] and "'감사보고서'" in errors[0]
    # 분류 체계에 없는 이름은 그대로 통과
    data["new_class_proposal"]["proposed_name"] = "관공서 신고서"
    assert validate(data, tax) == []
    # q37g_v2_r2: 이름 뒤에 괄호 설명을 붙여도 같은 이름 (CUS-01 비밀유지계약서)
    data["new_class_proposal"]["proposed_name"] = "비밀유지계약서 (NDA)"
    errors = validate(data, tax)
    assert len(errors) == 1 and "CUS-01" in errors[0]
    # 이름에 다른 말이 더 붙은 진짜 새 분류는 막지 않는다
    data["new_class_proposal"]["proposed_name"] = "가맹 비밀유지서약서 (직원용)"
    assert validate(data, tax) == []


def test_etc_becomes_new(tax):
    alloc = NewCodeAllocator.from_taxonomy(tax)
    data = ok_response(
        major="기타",
        minor_code=ETC_CODE,
        minor_name="분류불가",
        confidence=0.8,
        new_class_proposal={"proposed_name": "출장정산서", "proposed_major": "재무/회계", "reason": "출장비 정산 양식"},
    )
    assert validate(data, tax) == []
    r = finalize(data, tax, alloc)
    assert r["minor_code"] == "NEW-01"
    assert r["minor_name"] == "출장정산서"
    assert r["major"] == "재무/회계"
    assert r["status"] == "pending_review"
    assert r["new_class"]["proposed_name"] == "출장정산서"
    assert r["new_class"]["trigger"] == "etc"

    # 같은 제안명이면 같은 번호, 다른 제안명이면 다음 번호
    assert finalize(data, tax, alloc)["minor_code"] == "NEW-01"
    data2 = dict(data, new_class_proposal={"proposed_name": "활동보고서", "proposed_major": "영업/제안", "reason": "x"})
    assert finalize(data2, tax, alloc)["minor_code"] == "NEW-02"


def test_new_code_groups_names_with_same_ending(tax):
    alloc = NewCodeAllocator.from_taxonomy(tax)
    a = alloc.assign("비품 구매 요청서")
    assert alloc.assign("구매요청서") == a            # 개발 OOD에서 실제로 갈라졌던 두 이름 (공백 제거 후 끝부분 일치)
    assert alloc.assign("자산구매요청서") != a        # 이미 발급한 이름과 직접 일치할 때만 묶는다: 별칭을 거쳐 이어 묶지 않는다
    alloc2 = NewCodeAllocator.from_taxonomy(tax)
    b = alloc2.assign("구매요청서")
    assert alloc2.assign("비품 구매 요청서") == b     # 짧은 이름이 먼저 와도 같은 코드
    assert alloc.assign("휴가 신청서") != a           # 끝부분이 다르면 다른 코드
    assert alloc.assign("신청서") != a                # 짧은 이름(3자)은 모든 서식을 삼키지 않게 묶지 않는다
    assert alloc.assign("신청서") == alloc.assign("신청 서")   # 같은 이름은 그대로 같은 코드
    assert alloc.assign(None) not in {a, alloc.assign("휴가 신청서")}   # 제안명이 없으면 새 코드


def test_low_confidence_becomes_new(tax):
    alloc = NewCodeAllocator.from_taxonomy(tax)
    data = ok_response(confidence=0.55)
    r = finalize(data, tax, alloc, threshold=0.7)
    assert r["minor_code"].startswith("NEW-")
    assert r["predicted_code"] == "FIN-03"
    assert r["new_class"]["trigger"] == "low_confidence"
    assert r["new_class"]["proposed_major"] == "재무/회계"
    assert "0.55" in r["new_class"]["reason"]


def test_normal_result(tax):
    r = finalize(ok_response(), tax, NewCodeAllocator.from_taxonomy(tax))
    assert (r["major"], r["minor_code"], r["new_class"]) == ("재무/회계", "FIN-03", None)
    assert r["evidence"][0]["bbox"] == [120, 40, 480, 90]


# 가드레일 검증 --------------------------------------------------------------------
@pytest.mark.parametrize(
    "over, needle",
    [
        ({"minor_code": "FIN-99"}, "없는 코드"),
        ({"confidence": "높음"}, "confidence"),
        ({"evidence": [{"bbox_2d": [0, 0, 1500, 10]}]}, "bbox_2d"),
        ({"evidence": [{"bbox_2d": [120, 40, 120, 90]}]}, "넓이"),  # x1 = x2
        ({"evidence": [{"bbox_2d": [[0, 0, 1500, 10]]}]}, "bbox_2d"),  # 이중 대괄호를 풀어도 범위 검사는 유지
        ({"evidence": [{"bbox_2d": [[0, 0, 10, 10], [0, 0, 20, 20]]}]}, "bbox_2d"),  # 박스 여러 개는 풀지 않음
        ({"evidence": [{"page": 2, "bbox_2d": [0, 0, 10, 10]}]}, "page"),  # 1페이지 문서에 2페이지 근거
        ({"evidence": [{"page": "1페이지", "bbox_2d": [0, 0, 10, 10]}]}, "page"),
        ({"reasons": [{"text": "제목"}]}, "reasons"),
        ({"reasons": ["제목이 '표준임대차계약서'가 아니라 '표준임대차계약서'도 아니고, " * 20]}, "반복"),  # 실제 반복 출력
        ({"minor_code": ["FIN-03"]}, "minor_code"),
        ({"minor_code": "FIN-02"}, "맞지 않음"),  # 이름은 손익계산서인데 코드는 원가명세서  # 이상한 타입이 와도 예외 없이 오류 목록으로
        ({"minor_code": ETC_CODE, "new_class_proposal": None}, "new_class_proposal"),
    ],
)
def test_validate_errors(tax, over, needle):
    errs = validate(ok_response(**over), tax)
    assert any(needle in e for e in errs)


@pytest.mark.parametrize("code, name", [
    ("FIN-08", "소득ㆍ세액 공제 신고서"),
    ("HR-03", "HR-03 연봉 실수령액표"),  # 실제 응답: 이름 앞에 코드를 붙여 씀
    ("HR-03", "연봉 실수령액표 (HR-03)"),
])
def test_name_notation_ignored(tax, code, name):
    assert validate(ok_response(minor_code=code, minor_name=name), tax) == []


def test_code_name_mismatch_retried(tmp_path, monkeypatch):
    monkeypatch.setenv("VLM_API_KEY", "dummy")
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "0.7")
    img = tmp_path / "doc.png"
    Image.new("RGB", (100, 140), "white").save(img)
    client = FakeClient([json.dumps(ok_response(minor_code="FIN-02")), json.dumps(ok_response())])
    r = Classifier(client=client).classify(img)
    assert r["minor_code"] == "FIN-03" and r["retries"] == 1


def test_validate_multipage(tax):
    ev = [{"page": 1, "bbox_2d": [0, 0, 10, 10]}, {"page": 3, "bbox_2d": [0, 0, 10, 10]}]
    assert validate(ok_response(evidence=ev), tax, n_pages=3) == []


@pytest.mark.parametrize("box", [
    [480, 90, 120, 40],  # x1>x2, y1>y2 (Gemini HR-03_연봉실수령액표_044 같은 경우)
    [[120, 40, 480, 90]],  # 이중 대괄호
    [[480, 40, 120, 90]],  # 둘 다
])
def test_bbox_common_mistakes_accepted(tax, box):
    data = ok_response(evidence=[{"bbox_2d": box, "label": "문서 제목"}])
    assert validate(data, tax) == []
    assert finalize(data, tax, NewCodeAllocator())["evidence"][0]["bbox"] == [120, 40, 480, 90]


def test_finalize_cleans_label(tax):
    r = finalize(ok_response(evidence=[{"bbox_2d": [1, 2, 3, 4], "label": None}]), tax, NewCodeAllocator())
    assert r["evidence"] == [{"page": 1, "bbox": [1, 2, 3, 4], "label": ""}]


def test_parse_code_block():
    assert parse_response("```json\n" + json.dumps(ok_response()) + "\n```")["minor_code"] == "FIN-03"


def test_parse_tolerates_invalid_escape():
    # \' 는 JSON에 없는 이스케이프. \\ 와 \" 는 그대로 살아 있어야 한다
    text = json.dumps(ok_response(reasons=["X"]), ensure_ascii=False).replace('"X"', r'"제목이 \'상가건물\' 로 시작, 경로 C:\\a, 따옴표 \"b\""')
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)
    assert parse_response(text)["reasons"] == ["제목이 '상가건물' 로 시작, 경로 C:\\a, 따옴표 \"b\""]


def test_parse_still_rejects_broken_json():
    with pytest.raises(ParseError):
        parse_response('{"minor_code": "FIN-03",}')


def test_name_mismatch_message_gives_official_name(tax):
    errors = validate(ok_response(minor_code="LEG-01", minor_name="상가건물 임대차 표준계약서", major="법무/총무"), tax)
    assert any("'상가건물 임대차계약서' 그대로" in e for e in errors)


# classify 재요청 흐름 (가짜 API) ----------------------------------------------------
class FakeClient:
    def __init__(self, replies, usage=None):
        self.replies = list(replies)
        self.usage = usage  # 호출마다 돌려줄 토큰 사용량 (None이면 제공처가 안 보내는 경우)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls += 1
        text = self.replies.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))], usage=self.usage)


def test_retry_then_success(tmp_path, monkeypatch):
    monkeypatch.setenv("VLM_API_KEY", "dummy")
    img = tmp_path / "doc.png"
    Image.new("RGB", (100, 140), "white").save(img)
    client = FakeClient(["이건 JSON이 아님", json.dumps(ok_response(minor_code="FIN-99")), json.dumps(ok_response())])
    r = Classifier(prompt_version="v1", client=client).classify(img)
    assert r["minor_code"] == "FIN-03" and r["retries"] == 2 and client.calls == 3


def test_retry_exhausted(tmp_path, monkeypatch):
    monkeypatch.setenv("VLM_API_KEY", "dummy")
    img = tmp_path / "doc.png"
    Image.new("RGB", (100, 140), "white").save(img)
    r = Classifier(client=FakeClient(["x", "y", "z"])).classify(img)
    assert r["status"] == "error" and r["retries"] == 2


# 명령줄 실행: 결과 JSON과 근거 박스 이미지 저장 (bbox 좌표 확인용) ----------------------------
def test_cli_saves_result_and_boxes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VLM_API_KEY", "dummy")
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "0.7")
    ev = [{"page": 2, "bbox_2d": [100, 50, 700, 120], "label": "제목"}]
    reply = ok_response(minor_code="FIN-09", minor_name="감사보고서", evidence=ev)
    monkeypatch.setattr("openai.OpenAI", lambda **kw: FakeClient([json.dumps(reply)]))

    main([str(make_pdf(tmp_path / "audit.pdf", 2)), "--out", str(tmp_path / "out")])

    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((tmp_path / "out" / "audit.json").read_text(encoding="utf-8"))
    assert printed == saved and saved["minor_code"] == "FIN-09"
    red = (220, 38, 38)
    p1 = Image.open(tmp_path / "out" / "audit_p1.png")
    p2 = Image.open(tmp_path / "out" / "audit_p2.png")
    # 100/1000 × 1240px = 124px 지점에 2페이지에만 박스 왼쪽 선이 그려진다
    assert p2.getpixel((125, 150)) == red and p1.getpixel((125, 150)) != red


# 세로로 긴 이미지(전체 화면 캡처) → A4 비율 페이지로 자르기 ---------------------------------
def test_tall_image_split(tmp_path):
    tall = tmp_path / "tall.png"
    Image.new("RGB", (1000, 7000), "white").save(tall)  # A4 약 5장 분량
    pages = load_pages(tall)
    assert len(pages) == 5 and sum(p.height for p in pages) == 7000
    short = tmp_path / "short.png"
    Image.new("RGB", (1000, 1500), "white").save(short)
    assert len(load_pages(short)) == 1


# 데이터셋의 여러 쪽 문서(_p1, _p2 …) → 한 문서의 페이지로 묶기 ------------------------------------
def test_split_page_files_grouped(tmp_path):
    for i, color in enumerate(["white", "gray", "black"], start=1):
        Image.new("RGB", (100, 141), color).save(tmp_path / f"FIN-09_감사보고서_001_p{i}.png")
    Image.new("RGB", (100, 141), "red").save(tmp_path / "FIN-09_감사보고서_002_p2.png")  # 다른 문서는 섞이지 않음
    pages = load_pages(tmp_path / "FIN-09_감사보고서_001_p1.png")
    assert [p.getpixel((0, 0)) for p in pages] == [(255, 255, 255), (128, 128, 128), (0, 0, 0)]
    assert len(load_pages(tmp_path / "FIN-09_감사보고서_001_p2.png")) == 1  # _p1이 아니면 그 파일만


# 개발셋 일괄 실행: 오류가 나도 계속, 다시 실행하면 성공한 문서는 건너뜀 -------------------------
def test_run_continues_and_resumes(tmp_path, monkeypatch, capsys):
    import src.engine.run as run

    monkeypatch.setenv("VLM_API_KEY", "dummy")
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "0.7")
    monkeypatch.setattr(run, "ROOT", tmp_path)
    images = tmp_path / "images"
    images.mkdir()
    rows = [("FIN-03_손익계산서_001.png", "FIN-03"), ("FIN-03_손익계산서_002.png", "FIN-03"),
            ("HR-01_이력서_001.png", "HR-01")]
    labels = tmp_path / "labels.csv"
    labels.write_text("file,template,major,minor_code,split,variant,pages\n" + "".join(
        f"{f},t,{'재무/회계' if c.startswith('FIN') else '인사/채용'},{c},dev,clean,1\n" for f, c in rows
    ), encoding="utf-8-sig")
    for f, _ in rows:
        Image.new("RGB", (100, 140), "white").save(images / f)

    class Flaky(FakeClient):
        def _create(self, **kw):
            if self.calls == 1:  # 두 번째 호출만 네트워크 오류
                self.calls += 1
                raise TimeoutError("network")
            return super()._create(**kw)

    def fake_openai(**kw):
        return Flaky([json.dumps(ok_response())] * 5)

    monkeypatch.setattr("openai.OpenAI", fake_openai)
    args = ["--images", str(images), "--labels", str(labels), "--per-class", "1"]
    run.main(args)  # 소분류마다 1건 → FIN-03 1건, HR-01 1건. 두 번째 호출은 네트워크 오류
    summary = (tmp_path / "results" / "v1" / "summary.txt").read_text(encoding="utf-8")
    assert "문서 2건 (성공 1, 오류 1)" in summary and "소분류 정확도      100.0% (1/1)" in summary

    run.main(args)  # 다시 실행: 성공한 FIN-03은 건너뛰고 HR-01만 재시도 (가짜 응답은 FIN-03이라 오답)
    summary = (tmp_path / "results" / "v1" / "summary.txt").read_text(encoding="utf-8")
    assert "문서 2건 (성공 2, 오류 0)" in summary and "HR-01_이력서_001.png · HR-01 → FIN-03" in summary


def test_run_ignores_demo_taxonomy_path(tmp_path, monkeypatch):
    import src.engine.run as run
    from src.engine.taxonomy import DEFAULT_PATH

    seen = {}

    def spy(**kw):
        seen.update(kw)
        raise RuntimeError("여기까지만 확인")

    monkeypatch.setenv("TAXONOMY_PATH", str(tmp_path / "demo.yaml"))   # 데모 복사본이 지정돼 있어도
    monkeypatch.setattr(run, "ROOT", tmp_path)
    monkeypatch.setattr(run, "Classifier", spy)
    (tmp_path / "images").mkdir()
    Image.new("RGB", (10, 10)).save(tmp_path / "images" / "FIN-03_a_001.png")
    labels = tmp_path / "labels.csv"
    labels.write_text("file,template,major,minor_code,split,variant,pages\nFIN-03_a_001.png,t,재무/회계,FIN-03,dev,clean,1\n",
                      encoding="utf-8-sig")
    with pytest.raises(SystemExit):
        run.main(["--images", str(tmp_path / "images"), "--labels", str(labels)])
    assert seen["taxonomy_path"] == DEFAULT_PATH               # 평가는 원본을 읽는다

    other = tmp_path / "taxonomy_100.yaml"
    other.write_text("taxonomy: []\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        run.main(["--images", str(tmp_path / "images"), "--labels", str(labels), "--taxonomy", str(other)])
    assert seen["taxonomy_path"] == other                      # --taxonomy를 주면 그 파일로 잰다
    with pytest.raises(SystemExit):                            # 없는 파일은 호출 전에 막는다
        run.main(["--images", str(tmp_path / "images"), "--labels", str(labels), "--taxonomy", str(tmp_path / "x.yaml")])


# 토큰 사용량: 재요청까지 합치고, 문서마다 새로 센다 ------------------------------------------------
USAGE = SimpleNamespace(prompt_tokens=1000, completion_tokens=200)


def test_usage_summed_over_retries(tmp_path, monkeypatch):
    monkeypatch.setenv("VLM_API_KEY", "dummy")
    img = tmp_path / "doc.png"
    Image.new("RGB", (100, 140), "white").save(img)
    clf = Classifier(client=FakeClient(["이건 JSON이 아님", json.dumps(ok_response())], usage=USAGE))
    clf.classify(img)  # 첫 호출 형식 오류 → 재요청 1회 = 2번 호출
    assert clf.last_usage == {"input_tokens": 2000, "output_tokens": 400}
    clf.client.replies.append(json.dumps(ok_response()))
    clf.classify(img)  # 다음 문서는 이어서 더하지 않고 새로 센다
    assert clf.last_usage == {"input_tokens": 1000, "output_tokens": 200}


def test_usage_missing_from_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("VLM_API_KEY", "dummy")
    img = tmp_path / "doc.png"
    Image.new("RGB", (100, 140), "white").save(img)
    clf = Classifier(client=FakeClient([json.dumps(ok_response())]))
    assert clf.classify(img)["minor_code"] == "FIN-03"
    assert clf.last_usage == {"input_tokens": 0, "output_tokens": 0}


# 재요청 사유: 시도별로 남기고, 문서마다 새로 센다 ---------------------------------------------------
def test_retry_errors_recorded_and_reset(tmp_path, monkeypatch):
    monkeypatch.setenv("VLM_API_KEY", "dummy")
    img = tmp_path / "doc.png"
    Image.new("RGB", (100, 140), "white").save(img)
    clf = Classifier(client=FakeClient(["이건 JSON이 아님", json.dumps(ok_response(minor_code="FIN-99")),
                                        json.dumps(ok_response())]))
    assert clf.classify(img)["retries"] == 2
    assert len(clf.last_retry_errors) == 2 and all(errs for errs in clf.last_retry_errors)  # 실패한 두 시도의 사유
    assert any("FIN-99" in e for e in clf.last_retry_errors[1])
    clf.client.replies.append(json.dumps(ok_response()))
    clf.classify(img)  # 재요청 없는 다음 문서는 이전 사유가 남지 않는다
    assert clf.last_retry_errors == []


# 엔진 로그: 호출 1건당 한 줄, 문서 내용·API 키는 남기지 않음 ------------------------------------------
def log_records(caplog):
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "docsense.engine"]


def test_log_success_with_retry(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("VLM_API_KEY", "dummy")
    img = tmp_path / "doc.png"
    Image.new("RGB", (100, 140), "white").save(img)
    caplog.set_level("INFO", logger="docsense.engine")
    reply = ok_response(reasons=["문서 본문: 홍길동 연봉 5천만원"])
    Classifier(prompt_version="v2", client=FakeClient(["이건 JSON이 아님", json.dumps(reply)])).classify(img)
    (rec,) = log_records(caplog)
    assert set(rec) == {"file", "status", "retries", "errors", "model", "prompt_version"}
    assert rec["file"] == "doc.png" and rec["status"] == "confirmed" and rec["retries"] == 1
    assert rec["prompt_version"] == "v2" and len(rec["errors"]) == 1
    assert "홍길동" not in caplog.text and "dummy" not in caplog.text


def test_log_retry_exhausted(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("VLM_API_KEY", "dummy")
    img = tmp_path / "doc.png"
    Image.new("RGB", (100, 140), "white").save(img)
    caplog.set_level("INFO", logger="docsense.engine")
    Classifier(client=FakeClient(["x", "y", "z"])).classify(img)
    (rec,) = log_records(caplog)
    assert rec["status"] == "error" and rec["retries"] == 2 and len(rec["errors"]) == 3


def test_log_api_exception_without_message(tmp_path, monkeypatch, caplog):
    class RateLimit(Exception):
        status_code = 429

    def boom(**kw):
        raise RateLimit("Incorrect API key provided: sk-secret123 / 응답 본문")

    monkeypatch.setenv("VLM_API_KEY", "dummy")
    img = tmp_path / "doc.png"
    Image.new("RGB", (100, 140), "white").save(img)
    caplog.set_level("INFO", logger="docsense.engine")
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=boom)))
    with pytest.raises(RateLimit):  # 호출부(run.py·services.py)의 예외 처리는 그대로
        Classifier(client=client).classify(img)
    (rec,) = log_records(caplog)
    assert rec["status"] == "exception" and rec["errors"] == ["RateLimit 429"]
    assert "sk-secret123" not in caplog.text


def test_log_written_to_file(tmp_path, monkeypatch):
    import os

    from src.engine.classify import LOG

    monkeypatch.setenv("VLM_API_KEY", "dummy")
    img = tmp_path / "doc.png"
    Image.new("RGB", (100, 140), "white").save(img)
    Classifier(client=FakeClient([json.dumps(ok_response())])).classify(img)
    LOG.handlers[0].flush()
    last = open(os.environ["ENGINE_LOG_PATH"], encoding="utf-8").read().splitlines()[-1]
    stamp, _, body = last.partition(",")[2].partition(" ")  # "2026-10-26 12:00:00,123 {...}"
    assert stamp.isdigit() and json.loads(body)["file"] == "doc.png"


def test_run_records_retry_errors_only_when_retried(tmp_path, monkeypatch):
    import src.engine.run as run

    names = ["FIN-03_손익계산서_001.png", "FIN-03_손익계산서_002.png"]
    images = run_env(tmp_path, monkeypatch, names)
    labels = tmp_path / "labels.csv"
    labels.write_text("file,template,major,minor_code,split,variant,pages\n" + "".join(
        f"{n},t,재무/회계,FIN-03,dev,clean,1\n" for n in names), encoding="utf-8-sig")
    replies = ["이건 JSON이 아님", json.dumps(ok_response()), json.dumps(ok_response())]
    monkeypatch.setattr("openai.OpenAI", lambda **kw: FakeClient(replies))
    run.main(["--images", str(images), "--labels", str(labels)])
    lines = [json.loads(line) for line in (tmp_path / "results" / "v1" / "predictions.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert lines[0]["retries"] == 1 and len(lines[0]["retry_errors"]) == 1
    assert "retry_errors" not in lines[1]


# run.py: 실행 이름(--out), OOD 셋(--split ood) ----------------------------------------------------
def run_env(tmp_path, monkeypatch, names):
    """결과를 tmp_path/results에 쓰도록 하고, 빈 PNG 이미지 폴더를 만들어 돌려준다."""
    import src.engine.run as run

    monkeypatch.setenv("VLM_API_KEY", "dummy")
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "0.7")
    monkeypatch.setattr(run, "ROOT", tmp_path)
    images = tmp_path / "images"
    images.mkdir()
    for name in names:
        Image.new("RGB", (100, 140), "white").save(images / name)
    return images


def test_run_out_name_separates_results(tmp_path, monkeypatch):
    import src.engine.run as run

    name = "FIN-03_손익계산서_001.png"
    images = run_env(tmp_path, monkeypatch, [name])
    labels = tmp_path / "labels.csv"
    labels.write_text(f"file,template,major,minor_code,split,variant,pages\n{name},t,재무/회계,FIN-03,dev,clean,1\n",
                      encoding="utf-8-sig")
    clients = []

    def fake_openai(**kw):
        clients.append(FakeClient([json.dumps(ok_response())]))
        return clients[-1]

    monkeypatch.setattr("openai.OpenAI", fake_openai)
    base = ["--images", str(images), "--labels", str(labels)]
    run.main(base + ["--out", "run_a"])
    run.main(base + ["--out", "run_b"])  # 이름이 다르면 run_a의 기록을 이어받지 않고 다시 분류한다
    assert sum(c.calls for c in clients) == 2
    assert all((tmp_path / "results" / d / "predictions.jsonl").is_file() for d in ("run_a", "run_b"))
    run.main(base + ["--out", "run_a"])  # 같은 이름이면 이어받아 호출하지 않는다
    assert sum(c.calls for c in clients) == 2
    assert not (tmp_path / "results" / "v1").exists()  # --out을 주면 기본 폴더(프롬프트 버전)는 만들지 않는다


@pytest.mark.parametrize("bad", ["results/v2", "a\\b", ".."])
def test_run_out_rejects_path(tmp_path, monkeypatch, bad):
    import src.engine.run as run

    images = run_env(tmp_path, monkeypatch, [])
    with pytest.raises(SystemExit):
        run.main(["--images", str(images), "--out", bad])


def test_run_ood_summary_and_gold_fields(tmp_path, monkeypatch):
    import src.engine.run as run

    picked = run.read_labels(run.OOD_LABELS, "ood", 1)  # 실제 ood_labels.csv: 종류마다 1건 = 3건
    assert [r["minor_code"] for r in picked] == ["OOD-01", "OOD-02", "OOD-03"]
    images = run_env(tmp_path, monkeypatch, [r["file"] for r in picked])
    etc = ok_response(
        major="기타", minor_code=ETC_CODE, minor_name="분류불가", confidence=0.8,
        new_class_proposal={"proposed_name": "지출결의서", "proposed_major": "재무/회계", "reason": "x"},
    )
    low = ok_response(
        confidence=0.5,
        new_class_proposal={"proposed_name": "업무협조전", "proposed_major": "법무/총무", "reason": "확신 낮음"},
    )
    # OOD-01: 모델이 「기타」 선택, OOD-02: 정식 코드(FIN-03)로 확정, OOD-03: FIN-03을 골랐지만 확신도 0.5 → 기준 미만으로 「기타」
    replies = [json.dumps(etc), json.dumps(ok_response()), json.dumps(low)]
    monkeypatch.setattr("openai.OpenAI", lambda **kw: FakeClient(replies, usage=USAGE))

    run.main(["--images", str(images), "--split", "ood", "--per-class", "1", "--out", "ood_run"])

    out = tmp_path / "results" / "ood_run"
    summary = (out / "summary.txt").read_text(encoding="utf-8")
    assert "OOD 문서 3건 (성공 3, 오류 0)" in summary
    assert "「기타」 판정률     66.7% (2/3)" in summary
    assert "OOD-01  1/1" in summary and "OOD-02  0/1" in summary and "OOD-03  1/1" in summary
    assert f"{picked[1]['file']} · OOD-02 → FIN-03" in summary
    assert "모델이 직접 「기타」 1건 · 확신도 기준 미만 1건" in summary
    assert f"{picked[2]['file']} · OOD-03 → FIN-03 · 0.5" in summary  # 기준값이 거른 문서는 모델 1순위와 함께 보인다
    lines = [json.loads(line) for line in (out / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(r["gold_code"], r["gold_major"], r["split"]) for r in lines] == [
        ("OOD-01", None, "ood"), ("OOD-02", None, "ood"), ("OOD-03", None, "ood")]
    assert all(r["usage"] == {"input_tokens": 1000, "output_tokens": 200} for r in lines)


def test_run_usage_not_stale_after_error(tmp_path, monkeypatch):
    import src.engine.run as run

    names = ["FIN-03_손익계산서_001.png", "FIN-03_손익계산서_002.png"]
    images = run_env(tmp_path, monkeypatch, names)
    labels = tmp_path / "labels.csv"
    labels.write_text("file,template,major,minor_code,split,variant,pages\n" + "".join(
        f"{n},t,재무/회계,FIN-03,dev,clean,1\n" for n in names), encoding="utf-8-sig")

    class FailSecond(FakeClient):
        def _create(self, **kw):
            if self.calls == 1:  # 두 번째 문서는 호출 자체가 실패
                self.calls += 1
                raise TimeoutError("network")
            return super()._create(**kw)

    monkeypatch.setattr("openai.OpenAI", lambda **kw: FailSecond([json.dumps(ok_response())], usage=USAGE))
    run.main(["--images", str(images), "--labels", str(labels)])
    lines = [json.loads(line) for line in (tmp_path / "results" / "v1" / "predictions.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert lines[0]["usage"] == {"input_tokens": 1000, "output_tokens": 200}
    assert lines[1]["status"] == "error" and lines[1]["usage"] == {"input_tokens": 0, "output_tokens": 0}


# 승인된 신규 분류를 taxonomy.yaml에 추가 (FR-10) -- 실제 config가 아니라 임시 복사본만 쓴다 --------
@pytest.fixture
def yml(tmp_path):
    path = tmp_path / "taxonomy.yaml"
    path.write_bytes(open("config/taxonomy.yaml", "rb").read())
    return path


def test_add_minor_issues_next_code(yml):
    before = yml.read_bytes()
    code = add_minor("  출장  정산서 ", "재무/회계", "출장 경비를 정산하는 문서", path=yml)
    assert code == "FIN-23"                           # 접두어 FIN의 다음 번호 (FIN-22까지 있음)
    added = load_taxonomy(yml).get("FIN-23")
    assert (added.name, added.major) == ("출장 정산서", "재무/회계")
    assert add_minor("교육 신청서", "인사/채용", "교육 신청 문서", path=yml) == "HR-16"
    assert add_minor("계약 해지서", "법무/총무", "계약 해지 통지 문서", path=yml) == "LEG-19"
    # 기존 항목·줄바꿈(CRLF)·주석은 그대로, 새 항목은 해당 대분류 끝에만 들어간다
    after = yml.read_bytes()
    assert after.count(b"\r\n") == after.count(b"\n") and after.startswith(before.split(b"\r\n")[0])
    tax = load_taxonomy(yml)
    assert [i.code for i in tax.items if i.major == "재무/회계"][-1] == "FIN-23"
    assert len(tax.items) == len(load_taxonomy().items) + 3


def test_add_minor_rejects_bad_input_and_keeps_file(yml):
    before = yml.read_bytes()
    with pytest.raises(ValueError, match="이미 있는 분류명"):
        add_minor("감사 보고서", "재무/회계", "정의", path=yml)   # FIN-09 감사보고서와 공백만 다름
    with pytest.raises(ValueError, match="없는 대분류"):
        add_minor("새 문서", "없는 대분류", "정의", path=yml)
    with pytest.raises(ValueError, match="추가할 수 없습니다"):
        add_minor("새 문서", "기타", "정의", path=yml)
    with pytest.raises(ValueError, match="정의"):
        add_minor("새 문서", "재무/회계", "  ", path=yml)
    assert yml.read_bytes() == before and not list(yml.parent.glob("*.tmp"))


def test_add_minor_handles_yaml_special_chars_and_lf(yml):
    yml.write_bytes(yml.read_bytes().replace(b"\r\n", b"\n"))
    name, definition = '견적서 "별첨": 비고 #1', "따옴표(\")와 콜론: 샵 # 포함"
    code = add_minor(name, "영업/제안", definition, path=yml)
    assert code == "SAL-21" and b"\r" not in yml.read_bytes()   # LF 파일은 LF 그대로
    it = load_taxonomy(yml).get(code)
    assert (it.name, it.definition) == (name, definition)


def test_taxonomy_path_env_makes_demo_copy(tmp_path, monkeypatch):
    real = taxonomy_path()
    assert real.name == "taxonomy.yaml" and real.parent.name == "config"   # conftest가 TAXONOMY_PATH를 비워 둠
    demo = tmp_path / "db" / "demo.yaml"
    monkeypatch.setenv("TAXONOMY_PATH", str(demo))
    assert taxonomy_path() == demo and demo.exists()   # 없으면 원본을 복사해 만든다
    add_minor("출장 정산서", "재무/회계", "출장 경비 정산")
    assert load_taxonomy().get("FIN-23")               # 경로를 안 주면 복사본에 쓰고 읽는다
    assert not load_taxonomy(real).get("FIN-23")       # 실제 config는 그대로


def test_log_summary_counts(tmp_path, capsys):
    from src.engine.log_summary import main as summary_main

    def line(status, retries, errors):
        rec = {"file": "a.png", "status": status, "retries": retries, "errors": errors, "model": "m",
               "prompt_version": "v2"}
        return "2026-10-26 12:00:00,000 " + json.dumps(rec, ensure_ascii=False)

    log = tmp_path / "engine.log"
    log.write_text("\n".join([
        line("confirmed", 0, []),
        line("confirmed", 1, [["JSON 객체를 찾지 못함"]]),
        line("error", 2, [["JSON 객체를 찾지 못함"], ["빈 응답"], ["JSON 객체를 찾지 못함"]]),
        line("exception", 0, ["RateLimitError 429"]),
        "깨진 줄",
    ]), encoding="utf-8")
    summary_main([str(log)])
    out = capsys.readouterr().out
    assert "호출 4건" in out and "재요청이 있었던 호출 2건 (재요청 합계 3회)" in out
    assert "오류로 끝난 호출 2건" in out and "건너뛴 줄 1개" in out
    assert out.index("3회  JSON 객체를 찾지 못함") < out.index("1회  RateLimitError 429")


def test_run_ood_labels_fall_back_to_minor_code(tmp_path):
    from src.engine import run
    path = tmp_path / "ood.csv"
    path.write_text("file,minor_code,split\na.png,OOD-01,dev\n", encoding="utf-8-sig")
    assert run.read_labels(path, "ood", 0) == [{"file": "a.png", "minor_code": "OOD-01", "major": None, "split": "ood"}]
