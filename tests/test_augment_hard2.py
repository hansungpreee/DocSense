import random
import re
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "eval"))
import augment_hard2 as hard2  # noqa: E402


def test_pages_of_collects_numbered_pages(tmp_path, monkeypatch):
    monkeypatch.setattr(hard2, "CLEAN_DIR", tmp_path)
    for name in ["A_001_p1.png", "A_001_p2.png", "A_001_p4.png", "B_002.png"]:
        (tmp_path / name).touch()
    assert hard2.pages_of("A_001_p1.png") == ["A_001_p1.png", "A_001_p2.png"]  # 번호가 끊기면 멈춤
    assert hard2.pages_of("B_002.png") == ["B_002.png"]


def test_dev_documents_are_dev_only():
    docs = hard2.dev_documents()
    assert len(docs) == 264  # 테스트셋 문서는 들어가지 않음
    numbers = [re.search(r"_(\d{3})(?:_p1)?\.png$", d).group(1) for d in docs]
    assert all(n[-1] in "2345" for n in numbers)  # dev는 번호 끝자리 2~5


def test_transforms_keep_rgb_and_are_repeatable():
    img = Image.new("RGB", (400, 566), "white")
    for fn in hard2.TRANSFORMS:
        a, b = fn(img, random.Random(1)), fn(img, random.Random(1))
        assert a.mode == "RGB" and a.tobytes() == b.tobytes()  # 같은 시드면 같은 이미지
    assert hard2.top_cropped(img, random.Random(1)).height < img.height
    assert hard2.low_res_jpeg(img, random.Random(1)).width < img.width
