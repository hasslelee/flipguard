#!/usr/bin/env python3
"""Recompute new selection/audit/timing evidence without performing encryption."""
import argparse
import collections
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/"results/fg_expand_v1_20260905_run01"
OUT=ROOT/"docs/research/fg_expand_v1_20260905"


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise AssertionError(message)
def close(x,y):return math.isclose(x,y,rel_tol=1e-10,abs_tol=1e-12)
def same_derived(x,y):
    """Raw bytes are hash-bound; allow roundoff only in recomputed floats."""
    if isinstance(x,dict) and isinstance(y,dict):return x.keys()==y.keys() and all(same_derived(x[k],y[k]) for k in x)
    if isinstance(x,list) and isinstance(y,list):return len(x)==len(y) and all(same_derived(a,b) for a,b in zip(x,y))
    if isinstance(x,float) and isinstance(y,float):return close(x,y)
    return type(x)==type(y) and x==y
def scores(model,rows):
    indices=model["selected_feature_indices"]
    x=np.array([[float(r[f"x_{i}"]) for i in indices] for r in rows])
    x=(x-np.array(model["standardization"]["mean"]))/np.array(model["standardization"]["std"])
    p=model["scaled_model_for_ckks"]
    if model["model_type"]=="linear_poly3":
        z=x@np.array(p["weights"])+p["bias"]
        return .5+.197*z-.004*z**3
    require(model["model_type"]=="mlp_square_linear_score","unexpected model")
    h=np.square(x@np.array(p["hidden_weights"]).T+np.array(p["hidden_bias"]))
    z=h@np.array(p["output_weights"])+p["output_bias"]
    return .5+.197*z


def verify_trial(t,reference):
    c=t["candidate"];sec=c["security"]
    require(sec["target_bits"]==128 and sec["ciphertext_q_admission"]=="PASS" and sec["evaluation_key_qp_admission"]=="PASS","candidate security")
    ledger=t.get("sample_ledger",[])
    flips=viol=boundary_flips=0
    eligible=set();boundary=set();bad=set();flip_inputs=set();error_inputs=set();b_bad=set();ids=set();key_ids=set();seen=set();per_key=collections.defaultdict(set)
    for r in ledger:
        sid=r["sample_id"];k=r["key_repeat"]
        require((sid,k) not in seen,"duplicate row/key observation");seen.add((sid,k))
        ids.add(sid);key_ids.add(k)
        p=r["plaintext_score"];y=r["ckks_score"]
        require(sid in reference and close(reference[sid],p),"plaintext model mismatch")
        margin=abs(p-.5);e=abs(y-p);covered=margin>.001
        flip=(p>=.5)!=(y>=.5);violation=e>=.5*margin
        require(r["certifiable"]==covered and r["decision_flip"]==(covered and flip) and r["error_violation"]==(covered and violation),"ledger flags disagree with scores")
        require(close(r["threshold"],.5) and close(r["decision_margin"],margin) and close(r["error_budget"],.5*margin) and close(r["absolute_error"],e),"ledger quantities")
        per_key[sid].add(y>=.5)
        if covered:
            eligible.add(sid);flips+=flip;viol+=violation
            if flip:flip_inputs.add(sid)
            if violation:error_inputs.add(sid)
            if flip or violation:bad.add(sid)
        else:
            boundary.add(sid);boundary_flips+=flip
            if flip:b_bad.add(sid)
    complete=t["key_repeats_completed"]==3 and t["success_runs"]==3
    if complete:
        require(ids==set(reference) and key_ids=={1,2,3} and len(ledger)==3*len(reference),"trial observation denominator")
        require(len(eligible)==t["v_cert"] and len(boundary)==t["v_amb"],"coverage denominator")
        require(t["decision_flips"]==flips and t["error_violations"]==viol,"trial failure counts")
        require(close(t["max_observed_error"],max(abs(r["ckks_score"]-r["plaintext_score"]) for r in ledger)),"maximum observed score error")
        require(t["status"]==("SAFE" if eligible and flips==0 and viol==0 else "REJECTED"),"trial status")
    require(t.get("encrypted_sample_evaluations",0)==len(ledger),"ledger size")
    return dict(status=t["status"],inputs=len(ids),eligible=len(eligible),boundary=len(boundary),coverage=len(eligible)/len(ids) if ids else None,key_repeats=t["key_repeats_completed"],key_observations=len(ledger),protected_flip_events=flips,protected_error_violations=viol,protected_unique_flipped_inputs=len(flip_inputs),protected_unique_error_inputs=len(error_inputs),protected_unique_bad_inputs=len(bad),boundary_flip_events=boundary_flips,boundary_unique_flips=len(b_bad),key_disagreement_inputs=sum(len(v)>1 for v in per_key.values()),execution_complete=complete,candidate_id=c["id"],parameters=c["parameters"],mean_inference_ms=t["mean_total_ms"],max_observed_error=t["max_observed_error"])


def analyze():
    lock=read(RUN/"RUN_LOCK.json")
    expected=dict(lock["files_sha256"])
    for amendment in sorted(RUN.glob("SOURCE_AMENDMENT_*.json")):
        a=read(amendment);require(a["path"]=="scripts/run_fg_expand_v1.py" and a["old_sha256"]==expected[a["path"]],"source amendment chain");expected[a["path"]]=a["new_sha256"]
    skipped=[]
    for name,digest in expected.items():
        p=ROOT/name
        if name.startswith("bin/") and not p.exists():skipped.append(name);continue
        require(p.is_file() and sha(p)==digest,f"locked payload changed: {name}")
    raw_manifest=RUN/"RAW_SHA256SUMS.json"
    if raw_manifest.exists():
        for name,digest in read(raw_manifest).items():require(sha(RUN/name)==digest,f"raw payload changed: {name}")
    manifest=read(RUN/"plaintext/manifest.json")
    cases=[];trials_table=[];latency_table=[];ratios_by_group=collections.defaultdict(list);total_ledger=total_timing=total_key_contexts=warmup_calls=0
    unique_roles=collections.defaultdict(set)
    for item in manifest["cases"]:
        case_id=item["case_id"];p=RUN/"run"/case_id;plain=RUN/"plaintext"/case_id
        if not (p/"COMPLETED.json").exists():
            cases.append(dict(case_id=case_id,status="EXECUTION_INCOMPLETE",failure=read(p/"EXECUTION_FAILURE.json") if (p/"EXECUTION_FAILURE.json").exists() else None));continue
        model=read(plain/"model.json");reference={};labels={}
        role_sets=[]
        for role in ["model_training","development","configuration_selection","independent_evaluation"]:
            rows=list(csv.DictReader((plain/(role+".csv")).open()));ids={r["row_id"] for r in rows};role_sets.append(ids)
            require(len(rows)==len(ids)==item["roles"][role]["rows"],"role count")
            unique_roles[role].update((item["dataset"],i) for i in ids)
            if role in ["configuration_selection","independent_evaluation"]:
                values=scores(model,rows);reference[role]={r["row_id"]:float(v) for r,v in zip(rows,values)};labels[role]={r["row_id"]:int(r["label"]) for r in rows}
        require(sum(map(len,role_sets))==len(set.union(*role_sets)),"train/dev/selection/audit overlap")
        selref=reference["configuration_selection"];audref=reference["independent_evaluation"]
        direct=read(p/"selection.json");finite=read(p/"exhaustive.json")
        require(direct["plan"]["direct_policy_digest"]=="sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603","direct policy changed")
        require(direct["plan"]["security_policy_digest"]=="sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055","security policy changed")
        require(direct["trials_used"]==len(direct["trials"])<=4 and finite["formal_denominator"]==len(finite["entries"])<=8,"candidate budgets")
        selections=[];finites=[]
        for phase,entries,dest in [("direct",direct["trials"],selections),("finite",finite["entries"],finites)]:
            for t in entries:
                v=verify_trial(t,selref);dest.append(v);trials_table.append(dict(case_id=case_id,phase=phase,**v));total_ledger+=v["key_observations"];total_key_contexts+=v["key_repeats"]
        safe=[t for t in direct["trials"] if t["status"]=="SAFE"]
        require((direct.get("selected") or {}).get("id")== (safe[0]["candidate"]["id"] if safe else None),"first acceptable selection")
        require(not safe or direct["trials"][-1]["status"]=="SAFE","selection continued after acceptance")
        for field,eligible,key in [("fastest_safe",[t for t in finite["entries"] if t["status"]=="SAFE"],"mean_total_ms"),("fastest_executable",[t for t in finite["entries"] if t["success_runs"]==3 and t["key_repeats_completed"]==3],"mean_total_ms"),("minimum_error",[t for t in finite["entries"] if t["success_runs"]==3 and t["key_repeats_completed"]==3],"max_observed_error")]:
            best=min(eligible,key=lambda t:t[key])["candidate"]["id"] if eligible else None
            require((finite.get(field) or {}).get("id")==best,f"finite objective {field}")
        role_candidates=read(p/"FROZEN_SELECTION_ROLES.json");bindings=read(p/"audit_role_bindings.json");audits={}
        expected_roles={"direct":direct.get("selected"),"finite_fastest_safe":finite.get("fastest_safe"),"finite_fastest_executable":finite.get("fastest_executable"),"initial_criteria_off":direct["trials"][0]["candidate"] if selections and selections[0]["execution_complete"] else None}
        require({r["role"]:r["candidate"] for r in role_candidates}==expected_roles,"frozen roles differ from selection")
        for path in sorted((p/"audit_candidates").glob("*.json")):
            obj=read(path);v=verify_trial(obj["trial"],audref);v["wall_ms"]=obj["wall_ms"];audits[v["candidate_id"]]=v;trials_table.append(dict(case_id=case_id,phase="audit",**v));total_ledger+=v["key_observations"];total_key_contexts+=v["key_repeats"]
        audit_roles={}
        for r in role_candidates:
            if r["candidate"]:
                cid=r["candidate"]["id"];require(bindings[r["role"]]==cid and cid in audits,"audit role identity");audit_roles[r["role"]]=audits[cid]
        records=[];metadata=[]
        paths=sorted((p/"paired_latency").glob("keyset_*.json"))
        require(len(paths)==3,"fresh timing keyset count")
        for path in paths:
            obj=read(path);k=obj["keyset"];m=obj["measurement"];protocol=m["protocol"]
            require(path.name==f"keyset_{k}.json" and k in [1,2,3],"timing keyset identity")
            require(protocol["warmup_runs"]==1 and protocol["measurement_runs"]==6 and protocol["selected_rows"]==20,"timing schedule")
            require(protocol["order_schedule"]=="balanced_cyclic_and_reverse_row_rotated_v1" and protocol["outlier_policy"]=="none_all_raw_observations_preserved","timing order/outlier policy")
            require({a["id"] for a in m["arms"]}==set(audit_roles),"timing role set")
            ordered_rows=list(map(int,audref))
            require(protocol["selected_row_ids"]==[ordered_rows[i*(len(ordered_rows)-1)//19] for i in range(20)],"unchanged deterministic timing row selection")
            arm_order=[a["id"] for a in m["arms"]];n_arms=len(arm_order)
            orders=[[arm_order[(i+rotation)%n_arms] for i in range(n_arms)] for rotation in range(n_arms)]
            orders += [[arm_order[(n_arms-1-i+rotation)%n_arms] for i in range(n_arms)] for rotation in range(n_arms)]
            for arm in m["arms"]:
                require(arm["candidate_id"]==expected_roles[arm["id"]]["id"],"timing candidate identity")
                require(all(arm[key]==value for key,value in expected_roles[arm["id"]]["parameters"].items()),"timing parameters")
                metadata.append(dict(keyset=k,**arm))
            total_key_contexts+=len(m["arms"]);warmup_calls+=20*len(m["arms"])
            seen=set()
            for record_index,r in enumerate(m["records"],1):
                sid=str(r["row_id"]);identity=(r["arm_id"],r["measurement_run"],sid)
                require(identity not in seen,"duplicate timing observation");seen.add(identity)
                require(r["candidate_id"]==expected_roles[r["arm_id"]]["id"] and r["role"]==r["arm_id"],"timing record identity")
                order=(r["measurement_run"]+r["row_index"]-2)%len(orders)
                require(r["observation_index"]==record_index and r["order_index"]==order+1 and orders[order][r["order_position"]-1]==r["arm_id"],"actual timing execution order")
                require(protocol["selected_row_ids"][r["row_index"]-1]==r["row_id"],"timing row position")
                require(close(r["plain_y"],audref[sid]),"timing plaintext reference")
                require(close(r["y_error"],abs(r["ckks_y"]-r["plain_y"])) and r["decision_flip"]==((r["plain_y"]>=.5)!=(r["ckks_y"]>=.5)),"timing score diagnostics")
                residual=r["total_ms"]-r["encode_encrypt_ms"]-r["eval_only_ms"]-r["decrypt_decode_ms"]
                require(residual>=-1e-8,"negative inference timing residual")
                require(close(r["eval_only_ms"],r["model_eval_ms"]+r["polynomial_eval_ms"]),"HE timing partition")
                records.append(dict(keyset=k,**r))
            require(len(seen)==len(m["arms"])*20*6,"timing denominator")
            require(seen=={(a["id"],rep,str(row)) for a in m["arms"] for rep in range(1,7) for row in protocol["selected_row_ids"]},"timing pairing schedule")
        total_timing+=len(records)
        arm_names=[r["role"] for r in role_candidates if r["candidate"]]
        arm_time={};paired={};lookup={}
        for r in records:lookup[(r["keyset"],r["measurement_run"],r["row_id"],r["arm_id"])]=r
        for arm in arm_names:
            rr=[r for r in records if r["arm_id"]==arm]
            if not rr:continue
            covered=[r for r in rr if abs(r["plain_y"]-.5)>.001]
            v=dict(observations=len(rr),mean_total_ms=float(np.mean([r["total_ms"] for r in rr])),p95_total_ms=float(np.quantile([r["total_ms"] for r in rr],.95)),mean_encode_encrypt_ms=float(np.mean([r["encode_encrypt_ms"] for r in rr])),mean_eval_only_ms=float(np.mean([r["eval_only_ms"] for r in rr])),mean_decrypt_decode_ms=float(np.mean([r["decrypt_decode_ms"] for r in rr])),mean_setup_ms=float(np.mean([a["setup_ms"] for a in metadata if a["id"]==arm])),protected_flip_events=sum((r["plain_y"]>=.5)!=(r["ckks_y"]>=.5) for r in covered),protected_error_violations=sum(abs(r["ckks_y"]-r["plain_y"])>=.5*abs(r["plain_y"]-.5) for r in covered),boundary_flip_events=sum((r["plain_y"]>=.5)!=(r["ckks_y"]>=.5) for r in rr if abs(r["plain_y"]-.5)<=.001))
            v["mean_other_inference_ms"]=float(np.mean([r["total_ms"]-r["encode_encrypt_ms"]-r["eval_only_ms"]-r["decrypt_decode_ms"] for r in rr]))
            arm_time[arm]=v;latency_table.append(dict(case_id=case_id,arm=arm,**v))
            if arm!="direct" and "direct" in arm_names:
                ratios=[r["total_ms"]/lookup[(r["keyset"],r["measurement_run"],r["row_id"],"direct")]["total_ms"] for r in rr]
                value=float(np.exp(np.mean(np.log(ratios))));paired[arm+"_over_direct"]=value
                ratios_by_group[arm+"_over_direct"].append(dict(group=item["dataset"]+"/"+item["model_id"],value=value))
        timing=read(p/"stage_timing.json")
        direct_inference=sum(t["mean_total_ms"]*t.get("encrypted_sample_evaluations",0) for t in direct["trials"])
        finite_inference=sum(t["mean_total_ms"]*t.get("encrypted_sample_evaluations",0) for t in finite["entries"])
        roles_safe=all(audit_roles.get(a,{}).get("status")=="SAFE" for a in ["direct","finite_fastest_safe"])
        timing_safe=all(arm_time.get(a,{}).get("protected_flip_events",1)==0 and arm_time.get(a,{}).get("protected_error_violations",1)==0 for a in ["direct","finite_fastest_safe"])
        labels_a=labels["independent_evaluation"];quality=sum((score>=.5)==labels_a[i] for i,score in audref.items())/len(audref)
        cases.append(dict(case_id=case_id,status="COMPLETED",dataset=item["dataset"],model_id=item["model_id"],model_sha256=item["model_sha256"],direct_outcome=direct["outcome"],direct_trials=len(selections),finite_trials=len(finites),initial=selections[0] if selections else None,selected=next((t for t in selections if t["status"]=="SAFE"),None),finite=finites,finite_fastest_safe=finite.get("fastest_safe"),finite_fastest_executable=finite.get("fastest_executable"),minimum_error=finite.get("minimum_error"),audit_unique_executions=len(audits),audit_roles=audit_roles,independent_plaintext_accuracy=quality,selection_cost_ms=timing,direct_inference_sum_from_stored_means_ms=direct_inference,finite_inference_sum_from_stored_means_ms=finite_inference,direct_other_selection_wall_ms=timing["direct_selection_total_ms"]-direct_inference,finite_other_search_wall_ms=timing["finite_search_total_ms"]-finite_inference,timing=arm_time,paired_geometric_ratios=paired,safe_to_safe_pair_eligible=roles_safe and timing_safe))
    aggregates={}
    for metric,rows in ratios_by_group.items():
        groups=collections.defaultdict(list)
        for r in rows:groups[r["group"]].append(math.log(r["value"]))
        logs=np.array([np.mean(v) for v in groups.values()])
        rng=np.random.default_rng(20260824);boots=np.exp(rng.choice(logs,size=(10000,len(logs)),replace=True).mean(axis=1))
        aggregates[metric]=dict(geometric_mean=float(np.exp(logs.mean())),groups=len(logs),cases=len(rows),group_values={k:math.exp(float(np.mean(v))) for k,v in groups.items()},exploratory_cluster_bootstrap_95_interval=np.quantile(boots,[.025,.975]).tolist(),bootstrap_repeats=10000,seed=20260824,confirmatory=False,equivalence_claim=False)
        aggregates[metric]["interpretation"]="safe-to-safe observed comparison" if metric=="finite_fastest_safe_over_direct" and all(c.get("safe_to_safe_pair_eligible",False) for c in cases if c["status"]=="COMPLETED") else "all observed pairs retained; not an accuracy-qualified speed claim"
    summary=dict(protocol_id="FG_EXPAND_V1_20260905",run_id=RUN.name,completed_cases=sum(c["status"]=="COMPLETED" for c in cases),planned_cases=4,unique_inputs_by_role={k:len(v) for k,v in unique_roles.items()},selection_case_input_pairs=sum(i["roles"]["configuration_selection"]["rows"] for i in manifest["cases"]),independent_case_input_pairs=sum(i["roles"]["independent_evaluation"]["rows"] for i in manifest["cases"]),recorded_candidate_key_observations=total_ledger,recorded_timing_key_pass_observations=total_timing,unrecorded_timing_warmup_input_calls=warmup_calls,actual_main_key_contexts=total_key_contexts,raw_payload_hashes_checked=len(read(raw_manifest)) if raw_manifest.exists() else None,missing_local_binary_hash_only_skipped=skipped,cases=cases,latency_aggregates=aggregates,network_cost=None,confirmatory=False,old_primary_cases_unchanged=68,old_additional_cases_unchanged=63)
    return summary,trials_table,latency_table


def write_csv(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in r.items()})


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--check",action="store_true");args=parser.parse_args()
    summary,trials,latency=analyze()
    require(summary["completed_cases"]==summary["planned_cases"],"cannot publish a completed report while cases are pending")
    require((RUN/"RAW_SHA256SUMS.json").is_file(),"freeze raw payload manifest before publishing")
    if args.check:
        derived_manifest=OUT/'DERIVED_SHA256SUMS'
        if derived_manifest.exists():
            for line in derived_manifest.read_text().splitlines():
                digest,name=line.split('  ',1)
                require(sha(OUT/name)==digest,f'derived payload changed: {name}')
        old=read(OUT/"summary.json")
        for k in ["raw_payload_hashes_checked","missing_local_binary_hash_only_skipped"]:old.pop(k,None);summary.pop(k,None)
        require(same_derived(old,summary),"recomputed summary differs")
    else:
        (OUT/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
        write_csv(OUT/"candidate_and_audit_results.csv",trials);write_csv(OUT/"inference_costs.csv",latency)
    print(json.dumps({k:summary[k] for k in ["completed_cases","recorded_candidate_key_observations","recorded_timing_key_pass_observations","actual_main_key_contexts"]}))


if __name__=="__main__":main()
