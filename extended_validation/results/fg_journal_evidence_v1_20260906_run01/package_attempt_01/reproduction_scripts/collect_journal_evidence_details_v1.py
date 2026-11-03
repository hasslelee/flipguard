#!/usr/bin/env python3
"""Bounded read-only details for the journal evidence supplement; no HE imports."""
import csv, hashlib, importlib.util, io, json, math, statistics
from collections import defaultdict
from pathlib import Path

ROOT=Path('/home/ckks2/deciprotect')
spec=importlib.util.spec_from_file_location('evidence',ROOT/'scripts/analyze_journal_evidence_v1.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
DOC=e.DOC;RUN=e.RUN;OLD=e.OLD;T=DOC/'evidence_tables';copies=[]
previous=json.loads((RUN/'READ_BINDINGS.json').read_text())

def read(p):
    p=Path(p)
    return e.rd(p,previous.get(str(p),{}).get('sha256'))
def js(p):return json.loads(read(p))
def rows(p):return list(csv.DictReader(io.StringIO(read(p).decode())))
def save(name,obj):e.dump(T/name,obj)
def copy(p,name,lines=None):
    p=Path(p);data=read(p)
    if lines:
        data=('\n'.join(f'{i+1}: {v}' for i,v in enumerate(data.decode().splitlines()) if any(a<=i+1<=b for a,b in lines))+'\n').encode()
    target=DOC/'source_excerpts'/name
    with target.open('xb') as f:f.write(data)
    copies.append({'file':str(target.relative_to(DOC)),'source':str(p),'source_sha256':e.bindings[str(p)]['sha256'],
                   'kind':'line-numbered excerpt' if lines else 'byte-identical copy','line_ranges':lines,'sha256':e.digest(data)})

snapshot=js(OLD/'docs/evidence/model_family_expansion_v17/source_snapshots/v17_final_vm1x6_20260811T050104Z/manifest.json')
snap={r['path']:r['sha256'] for r in snapshot['source_files']}
source_names={
 'internal/ckksplanner/synthesis.go':[(204,374),(375,566),(654,815),(946,1010)],
 'internal/ckksplanner/v17_candidate_space.go':[(1,175)],
 'internal/ckksplanner/tabular_contract.go':[(112,255),(319,394),(546,730),(1131,1310)],
 'internal/analysis/bounds.go':[(44,101),(127,280)],
 'internal/certify/multiclass_decision_contract.go':[(102,164),(185,355)],
 'internal/ckksplanner/security_policy.go':None,
 'internal/ckksbackend/context.go':None,
 'cmd/flipguard-v17-tabular-case/main.go':[(90,250)],
 'scripts/build_v17_plaintext_suite.py':None,
}
closure=[]
for rel,line_range in source_names.items():
    p=ROOT/'baseline/source'/rel
    if not p.exists():p=OLD/rel
    b=read(p);assert e.digest(b)==snap[rel].removeprefix('sha256:')
    name=rel.replace('/','__')+('.excerpt.txt' if line_range else '')
    copy(p,name,line_range)
    closure.append({'source':str(p),'as_run_relative_source':rel,'as_run_sha256':snap[rel],'match':True})
save('ADDITIONAL_SOURCE_CLOSURE.json',closure)
copy(OLD/'docs/protocols/model_family_expansion_v17/candidate_space.json','FROZEN_CANDIDATE_SPACE.json')
copy(OLD/'docs/protocols/model_family_expansion_v17/latency_subsets.json','FROZEN_LATENCY_SUBSETS.json')
copy(OLD/'docs/audit/manuscript_implementation_facts_v20/INITIAL_CONFIGURATION_FORMULA_TRACE.md','EXISTING_INITIAL_FORMULA_TRACE.md')
copy(OLD/'docs/audit/model_family_expansion_v17/final_vm1x6_release_r3/SELECTION_WALLCLOCK_SCOPE_NOTE.md','EXISTING_SELECTION_WALLCLOCK_SCOPE.md')
copy(ROOT/'docs/research/fg_expand_v2_20260905/FHE_AGENT_CORRECTION_KO.md','EXISTING_FHE_AGENT_CORRECTION_KO.md')
copy(ROOT/'docs/research/fg_expand_v2_20260905/RELATED_WORK_CRITERIA_KO.md','EXISTING_RELATED_WORK_CRITERIA_KO.md')
copy(ROOT/'docs/research/fg_contrib_v1_20260906/EXTERNAL_DESIGN_AND_LITERATURE_KO.md','EXISTING_EXTERNAL_DESIGN_KO.md')
copy(ROOT/'docs/research/fg_contrib_v1_20260906/REPORT_KO.md','EXISTING_CONTRIBUTION_REPORT_EXCERPT.txt',[(1,47),(195,265)])
copy(ROOT/'docs/research/fg_expand_v2_20260905/REPORT_KO.md','EXISTING_EXPANSION_EXTERNAL_EXCERPT.txt',[(119,135)])

# Detailed observed interval arithmetic for the chosen frozen linear case.
x=js(T/'SYNTHESIS_WORKED_EXAMPLE.json');model=js(x['model_path']);raw=rows(model_path:=Path(x['model_path']).parent/'configuration_selection.csv')
p=model['scaled_model_for_ckks'];norm=model['standardization'];sel=model['selected_feature_indices'];values=defaultdict(list)
for r in raw:
    features=[(float(r[f'x_{k}'])-m)/s for k,m,s in zip(sel,norm['mean'],norm['std'])]
    for i,z in enumerate(features):values[f'x_{i}'].append(z)
    terms=[w*z for w,z in zip(p['weights'],features)]
    for i,z in enumerate(terms):values[f'model_term_{i}'].append(z)
    z=terms[0]
    for i in range(1,len(terms)):
        z+=terms[i];values[f'model_sum_{i}'].append(z)
    z+=p['bias'];values['model_affine'].append(z)
    values['score'].append(.5+.197*z-.004*z**3)
lo=min(values['model_affine']);hi=max(values['model_affine'])
deriv=max(abs(.197-.012*z*z) for z in [lo,hi]+([0] if lo<=0<=hi else []))
operation_nodes=[n for n in values if not n.startswith('x_')]
agg=1+deriv*(len(operation_nodes)-1)
assert abs(agg-x['contract']['calibration']['aggregate_sensitivity'])<1e-12
e.table('WORKED_EXAMPLE_NODE_RANGES.csv',[{'node':n,'min':min(v),'max':max(v),'output_sensitivity':1 if n=='score' else (abs(p['weights'][int(n[2:])])*deriv if n.startswith('x_') else deriv),'included_in_sensitivity_sum':not n.startswith('x_'),'derivation':'frozen selected-feature normalization, stored weights, as-run IR arithmetic; no fitting','source_model':x['model_path'],'source_input':str(model_path)} for n,v in values.items()])
save('WORKED_EXAMPLE_ARITHMETIC.json',{'cubic_derivative_bound':deriv,'non_input_non_constant_nodes':len(operation_nodes),'aggregate_sensitivity':agg,'z_interval':[lo,hi],'model_sha256':e.bindings[x['model_path']]['sha256'],'input_sha256':e.bindings[str(model_path)]['sha256'],'analysis_percentile_note':'0.05 is passed to the generic analyzer, but its ProtectedMargin is not the primary contract budget; primary uses minimum margin strictly above delta','plain_only':True})

# Real cost boundaries, retaining every saved timing observation.
cost=[];id_rows=[]
for r in rows(T/'TIMING_BY_CASE.csv'):
    v=js(r['source']);blocks=[b['measurement'] for b in v['keysets']] if 'keysets' in v else v['keyset_results']
    allrec=[a for b in blocks for a in b['records']]
    for arm in ('direct','finite_fastest_safe'):
        rec=[a for a in allrec if a['arm_id']==arm];a=[a for b in blocks for a in b['arms'] if a['id']==arm]
        get=lambda key:statistics.mean(float(z[key]) for z in rec) if all(key in z for z in rec) else None
        setup=[z.get('setup_ms',z.get('setup_keygen_ms')) for z in a]
        ev='eval_only_ms' if 'eval_only_ms' in rec[0] else 'evaluation_only_ms'
        row={'case_id':r['case_id'],'arm':arm,'unit':r['unit'],'observations':len(rec),'key_contexts':len(a),
             'mean_setup_ms_per_context':statistics.mean(setup),'setup_source_field':'arms.setup_ms' if 'setup_ms' in a[0] else 'arms.setup_keygen_ms',
             'mean_encode_encrypt_ms':get('encode_encrypt_ms'),'mean_homomorphic_ms':get(ev),
             'mean_decrypt_decode_ms':get('decrypt_decode_ms'),'mean_adapter_io_ms':get('adapter_io_ms'),
             'mean_total_ms':get('total_ms'),'median_total_ms':statistics.median(z['total_ms'] for z in rec),
             'network_cost':'not measured','standalone_gate_cost':'not separately recorded',
             'setup_in_total_ms':False,'source':r['source']}
        row['mean_total_minus_recorded_components_ms']=row['mean_total_ms']-sum(row[k] or 0 for k in ['mean_encode_encrypt_ms','mean_homomorphic_ms','mean_decrypt_decode_ms','mean_adapter_io_ms'])
        cost.append(row)
    d=v['direct_candidate'];f=v['finite_fastest_safe_candidate']
    diag=next(z for z in rows(T/'CANDIDATE_COUNT_AND_COMPARATORS.csv') if z['case_id']==r['case_id'])
    id_rows.append({'case_id':r['case_id'],'direct_id':d['id'],'acceptable_id':f['id'],'acceptable_same_id':d['id']==f['id'],'acceptable_same_parameters_path':e.canon(d)==e.canon(f),'fastest_executable_id':diag['fastest_executable_candidate'],'fastest_executable_different_id':diag['fastest_executable_candidate']!=d['id'],'fastest_executable_different_parameters_path':diag['fastest_executable_differs_literal'],'direct_literal':d['parameters'],'acceptable_literal':f['parameters'],'source':r['source']})
e.table('COST_COMPONENTS_AND_SETUP.csv',cost);e.table('CANDIDATE_ID_LITERAL_RECONCILIATION.csv',id_rows)
times=rows(T/'TIMING_BY_CASE.csv');common=[r for r in times if r['selection_timer_ms']]
ratios=[float(r['finite_timer_ms'])/float(r['selection_timer_ms']) for r in common]
group=defaultdict(list)
for r in times:group[r['dataset'],r['model_id']].append(math.log(float(r['finite_over_direct_geomean'])))
estimate=math.exp(statistics.mean(statistics.mean(v) for v in group.values()))
formal=js(ROOT/'docs/review/latency_recomputed.json');assert abs(estimate-formal['estimate'])<1e-14
assert len(common)==66 and sum(z['fastest_executable_different_id'] for z in id_rows)==23
save('COST_RECONCILIATION.json',{'common_stage_timer_cases':len(common),'direct_total_ms':sum(float(r['selection_timer_ms']) for r in common),'finite_total_ms':sum(float(r['finite_timer_ms']) for r in common),'finite_over_direct_case_median':statistics.median(ratios),'finite_over_direct_case_iqr':[e.quantile(ratios,.25),e.quantile(ratios,.75)],'paired_point_recomputed':estimate,'existing_interval_reused':formal,'fastest_executable_different_ids':23,'fastest_executable_different_parameters_paths':21,'acceptable_identical_parameters_paths':65,'acceptable_identical_ids':63,'identity_discrepancy_with_previous_checked_summary':False})

# Existing larger plaintext quality records, with exact primary model binding.
mr=rows(T/'MODEL_TASK_AND_TRAINING.csv');q=[]
for name in ('base_mlp100','base_lenet5_small'):
    p=OLD/'results/model_family_expansion_v17/plaintext/multiclass_quality'/name/'quality.json';v=js(p)
    row=next(r for r in mr if r['model_id']==v['model_id']);assert v['model_sha256'].removeprefix('sha256:')==row['model_sha256']
    q.append({**v,'source':str(p),'source_sha256':e.bindings[str(p)]['sha256'],'measurement':'existing plaintext-only official-test record; not 10000 encrypted inputs'})
save('EXISTING_FULL_TEST_PLAINTEXT_QUALITY.json',q)

# Prior exact-prime security checks, bound only to the two matching candidates.
secpath=OLD/'docs/evidence/journal_multiclass_security_reconciliation_v1/reconciliation.json';sec=js(secpath);bound=[]
for label,modelid in [('mlp_100','mnist_mlp_square_784_100_10_v1'),('lenet5_small','mnist_lenet5_small_square_v1')]:
    c=next(r for r in id_rows if f'|{modelid}|' in r['case_id']);s=sec['models'][label]
    assert c['direct_literal']==s['literal'] and c['direct_id']==s['candidate_id']
    bound.append({'case_id':c['case_id'],'candidate_id':c['direct_id'],'same_literal':True,**{k:s[k] for k in ['actual_log_q','actual_log_p','actual_log_qp','minimum_classical_bits','security_policy_v2']}})
save('SECURITY_CHECK_SCOPE.json',{'source':str(secpath),'source_sha256':e.bindings[str(secpath)]['sha256'],'matching_primary_selected_candidates':bound,'posthoc':True,'new_estimator_runs':0,'new_prime_materialization':0,'exact_distribution_claim':False,'runtime_distribution_caveat':sec['distribution_caveat'],'coverage_caveat':'this two-candidate binding does not establish exact-prime checks for all68 or the follow-up Bank caller','worked_banknote_exact_prime_record':'not established in the bounded source records'})
copy(OLD/'docs/evidence/journal_multiclass_security_reconciliation_v1/candidate_security_summary.csv','EXISTING_MULTICLASS_SECURITY_SUMMARY.csv')
save('SOURCE_COPY_MANIFEST.json',copies)
e.dump(RUN/'DETAIL_READ_BINDINGS.json',e.bindings)
print(json.dumps({'cost_rows':len(cost),'source_copies':len(copies),'sensitivity':agg,'common_cases':len(common),'all_checks_pass':True}))
