"""프롬프트 빌더.

버전별 차이는 PROMPT_VERSIONS 설정으로만 관리한다. 실험 버전을 바꿀 때 코드를 고치지 않고
`--prompt v2`처럼 버전 이름만 바꾸면 된다 (PRD 8절 단계별 성능 비교표).

    v1: 분류 체계 목록(대분류, 코드, 소분류명)만 제공  → zero-shot 기준선
    v2: v1 + 소분류 정의(definition)
    v3: v2 + 헷갈리는 쌍 구분 가이드 (PAIR_GUIDE)
    vFinal: v2 + 판단 순서를 「제목 먼저」에서 「내용(항목·서식·본문) 중심, 제목은 참고」로 바꿈
            (v3의 쌍 가이드는 LEG-01/02를 제목으로만 고르게 해 이 방향과 맞지 않아 넣지 않는다)
            + 예외 규칙(EXCEPTION_RULES, 11/16): dev 약점 사례에서 뽑은 일반 원칙 5개.
            vFinal은 버전을 늘리지 않고 이 한 곳에서 고친다(10/29 결정). 고치기 전 측정은 커밋 d795bb1의 vFinal.

완성된 프롬프트 확인 (API 호출 없음): python -m src.engine.prompt v1
"""
from __future__ import annotations

import base64
import io
import sys
from dataclasses import dataclass

from PIL import Image

from .taxonomy import ETC_CODE, Taxonomy, format_taxonomy, load_taxonomy


@dataclass(frozen=True)
class PromptConfig:
    include_definition: bool
    include_pair_guide: bool = False
    content_first: bool = False


PROMPT_VERSIONS: dict[str, PromptConfig] = {
    "v1": PromptConfig(include_definition=False),
    "v2": PromptConfig(include_definition=True),
    "v3": PromptConfig(include_definition=True, include_pair_guide=True),
    "vFinal": PromptConfig(include_definition=True, content_first=True),
    # v4 이후(few-shot, 2단계 분류)는 여기에 옵션을 추가한다.
}

# 초판(58d9611)은 v3_clean_r1·r2에서 LEG-02를 못 올렸고 LEG-01 오류 6건을 냈다: 제목을 minor_name에 옮겨 씀(2),
# 큰따옴표 안 작은따옴표를 \'로 출력(4). 그래서 따옴표 대신 「」를 쓰고, 제목 옮겨 적기·minor_name 규칙을 넣었다.
# 개발셋 오분류에서 나온 쌍만 넣는다 (v2_clean_r1: LEG-02 4건이 제목 비교가 꼬여 「기타」로 빠짐,
# v2_clean_r2: 제목을 '없다'고 본 뒤 본문 항목으로 LEG-01↔LEG-02를 바꿔 고르거나 머리글을 '라벨일 뿐'이라 버림).
# "~가 아님"을 되풀이하다 꼬이는 일이 있어 판정 규칙을 긍정형으로 쓴다.
# 코드는 taxonomy.yaml에 있는지 tests/test_engine.py가 확인한다.
PAIR_GUIDE = """헷갈리기 쉬운 문서 구분
- LEG-01 상가건물 임대차계약서와 LEG-02 표준임대차계약서는 본문 서식(임차 상가건물의 표시, 환산보증금, 관리비, 특약)이 똑같다. 본문 항목은 판단에 쓰지 않고 문서 제목으로만 고른다.
  1. 맨 위 가운데 큰 글씨 제목을 보이는 글자 그대로 reasons 첫 문장에 옮겨 적는다. 오른쪽 위 ■ 뒤 작은 머리글에도 같은 제목이 있다.
  2. 옮겨 적은 제목이 「상가건물 임대차 표준계약서」이면 LEG-01, 「표준임대차계약서」이면 LEG-02다.
  3. 빌린 곳이 창고·냉장창고·사무실이어도 제목대로 고른다. 두 제목 중 하나가 보이면 「기타」가 아니다.
  4. minor_name에는 문서 제목이 아니라 분류 체계 이름(상가건물 임대차계약서 또는 표준임대차계약서)을 쓴다."""

# 좌표 자리에 숫자 예시를 넣으면 모델이 그 값을 그대로 베끼기 쉬워 [x1, y1, x2, y2] 자리표시자로 쓴다.
# reasons를 맨 앞에 둔다: 코드를 먼저 쓰게 하면 근거는 손익계산서인데 코드는 FIN-02처럼 어긋나는 일이 있었다.
OUTPUT_FORMAT = """{
  "reasons": ["판단 근거 문장", "..."],
  "minor_name": "근거에 맞는 소분류 이름 (분류 체계에 적힌 이름 그대로)",
  "minor_code": "그 소분류 이름 바로 앞에 적힌 코드",
  "major": "그 소분류가 속한 대분류 이름 (분류 체계의 [ ] 안 이름 그대로)",
  "confidence": 0.0~1.0 사이 숫자 (이 판정이 맞을 확률에 대한 너의 추정),
  "evidence": [{"page": 페이지 번호, "bbox_2d": [x1, y1, x2, y2], "label": "근거 영역 이름 (예: 문서 제목)"}],
  "new_class_proposal": null 또는 {
    "proposed_name": "새 문서 종류 이름",
    "proposed_major": "가장 가까운 대분류 이름",
    "reason": "새 분류가 필요한 이유"
  }
}"""

JUDGE_TITLE_FIRST = """판단 순서
1. 문서 제목과 표제를 먼저 본다.
2. 제목이 없거나 애매하면 서식 구조(표 구성, 서명·날인란, 항목 배치)를 본다.
3. 마지막으로 본문 키워드를 본다. 금액·거래처·계약 같은 공통 단어만으로 판단하지 않는다."""

# vFinal: 줄글 하드셋(제목 없음·잘림)에서 제목에 기대다 「기타」로 빠지는 오답이 많아 내용 중심으로 바꾼다.
JUDGE_CONTENT_FIRST = """판단 순서
1. 문서에 실제로 적힌 항목명, 표 구성, 서명·날인·결재란, 본문 내용을 먼저 보고 이 문서가 무엇을 하는 문서인지 판단한다.
2. 그 내용이 각 소분류 정의의 특징과 맞는지 대조해 고른다. 닮은 소분류가 있으면 정의에 적힌 차이로 가른다.
3. 제목은 참고로만 쓴다. 제목이 없거나 잘렸거나 내용과 다르면 내용을 따른다.
4. 금액·거래처·계약 같은 공통 단어만으로 판단하지 않는다."""

# vFinal 예외 규칙. 특정 파일이 아니라 오답 유형마다 하나씩 쓴다. 근거 사례는 results/prompt_tune/README.md.
# 1: 줄글·메모를 「양식이 아니다」라며 「기타」로 보냄 (줄글 HR-03·SAL-03, 다듬은 줄글 9건)
# 2: 제목에 부제가 붙은 문서를 기존 이름 그대로 새 분류로 제안 (hard2 FIN-07 「/ 지급명세서」)
# 3: 당사자·금액 칸만 보고 다른 거래 문서로 고름 (줄글 견적서 → 세금계산서)
# 4: 항목 몇 개가 닮은 분류 체계 밖 문서를 확정 (개발용 OOD 출장결과보고서·고객사과문발송대장)
#    2회차에 제목 있는 문서로 범위를 좁혀 봤으나(줄글 SAL-04_H2는 고쳐짐) 다른 줄글 SAL-05_H2가 같은 이유로 빠져
#    효과가 없어 1회차 문장으로 되돌림 (results/prompt_tune/README.md 2회차)
# 5: 구분 근거가 잘리거나 없는 페이지를 높은 확신도로 확정 (hard2 상단 잘린 임대차, 줄글 빈 페이지)
#    2회차에 「본문 서식이 같은 소분류는 제목을 읽었을 때만」을 덧붙였으나 잘린 임대차 3건이 그대로 0.95여서 되돌림.
#    모델이 제목이 잘린 것을 알아채지 못해(근거 문장에 제목 언급 없음) 프롬프트로는 못 고치는 한계로 남긴다
EXCEPTION_RULES = """예외 규칙 (판단 순서보다 앞선다)
1. 표·칸이 있는 양식이 아니라 문장으로 풀어 쓴 글, 메모, 다른 문서의 내용을 「~라고 적혀 있다」처럼 옮겨 적은 글도 담긴 항목과 목적이 어떤 소분류 정의와 맞으면 그 소분류다. 「실제 양식이 아니다」, 「서술형이다」, 「내용을 설명하는 메모다」는 「기타」로 보낼 이유가 아니다.
2. 제목이 소분류 이름과 같거나, 이름 뒤에 부제·겸용 표기(「/ ○○」, 「(○○ 겸용)」)·연도·회사명이 붙었거나, 띄어쓰기만 다르면 그 소분류다. 「기타」로 답하면서 제안하려는 새 이름이 기존 소분류 이름과 같거나 그 이름을 포함하면 「기타」가 아니라 그 소분류를 고른다.
3. 당사자 정보(상호·사업자등록번호·대표자·주소), 금액·세액 합계, 품목·수량·단가 표, 날짜는 여러 소분류에 공통으로 나온다. 이것만으로 고르지 말고, 정의에 적힌 그 소분류만의 항목과 목적(무엇을 제시·증명·요청·보고·기록하는가)이 문서에 있는지로 가른다.
4. 항목 몇 개가 정의와 닮아도, 문서가 스스로 밝힌 이름과 목적이 그 소분류와 다른 별개의 업무 문서이면 그 소분류가 아니다. 목적까지 맞는 소분류가 없으면 「기타」로 답한다.
5. 페이지가 잘리거나 거의 비어서 소분류를 가르는 근거(정의가 구분 기준으로 든 제목·머리글·고유 항목)가 이미지에 보이지 않으면, 남은 내용에 가장 가까운 소분류를 고르되 confidence를 {threshold} 미만으로 준다. 보이지 않는 근거를 짐작해 높은 확신도로 답하지 않는다."""

SYSTEM_TEMPLATE = """너는 HS리테일 총무팀의 문서 분류 담당자다.
첨부된 문서 이미지(여러 장이면 같은 문서의 페이지들)를 보고, 아래 분류 체계에서 가장 알맞은 소분류 하나를 고른다.

{judge_order}

분류 체계
{taxonomy}
{pair_guide}
「기타」 규칙
- 위 소분류 어디에도 해당하지 않으면 minor_code를 {etc_code}로, major를 "{etc_major}"로 답한다.
- {etc_code}로 답하거나 confidence가 {threshold} 미만이면 new_class_proposal을 반드시 채운다.
  그 외에는 new_class_proposal을 null로 둔다.

출력 형식
- 아래 형식의 JSON 객체 하나만 출력한다. 코드블록, 설명 문장을 붙이지 않는다.
- 근거(reasons)를 먼저 쓰고, 그 근거가 가리키는 소분류의 이름과 코드를 분류 체계에서 그대로 옮겨 쓴다.
- evidence는 판단 근거가 된 영역 1~3개다. page는 1부터 세는 페이지 번호다.
- bbox_2d는 그 페이지 이미지에서 영역의 왼쪽 위 꼭짓점(x1, y1)과 오른쪽 아래 꼭짓점(x2, y2)이다.
  이미지의 가로와 세로를 각각 0~1000으로 본 상대 좌표(정수)로 쓴다.

{output_format}"""


def judge_order(cfg: PromptConfig, threshold: float) -> str:
    if not cfg.content_first:
        return JUDGE_TITLE_FIRST
    return JUDGE_CONTENT_FIRST + "\n\n" + EXCEPTION_RULES.format(threshold=threshold)


def build_system_prompt(tax: Taxonomy, version: str = "v1", threshold: float = 0.7) -> str:
    if version not in PROMPT_VERSIONS:
        raise KeyError(f"알 수 없는 프롬프트 버전: {version} (가능: {', '.join(PROMPT_VERSIONS)})")
    cfg = PROMPT_VERSIONS[version]
    return SYSTEM_TEMPLATE.format(
        judge_order=judge_order(cfg, threshold),
        taxonomy=format_taxonomy(tax, include_definition=cfg.include_definition),
        pair_guide=f"\n{PAIR_GUIDE}\n" if cfg.include_pair_guide else "",
        etc_code=ETC_CODE,
        etc_major=tax.major_of(ETC_CODE),
        threshold=threshold,
        output_format=OUTPUT_FORMAT,
    )


def image_to_data_url(img: Image.Image) -> str:
    # ponytail: 원본 해상도 그대로 PNG로 보냄; 휴대폰 사진처럼 큰 이미지에서 요청 크기 오류가 나면 축소·JPEG 도입
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def build_messages(
    pages: list[Image.Image], tax: Taxonomy, version: str = "v1", threshold: float = 0.7
) -> list[dict]:
    """OpenAI 호환 chat 메시지. 페이지마다 번호 문구와 이미지를 순서대로 넣어 evidence의 page 기준을 맞춘다."""
    content: list[dict] = []
    for no, page in enumerate(pages, start=1):
        content.append({"type": "text", "text": f"[{no}페이지]"})
        content.append({"type": "image_url", "image_url": {"url": image_to_data_url(page)}})
    content.append({"type": "text", "text": f"이 문서({len(pages)}페이지)를 분류하라."})
    return [
        {"role": "system", "content": build_system_prompt(tax, version, threshold)},
        {"role": "user", "content": content},
    ]


if __name__ == "__main__":
    print(build_system_prompt(load_taxonomy(), sys.argv[1] if len(sys.argv) > 1 else "v1"))
