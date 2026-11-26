"""화면 번역 사전 점검 (Streamlit 필요). 실행: python -m pytest tests -q"""
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import i18n  # noqa: E402
import services  # noqa: E402


def fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_placeholders_match_between_ko_and_en():
    for ko, en in i18n.EN.items():
        assert fields(ko) == fields(en), ko  # 한국어와 영어의 {자리표시자}가 같아야 format()이 깨지지 않는다


def test_every_major_minor_and_department_is_translated():
    # 내 PC의 data/db 복사본(데모에서 승인한 분류)이 아니라 저장소의 원본 분류 체계로 검사한다
    tax = services.load_taxonomy(services.DEFAULT_PATH)
    names = {i.major for i in tax.classifiable_items} | {i.name for i in tax.classifiable_items}
    names |= {e["department"] for e in services._load_employees()["employees"]}
    assert not [n for n in names if n not in i18n.EN and n != "기타"]
