"""txt·csv 업로드 지원 테스트: 글자를 이미지로 그리는 pages.render_text와 데모 업로드 연결. 실제 API는 부르지 않는다."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import services  # noqa: E402
from src.db.store import SqliteStore  # noqa: E402
from src.engine import pages  # noqa: E402


def test_txt_becomes_one_a4_page(tmp_path):
    f = tmp_path / "회의록_001.txt"
    f.write_text("회의록\n일시: 2026-11-12\n안건: 분류 체계 확정", encoding="utf-8")
    out = pages.load_pages(f)
    assert len(out) == 1 and out[0].size == (1240, 1754)
    assert out[0].convert("L").getextrema()[0] < 255  # 글자가 그려졌다


def test_csv_cells_joined_and_cp949_read(tmp_path):
    f = tmp_path / "재고_001.csv"
    f.write_bytes("품목,수량\n새우깡,10\n".encode("cp949"))
    assert pages.read_text(f) == ["품목 | 수량", "새우깡 | 10"]


def test_utf8_bom_removed(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes("﻿제목".encode("utf-8"))
    assert pages.read_text(f) == ["제목"]


def test_long_text_cut_to_max_pages(tmp_path):
    f = tmp_path / "긴글.txt"
    f.write_text("\n".join(f"{i}번째 줄" for i in range(1000)), encoding="utf-8")
    assert len(pages.load_pages(f)) == pages.TEXT_MAX_PAGES


def test_long_line_wraps_inside_margin(tmp_path):
    f = tmp_path / "한줄.txt"
    f.write_text("가" * 300, encoding="utf-8")
    assert len(pages.read_text(f)) == 1  # 줄바꿈은 그릴 때 하고, 읽기는 원래 줄 단위
    img = pages.load_pages(f)[0].convert("L")
    assert img.crop((1240 - pages.TEXT_MARGIN + 10, 0, 1240, 1754)).getextrema()[0] == 255  # 오른쪽 여백에는 글자가 없다


# id를 직접 붙인다: 1MB짜리 바이트가 테스트 이름에 들어가면 Windows에서 PYTEST_CURRENT_TEST가 32,767자를 넘어 오류가 난다
@pytest.mark.parametrize("name, data, msg", [
    pytest.param("빈파일.txt", b"  \n", "비어", id="빈파일"),
    pytest.param("깨짐.txt", b"\xff\xfe\x00\xd8\xff", "읽을 수 없는", id="깨짐"),
    pytest.param("큼.txt", b"a" * (pages.TEXT_MAX_BYTES + 1), "너무 큽니다", id="큼"),
])
def test_bad_text_files_raise_korean_message(tmp_path, name, data, msg):
    f = tmp_path / name
    f.write_bytes(data)
    with pytest.raises(ValueError, match=msg):
        pages.load_pages(f)


def test_csv_rows_limited(tmp_path):
    f = tmp_path / "많음.csv"
    f.write_text("\n".join(f"a,{i}" for i in range(500)), encoding="utf-8")
    assert len(pages.read_text(f)) == pages.CSV_MAX_ROWS


def test_demo_accepts_txt_csv_and_classifies_in_mock(tmp_path, monkeypatch):
    assert {"txt", "csv"} <= set(services.SUPPORTED)
    monkeypatch.setattr(services, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(services, "MIN_INTERVAL", 0.0)
    monkeypatch.setenv("DEMO_MOCK", "1")
    store = SqliteStore(":memory:", services.taxonomy())
    path, digest = services.save_upload("메모.txt", "견적서\n품목 단가".encode("utf-8"))
    assert services.classify(path, digest, store)["status"] != "error"
    path, digest = services.save_upload("빈.txt", b"")
    r = services.classify(path, digest, store)
    assert r["status"] == "error" and "비어" in r["errors"][0]  # 빈 파일은 한국어 오류 결과 (화면에 예외가 올라가지 않는다)
