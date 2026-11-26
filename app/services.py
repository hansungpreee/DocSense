"""화면과 백엔드 사이의 유일한 연결 지점.

화면(views/*.py)은 이 파일의 함수만 부른다. 그래서
  - 엔진이 완성되기 전에는 MOCK 모드로 가짜 결과를 보여주고,
  - 저장소는 open_store()가 만드는 SQLite(src/db의 SqliteStore)다. 서버를 다시 켜도 이력·승인 대기·NEW 번호가 남는다.

모드 선택
  .env에 VLM_API_KEY가 있고 DEMO_MOCK=0이면 실제 엔진(src.engine.classify) 사용
  그 외에는 MOCK 모드 (API 비용 없음)

설계 원칙
  - NEW-xx 번호는 저장소가 가진 발급기 하나에서만 나온다 (MOCK·실제 엔진 공통).
  - 저장소는 서버 전체에서 하나다 (main.py의 st.cache_resource). 새로고침해도 이력이 남는다.
  - 화면이 분류를 요청하면 예외가 나도 화면이 깨지지 않고 status="error" 결과가 돌아온다.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
from collections import Counter
from datetime import date
from functools import lru_cache
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.store import SqliteStore  # noqa: E402
from src.engine.pages import draw_evidence, load_pages  # noqa: E402  (draw_evidence는 결과 화면이 쓴다)
from src.engine.cross_check import cross_model_name, make_classifier  # noqa: E402
from src.engine.security import FLOOR, GRADES, UNGRADED, grade_fields, handling_grade, load_grades  # noqa: E402
from src.engine.taxonomy import DEFAULT_PATH, ETC_CODE, Taxonomy, load_taxonomy, taxonomy_path  # noqa: E402

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

UPLOAD_DIR = ROOT / "data" / "uploads"
DB_DIR = ROOT / "data" / "db"
MOCK_DIR = Path(__file__).parent / "mock"
SUPPORTED = ["png", "jpg", "jpeg", "pdf", "txt", "csv", "doc", "docx"]

MIN_INTERVAL = float(os.getenv("VLM_MIN_INTERVAL", "1.0"))  # 호출 사이 최소 간격(초). 1.0 = 분당 최대 60건
MAX_RATE_RETRIES = 3                                         # 429(호출 한도 초과) 시 기다렸다 다시 시도하는 횟수
WAIT_NOTICE = "서버가 바쁩니다. 잠시만 기다려 주세요 (재시도 {n}/{total})"  # 429 재시도 대기 중 화면 문구


def is_mock() -> bool:
    return os.getenv("DEMO_MOCK", "1") != "0" or not os.getenv("VLM_API_KEY")


def prompt_version() -> str:
    return os.getenv("PROMPT_VERSION", "v1")


def model_name() -> str:
    """캐시 조회 기준. 실제 모드는 Qwen+Gemini 합산 결과의 model 값과 같다 (Qwen 단독으로 낸 예전 결과를 다시 쓰지 않음)."""
    return "mock" if is_mock() else cross_model_name(os.getenv("VLM_MODEL", "qwen3.7-plus-2026-05-26"))


# 사원·부서 (데모 로그인) ------------------------------------------------------------
EMPLOYEES_PATH = ROOT / "config" / "employees.yaml"


@lru_cache(maxsize=1)
def _load_employees() -> dict:
    import yaml

    return yaml.safe_load(EMPLOYEES_PATH.read_text(encoding="utf-8"))


def find_employee(emp_id: str) -> dict | None:
    """사번(대소문자·앞뒤 공백 무시)으로 사원을 찾는다. 없으면 None.
    돌려주는 dict: id, name, title, department, majors(담당 대분류), summary(부서가 다루는 문서 설명). 비밀번호는 담지 않는다."""
    key = (emp_id or "").strip().upper()
    data = _load_employees()
    emp = next((e for e in data["employees"] if e["id"].upper() == key), None)
    if emp is None:
        return None
    dept = next(d for d in data["departments"] if d["name"] == emp["department"])
    info = {k: v for k, v in emp.items() if k != "password"}
    return {**info, "majors": list(dept["majors"]), "summary": dept["summary"]}


def login(emp_id: str, password: str) -> dict | None:
    """데모용 로그인: 사번과 가상 비밀번호가 맞으면 사원 정보, 아니면 None. 보안 기능이 아니다 (평문 비교).
    어느 쪽이 틀렸는지는 알리지 않도록 둘 다 None으로 돌려준다."""
    emp = find_employee(emp_id)
    if emp is None:
        return None
    real = next(e for e in _load_employees()["employees"] if e["id"] == emp["id"])["password"]
    return emp if (password or "") == real else None


def all_majors() -> list[str]:
    """화면에서 고를 수 있는 대분류 전체 (「기타」 대분류는 뺀다)."""
    tax = taxonomy()
    return [m for m in tax.majors if m != tax.major_of(ETC_CODE)]


FORMS_PATH = ROOT / "config" / "forms.yaml"
FORMS_DIR = ROOT / "app" / "forms"


@lru_cache(maxsize=1)
def _form_map() -> dict:
    import yaml

    return yaml.safe_load(FORMS_PATH.read_text(encoding="utf-8")) or {}


def form_file(code: str) -> Path | None:
    """소분류의 내려받을 양식 파일. 목록에 없거나 파일이 없으면 None."""
    name = _form_map().get(code)
    return FORMS_DIR / name if name and (FORMS_DIR / name).is_file() else None


FORM_MIME = {".hwp": "application/x-hwp", ".pdf": "application/pdf"}


def form_bytes(path: Path) -> bytes:
    """내려받을 양식: 받아 둔 원본 파일(한글·PDF)을 그대로 돌려준다."""
    return path.read_bytes()


def form_mime(path: Path) -> str:
    return FORM_MIME.get(path.suffix.lower(), "application/octet-stream")


def map_majors() -> list[str]:
    """대시보드 맵에 그릴 대분류: 전체 대분류 + 「기타」."""
    return all_majors() + [taxonomy().major_of(ETC_CODE)]


def department_items(majors: list[str]) -> list:
    """부서가 담당하는 대분류에 속한 소분류(분류 체계에서 읽음). 「기타」는 뺀다."""
    return [it for it in taxonomy().classifiable_items if it.major in majors]


# 분류 체계 (파일이 바뀌면 다시 읽음) -------------------------------------------------
_tax_cache: dict = {"key": None, "tax": None}
_tax_lock = threading.Lock()


def taxonomy_file() -> Path:
    """데모가 읽는 분류 체계 파일: .env에 TAXONOMY_PATH가 있으면 그 파일, 없으면 config/taxonomy.yaml (엔진과 같은 규칙).
    예전에는 data/db/에 복사본을 만들어 썼지만, 신규 분류 승인 화면이 없어진 뒤로 복사본에 쓰는 코드가 없고
    원본이 바뀌어도(소분류 추가) 화면이 옛 목록을 계속 보여 주므로 원본을 바로 읽는다."""
    return taxonomy_path()


def taxonomy() -> Taxonomy:
    with _tax_lock:
        path = taxonomy_file()
        key = (str(path), path.stat().st_mtime)  # 파일이 바뀌거나(승인) 모드가 바뀌면 다시 읽음
        if _tax_cache["key"] != key:
            _tax_cache.update(key=key, tax=load_taxonomy(path))
        return _tax_cache["tax"]


# 저장소 (SQLite) ------------------------------------------------------------------
def db_path(emp_id: str | None = None) -> Path:
    """사원마다 DB 파일 하나. MOCK이든 실제든 같은 파일이라 모드를 바꾸거나 서버를 다시 켜도 이력이 이어진다."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "", emp_id or "")  # 파일 이름에 쓰므로 사번의 특수문자는 뺀다
    return DB_DIR / f"docsense{'_' + safe if safe else ''}.sqlite3"


def open_store(emp_id: str | None = None) -> SqliteStore:
    """데모가 쓰는 저장소를 만든다. 저장소를 만드는 곳은 여기 한 곳뿐이다 (main.py가 로그인한 사원마다 한 번 부른다).
    사원마다 DB 파일을 따로 써서 분류 이력이 서로 보이지 않는다. 파일은 data/db/ 아래 (.gitignore, 지우면 초기화).
    예전 버전이 MOCK 모드에서 따로 쓰던 파일(docsense_mock_<사번>)만 있으면 한 번 복사해 이어 받는다."""
    path = db_path(emp_id)
    legacy = path.with_name(path.name.replace("docsense", "docsense_mock", 1))
    if not path.exists() and legacy.exists():
        shutil.copy2(legacy, path)
    return SqliteStore(path, taxonomy())


# 중요 표시(별) ----------------------------------------------------------------------
def _star_path(emp_id: str) -> Path:
    return db_path(emp_id).with_suffix(".stars.json")


def starred(emp_id: str) -> set[int]:
    """사원이 별을 붙인 분류 결과 ID. 서버를 다시 켜도 남도록 DB 옆 파일에 저장한다."""
    try:
        return set(json.loads(_star_path(emp_id).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def toggle_star(emp_id: str, result_id: int) -> None:
    ids = starred(emp_id) ^ {result_id}
    path = _star_path(emp_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(ids)), encoding="utf-8")


# 설정 (글자 크기 · 언어 · 사용 방법 안내) ---------------------------------------
DEFAULT_SETTINGS = {"lang": "ko", "font": 100, "tour": "daily"}
SETTING_CHOICES = {"lang": ("ko", "en"), "font": (90, 100, 115, 130), "tour": ("daily", "off")}


def _settings_path(emp_id: str) -> Path:
    return db_path(emp_id).with_suffix(".settings.json")


def load_settings(emp_id: str) -> dict:
    """사원의 설정. 파일이 없거나 값이 이상하면 기본값을 쓴다 (사원마다 따로 저장해 서버를 다시 켜도 남는다)."""
    try:
        saved = json.loads(_settings_path(emp_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    return {k: saved.get(k) if saved.get(k) in SETTING_CHOICES[k] else v for k, v in DEFAULT_SETTINGS.items()}


def save_setting(emp_id: str, key: str, value) -> None:
    if key not in SETTING_CHOICES or value not in SETTING_CHOICES[key]:
        raise ValueError(f"설정 값이 올바르지 않습니다: {key}={value}")
    path = _settings_path(emp_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(load_settings(emp_id) | {key: value}, ensure_ascii=False), encoding="utf-8")


# 파일 이름 겹침 ---------------------------------------------------------------------
def name_conflicts(names: list[str], taken: set[str]) -> list[int]:
    """이름을 바꿔야 하는 파일의 위치. 이미 분류한 문서(taken)와 같거나, 이번에 올린 앞쪽 파일과 같으면 겹친다 (대소문자 무시).
    같은 이름을 여러 번 올리면 첫 번째는 그대로 두고 나머지만 겹침으로 본다."""
    seen = {t.lower() for t in taken}
    bad = []
    for i, n in enumerate(names):
        if n.lower() in seen:
            bad.append(i)
        seen.add(n.lower())
    return bad


def suggest_name(name: str, used: set[str]) -> str:
    """겹치지 않는 이름 제안: 「보고서.pdf」 → 「보고서 (2).pdf」"""
    used = {u.lower() for u in used}
    stem, suffix = Path(name).stem, Path(name).suffix
    n = 2
    while f"{stem} ({n}){suffix}".lower() in used:
        n += 1
    return f"{stem} ({n}){suffix}"


# 분류 실행 -----------------------------------------------------------------------
def save_upload(name: str, data: bytes) -> tuple[Path, str]:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(data).hexdigest()
    path = UPLOAD_DIR / f"{digest[:12]}_{Path(name).name}"
    if not path.exists():
        path.write_bytes(data)
    return path, digest


def save_pages(names: list[str], datas: list[bytes]) -> tuple[Path, str]:
    """한 문서의 여러 페이지 이미지를 올린 순서대로 `<해시>_<이름>_p1.png`, `_p2.png` …로 저장하고 _p1 경로를 돌려준다.
    엔진(pages.py)이 _p1을 받으면 같은 폴더의 _p2, _p3 …를 이어 읽으므로 엔진은 고치지 않는다.
    캐시 키는 모든 페이지의 해시를 순서대로 이은 값의 해시다 (페이지 하나라도 바뀌거나 순서가 바뀌면 다시 분류)."""
    if not datas:
        raise ValueError("페이지 이미지를 1장 이상 올려 주세요.")
    if len(datas) == 1:  # 1장이면 단건 업로드와 같은 파일·같은 캐시
        return save_upload(names[0], datas[0])
    digest = hashlib.sha256("".join(hashlib.sha256(d).hexdigest() for d in datas).encode()).hexdigest()
    first = Path(names[0])
    stem = re.sub(r"_p\d+$", "", first.stem, flags=re.IGNORECASE)  # 데이터셋 파일(이름_p1.png)이면 번호를 떼어 낸다
    ext = first.suffix.lower()  # Pillow는 내용으로 형식을 읽으므로 PNG·JPG가 섞여도 확장자는 첫 장 기준으로 통일
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    paths = [UPLOAD_DIR / f"{digest[:12]}_{stem}_p{i}{ext}" for i in range(1, len(datas) + 1)]
    for path, data in zip(paths, datas):
        if not path.exists():
            path.write_bytes(data)
    return paths[0], digest


_classifier = None
_classifier_lock = threading.Lock()
_rate_lock = threading.Lock()
_last_call = 0.0


def classify(path: Path, file_hash: str, store: SqliteStore, on_wait=None) -> dict:
    """문서 1건 분류. 어떤 오류가 나도 예외를 올리지 않고 status="error" 결과를 돌려준다.

    on_wait: 429로 기다렸다 다시 시도하기 직전에 안내 문구(str)를 받아 화면에 보여주는 함수 (실제 엔진 모드에서만 호출됨).
    """
    original = path.name.split("_", 1)[-1]
    meta = {"path": str(path), "file": original, "file_hash": file_hash}

    cached = store.find_cached(file_hash, prompt_version(), model_name())
    if cached:
        r = {k: copy.deepcopy(v) for k, v in cached.items() if k not in ("id", "created_at")}
        return r | meta | {"cached": True, "latency_ms": 0}

    start = time.time()
    try:
        result = _mock_classify(original, path, store) if is_mock() else _engine_classify(path, store, on_wait)
    except Exception as e:  # 네트워크, 키 오류, 한도 초과, 파일 손상 등
        result = {
            "status": "error",
            "errors": [_describe_error(e)],
            "prompt_version": prompt_version(),
            "model": model_name(),
            "latency_ms": int((time.time() - start) * 1000),
        }
    return result | meta


def _engine_classify(path: Path, store: SqliteStore, on_wait=None) -> dict:
    global _classifier
    with _classifier_lock:
        if _classifier is None:
            # Qwen·Gemini 동시 호출 + 합산 확정 (평가의 cross_check와 같은 규칙)
            _classifier = make_classifier(prompt_version=prompt_version(), taxonomy_path=taxonomy_file(),
                                          allocator=store.allocator)

    for attempt in range(MAX_RATE_RETRIES + 1):
        _wait_for_slot()
        try:
            return _classifier.classify(path, allocator=store.allocator)
        except Exception as e:
            if _status_code(e) == 429 and attempt < MAX_RATE_RETRIES:
                if on_wait:
                    on_wait(WAIT_NOTICE.format(n=attempt + 1, total=MAX_RATE_RETRIES))
                time.sleep(2 ** (attempt + 1))  # 2초, 4초, 8초 기다렸다 다시 시도
                continue
            raise


def _wait_for_slot():
    """호출 사이에 MIN_INTERVAL초 이상 간격을 둔다 (여러 세션이 동시에 눌러도 전체 기준)."""
    global _last_call
    with _rate_lock:
        wait = MIN_INTERVAL - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()


def _status_code(e: Exception) -> int | None:
    return getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)


def _describe_error(e: Exception) -> str:
    code = _status_code(e)
    if code == 401:
        return "API 키가 올바르지 않습니다 (401). .env의 VLM_API_KEY와 리전을 확인하세요."
    if code == 429:
        return "API 호출 한도를 초과했습니다 (429). 잠시 후 다시 시도하세요."
    if code and code >= 500:
        return f"API 서버 오류입니다 ({code}). 잠시 후 다시 시도하세요."
    if isinstance(e, ValueError):  # 엔진·저장소가 사용자용 한국어 문구로 올리는 오류 (손상 파일 등)
        return str(e)[:300]
    name = type(e).__name__
    if "Connection" in name or "Timeout" in name:
        return "API 서버에 연결하지 못했습니다. 인터넷 연결을 확인하세요."
    return f"분류 중 오류가 발생했습니다: {name}: {e}"[:300]


def _mock_classify(original: str, path: Path, store: SqliteStore) -> dict:
    """MOCK 결과는 app/mock/samples/의 4종을 바탕으로 만든다. 파일명으로 경우를 고른다.

    'FIN-03_...'처럼 코드로 시작      → 정상 분류 (PDF가 여러 페이지면 02 다중 페이지 샘플)
    위 + 파일명에 '_hard' 또는 'lowconf' → 확신도 낮음 (04 샘플, 1순위 예측 = 그 코드)
    그 외                               → 「기타」 신규 분류 제안 (03 샘플, 제안명 = 파일명)
    """
    n_pages = len(load_preview_pages(path))  # 손상 파일은 여기서 실패 → 실제 모드처럼 오류 결과가 된다
    tax = taxonomy()
    code = "-".join(original.split("-")[:2]).split("_")[0]
    item = tax.get(code)
    stem = re.sub(r"_p1$", "", Path(original).stem)  # 여러 쪽 문서(이름_p1.png)는 번호를 뺀 이름을 제안명으로

    if item and item.code != ETC_CODE and ("_hard" in stem or "lowconf" in stem):
        r = _load_sample("04_low_confidence")
        r.update(major=item.major, predicted_code=item.code)
        r["new_class"].update(
            proposed_major=item.major,
            reason=f"확신도 {r['confidence']:.2f}가 기준 0.70 미만 (모델 1순위: {item.code} {item.name})",
        )
        r["minor_code"] = store.allocator.assign(None)  # 제안명이 없으므로 건마다 새 번호
    elif item and item.code != ETC_CODE:
        r = _load_sample("02_normal_multipage" if n_pages > 1 else "01_normal_single")
        r.update(major=item.major, minor_code=item.code, minor_name=item.name, predicted_code=item.code)
        r["reasons"][0] = f"상단 제목이 '{item.name}'"
        r["evidence"] = [e for e in r["evidence"] if e["page"] <= n_pages]
    else:
        r = _load_sample("03_etc_new_class")
        r["new_class"]["proposed_name"] = r["minor_name"] = stem  # MOCK: 파일명을 제안 분류명으로 사용
        r["reasons"][0] = f"상단 제목이 '{stem}'"
        r["minor_code"] = store.allocator.assign(stem)
    r["model"] = "mock"
    r["prompt_version"] = prompt_version()
    r["cross_check"] = _mock_cross_check(r)
    return r


def _mock_cross_check(r: dict) -> dict:
    """MOCK 전용 가짜 교차 확인(Gemini+Qwen 합산) 결과. 엔진의 합산 확정 함수가 같은 모양으로 낼 때까지 화면 확인용으로만 쓴다.
    정상 분류는 Gemini도 같은 분류로 확정, 「기타」·낮은 확신도는 Gemini가 다르게 봐서 미확정."""
    if r["status"] == "confirmed":
        return {"confirmed": True, "reason": "agree", "threshold": 0.95, "gemini": {"minor_code": r["minor_code"], "confidence": 0.97}}
    return {"confirmed": False, "reason": "disagree", "threshold": 0.95, "gemini": {"minor_code": r.get("predicted_code"), "confidence": 0.81}}


def _load_sample(name: str) -> dict:
    return json.loads((MOCK_DIR / "samples" / f"{name}.json").read_text(encoding="utf-8"))


# 화면 도우미 ---------------------------------------------------------------------
@lru_cache(maxsize=64)
def _pages_cached(path: str) -> tuple[Image.Image, ...]:
    return tuple(load_pages(path))


def load_preview_pages(path: str | Path) -> tuple[Image.Image, ...]:
    """미리보기용 페이지 이미지. 업로드 파일은 내용 해시로 이름을 붙여 바뀌지 않으므로 경로로 캐시한다.
    화면을 조작할 때마다 PDF를 다시 변환하지 않는다. 받은 이미지는 수정하지 말고 복사해서 쓸 것."""
    return _pages_cached(str(path))


_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~$:=])")


def plain(text) -> str:
    """모델·사용자가 쓴 글을 st.markdown/caption/error에 그대로 보이게 한다.
    마크다운 기호(굵게, 제목, 목록, 링크, 표, 수식 $, 색 :red[] 등)를 역슬래시로 무력화하고 줄바꿈은 공백으로 합친다."""
    if text is None:
        return ""
    return _MD_SPECIAL.sub(r"\\\1", " ".join(str(text).split()))


def shown(r: dict) -> tuple[str, str, str]:
    """화면에 보이는 (대분류, 소분류 코드, 소분류 이름). 「기타」로 빠진 문서(승인 대기 상태)는 모델이 제안한 분류와 무관하게
    대분류 「기타」, ETC-00으로 보인다. 제안한 문서 이름은 결과 화면의 참고 문구로만 남는다."""
    if r.get("status") == "pending_review":
        tax = taxonomy()
        return tax.major_of(ETC_CODE), ETC_CODE, "기타"
    return r.get("major") or "", r.get("minor_code") or "", r.get("minor_name") or ""  # 오류 행은 빈칸 (표에 None이 보이지 않게)


def cross_label(r: dict) -> str:
    """합산 확정 결과 한 단어. 합산 결과가 없는 문서(교차 확인 전 결과, 오류)는 빈칸."""
    cc = r.get("cross_check")
    return "" if not cc else ("확정" if cc.get("confirmed") else "미확정")


def result_row(r: dict) -> dict:
    """일괄 결과 표 · 이력 표의 한 줄."""
    major, code, name = shown(r)
    return {
        "ID": r.get("id"),
        "파일명": r.get("file"),
        "대분류": major,
        "소분류 코드": code,
        "소분류": name,
        "확신도": r.get("confidence"),
        "상태": {"confirmed": "확정", "pending_review": "기타", "error": "오류"}.get(r.get("status"), r.get("status")),
        "교차 확인": cross_label(r),
        "근거 요약": " / ".join(r.get("reasons") or r.get("errors") or [])[:80],
        "캐시": "재사용" if r.get("cached") else "",
        "프롬프트": r.get("prompt_version"),
        "처리 시간(ms)": r.get("latency_ms"),
        "시각": r.get("created_at"),
    }


# 결과 화면의 보안 등급 -----------------------------------------------------------------
def grade_info(r: dict) -> dict | None:
    """결과 화면에 보일 보안 등급. 오류 결과는 None, 「기타」는 {"etc": True}(등급 없음).
    등급은 저장된 값 대신 지금 등급표로 다시 찾는다(리포트와 같은 기준: MOCK·이전 결과도 보이고 등급표 수정이 바로 반영).
    provisional: 소분류가 확정되지 않았다(등급표에 없음·합산 미확정) → 확정 전까지 handling(대외비 이상)으로 취급.
    # ponytail: 열 때마다 등급표 파일을 읽는다(100줄); 느려지면 lru_cache."""
    if r.get("status") == "error":
        return None
    if r.get("status") == "pending_review":
        return {"etc": True, "handling": FLOOR}
    table = load_grades()
    fields = grade_fields(r, table)
    grade = fields.get("security_grade", UNGRADED)
    return {
        "etc": False,
        "grade": grade,
        "basis": fields.get("grade_basis"),
        "provisional": grade == UNGRADED or (r.get("cross_check") or {}).get("confirmed") is False,
        "handling": handling_grade(r, table),
    }


# 보안 등급 현황 리포트 ----------------------------------------------------------------
REPORT_ETC = "기타 (등급 없음)"
REPORT_ERROR = "오류"
REPORT_GRADES = [*GRADES, UNGRADED, REPORT_ETC, REPORT_ERROR]  # 표·차트 순서 (높은 등급부터)


def report_grade(r: dict, table: dict) -> str:
    """리포트에서 문서 1건이 들어갈 등급 칸. 저장된 security_grade 대신 지금 등급표로 다시 찾는다
    (MOCK 결과·등급표 도입 전 결과에도 등급이 보이고, 등급표를 고치면 리포트가 바로 따라온다)."""
    if r.get("status") == "error":
        return REPORT_ERROR
    if r.get("status") == "pending_review":
        return REPORT_ETC
    return grade_fields(r, table).get("security_grade", UNGRADED)


def grade_report(history: list[dict], start: date, end: date) -> dict:
    """기간(시작일~종료일, 양 끝 포함) 안에 분류한 문서의 등급별·대분류별 건수와 문서별 목록.
    # ponytail: 로그인한 사원 한 명의 이력만 센다; 회사 전체 리포트가 필요해지면 사원별 DB를 합친다."""
    table = load_grades()
    rows = [r for r in history if start.isoformat() <= (r.get("created_at") or "")[:10] <= end.isoformat()]
    n = len(rows)
    grades = Counter(report_grade(r, table) for r in rows)
    majors = Counter(shown(r)[0] or REPORT_ERROR for r in rows)
    major_order = all_majors() + [taxonomy().major_of(ETC_CODE), REPORT_ERROR]

    def table_of(key: str, order: list[str], counts: Counter) -> list[dict]:
        return [{key: k, "건수": counts[k], "비율(%)": round(counts[k] / n * 100, 1) if n else 0.0} for k in order]

    return {
        "total": n,
        "by_grade": table_of("보안 등급", REPORT_GRADES, grades),
        "by_major": table_of("대분류", major_order, majors),
        "rows": [result_row(r) | {"보안 등급": report_grade(r, table)} for r in rows],
    }
