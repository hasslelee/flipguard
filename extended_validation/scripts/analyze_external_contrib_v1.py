#!/usr/bin/env python3
"""Reconstruct both official-native and common exact-logit Bank outcomes."""
import argparse,collections,csv,math
import numpy as np
from run_fg_contrib_v1 import ROOT,RUN,read,write,literal_id,sha
from analyze_fg_contrib_v1 import trial_metrics,security,check,verdict,model_reference,csvout,DOC,compare_values
from analyze_contrib_timing import summarize

OUT=RUN/'external/hediff_bank'
def split_check(lock):
 train=lock['training_indices_original'];test=lock['test_indices_original']
 check(len(train)==len(set(train))==lock['training_count'],'external unique training rows')
 check(len(test)==len(set(test))==lock['test_count'],'external unique test rows')
 check(not(set(train)&set(test)),'external train/test row overlap')
 seen=set();roles={}
 for role,n in [('configuration_selection',16),('independent_evaluation',32),('development',128)]:
  rows=list(csv.DictReader((OUT/(role+'.csv')).open()));ids=[int(v['source_row_id']) for v in rows];positions=lock['roles'][role]['test_positions']
  check(len(rows)==len(set(ids))==n,'external role input count')
  check(ids==lock['roles'][role]['original_rows']==[test[p] for p in positions],'external original row mapping')
  check([int(v['row_id']) for v in rows]==[len(train)+p for p in positions],'external resampled test position mapping')
  check(not(seen&set(ids)) and not(set(train)&set(ids)),'external role overlap');seen.update(ids);roles[role]=len(ids)
 return dict(training_rows=len(train),test_rows=len(test),roles=roles,row_sets_disjoint=True,full_source_preprocessing_before_split=True,leakage_free_generalization_claim=False)
def public_context_check(p):
 check(p['status'] in ['READ','API_UNAVAILABLE'],'unexpected public context measurement state')
 check(p['public_metadata_only'] is True and p['introspection_ms']>=0,'public metadata scope/timing')
 if p['status']=='API_UNAVAILABLE':
  check(bool(p['reason']),'unavailable metadata needs reason');return p
 q=p['key_moduli'];d=p['data_moduli'];n=p['poly_modulus_degree']
 check(n==8192 and p['parameters_set'] and '128' in p['security_qualifier'],'original public admission')
 check([v.bit_length() for v in q]==[31,26,26,26,26,26,26,31] and d==q[:-1],'original actual modulus vector')
 check(len(set(q))==len(q) and all(v%(2*n)==1 for v in q),'original NTT moduli')
 check(math.prod(q).bit_length()==p['key_total_modulus_bits'] and math.prod(d).bit_length()==p['data_total_modulus_bits'],'original modulus product bits')
 return p
def stress_feature_validity():
 # Diagnose the predeclared normalized box without changing the generated set.
 # Integer source columns remain a real-data constraint even after normalization.
 src=ROOT/'work/fg_contrib_v1_20260906/external_data/bank-additional-full.csv'
 binding=read(OUT/'PREPROCESSING_FEATURE_RANGES.json');cols=binding['columns'];cats=set(binding['categorical_frozen']);ranges={int(k):v for k,v in binding['ranges'].items()}
 if src.exists():
  import hashlib
  check(hashlib.sha256(src.read_bytes()).hexdigest()==binding['source_sha256'],'public source digest')
  raw=list(csv.DictReader(src.open(),delimiter=';'));raw=[r for r in raw if all(v!='unknown' for v in r.values())]
  for i,want in ranges.items():
   x=np.asarray([float(r[cols[i]]) for r in raw],dtype=np.float32);have=[float(x.min()),float(x.max()),bool(np.all(x==np.rint(x)))];check(have==want,'preprocessing range recomputation')
 parents=list(csv.DictReader((OUT/'independent_evaluation.csv').open()))[:16];stress=list(csv.DictReader((OUT/'stress.csv').open()));check(len(parents)==len(stress)==16,'stress parent count');records=[]
 for p,s in zip(parents,stress):
  check(p['source_row_id']==s['source_row_id'] and p['row_id']==s['row_id'],'stress parent identity');x=np.array([float(s[f'x_{i}']) for i in range(20)]);x0=np.array([float(p[f'x_{i}']) for i in range(20)]);viol=[]
  for i,(lo,hi,integer) in ranges.items():
   if integer:
    restored=lo+x[i]*(hi-lo);tol=4*np.finfo(np.float32).eps*max(1,abs(lo),abs(hi),hi-lo)
    if abs(restored-round(restored))>tol:viol.append(cols[i])
  records.append(dict(row_id=int(s['row_id']),source_row_id=int(s['source_row_id']),normalized_box_valid=bool(np.all((x>=0)&(x<=1))),radius_valid=bool(np.max(abs(x-x0))<=.05+1e-12),categories_unchanged=bool(np.array_equal(x[list(cats)],x0[list(cats)])),integer_source_constraints_violated=viol,integer_constraints_valid=not viol,synthetic_truth_known=False))
 return dict(status='CHECKED_WITH_BOUND_PREPROCESSING_RANGES_NO_RETUNING',records=records,inputs=16,integer_valid_inputs=sum(r['integer_constraints_valid'] for r in records),integer_relaxed_inputs=sum(not r['integer_constraints_valid'] for r in records),joint_real_customer_feasibility='not established, including rows satisfying individual coordinate constraints',interpretation='Any fractional source-count inputs are numerical box diagnostics, not valid-customer counterexamples. All rows remain reported; no favourable validity filtering.')
def analyze():
 result=dict(status='NOT_EXECUTED',original_native=[],selection=[],audit=[],stress=[],timing=[],input_observations=[],input_comparisons=[],no_original_weights=True,synthetic_labels_known=False,same_security_policy_across_backends=False,cross_backend_latency_causal_claim=False)
 if not (OUT/'TRAINING_COMPLETE.json').exists():
  result['blocking_records']=[str(p.relative_to(ROOT)) for p in OUT.glob('*BLOCKED*.json')];return result
 lock=read(OUT/'INPUT_MODEL_LOCK.json');c=dict(case_id='hediff_bank',kind='multiclass',model=str(OUT/'model.json'),thresholds=lock['numeric_thresholds'])
 for filename,h in lock['files'].items():check(sha(OUT/filename)==h,'external input/model binding: '+filename)
 result['training']=read(OUT/'TRAINING_COMPLETE.json');result['input_model_binding']=str((OUT/'INPUT_MODEL_LOCK.json').relative_to(ROOT));result['input_separation']=split_check(lock)
 result['stress_feature_validity']=stress_feature_validity()
 for stage,filename in [('selection','configuration_selection'),('audit','independent_evaluation'),('stress','stress')]:
  refs=model_reference(c,OUT/(filename+'.csv'),stage)
  source_rows={'bank_test_'+v['row_id']:int(v['source_row_id']) for v in csv.DictReader((OUT/(filename+'.csv')).open())}
  for keyfile in sorted((OUT/'native'/stage).glob('key_*.json')):
   ev=read(keyfile);rows=[];eq2_original=eq2_common=0;all_original=all_common=0;numeric=0.;sq=[];differences=[];plain_classes={};seen=set()
   check(ev['model_sha256']==sha(OUT/'model.json'),'official native model digest')
   for r in ev['records']:
    sid='bank_test_'+str(r['row_id']);check(sid in refs and sid not in seen,'native identity');seen.add(sid);p,y=refs[sid];a=np.array(r['ckks_logits']);fp=np.array(r['original_float32_logits']);common=np.array(r['common_float64_logits']);check(np.allclose(p,common,atol=1e-10,rtol=1e-10),'native common logits')
    v=verdict(common,a);rows.append(v);pred=int(common.argmax());enc=int(a.argmax());po=int(fp.argmax());orig_enc=int(a.astype(np.float32).argmax());plain_classes[sid]=(pred,y,po);differences.append(float(abs(fp-common).max()))
    check(v['flip']==r['all_common_disagreement'],'native flip');all_common+=v['flip'];all_original+=int(po!=orig_enc)
    if stage!='stress':
     e1=po==y and po!=orig_enc;e2=pred==y and pred!=enc;check(e1==r['hediff_eq2_original'] and e2==r['hediff_eq2_common'],'Eq2 reconstruction');eq2_original+=e1;eq2_common+=e2
    result['input_observations'].append(dict(v,stage=stage,method='official_TenSEAL',sample_id=sid,source_row_id=source_rows[sid],key=ev['key'],context_id=str(keyfile.relative_to(ROOT)),literal_id=None,original_plain_class=po,original_rounded_encrypted_class=orig_enc,hediff_eq2_original=e1 if stage!='stress' else None,hediff_eq2_common=e2 if stage!='stress' else None,plaintext_correct=pred==y if stage!='stress' else None,numeric_pointwise_pass=v['max_abs']<=c['thresholds']['max_abs']))
    numeric=max(numeric,v['max_abs']);sq.append(v['mse'])
   check(len(seen)==len(refs),'native input denominator')
   result['original_native'].append(dict(stage=stage,key=ev['key'],unique_inputs=len(rows),applicable=sum(v['applicable'] for v in rows),boundary=sum(not v['applicable'] for v in rows),all_common_flip_events=all_common,all_original_HEDiff_rounded_flip_events=all_original,applicable_flip_events=sum(v['protected_flip'] for v in rows),boundary_flip_events=sum(v['flip'] and not v['applicable'] for v in rows),applicable_error_violations=sum(v['protected_error_violation'] for v in rows),hediff_eq2_original=eq2_original if stage!='stress' else None,hediff_eq2_common=eq2_common if stage!='stress' else None,eq2_original_denominator=sum(po==y for pred,y,po in plain_classes.values()) if stage!='stress' else None,eq2_common_denominator=sum(pred==y for pred,y,po in plain_classes.values()) if stage!='stress' else None,max_abs_logit_error=numeric,rmse_logit_error=math.sqrt(np.mean(sq)),numeric_max_pass=numeric<=c['thresholds']['max_abs'],numeric_rmse_pass=math.sqrt(np.mean(sq))<=c['thresholds']['rmse'],proposal_pass=bool(sum(v['applicable'] for v in rows)) and not any(v['protected_flip'] or v['protected_error_violation'] for v in rows),original_float32_to_common_float64_max_difference=max(differences),original_to_common_argmax_differences=sum(pred!=po for pred,y,po in plain_classes.values()),setup_ms=ev['setup_ms'],pdf_inference_ms_sum=sum(r['pdf_inference_ms'] for r in ev['records']),encode_encrypt_ms_sum=sum(r['encode_encrypt_ms'] for r in ev['records']),he_ms_sum=sum(r['he_ms'] for r in ev['records']),decrypt_decode_ms_sum=sum(r['decrypt_decode_ms'] for r in ev['records']),raw=str(keyfile.relative_to(ROOT)),implementation='official BankMLP_TS forward at pinned commit, public-procedure retrained weights, official native parameter bits preserved',original_own_condition='native default SEAL128 admission; original public settings do not implement our decision acceptance; own numerical selection condition not claimed'))
   native_row=result['original_native'][-1];native_row['configuration']=ev['config'];native_row['runtime_parameters']=public_context_check(ev['runtime_parameters'])
   native_row['original_float32_accuracy']=sum(po==y for pred,y,po in plain_classes.values())/len(plain_classes) if stage!='stress' else None
   native_row['common_float64_accuracy']=sum(pred==y for pred,y,po in plain_classes.values())/len(plain_classes) if stage!='stress' else None
 for role in ['B','C','A']:
  p=OUT/'selection'/role/'result.json'
  if not p.exists():continue
  r=read(p);metrics=[];accepted=[]
  for trial in sorted(p.parent.glob('trial_*/trial.json')):
   t=read(trial);security(t['candidate']);m,observations=trial_metrics(c,trial.parent,'selection',OUT/'configuration_selection.csv');check((t['status']=='SAFE')==m['proposal_pass'],'common native acceptance');metrics.append(m)
   result['input_observations'] += [dict(v,method=role,literal_id=literal_id(t['candidate']),hediff_eq2_common=v['plaintext_correct'] and v['flip']) for v in observations]
   if m['numeric_max_pass'] if role=='A' else m['proposal_pass']:accepted.append(t)
  check(bool(accepted)==bool(r['selected']),'common selection outcome')
  if accepted:check(accepted[0]['candidate']['parameters']==r['selected']['parameters'],'first acceptance')
  if (OUT/'FROZEN_SELECTION.json').exists():check(read(OUT/'FROZEN_SELECTION.json')['roles'][role]==r['selected'],'external frozen choice differs from actual selection')
  command_end=RUN/'commands'/f'external_select_{role}.end.json'
  result['selection'].append(dict(role=role,outcome=r['outcome'],candidate=r['selected'],actual_candidates=r['actual_encrypted_candidates'],wall_ms=r['wall_ms'],command_wall_ms=read(command_end)['wall_seconds']*1000 if command_end.exists() else None,analysis_ms=r['analysis_ms'],trial_metrics=metrics,raw=str(p.relative_to(ROOT))))
 for stage,filename in [('audit','independent_evaluation'),('stress','stress')]:
  for p in sorted((OUT/stage).glob('*/result.json')):
   candidate=read(p)['candidate'];security(candidate);check(literal_id(candidate)==p.parent.name,'external audit/stress configuration binding')
   check(candidate['parameters']==read(OUT/'FROZEN_SELECTION.json')['unique'][p.parent.name]['candidate']['parameters'],'external audit/stress differs from frozen choice')
   m,rows=trial_metrics(c,p.parent,stage,OUT/(filename+'.csv'));m['literal_id']=p.parent.name
   aliases='/'.join(read(OUT/'FROZEN_SELECTION.json')['unique'][p.parent.name]['roles'])
   source_rows={'bank_test_'+v['row_id']:int(v['source_row_id']) for v in csv.DictReader((OUT/(filename+'.csv')).open())}
   result['input_observations'] += [dict(v,method=aliases,literal_id=p.parent.name,source_row_id=source_rows[v['sample_id']],hediff_eq2_common=v['plaintext_correct'] and v['flip'] if stage!='stress' else None) for v in rows]
   m['eq2_common_events']=sum(r['plaintext_correct'] and r['flip'] for r in rows) if stage!='stress' else None;m['eq2_common_observation_denominator']=sum(r['plaintext_correct'] for r in rows) if stage!='stress' else None
   result[stage].append(m)
 if (OUT/'FROZEN_SELECTION.json').exists():
  frozen=read(OUT/'FROZEN_SELECTION.json');ref=frozen['roles'].get('C')
  if ref:
   for p in sorted((OUT/'timing').glob('*/key_*/result.json')):
    expected={'reference_C':ref,'comparator':frozen['unique'][p.parent.parent.name]['candidate']}
    b,_=summarize(p,'hediff_bank',literal_id(ref),p.parent.parent.name,int(p.parent.name.split('_')[1]),expected);result['timing'].append(b)
 result['status']='SCHEDULE_EXHAUSTED_CHECK_FAILURES' if (OUT/'EXTERNAL_COMPLETED.json').exists() else 'PARTIAL'
 result['blocking_records']=[str(p.relative_to(ROOT)) for p in OUT.glob('*BLOCKED*.json')]
 result['execution_failures']=[str(p.relative_to(ROOT)) for p in (RUN/'commands').glob('external_*.end.json') if read(p)['exit_code']!=0]
 result['thresholds']=c['thresholds'];result['original_reference_scope']='original float32 model vs common float64 exact polynomial vs CKKS; algebraic adapter rounding separately checked; no activation approximation'
 groups=collections.defaultdict(list)
 for v in result['input_observations']:
  if v['stage'] in ['audit','stress']:groups[(v['stage'],v['sample_id'])].append(v)
 for (stage,sid),rows in sorted(groups.items()):
  check(all(v['source_row_id']==rows[0]['source_row_id'] and v['applicable']==rows[0]['applicable'] and math.isclose(v['margin'],rows[0]['margin'],abs_tol=1e-10,rel_tol=1e-10) for v in rows),'external common input and application scope mismatch')
  native=[v for v in rows if v['method']=='official_TenSEAL'];cc=[v for v in rows if 'C' in v['method'].split('/')];ab=[v for v in rows if any(k in v['method'].split('/') for k in ['A','B'])]
  result['input_comparisons'].append(dict(stage=stage,sample_id=sid,source_row_id=rows[0]['source_row_id'],margin=rows[0]['margin'],applicable=rows[0]['applicable'],**{name+suffix:(sum(v[field] for v in vv) if vv else None) for name,vv in [('official_native',native),('A_B',ab),('C',cc)] for suffix,field in [('_flip_events','flip'),('_error_events','protected_error_violation')]},native_eq2_events=sum(v['hediff_eq2_original'] for v in native) if native and stage!='stress' else None,method_key_observations={method:sum(v['method']==method for v in rows) for method in sorted({v['method'] for v in rows})},synthetic_truth_known=False if stage=='stress' else None))
 return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');p.add_argument('--check',action='store_true');a=p.parse_args();check(not(a.write and a.check),'choose write or check');r=analyze()
 if a.write:
  write(DOC/'EXTERNAL_RESULTS.json',r)
  for k in ['original_native','selection','audit','stress','timing','input_observations','input_comparisons']:csvout(DOC/('EXTERNAL_'+k.upper()+'.csv'),r[k])
 if a.check:compare_values(read(DOC/'EXTERNAL_RESULTS.json'),r);print('external independent recomputation matches stored results')
 print(r['status'])
if __name__=='__main__':main()
