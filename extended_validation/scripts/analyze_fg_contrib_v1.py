#!/usr/bin/env python3
"""Independent score/decision/error/cost reconstruction; never runs CKKS."""
import argparse, collections, csv, gzip, hashlib, json, math
from pathlib import Path
import numpy as np
import analyze_fg_expand_v1 as old
from analyze_contrib_timing import analyze_timing
from analyze_contrib_stress_inputs import analyze_inputs
from run_fg_contrib_v1 import ROOT,RUN,PROTOCOL,read as native_read,sha,literal_id,write

DOC=ROOT/'docs/research/fg_contrib_v1_20260906'
def resolve_path(p):
 p=Path(p);prefix=Path('/home/ckks2/deciprotect')
 try:return ROOT/p.relative_to(prefix)
 except ValueError:return p

def read(p):return native_read(resolve_path(p))

def compare_values(a,b,path='root'):
 if isinstance(a,dict):
  check(isinstance(b,dict) and a.keys()==b.keys(),('comparison keys',path))
  for k in a:compare_values(a[k],b[k],path+'.'+k)
 elif isinstance(a,list):
  check(isinstance(b,list) and len(a)==len(b),('comparison length',path))
  for i,(x,y) in enumerate(zip(a,b)):compare_values(x,y,path+f'[{i}]')
 elif isinstance(a,float):check(isinstance(b,(int,float)) and near(a,b),('comparison numeric',path,a,b))
 else:check(type(a) is type(b) and a==b,('comparison value',path,a,b))
def check(v,msg):
 if not v:raise AssertionError(msg)
def near(a,b):return math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-9)
def verdict(plain,approx):
 p=np.asarray(plain,float);a=np.asarray(approx,float);check(p.shape==a.shape and np.isfinite(p).all() and np.isfinite(a).all(),'nonfinite or malformed score')
 e=abs(a-p)
 if len(p)==1:
  margin=abs(float(p[0])-.5);covered=margin>.001;flip=bool((p[0]>=.5)!=(a[0]>=.5));violation=bool(e[0]>=.5*margin);pred=int(p[0]>=.5)
  ratio=float(e[0]/(.5*margin)) if margin else None
 else:
  pred=int(p.argmax());ordered=np.sort(p);margin=float(ordered[-1]-ordered[-2]);covered=margin>.001;flip=int(a.argmax())!=pred
  js=np.arange(len(p))!=pred;budgets=.5*(p[pred]-p[js]);errors=e[pred]+e[js]
  violation=bool(np.any(errors>=budgets));ratio=float(np.max(errors/budgets)) if np.all(budgets>0) else None
 return dict(margin=margin,applicable=covered,flip=flip,error_violation=violation,protected_flip=covered and flip,protected_error_violation=covered and violation,max_abs=float(e.max()),mse=float(np.mean(e**2)),budget_usage=ratio,plain_class=pred)
def model_reference(c,data,stage):
 m=read(c['model']);rows=list(csv.DictReader(resolve_path(data).open()));result={}
 if m.get('model_type')=='hediff_bank_exact_two_logit_square_adapter_v1':
  W=np.array(m['original_w1']);b=np.array(m['original_b1']);V=np.array(m['original_w2']);d=np.array(m['original_b2']);X=np.array([[float(r[f'x_{j}']) for j in range(20)] for r in rows]);h=X@W.T+b;Z=(h*h+h)@V.T+d
  for r,z in zip(rows,Z):result['bank_test_'+r['row_id']]=(z,int(r['original_label']))
 elif c['kind']=='multiclass':
  w=np.array(m['parameters']);W=w[:78400].reshape(100,784);b=w[78400:78500];V=w[78500:79500].reshape(10,100);d=w[79500:]
  X=np.array([[int(r[f'pixel_{j:03d}'])/255 for j in range(784)] for r in rows]);Z=(X@W.T+b)**2@V.T+d
  if stage=='stress':rows=rows[:16];Z=Z[:16]
  for r,z in zip(rows,Z):result[r['sample_id']]=(z,int(r['label']))
 else:
  if stage=='stress':raw=RUN/'stress'/c['case_id']/'raw.csv'
  else:raw=resolve_path(c['model']).parent/('configuration_selection.csv' if stage in ['selection','diagnostic','extra'] else 'independent_evaluation.csv')
  rr=list(csv.DictReader(raw.open()));z=old.scores(m,rr)
  for r,v in zip(rr,z):result[str(r['row_id'])]=(np.array([v]),int(r['label']))
 return result
def raw_records(path,kind):
 ev=read(path)
 for r in ev['records']:
  if kind=='multiclass':yield ev['key_run'],str(r['sample_id']),r['plaintext_logits'],r['ckks_logits'],r['label']
  else:yield ev['key_run'],str(r['RowID']),[r['PlainY']],[r['CKKSY']],r['Label']
def cost(path,kind):
 ev=read(path);s=ev['summary']
 if kind=='multiclass':setup=s['crypto_setup_ms'];enc=s['encode_encrypt_ms'];he=s['evaluation_only_ms'];dec=s['decrypt_decode_ms'];native=s['total_ms'];io=s['adapter_io_ms']
 else:
  setup=s['CryptoSetupMS'];enc=sum(r['EncodeEncryptMS'] for r in ev['records']);he=sum(r['EvalOnlyMS'] for r in ev['records']);dec=sum(r['DecryptDecodeMS'] for r in ev['records']);native=sum(r['TotalEvalMS'] for r in ev['records'])+setup;io=0
 pdf=enc+he+dec
 return dict(parameter_ms=ev['parameter_ms'],key_setup_ms=setup,encode_encrypt_ms=enc,he_ms=he,decrypt_decode_ms=dec,pdf_inference_ms=pdf,backend_call_ms=ev['backend_ms'],backend_other_ms=ev['backend_ms']-setup-pdf-io,native_accounted_ms=native,adapter_io_ms=io)
def trial_metrics(c,folder,stage,data,writer=None,reference=None):
 keys=sorted(folder.glob('key_*.json'));rows=[];seen=set();ctx=[];reference=reference or model_reference(c,data,stage)
 cp=folder/'trial.json' if (folder/'trial.json').exists() else folder/'result.json';candidate=read(cp).get('candidate') if cp.exists() else None
 observed_parameters=None
 for keyfile in keys:
  ev=read(keyfile);n=ev['key_run'];context=str(keyfile.relative_to(ROOT));ctx.append(cost(keyfile,c['kind']))
  q=ev.get('q',[]);p=ev.get('p',[])
  check(q and p,'actual modulus vectors missing')
  if candidate:
   par=candidate['parameters'];twoN=2*(1<<par['log_n']);check(len(q)==len(par['log_q']) and len(p)==len(par['log_p']),'actual prime counts')
   check(all(v%twoN==1 for v in q+p) and len(set(q+p))==len(q+p),'NTT or duplicate prime')
   check([round(math.log2(v)) for v in q]==par['log_q'] and [round(math.log2(v)) for v in p]==par['log_p'],'actual vs declared prime sizes')
   bound=candidate['security']['max_allowed_log_qp'];check(math.prod(q+p).bit_length()<=bound,'actual QP product exceeds frozen security bound')
  if observed_parameters is None:observed_parameters=(q,p)
  else:check(observed_parameters==(q,p),'moduli changed within candidate key repeats')
  for k,sid,plain,approx,label in raw_records(keyfile,c['kind']):
   check((k,sid) not in seen,'duplicate input/key');seen.add((k,sid));check(sid in reference,('unexpected input',sid))
   want,y=reference[sid];check(np.allclose(want,plain,atol=1e-9,rtol=1e-9),'plaintext/model mismatch');check(y==label,'label metadata mismatch')
   wp=int(want[0]>=.5) if len(want)==1 else int(np.argmax(want));pp=int(plain[0]>=.5) if len(plain)==1 else int(np.argmax(plain));check(wp==pp,'independent plaintext arithmetic changes decision; inspect rounding/semantics')
   v=verdict(plain,approx);v.update(case_id=c['case_id'],stage=stage,run=str(folder.relative_to(ROOT)),sample_id=sid,key=k,context_id=context,label=label,plaintext_correct=(v['plain_class']==label) if stage!='stress' else None,numeric_pointwise_pass=v['max_abs']<=c['thresholds']['max_abs'])
   rows.append(v)
   if writer:writer.writerow(v)
  expected=len(reference)
  check(sum(1 for kk,_ in seen if kk==n)==expected,('key input denominator',folder,n,expected))
  # Recorded moduli are for one actual context, not a secret-key identity.
 per_key=[]
 for n in sorted(set(r['key'] for r in rows)):
  rr=[r for r in rows if r['key']==n];per_key.append(dict(key=n,max_abs=max(r['max_abs'] for r in rr),rmse=math.sqrt(np.mean([r['mse'] for r in rr]))))
 plain_by_id={r['sample_id']:r['plain_class'] for r in rows}
 ids={r['sample_id'] for r in rows};app={r['sample_id'] for r in rows if r['applicable']};boundary=ids-app
 sums={k:sum(d[k] for d in ctx) for k in ctx[0]} if ctx else {}
 r=dict(case_id=c['case_id'],stage=stage,raw=str(folder.relative_to(ROOT)),unique_inputs=len(ids),applicable=len(app),boundary=len(boundary),key_contexts=len(keys),observations=len(rows),protected_flip_events=sum(r['protected_flip'] for r in rows),protected_error_events=sum(r['protected_error_violation'] for r in rows),boundary_flip_events=sum(r['flip'] and not r['applicable'] for r in rows),all_flip_events=sum(r['flip'] for r in rows),protected_unique_flips=len({r['sample_id'] for r in rows if r['protected_flip']}),protected_unique_errors=len({r['sample_id'] for r in rows if r['protected_error_violation']}),max_abs=max((r['max_abs'] for r in rows),default=None),rmse=math.sqrt(np.mean([r['mse'] for r in rows])) if rows else None,numeric=per_key,numeric_max_pass=len(keys)==3 and all(v['max_abs']<=c['thresholds']['max_abs'] for v in per_key),numeric_rmse_pass=len(keys)==3 and all(v['rmse']<=c['thresholds']['rmse'] for v in per_key),proposal_pass=len(keys)==3 and bool(app) and not any(v['protected_flip'] or v['protected_error_violation'] for v in rows),plain_accuracy=float(np.mean([reference[i][1]==plain_by_id[i] for i in ids])) if ids and stage!='stress' else None,cost=sums)
 r['all_unique_flips']=len({v['sample_id'] for v in rows if v['flip']})
 r['boundary_unique_flips']=len({v['sample_id'] for v in rows if v['flip'] and not v['applicable']})
 return r,rows
def security(candidate):
 s=candidate['security'];p=candidate['parameters'];check(s['target_bits']==128 and s['ciphertext_q_admission']=='PASS' and s['evaluation_key_qp_admission']=='PASS','security admission')
 limits={v['log_n']:v['max_log_qp_bits'] for v in read(read(PROTOCOL)['cases'][0]['plan'])['policy']['security_envelope']['limits']}
 check(sum(p['log_q'])+sum(p['log_p'])<=limits[p['log_n']],'declared QP exceeds envelope')
def command_costs():
 groups=collections.defaultdict(lambda:dict(commands=0,wall_seconds=0.,nonzero_exits=0))
 for path in sorted((RUN/'commands').glob('*.end.json')):
  j=read(path);cmd=j['command'];tag=path.name
  if tag.startswith('external_connect'):stage='external_connection_install_or_import'
  elif tag.startswith('external_train'):stage='external_public_procedure_training'
  elif tag.startswith('external_native_'):stage='external_official_ckks_'+tag.removeprefix('external_native_').removesuffix('.end.json')
  else:
   mode=cmd[cmd.index('--mode')+1] if '--mode' in cmd else 'other'
   stage=('external_common_' if tag.startswith('external_') else 'internal_')+mode
  v=groups[stage];v['commands']+=1;v['wall_seconds']+=j['wall_seconds'];v['nonzero_exits']+=int(j['exit_code']!=0)
 return [dict(stage=k,**v) for k,v in sorted(groups.items())]
def analyze(writer=None):
 spec=read(PROTOCOL);trials=[];selections=[];audit=[];stress=[];diagnostic=[];diagnostic_examples=[];type_rows=[];refs={};failures=[]
 for c in spec['cases']:
  cid=c['case_id'];base=RUN/'cases'/cid;refsel=model_reference(c,c['selection'],'selection')
  for p in sorted(base.glob('selection/block_*/*/result.json')):
   r=read(p);block=int(p.parent.parent.name.split('_')[1]);role=p.parent.name;decision_ms=numeric_ms=0.;costs=collections.defaultdict(float)
   seen=[];selection_rows={}
   for tp in sorted(p.parent.glob('trial_*/trial.json'),key=lambda p:int(p.parent.name.split('_')[1])):
    t=read(tp);security(t['candidate']);metric,rs=trial_metrics(c,tp.parent,'selection',c['selection'],writer,refsel);metric['candidate_id']=t['candidate']['id'];metric['literal_id']=literal_id(t['candidate']);metric['status_native']=t['status'];trials.append(metric);seen.append((t,metric));selection_rows[metric['raw']]=rs
    check(t['keys']==metric['key_contexts'],'key count');check((t['status']=='SAFE')==metric['proposal_pass'],'native proposal verdict')
    for x,y in zip(t['numeric'],metric['numeric']):check(near(x['max_abs'],y['max_abs']) and near(x['rmse'],y['rmse']),'native numeric metrics')
    for k,v in metric['cost'].items():costs[k]+=v
    decision_ms+=t['decision_ms'];numeric_ms+=t['numeric_ms']
   accepted=[t for t,m in seen if m['numeric_max_pass'] if r['role']=='A'] if r['role']=='A' else [t for t,m in seen if m['proposal_pass']]
   check((r.get('selected') is not None)==bool(accepted),'selection outcome')
   if accepted:check(r['selected']['parameters']==accepted[0]['candidate']['parameters'],'first acceptable selection')
   if accepted:
    selected_metric=next(m for t,m in seen if t is accepted[0])
    refs[(cid,block,role,'selection')]=group(selection_rows[selected_metric['raw']],lambda v:v['sample_id'])
   check(len(seen)==r['actual_encrypted_candidates']<=4,'candidate budget')
   # Independent proposal scales may not change with margins or past errors.
   if r['role']!='C':
    for g in r['generation_attempts']:check(g['requested_scale']==r['start_scale']+4*(g['ordinal']-1),'independent order changed')
    for t,_ in seen:check(t['candidate']['generation_kind']=='independent_explicit_scale_v1','margin-based candidate in A/B')
   else:
    planning=read(p.parent/'analysis.json')['plan'];check(planning['initial_candidates'][0]['parameters']==read(c['plan'])['initial_candidates'][0]['parameters'],'C initial parameters changed')
   command_path=RUN/'commands'/f'{cid}_select_b{block}_{role}.end.json';command_ms=read(command_path)['wall_seconds']*1000 if command_path.exists() else None
   selections.append(dict(case_id=cid,block=block,role=role,command_wall_ms=command_ms,outer_call_minus_internal_wall_ms=(command_ms-r['wall_ms']) if command_ms is not None else None,outcome=r['outcome'],candidate_id=r['selected']['id'] if r.get('selected') else None,literal_id=literal_id(r['selected']) if r.get('selected') else None,parameters=r['selected']['parameters'] if r.get('selected') else None,encrypted_candidates=len(seen),static_attempts=len(r['generation_attempts']),workflow_wall_ms=r['wall_ms'],analysis_ms=r['analysis_ms'],evidence_write_ms=r['evidence_write_ms'],decision_evaluation_ms=decision_ms,numeric_evaluation_ms=numeric_ms,actual_wall_includes_posthoc=True,raw=str(p.relative_to(ROOT)),**costs))
  for p in sorted(list(base.glob('diagnostic/*/generation/result.json'))+list(base.glob('extra_*/*/generation/result.json'))):
   g=read(p);out=p.parent.parent/'execution';rec=dict(case_id=cid,diagnostic_kind=p.parent.parent.parent.name,scale=int(p.parent.parent.name.split('_')[0][1:]),generation_failure=g['failure'],raw=str(p.relative_to(ROOT)),executed=False)
   if (out/'result.json').exists():
    t=read(out/'result.json');security(t['candidate']);m,diagnostic_rows=trial_metrics(c,out,'diagnostic',c['selection'],writer,refsel);m['candidate_id']=t['candidate']['id'];m['literal_id']=literal_id(t['candidate']);trials.append(m);rec.update(executed=True,metrics=m)
    rec['sensitivity']=[dict(multiplier=a,numeric_max_pass=all(k['max_abs']<=a*c['thresholds']['max_abs'] for k in m['numeric']) and m['key_contexts']==3,numeric_rmse_pass=all(k['rmse']<=a*c['thresholds']['rmse'] for k in m['numeric']) and m['key_contexts']==3) for a in spec['diagnostic']['precision_sensitivity_multipliers']]
    passing=[v['multiplier'] for v in rec['sensitivity'] if v['numeric_max_pass']]
    if passing:
     for sid,vv in group(diagnostic_rows,lambda v:v['sample_id']).items():
      if not any(v['flip'] for v in vv):continue
      counterparts=[]
      for block in range(spec['selection']['blocks']):
       for role in ['A30','B30','C','A40','B40']:
        yy=refs.get((cid,block,role,'selection'),{}).get(sid,[])
        counterparts.append(dict(block=block,role=role,observations=len(yy),flips=sum(v['flip'] for v in yy),protected_error_violations=sum(v['protected_error_violation'] for v in yy),max_abs=max((v['max_abs'] for v in yy),default=None),contexts=[v['context_id'] for v in yy]))
      diagnostic_examples.append(dict(case_id=cid,scale=rec['scale'],sample_id=sid,margin=vv[0]['margin'],applicable=vv[0]['applicable'],numeric_passing_predeclared_multipliers=passing,main_numeric_pass=m['numeric_max_pass'],all_flip_events=sum(v['flip'] for v in vv),contexts=[v['context_id'] for v in vv],selected_counterparts=counterparts,interpretation='same selection input; independent diagnostic candidate, not actual A/B online choice; sensitivity does not retune the main criterion'))
   diagnostic.append(rec)
  for p in sorted(base.glob('audit/*/batch_*/result.json')):
   candidate=read(p)['candidate'];security(candidate);check(literal_id(candidate)==p.parent.parent.name,'audit result parameters differ from frozen configuration directory')
   batch=int(p.parent.name.split('_')[1]);data=c['audit'][batch];key=(cid,data)
   if key not in refs:refs[key]=model_reference(c,data,'audit')
   m,rs=trial_metrics(c,p.parent,'audit',data,writer,refs[key]);m['literal_id']=p.parent.parent.name;m['batch']=batch;audit.append(m)
   refs[(cid,m['literal_id'],batch)]=rs
  for p in sorted(base.glob('stress/*/result.json')):
   candidate=read(p)['candidate'];security(candidate);check(literal_id(candidate)==p.parent.name,'stress result parameters differ from frozen configuration directory')
   data=RUN/'stress'/cid/('batch.csv' if c['kind']=='multiclass' else 'materialized/prepared.csv')
   m,rs=trial_metrics(c,p.parent,'stress',data,writer);m['literal_id']=p.parent.name;stress.append(m)
 # Group audit batches, counting case-input pairs once and keeping all key contexts.
 audit_group=[]
 for (cid,lid),values in group(audit,lambda m:(m['case_id'],m['literal_id'])).items():
  c=next(c for c in spec['cases'] if c['case_id']==cid);allrows=[r for m in values for r in refs[(cid,lid,m['batch'])]];ids={r['sample_id'] for r in allrows};app={r['sample_id'] for r in allrows if r['applicable']}
  correct_by_id={r['sample_id']:r['plain_class']==r['label'] for r in allrows}
  audit_group.append(dict(case_id=cid,literal_id=lid,batches=len(values),expected_batches=len(c['audit']),evaluated_inputs=len(ids),planned_inputs=c['audit_inputs'],applicable=len(app),boundary=len(ids-app),key_contexts=sum(m['key_contexts'] for m in values),observations=len(allrows),protected_flip_events=sum(r['protected_flip'] for r in allrows),protected_error_events=sum(r['protected_error_violation'] for r in allrows),boundary_flip_events=sum(r['flip'] and not r['applicable'] for r in allrows),all_flip_events=sum(r['flip'] for r in allrows),protected_unique_flips=len({r['sample_id'] for r in allrows if r['protected_flip']}),protected_unique_errors=len({r['sample_id'] for r in allrows if r['protected_error_violation']}),max_abs=max(r['max_abs'] for r in allrows),rmse=math.sqrt(np.mean([r['mse'] for r in allrows])),numeric_max_pass=all(m['numeric_max_pass'] for m in values),proposal_pass=all(m['proposal_pass'] for m in values),complete=len(values)==len(c['audit']) and len(allrows)==c['audit_inputs']*3 and len(ids)==c['audit_inputs'],plain_accuracy=float(np.mean([correct_by_id[sid] for sid in ids]))))
  refs[(cid,lid,'all')]=allrows
 for g in audit_group:
  allrows=refs[(g['case_id'],g['literal_id'],'all')]
  g['all_unique_flips']=len({v['sample_id'] for v in allrows if v['flip']})
  g['boundary_unique_flips']=len({v['sample_id'] for v in allrows if v['flip'] and not v['applicable']})
  g['observed_numeric_max_pass']=g['numeric_max_pass'];g['observed_proposal_pass']=g['proposal_pass']
  if not g['complete']:
   cc=next(c for c in spec['cases'] if c['case_id']==g['case_id'])
   g['numeric_max_pass']=False if g['max_abs']>cc['thresholds']['max_abs'] else None
   g['proposal_pass']=False if g['protected_flip_events'] or g['protected_error_events'] else None
 if (RUN/'FROZEN_SELECTIONS.json').exists():
  for f in read(RUN/'FROZEN_SELECTIONS.json')['cases']:
   cid=f['case_id'];roles={(r['block'],r['role']):r['literal_id'] for r in f['roles']}
   for block in [0,1]:
    for a,b in [('A30','B30'),('B30','C'),('A40','B40'),('B40','C')]:
     x=refs.get((cid,roles[(block,a)],'all'));y=refs.get((cid,roles[(block,b)],'all'))
     if x is None or y is None:continue
     xx=group(x,lambda r:r['sample_id']);yy=group(y,lambda r:r['sample_id']);counts=collections.Counter()
     for sid in sorted(xx.keys()&yy.keys()):
      xf=any(r['flip'] for r in xx[sid]);yf=any(r['flip'] for r in yy[sid]);outside=not xx[sid][0]['applicable']
      category='both_preserved' if not xf and not yf else 'left_flip_right_preserved' if xf and not yf else 'right_flip_left_preserved' if yf and not xf else 'both_flip'
      counts[category]+=1;counts['outside_domain']+=int(outside)
      if category!='both_preserved' or outside or counts[category]==1:
       am=next(v for v in audit_group if v['case_id']==cid and v['literal_id']==roles[(block,a)]);bm=next(v for v in audit_group if v['case_id']==cid and v['literal_id']==roles[(block,b)])
       type_rows.append(dict(case_id=cid,block=block,left=a,right=b,sample_id=sid,category=category,outside_domain=outside,left_audit_numeric_pass=am['numeric_max_pass'] if am['complete'] else None,right_audit_numeric_pass=bm['numeric_max_pass'] if bm['complete'] else None,left_audit_proposal_pass=am['proposal_pass'] if am['complete'] else None,right_audit_proposal_pass=bm['proposal_pass'] if bm['complete'] else None,left_pointwise_numeric_all_keys=all(v['numeric_pointwise_pass'] for v in xx[sid]),right_pointwise_numeric_all_keys=all(v['numeric_pointwise_pass'] for v in yy[sid]),left_contexts=[v['context_id'] for v in xx[sid]],right_contexts=[v['context_id'] for v in yy[sid]],selection_and_audit_conditions_distinct=True,unit='unique input; any of three independent key observations; no common secret key'))
     type_rows.append(dict(case_id=cid,block=block,left=a,right=b,counts=dict(counts),unit='unique case-input pairs; same-config aliases share observations'))
 for p in (RUN/'commands').glob('*.end.json'):
  r=read(p)
  if r['exit_code']!=0:failures.append(dict(path=str(p.relative_to(ROOT)),status=r['status'],exit_code=r['exit_code']))
 costs=command_costs();total=sum(c['wall_seconds'] for c in costs)
 return dict(protocol_id=spec['protocol_id'],timing=analyze_timing(),selection_runs=selections,trial_metrics=trials,diagnostic=diagnostic,diagnostic_examples=diagnostic_examples,audit_batches=audit,audit=audit_group,stress=stress,stress_input_validity=analyze_inputs(spec,ROOT,RUN,resolve_path),input_types=type_rows,execution_failures=failures,command_costs=costs,recorded_command_wall_seconds=total,native_wall_seconds=total,native_wall_seconds_legacy_field_meaning='all recorded command wall time, including preparation and external connection/training; not pure homomorphic evaluation time',network=None,queue=None,unexposed_input_confirmation=False,risk_guarantee=False)
def group(rows,key):
 d=collections.defaultdict(list)
 for r in rows:d[key(r)].append(r)
 return d
def csvout(p,rows):
 if not rows:return
 fields=list(dict.fromkeys(k for r in rows for k in r))
 with p.open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def main():
 p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');p.add_argument('--check',action='store_true');a=p.parse_args();check(not(a.write and a.check),'choose write or check')
 if a.write:
  fields=['margin','applicable','flip','error_violation','protected_flip','protected_error_violation','max_abs','mse','budget_usage','plain_class','case_id','stage','run','sample_id','key','context_id','label','plaintext_correct','numeric_pointwise_pass']
  with gzip.open(DOC/'INPUT_OBSERVATIONS.csv.gz','xt',newline='') as f:
   w=csv.DictWriter(f,fieldnames=fields);w.writeheader();r=analyze(w)
  write(DOC/'RESULTS.json',r)
  for key in ['selection_runs','trial_metrics','audit','stress','stress_input_validity','input_types','diagnostic','diagnostic_examples','command_costs']:csvout(DOC/(key.upper()+'.csv'),r[key])
  for key in ['summary','blocks','records']:csvout(DOC/('TIMING_'+key.upper()+'.csv'),r['timing'][key])
  csvout(DOC/'TIMING_ARMS.csv',[dict(case_id=b['case_id'],reference=b['reference'],comparator=b['comparator'],key_block=b['key_block'],unit=b['unit'],selected_inputs=b['selected_inputs'],**arm) for b in r['timing']['blocks'] for arm in b['arms']])
 else:r=analyze()
 if a.check:compare_values(read(DOC/'RESULTS.json'),r);print('independent recomputation matches stored results')
 print(json.dumps({k:len(r[k]) for k in ['selection_runs','diagnostic','audit','stress','execution_failures']},ensure_ascii=False))
if __name__=='__main__':main()
