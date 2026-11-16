#!/usr/bin/env python3
"""Compare the frozen V17 as-run primary tabular results with the step-0
ciphertext-scale constant-encoding re-measurement. Read-only on both inputs;
writes a Markdown report and CSV files under runs/<run-id>/analysis/.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "results/model_family_expansion_v17/runs/v17_final_vm1x6_20260811T050104Z/primary"
MODEL_LABEL = {
    "linear_poly3": "다항식",
    "mlp_square_linear_score": "1층 MLP",
    "mlp_square2_linear_score": "2층 MLP",
}
DATASET_LABEL = {
    "banknote": "Banknote", "digits_binary": "Digits", "iris_binary": "Iris",
    "mnist_pool16": "MNIST(짝·홀)", "wdbc": "WDBC",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def error_structure(trial: dict) -> dict:
    by_input = collections.defaultdict(list)
    for row in trial.get("sample_ledger", []):
        by_input[row["sample_id"]].append(row["ckks_score"] - row["plaintext_score"])
    if not by_input:
        return {"bias": float("nan"), "key_sd": float("nan"), "inputs": 0}
    means = [st.mean(v) for v in by_input.values()]
    sds = [st.pstdev(v) for v in by_input.values()]
    return {"bias": st.mean(means), "key_sd": st.mean(sds), "inputs": len(means)}


def describe(case_dir: Path) -> dict | None:
    selection = load(case_dir / "selection.json")
    if selection is None:
        return None
    audit = load(case_dir / "direct_independent_evaluation.json") or {}
    initial, final = selection["trials"][0], selection["trials"][-1]
    selected = selection.get("selected") or {}
    params = selected.get("parameters", {})
    structure = error_structure(initial)
    budget = selection["plan"]["contract"]["decision"]["output_error_budget"]
    return {
        "initial_scale": initial["candidate"]["parameters"]["log_default_scale"],
        "initial_status": initial["status"],
        "initial_flips": initial.get("decision_flips", 0),
        "initial_violations": initial.get("error_violations", 0),
        "initial_max_error": initial.get("max_observed_error", float("nan")),
        "initial_max_usage": initial.get("max_error_budget_usage", float("nan")),
        "initial_bias": structure["bias"],
        "initial_key_sd": structure["key_sd"],
        "selection_inputs": structure["inputs"],
        "min_budget": budget,
        "outcome": selection.get("outcome", ""),
        "trials": selection.get("trials_used", len(selection["trials"])),
        "selected_scale": params.get("log_default_scale"),
        "selected_log_n": params.get("log_n"),
        "selected_q": len(params.get("log_q", [])) or None,
        "final_mean_ms": final.get("mean_total_ms"),
        "initial_mean_ms": initial.get("mean_total_ms"),
        "independent_status": audit.get("status", ""),
        "independent_flips": audit.get("decision_flips", 0),
        "independent_violations": audit.get("error_violations", 0),
        "independent_usage": audit.get("max_error_budget_usage"),
        "independent_v_cert": audit.get("v_cert"),
        "independent_v_amb": audit.get("v_amb"),
    }


def aggregate(rows: list[dict], prefix: str) -> dict:
    return {
        "cases": len(rows),
        "initial_rejected": sum(r[prefix + "initial_status"] != "SAFE" for r in rows),
        "initial_cases_with_flip": sum(r[prefix + "initial_flips"] > 0 for r in rows),
        "initial_flip_events": sum(r[prefix + "initial_flips"] for r in rows),
        "initial_violation_events": sum(r[prefix + "initial_violations"] for r in rows),
        "evaluations": sum(r[prefix + "trials"] for r in rows),
        "selected": sum(r[prefix + "outcome"] == "SELECTED" for r in rows),
        "independent_safe": sum(r[prefix + "independent_status"] == "SAFE" for r in rows),
        "independent_flip_events": sum(r[prefix + "independent_flips"] for r in rows),
        "independent_violation_events": sum(r[prefix + "independent_violations"] for r in rows),
    }


def fmt(value, digits=5):
    if value is None:
        return "–"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run = ROOT / "runs" / args.run_id
    out = run / "analysis"
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for frozen_dir in sorted(FROZEN.glob("*/*/fold_*/training_seed_0")):
        dataset, model, fold = frozen_dir.parts[-4], frozen_dir.parts[-3], frozen_dir.parts[-2]
        if model not in MODEL_LABEL:
            continue
        relative = Path(dataset) / model / fold / "training_seed_0"
        frozen = describe(frozen_dir)
        exact = describe(run / "ciphertext_scale" / relative) if (run / "ciphertext_scale" / relative / "case_summary.json").is_file() else None
        control = describe(run / "default_scale" / relative) if (run / "default_scale" / relative / "case_summary.json").is_file() else None
        row = {"dataset": dataset, "model": model, "fold": fold}
        for prefix, data in (("frozen_", frozen), ("exact_", exact), ("control_", control)):
            for key, value in (data or {}).items():
                row[prefix + key] = value
        row["has_exact"] = exact is not None
        row["has_control"] = control is not None
        rows.append(row)

    fields = sorted({k for r in rows for k in r})
    with (out / "case_comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    done = [r for r in rows if r["has_exact"]]
    lines = [f"# Step-0 재측정 비교 ({args.run_id})", "",
             f"완료된 사례: {len(done)} / {len(rows)} (주요 정형 사례). 동결값은 V17 as-run 기록, 수정값은 상수를 암호문 스케일로 인코딩한 실행.", ""]

    if done:
        a, b = aggregate(done, "frozen_"), aggregate(done, "exact_")
        lines += ["## 1. 전체 요약 (같은 사례끼리 비교)", "",
                  "| 항목 | 동결(as-run) | 수정(암호문 스케일) |", "|---|---:|---:|"]
        labels = [("cases", "사례 수"), ("initial_rejected", "초기 구성 거부 사례"),
                  ("initial_cases_with_flip", "초기 구성에서 실제 판정 변화가 있던 사례"),
                  ("initial_flip_events", "초기 구성 판정 변화 횟수(입력×키)"),
                  ("initial_violation_events", "초기 구성 오차 위반 횟수(입력×키)"),
                  ("evaluations", "구성 평가 횟수 합계"), ("selected", "구성 선택 성공"),
                  ("independent_safe", "별도 입력 재평가 수용"),
                  ("independent_flip_events", "별도 입력 판정 변화 횟수"),
                  ("independent_violation_events", "별도 입력 오차 위반 횟수")]
        for key, label in labels:
            lines.append(f"| {label} | {a[key]} | {b[key]} |")
        lines.append("")

        lines += ["## 2. 조합별 초기 구성 결과와 오차 구조", "",
                  "편향은 입력별 키 평균 부호 오차의 평균, 잡음은 키 사이 표준편차의 평균(선택용 입력).", "",
                  "| 조합 | 사례 | 초기 거부 (동결→수정) | 판정 변화 사례 (동결→수정) | 판정 변화 횟수 | 오차 위반 횟수 | 편향 (동결→수정) | 잡음 SD (동결→수정) | 선택 스케일 (동결→수정) | 별도 입력 수용 (동결→수정) |",
                  "|---|---:|---|---|---|---|---|---|---|---|"]
        groups = collections.defaultdict(list)
        for r in done:
            groups[(r["dataset"], r["model"])].append(r)
        for (dataset, model), group in sorted(groups.items(), key=lambda kv: (list(MODEL_LABEL).index(kv[0][1]), kv[0][0])):
            fa, ea = aggregate(group, "frozen_"), aggregate(group, "exact_")
            def scales(prefix):
                return "/".join(str(s) for s in sorted({r[prefix + "selected_scale"] for r in group}, key=lambda v: (v is None, v)))
            lines.append(
                f"| {DATASET_LABEL.get(dataset, dataset)} {MODEL_LABEL[model]} | {len(group)} | "
                f"{fa['initial_rejected']}→{ea['initial_rejected']} | {fa['initial_cases_with_flip']}→{ea['initial_cases_with_flip']} | "
                f"{fa['initial_flip_events']}→{ea['initial_flip_events']} | {fa['initial_violation_events']}→{ea['initial_violation_events']} | "
                f"{st.mean(r['frozen_initial_bias'] for r in group):+.5f}→{st.mean(r['exact_initial_bias'] for r in group):+.5f} | "
                f"{st.mean(r['frozen_initial_key_sd'] for r in group):.5f}→{st.mean(r['exact_initial_key_sd'] for r in group):.5f} | "
                f"{scales('frozen_')}→{scales('exact_')} | {fa['independent_safe']}→{ea['independent_safe']} |")
        lines.append("")

        changed = [r for r in done if (r["frozen_selected_scale"], r["frozen_selected_log_n"], r["frozen_selected_q"]) !=
                   (r["exact_selected_scale"], r["exact_selected_log_n"], r["exact_selected_q"])]
        lines += ["## 3. 선택 구성이 달라진 사례", ""]
        if changed:
            lines += ["| 사례 | 동결 선택 (logN, Q, 스케일) | 수정 선택 | 수정 평가 횟수 |", "|---|---|---|---:|"]
            for r in changed:
                lines.append(f"| {r['dataset']}/{r['model']}/{r['fold']} | ({r['frozen_selected_log_n']}, {r['frozen_selected_q']}, {r['frozen_selected_scale']}) | "
                             f"({r['exact_selected_log_n']}, {r['exact_selected_q']}, {r['exact_selected_scale']}) | {r['exact_trials']} |")
        else:
            lines.append("없음.")
        lines.append("")

    controls = [r for r in rows if r["has_control"]]
    if controls:
        lines += ["## 4. 대조: 같은 새 바이너리의 기본 스케일 방식이 동결 결과를 재현하는가", "",
                  "| 사례 | 초기 상태 (동결/대조) | 판정 변화 (동결/대조) | 오차 위반 (동결/대조) | 편향 (동결/대조) | 선택 스케일 (동결/대조) |",
                  "|---|---|---|---|---|---|"]
        for r in controls:
            lines.append(f"| {r['dataset']}/{r['model']}/{r['fold']} | {r['frozen_initial_status']}/{r['control_initial_status']} | "
                         f"{r['frozen_initial_flips']}/{r['control_initial_flips']} | {r['frozen_initial_violations']}/{r['control_initial_violations']} | "
                         f"{r['frozen_initial_bias']:+.5f}/{r['control_initial_bias']:+.5f} | {r['frozen_selected_scale']}/{r['control_selected_scale']} |")
        lines.append("")

    (out / "COMPARISON.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
