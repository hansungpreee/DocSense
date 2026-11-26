"""classify(): 문서 1건 → 결과 JSON. API 호출 + 가드레일 재요청을 묶는다.

코드에서 호출
    from src.engine.classify import Classifier
    clf = Classifier(prompt_version="v1")
    result = clf.classify("data/images/clean/FIN-03_손익계산서_007.png")

명령줄 실행 (저장소 루트에서, .env에 VLM_API_KEY 필요)
    python -m src.engine.classify 문서.png
    python -m src.engine.classify 문서.pdf --out results/check   # 결과 JSON + 근거 박스 이미지 저장 (bbox 확인용)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

from .guardrail import NewCodeAllocator, ParseError, finalize, parse_response, retry_feedback, validate
from .pages import draw_evidence, load_pages
from .prompt import PROMPT_VERSIONS, build_messages
from .security import GRADES_PATH, grade_fields, load_grades
from .taxonomy import load_taxonomy
from .taxonomy import taxonomy_path as default_taxonomy_path

MAX_RETRIES = 2
MAX_OUTPUT_TOKENS = 3000

# 호출 1건마다 한 줄. 시각·파일명·상태·재시도 횟수·오류·모델·프롬프트 버전만 남긴다 (문서 내용·API 키는 남기지 않음)
LOG = logging.getLogger("docsense.engine")


def open_log() -> None:
    """엔진 로그 파일을 연다. 프로세스당 한 번만 연다 (경로: .env의 ENGINE_LOG_PATH, 기본값 logs/engine.log)."""
    if LOG.handlers:
        return
    path = Path(os.getenv("ENGINE_LOG_PATH") or "logs/engine.log")
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    LOG.addHandler(handler)
    LOG.setLevel(logging.INFO)


class Classifier:
    def __init__(
        self,
        prompt_version: str = "v1",
        taxonomy_path: str | Path | None = None,   # 없으면 .env의 TAXONOMY_PATH, 그것도 없으면 config/taxonomy.yaml
        threshold: float | None = None,
        model: str | None = None,
        client=None,
        allocator: NewCodeAllocator | None = None,
        grades_path: str | Path = GRADES_PATH,   # 보안 등급표. 없으면 모든 결과가 "미산정"
    ):
        from dotenv import load_dotenv

        load_dotenv()
        self.taxonomy_path = Path(taxonomy_path) if taxonomy_path else default_taxonomy_path()
        self._tax_mtime = self.taxonomy_path.stat().st_mtime
        self.tax = load_taxonomy(self.taxonomy_path)
        self.prompt_version = prompt_version
        self.threshold = threshold if threshold is not None else float(os.getenv("CONFIDENCE_THRESHOLD", 0.7))
        self.model = model or os.getenv("VLM_MODEL", "qwen3.7-plus-2026-05-26")
        self.allocator = allocator or NewCodeAllocator.from_taxonomy(self.tax)
        self.grades = load_grades(grades_path)
        # 마지막 classify() 호출의 토큰 사용량 (재요청 포함). 결과 JSON 형식은 건드리지 않고 run.py가 읽어 간다
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}
        # 마지막 classify() 호출에서 검증에 실패한 시도별 사유 (없으면 빈 목록). 재요청이 왜 생겼는지 run.py가 기록한다
        self.last_retry_errors: list[list[str]] = []
        if client is None:
            from openai import OpenAI

            api_key = os.getenv("VLM_API_KEY")
            if not api_key:
                raise RuntimeError("VLM_API_KEY가 없습니다. .env.example을 복사해 .env를 만들고 API 키를 넣으세요.")
            client = OpenAI(
                api_key=api_key,
                base_url=os.getenv("VLM_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
            )
        self.client = client
        open_log()

    def refresh_taxonomy(self) -> bool:
        """taxonomy.yaml이 바뀌었으면 다시 읽는다 (승인된 신규 분류를 다음 호출부터 반영, FR-10)."""
        mtime = self.taxonomy_path.stat().st_mtime
        if mtime == self._tax_mtime:
            return False
        self.tax = load_taxonomy(self.taxonomy_path)
        self._tax_mtime = mtime
        self.allocator.taken |= set(self.tax.existing_new_codes)
        return True

    def classify(self, path: str | Path, allocator: NewCodeAllocator | None = None) -> dict:
        """allocator: NEW-xx 번호 발급기. 데모에서는 저장소(나중에 DB)의 발급기를 넘겨
        번호의 기준을 한 곳으로 맞춘다. 생략하면 이 Classifier의 발급기를 쓴다(평가 스크립트용)."""
        try:
            result = self._classify(path, allocator)
        except Exception as e:  # API 오류(401·429·5xx·네트워크)·파일 손상: 기록하고 호출부로 그대로 넘긴다
            # 예외 메시지는 응답 본문을 담을 수 있어 남기지 않는다. 종류와 HTTP 상태 코드만 남긴다
            code = getattr(e, "status_code", None)
            self._log(path, "exception", len(self.last_retry_errors), [f"{type(e).__name__} {code or ''}".strip()])
            raise
        self._log(path, result["status"], result["retries"], self.last_retry_errors)
        if result["status"] != "error":  # 오류 결과에는 등급을 붙이지 않는다
            result |= grade_fields(result, self.grades)
        return result

    def _log(self, path: str | Path, status: str, retries: int, errors: list) -> None:
        record = {
            "file": Path(path).name,
            "status": status,
            "retries": retries,
            "errors": errors,
            "model": self.model,
            "prompt_version": self.prompt_version,
        }
        LOG.info(json.dumps(record, ensure_ascii=False))

    def _classify(self, path: str | Path, allocator: NewCodeAllocator | None) -> dict:
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}  # 맨 앞에서 비운다: 오류로 끝나도 이전 문서 값이 남지 않게
        self.last_retry_errors = []
        self.refresh_taxonomy()
        allocator = allocator or self.allocator
        pages = load_pages(path)
        messages = build_messages(pages, self.tax, self.prompt_version, self.threshold)
        start = time.time()
        last_errors: list[str] = []

        for attempt in range(MAX_RETRIES + 1):
            # max_tokens: 반복 출력이 끝없이 길어지면 잘라서 재요청한다 (정상 응답은 1,000토큰 안팎)
            resp = self.client.chat.completions.create(
                model=self.model, temperature=0, max_tokens=MAX_OUTPUT_TOKENS, messages=messages
            )
            usage = getattr(resp, "usage", None)  # 제공처가 사용량을 안 보내면 None
            if usage:
                self.last_usage["input_tokens"] += usage.prompt_tokens or 0
                self.last_usage["output_tokens"] += usage.completion_tokens or 0
            text = resp.choices[0].message.content or ""
            try:
                data = parse_response(text)
                last_errors = validate(data, self.tax, n_pages=len(pages))
            except ParseError as e:
                last_errors = [str(e)]

            if last_errors:
                self.last_retry_errors.append([e[:200] for e in last_errors])
            else:
                return finalize(
                    data,
                    self.tax,
                    allocator,
                    self.threshold,
                    file=Path(path).name,
                    prompt_version=self.prompt_version,
                    model=self.model,
                    latency_ms=int((time.time() - start) * 1000),
                ) | {"retries": attempt}

            messages = messages + [
                {"role": "assistant", "content": text},
                {"role": "user", "content": retry_feedback(last_errors)},
            ]

        # 재요청 한도 초과: 화면에 오류로 표시하고 이력에 남길 수 있게 실패 결과를 돌려준다
        return {
            "file": Path(path).name,
            "status": "error",
            "errors": last_errors,
            "retries": MAX_RETRIES,
            "prompt_version": self.prompt_version,
            "model": self.model,
            "latency_ms": int((time.time() - start) * 1000),
        }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.engine.classify", description="문서 1건(PNG·JPG·PDF·TXT·CSV·DOC·DOCX)을 분류해 결과 JSON을 출력한다."
    )
    parser.add_argument("file", type=Path, help="분류할 문서 파일")
    parser.add_argument("--prompt", default="v1", choices=list(PROMPT_VERSIONS), help="프롬프트 버전 (기본값 v1)")
    parser.add_argument("--out", type=Path, help="결과 JSON과 근거 박스를 그린 페이지 이미지를 저장할 폴더")
    args = parser.parse_args(argv)
    if not args.file.is_file():
        parser.error(f"파일이 없습니다: {args.file}")

    try:
        clf = Classifier(prompt_version=args.prompt)
    except RuntimeError as e:
        parser.exit(1, f"{e}\n")
    result = clf.classify(args.file)
    text = json.dumps(result, ensure_ascii=False, indent=2)

    if args.out:  # 화면에 출력하기 전에 먼저 저장해 API 호출 결과를 잃지 않는다
        args.out.mkdir(parents=True, exist_ok=True)
        stem = args.file.stem
        (args.out / f"{stem}.json").write_text(text, encoding="utf-8")
        for no, page in enumerate(load_pages(args.file), start=1):
            draw_evidence(page, result.get("evidence", []), page=no).save(args.out / f"{stem}_p{no}.png")
        print(f"저장 완료: {args.out / stem}.json, 페이지 이미지 {stem}_p*.png", file=sys.stderr)
    print(text)


if __name__ == "__main__":
    main()
