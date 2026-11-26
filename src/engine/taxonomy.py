"""분류 체계 로더: config/taxonomy.yaml을 읽어 검증하고 프롬프트용 텍스트로 만든다.
승인된 신규 분류는 add_minor()가 같은 파일에 추가한다 (FR-10).

YAML 구조 (백엔드 2 관리 파일)
    taxonomy:
      - major: "인사/채용"
        items:
          - minor_code: "HR-01"
            minor_name: "이력서"
            definition: "..."

사용 예
    tax = load_taxonomy()
    text_v1 = format_taxonomy(tax, include_definition=False)  # v1: 목록만
    text_v2 = format_taxonomy(tax, include_definition=True)   # v2: 정의 포함
"""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / "config" / "taxonomy.yaml"
_write_lock = threading.Lock()   # 데모 서버의 여러 세션이 동시에 승인해도 파일이 꼬이지 않게

ETC_CODE = "ETC-00"          # taxonomy.yaml에 등록된 「기타」 코드
NEW_PREFIX = "NEW-"          # 최종 출력에서 「기타」를 바꿔 쓸 신규 분류 코드 접두사


class TaxonomyError(ValueError):
    """taxonomy.yaml 형식이 약속과 다를 때 발생."""


@dataclass(frozen=True)
class Item:
    code: str
    name: str
    definition: str
    major: str


@dataclass
class Taxonomy:
    majors: list[str]
    items: list[Item]
    _by_code: dict[str, Item] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self._by_code = {it.code: it for it in self.items}

    # 조회 도우미 ---------------------------------------------------------
    def get(self, code: str) -> Item | None:
        return self._by_code.get(code)

    def is_valid_code(self, code: str) -> bool:
        return code in self._by_code

    def major_of(self, code: str) -> str | None:
        it = self.get(code)
        return it.major if it else None

    @property
    def codes(self) -> list[str]:
        return [it.code for it in self.items]

    @property
    def classifiable_items(self) -> list[Item]:
        """「기타」를 뺀 정식 소분류 목록."""
        return [it for it in self.items if it.code != ETC_CODE]

    @property
    def existing_new_codes(self) -> list[str]:
        """승인되어 taxonomy.yaml에 추가된 NEW-xx 코드 (번호 중복 방지용)."""
        return [c for c in self.codes if c.startswith(NEW_PREFIX)]


def taxonomy_path() -> Path:
    """분류 체계 파일 경로. .env에 TAXONOMY_PATH가 있으면 그 파일(데모용 복사본), 없으면 config/taxonomy.yaml.
    복사본이 아직 없으면 원본을 복사해 만든다. 데모에서 승인한 신규 분류가 실제 config를 바꾸지 않게 하려는 것이다.
    복사본을 지우면 원본 상태로 초기화된다."""
    raw = os.getenv("TAXONOMY_PATH")
    if not raw:
        return DEFAULT_PATH
    path = ROOT / raw   # 절대 경로면 ROOT는 무시된다
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DEFAULT_PATH, path)
    return path


def load_taxonomy(path: str | Path | None = None) -> Taxonomy:
    """taxonomy.yaml을 읽고 형식을 검증해 Taxonomy 객체로 돌려준다. path가 없으면 taxonomy_path()."""
    path = Path(path) if path else taxonomy_path()
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "taxonomy" not in data:
        raise TaxonomyError(f"{path}: 최상단에 'taxonomy' 키가 없습니다.")
    groups = data["taxonomy"]
    if not isinstance(groups, list) or not groups:
        raise TaxonomyError(f"{path}: 'taxonomy'는 대분류 리스트여야 합니다.")

    majors: list[str] = []
    items: list[Item] = []
    seen: set[str] = set()

    for gi, group in enumerate(groups):
        major = (group or {}).get("major")
        if not major:
            raise TaxonomyError(f"{path}: {gi + 1}번째 대분류에 'major'가 없습니다.")
        if major in majors:
            raise TaxonomyError(f"{path}: 대분류 '{major}'가 두 번 나옵니다.")
        majors.append(major)

        for ii, raw in enumerate(group.get("items") or []):
            missing = [k for k in ("minor_code", "minor_name", "definition") if not raw.get(k)]
            if missing:
                raise TaxonomyError(
                    f"{path}: '{major}'의 {ii + 1}번째 항목에 {', '.join(missing)} 값이 없습니다."
                )
            code = str(raw["minor_code"]).strip()
            if code in seen:
                raise TaxonomyError(f"{path}: 소분류 코드 '{code}'가 중복됩니다.")
            seen.add(code)
            items.append(
                Item(
                    code=code,
                    name=str(raw["minor_name"]).strip(),
                    definition=" ".join(str(raw["definition"]).split()),
                    major=major,
                )
            )

    if ETC_CODE not in seen:
        raise TaxonomyError(f"{path}: 「기타」 코드 {ETC_CODE}가 없습니다.")

    return Taxonomy(majors=majors, items=items)


def format_taxonomy(tax: Taxonomy, include_definition: bool = False) -> str:
    """프롬프트에 넣을 분류 체계 텍스트.

    include_definition=False (v1): 대분류, 코드, 소분류명만
    include_definition=True  (v2): 위 내용 + 소분류 정의
    """
    lines: list[str] = []
    for major in tax.majors:
        lines.append(f"[{major}]")
        for it in (i for i in tax.items if i.major == major):
            if include_definition:
                lines.append(f"- {it.code} {it.name}: {it.definition}")
            else:
                lines.append(f"- {it.code} {it.name}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _squash(text: str) -> str:
    """이름 중복 비교용: 공백을 없애고 소문자로."""
    return "".join(text.split()).lower()


def add_minor(name: str, major: str, definition: str, path: str | Path | None = None) -> str:
    """승인된 신규 분류를 taxonomy.yaml의 해당 대분류 맨 끝에 추가하고 발급한 정식 코드(예: FIN-10)를 돌려준다.

    코드는 대분류의 접두어(FIN)와 그 접두어의 다음 번호로 정한다. 호출하는 쪽이 코드를 정하지 않는다.
    이름이 이미 있거나 대분류가 없거나 「기타」 대분류면 ValueError (화면에 보여줄 한국어 메시지).
    파일은 텍스트로 끼워 넣어 주석·줄바꿈(CRLF)을 보존하고, 검증을 통과한 뒤에만 교체한다.
    교체하면 파일 수정 시각이 바뀌므로 Classifier.refresh_taxonomy()가 다음 호출부터 새 분류를 읽는다.
    """
    name = " ".join(str(name or "").split())
    definition = " ".join(str(definition or "").split())
    if not name or not definition:
        raise ValueError("분류명과 정의를 모두 입력해야 분류 체계에 추가할 수 있습니다.")
    path = Path(path) if path else taxonomy_path()

    with _write_lock:
        tax = load_taxonomy(path)
        if major not in tax.majors:
            raise ValueError(f"분류 체계에 없는 대분류입니다: {major}")
        if major == tax.major_of(ETC_CODE):
            raise ValueError(f"「{major}」 대분류에는 소분류를 추가할 수 없습니다.")
        same = next((it for it in tax.items if _squash(it.name) == _squash(name)), None)
        if same:
            raise ValueError(f"이미 있는 분류명입니다: {same.code} '{same.name}'")

        in_major = [it.code for it in tax.items if it.major == major]
        if not in_major:
            raise ValueError(f"「{major}」에 기존 소분류가 없어 코드 접두어를 정할 수 없습니다.")
        prefix = in_major[0].rsplit("-", 1)[0]
        same_prefix = [c.rsplit("-", 1) for c in tax.codes]
        numbers = [int(num) for pre, num in same_prefix if pre == prefix and num.isdigit()]
        code = f"{prefix}-{max(numbers, default=0) + 1:02d}"

        text = path.read_bytes().decode("utf-8")
        nl = "\r\n" if "\r\n" in text else "\n"
        lines = text.splitlines(keepends=True)
        is_major = re.compile(r"^\s*-\s*major:")
        start = next(
            (i for i, ln in enumerate(lines) if is_major.match(ln) and ln.split(":", 1)[1].strip().strip("\"'") == major),
            None,
        )
        if start is None:
            raise TaxonomyError(f"{path}: 대분류 '{major}' 줄을 찾지 못했습니다.")
        end = next((i for i in range(start + 1, len(lines)) if is_major.match(lines[i])), len(lines))
        while end - 1 > start and not lines[end - 1].strip():   # 대분류 사이의 빈 줄 앞에 넣는다
            end -= 1
        if not lines[end - 1].endswith(("\n", "\r")):
            lines[end - 1] += nl
        entry = [
            f"      - minor_code: {json.dumps(code)}",
            f"        minor_name: {json.dumps(name, ensure_ascii=False)}",
            f"        definition: {json.dumps(definition, ensure_ascii=False)}",
        ]
        lines[end:end] = [ln + nl for ln in entry]

        tmp = path.with_name(path.name + ".tmp")
        try:
            tmp.write_bytes("".join(lines).encode("utf-8"))
            added = load_taxonomy(tmp).get(code)   # 형식이 깨졌으면 여기서 TaxonomyError, 원본은 그대로
            if not added or added.major != major or added.name != name:
                raise TaxonomyError(f"{path}: 추가한 {code}를 다시 읽지 못했습니다.")
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
    return code
