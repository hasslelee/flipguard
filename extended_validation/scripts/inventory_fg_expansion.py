#!/usr/bin/env python3
"""Read only a bounded set of already identified legacy evidence files."""
import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = Path("/home/ckks2/flipguard")
RUN = OLD / "results/model_family_expansion_v17/runs/v17_final_vm1x6_20260811T050104Z"
OUT = ROOT / "docs/research/fg_expand_v1_20260905"
BINDINGS = {}


def read(path):
    raw = path.read_bytes()
    BINDINGS[str(path)] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def summary_trial(payload):
    payload = payload.get("result", payload)
    trial = payload.get("trial", payload.get("audit_trial", payload))
    agg = trial.get("aggregation", trial)
    return dict(status=trial.get("status", payload.get("outcome")), inputs=agg.get("v_cert", 0)+agg.get("v_amb", 0), eligible=agg.get("v_cert"), boundary=agg.get("v_amb"), key_repeats=trial.get("key_repeats_completed"), decision_flip_key_observations=agg.get("decision_flips",agg.get("argmax_flips")), error_violation_key_observations=agg.get("error_violations",agg.get("reserve_policy_violations")))


def entry(kind, case_id, selection_path, audit_path=None):
    selected = read(selection_path)
    selected = selected.get("result", selected)
    c = selected["plan"]["contract"]
    model_path = Path(c["model_artifact"]["path"])
    model = read(model_path) if model_path.exists() else {}
    decision = c.get("multiclass_decision") or c["decision"]
    deployment = c["deployment"]
    result = dict(group=kind,case_id=case_id,dataset_id=c["dataset_id"],model_id=c["model_id"],model_type=c["model_type"],split_id=c["split_id"],model_artifact=c["model_artifact"],raw_source_binding=c.get("source_data"),input_materialization=c.get("input_materialization"),training_seed=model.get("training_seed",model.get("seed","NOT_RECORDED_AT_TOP_LEVEL")),training_rows=model.get("train_samples",model.get("training_samples","NOT_RECORDED_AT_TOP_LEVEL")),input_dim=model.get("input_dim"),training_status="Fixed reference training recipe; no convergence guarantee inferred from completed inference",selection_inputs=decision["validation_samples"],selection_eligible=decision["certifiable_samples"],selection_boundary=decision["ambiguous_samples"],packing=deployment.get("packing_strategy"),required_slots=deployment.get("required_slots"),key_repeats=deployment["validation_key_repeats"],max_candidate_trials=deployment["max_encrypted_trials"],direct_policy_digest=selected["plan"].get("direct_policy_digest"),security_policy_digest=selected["plan"].get("security_policy_digest"),outcome=selected["outcome"],trials=selected["trials_used"],selected_candidate=selected.get("selected"),selection_source=str(selection_path),audit_source=str(audit_path) if audit_path else None,completed=True,independent_environment_replicates=1)
    if audit_path:
        result["audit"]=summary_trial(read(audit_path))
    return result


def main():
    coverage_path=ROOT/"docs/review/all_coverage_recomputed.csv"
    BINDINGS[str(coverage_path)]=hashlib.sha256(coverage_path.read_bytes()).hexdigest()
    coverage=list(csv.DictReader(coverage_path.open()))
    cases=[]
    for row in coverage:
        if row["stage"]!="selection":continue
        a=next(x for x in coverage if x["case_id"]==row["case_id"] and x["stage"]!="selection")
        item=entry("primary_68",row["case_id"],OLD/row["source"],OLD/a["source"])
        item["previous_independent_coverage_recomputation"]={k:int(a[k]) for k in ["inputs","eligible","boundary","protected_flip_events","protected_error_violations","boundary_flip_events","boundary_unique_flips"]}
        cases.append(item)
    status_path=RUN/"run_status.csv"
    BINDINGS[str(status_path)]=hashlib.sha256(status_path.read_bytes()).hexdigest()
    jobs=list(csv.DictReader(status_path.open()))
    for row in jobs:
        if row["phase"] not in ["ablation","training_seed","training_seed_multiclass","training_seed_packed"]:continue
        path=(OLD/row["output"]).parent
        audit=path/("independent_evaluation.json" if row["phase"]=="training_seed_multiclass" else "direct_independent_evaluation.json")
        item=entry(row["phase"],row["case_id"],path/"selection.json",audit)
        item["job_summary"]=read(OLD/row["output"])
        item["completed"]=row["state"]=="DONE"
        cases.append(item)
    depths=[]
    for row in jobs:
        if row["phase"]=="depth_ladder":
            v=read(OLD/row["output"])
            c=v["plan"]["contract"]
            depths.append(dict(case_id=row["case_id"],source=str(OLD/row["output"]),depth=v["depth"],outcome=v["outcome"],trials=v["trials_used"],selected=v.get("selected"),decision=c["decision"],deployment=c["deployment"],separate_input_audit="NOT_PRESENT_IN_THIS_DEPTH_RESULT",trained_model=False))
    assert len(cases)==131 and len(depths)==5
    result=dict(primary_cases=68,additional_model_cases=63,separate_depth_conditions=5,job_rows=len(jobs),job_phase_counts=dict(collections.Counter(x["phase"] for x in jobs)),case_groups=dict(collections.Counter(x["group"] for x in cases)),primary_dataset_model_case_counts=dict(collections.Counter(x["dataset_id"]+"/"+x["model_id"] for x in cases if x["group"]=="primary_68")),all_cases_completed=all(x["completed"] for x in cases),additional_audit_non_safe=[dict(group=x["group"],case_id=x["case_id"],audit=x["audit"]) for x in cases if x["group"]!="primary_68" and x["audit"]["status"]!="SAFE"],pdf_scope_wording_issue=dict(pdf_page=7,section="5.1",description="PDF prose mentions depth among 63 additional cases. Raw job classification gives 30 body/head +24 tabular seeds +6 multiclass seeds +3 packed seeds =63, with five depth conditions separate. No frozen count or manuscript edited."),cases=cases,depth_conditions=depths)
    (OUT/"LEGACY_INVENTORY.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    (OUT/"LEGACY_SOURCE_BINDINGS.json").write_text(json.dumps(BINDINGS,indent=2,sort_keys=True)+"\n")
    fields=["group","case_id","dataset_id","model_id","split_id","training_seed","training_rows","input_dim","selection_inputs","selection_eligible","selection_boundary","packing","required_slots","key_repeats","outcome","trials","audit_inputs","audit_eligible","audit_status","audit_flips","audit_violations","selection_source","audit_source"]
    with (OUT/"LEGACY_CASES.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");w.writeheader()
        for x in cases:
            a=x["audit"]
            w.writerow({**{k:x.get(k) for k in fields if not k.startswith("audit_")},"audit_inputs":a["inputs"],"audit_eligible":a["eligible"],"audit_status":a["status"],"audit_flips":a["decision_flip_key_observations"],"audit_violations":a["error_violation_key_observations"],"audit_source":x["audit_source"]})
    print(json.dumps({k:result[k] for k in ["primary_cases","additional_model_cases","separate_depth_conditions","job_phase_counts","additional_audit_non_safe"]}))


if __name__=="__main__":main()
