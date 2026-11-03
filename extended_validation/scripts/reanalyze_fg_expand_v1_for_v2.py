#!/usr/bin/env python3
"""Read-only reanalysis; new files only in the V2 report directory."""
import csv, json
from pathlib import Path
import numpy as np
import analyze_fg_expand_v1 as old

OUT=old.ROOT/'docs/research/fg_expand_v2_20260905'
def rows(p):return list(csv.DictReader(p.open()))
def write(n,v):
    with (OUT/n).open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def csvout(n,rs):
    with (OUT/n).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def main():
    summary,_,_=old.analyze();manifest=old.read(old.RUN/'plaintext/manifest.json');cases=[];margins=[];candrows=[];violations=[];typology=[]
    for item in manifest['cases']:
        cid=item['case_id'];pr=old.RUN/'plaintext'/cid;rr=old.RUN/'run'/cid;m=old.read(pr/'model.json');values={};role_rows={}
        for role in ['model_training','development','configuration_selection','independent_evaluation']:
            rs=rows(pr/(role+'.csv'));z=old.scores(m,rs);g=abs(z-.5);values[role]=z;role_rows[role]=rs
            margins.append(dict(case_id=cid,role=role,n=len(z),applicable=int((g>.001).sum()),boundary=int((g<=.001).sum()),minimum=float(g.min()),q01=float(np.quantile(g,.01)),q10=float(np.quantile(g,.1)),median=float(np.median(g)),q90=float(np.quantile(g,.9)),maximum=float(g.max()),score_min=float(z.min()),score_max=float(z.max())))
        dev=values['development'];fp16=dev.astype(np.float16).astype(float);tau=dict(rmse=float(np.sqrt(np.mean((dev-fp16)**2))),max_abs=float(abs(dev-fp16).max()))
        finite=old.read(rr/'exhaustive.json');direct=old.read(rr/'selection.json');entries=[]
        for t in finite['entries']:
            led=t['sample_ledger'];numeric=[]
            for k in [1,2,3]:
                es=np.array([r['ckks_score']-r['plaintext_score'] for r in led if r['key_repeat']==k]);numeric.append(dict(rmse=float(np.sqrt(np.mean(es**2))),max_abs=float(abs(es).max())))
            entry=dict(case_id=cid,candidate_id=t['candidate']['id'],status=t['status'],log_n=t['candidate']['parameters']['log_n'],scale=t['candidate']['parameters']['log_default_scale'],q_count=len(t['candidate']['parameters']['log_q']),selection_inputs=len(values['configuration_selection']),applicable=t['v_cert'],max_all=max(r['absolute_error'] for r in led),max_applicable=max(r['absolute_error'] for r in led if r['certifiable']),max_key_rmse=max(v['rmse'] for v in numeric),rmse_threshold=tau['rmse'],max_abs_threshold=tau['max_abs'],numeric_rmse_pass=all(v['rmse']<=tau['rmse'] for v in numeric),numeric_max_abs_pass=all(v['max_abs']<=tau['max_abs'] for v in numeric),flips=t['decision_flips'],error_violations=t['error_violations'],selection_mean_total_ms=t['mean_total_ms'],source=str((rr/'exhaustive.json').relative_to(old.ROOT)))
            candrows.append(entry);entries.append(entry)
            if cid.startswith('spambase__linear') and entry['scale'] in [24,28] and entry['q_count']==7:
                for r in led:
                    if r['certifiable'] and r['error_violation']:
                        violations.append(dict(case_id=cid,candidate_id=entry['candidate_id'],sample_id=r['sample_id'],key=r['key_repeat'],plain=r['plaintext_score'],ckks=r['ckks_score'],margin=r['decision_margin'],error=r['absolute_error'],budget=r['error_budget'],flip=r['decision_flip']))
        minimum=min(entries,key=lambda e:e['max_all'])
        aliases=old.read(rr/'audit_role_bindings.json');audit={}
        for p in (rr/'audit_candidates').glob('*.json'):
            t=old.read(p)['trial'];audit[t['candidate']['id']]=t
        nums={}
        for metric,field in [('rmse','numeric_rmse_pass'),('max_abs','numeric_max_abs_pass')]:
            passed=[e for e in entries if e[field]];chosen=min(passed,key=lambda e:e['selection_mean_total_ms']) if passed else None
            nums[metric]=dict(candidate=chosen['candidate_id'] if chosen else None,original_numeric_condition_pass=bool(chosen),proposal_condition_pass=chosen['status']=='SAFE' if chosen else None,audit='reused_existing_same_candidate' if chosen and chosen['candidate_id'] in audit else 'NOT_EVALUATED_NO_NEW_CKKS_IN_REANALYSIS')
            if chosen:
                pinit=audit.get(chosen['candidate_id']);pdir=audit.get(aliases['direct'])
                if pinit and pdir:
                    by={(r['sample_id'],r['key_repeat']):r for r in pdir['sample_ledger']};counts={'numeric_pass_flip_proposed_preserved':0,'both_decisions_preserved':0,'proposed_failed_or_boundary':0}
                    for r in pinit['sample_ledger']:
                        d=by[(r['sample_id'],r['key_repeat'])];nf=(r['plaintext_score']>=.5)!=(r['ckks_score']>=.5);df=(d['plaintext_score']>=.5)!=(d['ckks_score']>=.5)
                        counts['numeric_pass_flip_proposed_preserved']+=int(nf and not df);counts['both_decisions_preserved']+=int(not nf and not df);counts['proposed_failed_or_boundary']+=int(df or not d['certifiable'])
                    typology.append(dict(case_id=cid,method=metric,counts=counts,unit='input-key observations; numerical acceptance was on selection, not per-audit-input guarantee'))
        cases.append(dict(case_id=cid,selection_applicable=direct['trials'][0]['v_cert'],selection_n=32,selected_features=m['selected_feature_indices'],feature_rule='abs(train-only standardized liblinear coefficient), descending top min(16,d), sorted indices; inherited bounded adapter experiment convention, not proof16 optimal or universal backend limit',training_only_logit_scale=m['training_only_logit_scale'],unscaled_training_maxabs=1/m['training_only_logit_scale'],model_sha256=old.sha(pr/'model.json'),minimum_max_error_candidate=minimum,numerical_comparators=nums,alias_bindings=aliases,actual_audit_candidates=len(audit),training_warnings=item['warnings'],training_completion=item['training_completion']))
    totals={}
    for name in ['initial_criteria_off','direct']:
        arr=[c['audit_roles'][name] for c in summary['cases']]
        totals[name]={k:sum(v[k] for v in arr) for k in ['eligible','key_observations','protected_flip_events','protected_error_violations','protected_unique_flipped_inputs','protected_unique_error_inputs','boundary_flip_events']}
    assert totals['initial_criteria_off']['eligible']==820
    assert totals['initial_criteria_off']['protected_flip_events']==201
    assert totals['initial_criteria_off']['protected_unique_flipped_inputs']==70
    assert totals['initial_criteria_off']['protected_error_violations']==675
    assert totals['initial_criteria_off']['protected_unique_error_inputs']==228
    assert totals['direct']['protected_flip_events']==0 and totals['direct']['boundary_flip_events']==1
    write('FIRST_EXPANSION_REANALYSIS.json',dict(parent_run=old.RUN.name,readonly=True,new_ckks_executions=0,totals=totals,applicable_case_inputs=820,applicable_key_observations=2460,initial_synthesis_still_uses_margin=True,numerical_comparison_scope='retrospective development-based precision diagnostic; thresholds fixed in V2_PREP, prior outcomes already known; not confirmatory',cases=cases,input_types=typology))
    csvout('FIRST_MARGIN_DISTRIBUTIONS.csv',margins);csvout('FIRST_NUMERICAL_CANDIDATES.csv',candrows);csvout('FIRST_SCALE_PAIR_VIOLATIONS.csv',violations)
    print(json.dumps(totals))
if __name__=='__main__':main()
