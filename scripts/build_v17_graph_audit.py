#!/usr/bin/env python3
"""Build the pre-execution V17 graph coverage audit from frozen artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audits"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def tabular_range(model_id: str) -> tuple[str, str, str]:
    dims, hidden, params = [], [], []
    for path in sorted((ROOT / "datasets/tabular_suite").glob(f"*/{model_id}/model.json")):
        model = json.loads(path.read_text())
        dim = int(model["input_dim"])
        dims.append(dim)
        scaled = model["scaled_model_for_ckks"]
        units = len(scaled.get("hidden_weights", []))
        hidden.append(units)
        if units:
            params.append(units * dim + units + units + 1)
        else:
            params.append(dim + 1)
    fmt = lambda xs: str(xs[0]) if min(xs) == max(xs) else f"{min(xs)}-{max(xs)}"
    return fmt(dims), fmt(hidden), fmt(params)


def rows() -> list[dict[str, object]]:
    linear_dim, _, linear_params = tabular_range("linear_poly3")
    mlp_dim, mlp_hidden, mlp_params = tabular_range("mlp_square_linear_score")
    common = {
        "class_count": 2,
        "decision_rule": "binary threshold",
        "rotations": 0,
        "bootstrap_count": 0,
        "packing_strategy": "one replicated scalar per ciphertext",
        "scalar_replicated": True,
    }
    result = [
        dict(common, model_id="linear_affine_score", paper_facing_name="Linear body with affine output (controlled ablation)", task="binary classification", input_shape=linear_dim, parameter_count=linear_params, multiplicative_depth=0, required_levels=0, ct_ct_multiplications=0, ct_pt_multiplications=f"input_dim+1", additions=f"input_dim+1", rescale_count=0, slot_count=1, output_head="affine", existing_candidate_metrics="none; V17 adapter added before protocol freeze", existing_independent_evaluation="none", implementation_gap="plaintext artifacts and V17 run required"),
        dict(common, model_id="linear_poly3", paper_facing_name="Cubic-polynomial threshold model", task="binary classification", input_shape=linear_dim, parameter_count=linear_params, multiplicative_depth=2, required_levels=3, ct_ct_multiplications=2, ct_pt_multiplications="input_dim+2", additions="input_dim+2", rescale_count=2, slot_count=1, output_head="fixed cubic polynomial", existing_candidate_metrics="full legacy 5-dataset direct/catalog/latency", existing_independent_evaluation="50/50 legacy locked audit", implementation_gap="outer-fold retraining and V17 depth-complete oracle"),
        dict(common, model_id="mlp_square_linear_score", paper_facing_name="Shallow square-activation MLP", task="binary classification", input_shape=mlp_dim, parameter_count=mlp_params, multiplicative_depth=1, required_levels=4, ct_ct_multiplications=mlp_hidden, ct_pt_multiplications="hidden*input_dim+hidden+1", additions="hidden*input_dim+hidden+1", rescale_count=1, slot_count=1, output_head="affine", existing_candidate_metrics="full legacy 5-dataset direct/catalog/latency", existing_independent_evaluation="50/50 legacy locked audit", implementation_gap="outer-fold retraining and V17 depth-complete oracle"),
        dict(common, model_id="mlp_square_poly3", paper_facing_name="Square MLP with cubic output (controlled ablation)", task="binary classification", input_shape=mlp_dim, parameter_count=mlp_params, multiplicative_depth=3, required_levels=10, ct_ct_multiplications=f"{mlp_hidden}+2", ct_pt_multiplications="hidden*input_dim+hidden+3", additions="hidden*input_dim+hidden+3", rescale_count=3, slot_count=1, output_head="fixed cubic polynomial", existing_candidate_metrics="25 selections, 24 PASS + 1 reserve-policy REJECT audit", existing_independent_evaluation="25 structural locked audits", implementation_gap="outer-fold retraining and exhaustive V17 oracle"),
        dict(common, model_id="mlp_square2_linear_score", paper_facing_name="Two-hidden-layer square-activation MLP", task="binary classification", input_shape="4-16", parameter_count="trained per fold", multiplicative_depth=2, required_levels=6, ct_ct_multiplications=12, ct_pt_multiplications="69-165", additions="69-165", rescale_count=2, slot_count=1, output_head="affine", existing_candidate_metrics="P3 smoke: first candidate SAFE on banknote fold 0", existing_independent_evaluation="smoke-only independent replay pending protocol freeze", implementation_gap="full outer-fold and finite-oracle execution pending"),
        {
            "model_id": "mnist_mlp_square_784_100_10_v1", "paper_facing_name": "MNIST MLP-100", "task": "10-class classification", "class_count": 10, "input_shape": "784", "parameter_count": 79510, "multiplicative_depth": 1, "required_levels": 3, "ct_ct_multiplications": 100, "ct_pt_multiplications": 79400, "additions": 79400, "rotations": 0, "rescale_count": 1, "bootstrap_count": 0, "slot_count": 500, "packing_strategy": "feature ciphertexts; sample batching across slots", "scalar_replicated": False, "decision_rule": "multiclass argmax", "output_head": "10 affine logits", "existing_candidate_metrics": "direct, 7-profile catalog, 5400 paired latency records", "existing_independent_evaluation": "500 validation + 500 locked audit", "implementation_gap": "training-seed and depth-complete V17 accounting",
        },
        {
            "model_id": "mnist_lenet5_small_square_v1", "paper_facing_name": "FHE-compatible LeNet-5-small", "task": "10-class classification", "class_count": 10, "input_shape": "1x28x28", "parameter_count": 59086, "multiplicative_depth": 4, "required_levels": 16, "ct_ct_multiplications": "square activations across conv/FC stages", "ct_pt_multiplications": 421984, "additions": 418648, "rotations": 0, "rescale_count": 4, "bootstrap_count": 0, "slot_count": 500, "packing_strategy": "feature ciphertexts; sample batching across slots", "scalar_replicated": False, "decision_rule": "multiclass argmax", "output_head": "10 affine logits", "existing_candidate_metrics": "direct only; legacy catalog 7/7 PLAN_UNSUPPORTED", "existing_independent_evaluation": "500 validation + 500 locked audit", "implementation_gap": "not spatially packed; V17 depth-complete oracle and latency missing",
        },
        {
            "model_id": "cnn_lite_square_binary01", "paper_facing_name": "CNN-lite system regression graph", "task": "binary classification", "class_count": 2, "input_shape": "4x4 pooled image", "parameter_count": 57, "multiplicative_depth": 1, "required_levels": 3, "ct_ct_multiplications": 36, "ct_pt_multiplications": 180, "additions": 180, "rotations": 0, "rescale_count": 1, "bootstrap_count": 0, "slot_count": 1, "packing_strategy": "scalar replicated per pixel ciphertext", "scalar_replicated": True, "decision_rule": "binary threshold", "output_head": "affine", "existing_candidate_metrics": "selection and locked audit only", "existing_independent_evaluation": "250 + 250", "implementation_gap": "not true packed; cannot satisfy P6",
        },
        {
            "model_id": "packed_cnn_lite_binary01_v17", "paper_facing_name": "True-packed CNN-lite (predeclared P6)", "task": "binary classification", "class_count": 2, "input_shape": "4x4 pooled image in one ciphertext", "parameter_count": 57, "multiplicative_depth": 2, "required_levels": 4, "ct_ct_multiplications": 4, "ct_pt_multiplications": 212, "additions": 180, "rotations": 11, "rescale_count": 2, "bootstrap_count": 0, "slot_count": 16, "packing_strategy": "spatial slots with rotations", "scalar_replicated": False, "decision_rule": "binary threshold", "output_head": "packed affine reduction", "existing_candidate_metrics": "P6 smoke: first candidate SAFE on 8 images x 3 keys", "existing_independent_evaluation": "full 250-image audit pending protocol freeze", "implementation_gap": "full selection, finite-oracle, independent-evaluation, and latency execution pending",
        },
        {
            "model_id": "sobel_edge_score", "paper_facing_name": "Sobel edge-energy regression check", "task": "thresholded image operator", "class_count": 2, "input_shape": "3x3 patch", "parameter_count": 0, "multiplicative_depth": 1, "required_levels": 2, "ct_ct_multiplications": 2, "ct_pt_multiplications": 12, "additions": 11, "rotations": 0, "rescale_count": 1, "bootstrap_count": 0, "slot_count": 1, "packing_strategy": "scalar replicated", "scalar_replicated": True, "decision_rule": "binary threshold", "output_head": "gradient energy", "existing_candidate_metrics": "selection and audit", "existing_independent_evaluation": "400 + 400", "implementation_gap": "operation-coverage evidence only",
        },
        {
            "model_id": "harris_corner_response", "paper_facing_name": "Harris corner-response regression check", "task": "thresholded image operator", "class_count": 2, "input_shape": "5x5 patch", "parameter_count": 0, "multiplicative_depth": 2, "required_levels": 5, "ct_ct_multiplications": 142, "ct_pt_multiplications": "included in logical mul count", "additions": 146, "rotations": 0, "rescale_count": 2, "bootstrap_count": 0, "slot_count": 1, "packing_strategy": "scalar replicated", "scalar_replicated": True, "decision_rule": "binary threshold", "output_head": "corner response", "existing_candidate_metrics": "selection and audit", "existing_independent_evaluation": "200 + 200", "implementation_gap": "operation-coverage evidence only",
        },
        {
            "model_id": "depth_ladder_D1_D2_D4_D6_D8", "paper_facing_name": "Predeclared polynomial depth ladder", "task": "synthetic threshold decision", "class_count": 2, "input_shape": "bounded scalar [0.98,1.02]", "parameter_count": 0, "multiplicative_depth": "1,2,4,6,8", "required_levels": "1,2,4,6,8", "ct_ct_multiplications": "1,2,4,6,8", "ct_pt_multiplications": 0, "additions": 0, "rotations": 0, "rescale_count": "1,2,4,6,8", "bootstrap_count": 0, "slot_count": 1, "packing_strategy": "scalar replicated", "scalar_replicated": True, "decision_rule": "binary threshold at 1.0", "output_head": "repeated square", "existing_candidate_metrics": "none", "existing_independent_evaluation": "not applicable: controlled graph stress", "implementation_gap": "smoke and full finite-depth execution pending; unsupported remains distinct from NO_SAFE",
        },
    ]
    return result


def write_csv(path: Path, records: list[dict[str, object]]) -> None:
    fields = list(records[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    records = rows()
    fingerprint_rows = [dict(row, graph_digest=digest(row)) for row in records]
    write_csv(OUT / "v17_graph_fingerprints.csv", fingerprint_rows)
    write_csv(OUT / "model_family_inventory_v17.csv", fingerprint_rows)
    operations = []
    for row in records:
        operations.append({
            "model_id": row["model_id"],
            "affine": "yes",
            "ct_ct_mul": "yes" if str(row["ct_ct_multiplications"]) != "0" else "no",
            "polynomial": "yes" if "poly" in str(row["model_id"]) or "depth_ladder" in str(row["model_id"]) else "no",
            "rotation": "yes" if str(row["rotations"]) not in {"0", ""} else "no",
            "spatial_packing": "yes" if "spatial" in str(row["packing_strategy"]) else "no",
            "multiclass": "yes" if int(row["class_count"]) > 2 else "no",
            "depth_ge_2": "yes" if str(row["multiplicative_depth"]) not in {"0", "1"} else "no",
            "evidence_role": "planned_primary" if row["model_id"] in {"mlp_square2_linear_score", "packed_cnn_lite_binary01_v17", "depth_ladder_D1_D2_D4_D6_D8"} else "existing_or_reused",
        })
    write_csv(OUT / "v17_operation_coverage_matrix.csv", operations)

    text = """# V17 Graph Coverage Audit

## Scope and sources

This audit binds the current implementation and frozen evidence before any V17 encrypted result. Primary sources are `internal/ckksplanner`, `internal/ckksbackend`, `internal/journalmnist`, `datasets/tabular_suite`, and the frozen structural, multiclass, CNN-lite, Sobel, and Harris evidence packs.

## Required findings

1. **The four tabular combinations are one shallow binary scalar-replicated family matrix.** They isolate linear versus one-hidden-square bodies and affine versus cubic heads, but they do not supply four independent architecture families.
2. **The frozen LeNet-5-small is not a true spatially packed convolution.** It has two convolution stages and depth four, but `rot_ops=0`; feature ciphertexts batch samples across slots. It therefore fails the V17 P5 gate requiring rotations and spatial packing.
3. **CNN-lite is scalar-replicated.** The model and executor explicitly bind `scalar_replicated_per_ciphertext_v1`; every pooled pixel is encrypted separately.
4. **MLP-100 already has direct, finite-catalog, decision-stability, audit, and paired-latency evidence.** LeNet has direct and locked-audit evidence but the legacy catalog is depth-incomplete and its latency is descriptive only. V17 must add a depth-complete finite reference rather than treat 7/7 `PLAN_UNSUPPORTED` as `NO_SAFE`.
5. **The legacy candidate set is not depth complete.** It covers six of seven profiles for MLP-100 but zero of seven for LeNet-5-small. A graph-derived V17 finite set must be frozen before new results.
6. **The minimum synthesis floor masks some configuration variation.** Existing shallow tabular plans commonly collapse to the minimum scale tier, while the structural MLP, MLP-100, and LeNet select materially different Q-chain/scale requirements. V17 must report both collapse and adaptation.

## P6 pre-execution decision

Because P5 fails the rotation/spatial-packing gate and the existing CNN-lite is the nearest implemented learned convolution, V17 predeclares `packed_cnn_lite_binary01_v17`: the same 4x4 learned CNN-lite computation mapped to one spatially packed ciphertext with explicit rotations. This preserves model semantics while testing packing rather than introducing a new dataset or an unrelated architecture.

## Primary versus supporting roles

- Controlled ablation: the four body-by-head tabular combinations.
- Primary: cubic linear threshold model, shallow square MLP, two-hidden-square MLP, MLP-100, LeNet-5-small, and the conditional true-packed CNN-lite.
- Stress: the D1/D2/D4/D6/D8 depth ladder.
- Supporting regression: Sobel and Harris.

No broad claim is opened by this audit. Claim admission requires completed V17 metrics, a depth-complete finite oracle, independent evaluation, false-NO_SAFE reporting, and latency regret.
"""
    (OUT / "V17_GRAPH_COVERAGE_AUDIT.md").write_text(text, encoding="utf-8")
    model_audit = """# Model Family Audit V17

## Verdict

The original `linear_poly3` and `mlp_square_linear_score` pair was not forced by CKKS theory. It was a development-stage controlled choice that held data, binary threshold semantics, scalar-replicated packing, and most execution machinery constant while varying a cubic output polynomial versus a square hidden layer. The pair is useful for a narrow controlled study, but it cannot independently identify the effects of body nonlinearity and output-head degree and cannot support heterogeneous encrypted-inference breadth by itself.

## Controlled 2x2 interpretation

`linear_affine_score`, `linear_poly3`, `mlp_square_linear_score`, and `mlp_square_poly3` fill the body-by-head matrix. Their role is factor isolation: linear versus one-hidden square body, affine versus cubic head, and the interaction. They remain shallow binary scalar-replicated computations and must be counted as one controlled ablation matrix, not four unrelated primary architectures.

## Executability audit

- The generic tabular runtime can execute a linear body with an affine head; no dataset-specific CKKS branch is required.
- The two-hidden-square adapter adds genuine hidden depth with the same generic body/head interface. Its representative P3 smoke graph has depth 2, 12 ciphertext-ciphertext squares, 6 consumed rescale levels, and 9 required Q primes.
- Existing `mlp_square_poly3` artifacts covered five datasets in prior evidence, but V17 retrains it only on the three predeclared ablation datasets and evaluates it under the new split and finite-reference protocol.
- The two original families alone confound body and head effects because they occupy opposite diagonal cells of the 2x2 matrix.
- MLP-100 contributes width and multiclass argmax. LeNet-5-small contributes a deeper convolutional operation graph but uses feature-ciphertext sample batching, not spatial packed convolution.
- The predecessor CNN-lite is scalar replicated. The predeclared P6 adapter preserves its learned function while mapping a 4x4 image into sixteen spatial slots and executing 11 rotations.

## Claim consequence

The broad title is not admitted by implementation alone. It requires completed full metrics for at least five structurally distinct primary families, a true packed graph, the D1/D2/D4/D6/D8 ladder, depth-complete fastest-SAFE references, latency regret, false-NO_SAFE disclosure, and independent-evaluation outcomes. Until those ledgers complete, the result is `NOT_EVALUATED`, not a breadth success.
"""
    (OUT / "MODEL_FAMILY_AUDIT_V17.md").write_text(model_audit, encoding="utf-8")
    justification = """# V17 Model Suite Justification

The suite is organized by CKKS-relevant structural variation rather than by row count. The controlled 2x2 matrix estimates body and output-head effects. P3 adds genuine hidden depth. P4 adds width and multiclass argmax. P5 adds a deep convolutional computation but not spatial packing. P6 therefore isolates true packed rotations using the nearest existing learned CNN-lite semantics. The depth ladder tests whether graph-derived configuration synthesis responds monotonically to required levels independent of model quality.

This organization prevents three invalid interpretations: counting the four tabular cells as unrelated architectures, treating a depth-incomplete catalog as proof of global infeasibility, and calling sample-batched feature ciphertexts a packed convolution. Sobel and Harris remain useful regression evidence but are not counted as encrypted-inference primary families.
"""
    (OUT / "V17_MODEL_SUITE_JUSTIFICATION.md").write_text(justification, encoding="utf-8")
    print(json.dumps({"status": "AUDIT_COMPLETE", "models": len(records)}, sort_keys=True))


if __name__ == "__main__":
    main()
