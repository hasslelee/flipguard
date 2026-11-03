#!/usr/bin/env python3
"""Run the four frozen cases serially; preserve all attempts and stage evidence."""
import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "protocols/FG_EXPAND_V1.json"
SPEC = json.loads(PROTOCOL.read_text())
OUT = ROOT / "results" / SPEC["run_id"]
SOURCE = ROOT / "research/selection_extension"
BIN = ROOT / "bin/fg-expand-case"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, obj):
    if p.exists():
        raise FileExistsError(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def environment():
    return dict(unix=time.time(), uname=platform.uname()._asdict(), loadavg=os.getloadavg(), cpu_count=os.cpu_count(), meminfo=Path("/proc/meminfo").read_text(), gomaxprocs="4", omp_num_threads="1", openblas_num_threads="1", process_snapshot=subprocess.check_output(["ps", "-eo", "pid,comm,pcpu,pmem,etimes", "--sort=-pcpu"], text=True).splitlines()[:16])


def verify_lock():
    lock = json.loads((OUT/"RUN_LOCK.json").read_text())
    expected_files = dict(lock["files_sha256"])
    for amendment in sorted(OUT.glob("SOURCE_AMENDMENT_*.json")):
        change = json.loads(amendment.read_text())
        assert change["path"] == "scripts/run_fg_expand_v1.py"
        assert change["old_sha256"] == expected_files[change["path"]]
        expected_files[change["path"]] = change["new_sha256"]
    for name, expected in expected_files.items():
        assert sha(ROOT/name) == expected, f"LOCK_MISMATCH {name}"
    return lock


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["lock", "preflight", "run"])
    args = parser.parse_args()
    manifest = json.loads((OUT/"plaintext/manifest.json").read_text())
    if args.phase == "lock":
        old = json.loads((SOURCE/"SOURCE_BINDING.json").read_text())
        for relative, expected in old["files_sha256"].items():
            assert sha(SOURCE/relative) == expected, relative
        files = [p for p in SOURCE.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        files += [p for p in (OUT/"plaintext").rglob("*") if p.is_file()]
        files += [PROTOCOL, BIN, ROOT/"scripts/build_fg_expand_v1.py", Path(__file__).resolve()]
        write(OUT/"RUN_LOCK.json", dict(protocol_id=SPEC["protocol_id"], run_id=SPEC["run_id"], files_sha256={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(files))}, start_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(), source_core_exact_copy=True, copied_files_checked=len(old["files_sha256"]), environment=environment(), source_compile_command="GOMAXPROCS=4 go build -o ../../bin/fg-expand-case ./cmd/fg-expand-case (cwd research/selection_extension)", toolchain={"go":subprocess.check_output(["go","version"],text=True).strip(),"python":platform.python_version()}))
        return
    verify_lock()
    if args.phase == "run":
        preflight = json.loads((OUT/"PREFLIGHT_VERIFICATION.json").read_text())
        assert preflight["plumbing_pass"] and len(preflight["cases"]) == len(manifest["cases"])
    stage_root = OUT / args.phase
    stage_root.mkdir(exist_ok=False)
    started = time.monotonic()
    events = stage_root / "events.jsonl"
    results = []
    for item in manifest["cases"]:
        if time.monotonic()-started >= SPEC["budget"]["wall_cap_seconds"]:
            results.append(dict(case_id=item["case_id"], status="NOT_RUN_WALL_BUDGET"))
            continue
        model = ROOT / item["model_path"]
        case_root = stage_root / item["case_id"]
        command = [str(BIN), "--mode", args.phase, "--model", str(model), "--selection", str(model.parent/"configuration_selection.csv"), "--out-root", str(case_root)]
        if args.phase == "preflight":
            smoke = stage_root / (item["case_id"]+"_development2.csv")
            lines = (model.parent/"development.csv").read_text().splitlines()
            smoke.write_text("\n".join(lines[:3])+"\n")
            command += ["--smoke", str(smoke)]
        else:
            command += ["--independent", str(model.parent/"independent_evaluation.csv")]
        env = dict(os.environ, GOMAXPROCS="4", PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
        before = environment()
        with events.open("a") as f:
            f.write(json.dumps(dict(event="START",case_id=item["case_id"],command=command,environment=before))+"\n")
        log = stage_root / (item["case_id"]+".log")
        rss = stage_root / (item["case_id"]+".resource.json")
        with log.open("x") as f:
            proc = subprocess.run(["/usr/bin/time", "-f", '{"elapsed_seconds":%e,"maximum_rss_kib":%M,"exit_code":%x}', "-o", str(rss)] + command, cwd=SOURCE,env=env,stdout=f,stderr=subprocess.STDOUT)
        after = environment()
        result = dict(case_id=item["case_id"],exit_code=proc.returncode,environment_after=after,log=str(log.relative_to(ROOT)),status="COMPLETED" if proc.returncode==0 else "EXECUTION_FAILURE_PRESERVED")
        results.append(result)
        with events.open("a") as f:
            f.write(json.dumps(dict(event="END",**result))+"\n")
        print(json.dumps({"phase":args.phase,"case":item["case_id"],"status":result["status"],"wall_seconds":after["unix"]-before["unix"]}),flush=True)
    write(stage_root/"STAGE_STATUS.json", results)
    if args.phase == "preflight":
        checked=[]
        for item, result in zip(manifest["cases"],results):
            p=stage_root/item["case_id"]
            empty_smoke = False
            if result["status"]!="COMPLETED":
                failure = json.loads((p/"EXECUTION_FAILURE.json").read_text())
                empty_smoke = (failure["error"] == "validation data has no certifiable sample above margin floor 0.001" and (p/"finite_static.json").exists() and (p/"smoke.prepared.csv").exists())
                if not empty_smoke:
                    raise RuntimeError("Plumbing infrastructure failure; inspect preserved logs before main run")
            reference=json.loads((ROOT/item["model_path"]).with_name("selection_plaintext_reference.json").read_text())
            rows=list(csv.DictReader((p/"configuration_selection.prepared.csv").open()))
            by_id={str(i):s for i,s in zip(reference["row_ids"],reference["scores"])}
            differences=[abs(float(row["polynomial_score"])-by_id[row["row_id"]]) for row in rows]
            assert len(rows)==32 and max(differences)<1e-12
            trial_path=p/"smoke_trial.json"
            trial=json.loads(trial_path.read_text()) if trial_path.exists() else {}
            checked.append(dict(case_id=item["case_id"],plaintext_max_absolute_difference=max(differences),smoke_status=trial.get("status","EMPTY_APPLICABLE_DEVELOPMENT_PAIR" if empty_smoke else "NO_INITIAL_CANDIDATE"),smoke_key_repeats=trial.get("key_repeats_completed",0),scientific_rejection_not_exclusion=True))
        write(OUT/"PREFLIGHT_VERIFICATION.json",dict(plumbing_pass=True,cases=checked,criteria_changed=False,independent_scores_accessed=False))


if __name__ == "__main__":
    main()
