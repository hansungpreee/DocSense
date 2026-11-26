"""보안 등급 조회: 소분류 코드 → 기본 등급 (config/security_grades.yaml, 백엔드 2 관리).

문서 내용을 보고 등급을 올리지 않는다. 소분류가 정해지면 등급표에서 찾아 붙일 뿐이다.
표에 없는 코드(ETC-00, NEW-xx, 등급을 정하지 않은 소분류)나 표 파일이 없으면 "미산정"이고 오류를 올리지 않는다.

등급표 형식 (코드: 등급, 또는 근거를 단 형식)
    FIN-03: 기밀
    FIN-10: {grade: 사내한정, basis: "부가가치세법 제32조 공급받는자 교부, 단가 포함"}

명령줄 실행: dev 결과에서 등급 일치율과 하향 오류(높은 등급 문서가 낮게 표시된 건수)를 센다 (API 호출 없음)
    python -m src.engine.security results/b_vfinal_qwen_fix/predictions.jsonl [다른 결과 ...] [--grades 등급표.yaml]
    python -m src.engine.security <qwen.jsonl> --gemini <gemini.jsonl>   # 합산 확정 뒤 기준
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import yaml

GRADES_PATH = Path(__file__).resolve().parents[2] / "config" / "security_grades.yaml"
GRADES = ("기밀", "대외비", "사내한정", "공개")  # 높은 등급부터 (11/16 4단계 결정). 이름을 바꾸면 여기와 등급표만 고친다
UNGRADED = "미산정"
FLOOR = "대외비"  # 등급이 확정되지 않은 문서(미산정·「기타」·합산 미확정)를 취급할 때의 최소 등급 (하향 오류 방지)


def load_grades(path: str | Path = GRADES_PATH) -> dict[str, dict]:
    """등급표를 읽는다: 코드 → {"grade", "basis"}. 파일이 없으면 빈 표(전부 미산정).
    한 줄 형식(FIN-03: 기밀)과 근거를 단 형식(FIN-03: {grade: 기밀, basis: "..."})을 모두 받는다. 다른 키는 무시한다.
    등급 이름이 GRADES 중 하나가 아닌 줄은 버린다(오타가 등급으로 보이지 않게)."""
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}
    table = {}
    for code, v in raw.items():
        entry = v if isinstance(v, dict) else {"grade": v}
        if entry.get("grade") in GRADES:
            table[str(code)] = {"grade": entry["grade"], "basis": entry.get("basis")}
    return table


def grade_fields(result: dict, table: dict[str, dict]) -> dict:
    """결과에 붙일 두 필드. 「기타」(pending_review)는 분류 체계 밖 문서라 등급을 매기지 않고 필드도 붙이지 않는다(빈 dict).
    체계 안 소분류인데 등급표에 없으면 미산정이다."""
    if result.get("status") != "confirmed":
        return {}
    code = result.get("minor_code")
    entry = table.get(code)
    if not entry:
        return {"security_grade": UNGRADED, "grade_basis": f"등급표에 없는 분류 (확정 전까지 {FLOOR} 이상으로 취급)"}
    basis = f"소분류 {code} {result.get('minor_name')}의 기본 등급"
    return {"security_grade": entry["grade"], "grade_basis": f"{basis} ({entry['basis']})" if entry["basis"] else basis}


def handling_grade(result: dict, table: dict[str, dict]) -> str:
    """실제 취급에 쓸 등급. 소분류가 확정되지 않았으면(「기타」·미산정·합산 미확정) 최소 FLOOR로 올린다.
    표시 등급(security_grade)은 그대로 두고, 화면의 「잠정」 표시와 등급 지표가 이 값을 쓴다."""
    grade = grade_fields(result, table).get("security_grade", UNGRADED)  # 「기타」는 필드가 없고 미산정처럼 취급
    unconfirmed = (result.get("cross_check") or {}).get("confirmed") is False
    if grade == UNGRADED:
        return FLOOR
    if unconfirmed and GRADES.index(grade) > GRADES.index(FLOOR):
        return FLOOR
    return grade


def summarize(results: list[dict], table: dict[str, dict]) -> str:
    """정답 소분류가 등급표에 있는 문서만 센다. 소분류가 틀려도 같은 등급이면 일치로 본다.
    하향 오류는 표시 등급과 보수 처리(handling_grade) 뒤 두 가지로 센다. 사람에게 넘긴 문서는 미산정이거나 합산 미확정인 것이다."""
    rows = [r for r in results if r.get("status") != "error" and r.get("gold_code") in table]
    match, handed, down, down_floor, wrong, wrong_down = 0, 0, [], 0, 0, 0
    by_grade = Counter()
    for r in rows:
        gold = table[r["gold_code"]]["grade"]
        got = grade_fields(r, table).get("security_grade", UNGRADED)
        by_grade[gold] += 1
        match += got == gold
        handed += got == UNGRADED or (r.get("cross_check") or {}).get("confirmed") is False
        is_down = got != UNGRADED and GRADES.index(got) > GRADES.index(gold)
        if is_down:
            down.append(f"  {r['file']} · {r['gold_code']} {gold} → {r.get('minor_code')} {got}")
        down_floor += GRADES.index(handling_grade(r, table)) > GRADES.index(gold)
        if r.get("minor_code") != r["gold_code"]:
            wrong += 1
            wrong_down += is_down
    n = len(rows) or 1
    lines = [
        f"등급표에 있는 문서 {len(rows)}건 (" + ", ".join(f"{g} {by_grade[g]}" for g in GRADES) + ")",
        f"등급 일치 {match}건 ({match / n:.1%}) · 사람에게 넘김(「기타」·미산정·합산 미확정) {handed}건 ({handed / n:.1%})",
        f"하향 오류 {len(down)}건 · 미확정을 {FLOOR} 이상으로 보수 처리하면 {down_floor}건",
        f"소분류 오분류 {wrong}건 중 등급 하향 {wrong_down}건" + (f" ({wrong_down / wrong:.1%})" if wrong else ""),
    ]
    return "\n".join(lines + (["하향 오류 (표시 등급)"] + down if down else []))


def _load(path: Path) -> list[dict]:
    """파일명별 마지막 줄 (오류 후 재실행한 문서는 뒤의 성공 줄이 남는다)."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    return list({r["file"]: r for r in rows}.values())


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="dev 결과의 보안 등급 일치율·하향 오류 집계 (API 호출 없음)")
    ap.add_argument("predictions", type=Path, nargs="+")
    ap.add_argument("--grades", type=Path, default=GRADES_PATH)
    ap.add_argument("--gemini", type=Path, help="같은 세트의 Gemini 결과. 주면 합산 확정(cross_check) 뒤 결과로 센다 (Qwen 결과는 1개만)")
    args = ap.parse_args(argv)
    table = load_grades(args.grades)
    if not table:
        ap.error(f"등급표가 없거나 비어 있습니다: {args.grades}")
    if args.gemini:
        if len(args.predictions) != 1:
            ap.error("--gemini를 쓸 때는 Qwen 결과 파일을 하나만 줍니다")
        from .cross_check import cross_check

        qwen = {r["file"]: r for r in _load(args.predictions[0])}
        gemini = {r["file"]: r for r in _load(args.gemini)}
        results = [cross_check(qwen.get(f) or {"status": "error"}, gemini.get(f) or {"status": "error"})
                   for f in sorted(set(qwen) | set(gemini))]
    else:
        results = [r for p in args.predictions for r in _load(p)]
    print(summarize(results, table))


if __name__ == "__main__":
    main()
