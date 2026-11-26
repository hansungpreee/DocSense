"""doc·docx 지원 테스트: LibreOffice로 PDF를 만든 뒤 PDF 경로로 읽는 pages.office_to_pdf. 실제 API는 부르지 않는다."""
import shutil
import subprocess

import pytest

from src.engine import pages


def test_no_libreoffice_raises_korean_message(tmp_path, monkeypatch):
    monkeypatch.setattr(pages.shutil, "which", lambda name: None)
    monkeypatch.setattr(pages, "SOFFICE_PATHS", [])
    f = tmp_path / "재직증명서.docx"
    f.write_bytes(b"x")
    with pytest.raises(ValueError, match="LibreOffice를 설치"):
        pages.load_pages(f)


def test_conversion_without_output_raises(tmp_path, monkeypatch):
    # 손상·암호 문서: LibreOffice가 PDF를 만들지 않고 끝난다
    monkeypatch.setattr(pages.shutil, "which", lambda name: "soffice")
    monkeypatch.setattr(pages.subprocess, "run", lambda *a, **k: None)
    f = tmp_path / "깨진문서.doc"
    f.write_bytes(b"x")
    with pytest.raises(ValueError, match="PDF로 바꾸지 못했습니다"):
        pages.load_pages(f)


def test_timeout_raises(tmp_path, monkeypatch):
    def slow(*a, **k):
        raise subprocess.TimeoutExpired("soffice", pages.OFFICE_TIMEOUT)

    monkeypatch.setattr(pages.shutil, "which", lambda name: "soffice")
    monkeypatch.setattr(pages.subprocess, "run", slow)
    f = tmp_path / "a.docx"
    f.write_bytes(b"x")
    with pytest.raises(ValueError, match="끝나지 않았습니다"):
        pages.load_pages(f)


@pytest.mark.skipif(not shutil.which("soffice"), reason="LibreOffice 미설치")
@pytest.mark.parametrize("fmt, suffix", [("docx", ".docx"), ("doc:MS Word 97", ".doc")])
def test_real_conversion_gives_page_images(tmp_path, fmt, suffix):
    src = tmp_path / "재직증명서.txt"
    src.write_text("재직증명서\n성명: 홍길동\n위 사람은 당사에 재직 중임을 증명합니다.", encoding="utf-8")
    made = tmp_path / "made"
    subprocess.run(["soffice", "--headless", "--convert-to", fmt, "--outdir", str(made), str(src)],
                   capture_output=True, timeout=120)
    doc = made / f"재직증명서{suffix}"
    assert doc.is_file()
    out = pages.load_pages(doc)
    assert len(out) == 1 and out[0].size[0] > 1000  # A4 150dpi 약 1240px
    assert out[0].convert("L").getextrema()[0] < 255  # 글자가 그려졌다
