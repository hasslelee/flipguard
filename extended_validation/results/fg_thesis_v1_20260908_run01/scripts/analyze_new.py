"""Recompute the finite new bundle. This reducer never invokes CKKS or trains a model."""
from pathlib import Path
import json,csv,collections,re,math,statistics
import numpy as np
import run as r
import metrics
RUN=r.RUN;DOC=r.ROOT/'docs/research/fg_thesis_v1_20260908'

def csvout(name,rows):
    fields=list(dict.fromkeys(k for x in rows for k in x))
    with (DOC/name).open('x',newline='') as f:
        w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)

def keycost(j):
    s=j['summary'];rs=j['records'];tab='PlainY' in rs[0]
    if tab:
        enc=sum(x['EncodeEncryptMS'] for x in rs);he=sum(x['EvalOnlyMS'] for x in rs);dec=sum(x['DecryptDecodeMS'] for x in rs)
        return {'parameter_ms':j['parameter_ms'],'setup_ms':s['CryptoSetupMS'],'encode_encrypt_ms':enc,
            'he_ms':he,'decrypt_decode_ms':dec,'pdf_inference_ms':enc+he+dec,'input_count':len(rs),
            'he_batch_executions':len(rs),'input_ciphertexts_per_batch':s['InputDim'],'output_ciphertexts_per_batch':1,
            'valid_inputs_per_batch':1,'available_slots':s['MaxSlots'],'initial_level':s['InitialLevel'],
            'final_level':s['FinalYLevel'],'adapter_io_ms':None,'packing':'one input, feature ciphertext with replicated scalar slots'}
    return {'parameter_ms':j['parameter_ms'],'setup_ms':s['crypto_setup_ms'],'encode_encrypt_ms':s['encode_encrypt_ms'],
        'he_ms':s['evaluation_only_ms'],'decrypt_decode_ms':s['decrypt_decode_ms'],'pdf_inference_ms':s['total_ms'],
        'input_count':len(rs),'he_batch_executions':1,'input_ciphertexts_per_batch':s['input_ciphertexts'],
        'output_ciphertexts_per_batch':s['output_ciphertexts'],'valid_inputs_per_batch':s['required_slots'],
        'available_slots':s['available_slots'],'initial_level':s['initial_level'],'final_level':s['final_level'],
        'adapter_io_ms':s.get('adapter_io_ms'),'packing':'feature ciphertexts, input samples in slots'}

def params(c):
    if not c:return {}
    p=c['parameters'];return {'log_n':p['log_n'],'N':2**p['log_n'],'scale_bits':p['log_default_scale'],
        'Q_count':len(p['log_q']),'P_count':len(p['log_p']),'declared_Q_bits':sum(p['log_q']),
        'declared_QP_bits':sum(p['log_q'])+sum(p['log_p']),'Q_bit_list':str(p['log_q']),
        'P_bit_list':str(p['log_p']),'path':c['path']}

def main():
    assert metrics.selftest();r.verify()
    sp=r.read(r.PROTOCOL);cases={x['case_id']:x for x in sp['cases']};fr=r.read(RUN/'FROZEN_SELECTIONS.json')
    selections=[];prefix=[];trials=[];costs=[];index=[];failures=[];analyses=[]
    def loadkey(p,**meta):
        j=r.read(p);index.append({'path':str(p),'sha256':r.sha(p),'bytes':p.stat().st_size,**meta})
        costs.append({**meta,'path':str(p),**keycost(j)});return j
    for x in fr['records']:
        p=Path(x['result']);res=r.read(p) if p.exists() else {};end=r.read(RUN/'commands'/(x['id']+'.end.json'))
        ap=p.parent/'analysis.json'
        if ap.exists():
            aj=r.read(ap);plan=aj.get('plan',{});contract=aj.get('evaluation_contract',{});cal=contract.get('calibration',{})
            dc=contract.get('multiclass_decision') or contract.get('decision',{})
            initial=(plan.get('initial_candidates') or [t['candidate'] for t in res.get('trials',[])])
            ic=initial[0] if initial else {}
            analyses.append({'job':x['id'],'case':x['case'],'role':x['role'],'phase':x['phase'],'setting':x['setting'],
                'selection_inputs':dc.get('validation_samples'),'applicable_selection_inputs':dc.get('certifiable_samples'),
                'boundary_selection_inputs':dc.get('ambiguous_samples'),'protected_margin_or_gap':dc.get('protected_top_two_gap',dc.get('protected_margin')),
                'output_error_budget':dc.get('per_logit_error_budget',dc.get('output_error_budget')),
                'aggregate_sensitivity':cal.get('aggregate_sensitivity'),'max_input_abs':cal.get('max_input_abs'),
                'max_plaintext_output_abs':cal.get('max_plaintext_output_abs'),
                'margin_fields_role':'C synthesis and acceptance' if x['role'] in ['C','Cprime'] else 'acceptance only, excluded from independent generator',
                'generator_independent_of_evaluation_contract':aj.get('generator_does_not_receive_evaluation_contract'),
                'initial_scale_bits':ic.get('parameters',{}).get('log_default_scale'),'initial_log_n':ic.get('parameters',{}).get('log_n'),
                'analysis_scale_bits':ic.get('analysis_scale_bits'),'precision_target_bits':ic.get('precision_target_bits'),
                'backend_scale_lift_bits':ic.get('backend_scale_lift_bits'),'legacy_backend_validation_attempts':ic.get('backend_validation_attempts'),
                'same_tier_precision_gain_bits':ic.get('same_tier_precision_gain_bits'),'legacy_same_tier_static_candidates_tried':ic.get('same_tier_static_candidates_tried'),
                'static_count_limit':'legacy counters are reported separately; not total static calls, Cprime also checks base Synthesize once',
                'source':str(ap),'source_sha256':r.sha(ap)})
        state=res.get('outcome','EXECUTION_FAILURE')
        if not p.exists():
            log=(RUN/'commands'/(x['id']+'.log')).read_text()
            if 'validation data has no certifiable sample above margin floor' in log:
                state='NO_APPLICABLE_SELECTION_DOMAIN'
            failures.append({'command_id':x['id'],'classification':state,'exit_code':end['exit_code'],'log':str(RUN/'commands'/(x['id']+'.log'))})
        cs=[];key_files=0
        for ordinal,t in enumerate(res.get('trials',[]),1):
            files=sorted(p.parent.glob(f'trial_{ordinal}/key_*.json'));js=[loadkey(f,phase=x['phase'],case=x['case'],role=x['role'],job=x['id'],trial=ordinal,stage='selection') for f in files]
            key_files+=len(files);cs += [keycost(j) for j in js]
            m=metrics.summarize([j['records'] for j in js],x['rho'],x['delta'])
            if t['status']=='SAFE':
                assert len(js)==3 and m['applicable_inputs']>0 and m['applicable_flip_events']==0 and m['applicable_error_events']==0,('SAFE_RECOMPUTE_MISMATCH',x['id'],ordinal)
            trials.append({'job':x['id'],'phase':x['phase'],'case':x['case'],'role':x['role'],'block':x['block'],
                'ordinal':ordinal,'status':t['status'],'failure_signal':t.get('failure_signal'), 'keys':t['keys'],
                **params(t['candidate']),**m,'native_wall_ms':t.get('native_wall_ms'),
                'legacy_backend_validation_attempts':t['candidate'].get('backend_validation_attempts'),
                'legacy_same_tier_static_candidates_tried':t['candidate'].get('same_tier_static_candidates_tried')})
        cost={k:sum(z[k] for z in cs) for k in ['parameter_ms','setup_ms','encode_encrypt_ms','he_ms','decrypt_decode_ms','pdf_inference_ms']}
        native=sum(t.get('native_wall_ms',0) for t in res.get('trials',[]))
        selections.append({'job':x['id'],'phase':x['phase'],'case':x['case'],'role':x['role'],'block':x['block'],
            'setting':x['setting'],'rho':x['rho'],'delta':x['delta'],'input_order_seed':x.get('input_order_seed'),
            'selection_inputs':x.get('n',cases[x['case']]['selection_inputs']),'outcome':state,'literal_id':x['literal_id'],
            **params(res.get('selected')),'encrypted_candidates':res.get('actual_encrypted_candidates',0),
            'key_contexts_written':key_files,'selection_wall_ms':end['wall_seconds']*1000,
            'analysis_ms':res.get('analysis_ms'),'candidate_native_wall_ms':native,'evidence_write_ms':res.get('evidence_write_ms'),
            'decision_gate_ms':sum(t.get('decision_ms',0) for t in res.get('trials',[])),
            'numeric_summary_ms':sum(t.get('numeric_ms',0) for t in res.get('trials',[])),**cost,
            'independent_generation_attempts':len(res.get('generation_attempts',[])),
            'process_exit':end['exit_code']})
        if x['phase'] in ['A2','A3']:
            for cap in [1,2,4]:
                success=state=='SELECTED' and res['actual_encrypted_candidates']<=cap
                prefix.append({'job':x['id'],'phase':x['phase'],'case':x['case'],'setting':x['setting'],'prefix_cap':cap,
                    'selected_in_observed_prefix':success,'literal_id':x['literal_id'] if success else None,
                    'observed_candidate_count':min(cap,res.get('actual_encrypted_candidates',0)),
                    'scope':'observed prefix, not separate cap execution; no extrapolation beyond 4','original_outcome':state})
    csvout('SELECTION_METRICS.csv',selections);csvout('TRIAL_METRICS.csv',trials);csvout('PREFIX_CAP.csv',prefix);csvout('INITIAL_ANALYSIS.csv',analyses)
    audit_rows=[];events=[];input_units=collections.defaultdict(set);normal_cases=set();normal_sources=set();synthetic_cases=set()
    for case in sorted({x['case'] for x in fr['records']}):
        c=cases[case]
        for folder in sorted((RUN/'audit'/case).glob('*/*')):
            lid=folder.parent.name;stage=folder.name;files=sorted(folder.glob('batch_*/key_*.json'))
            if not files:continue
            js=[loadkey(p,phase='audit',case=case,role='shared_literal',job=lid,trial='',stage=stage) for p in files]
            for j in js:
                for rec in j['records']:
                    tab='RowID' in rec
                    sid=str(rec['RowID'] if tab else rec['source_index'])
                    family=case.split('__')[0] if tab else 'fashion_mnist' if case.startswith('fashion') else 'bank_marketing'
                    part='original_source_rows' if tab else rec['source_partition']
                    identity=(family,part,sid)
                    if stage=='exposed_synthetic':identity=(family,'synthetic_point_ids',str(rec['sample_id']))
                    input_units[(case,stage)].add(identity)
                    if stage=='exposed_synthetic':synthetic_cases.add((case,identity))
                    else:normal_cases.add((case,identity));normal_sources.add(identity)
            aliases=[x for x in fr['records'] if x['case']==case and x['literal_id']==lid]
            settings={('base',.5,.001)}|{(x['setting'],x['rho'],x['delta']) for x in aliases if x['phase']=='A2'}
            cand=r.read(aliases[0]['candidate_path']);expected=9 if stage=='reserved684' else 6 if c['kind']=='multiclass' else 3
            for setting,rho,delta in sorted(settings):
                m=metrics.summarize([j['records'] for j in js],rho,delta,stage=='exposed_synthetic')
                tau=c['thresholds']['max_abs']
                if c['kind']=='bank':
                    tau=r.read(r.ROOT/'results/fg_contrib_v1_20260906_run01/external/hediff_bank/INPUT_MODEL_LOCK.json')['numeric_thresholds']['max_abs']
                audit_rows.append({'case':case,'literal_id':lid,'stage':stage,'setting':setting,'aliases':';'.join(x['id'] for x in aliases),
                    **params(cand),**m,'expected_key_contexts':expected,'complete_key_count':len(js)==expected,
                    'A_development_maxabs_threshold':tau,'passes_A_maxabs_each_key':all(metrics.summarize([j['records']])['max_abs']<=tau for j in js) if tau else None,
                    'numeric_threshold_scope':'reused historical development threshold, posthoc only for these C/Cprime/B paths, all outputs and executed key contexts',
                    'audit_input_exposure':'previously unscored, whole-source preprocessing exposed' if stage=='reserved684' else 'previously exposed',
                    'network_ms':None,'queue_ms':None})
            for path,j in zip(files,js):
                v=metrics.arrays(j['records'])
                for i,(sid,g,rat,f) in enumerate(zip(v['ids'],v['margin'],v['ratio'],v['flip'])):
                    if not f and not (g>.001 and rat>=.5):continue
                    events.append({'case':case,'literal_id':lid,'stage':stage,'key_file':str(path),'input_id':sid,
                        'margin':g,'applicable_base':g>.001,'decision_flip':bool(f),'error_violation_base':bool(rat>=.5),
                        'budget_usage_base':rat/.5,'plaintext':json.dumps(v['p'][i].tolist()),'ckks':json.dumps(v['a'][i].tolist()),
                        'synthetic_truth_asserted':False})
    csvout('AUDIT_METRICS.csv',audit_rows);csvout('KEY_COSTS.csv',costs);csvout('EVENTS_LOCAL_ONLY.csv',events)
    unit_rows=[{'scope':'per model and stage, union across literal/method/key','case':k[0],'stage':k[1],'unique_case_inputs':len(v),'unique_source_rows':len(v) if k[1]!='exposed_synthetic' else 'not counted; synthetic point IDs are not original rows','synthetic_is_original_population':False} for k,v in sorted(input_units.items())]
    unit_rows += [{'scope':'all normal audits, union across methods/literals/keys','case':'ALL','stage':'existing + reserved','unique_case_inputs':len(normal_cases),'unique_source_rows':len(normal_sources),'synthetic_is_original_population':False},
        {'scope':'exposed synthetic regression, kept separate','case':'ALL','stage':'exposed_synthetic','unique_case_inputs':len(synthetic_cases),'unique_source_rows':'not counted; synthetic points are not original source rows','synthetic_is_original_population':False}]
    csvout('INPUT_UNITS.csv',unit_rows)
    csvout('RAW_INDEX.csv',index)
    identity=r.read(RUN/'A3_INPUT_SEPARATION_CHECK.json')
    csvout('A3_INPUT_IDENTITY.csv',identity['subset_checks'])
    csvout('INPUT_VECTOR_SEPARATION.csv',[{k:v for k,v in x.items() if k!='source_files'} for x in identity['checks']])
    # Parse all process outcomes, including unsuccessful or partial ones.
    resources=[]
    for p in sorted((RUN/'commands').glob('*.end.json')):
        e=r.read(p);name=p.name[:-9];log=Path(str(p).replace('.end.json','.log')).read_text()
        rss=re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)',log)
        resources.append({'command_id':name,'exit_code':e['exit_code'],'wall_seconds':e['wall_seconds'],
            'charged_native':e['charged_native'],'peak_rss_kib':int(rss[1]) if rss else None,'result_exists':e['result_exists'],
            'load_before':str(e.get('before',{}).get('load')),'load_after':str(e.get('after',{}).get('load')),
            'command':json.dumps(e['command'],ensure_ascii=False)})
        if e['exit_code'] and name not in {x['command_id'] for x in failures}:failures.append({'command_id':name,'classification':'EXECUTION_FAILURE','exit_code':e['exit_code'],'log':str(p).replace('.end.json','.log')})
    csvout('PROCESS_COSTS.csv',resources);csvout('FAILURES.csv',failures)
    security=[]
    concrete_records=[(p,r.read(p),'selection') for p in (RUN/'selection').glob('*/concrete_*.json')]
    concrete_records += [(p,r.read(p)['concrete'],'static') for p in (RUN/'static').glob('*/*/result.json')]
    for p,cr,stage in concrete_records:
        se=cr['actual_security'];de=cr['declared'];co=cr['concrete']
        security.append({'stage':stage,'source':str(p),'source_sha256':r.sha(p),'candidate_id':cr['candidate_id'],
            'log_n':de['log_n'],'scale_bits':de['log_default_scale'],'declared_Q_bits':sum(de['log_q']),
            'declared_QP_bits':sum(de['log_q'])+sum(de['log_p']),'actual_ceil_log2_Q':se['log_q'],
            'actual_ceil_log2_P':se['log_p'],'actual_ceil_log2_QP':se['log_qp'],'cap_bits':se['max_allowed_log_qp'],
            'Q_admission':se['ciphertext_q_admission'],'QP_admission':se['evaluation_key_qp_admission'],
            'admission':se['final_admission'],'Xs':cr['Xs'],'Xe':cr['Xe'],'backend_valid':cr['backend_valid'],
            'Q_primes':json.dumps(co['q']),'P_primes':json.dumps(co['p']),
            'interpretation':'frozen 128-bit parameter policy and Lattigo validity; not new attack-cost estimate'})
    csvout('SECURITY_PARAMETERS.csv',security)
    r.write(RUN/'NEW_METRICS_VERIFIED.json',{'utc':r.now(),'selections':len(selections),'trials':len(trials),
        'audit_rows_with_alias_and_setting':len(audit_rows),'raw_key_files':len(index),'events':len(events),
        'sufficient_condition_counterexample_events':0,'condition_boundary_tests':metrics.selftest(),
        'charged_native_seconds':r.used(),'all_recorded_native_seconds':sum(x['wall_seconds'] for x in resources),'analysis_source_sha256':r.sha(Path(__file__))})
    print('REDUCED',len(selections),len(trials),len(audit_rows),len(index))

if __name__=='__main__':main()
