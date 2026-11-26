import os
import csv
import random
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance

def find_project_root():
    candidates = [
        os.getcwd(),
        os.path.dirname(os.path.abspath(__file__)),
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ]
    for path in candidates:
        if os.path.exists(os.path.join(path, "config", "taxonomy.yaml")):
            return path
    return os.getcwd()

BASE_DIR = find_project_root()
clean_dir = os.path.join(BASE_DIR, "data", "images", "clean")
hard_dir = os.path.join(BASE_DIR, "data", "images", "hard")
os.makedirs(hard_dir, exist_ok=True)

random.seed(42)
np.random.seed(42)

VARIANTS = ["스캔 기울어짐", "저화질 노이즈", "초점 흐림", "촬영 그림자"]  # idx % 4 순서
VARIANTS_CSV = os.path.join(BASE_DIR, "data", "meta", "hard_variants.csv")


def write_variants(files: list[str], path: str = VARIANTS_CSV) -> None:
    """하드셋 파일마다 어떤 변형을 적용했는지 기록한다 (변형별 정확도 계산용)."""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["file", "variant"])
        writer.writerows([fname, VARIANTS[idx % 4]] for idx, fname in enumerate(files))


def augment_image(img: Image.Image, idx: int) -> Image.Image:
    img = img.convert("RGB")
    mode = idx % 4  # 4가지 변형 패턴을 골고루 적용

    if mode == 0:
        # 1) 스캔 기울어짐 (미세 회전 + 약한 블러)
        angle = random.choice([-2.5, -1.8, 1.8, 2.5])
        img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(245, 245, 245))
        img = img.filter(ImageFilter.GaussianBlur(radius=0.6))

    elif mode == 1:
        # 2) 저화질 팩스/스캔 노이즈 (가우시안 노이즈 + 대비 감소)
        img = ImageEnhance.Contrast(img).enhance(0.85)
        arr = np.array(img, dtype=np.float32)
        noise = np.random.normal(0, 12, arr.shape)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)

    elif mode == 2:
        # 3) 초점 흐림 (가우시안 블러 + 밝기 저하)
        img = img.filter(ImageFilter.GaussianBlur(radius=1.2))
        img = ImageEnhance.Brightness(img).enhance(0.9)

    else:
        # 4) 스마트폰 촬영 그림자 효과 + 미세 회전
        angle = random.choice([-1.5, 1.5])
        img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(240, 240, 240))
        arr = np.array(img, dtype=np.float32)
        h, w, _ = arr.shape
        # 가로 방향 조명 그라데이션 적용
        gradient = np.linspace(0.75, 1.05, w).reshape(1, w, 1)
        arr = np.clip(arr * gradient, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)

    return img

files = sorted([f for f in os.listdir(clean_dir) if f.endswith(".png")])
for idx, fname in enumerate(files):
    src_path = os.path.join(clean_dir, fname)
    dst_path = os.path.join(hard_dir, fname)
    with Image.open(src_path) as im:
        hard_im = augment_image(im, idx)
        hard_im.save(dst_path, "PNG")

write_variants(files)
print(f"✅ 하드셋 생성 완료! 총 {len(files)}장 -> 저장 위치: {hard_dir}, 변형 기록: {VARIANTS_CSV}")