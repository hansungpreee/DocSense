"""
predictions.jsonl 파일을 읽어 상세 평가(Macro-F1, 소분류별 F1, 혼동행렬)를 출력하고
마크다운 리포트(eval_report.md)를 자동 저장하는 스크립트.
split=ood 줄은 따로 채점한다: status가 pending_review(「기타」)이면 정답.

사용법:
    python src/eval/evaluate.py --pred results/v1/predictions.jsonl
    python src/eval/evaluate.py --pred results/v2/predictions.jsonl results/v2_ood/predictions.jsonl
"""
import os
import csv
import math
import json
import argparse
from collections import defaultdict, Counter

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """정확도 k/n의 Wilson 95% 신뢰구간 (0~1). 표본이 작거나 100%에 가까워도 0~1을 벗어나지 않는다."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, center - half), min(1.0, center + half)


def ci_text(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"95% CI {lo * 100:.1f}~{hi * 100:.1f}%"


def load_records(pred_paths: list[str]) -> list[dict]:
    records = []
    for path in pred_paths:
        with open(path, "r", encoding="utf-8-sig") as f:
            records += [json.loads(line) for line in f if line.strip()]
    return records


def latest_per_file(records: list[dict]) -> list[dict]:
    """같은 파일이 여러 줄이면(오류 후 run.py 재실행) 마지막 줄만 남긴다. 채점은 이 결과로 한다."""
    return list({r["file"]: r for r in records}.values())


def count_line(rows: list[dict], records: list[dict], ok: list[dict]) -> str:
    """평가 문서 수 줄. 재실행으로 대체된 줄이 있으면 함께 적는다."""
    replaced = len(rows) - len(records)
    note = f", 재실행으로 대체된 줄 {replaced}개 제외" if replaced else ""
    return f"- **평가 문서 수**: 총 {len(records)}건 (성공 {len(ok)}건, 오류 {len(records) - len(ok)}건{note})"


def token_lines(records: list[dict]) -> list[str]:
    """usage가 있는 줄의 토큰을 모두 더한다. 오류·재실행 줄도 실제로 쓴 토큰이므로 포함."""
    used = [r["usage"] for r in records if r.get("usage")]
    if not used:  # PR #5 이전 결과에는 usage가 없다
        return []
    inp = sum(u.get("input_tokens", 0) for u in used)
    out = sum(u.get("output_tokens", 0) for u in used)
    return [f"- **토큰 사용량**: 입력 {inp:,} + 출력 {out:,} = **{inp + out:,}** "
            f"(usage 기록 {len(used)}줄, 오류·재실행 포함)"]


def report_path(pred_paths: list[str]) -> str:
    """리포트는 첫 번째 --pred 파일과 같은 폴더에 저장한다."""
    return os.path.join(os.path.dirname(pred_paths[0]), "eval_report.md")


# 2주 차 회의 계획 5절 + 분류 체계 누락 착각(10-12, #56). 「기타」로 빠진 오답의 경계:
#   제목·양식은 맞게 읽었고 정의 문구와 무관하게 "해당 소분류가 없다"고 하면 누락 착각, 정의 문구가 원인이면 정의 불일치
CAUSE_TAGS = "제목 누락 / 헷갈림 쌍 / 대분류 경계 / 이미지 품질 / 출력 형식 오류 / 정의 불일치 / 분류 체계 누락 착각"


def write_misclassified(records: list[dict], out_dir: str) -> tuple[str, int]:
    """오분류 문서 목록을 CSV로 저장한다. '원인 태그'는 주간 오분류 리뷰에서 사람이 채운다."""
    ok = [r for r in latest_per_file(records) if r.get("status") != "error"]
    wrong = [r for r in ok if r.get("minor_code") != r.get("gold_code")]
    path = os.path.join(out_dir, "misclassified.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:  # 엑셀에서 한글이 깨지지 않게
        w = csv.writer(f)
        w.writerow(["file", "gold_code", "minor_code", "predicted_code", "confidence", "status", "원인 태그"])
        for r in wrong:
            w.writerow([r["file"], r.get("gold_code"), r.get("minor_code"), r.get("predicted_code"),
                        r.get("confidence"), r.get("status"), ""])
    return path, len(wrong)


def save_confusion_png(records: list[dict], out_dir: str) -> str | None:
    """정답(행) × 최종 예측(열) 건수 그림. matplotlib이 없으면 건너뛰고 None을 돌려준다."""
    try:
        import matplotlib
        matplotlib.use("Agg")  # 창 없이 파일로만 그린다
        import matplotlib.pyplot as plt
        from matplotlib.colors import LinearSegmentedColormap
    except ImportError:
        return None

    ok = [r for r in latest_per_file(records) if r.get("status") != "error"]
    gold = sorted({r["gold_code"] for r in ok})
    pred = gold + sorted({r["minor_code"] for r in ok} - set(gold))  # 정답에 없는 코드(NEW-xx 등)는 오른쪽 끝
    counts = Counter((r["gold_code"], r["minor_code"]) for r in ok)
    grid = [[counts[(g, p)] for p in pred] for g in gold]
    top = max(max(row) for row in grid) or 1

    installed = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    korean = [f for f in ("Malgun Gothic", "AppleGothic", "Noto Sans CJK KR", "NanumGothic") if f in installed]
    plt.rcParams["font.family"] = korean + ["DejaVu Sans"]  # 설치된 한글 글꼴만 (없는 글꼴 경고 방지)
    blues = LinearSegmentedColormap.from_list("blues", ["#ffffff", "#cde2fb", "#6da7ec", "#256abf", "#0d366b"])
    fig, ax = plt.subplots(figsize=(1.6 + 0.42 * len(pred), 1.4 + 0.42 * len(gold)), dpi=150)
    ax.imshow(grid, cmap=blues, vmin=0, vmax=top)
    for i, row in enumerate(grid):
        for j, n in enumerate(row):
            if n:  # 0인 칸은 비워 둔다
                ax.text(j, i, n, ha="center", va="center", fontsize=8,
                        color="#ffffff" if n > top * 0.55 else "#1f2328")
    ax.set_xticks(range(len(pred)), pred, rotation=90, fontsize=8)
    ax.set_yticks(range(len(gold)), gold, fontsize=8)
    ax.set_xticks([x - 0.5 for x in range(1, len(pred))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(gold))], minor=True)
    ax.grid(which="minor", color="#ffffff", linewidth=2)  # 칸 사이 2px 여백
    ax.tick_params(which="both", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xlabel("최종 예측 (minor_code)", fontsize=9)
    ax.set_ylabel("정답 (gold_code)", fontsize=9)
    ax.set_title(f"소분류 혼동행렬 · 문서 {len(ok)}건 (대각선이 정답)", fontsize=10, loc="left")
    path = os.path.join(out_dir, "confusion_matrix.png")
    fig.tight_layout()
    fig.savefig(path, facecolor="#ffffff")
    plt.close(fig)
    return path


THRESHOLDS = tuple(round(0.50 + 0.05 * i, 2) for i in range(10))  # 0.50~0.95, 0.05 간격 (2주 차 계획 5절)


def _goes_to_review(r: dict, th: float) -> bool:
    """기준값 th에서 담당자 검토(「기타」)로 가는지. 실행 당시 기준이 이미 적용돼 있으므로 모델의 원래 선택으로 다시 판단한다."""
    return r.get("predicted_code") == "ETC-00" or (r.get("confidence") or 0) < th


def threshold_lines(ok: list[dict], ood_ok: list[dict] | None = None) -> list[str]:
    """확신도 기준값별로 dev 자동 확정과 OOD 「기타」 판정을 함께 본다. 기준을 올리면 OOD는 더 잘 잡히지만 dev 정답도 더 빠진다."""
    n = len(ok)
    right = [r for r in ok if r.get("predicted_code") == r.get("gold_code")]  # 모델이 맞힌 문서
    lines = [
        "## 4. 확신도 기준별 자동 처리",
        "모델이 「기타」를 고르지 않았고 확신도가 기준 이상이면 자동 확정, 나머지는 담당자 검토(「기타」). "
        "현재 기본값은 0.7 (.env `CONFIDENCE_THRESHOLD`).",
        "",
        "| 기준값 | dev 자동 확정 | 자동 확정 정확도 | 자동 확정 중 오답 | dev 정답이 「기타」로 빠짐 | OOD 「기타」 판정 |",
        "| :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for th in THRESHOLDS:
        auto = [r for r in ok if not _goes_to_review(r, th)]
        hit = sum(r.get("predicted_code") == r.get("gold_code") for r in auto)
        acc = f"{hit / len(auto) * 100:.1f}% ({ci_text(hit, len(auto))})" if auto else "-"
        lost = sum(_goes_to_review(r, th) for r in right)
        lost_text = f"{lost}/{len(right)} ({lost / len(right) * 100:.1f}%)" if right else "-"
        if ood_ok:
            caught = sum(_goes_to_review(r, th) for r in ood_ok)
            ood_text = f"{caught}/{len(ood_ok)} ({caught / len(ood_ok) * 100:.1f}%)"
        else:
            ood_text = "-"
        lines.append(f"| {th:.2f} | {len(auto)}/{n} ({len(auto) / n * 100:.1f}%) | {acc} | {len(auto) - hit}건 | "
                     f"{lost_text} | {ood_text} |")
    levels = sorted({r.get("confidence") for r in ok if r.get("confidence") is not None})
    lines += ["", f"- 확신도 값 종류: {len(levels)}개 ({', '.join(str(v) for v in levels[:10])}"
                  f"{' …' if len(levels) > 10 else ''}). 종류가 적으면 기준값을 바꿔도 결과가 계단식으로만 바뀝니다."]
    if not ood_ok:
        lines.append("- OOD 열은 OOD 결과(`--pred`에 split=ood 파일)를 함께 넣으면 채워집니다. 기준값은 최종 OOD셋이 아니라 "
                     "개발용 OOD(`render_ood.py --dev`)로 정합니다.")
    return lines


def variant_lines(ok: list[dict], variants: dict[str, str]) -> list[str]:
    """하드셋 변형별 소분류 정확도. 문서는 첫 페이지(labels.csv의 파일)의 변형으로 나눈다."""
    groups = defaultdict(list)
    for r in ok:
        groups[variants.get(r["file"], "변형 정보 없음")].append(r)
    lines = [
        "## 하드셋 변형별 정확도 (첫 페이지 변형 기준)",
        "문서는 `--variants` CSV에 적힌 첫 페이지(labels.csv의 파일)의 변형으로 묶었습니다. "
        "hard(`hard_variants.csv`)는 페이지마다 변형이 다를 수 있고, hard2(`hard2_dev_variants.csv`)는 문서의 모든 페이지가 같은 변형입니다.",
        "",
        "| 변형 | 문서 수 | 소분류 정확도 |",
        "| :--- | :---: | :---: |",
    ]
    for name in sorted(groups):
        rs = groups[name]
        hit = sum(r.get("minor_code") == r.get("gold_code") for r in rs)
        lines.append(f"| {name} | {len(rs)} | {hit / len(rs) * 100:.1f}% ({hit}/{len(rs)}, {ci_text(hit, len(rs))}) |")
    return lines


def dev_report(records: list[dict], ood: list[dict] | None = None) -> list[str]:
    """체계 안 문서(dev·test): 정답 소분류 코드와 비교."""
    rows, records = records, latest_per_file(records)
    ok = [r for r in records if r.get("status") != "error"]
    if not ok:
        return ["## 체계 안 문서", "- 유효한 분류 결과가 0건입니다."]

    total = len(ok)
    maj_correct = sum(1 for r in ok if r.get("major") == r.get("gold_major"))
    min_correct = sum(1 for r in ok if r.get("minor_code") == r.get("gold_code"))
    first_correct = sum(1 for r in ok if r.get("predicted_code") == r.get("gold_code"))

    # 소분류별 TP, FP, FN 및 혼동행렬 집계
    classes = sorted(list(set(r["gold_code"] for r in ok)))
    stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "support": 0})
    confusion = Counter()

    for r in ok:
        g = r["gold_code"]
        p = r.get("minor_code", "UNK")
        stats[g]["support"] += 1
        if g == p:
            stats[g]["tp"] += 1
        else:
            stats[g]["fn"] += 1
            stats[p]["fp"] += 1
            confusion[(g, p)] += 1

    # 소분류별 Precision, Recall, F1 계산
    class_rows = []
    f1_list = []
    for c in classes:
        tp, fp, fn, sup = stats[c]["tp"], stats[c]["fp"], stats[c]["fn"], stats[c]["support"]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        f1_list.append(f1)
        class_rows.append((c, sup, prec * 100, rec * 100, f1 * 100, tp, sup))

    macro_f1 = (sum(f1_list) / len(f1_list) * 100) if f1_list else 0.0

    # 리포트 텍스트 구성
    lines = [
        "## 1. 전체 성능 요약",
        count_line(rows, records, ok),
        f"- **대분류 정확도 (Major Acc)**: **{maj_correct/total*100:.2f}%** ({maj_correct}/{total}, "
        f"{ci_text(maj_correct, total)})",
        f"- **소분류 정확도 (Minor Acc)**: **{min_correct/total*100:.2f}%** ({min_correct}/{total}, "
        f"{ci_text(min_correct, total)})",
        f"- **소분류 1순위 정확도 (가드레일 전)**: **{first_correct/total*100:.2f}%** ({first_correct}/{total})",
        f"- **소분류 Macro-F1**: **{macro_f1:.2f}%**",
        *token_lines(rows),
        "",
        "## 2. 소분류별 상세 지표 (Precision / Recall / F1)",
        "| 소분류 코드 | 정답 수/전체 | Precision | Recall | F1-Score |",
        "| :--- | :---: | :---: | :---: | :---: |",
    ]
    for c, sup, p, r, f1, tp, tot in class_rows:
        lines.append(f"| **{c}** | {tp}/{tot} | {p:.1f}% | {r:.1f}% | **{f1:.1f}%** |")

    lines += [
        "",
        "## 3. 주요 혼동 행렬 (Top Confusions: 정답 → 오예측)",
    ]
    if confusion:
        lines.append("| 정답 코드 (Gold) | 예측 코드 (Pred) | 발생 건수 |")
        lines.append("| :---: | :---: | :---: |")
        for (g, p), cnt in confusion.most_common(20):
            lines.append(f"| **{g}** | {p} | {cnt}건 |")
    else:
        lines.append("- 오분류 없음 (완벽 일치!)")

    ood_ok = [r for r in latest_per_file(ood or []) if r.get("status") != "error"]
    return lines + [""] + threshold_lines(ok, ood_ok)


def ood_report(records: list[dict]) -> list[str]:
    """체계 밖 문서(split=ood): status가 pending_review(「기타」 NEW-xx)이면 정답."""
    rows, records = records, latest_per_file(records)
    ok = [r for r in records if r.get("status") != "error"]
    lines = ["## 5. OOD 「기타」 판정 (분류 체계 밖 문서)"]
    if not ok:
        return lines + ["- 유효한 분류 결과가 0건입니다."]

    def name_of(r):  # 파일명 OOD-01_법인카드지출결의서_001.png에서 종류 이름을 꺼낸다
        return r["file"].split("_")[1]

    per_kind = defaultdict(list)
    for r in ok:
        per_kind[(r["gold_code"], name_of(r))].append(r)
    hit = sum(r["status"] == "pending_review" for r in ok)

    lines += [
        count_line(rows, records, ok),
        f"- **「기타」 판정률 (전체)**: **{hit / len(ok) * 100:.2f}%** ({hit}/{len(ok)}, {ci_text(hit, len(ok))})",
        *token_lines(rows),
        "",
        "| OOD 종류 | 「기타」 판정 | 판정률 |",
        "| :--- | :---: | :---: |",
    ]
    for (code, name), rs in sorted(per_kind.items()):
        n = sum(r["status"] == "pending_review" for r in rs)
        lines.append(f"| **{code}** {name} | {n}/{len(rs)} | {n / len(rs) * 100:.1f}% |")

    lines += ["", "### 제안된 분류명 (종류별, 많은 순)"]
    for (code, name), rs in sorted(per_kind.items()):
        names = Counter((r.get("new_class") or {}).get("proposed_name") or "(이름 없음)"
                        for r in rs if r["status"] == "pending_review")
        listed = ", ".join(f"{n} {c}건" for n, c in names.most_common()) or "-"
        lines.append(f"- **{code}** {name}: {listed}")

    wrong = [r for r in ok if r["status"] != "pending_review"]
    lines += ["", f"### 정식 분류로 확정된 OOD 문서 {len(wrong)}건 (오답)"]
    lines += [f"- {r['file']} → {r.get('minor_code')} (확신도 {r.get('confidence')})" for r in wrong]
    return lines


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pred", nargs="+", default=["results/v1/predictions.jsonl"],
                        help="predictions.jsonl 경로 (여러 개 가능: dev 결과와 OOD 결과를 함께 넣으면 따로 채점)")
    parser.add_argument("--variants", help="하드셋 결과일 때 변형 기록 CSV (data/meta/hard_variants.csv) → 변형별 정확도")
    args = parser.parse_args()

    missing = [p for p in args.pred + ([args.variants] if args.variants else []) if not os.path.exists(p)]
    if missing:
        raise SystemExit(f"⚠️ 파일을 찾을 수 없습니다: {', '.join(missing)}")

    records = load_records(args.pred)
    dev = [r for r in records if r.get("split") != "ood"]  # split이 없는 옛 결과는 체계 안 문서로 본다
    ood = [r for r in records if r.get("split") == "ood"]

    lines = [f"# 📊 상세 평가 리포트 ({', '.join(args.pred)})", ""]
    if dev:
        lines += dev_report(dev, ood)
    if dev and args.variants:
        with open(args.variants, encoding="utf-8-sig") as f:
            variants = {row["file"]: row["variant"] for row in csv.DictReader(f)}
        dev_ok = [r for r in latest_per_file(dev) if r.get("status") != "error"]
        lines += [""] + variant_lines(dev_ok, variants)
    if ood:
        lines += ([""] if dev else []) + ood_report(ood)
    report_text = "\n".join(lines)
    print(report_text)

    out_md = report_path(args.pred)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(report_text + "\n")
    print(f"\n✅ 마크다운 평가 리포트 저장 완료: {out_md}")

    if dev:  # 오분류 목록과 혼동행렬은 체계 안 문서만
        out_dir = os.path.dirname(out_md)
        csv_path, n_wrong = write_misclassified(dev, out_dir)
        print(f"✅ 오분류 목록 저장 완료: {csv_path} ({n_wrong}건, '원인 태그' 열에 {CAUSE_TAGS} 중 하나를 적어 주세요)")
        png_path = save_confusion_png(dev, out_dir)
        if png_path:
            print(f"✅ 혼동행렬 그림 저장 완료: {png_path}")
        else:
            print("⚠️ matplotlib이 없어 혼동행렬 그림은 건너뜀 (pip install -r requirements.txt)")