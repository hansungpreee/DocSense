"""가드레일: 모델 응답 검증, 재요청 판단, 「기타」 → NEW-xx 변환.

흐름
    raw_text ──parse_response──▶ dict ──validate──▶ 오류 목록
        오류 있음 → retry_feedback()으로 재요청 (classify.py, 최대 2회)
        오류 없음 → finalize()로 결과 JSON(회의 문서 3절 형식) 생성

finalize 규칙 (PRD 3절, FR-05, FR-08)
    - 모델이 ETC-00으로 답함            → minor_code = NEW-xx, new_class 채움
    - 확신도 < threshold (정식 코드라도) → minor_code = NEW-xx, new_class 채움
    - 그 외                             → 정식 코드 그대로, new_class = None
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .taxonomy import ETC_CODE, NEW_PREFIX, Taxonomy

SIMILAR_MIN_LEN = 4  # 제안명을 같은 NEW 코드로 묶을 때 짧은 쪽의 최소 글자 수 (공백 제외)
MAX_REASON_CHARS = 400  # 정상 근거 문장은 250자 안팎. 같은 말을 되풀이하는 반복 출력을 잡는다


class ParseError(ValueError):
    pass


# 1. 파싱 -------------------------------------------------------------------
def parse_response(text: str) -> dict:
    """응답 문자열에서 JSON 객체를 꺼낸다. ```json 코드블록으로 감싼 경우도 처리."""
    if not text:
        raise ParseError("빈 응답")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ParseError("JSON 객체를 찾지 못함")
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        try:  # 모델이 작은따옴표를 \'처럼 JSON에 없는 이스케이프로 쓰는 경우 (v3_clean_r2 LEG-01 4건)
            data = json.loads(_drop_invalid_escapes(m.group(0)))
        except json.JSONDecodeError:
            raise ParseError(f"JSON 문법 오류: {e.msg}") from e
    if not isinstance(data, dict):
        raise ParseError("최상위가 JSON 객체가 아님")
    return data


def _drop_invalid_escapes(s: str) -> str:
    """JSON이 허용하지 않는 \\X(X가 " \\ / b f n r t u가 아님)에서 역슬래시만 지운다. 앞에서부터 두 글자씩 봐서 \\\\는 그대로 둔다."""
    return re.sub(r"\\(.)", lambda m: m.group(0) if m.group(1) in '"\\/bfnrtu' else m.group(1), s, flags=re.S)


# 2. 검증 -------------------------------------------------------------------
def validate(data: dict, tax: Taxonomy, n_pages: int = 1) -> list[str]:
    """재요청이 필요한 오류만 돌려준다. 빈 리스트면 통과.
    모델 응답은 외부 입력이라 값의 타입까지 확인한다 (finalize·화면이 깨지지 않도록)."""
    errors: list[str] = []

    code = data.get("minor_code")
    if not _text(code):
        errors.append("minor_code가 없음")
    elif not tax.is_valid_code(code):
        errors.append(f"분류 체계에 없는 코드: {code}")

    conf = data.get("confidence")
    if not _is_number(conf) or not 0 <= conf <= 1:
        errors.append(f"confidence가 0~1 숫자가 아님: {conf!r}")

    reasons = data.get("reasons")
    if not isinstance(reasons, list) or not reasons or not all(_text(r) for r in reasons):
        errors.append("reasons가 근거 문장 리스트가 아님")
    elif any(len(r) > MAX_REASON_CHARS for r in reasons):
        errors.append(f"reasons 문장이 {MAX_REASON_CHARS}자를 넘음 (같은 말 반복). 근거를 한 문장씩 짧게 다시 쓸 것")

    evidence = data.get("evidence") or []
    if not isinstance(evidence, list):
        errors.append("evidence가 리스트가 아님")
        evidence = []
    for i, ev in enumerate(evidence):
        if not isinstance(ev, dict):
            errors.append(f"evidence[{i}]가 객체가 아님")
            continue
        page = ev.get("page", 1)
        if not (isinstance(page, int) and not isinstance(page, bool) and 1 <= page <= n_pages):
            errors.append(f"evidence[{i}].page가 1~{n_pages} 사이 정수가 아님: {page!r}")
        box = _box(ev.get("bbox_2d"))
        if not (isinstance(box, list) and len(box) == 4 and all(_is_number(v) and 0 <= v <= 1000 for v in box)):
            errors.append(f"evidence[{i}].bbox_2d가 0~1000 범위의 숫자 4개가 아님: {box!r}")
        elif not (box[0] < box[2] and box[1] < box[3]):
            errors.append(f"evidence[{i}].bbox_2d의 넓이가 0임 (x1=x2 또는 y1=y2): {box}")

    # 근거는 손익계산서인데 코드는 FIN-02처럼 어긋나는 경우를 잡는다 (「기타」는 이름 표기가 다양해 제외)
    name = _text(data.get("minor_name"))
    item = tax.get(code) if _text(code) else None
    if name and item and code != ETC_CODE and _loose(name, code) != _loose(item.name, code):
        # 문서 제목을 이름으로 옮겨 쓰는 경우가 있어 (v3_clean_r1 LEG-01 2건) 코드의 정식 이름을 알려 준다
        errors.append(
            f"minor_name '{name}'과 minor_code {code}({item.name})가 맞지 않음. "
            f"코드가 맞으면 minor_name을 분류 체계 이름 '{item.name}' 그대로 쓰고, 이름이 맞으면 그 이름의 코드를 고를 것"
        )

    if code == ETC_CODE and not _proposal_ok(data.get("new_class_proposal")):
        errors.append(f"{ETC_CODE}인데 new_class_proposal(proposed_name, proposed_major, reason)이 비어 있음")

    # 제목을 맞게 읽고도 "분류 체계에 없다"며 기존 소분류 이름을 신규 제안하는 경우 (q37 dev 오답 5건 중 4건)
    same = _existing_item_named(tax, data.get("new_class_proposal")) if code == ETC_CODE else None
    if same:
        errors.append(
            f"신규 제안 이름이 분류 체계의 소분류와 같음: {same.code} '{same.name}'. "
            f"분류 체계에 있는 문서이므로 minor_code {same.code}, minor_name '{same.name}' 그대로 답할 것"
        )

    return errors


def _box(box):
    """bbox_2d의 흔한 형식 실수를 고쳐 돌려준다. 분류 결과와 무관한 오류로 재요청 한도를 넘기지 않기 위함.

    - 이중 대괄호 [[x1, y1, x2, y2]] → 한 겹 푼다 (이전 측정 9건)
    - 뒤집힌 순서 (x1>x2 또는 y1>y2) → 작은 값이 앞에 오게 정렬 (Gemini HR-03_연봉실수령액표_044)
    숫자 4개가 아니면 그대로 돌려줘 검증에서 오류로 잡는다.
    """
    if isinstance(box, list) and len(box) == 1 and isinstance(box[0], list):
        box = box[0]
    if isinstance(box, list) and len(box) == 4 and all(_is_number(v) for v in box):
        x1, y1, x2, y2 = box
        box = [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
    return box


def _text(v) -> str | None:
    """비어 있지 않은 문자열이면 앞뒤 공백을 지워 돌려주고, 아니면 None."""
    return v.strip() if isinstance(v, str) and v.strip() else None


def _loose(name: str, code: str) -> str:
    """표기 차이는 같은 이름으로 본다: 공백·가운뎃점(소득·세액 / 소득ㆍ세액), 괄호,
    이름에 붙여 쓴 코드("HR-03 연봉 실수령액표", "연봉 실수령액표(HR-03)")."""
    return re.sub(r"[\s·ㆍ・()\[\]]", "", name.replace(code, ""))


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _existing_item_named(tax: Taxonomy, proposal):
    """신규 제안 이름과 표기 차이만 있는 정식 소분류. 없으면 None."""
    name = _text(proposal.get("proposed_name")) if isinstance(proposal, dict) else None
    if not name:
        return None
    # 이름 뒤에 붙인 괄호 설명은 뺀다: '비밀유지계약서 (NDA)' = CUS-01 비밀유지계약서 (q37g_v2_r2 CUS-01 1건이 이 틈으로 빠졌다)
    name = _without_paren(name)
    return next(
        (it for it in tax.classifiable_items if _loose(name, it.code) == _loose(_without_paren(it.name), it.code)), None
    )


def _without_paren(name: str) -> str:
    return re.sub(r"\([^)]*\)|\[[^\]]*\]", "", name)


def _proposal_ok(p) -> bool:
    return isinstance(p, dict) and all(_text(p.get(k)) for k in ("proposed_name", "proposed_major", "reason"))


def retry_feedback(errors: list[str]) -> str:
    """재요청 시 모델에게 보낼 문장."""
    return (
        "이전 답변에 다음 문제가 있었다:\n- "
        + "\n- ".join(errors)
        + "\n출력 형식과 분류 체계의 코드를 지켜 JSON 객체 하나만 다시 답하라."
    )


# 3. NEW-xx 번호 발급 --------------------------------------------------------
@dataclass
class NewCodeAllocator:
    """신규 분류 코드 발급기. 같은 제안명에는 같은 코드를 준다.

    taken: 이미 쓰인 NEW 코드 (taxonomy.yaml에 승인된 것 + 이 발급기가 낸 것)
    by_name: 제안명(공백 제거) → 코드
    """

    # ponytail: 메모리에만 기록; SQLite 저장소가 생기면 승인 대기 목록으로 taken·by_name을 채워 재시작 후에도 번호 유지
    taken: set[str] = field(default_factory=set)
    by_name: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_taxonomy(cls, tax: Taxonomy) -> "NewCodeAllocator":
        return cls(taken=set(tax.existing_new_codes))

    def assign(self, proposed_name: str | None) -> str:
        key = _norm(proposed_name) if proposed_name else None
        if key:
            known = self.by_name.get(key) or self._similar_code(key)
            if known:
                return known
        n = 1
        while f"{NEW_PREFIX}{n:02d}" in self.taken:
            n += 1
        code = f"{NEW_PREFIX}{n:02d}"
        self.taken.add(code)
        if key:
            self.by_name[key] = code
        return code

    def _similar_code(self, key: str) -> str | None:
        """이미 발급한 제안명 중 key와 끝부분이 같은 것의 코드. 「비품구매요청서」와 「구매요청서」를 한 건으로 묶는다.
        짧은 쪽이 SIMILAR_MIN_LEN자 이상일 때만 본다 (「계약서」 같은 짧은 말이 모든 계약서를 삼키지 않게)."""
        # ponytail: 끝부분 일치만 사용; 앞부분이 다른 변형(「구매요청서(비품)」 등)까지 묶어야 하면 유사도 도입
        for name, code in self.by_name.items():
            short, long = sorted((name, key), key=len)
            if len(short) >= SIMILAR_MIN_LEN and long.endswith(short):
                return code
        return None


def _norm(name: str) -> str:
    return re.sub(r"\s+", "", name)


# 4. 최종 결과 만들기 ----------------------------------------------------------
def finalize(
    data: dict,
    tax: Taxonomy,
    allocator: NewCodeAllocator,
    threshold: float = 0.7,
    *,
    file: str = "",
    prompt_version: str = "",
    model: str = "",
    latency_ms: int | None = None,
) -> dict:
    """검증을 통과한 모델 응답을 회의 문서 3절의 결과 JSON 형식으로 바꾼다."""
    code = data["minor_code"]
    conf = float(data["confidence"])
    proposal = data.get("new_class_proposal")
    proposal = proposal if isinstance(proposal, dict) else {}

    result = {
        "file": file,
        "major": None,
        "minor_code": None,
        "minor_name": None,
        "confidence": round(conf, 4),
        "reasons": list(data.get("reasons") or []),
        "evidence": [
            {
                "page": ev.get("page", 1),
                "bbox": [int(round(v)) for v in _box(ev["bbox_2d"])],
                "label": _text(ev.get("label")) or "",
            }
            for ev in (data.get("evidence") or [])
        ],
        "new_class": None,
        "prompt_version": prompt_version,
        "model": model,
        "latency_ms": latency_ms,
        "status": "confirmed",
        "predicted_code": code,  # 모델이 원래 고른 코드 (평가·오분류 분석용)
    }

    is_etc = code == ETC_CODE
    low_conf = (not is_etc) and conf < threshold

    if not (is_etc or low_conf):
        item = tax.get(code)
        result.update(major=item.major, minor_code=item.code, minor_name=item.name)
        return result

    # 「기타」 처리: NEW-xx 가분류 + 신규 분류 제안
    predicted = tax.get(code)
    name = _text(proposal.get("proposed_name"))
    major = _text(proposal.get("proposed_major"))
    if major not in tax.majors:
        major = predicted.major if (low_conf and predicted) else None
    reason = _text(proposal.get("reason"))
    if low_conf:
        note = f"확신도 {conf:.2f}가 기준 {threshold:.2f} 미만 (모델 1순위: {predicted.code} {predicted.name})"
        reason = f"{reason} / {note}" if reason else note

    new_code = allocator.assign(name)
    result.update(
        major=major or tax.major_of(ETC_CODE),
        minor_code=new_code,
        minor_name=name or "미정 (담당자 지정 필요)",
        status="pending_review",
        new_class={
            "proposed_name": name,
            "proposed_major": major,
            "reason": reason,
            "trigger": "low_confidence" if low_conf else "etc",
        },
    )
    return result
