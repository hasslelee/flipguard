#!/usr/bin/env python3
"""Data-only adapter to the frozen reference trainer; never reads CKKS results."""
import csv
import hashlib
import importlib.util
import io
import json
import sys
import time
import urllib.request
import warnings
import zipfile
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
PROTO = ROOT / "protocols/FG_EXPAND_V1.json"
SPEC = json.loads(PROTO.read_text())
OUT = ROOT / "results" / SPEC["run_id"] / "plaintext"
TRAINER = ROOT / "research/selection_extension/reference_training/build_v17_plaintext_suite.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def data(name):
    spec = SPEC["data"][name]
    cached = ROOT / "data/raw" / (name + ".zip")
    if not cached.exists():
        cached.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(spec["url"], timeout=60) as response:
            payload = response.read()
        cached.write_bytes(payload)
    with zipfile.ZipFile(cached) as z:
        member = next(n for n in z.namelist() if n.split("/")[-1] == spec["member"])
        raw = np.loadtxt(z.read(member).decode("ascii").splitlines(), delimiter=",")
    assert raw.shape == (spec["expected_raw_rows"], spec["features"] + 1)
    assert np.isfinite(raw).all() and set(raw[:, -1]) == {0.0, 1.0}
    groups = {}
    for i, row in enumerate(raw):
        groups.setdefault(np.ascontiguousarray(row[:-1]).tobytes(), []).append(i)
    kept, conflict = [], []
    for group in groups.values():
        if len(set(raw[group, -1])) == 1:
            kept.append(group[0])
        else:
            conflict.extend(group)
    kept = np.array(sorted(kept))
    x, y = raw[kept, :-1], raw[kept, -1].astype(int)
    remaining, audit = train_test_split(np.arange(len(y)), test_size=SPEC["split"]["independent_rows"], stratify=y, random_state=1701)
    remaining, dev = train_test_split(remaining, test_size=SPEC["split"]["development_rows"], stratify=y[remaining], random_state=2701)
    train, selection = train_test_split(remaining, test_size=SPEC["split"]["selection_rows"], stratify=y[remaining], random_state=3701)
    roles = dict(model_training=np.sort(train), development=np.sort(dev), configuration_selection=np.sort(selection), independent_evaluation=np.sort(audit))
    assert len(set(np.concatenate(list(roles.values())))) == len(y)
    return x, y, kept, roles, dict(source_url=spec["url"], zip_sha256=sha(cached), member=member, raw_rows=len(raw), retained_rows=len(y), dropped_conflicting_rows=conflict, dropped_duplicate_rows=len(raw)-len(y)-len(conflict), features=x.shape[1], class_counts=np.bincount(y).tolist(), exposure=spec["exposure"])


def main():
    if OUT.exists():
        raise SystemExit(f"Refuse existing plaintext root: {OUT}")
    module_spec = importlib.util.spec_from_file_location("fg_reference_training", TRAINER)
    ref = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = ref
    module_spec.loader.exec_module(ref)
    datasets = {name: data(name) for name in SPEC["data"]}
    manifest = dict(protocol_id=SPEC["protocol_id"], protocol_sha256=sha(PROTO), trainer_sha256=sha(TRAINER), created_unix=time.time(), cases=[])
    for name, model_id in SPEC["cases_in_execution_order"]:
        x, y, ids, roles, source = datasets[name]
        train = roles["model_training"]
        mean, std = x[train].mean(0), x[train].std(0)
        std = np.where(std == 0, 1.0, std)
        normalized = (x[train] - mean) / std
        start = time.perf_counter()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            selector = LogisticRegression(solver="liblinear", max_iter=2000, random_state=0).fit(normalized, y[train])
            selected = np.sort(np.argsort(abs(selector.coef_[0]))[::-1][:min(16, x.shape[1])])
            trained, logits = ref.fit_model(model_id, normalized[:, selected], y[train], 0)
        assert np.isfinite(logits).all()
        scale = 1.0 / np.max(abs(logits)) if np.max(abs(logits)) else 1.0
        case = f"{name}__{model_id}__split0_seed0"
        path = OUT / case
        model = dict(schema_version=ref.SCHEMA, dataset_id=name, dataset_name=name, model_id=model_id, model_type=model_id, task="binary classification", input_dim=len(selected), train_samples=len(train), test_samples=len(roles["independent_evaluation"]), outer_fold=0, training_seed=0, selected_feature_indices=selected.tolist(), selected_feature_names=[f"x_{i}" for i in selected], standardization=dict(mean=mean[selected].tolist(), std=std[selected].tolist()), scaled_model_for_ckks=ref.scaled_parameters(model_id, trained, scale), polynomial_score=dict(formula=ref.head_formula(model_id), decision_threshold=0.5), training_only_logit_scale=float(scale))
        write(path / "model.json", model)
        dataset = ref.Dataset(name, name, x, y, ids, [f"x_{i}" for i in range(x.shape[1])], source["source_url"], source["zip_sha256"])
        role_meta = {}
        for role, idx in roles.items():
            ref.write_role_csv(path / f"{role}.csv", dataset, idx)
            role_meta[role] = dict(rows=len(idx), row_ids=ids[idx].tolist(), class_counts=np.bincount(y[idx], minlength=2).tolist(), sha256=sha(path / f"{role}.csv"))
        quality = {}
        for role in ("model_training", "development", "configuration_selection"):
            idx = roles[role]
            transformed = ((x[idx]-mean)/std)[:, selected]
            z = (transformed @ trained["weights"] + trained["bias"] if model_id.startswith("linear_") else ref.network_logits(transformed, trained)) * scale
            score = ref.scores(model_id, z)
            assert np.isfinite(score).all()
            if role != "configuration_selection":
                quality[role] = dict(accuracy=accuracy_score(y[idx], score>=.5), balanced_accuracy=balanced_accuracy_score(y[idx], score>=.5), macro_f1=f1_score(y[idx], score>=.5, average="macro"), auroc=roc_auc_score(y[idx], score), score_margin_quantiles={str(q): float(np.quantile(abs(score-.5), q)) for q in [0,.1,.5,.9,1]}, score_vs_unscaled_logit_decision_differences=int(np.sum((score>=.5)!=(z>=0))))
            else:
                write(path / "selection_plaintext_reference.json", dict(row_ids=ids[idx].tolist(), scores=score.tolist(), logits=z.tolist()))
        item = dict(case_id=case, dataset=name, model_id=model_id, model_path=str((path/"model.json").relative_to(ROOT)), model_sha256=sha(path/"model.json"), roles=role_meta, source=source, quality=quality, training_wall_seconds=time.perf_counter()-start, warnings=[str(w.message) for w in caught], training_completion="FIXED_1200_EPOCHS_NOT_CONVERGENCE_CERTIFICATE" if model_id.startswith("mlp_") else "LIBLINEAR_RETURNED_WITH_WARNINGS_RECORDED", selector_iterations=selector.n_iter_.tolist(), protocol_sha256=sha(PROTO))
        write(path / "manifest.json", item)
        manifest["cases"].append(item)
        print(json.dumps({"case":case, "development":quality["development"], "warnings":item["warnings"]}), flush=True)
    write(OUT / "manifest.json", manifest)


if __name__ == "__main__":
    main()
