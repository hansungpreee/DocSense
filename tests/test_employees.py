import pytest
"""데모 로그인(사번) · 부서 담당 문서 테스트. 실행: python -m pytest tests -q"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import services  # noqa: E402


def test_사번_조회는_대소문자_공백을_무시한다():
    emp = services.find_employee("  hs1001 ")
    assert emp["id"] == "HS1001" and emp["department"] == "인사팀"
    assert emp["majors"] == ["인사/채용"] and emp["summary"]


def test_없는_사번이나_빈값은_None():
    assert services.find_employee("ZZ9999") is None
    assert services.find_employee("") is None
    assert services.find_employee(None) is None


def test_부서의_대분류는_모두_분류_체계에_있고_6개_대분류를_빠짐없이_나눈다():
    data = yaml.safe_load((ROOT / "config" / "employees.yaml").read_text(encoding="utf-8"))
    tax_majors = set(services.taxonomy().majors) - {services.taxonomy().major_of(services.ETC_CODE)}
    used = [m for d in data["departments"] for m in d["majors"]]
    assert set(used) == tax_majors and len(used) == len(set(used))  # 대분류 하나는 한 부서가 담당


def test_사번은_중복이_없고_모두_존재하는_부서에_속한다():
    data = yaml.safe_load((ROOT / "config" / "employees.yaml").read_text(encoding="utf-8"))
    ids = [e["id"] for e in data["employees"]]
    assert len(ids) == len(set(ids))
    names = {d["name"] for d in data["departments"]}
    assert all(e["department"] in names for e in data["employees"])


def test_부서_담당_소분류는_해당_대분류만_담고_기타를_뺀다():
    items = services.department_items(["재무/회계"])
    assert items and all(it.major == "재무/회계" for it in items)
    assert all(it.code != services.ETC_CODE for it in services.department_items(services.taxonomy().majors))


def test_로그인은_사번과_비밀번호가_모두_맞아야_하고_비밀번호는_노출하지_않는다():
    assert services.login("HS1001", "hs1001!")["name"]
    assert services.login(" hs1001 ", "hs1001!")["id"] == "HS1001"
    assert services.login("HS1001", "틀림") is None
    assert services.login("HS1001", "") is None
    assert services.login("ZZ9999", "hs1001!") is None
    assert "password" not in services.find_employee("HS1001")


def test_가상_비밀번호는_사번마다_다르다():
    pws = [e["password"] for e in yaml.safe_load((ROOT / "config" / "employees.yaml").read_text(encoding="utf-8"))["employees"]]
    assert len(pws) == len(set(pws))


def test_전체_대분류는_기타를_빼고_6개():
    assert len(services.all_majors()) == 6 and "기타" not in services.all_majors()


@pytest.mark.skipif(not services.FORMS_DIR.is_dir(), reason="양식 원본(HWP·PDF)은 재배포 허락을 확인하지 못해 공개 저장소에 넣지 않았다")
def test_양식_매핑은_분류_체계의_코드와_실제_파일을_가리킨다():
    data = yaml.safe_load((ROOT / "config" / "forms.yaml").read_text(encoding="utf-8"))
    tax = services.taxonomy()
    assert all(tax.is_valid_code(c) for c in data)
    for code in data:
        assert services.form_file(code) is not None, code  # 이름이 틀리거나 파일이 없으면 걸린다
