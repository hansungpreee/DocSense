import re
from collections import Counter

from src.eval import render_expansion as ex

DOCS, ROWS = ex.build_all()


def test_counts_and_split_per_minor():
    assert len(ROWS) == 38 * 25 == len(DOCS)
    for code in {r["minor_code"] for r in ROWS}:
        got = Counter(r["split"] for r in ROWS if r["minor_code"] == code)
        assert got == {"fewshot": 3, "dev": 10, "test": 12}
    assert Counter(r["major_code"] for r in ROWS) == {"FIN": 300, "MGT": 300, "SAL": 350}
    assert len({r["file"] for r in ROWS}) == len(ROWS)


def test_both_layouts_in_every_split():
    for code in {r["minor_code"] for r in ROWS}:
        for split in ("fewshot", "dev", "test"):
            assert {r["template"] for r in ROWS if r["minor_code"] == code and r["split"] == split} == {"양식A", "양식B"}


def test_no_duplicate_documents_and_deterministic():
    html = [h for _, h in DOCS]
    assert len(set(html)) == len(html)  # 숫자만 바꾼 복제가 아니라 내용이 모두 다르다
    assert [h for _, h in ex.build_all(["FIN-11"])[0]] == html[:25]  # 일부만 만들어도 같은 문서


def test_no_answer_hints_in_documents():
    for name, h in DOCS:
        text = re.sub(r"<[^>]+>", " ", h)
        assert not re.search(r"OOD|분류 체계|확장|계획 소분류", text), name
