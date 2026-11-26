"""개발셋(dev) 264건만으로 더 어려운 하드셋(hard2)을 만든다. 기존 하드셋(augment.py)은 그대로 둔다.

실행 (저장소 루트): python src/eval/augment_hard2.py
결과: data/images/hard2_dev/ (PNG, .gitignore), data/meta/hard2_dev_variants.csv (문서별 변형 기록)

- 기존 hard(기울기 ±2.5°·노이즈 σ12·블러 1.2·그림자)가 새 모델에서 100%라 변별력이 없어서 만든다 (10-12).
- 변형 4종은 실제 스캔·촬영에서 생기는 것 중 더 센 것으로 고른다. 문서 순서대로 4종을 돌아가며 쓰고,
  여러 쪽 문서는 모든 쪽에 같은 변형을 준다 (변형별 정확도를 문서 단위로 내기 위해).
- dev만 만든다. 테스트셋(split=test)은 이 스크립트가 열지 않는다. 테스트셋에도 hard2를 둘지는 팀이 정한다.
- 시드 고정이라 다시 실행해도 같은 이미지가 나온다.
"""
import csv
import io
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
CLEAN_DIR = ROOT / "data" / "images" / "clean"
OUT_DIR = ROOT / "data" / "images" / "hard2_dev"
LABELS = ROOT / "data" / "meta" / "labels.csv"
VARIANTS_CSV = ROOT / "data" / "meta" / "hard2_dev_variants.csv"
SEED = 2026

VARIANTS = ["저해상도 JPEG", "상단 잘림", "촬영 원근 왜곡", "흐린 복사본"]  # 문서 순서 % 4
PAPER = (238, 236, 230)


def low_res_jpeg(img: Image.Image, rng: random.Random) -> Image.Image:
    """저해상도 스캔(약 70~80dpi)을 JPEG 저품질로 저장한 것. 크기는 줄인 그대로 둔다."""
    scale = rng.uniform(0.35, 0.4)
    small = img.resize((int(img.width * scale), int(img.height * scale)), Image.BILINEAR)
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=rng.randint(20, 30))
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def top_cropped(img: Image.Image, rng: random.Random) -> Image.Image:
    """촬영·스캔 때 위쪽이 잘린 것. 위 8~12%를 자른다 (큰 제목이 잘릴 수 있음)."""
    cut = int(img.height * rng.uniform(0.08, 0.12))
    return img.crop((0, cut, img.width, img.height))


def perspective_photo(img: Image.Image, rng: random.Random) -> Image.Image:
    """휴대폰으로 비스듬히 찍은 것: 원근 왜곡 + 기울기 4~6° + 한쪽 그림자."""
    w, h = img.size
    d = int(w * rng.uniform(0.05, 0.08))  # 위쪽이 좁아지는 사다리꼴
    # PERSPECTIVE 계수: 출력 좌표 → 입력 좌표. 네 모서리를 맞추는 계수를 구한다
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    dst = [(d, 0), (w - d, 0), (w, h), (0, h)]
    a = []
    for (x, y), (u, v) in zip(dst, src):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    coeffs = np.linalg.solve(np.array(a, dtype=float), np.array([c for p in src for c in p], dtype=float))
    img = img.transform((w, h), Image.PERSPECTIVE, tuple(coeffs), Image.BICUBIC, fillcolor=PAPER)
    img = img.rotate(rng.choice([-1, 1]) * rng.uniform(4, 6), resample=Image.BICUBIC, fillcolor=PAPER)
    arr = np.asarray(img, dtype=np.float32)
    shade = np.linspace(0.6, 1.0, w).reshape(1, w, 1)
    return Image.fromarray(np.clip(arr * shade, 0, 255).astype(np.uint8))


def blurry_copy(img: Image.Image, rng: random.Random) -> Image.Image:
    """여러 번 복사한 흐린 문서: 블러 2.0 + 대비 0.65 + 노이즈 σ25."""
    img = img.filter(ImageFilter.GaussianBlur(radius=2.0))
    img = ImageEnhance.Contrast(img).enhance(0.65)
    arr = np.asarray(img, dtype=np.float32)
    noise = np.random.default_rng(rng.randrange(1 << 30)).normal(0, 25, arr.shape)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))


TRANSFORMS = [low_res_jpeg, top_cropped, perspective_photo, blurry_copy]


def dev_documents() -> list[str]:
    """labels.csv의 dev 문서 파일명 (여러 쪽 문서는 _p1 파일). test 줄은 이름만 건너뛰고 열지 않는다."""
    with LABELS.open(encoding="utf-8-sig") as f:
        return sorted(r["file"] for r in csv.DictReader(f) if r["split"] == "dev")


def pages_of(first: str) -> list[str]:
    """`이름_p1.png`이면 `_p2`, `_p3` …를 끊길 때까지 모은다 (src/engine/pages.py와 같은 규칙)."""
    if not first.endswith("_p1.png"):
        return [first]
    stem, pages, n = first[: -len("_p1.png")], [], 1
    while (CLEAN_DIR / f"{stem}_p{n}.png").exists():
        pages.append(f"{stem}_p{n}.png")
        n += 1
    return pages


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    rows, n_pages = [], 0
    for idx, doc in enumerate(dev_documents()):
        variant = idx % len(VARIANTS)
        for page in pages_of(doc):
            with Image.open(CLEAN_DIR / page) as im:
                TRANSFORMS[variant](im.convert("RGB"), rng).save(OUT_DIR / page, "PNG")
            n_pages += 1
        rows.append([doc, VARIANTS[variant]])
    with VARIANTS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows([["file", "variant"], *rows])
    print(f"hard2(dev) {len(rows)}건 · {n_pages}장 → {OUT_DIR}, 변형 기록 → {VARIANTS_CSV}")


if __name__ == "__main__":
    main()
