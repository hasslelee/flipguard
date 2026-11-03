#!/usr/bin/env python3
"""Bounded common plaintext-only stress. Labels are parent metadata, not truth."""
import argparse,csv,fcntl,json,os,time
from pathlib import Path
import numpy as np
from run_fg_contrib_v1 import ROOT,RUN,PROTOCOL,read,write,sha,call,verify

def tabular_forward_gradient(m,X):
 ids=m['selected_feature_indices'];std=np.array(m['standardization']['std']);x=(X[:,ids]-m['standardization']['mean'])/std;p=m['scaled_model_for_ckks']
 if m['model_type']=='linear_poly3':
  w=np.array(p['weights']);z=x@w+p['bias'];score=.5+.197*z-.004*z**3;g=(.197-.012*z*z)[:,None]*w/std
 else:
  W=np.array(p['hidden_weights']);v=np.array(p['output_weights']);h=x@W.T+p['hidden_bias'];z=h*h@v+p['output_bias'];score=.5+.197*z;g=.197*((2*h*v)@W)/std
 full=np.zeros_like(X);full[:,ids]=g;return score,full
def multi_forward_gradient(m,X):
 w=np.array(m['parameters']);W=w[:78400].reshape(100,784);b=w[78400:78500];V=w[78500:79500].reshape(10,100);d=w[79500:]
 h=X@W.T+b;z=h*h@V.T+d;order=np.argsort(-z,axis=1,kind='stable');top=order[:,0];runner=order[:,1]
 g=(2*h*(V[top]-V[runner]))@W;gap=z[np.arange(len(X)),top]-z[np.arange(len(X)),runner];return z,gap,g
def csvwrite(p,fields,rows):
 with p.open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def prepare():
 assert (RUN/'FROZEN_SELECTIONS.json').exists(),'selection must be frozen first'
 spec=read(PROTOCOL);lock=RUN/'STRESS_RULE_LOCK.json'
 if not lock.exists():write(lock,dict(protocol_sha256=sha(PROTOCOL),script_sha256=sha(__file__),selection_freeze_sha256=sha(RUN/'FROZEN_SELECTIONS.json'),steps=20,step='radius/20 per coordinate; fixed, no early stop or line search',image_rounding='round-to-nearest uint8 after final projection',labels='inherited metadata only; all synthetic accuracy and HEDiff Eq2 labels unknown',tabular_validity='coordinate bounds; binary <=2 distinct values frozen; integer-valued features rounded. Does not prove realizable emails or physically consistent joint statistics.'))
 check=read(lock);assert check['script_sha256']==sha(__file__)
 for c in spec['cases']:
  out=RUN/'stress'/c['case_id'];out.mkdir(parents=True,exist_ok=True)
  if (out/'INPUT_LOCK.json').exists():continue
  m=read(c['model']);records=[];checks=[]
  if c['kind']=='multiclass':
   rows=list(csv.DictReader(Path(c['audit'][0]).open()));fields=list(rows[0]);X0=np.array([[int(r[f'pixel_{j:03d}'])/255 for j in range(784)] for r in rows[:16]]);eps=np.full(784,8/255);X=X0.copy()
   z0,g0,_=multi_forward_gradient(m,X0)
   # Central-difference check at original seed, away from class ordering ties.
   z,gap,grad=multi_forward_gradient(m,X0[:1]);order=np.argsort(-z[0],kind='stable')[:2]
   for j in [0,100,400,783]:
    h=1e-6;a=X0[:1].copy();b=a.copy();a[0,j]+=h;b[0,j]-=h;za,_,_=multi_forward_gradient(m,a);zb,_,_=multi_forward_gradient(m,b);fd=((za[0,order[0]]-za[0,order[1]])-(zb[0,order[0]]-zb[0,order[1]]))/(2*h);checks.append(dict(coordinate=j,analytic=float(grad[0,j]),finite_difference=float(fd)));assert np.isclose(fd,grad[0,j],rtol=2e-4,atol=2e-5)
   for _ in range(20):
    _,_,g=multi_forward_gradient(m,X);X-=eps/20*np.sign(g);X=np.minimum(np.maximum(X,X0-eps),X0+eps);X=np.clip(X,0,1)
   X=np.rint(X*255).clip(0,255)/255;z1,g1,_=multi_forward_gradient(m,X)
   for i,row in enumerate(rows[:16]):
    parent=row['sample_id'];row['sample_id']='contrib_stress:'+parent;row['source_partition']='synthetic_from_'+row['source_partition']
    for j in range(784):row[f'pixel_{j:03d}']=str(int(round(X[i,j]*255)))
    records.append(dict(row_id=i,parent_sample_id=parent,synthetic_sample_id=row['sample_id'],parent_label_metadata=int(row['label']),parent_gap=float(g0[i]),stress_gap=float(g1[i]),linfinity=float(abs(X[i]-X0[i]).max()),parent_prediction=int(z0[i].argmax()),stress_prediction=int(z1[i].argmax()),label_known=False))
   # A full valid legacy container is loaded; raw executor selects only rows0..15.
   csvwrite(out/'batch.csv',fields,rows);assert np.max(abs(X-X0))<=8/255+1e-12
  else:
   pr=Path(c['model']).parent;rows=list(csv.DictReader((pr/'independent_evaluation.csv').open()))[:16];fields=list(rows[0]);train=list(csv.DictReader((pr/'model_training.csv').open()));features=sorted([k for k in fields if k.startswith('x_')],key=lambda s:int(s[2:]));T=np.array([[float(r[k]) for k in features] for r in train]);X0=np.array([[float(r[k]) for k in features] for r in rows]);lo=T.min(axis=0);hi=T.max(axis=0);eps=.02*(hi-lo);frozen=np.array([len(np.unique(T[:,j]))<=2 for j in range(T.shape[1])]);eps[frozen]=0;integer=np.all(np.equal(T,np.rint(T)),axis=0);X=X0.copy();s0,_=tabular_forward_gradient(m,X0)
   _,g=tabular_forward_gradient(m,X0[:1])
   for j in m['selected_feature_indices'][:4]:
    h=1e-5;xa=X0[:1].copy();xb=xa.copy();xa[0,j]+=h;xb[0,j]-=h;fd=(tabular_forward_gradient(m,xa)[0][0]-tabular_forward_gradient(m,xb)[0][0])/(2*h);checks.append(dict(coordinate=j,analytic=float(g[0,j]),finite_difference=float(fd)));assert np.isclose(fd,g[0,j],rtol=2e-4,atol=2e-7)
   for _ in range(20):
    score,g=tabular_forward_gradient(m,X);X-=eps/20*np.sign((score-.5)[:,None]*g);X=np.minimum(np.maximum(X,X0-eps),X0+eps)
    # A parent outside training min/max remains at its original value, never
    # silently moved further than the declared local perturbation radius.
    low=np.maximum(np.minimum(lo,X0),X0-eps);high=np.minimum(np.maximum(hi,X0),X0+eps);X=np.minimum(np.maximum(X,low),high)
   X[:,integer]=np.rint(X[:,integer]);X[:,frozen]=X0[:,frozen];X=np.minimum(np.maximum(X,X0-eps),X0+eps)
   # Integer projection must remain in both the radius and integer lattice.
   for j in np.flatnonzero(integer & ~frozen):X[:,j]=np.clip(np.rint(X[:,j]),np.ceil(X0[:,j]-eps[j]),np.floor(X0[:,j]+eps[j]))
   assert np.array_equal(X[:,frozen],X0[:,frozen]),'frozen categorical/binary coordinates changed'
   s1,_=tabular_forward_gradient(m,X)
   for i,row in enumerate(rows):
    for j,k in enumerate(features):row[k]=format(X[i,j],'.17g')
    records.append(dict(row_id=int(row['row_id']),parent_sample_id=row['row_id'],parent_label_metadata=int(row['label']),parent_margin=float(abs(s0[i]-.5)),stress_margin=float(abs(s1[i]-.5)),parent_prediction=int(s0[i]>=.5),stress_prediction=int(s1[i]>=.5),label_known=False,max_radius_usage=float(np.max(np.divide(abs(X[i]-X0[i]),eps,out=np.zeros_like(eps),where=eps>0)))))
   csvwrite(out/'raw.csv',fields,rows);assert np.all(abs(X-X0)<=eps+1e-9)
  write(out/'INPUT_LOCK.json',dict(case_id=c['case_id'],model_sha256=sha(c['model']),generator_sha256=sha(__file__),records=records,gradient_checks=checks,inputs={p.name:sha(p) for p in out.glob('*.csv')},ckks_feedback_used=False,labels_asserted=False))
def run():
 verify();spec=read(PROTOCOL);frozen=read(RUN/'FROZEN_SELECTIONS.json');by={f['case_id']:f for f in frozen['cases']}
 lease=(ROOT/'work/fg_contrib_v1_20260906/native.lock').open('a');fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for c in spec['cases']:
  out=RUN/'stress'/c['case_id'];assert (out/'INPUT_LOCK.json').exists()
  if c['kind']=='tabular':
   call(c['case_id']+'_stress_materialize',['--mode','materialize','--model',c['model'],'--data',out/'raw.csv','--out',out/'materialized']);data=out/'materialized/prepared.csv'
  else:data=out/'batch.csv'
  for lid,u in by[c['case_id']]['unique'].items():
   dest=RUN/'cases'/c['case_id']/'stress'/lid
   call(c['case_id']+'_stress_'+lid,['--mode','raw-stress','--legacy-plan',c['plan'],'--candidate',u['path'],'--data',data,'--out',dest])
 write(RUN/'STRESS_COMPLETED.json',dict(cases=7,labels_asserted=False,risk_guarantee=False))
def wait_and_run():
 # Only the already approved finite stress stage is queued. No new research.
 def alive(script):
  for p in Path('/proc').glob('[0-9]*/cmdline'):
   try:
    a=p.read_bytes().split(b'\0')
    if len(a)>1 and a[1]==script.encode():return True
   except (FileNotFoundError,PermissionError):pass
  return False
 started=time.monotonic()
 while not (RUN/'FROZEN_SELECTIONS.json').exists():
  if not alive('scripts/run_fg_contrib_v1.py'):raise RuntimeError('internal selection stopped before freeze; inspect existing records')
  if time.monotonic()-started>43200:raise RuntimeError('finite stage wait limit')
  time.sleep(5)
 prepare();print('fixed common stress inputs prepared after all selections froze',flush=True)
 while alive('scripts/run_fg_contrib_v1.py') or alive('scripts/run_external_contrib_v1.py'):
  if time.monotonic()-started>44400:raise RuntimeError('finite stage wait limit')
  time.sleep(5)
 if not (RUN/'TIMING_PHASE_COMPLETED.json').exists():raise RuntimeError('internal schedule incomplete; inspect remaining budget before stress')
 run()
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('phase',choices=['prepare','run','wait_and_run']);args=a.parse_args();globals()[args.phase]()
