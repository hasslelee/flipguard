#!/usr/bin/env python3
"""Plaintext-only retrospective cause analysis. No HE, training, subprocess or network.
Writes exclusively to a new cause pack. Future audit identities never enter forward().
"""
import argparse, collections, csv, hashlib, io, json, math, sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'docs/research/fg_contrib_v1_20260906'
RUN=ROOT/'results/fg_contrib_v1_20260906_run01'
BANK=RUN/'external/hediff_bank'
DOC=ROOT/'docs/research/fg_cause_v1_20260906'
NEW=ROOT/'results/fg_cause_v1_20260906_run01'
BIND={}
def path(p):
 p=Path(p);return p if p.is_absolute() else ROOT/p
def payload(p):
 p=path(p);b=p.read_bytes();BIND[str(p.relative_to(ROOT))]=hashlib.sha256(b).hexdigest();return b
def read(p):return json.loads(payload(p))
def rows(p,delimiter=','):return list(csv.DictReader(io.StringIO(payload(p).decode()),delimiter=delimiter))
def serial(v):
 if isinstance(v,np.generic):return v.item()
 if isinstance(v,np.ndarray):return v.tolist()
 raise TypeError(type(v))
def emit(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2,ensure_ascii=False,allow_nan=False,default=serial);f.write('\n')
def table(name,data):
 assert data,name
 with (DOC/name).open('x',newline='') as f:
  fields=list(dict.fromkeys(k for r in data for k in r));w=csv.DictWriter(f,fields,lineterminator='\n');w.writeheader()
  for r in data:w.writerow({k:json.dumps(v,ensure_ascii=False,default=serial,allow_nan=False) if isinstance(v,(list,dict,np.ndarray)) else serial(v) if isinstance(v,np.generic) else v for k,v in r.items()})
def verdict(p,a):
 p=np.asarray(p,float);a=np.asarray(a,float);assert p.shape==a.shape and np.isfinite(p).all() and np.isfinite(a).all();e=abs(a-p)
 if len(p)==1:
  gap=abs(p[0]-.5);pred=int(p[0]>=.5);flip=pred!=int(a[0]>=.5);usage=float(e[0]/(.5*gap)) if gap else None;slack=.5*gap-e[0]
 else:
  pred=int(p.argmax());js=np.arange(len(p))!=pred;gap=p[pred]-max(p[js]);bud=.5*(p[pred]-p[js]);err=e[pred]+e[js];usage=float(max(err/bud)) if min(bud)>0 else None;slack=min(bud-err);flip=pred!=int(a.argmax())
 return dict(margin=float(gap),applicable=bool(gap>.001),flip=bool(flip),violation=bool(slack<=0),max_usage=usage,slack=float(slack),max_abs=float(e.max()),mse=float(np.mean(e*e)))
def actual_records(k,kind):
 if kind=='multiclass':return [(str(r['sample_id']),r['plaintext_logits'],r['ckks_logits']) for r in k['records']]
 return [(str(r['RowID']),[r['PlainY']],[r['CKKSY']]) for r in k['records']]
def trial(row,kind,tau):
 folder=path(row['raw']);cp=folder/('trial.json' if (folder/'trial.json').exists() else 'result.json');cand=read(cp)['candidate'];vv=[];cost=[];perkey=[]
 for f in sorted(folder.glob('key_*.json')):
  k=read(f);vs=[verdict(p,a) for _,p,a in actual_records(k,kind)];vv+=vs;perkey.append(dict(key=k['key_run'],max_abs=max(v['max_abs'] for v in vs),rmse=math.sqrt(np.mean([v['mse'] for v in vs]))))
  if kind=='multiclass':s=k['summary'];cost.append(s['encode_encrypt_ms']+s['evaluation_only_ms']+s['decrypt_decode_ms'])
  else:cost.append(sum(r['EncodeEncryptMS']+r['EvalOnlyMS']+r['DecryptDecodeMS'] for r in k['records']))
 assert len(perkey)==3
 numeric=all(v['max_abs']<=tau for v in perkey);app=[v for v in vv if v['applicable']];proposal=bool(app) and not any(v['flip'] or v['violation'] for v in app)
 assert numeric==(row['numeric_max_pass']=='True') and proposal==(row['proposal_pass']=='True')
 assert sum(v['flip'] for v in app)==int(row['protected_flip_events']) and sum(v['violation'] for v in app)==int(row['protected_error_events'])
 assert math.isclose(max(v['max_abs'] for v in vv),float(row['max_abs']),rel_tol=1e-10,abs_tol=1e-12)
 par=cand['parameters'];cost0=json.loads(row['cost']);assert math.isclose(sum(cost),cost0['pdf_inference_ms'],rel_tol=1e-9)
 return dict(case_id=row['case_id'],stage=row['stage'],raw=row['raw'],literal_id=row['literal_id'],candidate_id=cand['id'],path=cand['path'],scale=par['log_default_scale'],log_n=par['log_n'],q_count=len(par['log_q']),p_count=len(par['log_p']),log_q=par['log_q'],log_p=par['log_p'],qp=sum(par['log_q'])+sum(par['log_p']),inputs=int(row['unique_inputs']),applicable=int(row['applicable']),key_contexts=3,numeric_pass=numeric,proposal_pass=proposal,max_abs=max(v['max_abs'] for v in vv),max_budget_usage=max(v['max_usage'] for v in app) if app else None,min_error_slack=min(v['slack'] for v in app) if app else None,protected_flips=sum(v['flip'] for v in app),protected_violations=sum(v['violation'] for v in app),pdf_ms_sum=sum(cost),pdf_ms_per_key_batch=sum(cost)/3,security_pass=cand['security']['final_admission']=='PASS')
def synth(cid,plan,selected):
 c=plan['contract'];d=c.get('multiclass_decision') or c['decision'];cal=c['calibration'];budget=d.get('per_logit_error_budget',d.get('output_error_budget'));u=budget/cal['aggregate_sensitivity'];p=max(0,math.ceil(-math.log2(u)));initial=plan['initial_candidates'][0];par=initial['parameters'];assert p==initial['precision_target_bits']
 return dict(case_id=cid,protected_margin=d.get('protected_top_two_gap',d.get('protected_margin')),output_budget=budget,aggregate_sensitivity=cal['aggregate_sensitivity'],unit_budget=u,precision_bits=p,guard=plan['policy']['scale_guard_bits'],floor=plan['policy']['min_scale_bits'],analysis_scale=initial['analysis_scale_bits'],backend_lift=initial['backend_scale_lift_bits'],initial_scale=par['log_default_scale'],message_bits=initial['message_magnitude_bits'],max_output_abs=cal['max_plaintext_output_abs'],q=par['log_q'],p=par['log_p'],qp=sum(par['log_q'])+sum(par['log_p']),initial_log_n=par['log_n'],selected_parameters=selected,precision_slack_mode=plan['policy']['precision_slack_mode'],initial_reason=initial['reason'])
def analyze_internal():
 spec=read('protocols/FG_CONTRIB_V1.json');sr=rows(OLD/'SELECTION_RUNS.csv');tm=rows(OLD/'TRIAL_METRICS.csv');dg=rows(OLD/'DIAGNOSTIC.csv');candidates=[];logic=[];synthesis=[]
 for c in spec['cases']:
  cid=c['case_id'];tau=c['thresholds']['max_abs'];rr=[r for r in tm if r['case_id']==cid];tt=[trial(r,c['kind'],tau) for r in rr];candidates+=tt
  key=read(path(rr[0]['raw'])/'key_1.json');pp=actual_records(key,c['kind']);m=[verdict(p,p)['margin'] for _,p,_ in pp];ap=[g for g in m if g>.001];factor=1 if c['kind']=='tabular' else 2
  starts={}
  for start in (30,40):
   aa=[r for r in sr if r['case_id']==cid and r['role']=='A'+str(start)];bb=[r for r in sr if r['case_id']==cid and r['role']=='B'+str(start)];assert len(aa)==len(bb)==2
   starts[str(start)]=dict(same_choices=sum(a['literal_id']==b['literal_id'] for a,b in zip(aa,bb)),both_first=sum(a['encrypted_candidates']==b['encrypted_candidates']=='1' for a,b in zip(aa,bb)))
  differential=[t for t in tt if t['stage']=='diagnostic' and t['numeric_pass']!=t['proposal_pass']]
  logic.append(dict(case_id=cid,kind=c['kind'],tau_max=tau,tau_rmse=c['thresholds']['rmse'],delta=.001,rho=.5,pointwise_error_factor=factor,global_numeric_implies_margin=(factor*tau<=.0005),selection_min_app_margin=min(ap),selection_numeric_implies_margin=(factor*tau<.5*min(ap)),selection_inputs=len(m),selection_applicable=len(ap),selection_boundary=len(m)-len(ap),keys_each=3,primary_max_over='all input outputs per key; all3 keys',same_starts=starts,different_diagnostic_acceptance=len(differential),different_candidates=[dict(scale=t['scale'],numeric=t['numeric_pass'],proposal=t['proposal_pass']) for t in differential],numeric_pass_proposal_fail=sum(t['numeric_pass'] and not t['proposal_pass'] for t in tt),rmse_to_max_bound=math.sqrt(len(m)*(1 if c['kind']=='tabular' else 10))*c['thresholds']['rmse'],rmse_bound_implies_selection_condition=(factor*math.sqrt(len(m)*(1 if c['kind']=='tabular' else 10))*c['thresholds']['rmse']<.5*min(ap))))
  plan=read(RUN/'cases'/cid/'selection/block_0/C/analysis.json')['plan'];selected=json.loads(next(r for r in sr if r['case_id']==cid and r['block']=='0' and r['role']=='C')['parameters']);synthesis.append(synth(cid,plan,selected))
 table('AB_RELATIONS.csv',logic);table('CANDIDATE_RECONSTRUCTION.csv',candidates)
 # All existing evaluated candidates, no test/stress evidence used to rank alternatives.
 alternatives=[]
 for c in spec['cases']:
  cid=c['case_id'];tt=[v for v in candidates if v['case_id']==cid];refid=next(r['literal_id'] for r in sr if r['case_id']==cid and r['block']=='0' and r['role']=='C');refs=[t for t in tt if t['literal_id']==refid];ref=refs[0];rusage=max(t['max_budget_usage'] for t in refs);rtime=float(np.mean([t['pdf_ms_per_key_batch'] for t in refs]));seen={}
  for t in tt:seen.setdefault(t['literal_id'],[]).append(t)
  for lid,gg in seen.items():
   t=gg[0];allpass=all(v['proposal_pass'] for v in gg);usage=max(v['max_budget_usage'] for v in gg);ptime=float(np.mean([v['pdf_ms_per_key_batch'] for v in gg]));tier=(t['log_n'],t['q_count'],t['p_count'],t['path']);rtier=(ref['log_n'],ref['q_count'],ref['p_count'],ref['path']);cheaper=(t['log_n']<ref['log_n'] and t['q_count']<=ref['q_count'] and t['p_count']<=ref['p_count']) or (t['log_n']==ref['log_n'] and t['q_count']<ref['q_count'] and t['p_count']<=ref['p_count']);same=tier==rtier
   alternatives.append(dict(case_id=cid,literal_id=lid,is_C=lid==refid,parameters=dict(log_n=t['log_n'],scale=t['scale'],q=t['log_q'],p=t['log_p']),observed_executions=len(gg),keys_total=3*len(gg),all_observed_proposal_pass=allpass,all_numeric_pass=all(v['numeric_pass'] for v in gg),max_budget_usage=usage,C_max_budget_usage=rusage,same_structural_tier=same,lower_structural_tier=cheaper,larger_observed_error_slack=usage<rusage,mean_pdf_ms_per_key_batch=ptime,C_mean_pdf_ms_per_key_batch=rtime,observed_ratio_candidate_over_C=ptime/rtime,cheaper_passing_alternative=lid!=refid and allpass and cheaper and ptime<rtime,same_tier_more_slack=lid!=refid and allpass and same and usage<rusage,evidence=[v['raw'] for v in gg],scope='posthoc observed selection inputs; mixed selection/diagnostic times, not paired latency or new selector'))
 table('OBSERVED_ALTERNATIVES.csv',alternatives)
 return dict(logic=logic,synthesis=synthesis,alternatives=alternatives,verified_trials=len(candidates),diagnostic_declared=len(dg),diagnostic_executed=sum(r['executed']=='True' for r in dg))

def analyze_bank():
 model=read(BANK/'model.json');lock=read(BANK/'INPUT_MODEL_LOCK.json');poollock=read(NEW/'INPUT_POOL_LOCK.json');protocol=read('protocols/FG_CAUSE_V1_20260906.json');assert poollock['protocol_sha256']==hashlib.sha256(payload('protocols/FG_CAUSE_V1_20260906.json')).hexdigest()
 W=np.array(model['original_w1']);b=np.array(model['original_b1']);V=np.array(model['original_w2']);d=np.array(model['original_b2']);cats=[1,2,3,4,5,6,7,8,9,14];reserved={r['source_row_id'] for r in poollock['future_audit_reserve']};called=[]
 def forward(X,ids):
  assert not (set(map(int,ids))&reserved),'audit reserve entered plaintext forward'
  called.extend(map(int,ids));h=X@W.T+b;a=h*h+h;z=a@V.T+d;shift=h+.5;grad=((2*h+1)*(V[0]-V[1]))@W
  return h,a,z,shift,grad
 stages={};inputrows=[];ranges=[]
 for stage,name in [('selection','configuration_selection'),('development','development'),('audit','independent_evaluation'),('stress','stress')]:
  rr=rows(BANK/(name+'.csv'));X=np.array([[float(r[f'x_{j}']) for j in range(20)] for r in rr]);ids=[int(r['source_row_id']) for r in rr];h,a,z,shift,grad=forward(X,ids);stages[stage]=dict(rows=rr,X=X,h=h,a=a,z=z,shift=shift,grad=grad)
 sel=stages['selection'];n2=max(np.sum(abs(V),axis=1))
 def features(stage,rr,X,h,a,z,shift,grad):
  result=[]
  for i,r in enumerate(rr):
   gap=abs(z[i,0]-z[i,1]);src=int(r['source_row_id']);parent='bank_test_'+r['row_id'];v=dict(stage=stage,sample_id=parent,source_row_id=src,parent_sample_id=parent if stage=='stress' else None,synthetic=stage=='stress',synthetic_truth_known=False if stage=='stress' else None,plain0=z[i,0],plain1=z[i,1],margin=gap,applicable=gap>.001,input_min=X[i].min(),input_max=X[i].max(),hidden_pre_min=h[i].min(),hidden_pre_max=h[i].max(),shifted_hidden_maxabs=abs(shift[i]).max(),activation_min=a[i].min(),activation_max=a[i].max(),output_maxabs=abs(z[i]).max(),gap_gradient_l1=sum(abs(grad[i])),gap_mutable_gradient_l1=sum(abs(grad[i][[j for j in range(20) if j not in cats]])),rowwise_primitive_sensitivity=512+n2+n2*2*abs(shift[i]).max()*40,features_outside_selection_interval=int(np.sum((X[i]<sel['X'].min(axis=0)-1e-12)|(X[i]>sel['X'].max(axis=0)+1e-12))),hidden_units_outside_selection_interval=int(np.sum((shift[i]<sel['shift'].min(axis=0)-1e-12)|(shift[i]>sel['shift'].max(axis=0)+1e-12))),exceeds_selection_global_shifted_max=bool(abs(shift[i]).max()>abs(sel['shift']).max()),input_vector=X[i].tolist())
   result.append(v)
  return result
 for stage,t in stages.items():
  rr=features(stage,t["rows"],t["X"],t["h"],t["a"],t["z"],t["shift"],t["grad"]);inputrows+=rr
  for j in range(20):ranges.append(dict(stage=stage,feature=j,min=float(t['X'][:,j].min()),max=float(t['X'][:,j].max()),categorical=j in cats))
 # Reconstruct existing full-source preprocessing metadata; do not rerun NearMiss.
 source=rows('work/fg_contrib_v1_20260906/external_data/bank-additional-full.csv',delimiter=';');cols=list(source[0])[:-1];complete=[(i,r) for i,r in enumerate(source) if all(v!='unknown' and v!='' for v in r.values())];assert len(complete)==30488
 enc={j:{s:n for n,s in enumerate(sorted({r[cols[j]] for _,r in complete}))} for j in cats};Xraw=np.array([[enc[j][r[cols[j]]] if j in cats else float(r[cols[j]]) for j in range(20)] for _,r in complete],dtype=np.float32);lo=Xraw.min(axis=0);hi=Xraw.max(axis=0);lookup={idx:i for i,(idx,_) in enumerate(complete)}
 def reconstruct(ids):
  assert not (set(ids)&reserved),'reserve feature materialization prohibited'
  xx=Xraw[[lookup[i] for i in ids]];return ((xx-lo)/(hi-lo)).astype(float)
 for stage in ('selection','development','audit'):
  t=stages[stage];xx=reconstruct([int(r['source_row_id']) for r in t['rows']]);assert np.array_equal(xx,t['X']),('normalized mismatch',stage)
 candidate=poollock['candidate_pool'];ids=[r['source_row_id'] for r in candidate];X=reconstruct(ids);hh,aa,zz,ss,gg=forward(X,ids);rr=[dict(row_id=str(r['row_id']),source_row_id=str(r['source_row_id'])) for r in candidate];newrows=features('candidate_pool',rr,X,hh,aa,zz,ss,gg)
 devgap=np.abs(stages['development']['z'][:,0]-stages['development']['z'][:,1]);cuts=np.quantile(devgap,[.25,.5,.75],method='linear');rank=lambda r:(hashlib.sha256(('FG_CAUSE_V1_20260906/select/'+str(r['source_row_id'])).encode()).hexdigest(),r['source_row_id'])
 for r in newrows:r['quartile']=int(np.searchsorted(cuts,r['margin'],side='right'))+1
 uniform=sorted(newrows,key=rank)[:16];groups=[[r for r in newrows if r['quartile']==q] for q in range(1,5)];feasible=all(len(g)>=4 for g in groups);quartile=sum([sorted(g,key=rank)[:4] for g in groups],[]) if feasible else []
 chosen=[]
 for policy,rs in [('original_first16',[r for r in inputrows if r['stage']=='selection']),('uniform_hash16',uniform),('development_quartile4x4',quartile)]:
  for r in rs:chosen.append(dict(policy=policy,source_row_id=r['source_row_id'],sample_id=r['sample_id'],margin=r['margin'],applicable=r['applicable'],quartile=int(np.searchsorted(cuts,r['margin'],side='right'))+1,rank_hash=rank(r)[0],gap_gradient_l1=r['gap_gradient_l1'],shifted_hidden_maxabs=r['shifted_hidden_maxabs']))
 table('BANK_INPUT_PLAINTEXT.csv',inputrows);table('BANK_FEATURE_RANGES.csv',ranges);table('BANK_CANDIDATE_POOL.csv',newrows);table('BANK_PLAINTEXT_SELECTIONS.csv',chosen)
 # Raw key outputs, all methods/stages/inputs, not only selected failures.
 obs=[];rawjobs=[]
 for method in ('A','B','C'):
  for f in sorted((BANK/'selection'/method/'trial_1').glob('key_*.json')):rawjobs.append(('selection',method,f,False))
 for stage in ('audit','stress'):
  for f in sorted((BANK/stage).glob('*/key_*.json')):rawjobs.append((stage,'C' if f.parent.name=='ac9dc140d8f56b6f' else 'A/B',f,False))
 for stage in ('selection','audit','stress'):
  for f in sorted((BANK/'native'/stage).glob('key_*.json')):rawjobs.append((stage,'official_TenSEAL',f,True))
 for stage,method,f,native in rawjobs:
  k=read(f);t=stages[stage];refs={int(r['row_id']):(i,r) for i,r in enumerate(t['rows'])}
  for r in k['records']:
   i,src=refs[int(r['row_id'])];p=np.array(r['common_float64_logits'] if native else r['plaintext_logits']);a=np.array(r['ckks_logits']);assert np.allclose(p,t['z'][i],atol=1e-10,rtol=1e-10);v=verdict(p,a);signed=a-p;winner=int(p.argmax());other=1-winner;perturb=signed[winner]-signed[other];hegap=a[winner]-a[other];assert v['flip']==bool(hegap<0) or hegap==0
   obs.append(dict(stage=stage,method=method,sample_id='bank_test_'+str(r['row_id']),source_row_id=int(src['source_row_id']),parent_sample_id='bank_test_'+str(r['row_id']) if stage=='stress' else None,key=k['key'] if native else k['key_run'],raw=str(f.relative_to(ROOT)),plain0=p[0],plain1=p[1],ckks0=a[0],ckks1=a[1],signed_error0=signed[0],signed_error1=signed[1],abs_error0=abs(signed[0]),abs_error1=abs(signed[1]),pair_error_sum=sum(abs(signed)),pair_budget=.5*v['margin'],common_mode_error=float(np.mean(signed)),winner_gap_error=perturb,encrypted_winner_gap=hegap,numeric_pointwise_pass=max(abs(signed))<=lock['numeric_thresholds']['max_abs'],synthetic_truth_known=False if stage=='stress' else None,**v))
 table('BANK_CLASS_ERRORS.csv',obs)
 # Validate preserved event totals without calling the old experiment drivers.
 cc=[r for r in obs if r['method']=='C' and r['stage']=='stress'];assert sum(r['flip'] for r in cc)==1 and sum(r['violation'] and r['applicable'] for r in cc)==6
 assert len({r['sample_id'] for r in cc if r['violation']})==3
 summary=[]
 for stage in stages:
  rr=[r for r in inputrows if r['stage']==stage];m=np.array([r['margin'] for r in rr]);summary.append(dict(stage=stage,inputs=len(rr),min_margin=m.min(),quartiles=np.quantile(m,[.25,.5,.75]),max_margin=m.max(),applicable=sum(r['applicable'] for r in rr),max_shifted_hidden=max(r['shifted_hidden_maxabs'] for r in rr),max_gap_gradient_l1=max(r['gap_gradient_l1'] for r in rr),max_rowwise_primitive_sensitivity=max(r['rowwise_primitive_sensitivity'] for r in rr),rows_exceed_selection_hidden_max=sum(r['exceeds_selection_global_shifted_max'] for r in rr),CKKS_available=stage!='development'))
 for method in ('A','B','A/B','C','official_TenSEAL'):
  for stage in ('selection','audit','stress'):
   vv=[r for r in obs if r['method']==method and r['stage']==stage]
   if vv:summary.append(dict(stage=stage,method=method,inputs=len({r['sample_id'] for r in vv}),key_observations=len(vv),flip_events=sum(r['flip'] for r in vv),condition_violations=sum(r['violation'] and r['applicable'] for r in vv),max_pair_error_sum=max(r['pair_error_sum'] for r in vv),max_budget_usage=max(r['max_usage'] for r in vv)))
 table('BANK_STAGE_SUMMARY.csv',summary)
 coverage=[]
 for policy,rs in [('candidate_pool',newrows),('original_first16',[r for r in inputrows if r['stage']=='selection']),('uniform_hash16',uniform),('development_quartile4x4',quartile)]:
  if not rs:continue
  margins=np.array([r['margin'] for r in rs]);coverage.append(dict(policy=policy,inputs=len(rs),min_margin=margins.min(),max_margin=margins.max(),quartiles=np.quantile(margins,[.25,.5,.75]),development_bin_counts=[sum(int(np.searchsorted(cuts,r['margin'],side='right'))==q for r in rs) for q in range(4)],boundary=sum(margins<=.001),below_original_min=sum(margins<min(abs(sel['z'][:,0]-sel['z'][:,1]))),at_or_below_smallest_failed_stress_margin=sum(margins<=.0116961255746172),below_point1=sum(margins<.1),max_shifted_hidden=max(r['shifted_hidden_maxabs'] for r in rs),max_gap_gradient_l1=max(r['gap_gradient_l1'] for r in rs)))
 table('BANK_POLICY_COVERAGE.csv',coverage)
 # Observation-only same-cost alternative: no inference from stress winner to policy.
 ext=read(OLD/'EXTERNAL_RESULTS.json');plan=read(BANK/'planning/plan.json');selected=read(BANK/'selection/C/result.json')['selected']['parameters'];syn=synth('hediff_bank',plan,selected)
 assert math.isclose(syn['aggregate_sensitivity'],max(r['rowwise_primitive_sensitivity'] for r in inputrows if r['stage']=='selection'),rel_tol=1e-12)
 development=dict(permutation_locked=True,source_rows=len(source),complete_cases=len(complete),normalization_validation='bitwise exact on all176 existing selection/development/audit inputs',near_miss_rerun=False,model_retrained=False,full_source_preprocessing_preserved=True,quartile_cuts=cuts.tolist(),candidate_bin_counts=[len(g) for g in groups],quartile_feasible=feasible,candidate_inputs=684,audit_reserved=684,audit_reserve_forward_count=len(set(called)&reserved),model_forward_source_ids=sorted(set(called)),coverage=coverage)
 emit(NEW/'PLAINTEXT_ACCESS_AUDIT.json',development)
 return dict(synthesis=syn,pool=development,stage_summary=summary,failure_rows=[r for r in obs if r['stage']=='stress' and r['method']=='C' and r['violation']],timing=ext['timing'])

def main():
 p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');a=p.parse_args();assert a.write
 assert not (DOC/'ANALYSIS.json').exists(),'analysis pack already exists; never overwrite'
 internal=analyze_internal();bank=analyze_bank();table('SYNTHESIS_PATHS.csv',internal['synthesis']+[bank['synthesis']]);result=dict(protocol='FG_CAUSE_V1_20260906',mode='plaintext and existing raw keys only',internal=internal,bank=bank,new_ckks_calls=0,model_training_calls=0,C_modified=False)
 emit(DOC/'ANALYSIS.json',result);emit(NEW/'READ_BINDINGS.json',dict(files=BIND,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='only actually consumed files; archive never read'))
 print(json.dumps(dict(verified_trials=internal['verified_trials'],new_ckks=0,pool_summary=bank['pool']['coverage'],failure_events=len(bank['failure_rows'])),default=serial,ensure_ascii=False))
if __name__=='__main__':main()
