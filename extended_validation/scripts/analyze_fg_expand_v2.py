#!/usr/bin/env python3
"""Independent multiclass recomputation, provenance checks, and descriptive costs."""
import argparse, collections, csv, functools, gzip, hashlib, json, math, re, sys
from pathlib import Path
import numpy as np
from run_fg_expand_v2 import ROOT,RUN,read,sha
OUT=ROOT/'docs/research/fg_expand_v2_20260905'

def same_derived(x,y):
    if isinstance(x,dict) and isinstance(y,dict):return x.keys()==y.keys() and all(same_derived(x[k],y[k]) for k in x)
    if isinstance(x,list) and isinstance(y,list):return len(x)==len(y) and all(same_derived(a,b) for a,b in zip(x,y))
    if isinstance(x,float) and isinstance(y,float):return math.isclose(x,y,rel_tol=1e-10,abs_tol=1e-12)
    return type(x)==type(y) and x==y
def dump(name,value):
    with (OUT/name).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def csvout(name,rows):
    with (OUT/name).open('x',newline='') as f:
        fields=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def go_json_digest(path):
    # Preserve Go's numeric/string serialization; remove only outside-string whitespace.
    payload=re.sub(r'"(?:\\.|[^"\\])*"|\s+',lambda m:m[0] if m[0].startswith('"') else '',path.read_text())
    return 'sha256:'+hashlib.sha256(payload.encode()).hexdigest()
def metrics(records):
    p=np.array([r['plaintext_logits'] for r in records]);z=np.array([r['ckks_logits'] for r in records]);labels=np.array([r['label'] for r in records]);assert p.shape==z.shape and p.shape[1]==10 and np.isfinite(p).all() and np.isfinite(z).all()
    top=p.argmax(1);other=z.argmax(1);rank=np.sort(p,axis=1);gap=rank[:,-1]-rank[:,-2];app=gap>.001;e=abs(z-p);flip=top!=other;idx=np.arange(len(p));dg=p[idx,top,None]-p
    numer=e[idx,top,None]+e;dg[idx,top]=np.inf
    with np.errstate(divide='ignore',invalid='ignore'):cap=(numer/dg).max(1)
    cap[gap==0]=0  # Original tied plaintext certificate marks cap inapplicable.
    viol=app & (cap>=.5)
    return dict(app=app,flip=flip,viol=viol,gap=gap,cap=cap,error=e,plain=p,ckks=z,plain_correct=top==labels,ckks_correct=other==labels,labels=labels,plain_top=top,ckks_top=other)
@functools.lru_cache(maxsize=64)
def plaintext_reference(seed,filename):
    model=read(RUN/f'plaintext/seed_{seed}/model.json');w=np.asarray(model['parameters']);assert w.shape==(79510,)
    rows=list(csv.DictReader((RUN/'inputs'/filename).open()))
    x=np.asarray([[int(r[f'pixel_{i:03d}']) for i in range(784)] for r in rows],dtype=float)/255.
    z=(x@w[:78400].reshape(100,784).T+w[78400:78500])**2@w[78500:79500].reshape(10,100).T+w[79500:]
    assert z.shape==(500,10) and np.isfinite(z).all()
    return [r['sample_id'] for r in rows],np.array([int(r['label']) for r in rows]),z
def trial_summary(keyfiles,expected_n=500,reference=None,candidate_id=None,contract_digest=None):
    keyfiles=[p.resolve() for p in keyfiles]
    raw=[read(p) for p in keyfiles];assert len(raw)==3
    arrays=[];sids=None;rows=[];timings=[]
    for k,ev in enumerate(raw,1):
        assert ev['key_run']==k and len(ev['records'])==expected_n
        assert ev['candidate_id']==raw[0]['candidate_id'] and ev['contract_digest']==raw[0]['contract_digest']
        if candidate_id is not None:assert ev['candidate_id']==candidate_id
        if contract_digest is not None:assert ev['contract_digest']==contract_digest
        ids=[r['sample_id'] for r in ev['records']]
        if sids is None:sids=ids
        assert ids==sids and len(set(ids))==expected_n
        a=metrics(ev['records']);arrays.append(a);timings.append(ev['summary'])
        if reference is not None:
            ref_ids,ref_labels,ref_logits=reference
            assert ids==ref_ids and np.array_equal(a['labels'],ref_labels)
            assert np.max(abs(a['plain']-ref_logits))<1e-10,'independent plaintext graph mismatch'
        assert np.array_equal([r['plaintext_top_1'] for r in ev['records']],a['plain_top'])
        assert np.array_equal([r['ckks_top_1'] for r in ev['records']],a['ckks_top'])
        assert np.array_equal([r['argmax_flip'] for r in ev['records']],a['flip'])
        batch_rmse=float(np.sqrt(np.mean(a['error']**2)));batch_max=float(a['error'].max())
        for i,sid in enumerate(ids):rows.append(dict(sample_id=sid,key_ordinal=k,applicable=bool(a['app'][i]),flip=bool(a['flip'][i]),error_violation=bool(a['viol'][i]),gap=float(a['gap'][i]),max_abs_error=float(a['error'][i].max()),cap=float(a['cap'][i]),plain_top=int(a['plain_top'][i]),ckks_top=int(a['ckks_top'][i]),label=int(a['labels'][i]),plain_logits=a['plain'][i].tolist(),ckks_logits=a['ckks'][i].tolist(),batch_key_rmse=batch_rmse,batch_key_max_abs=batch_max,source=str(keyfiles[k-1].relative_to(ROOT))))
    for a in arrays[1:]:assert np.array_equal(a['plain'],arrays[0]['plain'])
    app=arrays[0]['app'];flip=np.stack([a['flip'] for a in arrays]);viol=np.stack([a['viol'] for a in arrays]);err=np.concatenate([a['error'] for a in arrays])
    summary=dict(inputs=expected_n,applicable=int(app.sum()),boundary=int((~app).sum()),key_observations=3*expected_n,applicable_key_observations=int(3*app.sum()),applicable_flip_events=int(flip[:,app].sum()),applicable_flip_inputs=int(flip[:,app].any(0).sum()),applicable_error_events=int(viol.sum()),applicable_error_inputs=int(viol.any(0).sum()),boundary_flip_events=int(flip[:,~app].sum()),boundary_flip_inputs=int(flip[:,~app].any(0).sum()),all_flip_events=int(flip.sum()),all_flip_inputs=int(flip.any(0).sum()),max_abs_all=float(err.max()),max_abs_applicable=float(np.concatenate([a['error'][app] for a in arrays]).max()) if app.any() else None,rmse_all=float(np.sqrt(np.mean(err**2))),squared_error_sum=float(np.sum(err**2)),logit_observations=int(err.size),plain_correct=int(arrays[0]['plain_correct'].sum()),ckks_correct_events=int(sum(a['ckks_correct'].sum() for a in arrays)),key_contexts=3,execution_failures=0,status='SAFE' if app.any() and not flip[:,app].any() and not viol.any() else 'REJECTED')
    return summary,rows,timings
def verify_sources():
    expected=dict(read(RUN/'MAIN_SOURCE_LOCK.json')['files'])
    for p in sorted(RUN.glob('MAIN_SOURCE_AMENDMENT_*.json')):
        a=read(p);assert expected[a['path']]==a['old_sha256'];expected[a['path']]=a['new_sha256']
    for p,h in expected.items():
        path=ROOT/p
        if not path.exists() and p.startswith('research/fashion_extension/bin/'):
            print('LOCAL_BINARY_NOT_PRESENT: '+p+'; source/raw checks continue, binary not reverified',file=sys.stderr)
            continue
        assert sha(path)==h,p
    # Full old archive is deliberately not read. New source core policies must match copies.
    unchanged=['internal/journalmnist/mlp.go','internal/journalmnist/optimizer.go','internal/certify/multiclass_decision_contract.go','internal/ckksplanner/synthesis.go','internal/ckksplanner/direct_policy.go','internal/ckksplanner/security_policy.go','internal/ckksplanner/v17_candidate_space.go','internal/ckksplanner/multiclass_executor.go','internal/ckksbackend/journal_mnist_multiclass.go','internal/ckksbackend/v17_primary_paired_latency.go']
    for n in unchanged:assert sha(ROOT/'research/fashion_extension'/n)==sha(ROOT/'research/selection_extension'/n),n
    assert sha(ROOT/'baseline/journal_final_20260905.pdf')=='0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85'
    return dict(bound_files=len(expected),unchanged_critical_functions=unchanged)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
    bindings=verify_sources();complete=(RUN/'MAIN_COMPLETED.json').exists()
    tables=[];candidate_table=[];acceptance_table=[];batch_table=[];timing_table=[];setup_table=[];examples=[];cases=[];key_payload_count=0
    for seed in [0,1,2]:
        cr=RUN/f'cases/seed_{seed}';frozen=read(cr/'FROZEN_SELECTION_ROLES.json');roles=frozen['roles'];plan=read(cr/'planning/plan.json');direct=read(cr/'direct/result.json');quality=read(RUN/f'plaintext/seed_{seed}/DEVELOPMENT_QUALITY.json')
        assert quality['model_sha256']==sha(RUN/f'plaintext/seed_{seed}/model.json')
        dev_path=RUN/f'plaintext/seed_{seed}/development_logits.json';assert quality['development_logits_sha256']==sha(dev_path)
        dev=np.array([r['logits'] for r in read(dev_path)]);assert dev.shape==(5000,10) and np.isfinite(dev).all()
        reference_error=dev-dev.astype(np.float16).astype(np.float64)
        assert math.isclose(quality['numerical_thresholds']['rmse'],float(np.sqrt(np.mean(reference_error**2))),rel_tol=1e-12)
        assert quality['numerical_thresholds']['max_abs']==float(abs(reference_error).max())
        assert plan['direct_policy_digest']=='sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603';assert plan['security_policy_digest']=='sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055'
        assert direct['trials_used']==len(direct['trials'])<=4
        safe=[t for t in direct['trials'] if t['status']=='SAFE'];assert (direct.get('selected') or {}).get('id')==(safe[0]['candidate']['id'] if safe else None)
        audit_summaries={};audit_rows={};sel_summaries={};direct_summaries={};finite_recomputed=[]
        for p in sorted((cr/'finite').glob('candidate_*')):
            t=read(p/'result.json');s,rows,times=trial_summary(sorted(p.glob('key_*.json')),reference=plaintext_reference(seed,'selection.csv'),candidate_id=t['candidate']['id'],contract_digest=plan['contract_digest']);key_payload_count+=3;assert s['status']==t['status'];assert s['applicable_flip_events']==t['aggregation']['argmax_flips'];assert s['applicable_error_events']==t['aggregation']['reserve_policy_violations']
            sec=t['candidate']['security'];assert sec['ciphertext_q_admission']==sec['evaluation_key_qp_admission']=='PASS' and sec['target_bits']==128
            errors=np.array([r['max_abs_error'] for r in rows]);perkey=[metrics(read(q)['records']) for q in sorted(p.glob('key_*.json'))]
            m={'rmse':max(float(np.sqrt(np.mean(a['error']**2))) for a in perkey),'max_abs':s['max_abs_all']};c=t['candidate'];sel_summaries[c['id']]=s
            assert math.isclose(t['mean_total_ms'],sum(tm['total_ms'] for tm in times)/3,rel_tol=1e-12)
            finite_recomputed.append(dict(candidate=c,mean_total_ms=t['mean_total_ms'],proposal_pass=s['status']=='SAFE',rmse_pass=m['rmse']<=quality['numerical_thresholds']['rmse'],max_abs_pass=m['max_abs']<=quality['numerical_thresholds']['max_abs'],max_error=s['max_abs_all']))
            candidate_table.append(dict(seed=seed,candidate_id=c['id'],parameters=c['parameters'],own_rmse_pass=m['rmse']<=quality['numerical_thresholds']['rmse'],own_max_abs_pass=m['max_abs']<=quality['numerical_thresholds']['max_abs'],max_key_rmse=m['rmse'],mean_selection_batch_ms=t['mean_total_ms'],**s))
        acceptance=[]
        for metric in ['rmse','max_abs']:
            counts=collections.Counter((e[metric+'_pass'],e['proposal_pass']) for e in finite_recomputed)
            row=dict(seed=seed,numerical_criterion=metric,candidates=len(finite_recomputed),both_pass=counts[True,True],numerical_only=counts[True,False],proposal_only=counts[False,True],both_fail=counts[False,False],same_observed_acceptance_set=counts[True,False]==counts[False,True]==0)
            acceptance.append(row);acceptance_table.append(row)
        for role,predicate in [('finite_fastest_acceptable',lambda e:e['proposal_pass']),('finite_fastest_executable',lambda e:True),('numeric_rmse',lambda e:e['rmse_pass']),('numeric_max_abs',lambda e:e['max_abs_pass'])]:
            eligible=[e for e in finite_recomputed if predicate(e)];expected=min(eligible,key=lambda e:e['mean_total_ms'])['candidate'] if eligible else None
            assert roles[role]==expected,'finite role argmin mismatch: '+role
        assert frozen['minimum_max_error_diagnostic']==min(finite_recomputed,key=lambda e:e['max_error'])['candidate']
        assert roles['initial']==plan['initial_candidates'][0]
        for p in sorted((cr/'direct').glob('trial_*')):
            t=read(p/'trial.json');s,_,_=trial_summary(sorted(p.glob('key_*.json')),reference=plaintext_reference(seed,'selection.csv'),candidate_id=t['candidate']['id'],contract_digest=plan['contract_digest']);key_payload_count+=3;assert t['status']==s['status']
            direct_summaries[t['candidate']['id']]=s
        unique={c['id']:c for c in roles.values() if c}
        for cid,c in unique.items():
            bs=[];allrows=[];alltimes=[];seen=set()
            missing_batches=[]
            for batch in range(20):
                p=cr/f'audit/{cid}/batch_{batch:02d}'
                if not (p/'result.json').exists():missing_batches.append(batch);continue
                contract=read(p/'audit_contract.json')
                for name in ['model_artifact','source_data','calibration','deployment']:assert contract[name]==plan['contract'][name],name
                for name in ['class_count','tie_break','bound_mode','margin_floor','margin_utilization_cap']:assert contract['multiclass_decision'][name]==plan['contract']['multiclass_decision'][name],name
                assert contract['validation_data']['sha256']=='sha256:'+sha(RUN/f'inputs/audit_{batch:02d}.csv')
                t=read(p/'result.json');assert t['candidate']==c
                s,rows,times=trial_summary(sorted(p.glob('key_*.json')),reference=plaintext_reference(seed,f'audit_{batch:02d}.csv'),candidate_id=cid,contract_digest=go_json_digest(p/'audit_contract.json'));key_payload_count+=3
                assert s['status']==t['status'];assert s['applicable_flip_events']==t['aggregation']['argmax_flips'];assert s['applicable_error_events']==t['aggregation']['reserve_policy_violations']
                ids={r['sample_id'] for r in rows};assert not ids&seen;seen|=ids
                for tm in times:
                    assert tm['input_ciphertexts']==784 and tm['output_ciphertexts']==10 and tm['required_slots']==500
                    assert tm['available_slots']==2**(c['parameters']['log_n']-1)
                for row in rows:row['batch']=batch;row['candidate_id']=cid
                allrows.extend(rows);bs.append(s);alltimes.extend(times);batch_table.append(dict(seed=seed,candidate_id=cid,batch=batch,parameters=c['parameters'],**s))
            if complete:assert len(seen)==10000
            if not bs:
                audit_summaries[cid]=dict(inputs=0,planned_inputs=10000,status='NOT_EVALUATED',missing_batches=missing_batches)
                audit_rows[cid]=[];continue
            summed=['inputs','applicable','boundary','key_observations','applicable_key_observations','applicable_flip_events','applicable_flip_inputs','applicable_error_events','applicable_error_inputs','boundary_flip_events','boundary_flip_inputs','all_flip_events','all_flip_inputs','plain_correct','ckks_correct_events','key_contexts','execution_failures','squared_error_sum','logit_observations']
            combined={k:sum(b[k] for b in bs) for k in summed};combined['max_abs_all']=max(b['max_abs_all'] for b in bs);combined['max_abs_applicable']=max(b['max_abs_applicable'] for b in bs if b['max_abs_applicable'] is not None);combined['rmse_all']=math.sqrt(combined['squared_error_sum']/combined['logit_observations']);combined['plaintext_accuracy']=combined['plain_correct']/combined['inputs'];combined['ckks_accuracy']=combined['ckks_correct_events']/combined['key_observations'];combined['status']='SAFE' if not combined['applicable_flip_events'] and not combined['applicable_error_events'] else 'REJECTED'
            combined['planned_inputs']=10000;combined['missing_batches']=missing_batches;combined['completion']='COMPLETE' if not missing_batches else 'PARTIAL_OBSERVATIONS_NOT_FULL_AUDIT'
            combined['audit_native_cost_ms']={k:sum(tm[k] for tm in alltimes) for k in ['crypto_setup_ms','encode_encrypt_ms','evaluation_only_ms','decrypt_decode_ms','adapter_io_ms','total_ms']}
            cm=np.zeros((10,10),int)
            for row in allrows:
                if row['key_ordinal']==1:cm[row['label'],row['plain_top']]+=1
            combined['plaintext_confusion_matrix']=cm.tolist();combined['plaintext_class_recall']=(cm.diagonal()/cm.sum(1)).tolist()
            audit_summaries[cid]=combined;audit_rows[cid]=allrows
        proposed_rows=audit_rows.get((roles['proposed'] or {}).get('id'),[]);proposed=collections.defaultdict(list)
        for r in proposed_rows:proposed[r['sample_id']].append(r)
        types=[]
        for role,c in roles.items():
            if not c:
                tables.append(dict(seed=seed,method=role,selection_status='NO_SELECTION'));continue
            a=audit_summaries[c['id']];original_pass=None if role=='initial' else True
            if role.startswith('numeric_'):original_pass=next(e for e in frozen['finite_entries'] if e['candidate']['id']==c['id'])[role.removeprefix('numeric_')+'_pass']
            numeric_audit_pass=None
            if role.startswith('numeric_') and audit_rows[c['id']]:
                metric=role.removeprefix('numeric_');tau=quality['numerical_thresholds'][metric]
                numeric_audit_pass=all(r['batch_key_'+metric]<=tau for r in audit_rows[c['id']])
            selected_evidence=(direct_summaries if role in ['initial','proposed'] else sel_summaries)[c['id']]
            own_condition={'initial':'none beyond synthesis/security/execution; both acceptance checks disabled','proposed':'inputwise decision agreement and all-competitor margin/error condition','finite_fastest_acceptable':'same proposal acceptance within full finite set','finite_fastest_executable':'execution/security only','numeric_rmse':'every selection key RMSE <= development FP16 threshold','numeric_max_abs':'every selection key maximum absolute error <= development FP16 threshold'}[role]
            tables.append(dict(seed=seed,method=role,model_sha256=quality['model_sha256'],candidate_id=c['id'],parameters=c['parameters'],selection_origin='original bounded direct' if role=='proposed' else 'internal finite/common synthesis comparison',own_condition=own_condition,selection_inputs=500,selection_applicable=selected_evidence['applicable'],selection_boundary=selected_evidence['boundary'],actual_candidates_evaluated=direct['trials_used'] if role=='proposed' else (1 if role=='initial' else len(frozen['finite_entries'])),own_selection_condition_pass=original_pass,numeric_audit_all_batch_key_condition_pass=numeric_audit_pass,proposal_selection_condition_pass=selected_evidence['status']=='SAFE',alias_roles=[n for n,v in roles.items() if v and v['id']==c['id']],**a))
            if role.startswith('numeric_'):
                counts=collections.Counter();examples_by_type=collections.defaultdict(list);grouped=collections.defaultdict(list)
                for r in audit_rows[c['id']]:grouped[r['sample_id']].append(r)
                metric=role.removeprefix('numeric_');tau=quality['numerical_thresholds'][metric]
                for sid,rr in grouped.items():
                    dd=proposed.get(sid)
                    if not dd:continue
                    assert len(rr)==len(dd)==3
                    cats=[]
                    if any(r['flip'] and r['batch_key_'+metric]<=tau for r in rr):
                        cats.append('numeric_batch_condition_pass_flip')
                        if not any(d['flip'] for d in dd):cats.append('numeric_batch_condition_pass_flip_proposed_preserved_all_keys')
                    if not any(r['flip'] for r in rr) and not any(d['flip'] for d in dd):cats.append('both_decisions_preserved_all_keys')
                    if any(d['flip'] or d['error_violation'] or not d['applicable'] for d in dd):cats.append('proposed_failure_or_outside_domain')
                    if any(d['flip'] and d['applicable'] for d in dd):cats.append('proposed_applicable_decision_flip')
                    if any(d['error_violation'] for d in dd) and not any(d['flip'] and d['applicable'] for d in dd):cats.append('proposed_error_violation_without_applicable_flip')
                    if any(not d['applicable'] for d in dd):cats.append('proposed_outside_domain')
                    for cat in cats:
                        counts[cat]+=1
                        if len(examples_by_type[cat])<10:examples_by_type[cat].append(dict(seed=seed,method=role,sample_id=sid,type=cat,numeric_threshold=tau,numeric=rr,proposed=dd,key_alignment='all three observations compared perinput; different candidate keys independently generated, not paired cryptographic keys'))
                for name in ['numeric_batch_condition_pass_flip','numeric_batch_condition_pass_flip_proposed_preserved_all_keys','both_decisions_preserved_all_keys','proposed_failure_or_outside_domain','proposed_applicable_decision_flip','proposed_error_violation_without_applicable_flip','proposed_outside_domain']:types.append(dict(method=role,type=name,case_input_pairs=counts[name],unit='unique input within this seed and method; categories can overlap on boundary inputs'))
                for ex in examples_by_type.values():examples.extend(ex)
        timings=[]
        for p in sorted((cr/'timing').glob('*/keyset_*/result.json')):
            j=read(p);assert j['protocol']['warmup_runs']==1 and j['protocol']['measurement_runs']==6;assert len(j['records'])==12
            assert j['selected_row_ids']==[i*499//19 for i in range(20)]
            assert [a['id'] for a in j['arms']]==['proposed','comparator']
            assert j['protocol']['keyset']==int(p.parent.name.split('_')[1])
            assert {(r['measurement_run'],r['arm_id']) for r in j['records']}=={(k,a) for k in range(1,7) for a in ['proposed','comparator']}
            assert all(r['keyset']==j['protocol']['keyset'] for r in j['records'])
            for r in j['records']:assert r['selected_inputs']==20
            by=collections.defaultdict(dict)
            for r in j['records']:by[r['measurement_run']][r['arm_id']]=r
            ratio=float(np.exp(np.mean([math.log(v['comparator']['total_ms']/v['proposed']['total_ms']) for v in by.values()])))
            pdf_time=lambda r:sum(r[k] for k in ['encode_encrypt_ms','evaluation_only_ms','decrypt_decode_ms'])
            pdf_ratio=float(np.exp(np.mean([math.log(pdf_time(v['comparator'])/pdf_time(v['proposed'])) for v in by.values()])))
            cid=j['arms'][1]['candidate_id'];timings.append(dict(candidate_id=cid,keyset=j['protocol']['keyset'],geometric_time_ratio=ratio,geometric_pdf_inference_ratio=pdf_ratio))
            for arm in j['arms']:setup_table.append(dict(seed=seed,comparison_candidate_id=cid,keyset=j['protocol']['keyset'],**arm))
            for r in j['records']:timing_table.append(dict(seed=seed,comparison_candidate_id=cid,pdf_defined_inference_ms=pdf_time(r),**r))
        ratios={cid:float(np.exp(np.mean([math.log(t['geometric_time_ratio']) for t in timings if t['candidate_id']==cid]))) for cid in {t['candidate_id'] for t in timings}}
        pdf_ratios={cid:float(np.exp(np.mean([math.log(t['geometric_pdf_inference_ratio']) for t in timings if t['candidate_id']==cid]))) for cid in {t['candidate_id'] for t in timings}}
        costs=read_command_costs(seed)
        expected_pairs={c['id'] for n,c in roles.items() if n!='proposed' and c}
        missing_timing=[dict(candidate_id=cid,keyset=k) for cid in sorted(expected_pairs) for k in [1,2,3] if not any(t['candidate_id']==cid and t['keyset']==k for t in timings)]
        if complete:assert not missing_timing
        common_ids=set.intersection(*[{r['sample_id'] for r in rows} for rows in audit_rows.values()]) if audit_rows else set()
        cases.append(dict(seed=seed,development=quality,selection_applicable=plan['contract']['multiclass_decision']['certifiable_samples'],selection_inputs=500,direct_trials=direct['trials_used'],finite_candidates=len(frozen['finite_entries']),acceptance_set_comparisons=acceptance,roles=roles,actual_unique_audit_candidates=len(unique),common_evaluated_audit_inputs=len(common_ids),audit=audit_summaries,timing_ratios_comparator_over_proposed=ratios,pdf_inference_ratios_comparator_over_proposed=pdf_ratios,missing_timing_blocks=missing_timing,selection_costs=costs,input_types=types,minimum_error_diagnostic=frozen['minimum_max_error_diagnostic']))
    summary=dict(protocol='FG_EXPAND_V2_MAIN_20260905',run_id=RUN.name,status='COMPLETED_EXPLORATORY' if complete else 'RESOURCE_OR_EXECUTION_INCOMPLETE',new_datasets=1,new_architectures=0,new_trained_models=3,dataset_architecture_groups=1,training_seed_cases=3,unique_selection_inputs=500,selection_case_inputs=1500,planned_unique_audit_inputs=10000,planned_audit_case_inputs=30000,common_evaluated_audit_case_inputs=sum(c['common_evaluated_audit_inputs'] for c in cases),independent_key_sample_guarantee=False,source_verification=bindings,main_key_evidence_payloads=key_payload_count,actual_audit_key_contexts=sum(a.get('key_contexts',0) for c in cases for a in c['audit'].values()),actual_audit_input_key_observations=sum(a.get('key_observations',0) for c in cases for a in c['audit'].values()),actual_distinct_audit_candidate_cases=sum(c['actual_unique_audit_candidates'] for c in cases),cases=cases,automatic_followup=False,network_cost=None,confidence_or_risk_bound=None)
    if args.check:
        assert same_derived(read(OUT/'summary.json'),summary)
        for p,h in read(RUN/'RAW_SHA256SUMS.json').items():assert sha(RUN/p)==h,p
        manifest=OUT/'DERIVED_SHA256SUMS'
        if manifest.exists():
            for line in manifest.read_text().splitlines():
                h,p=line.split('  ',1);assert sha(OUT/p)==h,p
        print('READ_ONLY_VERIFICATION_PASS');return
    dump('summary.json',summary);csvout('METHOD_CASE_RESULTS.csv',tables);csvout('FINITE_CANDIDATES.csv',candidate_table);csvout('ACCEPTANCE_SET_COMPARISON.csv',acceptance_table);csvout('AUDIT_BATCHES.csv',batch_table);csvout('TIMING_RECORDS.csv',timing_table);csvout('TIMING_SETUP.csv',setup_table);dump('INPUT_TYPE_EXAMPLES.json',examples)
    print(json.dumps({'seeds':len(cases),'audit_case_inputs':summary['common_evaluated_audit_case_inputs'],'key_evidence_files':key_payload_count,'status':summary['status']}))
def read_command_costs(seed):
    result=collections.defaultdict(float)
    for p in (RUN/'commands').glob(f'seed{seed}_*.json'):
        j=read(p);stage=p.name.split('_',1)[1].split('.')[0]
        category='finite' if stage.startswith('finite') else 'audit' if stage.startswith('audit') else 'timing' if stage.startswith('timing') else stage
        result[category+'_all_attempt_wall_seconds']+=j['wall_seconds']
        if j['exit_code']==0:result[category+'_completed_wall_seconds']+=j['wall_seconds']
        else:result['interrupted_or_failed_wall_seconds']+=j['wall_seconds']
    return dict(result)
if __name__=='__main__':main()
