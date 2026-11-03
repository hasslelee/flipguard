#!/usr/bin/env python3
"""Reaggregate already frozen journal observations. No HE/model training/import.

All predecessor accesses are bounded file reads from this DeciProtect process.
No parameter generation, old scripts, reserved DeciProtect audit or archive.
"""
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import statistics

ROOT=Path('/home/ckks2/deciprotect')
OLD=Path('/home/ckks2/flipguard')
import os
DOC=Path(os.environ.get('FG_EVIDENCE_DOC',str(ROOT/'docs/research/fg_journal_evidence_v1_20260906'))).resolve()
RUN=Path(os.environ.get('FG_EVIDENCE_RUN',str(ROOT/'results/fg_journal_evidence_v1_20260906_run01'))).resolve()
assert DOC.is_relative_to(ROOT/'docs/research') and RUN.is_relative_to(ROOT/'results')
RAW=OLD/'results/model_family_expansion_v17/runs/v17_final_vm1x6_20260811T050104Z'
LEG=ROOT/'docs/research/fg_expand_v1_20260905'
bindings={}; checks=[]; gaps=[]


def digest(b): return hashlib.sha256(b).hexdigest()
def rd(p, expected=None):
    p=Path(p)
    assert p.is_absolute() and (p.is_relative_to(ROOT) or p.is_relative_to(OLD))
    assert '/archive/' not in str(p) and 'fg_cause_v1_20260906_run01' not in str(p)
    assert not p.is_symlink() and p.resolve()==p
    b=p.read_bytes(); h=digest(b)
    if expected: assert h==expected.removeprefix('sha256:'),(str(p),'source binding mismatch')
    if str(p) in bindings: assert bindings[str(p)]['sha256']==h
    bindings[str(p)]={'sha256':h,'bytes':len(b),'expected_sha256':expected or bindings.get(str(p),{}).get('expected_sha256')}
    return b
def js(p, expected=None): return json.loads(rd(p,expected))
def rows(p, expected=None): return list(csv.DictReader(io.StringIO(rd(p,expected).decode())))
def dump(p,obj):
    with Path(p).open('x') as f: json.dump(obj,f,ensure_ascii=False,indent=2); f.write('\n')
def table(name,rs):
    fields=list(dict.fromkeys(k for r in rs for k in r))
    with (DOC/'evidence_tables'/name).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rs:w.writerow({k:json.dumps(v,ensure_ascii=False,separators=(',',':')) if isinstance(v,(list,dict,tuple)) else v for k,v in r.items()})
def unwrap(x):
    while 'result' in x:x=x['result']
    return x
def trial(x):
    x=unwrap(x)
    return x['trials'][-1] if 'trials' in x else x.get('trial',x.get('audit_trial',x))
def obs(t): return t.get('sample_ledger') or t.get('aggregation',{}).get('observations',[])
def rawpath(s):
    p=Path(s);return p if p.is_absolute() else OLD/p
def canon(c): return json.dumps({'parameters':c['parameters'],'path':c.get('path')},sort_keys=True,separators=(',',':'))
def ident(c): return digest(canon(c).encode())
def quantile(v,q):
    a=sorted(v);x=(len(a)-1)*q;i=int(x)
    return a[i]+(a[min(i+1,len(a)-1)]-a[i])*(x-i)


def observation(o):
    if 'plain_logits' in o:
        plain=o['plain_logits']; enc=o['ckks_logits'];
        rank=sorted(range(len(plain)),key=lambda i:(-plain[i],i));top=rank[0]
        margin=plain[top]-plain[rank[1]]
        e=[abs(a-b) for a,b in zip(plain,enc)]
        flip=top!=max(range(len(enc)),key=lambda i:enc[i])
        usage=max((e[top]+e[j])/(.5*(plain[top]-plain[j])) for j in range(len(plain)) if j!=top) if margin>0 else math.inf
        pred=top; score=plain
    else:
        plain=o.get('plaintext_score',o.get('plain_score')); enc=o['ckks_score'];th=o['threshold']
        assert plain is not None
        margin=abs(plain-th);e=[abs(plain-enc)];usage=e[0]/(.5*margin) if margin else math.inf
        pred=int(plain>=th);flip=pred!=int(enc>=th);score=plain
    eligible=margin>.001
    assert eligible==o['certifiable']
    return {'id':str(o['sample_id']),'key':o.get('key_repeat',o.get('key_run')),
            'plain':score,'pred':pred,'margin':margin,'eligible':eligible,'flip':flip,
            'violation':usage>=1,'usage':usage,'max_abs':max(e)}


def metrics(t, verify=True):
    ledger=obs(t); byid={};keys=defaultdict(set);flips=viol=boundary_flips=0;mi=[];errs=[];us=[]
    for o in ledger:
        a=observation(o);i=a['id'];keys[i].add(a['key'])
        if i in byid:assert byid[i]['plain']==a['plain']
        byid[i]=a;mi.append(a['margin']);errs.append(a['max_abs'])
        if a['eligible']:flips+=a['flip'];viol+=a['violation'];us.append(a['usage'])
        else:boundary_flips+=a['flip']
    if ledger:
        assert all(len(v)==t['key_repeats_completed'] for v in keys.values())
        if verify and 'decision_flips' in t:assert flips==t['decision_flips'] and viol==t['error_violations']
        if verify and 'aggregation' in t:
            g=t['aggregation']
            for name,value in [('argmax_flips',flips),('reserve_policy_violations',viol)]:
                if name in g:assert g[name]==value,(name,g[name],value)
    elig=[a for a in byid.values() if a['eligible']]
    return {'inputs':len(byid),'applicable':len(elig),'boundary':len(byid)-len(elig),
            'key_observations':len(ledger),'key_repeats':t.get('key_repeats_completed',0),
            'protected_flips':flips,'protected_error_violations':viol,'boundary_flip_observations':boundary_flips,
            'min_margin':min(mi) if mi else None,'max_margin':max(mi) if mi else None,
            'min_applicable_margin':min(a['margin'] for a in elig) if elig else None,
            'max_absolute_error':max(errs) if errs else None,'max_budget_usage':max(us) if us else None,
            'status':t.get('status','NOT_RECORDED')},byid


def label_map(p, expected=None):
    data=rows(p,expected); out={}
    for r in data:
        i=r.get('sample_id',r.get('row_id'));label=r.get('label',r.get('binary_label'))
        assert i is not None and label is not None
        assert i not in out
        out[i]=int(label)
    return out,data


def quality(case, role, observations, labels, source, model_hash):
    assert set(observations)==set(labels),(case,role,len(observations),len(labels))
    matrix=Counter((labels[i],a['pred']) for i,a in observations.items());cl=sorted(set(labels.values()))
    count=Counter(labels.values());correct=sum(v for (a,b),v in matrix.items() if a==b);n=len(labels)
    recalls={c:matrix[c,c]/count[c] for c in cl}
    f1=[]
    for c in cl:
        tp=matrix[c,c];fp=sum(v for (a,b),v in matrix.items() if a!=c and b==c);fn=count[c]-tp
        f1.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
    return {'case_id':case,'role':role,'n':n,'correct':correct,'accuracy':correct/n,
            'balanced_accuracy':statistics.mean(recalls.values()),'macro_f1':statistics.mean(f1),
            'class_counts':dict(count),'class_recall':recalls,
            'confusion_true_pred':{f'{a}->{b}':v for (a,b),v in sorted(matrix.items())},
            'model_sha256':model_hash,'label_source':str(source),'measurement':'reaggregation of frozen predictions and labels; key repeats deduplicated'}


def predict_tabular(model, data):
    p=model['scaled_model_for_ckks'];m=model['standardization'];sel=model['selected_feature_indices'];result={}
    for r in data:
        x=[(float(r[f'x_{k}'])-a)/s for k,a,s in zip(sel,m['mean'],m['std'])]
        if model['model_type'].startswith('linear_'):z=sum(a*b for a,b in zip(p['weights'],x))+p['bias']
        else:
            h=[(sum(a*b for a,b in zip(w,x))+b)**2 for w,b in zip(p['hidden_weights'],p['hidden_bias'])]
            if 'hidden2_weights' in p:h=[(sum(a*b for a,b in zip(w,h))+b)**2 for w,b in zip(p['hidden2_weights'],p['hidden2_bias'])]
            z=sum(a*b for a,b in zip(p['output_weights'],h))+p['output_bias']
        score=.5+.197*z-(.004*z**3 if model['model_type'].endswith('poly3') else 0)
        result[r['row_id']]={'pred':int(score>=.5),'plain':score}
    return result


def candidate_row(case,role,index,t,source,contract):
    m,_=metrics(t);c=t['candidate'];p=c['parameters'];sec=c.get('security',{})
    return {'case_id':case['case_id'],'dataset':case['dataset'],'model_id':case['model_id'],'split_id':case['split_id'],
            'role':role,'evaluation_ordinal':index,'candidate_id':c['id'],'literal_path_sha256':ident(c),
            'literal_spec_json':p,'log2N':p['log_n'],'q_count':len(p.get('log_q',p.get('q',[]))),
            'p_count':len(p.get('log_p',p.get('p',[]))),'q_bits':p.get('log_q'),'p_bits':p.get('log_p'),
            'scale':p['log_default_scale'],'execution_path':c.get('path'),
            'generation_kind':c.get('generation_kind'),'generation_reason':c.get('reason'),
            'security_admission':sec.get('final_admission',sec.get('admission_status')),
            'actual_encrypted_trial_record':True,'key_runs_completed':t.get('key_repeats_completed',0),
            'encrypted_sample_evaluations':t.get('encrypted_sample_evaluations'),
            **m,'candidate_stage_mean_total_ms':t.get('mean_total_ms'),
            'model_sha256':contract['model_artifact']['sha256'],'input_sha256':contract['validation_data']['sha256'],
            'raw_source':str(source),'raw_source_sha256':bindings[str(source)]['sha256'],
            'json_pointer':('/result' if role=='direct' and source.name=='selection_result.json' else '')+f'/{"entries" if role=="finite" else "trials"}/{index-1}/candidate',
            'literal_semantics':'complete stored ParametersLiteral specification, not newly materialized Q/P primes',
            'generator_dependency':'same decision-derived initial contract; not independent of margins' if role=='finite' else 'unchanged proposed procedure'}


def main():
    assert not (RUN/'ANALYSIS.json').exists()
    inv=rows(LEG/'legacy_inventory_sources/PRIMARY_68_CASE_INVENTORY.csv')
    legacy=rows(LEG/'LEGACY_CASES.csv'); primary={r['case_id']:r for r in legacy if r['group']=='primary_68'}
    assert len(inv)==68 and len(primary)==68
    aliases=[]
    for r in inv:
        if r['case_id'] not in primary:
            matches=[a for a in legacy if a['group']=='primary_68' and a['model_id']==r['model_id']]
            assert len(matches)==1 and r['model_id'] in ('mnist_mlp_square_784_100_10_v1','mnist_lenet5_small_square_v1')
            primary[r['case_id']]=matches[0]
            aliases.append({'inventory_case_id':r['case_id'],'legacy_alias':matches[0]['case_id'],
                            'selection_source':matches[0]['selection_source'],'reason':'two names for same frozen multiclass case; original selection contract split checked below'})
    coverage_old={(r['case_id'],r['stage']):r for r in rows(ROOT/'docs/review/all_coverage_recomputed.csv')}
    coverage_by_source={(str(rawpath(r['source'])),r['stage']):r for r in coverage_old.values()}
    oldbindings=js(LEG/'LEGACY_SOURCE_BINDINGS.json')
    source_snapshot_path=OLD/'docs/evidence/model_family_expansion_v17/source_snapshots/v17_final_vm1x6_20260811T050104Z/manifest.json'
    snap=js(source_snapshot_path); source_expected={r['path']:r['sha256'] for r in snap['source_files']}
    source_refs=['internal/ckksplanner/synthesis.go','internal/ckksplanner/v17_candidate_space.go',
                 'internal/ckksplanner/direct_policy.go','internal/ckksplanner/security_policy.go',
                 'internal/ckksplanner/tabular_contract.go','internal/ckksplanner/executor.go',
                 'internal/ckksplanner/multiclass_executor.go','internal/certify/multiclass_decision_contract.go',
                 'internal/ckksbackend/context.go','internal/ckksbackend/profile.go',
                 'cmd/flipguard-v17-tabular-case/main.go','scripts/build_v17_plaintext_suite.py']
    closure=[]
    for rel in source_refs:
        p=ROOT/'baseline/source'/rel
        if not p.exists():p=OLD/rel
        rd(p,source_expected[rel]);closure.append({'relative_source':rel,'read_path':str(p),'sha256':bindings[str(p)]['sha256'],
            'as_run_sha256':source_expected[rel],'as_run_match':True,'snapshot':str(source_snapshot_path),
            'execution_source_closure_commit':'cefc44b0d7e351db2a34886dd758a2d31a3e4c12'})
    table('SOURCE_CLOSURE.csv',closure)
    table('CASE_ID_ALIASES.csv',aliases)
    cases=[];candidates=[];quality_rows=[];model_rows=[];timing=[];diagnostics=[];example=None
    all_ids=defaultdict(set); training_ids=defaultdict(set); illustration=None
    for count,r in enumerate(sorted(inv,key=lambda r:r['case_id']),1):
        case=r['case_id']; l=primary[case]
        selection_path=Path(l['selection_source']);audit_path=Path(l['audit_source'])
        selection=unwrap(js(selection_path,oldbindings.get(str(selection_path))));audit=unwrap(js(audit_path,oldbindings.get(str(audit_path))))
        contract=selection['plan']['contract'];modelpath=rawpath(contract['model_artifact']['path'])
        model=js(modelpath,contract['model_artifact']['sha256']);modelhash=bindings[str(modelpath)]['sha256']
        ismulti='multiclass_decision' in contract;ispacked='packed_cnn' in r['model_id']
        if ismulti:assert contract['split_id']==r['split_id']
        splitmeta=None
        if ismulti:
            splitmeta=js(rawpath(model['split_manifest']['path']),model['split_manifest']['sha256'])
            selectp=rawpath(contract['validation_data']['path']);auditp=OLD/'datasets/journal_multiclass_extension_v1/mnist/locked_audit.csv'
        elif ispacked:
            splitmeta=js(modelpath.parent/'extraction_manifest.json')
            selectp=rawpath(contract['validation_data']['path']);auditp=rawpath(audit['audit_contract']['validation_data']['path'])
        else:
            selectp=rawpath(contract['source_data']['path']);auditp=modelpath.parent/'independent_evaluation.csv'
            splitmeta=js(modelpath.parent/'manifest.json')
            assert splitmeta['model_sha256'].removeprefix('sha256:')==modelhash
        stage_preds={}
        for stage, t, path, datapath in [('selection',selection['trials'][-1],selection_path,selectp),('separate',trial(audit),audit_path,auditp)]:
            m,unique=metrics(t)
            saved=coverage_by_source[str(path),stage]
            for key,old in [('inputs','inputs'),('applicable','eligible'),('boundary','boundary'),('protected_flips','protected_flip_events'),('protected_error_violations','protected_error_violations')]:
                assert m[key]==int(saved[old]),(case,stage,key,m[key],saved[old])
            expected=contract['validation_data']['sha256'] if (stage=='selection' and (ismulti or ispacked)) else None
            labels,data=label_map(datapath,expected)
            if not ismulti and not ispacked:
                role='configuration_selection' if stage=='selection' else 'independent_evaluation'
                assert bindings[str(datapath)]['sha256']==splitmeta['roles'][role]['sha256'].removeprefix('sha256:')
            if ismulti:assert bindings[str(datapath)]['sha256']==splitmeta['partitions']['configuration_validation' if stage=='selection' else 'locked_audit']['sha256'].removeprefix('sha256:')
            q=quality(case,stage,unique,labels,datapath,modelhash);quality_rows.append(q)
            stage_preds[stage]=unique
            observed_scores=[s for a in unique.values() for s in (a['plain'] if isinstance(a['plain'],list) else [a['plain']])]
            cases.append({'case_id':case,'dataset':r['dataset'],'model_id':r['model_id'],'stage':stage,**m,
                          'coverage':m['applicable']/m['inputs'],'plain_output_min':min(observed_scores),'plain_output_max':max(observed_scores),
                          'source':str(path),'label_source':str(datapath),'model_sha256':modelhash,'input_sha256':bindings[str(datapath)]['sha256'],
                          'class_counts':q['class_counts'],'plaintext_accuracy':q['accuracy']})
            all_ids[stage,r['dataset']].update(labels)
        assert not set(stage_preds['selection'])&set(stage_preds['separate'])
        if not ismulti and not ispacked:
            trainpath=modelpath.parent/'model_training.csv';labels,data=label_map(trainpath,splitmeta['roles']['model_training']['sha256'])
            assert not set(labels)&(set(stage_preds['selection'])|set(stage_preds['separate']))
            trainpred=predict_tabular(model,data)
            q=quality(case,'model_training',trainpred,labels,trainpath,modelhash);q['measurement']='plaintext arithmetic from frozen model/preprocessing; no refit or training';quality_rows.append(q)
            training_ids[r['dataset']].update(labels)
            # Check the plaintext-only evaluator against stored inference scores.
            _,data=label_map(selectp);replay=predict_tabular(model,data)
            gap=max(abs(replay[i]['plain']-stage_preds['selection'][i]['plain']) for i in replay)
            checks.append({'check':'frozen_plaintext_replay','case_id':case,'max_abs_gap':gap,'pass':gap<1e-10})
            assert gap<1e-10
        model_rows.append({'case_id':case,'dataset':r['dataset'],'model_id':r['model_id'],'split_id':r['split_id'],
                           'model_path':str(modelpath),'model_sha256':modelhash,'model_type':model.get('model_type'),
                           'architecture':model.get('architecture') or {'input_dim':model.get('input_dim'),'hidden': [8,4] if 'square2' in r['model_id'] else ([4] if 'mlp' in r['model_id'] else []),'output_formula':model.get('polynomial_score')},
                           'training':model.get('training') or {'training_seed':model.get('training_seed'),'training_rows':model.get('train_samples'),'source_rule':'build_v17_plaintext_suite.py; fixed optimizer limits, no saved convergence flag'},
                           'preprocessing':model.get('preprocessing') or {'selected_features':model.get('selected_feature_indices'),'fit_role':'model_training only','training_only_logit_scale':model.get('training_only_logit_scale')},
                           'stored_quality':model.get('plaintext_accuracy') or splitmeta.get('quality_independent_evaluation',{}),
                           'packing':contract['deployment']['packing_strategy'],'required_slots':contract['deployment']['required_slots'],
                           'training_quality_status':'stored epoch online metric only' if ismulti else ('stored final model metric' if ispacked else 'plaintext reaggregation'),
                           'convergence_status':'fixed epochs; no convergence claim' if ismulti or ispacked or 'mlp' in r['model_id'] else 'iteration cap2000; fitted n_iter/warnings not stored in model artifact'})
        if ismulti or ispacked:
            meta={k:v for k,v in model.items() if k not in ('parameters','learned_parameters')}
            dump(DOC/'evidence_tables'/f'MODEL_METADATA_{r["model_id"]}.json',{'model':meta,'split_record':splitmeta,'original_model_sha256':modelhash,'original_model_path':str(modelpath)})
        finite_path=(RAW/'exhaustive'/r['model_id']/'exhaustive.json') if ismulti else selection_path.parent/'exhaustive.json'
        finite=js(finite_path)
        assert finite['formal_denominator']==len(finite['entries'])
        direct_rows=[candidate_row(r,'direct',i,t,selection_path,contract) for i,t in enumerate(selection['trials'],1)]
        finite_rows=[candidate_row(r,'finite',i,t,finite_path,contract) for i,t in enumerate(finite['entries'],1)]
        candidates.extend(direct_rows+finite_rows)
        valid=[(t,x) for t,x in zip(finite['entries'],finite_rows) if x['key_runs_completed']==3 and x['security_admission']=='PASS' and x['status'] in ('SAFE','REJECTED')]
        fast,fr=min(valid,key=lambda pair:(pair[0]['mean_total_ms'],pair[0]['trial_index']))
        safe,sr=min((p for p in valid if p[1]['status']=='SAFE'),key=lambda pair:(pair[0]['mean_total_ms'],pair[0]['trial_index']))
        selected=selection['selected'];
        diagnostics.append({'case_id':case,'finite_evaluations':len(finite_rows),'direct_evaluations':len(direct_rows),
                            'finite_unique_ids':len({x['candidate_id'] for x in finite_rows}),
                            'finite_unique_literal_paths':len({x['literal_path_sha256'] for x in finite_rows}),
                            'direct_finite_shared_literal_paths':len({x['literal_path_sha256'] for x in direct_rows}&{x['literal_path_sha256'] for x in finite_rows}),
                            'fastest_executable_candidate':fast['candidate']['id'],'fastest_executable_flips':fr['protected_flips'],
                            'fastest_executable_violations':fr['protected_error_violations'],
                            'fastest_executable_differs_literal':canon(fast['candidate'])!=canon(selected),
                            'fastest_acceptable_candidate':safe['candidate']['id'],
                            'fastest_acceptable_differs_literal':canon(safe['candidate'])!=canon(selected),
                            'fastest_acceptable_differs_id':safe['candidate']['id']!=selected['id'],
                            'finite_source':str(finite_path),'selection_source':str(selection_path),
                            'formal_denominator':finite['formal_denominator'],'generator_id':finite['generator_id']})
        # One procedural case: first adjusted case under the rule fixed in START_STATE.
        if example is None and len(selection['trials'])>1:
            a=selection['plan']['initial_candidates'][0];d=contract['decision'];cal=contract['calibration'];u=d['output_error_budget']/cal['aggregate_sensitivity'];p=max(0,math.ceil(-math.log2(u)))
            assert p==a['precision_target_bits'] and max(18,p+3)==a['analysis_scale_bits']
            firstobs={ (str(o['sample_id']),o.get('key_repeat',o.get('key_run'))):o for o in obs(selection['trials'][0]) }
            lastobs={ (str(o['sample_id']),o.get('key_repeat',o.get('key_run'))):o for o in obs(selection['trials'][-1]) }
            eligible=[key for key,o in firstobs.items() if observation(o)['eligible'] and observation(o)['flip'] and not observation(lastobs[key])['flip']]
            example={'case_id':case,'selection_rule':'lexicographic case_id first of frozen21 adjusted with complete evidence',
                     'contract':contract,'policy':selection['plan']['policy'],'unit_budget_recomputed':u,
                     'precision_bits_recomputed':p,'analysis_scale_recomputed':max(18,p+3),
                     'initial_candidate':a,'selected_candidate':selected,'trial_metrics':direct_rows,
                     'selection_path':str(selection_path),'model_path':str(modelpath),'split_manifest':str(modelpath.parent/'manifest.json')}
            if eligible:
                key=min(eligible,key=lambda t:(int(t[0]) if t[0].isdigit() else t[0],t[1]))
                illustration={'case_id':case,'sample_id':key[0],'key_repeat_index':key[1],
                              'selection_rule':'smallest original input ID then key index among applicable repaired flips in first illustrative case',
                              'initial_observation':firstobs[key],'selected_observation':lastobs[key],
                              'key_caveat':'same key-repeat index, independently generated contexts for different candidate literals; not the same secret key',
                              'source':str(selection_path),'source_sha256':bindings[str(selection_path)]['sha256']}
        # Existing timing only; infer no unmeasured service/network cost.
        timing_path=OLD/r['formal_latency_record'];v=js(timing_path)
        arms=defaultdict(list);setup=defaultdict(list);pairs=defaultdict(dict)
        blocks=[(b['keyset'],b['measurement']) for b in v['keysets']] if 'keysets' in v else [(None,v)]
        for key,b in blocks:
            if 'setup_ms' in b:setup['recorded'].append(b['setup_ms'])
            for rec in b['records']:
                arm=rec['arm_id'];arms[arm].append(rec['total_ms']);pair=(key if key is not None else rec['keyset'],rec['measurement_run'],rec.get('row_id','batch'))
                assert arm not in pairs[pair];pairs[pair][arm]=rec['total_ms']
        ratios=[a['finite_fastest_safe']/a['direct'] for a in pairs.values()]
        raw_direct=selection['trials'][-1]['mean_total_ms']; raw_initial=selection['trials'][0]['mean_total_ms']
        stpath=selection_path.parent/'stage_timing.json';stage=js(stpath) if stpath.exists() else {}
        timing.append({'case_id':case,'dataset':r['dataset'],'model_id':r['model_id'],
                       'unit':'one invocation over batch20 inputs' if ismulti or ispacked else 'one input invocation',
                       'paired_ratios':len(ratios),'direct_median_ms':statistics.median(arms['direct']),
                       'finite_acceptable_median_ms':statistics.median(arms['finite_fastest_safe']),
                       'finite_over_direct_geomean':math.exp(statistics.mean(map(math.log,ratios))),
                       'literal_path_identical':canon(v['direct_candidate'])==canon(v['finite_fastest_safe_candidate']),
                       'candidate_id_identical':v['direct_candidate']['id']==v['finite_fastest_safe_candidate']['id'],
                       'selection_initial_mean_ms':raw_initial,'selection_final_mean_ms':raw_direct,
                       'selection_final_over_initial':raw_direct/raw_initial,
                       'adjusted':len(selection['trials'])>1,'selection_timer_ms':stage.get('selection_wall_clock_ms'),
                       'finite_timer_ms':stage.get('exhaustive_wall_clock_ms',finite.get('wall_clock_ms')),
                       'initial_final_timing_class':'selection-stage observational, separate candidate key contexts; not matched timing',
                       'source':str(timing_path),'stage_timing_source':str(stpath) if stpath.exists() else 'direct wall clock missing for frozen multiclass predecessor'})
        if count%10==0: print(f'PRIMARY_CASES {count}/68',flush=True)
    table('CANDIDATE_SPECIFICATIONS.csv',candidates);table('CASE_SCOPE_AND_QUALITY.csv',cases)
    table('MODEL_QUALITY_BY_ROLE.csv',quality_rows);table('MODEL_TASK_AND_TRAINING.csv',model_rows)
    table('CANDIDATE_COUNT_AND_COMPARATORS.csv',diagnostics);table('TIMING_BY_CASE.csv',timing)
    dump(DOC/'evidence_tables/SYNTHESIS_WORKED_EXAMPLE.json',example)
    dump(DOC/'evidence_tables/ACTUAL_DECISION_REPAIR_EXAMPLE.json',illustration)
    add=[]
    for r in legacy:
        if r['group']!='primary_68':add.append(r)
    table('ADDITIONAL_63_CASES.csv',add)
    runstatus=rows(RAW/'run_status.csv');table('RUN_CLASSIFICATION.csv', [{'phase':p,'jobs':n} for p,n in sorted(Counter(r['phase'] for r in runstatus).items())])
    depth=rows(OLD/'results/model_family_expansion_v17/final_vm1x6/table_10_depth_ladder.csv');table('DEPTH_5_CONDITIONS.csv',depth)
    neg=next(r for r in add if r['dataset_id']=='banknote' and r['model_id']=='mlp_square_poly3' and 'fold_3' in r['split_id'])
    nt=trial(js(Path(neg['audit_source']),oldbindings.get(neg['audit_source'])));nm,_=metrics(nt)
    bad=[o for o in obs(nt) if observation(o)['eligible'] and observation(o)['violation']]
    assert nm['protected_flips']==0 and nm['protected_error_violations']==1
    dump(DOC/'evidence_tables/ADDITIONAL_ERROR_ONLY_CASE.json',{'case':neg,'metrics':nm,'violating_observations':bad})
    groups=[]
    for dataset,model in sorted({(r['dataset'],r['model_id']) for r in cases}):
        c=[r for r in cases if r['dataset']==dataset and r['model_id']==model and r['stage']=='separate']
        t=[r for r in timing if r['dataset']==dataset and r['model_id']==model]
        groups.append({'dataset':dataset,'model_id':model,'cases':len(c),'separate_inputs':sum(r['inputs'] for r in c),
                       'applicable':sum(r['applicable'] for r in c),'boundary':sum(r['boundary'] for r in c),
                       'accuracy_min':min(r['plaintext_accuracy'] for r in c),'accuracy_max':max(r['plaintext_accuracy'] for r in c),
                       'coverage_min':min(r['coverage'] for r in c),'coverage_max':max(r['coverage'] for r in c),
                       'direct_median_ms_min':min(r['direct_median_ms'] for r in t),'direct_median_ms_max':max(r['direct_median_ms'] for r in t),
                       'timing_unit':t[0]['unit']})
    table('MODEL_SUMMARY.csv',groups)
    table('INPUT_UNITS.csv',[{'role':stage,'dataset':data,'unique_source_ids_within_dataset_role':len(ids),
                             'note':'same original row may recur across models/folds and roles; not independent case-input pairs'}
                            for (stage,data),ids in sorted(all_ids.items())])
    formal=js(ROOT/'docs/review/latency_recomputed.json')
    totals={stage:{k:sum(r[k] for r in cases if r['stage']==stage) for k in ['inputs','applicable','boundary','key_observations','protected_flips','protected_error_violations']} for stage in ('selection','separate')}
    assert totals['selection']['inputs']==18385 and totals['selection']['applicable']==16081
    assert totals['separate']['inputs']==18367 and totals['separate']['applicable']==16049
    finite_rows=[r for r in candidates if r['role']=='finite'];direct_rows=[r for r in candidates if r['role']=='direct']
    assert len(finite_rows)==537 and len(direct_rows)==89
    assert sum(r['paired_ratios'] for r in timing)==23454
    adjusted=[r['selection_final_over_initial'] for r in timing if r['adjusted']]
    summary={'task_id':'FG_JOURNAL_EVIDENCE_V1_20260906','created_utc':datetime.now(timezone.utc).isoformat(),
             'primary_cases':68,'candidate_trials':{'direct':len(direct_rows),'finite':len(finite_rows)},
             'finite_statuses':dict(Counter(r['status'] for r in finite_rows)),
             'direct_statuses':dict(Counter(r['status'] for r in direct_rows)),
             'finite_count_distribution':dict(Counter(r['finite_evaluations'] for r in diagnostics)),
             'finite_unique_case_literal_paths':sum(r['finite_unique_literal_paths'] for r in diagnostics),
             'finite_actual_key_runs':sum(r['key_runs_completed'] for r in finite_rows),
             'fastest_executable':{'flip_cases':sum(r['fastest_executable_flips']>0 for r in diagnostics),
                                   'violation_cases':sum(r['fastest_executable_violations']>0 for r in diagnostics),
                                   'flip_and_violation':sum(r['fastest_executable_flips']>0 and r['fastest_executable_violations']>0 for r in diagnostics),
                                   'different_literal_cases':sum(r['fastest_executable_differs_literal'] for r in diagnostics),
                                   'different_and_violation':sum(r['fastest_executable_differs_literal'] and r['fastest_executable_violations']>0 for r in diagnostics)},
             'fastest_acceptable_different_literal_cases':sum(r['fastest_acceptable_differs_literal'] for r in diagnostics),
             'fastest_acceptable_different_id_cases':sum(r['fastest_acceptable_differs_id'] for r in diagnostics),
             'formal_timing_identical_literal_cases':sum(r['literal_path_identical'] for r in timing),
             'scope_totals':totals,'adjusted_cases':len(adjusted),'adjusted_selection_time_ratio_median':statistics.median(adjusted),
             'stored_formal_latency_summary':formal,'additional_groups':dict(Counter(r['group'] for r in add)),
             'depth_rows':len(depth),'run_jobs':dict(Counter(r['phase'] for r in runstatus)),
             'new_ckks':0,'new_parameter_generation':0,'retraining':0,'reserved_audit_access':False,
             'gaps':gaps,'checks':checks,'tables':[p.name for p in sorted((DOC/'evidence_tables').iterdir())]}
    dump(RUN/'ANALYSIS.json',summary);dump(RUN/'READ_BINDINGS.json',bindings)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('checks','stored_formal_latency_summary','tables')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
