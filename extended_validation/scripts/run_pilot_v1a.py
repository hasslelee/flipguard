#!/usr/bin/env python3
"""Run a fresh, prespecified pilot; never access predecessor test inputs."""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import urllib.request
import zipfile

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, logsumexp
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from deciprotect.decision import calibration_radius, interval_gate, reference_decision, decision_metrics


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_json(p, value):
    with Path(p).open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def fetch(dataset):
    ident, member = {'spambase': (94, 'spambase.data'), 'wine': (109, 'wine.data')}[dataset]
    url = f'https://archive.ics.uci.edu/static/public/{ident}/{dataset}.zip'
    cache = ROOT / 'data/raw' / f'{dataset}.zip'
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        last = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    data = r.read()
                with cache.open('xb') as f: f.write(data)
                break
            except Exception as e:
                last = e
                print(f'DOWNLOAD_RETRY dataset={dataset} attempt={attempt+1} error={e}', flush=True)
        else: raise last
    with zipfile.ZipFile(cache) as z:
        matrix = np.loadtxt(io.BytesIO(z.read(member)), delimiter=',')
    x, y = (matrix[:, :-1], matrix[:, -1].astype(int)) if dataset == 'spambase' else (matrix[:, 1:], matrix[:, 0].astype(int)-1)
    groups = {}
    for i, row in enumerate(x): groups.setdefault(row.tobytes(), []).append(i)
    keep, duplicates, conflicts = [], [], []
    for indices in groups.values():
        if len(set(y[indices])) > 1: conflicts.extend(indices)
        else: keep.append(indices[0]); duplicates.extend(indices[1:])
    keep = np.array(sorted(keep))
    info = {'url': url, 'archive_sha256': digest(cache), 'original_rows': len(x), 'features': x.shape[1],
            'retained_rows': len(keep), 'duplicate_rows_removed': duplicates, 'conflicting_rows_removed': conflicts,
            'license_source': f'https://archive.ics.uci.edu/dataset/{ident}/{dataset}'}
    return x[keep], y[keep], keep, info


def train(x, y, family, seed):
    classes = int(y.max()+1)
    if family == 'logistic_linear':
        model = LogisticRegression(C=1.0, max_iter=1000, random_state=seed).fit(x, y)
        return [{'weights': model.coef_.tolist(), 'bias': model.intercept_.tolist(), 'square': False}], {'optimizer': 'sklearn LogisticRegression', 'iterations': model.n_iter_.tolist()}
    d, h, k = x.shape[1], 12, classes
    rng = np.random.default_rng(seed)
    w1 = rng.normal(0, .25 / math.sqrt(d), size=(h,d))
    b1 = np.zeros(h)
    w2 = rng.normal(0, .25 / math.sqrt(h), size=(k,h))
    b2 = np.zeros(k)
    sizes = [h*d,h,k*h,k]
    def unpack(t):
        a,b,c,e = np.split(t,np.cumsum(sizes)[:-1])
        return a.reshape(h,d),b,c.reshape(k,h),e
    def objective(t):
        a,b,c,e = unpack(t)
        u=x@a.T+b; hidden=u*u; logits=hidden@c.T+e
        logp=logits-logsumexp(logits,axis=1,keepdims=True)
        loss=-logp[np.arange(len(y)),y].mean()+.001*(np.sum(a*a)+np.sum(c*c))/2
        g=np.exp(logp);g[np.arange(len(y)),y]-=1;g/=len(y)
        gc=g.T@hidden+.001*c;ge=g.sum(axis=0)
        gu=(g@c)*2*u;ga=gu.T@x+.001*a;gb=gu.sum(axis=0)
        return loss,np.concatenate([ga.ravel(),gb,gc.ravel(),ge])
    initial=np.concatenate([w1.ravel(),b1,w2.ravel(),b2])
    opt=minimize(objective,initial,jac=True,method='L-BFGS-B',options={'maxiter':200})
    a,b,c,e=unpack(opt.x)
    return [{'weights':a.tolist(),'bias':b.tolist(),'square':True},{'weights':c.tolist(),'bias':e.tolist(),'square':False}], {'optimizer':'L-BFGS-B','iterations':int(opt.nit),'converged':bool(opt.success),'message':str(opt.message),'final_loss':float(opt.fun)}


def plain(layers,x):
    z=x
    for layer in layers:
        z=z@np.asarray(layer['weights']).T+np.asarray(layer['bias'])
        if layer['square']: z=z*z
    if not np.isfinite(z).all(): raise RuntimeError('Nonfinite reference output')
    return z


def encrypted(case, name, layers, x, scale, repeats=3):
    req=case/'inputs'/f'{name}.json'
    write_json(req,{'layers':layers,'inputs':x.tolist(),'scale':scale,'repeats':repeats})
    out=case/f'{name}.json';start=time.monotonic()
    with (case/f'{name}.log').open('x') as log:
        result=subprocess.run([str(ROOT/'bin/deciprotect-ckks'),'--input',str(req),'--output',str(out)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'GOMAXPROCS':'4'},timeout=600)
    if result.returncode:
        raise RuntimeError(f'CKKS command failed: {name}; see {case/name}.log')
    result=json.loads(out.read_text());result['process_wall_seconds']=time.monotonic()-start
    assert result['request_sha256']==digest(req)
    return result


def run_case(run,dataset,family,seed,protocol):
    case=run/f'{dataset}__{family}__{seed}';case.mkdir();(case/'inputs').mkdir()
    x,y,row_ids,source=fetch(dataset)
    train_idx,other=train_test_split(np.arange(len(y)),train_size=.5,random_state=seed,stratify=y)
    dev_idx,other=train_test_split(other,train_size=.3,random_state=seed+1,stratify=y[other])
    cal_idx,test_idx=train_test_split(other,train_size=3/7,random_state=seed+2,stratify=y[other])
    splits={'train':train_idx,'development':dev_idx,'calibration':cal_idx,'test':test_idx}
    assert len(set(np.concatenate(list(splits.values()))))==len(y)
    scaler=StandardScaler().fit(x[train_idx]);z=np.clip(scaler.transform(x),-5,5)
    start=time.monotonic();layers,training=train(z[train_idx],y[train_idx],family,seed)
    training['wall_seconds']=time.monotonic()-start
    write_json(case/'model.json',{'family':family,'seed':seed,'layers':layers,'mean':scaler.mean_.tolist(),'scale':scaler.scale_.tolist(),'clip':[-5,5],'training':training})
    write_json(case/'data_manifest.json',{'source':source,'split_source_row_ids':{k:row_ids[v].tolist() for k,v in splits.items()},'stratified':True,'overlap':0})
    preds={key:plain(layers,z[idx]) for key,idx in splits.items()}
    write_json(case/'plaintext.json',{key:{'source_row_ids':row_ids[idx].tolist(),'labels':y[idx].tolist(),'logits':preds[key].tolist()} for key,idx in splits.items()})
    low_scale=protocol['deployment_low_scale_by_family'][family]
    dev=[]
    for s in protocol['development_scales_by_family'][family]:
        obj=encrypted(case,f'development_s{s}',layers,z[dev_idx],s)
        err=np.array([m['logits'] for m in obj['measurements']])-preds['development'][None,:,:]
        dev.append({'scale':s,'log_n':obj['log_n'],'mean_abs_error':float(np.abs(err).mean()),'max_abs_error':float(np.abs(err).max()),
                    'flips_by_key':[int((reference_decision(m['logits'])!=reference_decision(preds['development'])).sum()) for m in obj['measurements']],
                    'mean_batch_total_ms':float(np.mean([m['total_ms'] for m in obj['measurements']]))})
    envelopes={};cal_objects={}
    for s in [low_scale,30]:
        obj=encrypted(case,f'calibration_s{s}',layers,z[cal_idx],s);cal_objects[s]=obj
        errors=np.max(np.abs(np.array([m['logits'] for m in obj['measurements']])-preds['calibration'][None,:,:]),axis=(0,2))
        envelopes[s]=calibration_radius(errors,protocol['alpha_stage_nominal'])
    # Commit the deployment state before any test ciphertext is evaluated.
    write_json(case/'deployment_lock.json',{'model_sha256':digest(case/'model.json'),'protocol_sha256':digest(ROOT/'protocols/DP_PILOT_V1A.json'),
                 'low_scale':low_scale,'high_scale':30,'calibration_rows':len(cal_idx),
                 'radius':{str(s):(q if math.isfinite(q) else 'INFINITY') for s,q in envelopes.items()},
                 'formal_risk_claim':'NOT_ADMITTED_DEPENDENT_KEYS_AND_PACKED_SLOTS','locked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()})
    low=encrypted(case,f'test_s{low_scale}',layers,z[test_idx],low_scale)
    high=encrypted(case,'test_s30',layers,z[test_idx],30)
    metrics=[];fallbacks=[]
    for key in range(3):
        low_logits=np.array(low['measurements'][key]['logits']);high_logits=np.array(high['measurements'][key]['logits'])
        accept_low=interval_gate(low_logits,envelopes[low_scale]);pending=np.flatnonzero(accept_low<0)
        decisions=accept_low.copy();fallback_time=0;fallback_measurement=None
        if len(pending) and math.isfinite(envelopes[30]):
            rerun=encrypted(case,f'fallback_key{key}_s30',layers,z[test_idx[pending]],30,repeats=1)
            fallback_measurement=rerun['measurements'][0];fallback_time=fallback_measurement['total_ms']
            decisions[pending]=interval_gate(fallback_measurement['logits'],envelopes[30])
        arms={f'fixed_scale{low_scale}':reference_decision(low_logits),'fixed_scale30':reference_decision(high_logits),
              'low_envelope_abstain':accept_low,'two_stage_envelope':decisions}
        for arm,ds in arms.items():
            m=decision_metrics(preds['test'],ds,y[test_idx]);m.update(arm=arm,key_repeat=key)
            m['measured_batch_total_ms']=high['measurements'][key]['total_ms'] if arm=='fixed_scale30' else low['measurements'][key]['total_ms']+(fallback_time if arm=='two_stage_envelope' else 0)
            metrics.append(m)
        fallbacks.append({'key_repeat':key,'requested_rows':len(pending),'executed_rows':len(pending) if fallback_measurement else 0,'source_row_ids':row_ids[test_idx[pending]].tolist(),
                          'decisions':decisions.tolist(),'fallback_total_ms':fallback_time,'fallback_measurement':{k:v for k,v in fallback_measurement.items() if k!='logits'} if fallback_measurement else None})
    summary={'case_id':case.name,'dataset':dataset,'model':family,'seed':seed,'source_rows':len(y),'split_sizes':{k:len(v) for k,v in splits.items()},
             'training':training,'development':dev,'envelopes':{str(s):(q if math.isfinite(q) else 'INFINITY') for s,q in envelopes.items()},
             'metrics':metrics,'fallbacks':fallbacks,'claim':'EXPLORATORY_ONLY','risk_admission':False,'key_repeats_are_not_independent_inputs':True}
    write_json(case/'summary.json',summary)
    manifest={str(p.relative_to(case)):digest(p) for p in sorted(case.rglob('*')) if p.is_file()}
    write_json(case/'evidence_manifest.json',manifest)
    m=next(m for m in metrics if m['arm']=='two_stage_envelope')
    print(f'CASE_DONE {case.name} coverage={m["coverage"]:.4f} disagreements={m["accepted_disagreements"]} training_converged={training.get("converged")}',flush=True)
    return summary


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);args=ap.parse_args()
    if not args.run_id.replace('_','').replace('-','').isalnum(): raise SystemExit('Invalid run ID')
    run=ROOT/'results'/args.run_id;run.mkdir(exist_ok=False)
    protocol=json.loads((ROOT/'protocols/DP_PILOT_V1A.json').read_text())
    sources=[ROOT/'protocols/DP_PILOT_V1A.json',Path(__file__),*sorted((ROOT/'src').rglob('*.py')),*sorted((ROOT/'cmd/deciprotect-ckks').glob('*.go')),ROOT/'go.mod',ROOT/'go.sum',ROOT/'requirements.txt']
    write_json(run/'run_binding.json',{'protocol_sha256':digest(ROOT/'protocols/DP_PILOT_V1A.json'),'sources':{str(p.relative_to(ROOT)):digest(p) for p in sources},'binary_sha256':digest(ROOT/'bin/deciprotect-ckks'),
                 'python':sys.version,'platform':platform.platform(),'started_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'GOMAXPROCS':4,'timing_class':'SHARED_VM_EXPLORATORY'})
    completed=[];failed=[]
    for dataset in ['spambase','wine']:
        for family in protocol['models']:
            for seed in protocol['training_seeds']:
                print(f'CASE_START {dataset} {family} {seed}',flush=True)
                try: completed.append(run_case(run,dataset,family,seed,protocol))
                except Exception as exc:
                    import traceback
                    traceback.print_exc();failed.append({'dataset':dataset,'family':family,'seed':seed,'error':str(exc)})
    write_json(run/'run_summary.json',{'status':'PILOT_COMPLETE' if not failed else 'PILOT_COMPLETE_WITH_FAILURES','completed_cases':len(completed),'failed_cases':failed,'confirmatory_claims':0})
    print('PILOT_FINISHED',len(completed),'completed',len(failed),'failed',flush=True)


if __name__=='__main__': main()
