"""페이지 이미지 입출력: 문서 파일 → 페이지 이미지 목록, 근거 박스 그리기.

    pages = load_pages("FIN-09_감사보고서_003.pdf")       # PDF는 페이지마다 이미지 1장
    pages = load_pages("CUS-02_가맹계약서_001.png")       # 세로로 긴 이미지는 A4 비율로 잘라 여러 장
    pages = load_pages("FIN-09_감사보고서_001_p1.png")    # _p1이면 같은 폴더의 _p2, _p3 …까지 한 문서로 묶음
    pages = load_pages("회의록_001.txt")                   # txt·csv는 글자를 그린 A4 페이지 이미지로 바꿔 같은 방식으로 분류
    pages = load_pages("재직증명서.docx")                  # doc·docx는 LibreOffice로 PDF를 만든 뒤 PDF와 같은 방식
    img = draw_evidence(pages[0], result["evidence"], page=1)

근거 박스 좌표(bbox)는 페이지 이미지의 가로·세로를 각각 0~1000으로 본 상대 좌표다 (Qwen3-VL 출력 형식).
"""
from __future__ import annotations

import csv
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

PDF_DPI = 150  # A4 한 장이 약 1240×1754 픽셀이 된다
A4_RATIO = 297 / 210  # 세로 ÷ 가로
SPLIT_OVER = 1.2  # 세로가 A4 한 장의 1.2배를 넘으면 페이지로 자른다
TEXT_SUFFIXES = {".txt", ".csv"}
OFFICE_SUFFIXES = {".doc", ".docx"}
OFFICE_TIMEOUT = 60  # 변환 한 건 최대 대기(초). 처음 실행은 LibreOffice가 뜨느라 몇 초 걸린다
# PATH에 없을 때 찾아볼 기본 설치 위치 (Windows는 설치해도 PATH에 넣지 않는다)
SOFFICE_PATHS = [r"C:\Program Files\LibreOffice\program\soffice.exe", "/Applications/LibreOffice.app/Contents/MacOS/soffice"]
TEXT_MAX_BYTES = 1_000_000  # 이보다 큰 텍스트 파일은 받지 않는다
CSV_MAX_ROWS = 200  # csv는 앞 200행만 그린다
TEXT_MAX_PAGES = 5  # 텍스트는 앞 5쪽(약 200줄)까지만 그린다. 분류에는 앞부분이면 충분하고, 요청 크기를 제한한다
TEXT_FONT, TEXT_LINE, TEXT_MARGIN = 26, 38, 80  # 글자 크기·줄 높이·여백(픽셀, A4 1240×1754 기준)
FIRST_PAGE = re.compile(r"_p1(\.(?:png|jpe?g))$", re.IGNORECASE)  # 데이터셋의 여러 쪽 문서: 이름_p1.png, _p2.png …


def load_pages(path: str | Path, dpi: int = PDF_DPI) -> list[Image.Image]:
    """PDF는 페이지 순서대로 RGB 이미지 목록으로 돌려준다.
    이미지 파일은 1장으로 보되, 여러 페이지를 세로로 이어 붙인 긴 이미지(전체 화면 캡처)는
    A4 비율 조각으로 잘라 페이지처럼 돌려준다. 그대로 보내면 API가 크게 줄여 글씨를 못 읽는다."""
    # ponytail: 페이지 수 제한 없음; 수십 페이지 PDF에서 요청 크기·비용 문제가 확인되면 상한 도입
    path = Path(path)
    if path.suffix.lower() in TEXT_SUFFIXES:
        return render_text(path)
    if path.suffix.lower() in OFFICE_SUFFIXES:
        with tempfile.TemporaryDirectory() as tmp:
            return load_pages(office_to_pdf(path, Path(tmp)), dpi)
    if path.suffix.lower() == ".pdf":
        import pymupdf

        with pymupdf.open(path) as doc:
            pixmaps = [pg.get_pixmap(dpi=dpi) for pg in doc]
        if not pixmaps:
            raise ValueError(f"PDF에 페이지가 없습니다: {path.name}")
        return [Image.frombytes("RGB", (pix.width, pix.height), pix.samples) for pix in pixmaps]

    pages = []
    for part in page_files(path):
        try:
            with Image.open(part) as img:
                pages += split_tall(img.convert("RGB"))
        except UnidentifiedImageError:
            raise ValueError(f"이미지나 PDF로 읽을 수 없는 파일입니다 (PNG·JPG·PDF 지원): {part.name}") from None
    return pages


def office_to_pdf(path: Path, out_dir: Path) -> Path:
    """doc·docx를 LibreOffice(headless)로 out_dir에 PDF로 바꿔 그 경로를 돌려준다."""
    # ponytail: 변환마다 LibreOffice를 새로 띄움(건당 약 2초); 일괄 분류에서 느리다고 확인되면 상주 프로세스 도입
    soffice = shutil.which("soffice") or next((p for p in SOFFICE_PATHS if Path(p).is_file()), None)
    if not soffice:
        raise ValueError(f"DOC·DOCX를 읽으려면 LibreOffice를 설치해야 합니다: {path.name}")
    # 사용자 프로필을 임시 폴더에 따로 둔다: 사용자가 LibreOffice를 열어 둔 상태에서도 변환이 막히지 않게
    profile = (out_dir / "profile").resolve().as_uri()
    cmd = [soffice, f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf",
           "--outdir", str(out_dir), str(path)]
    try:
        subprocess.run(cmd, capture_output=True, timeout=OFFICE_TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        raise ValueError(f"DOC·DOCX 변환이 {OFFICE_TIMEOUT}초 안에 끝나지 않았습니다: {path.name}") from None
    pdf = out_dir / f"{path.stem}.pdf"
    if not pdf.is_file():  # 손상·암호 걸린 문서는 LibreOffice가 오류 코드 없이 결과만 안 만든다
        raise ValueError(f"DOC·DOCX를 PDF로 바꾸지 못했습니다 (손상되었거나 암호가 걸린 문서일 수 있습니다): {path.name}")
    return pdf


def read_text(path: Path) -> list[str]:
    """txt·csv를 줄 목록으로 읽는다. csv는 칸을 " | "로 이어 한 줄로 만든다. 인코딩은 UTF-8(BOM 포함) → CP949 순."""
    if path.stat().st_size > TEXT_MAX_BYTES:
        raise ValueError(f"텍스트 파일이 너무 큽니다 (1MB 이하만 지원): {path.name}")
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"글자를 읽을 수 없는 파일입니다 (UTF-8 또는 CP949만 지원): {path.name}")
    if not text.strip():
        raise ValueError(f"내용이 비어 있는 파일입니다: {path.name}")
    if path.suffix.lower() == ".csv":
        rows = csv.reader(text.splitlines())
        return [" | ".join(cell.strip() for cell in row) for _, row in zip(range(CSV_MAX_ROWS), rows)]
    return text.splitlines()


def render_text(path: Path) -> list[Image.Image]:
    """txt·csv 내용을 흰 바탕 A4 비율 이미지로 그린다 (긴 줄은 줄바꿈, 앞 TEXT_MAX_PAGES쪽까지)."""
    # ponytail: 표 서식 없이 글자만 그림; csv 칸 정렬이 오분류를 일으킨다고 확인되면 칸 너비 맞춤 도입
    # 한계: 한글 글꼴을 하나도 못 찾으면 한글이 깨진 이미지가 그대로 분류된다(오류로 알리지 않음). 글꼴 탐색은 _font() 참고;
    # 서버에 글꼴이 없는 환경이 확인되면 여기서 오류로 바꾼다
    w, h = 1240, round(1240 * A4_RATIO)
    font = _font(TEXT_FONT)
    max_w = w - 2 * TEXT_MARGIN
    lines = []
    for raw in read_text(path):
        line = ""
        for ch in raw.expandtabs(4) or " ":
            if line and font.getlength(line + ch) > max_w:
                lines.append(line)
                line = ch
            else:
                line += ch
        lines.append(line)
    per_page = (h - 2 * TEXT_MARGIN) // TEXT_LINE
    pages = []
    for start in range(0, min(len(lines), per_page * TEXT_MAX_PAGES), per_page):
        img = Image.new("RGB", (w, h), "white")
        draw = ImageDraw.Draw(img)
        for i, line in enumerate(lines[start:start + per_page]):
            draw.text((TEXT_MARGIN, TEXT_MARGIN + i * TEXT_LINE), line, fill="black", font=font)
        pages.append(img)
    return pages


def page_files(path: Path) -> list[Path]:
    """`이름_p1.png`이면 같은 폴더의 `이름_p2.png`, `_p3.png` …를 번호가 끊길 때까지 모은다. 그 외에는 그 파일 하나."""
    m = FIRST_PAGE.search(path.name)
    if not m:
        return [path]
    stem, ext = path.name[: m.start()], m.group(1)
    files = [path]
    while (nxt := path.with_name(f"{stem}_p{len(files) + 1}{ext}")).is_file():
        files.append(nxt)
    return files


def split_tall(img: Image.Image) -> list[Image.Image]:
    """세로로 긴 이미지를 같은 높이의 A4 비율 조각으로 나눈다. 짧으면 그대로 1장."""
    # ponytail: 겹침 없이 자름; 경계에 걸린 제목·표 행 때문에 오분류가 확인되면 조각 사이 겹침 도입
    w, h = img.size
    page_h = round(w * A4_RATIO)
    if h <= page_h * SPLIT_OVER:
        return [img]
    n = -(-h // page_h)  # 올림
    step = -(-h // n)
    return [img.crop((0, top, w, min(top + step, h))) for top in range(0, h, step)]


def draw_evidence(img: Image.Image, evidence: list[dict], page: int = 1) -> Image.Image:
    """원본을 바꾸지 않고, 해당 페이지의 근거 박스와 이름을 그린 사본을 돌려준다."""
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    font = _font(max(14, w // 60))
    for e in evidence:
        if e.get("page", 1) != page or len(e.get("bbox", [])) != 4:
            continue
        x1, y1, x2, y2 = e["bbox"]
        box = [x1 / 1000 * w, y1 / 1000 * h, x2 / 1000 * w, y2 / 1000 * h]
        if box[2] <= box[0] or box[3] <= box[1]:
            continue  # 잘못된 좌표는 그리지 않고 텍스트 근거만 보여준다
        draw.rectangle(box, outline=(220, 38, 38), width=max(3, w // 300))
        draw.text((box[0], max(box[1] - font.size - 4, 0)), e.get("label", ""), fill=(220, 38, 38), font=font)
    return img


@lru_cache(maxsize=8)
def _font(size: int):
    """한글 라벨용 글꼴. 없으면 기본 글꼴(한글은 깨져 보임)을 쓴다."""
    for name in ("NanumGothic.ttf", "malgun.ttf", "AppleGothic.ttf", "NotoSansCJK-Regular.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)
