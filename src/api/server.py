"""외부 AI 업로드 검사 서버 (시연용 시제품, ChatGPT 한정 크롬 확장 extension/이 부른다).

확장이 가로챈 파일을 받아 엔진으로 분류하고 보안 등급과 확장이 할 동작을 돌려준다.
등급 규칙은 src/engine/security.py를 그대로 쓴다 (미확정·「기타」·미산정은 handling_grade로 최소 대외비).
    기밀     → block   : 취소가 기본, 사유를 체크해야 업로드 가능
    대외비   → confirm : 경고와 업로드/취소 확인 창
    사내한정·공개 → pass : 등급만 잠깐 보여 주고 통과
    검사 실패(형식·크기·API 오류) → status "error", 확장은 취소가 기본인 확인 창을 띄운다

API (127.0.0.1에서만 듣는다)
    POST /check     본문 = 파일 바이트, 헤더 X-Filename = encodeURIComponent(파일명)
    POST /decision  본문 = {"file", "grade", "choice": "upload"|"cancel"} → logs/gate.log에 사용자 선택 기록
    GET  /health    서버 켜짐 확인

실행 (저장소 루트에서). DEMO_MOCK이 0이 아니면 API 없이 파일명 앞 코드(예: FIN-03_...)로 가짜 분류를 낸다
    python -m src.api.server
    python -m src.api.server --grades /path/security_grades_draft_4level.yaml   # 등급표 초안으로 리허설

ponytail: 단일 스레드 http.server, 한 번에 한 파일. 동시 업로드가 필요해지면 ThreadingHTTPServer + 호출 간격 잠금.
ponytail: 같은 파일 재검사는 결과 캐시(logs/check_cache.json, ResultCache)로 모델 호출을 건너뛴다. 소분류 코드만 저장하고
          등급·동작은 매번 현재 등급표로 다시 낸다. 항목 수 제한 없음; 파일이 커져 느려지면 오래된 항목 정리 도입.
실제 모드는 데모와 같이 Qwen·Gemini를 동시에 불러 합산 확정(src/engine/cross_check.py)한다. 미확정은 「잠정」, 최소 대외비.
GEMINI_API_KEY가 없으면 모든 결과가 미확정(gemini_unavailable)이다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import tempfile
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote

from src.engine.security import GRADES_PATH, grade_fields, handling_grade, load_grades
from src.engine.taxonomy import ETC_CODE, load_taxonomy, taxonomy_path

HOST, PORT = "127.0.0.1", 8765
MAX_BYTES = 20 * 1024 * 1024
ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".doc", ".docx"}  # 엔진(pages.py)이 읽는 형식만
ACTIONS = {"기밀": "block", "대외비": "confirm", "사내한정": "pass", "공개": "pass"}
ETC_BASIS = "분류 체계 밖 문서, 담당자 확인 필요"
# 캐시 키에 들어가지 않는 검사 방식(PDF 변환 해상도, 결과 해석 등)을 바꾸면 올린다. 모델·프롬프트·분류 체계는 키에 자동 반영
CACHE_VERSION = "1"
CACHE_PATH = Path("logs/check_cache.json")

# 판단 1건당 한 줄: 시각, 종류(check/decision), 파일명, 소분류, 등급, 동작 또는 사용자 선택. 문서 내용은 남기지 않는다
GATE_LOG = logging.getLogger("docsense.gate")


def open_gate_log(path: str | Path = "logs/gate.log") -> None:
    if GATE_LOG.handlers:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    GATE_LOG.addHandler(handler)
    GATE_LOG.setLevel(logging.INFO)


class MockEngine:
    """API 없이 시연 리허설용. 파일명이 체계 안 코드로 시작하면 그 소분류로 확정, '_lowconf'가 있으면 합산 미확정,
    그 밖에는 「기타」. Classifier와 같은 모양(classify(path) → dict, grades)만 맞춘다."""

    def __init__(self, grades: dict):
        self.tax = load_taxonomy()
        self.grades = grades

    def classify(self, path: Path) -> dict:
        name = path.name.split("__", 1)[-1]  # 임시 파일 접두사 제거
        item = self.tax.get("-".join(name.split("-")[:2]).split("_")[0])
        if not item or item.code == ETC_CODE:
            return {"status": "pending_review", "minor_code": "NEW-01", "minor_name": "기타", "predicted_code": ETC_CODE}
        r = {"status": "confirmed", "minor_code": item.code, "minor_name": item.name}
        if "_lowconf" in name:
            r["cross_check"] = {"confirmed": False, "reason": "low_confidence"}
        return r | grade_fields(r, self.grades)


def make_engine(grades_path: str | Path = GRADES_PATH):
    grades = load_grades(grades_path)
    if os.getenv("DEMO_MOCK", "1") != "0":
        return MockEngine(grades)
    from src.engine.cross_check import make_classifier

    return make_classifier(prompt_version=os.getenv("PROMPT_VERSION", "v1"), grades_path=grades_path)


class ResultCache:
    """원본 바이트 SHA-256 + 검사 설정 → 소분류 코드. 원본·본문·파일명·등급·사용자 선택은 저장하지 않는다.
    확정된 체계 안 결과만 넣는다(검사 실패·「기타」·합산 미확정은 매번 다시 검사)."""

    def __init__(self, path: str | Path = CACHE_PATH):
        self.path = Path(path)
        try:
            self.items = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):  # 없거나 깨진 캐시는 비우고 시작한다 (다시 검사하면 될 뿐 잃는 것 없음)
            self.items = {}

    @staticmethod
    def key(data: bytes, engine) -> str:
        tax = hashlib.sha256(taxonomy_path().read_bytes()).hexdigest()
        setting = f"{CACHE_VERSION}|{getattr(engine, 'model', 'mock')}|{getattr(engine, 'prompt_version', 'mock')}|{tax}"
        return hashlib.sha256(setting.encode() + b"|" + hashlib.sha256(data).digest()).hexdigest()

    def get(self, key: str) -> str | None:
        return (self.items.get(key) or {}).get("minor_code")

    def put(self, key: str, minor_code: str, engine) -> None:
        self.items[key] = {"minor_code": minor_code, "model": getattr(engine, "model", "mock"),
                           "prompt_version": getattr(engine, "prompt_version", "mock"),
                           "checked_at": datetime.now().isoformat(timespec="seconds")}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.items, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)  # 쓰다 멈춰도 기존 캐시 파일이 깨지지 않게


def error(file: str, message: str) -> dict:
    return {"status": "error", "file": file, "action": "error", "message": message}


def check(data: bytes, filename: str, engine, cache: ResultCache | None = None) -> dict:
    """파일 1건 검사. 어떤 오류도 예외로 올리지 않고 status "error" 결과로 돌려준다(확장은 확인 창으로 처리).
    cache가 있으면 같은 파일·같은 설정의 확정 결과를 재사용한다. 등급·동작은 재사용 때도 현재 등급표로 다시 낸다."""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        return error(filename, f"검사할 수 없는 형식입니다 ({suffix or '확장자 없음'}). PNG·JPG·PDF·DOC·DOCX만 검사합니다.")
    if not data:
        return error(filename, "빈 파일입니다.")
    if len(data) > MAX_BYTES:
        return error(filename, f"파일이 너무 큽니다 (최대 {MAX_BYTES // 1024 // 1024}MB).")

    start = time.time()
    key = cache.key(data, engine) if cache else None
    item = engine.tax.get(cache.get(key)) if cache else None
    if item:
        r = {"status": "confirmed", "minor_code": item.code, "minor_name": item.name}
        r |= grade_fields(r, engine.grades)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"upload__{Path(filename).name}"
            path.write_bytes(data)
            try:
                r = engine.classify(path)
            except Exception as e:  # 키 오류·한도 초과·네트워크·손상 파일. 예외 메시지는 응답 본문을 담을 수 있어 종류만 쓴다
                code = getattr(e, "status_code", None)
                return error(filename, f"분류하지 못했습니다 ({type(e).__name__}{' ' + str(code) if code else ''}).")
        if r.get("status") == "error":
            return error(filename, "분류 응답 형식 오류가 반복되어 검사하지 못했습니다.")

    grade = handling_grade(r, engine.grades)
    shown = r.get("security_grade")  # 「기타」는 등급 필드가 없다
    is_etc = r.get("status") != "confirmed"
    unconfirmed = (r.get("cross_check") or {}).get("confirmed") is False
    if cache and not item and not is_etc and not unconfirmed:
        cache.put(key, r["minor_code"], engine)
    return {
        "status": "ok",
        "file": filename,
        "minor_code": None if is_etc else r.get("minor_code"),
        "minor_name": "기타" if is_etc else r.get("minor_name"),
        "security_grade": shown,
        "handling_grade": grade,
        "provisional": is_etc or unconfirmed or shown != grade,  # 표시 등급과 다른 보수 처리 등급이면 「잠정」
        "grade_basis": ETC_BASIS if is_etc else r.get("grade_basis"),
        "action": ACTIONS[grade],
        "cached": bool(item),
        "latency_ms": int((time.time() - start) * 1000),
    }


def origin_allowed(origin: str | None) -> bool:
    """크롬 확장(chrome-extension://)과 Origin 없는 로컬 도구(curl)만 받는다. 웹 페이지가 직접 부르는 것은 막는다."""
    return origin is None or origin.startswith("chrome-extension://")


class Handler(BaseHTTPRequestHandler):
    engine = None  # main()에서 채운다
    cache = None

    def _send(self, code: int, body: dict) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"status": "ok", "mock": isinstance(self.engine, MockEngine)})
        self._send(404, {"status": "error", "message": "없는 주소입니다."})

    def do_POST(self):
        if not origin_allowed(self.headers.get("Origin")):
            return self._send(403, {"status": "error", "message": "허용되지 않은 출처입니다."})
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BYTES:
            # 본문을 읽지 않고 끊는다
            self.close_connection = True
            return self._send(413, error(self.headers.get("X-Filename", ""), "파일이 너무 큽니다."))
        data = self.rfile.read(length)

        if self.path == "/check":
            filename = unquote(self.headers.get("X-Filename") or "")
            result = check(data, filename, self.engine, self.cache)
            GATE_LOG.info("check\t%s\t%s\t%s\t%s\t%s\t%s", filename, result.get("minor_code") or "-",
                          result.get("handling_grade") or "-", result["action"],
                          "cached" if result.get("cached") else "new", result.get("latency_ms", "-"))
            return self._send(200, result)
        if self.path == "/decision":
            try:
                d = json.loads(data or b"{}")
                choice = d["choice"]
                if choice not in ("upload", "cancel"):
                    raise ValueError
            except (ValueError, KeyError, TypeError):
                return self._send(400, {"status": "error", "message": "choice는 upload 또는 cancel이어야 합니다."})
            GATE_LOG.info("decision\t%s\t-\t%s\t%s", str(d.get("file", ""))[:200], str(d.get("grade", ""))[:10], choice)
            return self._send(200, {"status": "ok"})
        self._send(404, {"status": "error", "message": "없는 주소입니다."})

    def log_message(self, fmt, *args):  # 기본 접근 로그(stderr)는 끈다. 판단 기록은 gate.log에 남긴다
        pass


def main(argv: list[str] | None = None) -> None:
    from dotenv import load_dotenv

    load_dotenv()
    ap = argparse.ArgumentParser(description="외부 AI 업로드 검사 서버 (시연용)")
    ap.add_argument("--grades", default=str(GRADES_PATH), help="보안 등급표 (기본 config/security_grades.yaml)")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--no-cache", action="store_true", help="같은 파일 결과 재사용을 끈다 (속도 비교용)")
    args = ap.parse_args(argv)

    Handler.engine = make_engine(args.grades)
    # MOCK은 파일명으로 분류하므로 내용 기준 캐시를 쓰면 같은 그림을 이름만 바꾼 리허설 파일이 섞인다
    Handler.cache = None if args.no_cache or isinstance(Handler.engine, MockEngine) else ResultCache()
    open_gate_log()
    mode = "MOCK" if isinstance(Handler.engine, MockEngine) else f"실제 API, {Handler.engine.model}"  # Gemini 키가 없으면 「gemini 없음」
    n = len(Handler.engine.grades)
    print(f"검사 서버 시작: http://{HOST}:{args.port} ({mode}, 등급표 {n}개 코드{' — 없음, 전부 대외비로 처리' if not n else ''}"
          f", 결과 재사용 {'켬' if Handler.cache else '끔'})")
    HTTPServer((HOST, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
