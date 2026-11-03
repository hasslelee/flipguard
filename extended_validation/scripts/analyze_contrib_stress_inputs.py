"""Read-only reconstruction of the fixed common stress input constraints."""
import csv
import numpy as np

def rows(path):
 with path.open() as f:return list(csv.DictReader(f))

def analyze_inputs(spec,root,run,resolve):
 result=[]
 for c in spec['cases']:
  folder=run/'stress'/c['case_id']
  if not (folder/'INPUT_LOCK.json').exists():continue
  if c['kind']=='multiclass':
   parents=rows(resolve(c['audit'][0]));generated=rows(folder/'batch.csv');assert len(parents)==len(generated)
   fields=[f'pixel_{j:03d}' for j in range(784)]
   assert generated[16:]==parents[16:],'unused container rows changed'
   checks=[]
   for p,s in zip(parents[:16],generated[:16]):
    a=np.array([int(p[k]) for k in fields]);b=np.array([int(s[k]) for k in fields])
    assert s['sample_id']=='contrib_stress:'+p['sample_id'] and p['label']==s['label']
    valid=bool(np.all((b>=0)&(b<=255)) and np.max(abs(b-a))<=8)
    assert valid,'image integer box/radius constraint'
    checks.append(dict(parent=p['sample_id'],synthetic=s['sample_id'],integer_pixel_box_valid=valid,max_pixel_change=int(np.max(abs(b-a))),synthetic_truth_known=False))
   rule='first16 parents; uint8 pixels, L-infinity<=8 raw pixel units; remaining container rows excluded from HE stress'
  else:
   base=resolve(c['model']).parent;parents=rows(base/'independent_evaluation.csv')[:16];generated=rows(folder/'raw.csv');training=rows(base/'model_training.csv')
   assert len(generated)==len(parents)==16
   fields=sorted((k for k in parents[0] if k.startswith('x_')),key=lambda k:int(k[2:]));T=np.array([[float(r[k]) for k in fields] for r in training]);lo=T.min(axis=0);hi=T.max(axis=0);radius=.02*(hi-lo)
   frozen=np.array([len(np.unique(T[:,j]))<=2 for j in range(T.shape[1])]);radius[frozen]=0;integer=np.all(T==np.rint(T),axis=0);checks=[]
   for p,s in zip(parents,generated):
    a=np.array([float(p[k]) for k in fields]);b=np.array([float(s[k]) for k in fields]);assert p['row_id']==s['row_id'] and p['label']==s['label']
    rv=bool(np.all(abs(b-a)<=radius+1e-9));bv=bool(np.all(b>=np.minimum(lo,a)-1e-9) and np.all(b<=np.maximum(hi,a)+1e-9));fv=bool(np.array_equal(a[frozen],b[frozen]));iv=bool(np.all(abs(b[integer]-np.rint(b[integer]))<=1e-9))
    assert rv and bv and fv and iv,('tabular stress constraint',c['case_id'],p['row_id'])
    checks.append(dict(parent=p['row_id'],synthetic=p['row_id'],radius_valid=rv,training_box_or_original_valid=bv,frozen_features_unchanged=fv,integer_features_valid=iv,frozen_feature_count=int(frozen.sum()),integer_feature_count=int(integer.sum()),max_radius_usage=float(np.max(np.divide(abs(b-a),radius,out=np.zeros_like(radius),where=radius>0))),synthetic_truth_known=False))
   rule='first16 parents; 2percent training feature range; <=2-valued features frozen; integer features retained; original out-of-range parent bounds retained'
  result.append(dict(case_id=c['case_id'],inputs=len(checks),rule=rule,records=checks,coordinate_constraints_passed=True,joint_real_world_validity='not established',synthetic_truth_known=False,raw=str(folder.relative_to(root))))
 return result
