#!/usr/bin/env python3
"""Finite, resumable execution; never selects from held-out outputs."""
import argparse, datetime, hashlib, json, os, resource, subprocess, time
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'results/fg_expand_v2_20260905_run01'
BIN=ROOT/'research/fashion_extension/bin/fashion-case'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def snapshot():
    mem={l.split(':')[0]:l.split(':')[1].strip() for l in Path('/proc/meminfo').read_text().splitlines()}
    return dict(utc=utc(),load_average=os.getloadavg(),mem_available=mem['MemAvailable'],swap_free=mem['SwapFree'],disk_free=os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize)
def limits():resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
def wait_for_exclusive():
    announced=False
    while True:
        busy=[]
        for p in Path('/proc').glob('[0-9]*/cmdline'):
            try:command=p.read_bytes().split(b'\0')[0].decode()
            except (OSError,UnicodeError):continue
            if command.endswith('/external-one') or command.endswith('/fashion-train'):
                busy.append(int(p.parent.name))
        if not busy:return
        if not announced:print('Waiting for isolated native execution; active PIDs',busy,flush=True);announced=True
        time.sleep(1)
def execute(name,args,timeout=1800):
    wait_for_exclusive()
    logs=RUN/'commands';logs.mkdir(exist_ok=True)
    attempts=len(list(logs.glob(name+'.attempt*.json')))+1
    stem=logs/f'{name}.attempt{attempts:02d}'
    command=['/usr/bin/time','-v',str(BIN),*map(str,args)]
    start=time.monotonic();before=snapshot();status='COMPLETED'
    with Path(str(stem)+'.log').open('x') as log:
        try:r=subprocess.run(command,cwd=ROOT,env={**os.environ,'GOMAXPROCS':'4','GOMEMLIMIT':'6GiB'},stdout=log,stderr=subprocess.STDOUT,timeout=timeout,preexec_fn=limits);code=r.returncode
        except subprocess.TimeoutExpired:status='TIMEOUT';code=124
    rec=dict(command=command,cwd=str(ROOT),started=before,finished=snapshot(),wall_seconds=time.monotonic()-start,exit_code=code,status=status,binary_sha256=sha(BIN))
    write(Path(str(stem)+'.json'),rec);print(json.dumps(dict(job=name,exit_code=code,wall_seconds=rec['wall_seconds'])),flush=True)
    return code
def quality():
    for seed in [0,1,2]:
        d=RUN/f'plaintext/seed_{seed}';out=d/'DEVELOPMENT_QUALITY.json'
        if out.exists():continue
        rows=read(d/'development_logits.json');z=np.array([r['logits'] for r in rows]);y=np.array([r['label'] for r in rows]);assert z.shape==(5000,10) and np.isfinite(z).all()
        p=z.argmax(axis=1);s=np.sort(z,axis=1);gap=s[:,-1]-s[:,-2];q=z.astype(np.float16).astype(np.float64);assert np.isfinite(q).all();err=abs(z-q)
        cm=np.zeros((10,10),int);np.add.at(cm,(y,p),1)
        tau=dict(rmse=float(np.sqrt(np.mean(err**2))),max_abs=float(err.max()))
        assert min(tau.values())>0
        write(out,dict(seed=seed,development_n=5000,accuracy=float(np.mean(y==p)),confusion_matrix=cm.tolist(),class_recall=(cm.diagonal()/cm.sum(axis=1)).tolist(),gap_quantiles={str(t):float(np.quantile(gap,t)) for t in [0,.01,.1,.5,.9,.99,1]},applicable=int(np.sum(gap>.001)),boundary=int(np.sum(gap<=.001)),finite=True,convergence_claim=False,numerical_thresholds=tau,threshold_rule='development logits round-to-nearest binary16; all rows/classes; no labels/margins/test/CKKS influence',development_logits_sha256=sha(d/'development_logits.json'),model_sha256=sha(d/'model.json')))
        print('quality',seed,tau,float(np.mean(y==p)),flush=True)
def numeric(out):
    values=[]
    for p in sorted(Path(out).glob('key_*.json')):
        ev=read(p);e=np.array([np.array(r['ckks_logits'])-np.array(r['plaintext_logits']) for r in ev['records']]);values.append(dict(key=ev['key_run'],rmse=float(np.sqrt(np.mean(e**2))),max_abs=float(abs(e).max())))
    return values
def pick_roles(seed):
    root=RUN/f'cases/seed_{seed}';dest=root/'FROZEN_SELECTION_ROLES.json'
    if dest.exists():return read(dest)
    plan=read(root/'planning/plan.json');direct=read(root/'direct/result.json');candidates=read(root/'planning/candidates.json');threshold=read(RUN/f'plaintext/seed_{seed}/DEVELOPMENT_QUALITY.json')['numerical_thresholds']
    entries=[]
    for i,c in enumerate(candidates):
        p=root/f'finite/candidate_{i:02d}';t=read(p/'result.json');m=numeric(p);eligible=t['key_repeats_completed']==3 and len(m)==3 and not t.get('failure')
        entries.append(dict(candidate=c,status=t['status'],executable=eligible,mean_total_ms=t['mean_total_ms'],numeric=m,rmse_pass=eligible and all(v['rmse']<=threshold['rmse'] for v in m),max_abs_pass=eligible and all(v['max_abs']<=threshold['max_abs'] for v in m),raw=str(p.relative_to(ROOT))))
    def best(test,key=lambda e:e['mean_total_ms']):
        v=[e for e in entries if test(e)];return min(v,key=key)['candidate'] if v else None
    roles={'initial':plan['initial_candidates'][0],'proposed':direct.get('selected'),'finite_fastest_acceptable':best(lambda e:e['status']=='SAFE'),'finite_fastest_executable':best(lambda e:e['executable']),'numeric_rmse':best(lambda e:e['rmse_pass']),'numeric_max_abs':best(lambda e:e['max_abs_pass'])}
    obj=dict(created_utc=utc(),seed=seed,roles=roles,finite_entries=entries,minimum_max_error_diagnostic=best(lambda e:e['executable'],key=lambda e:max(v['max_abs'] for v in e['numeric'])),minimum_error_audit='not separately required; selection-only diagnostic',thresholds=threshold,finite_analysis='all candidates evaluated; retrospective finite-set argmin, not a bounded online selector',retuning=0,planning_sha256=sha(root/'planning/plan.json'))
    write(dest,obj)
    for name,c in roles.items():
        if c:write(root/f'role_candidates/{name}.json',c)
    return obj
def main():
    a=argparse.ArgumentParser();a.add_argument('--quality',action='store_true');args=a.parse_args()
    quality()
    if args.quality:return
    protocol=read(ROOT/'protocols/FG_EXPAND_V2_MAIN.json');lock=read(RUN/'MAIN_SOURCE_LOCK.json')
    expected=dict(lock['files'])
    for p in sorted(RUN.glob('MAIN_SOURCE_AMENDMENT_*.json')):
        amendment=read(p);assert expected[amendment['path']]==amendment['old_sha256'];expected[amendment['path']]=amendment['new_sha256']
    for p,digest in expected.items():assert sha(ROOT/p)==digest,p
    start=time.monotonic();cap=protocol['resource']['main_wall_cap_seconds'];run_record=RUN/'MAIN_STARTED.json'
    if not run_record.exists():write(run_record,dict(utc=utc(),protocol_sha256=sha(ROOT/'protocols/FG_EXPAND_V2_MAIN.json'),environment=snapshot()))
    def budget():
        used=sum(read(p)['wall_seconds'] for p in (RUN/'commands').glob('*.json')) if (RUN/'commands').exists() else 0
        if used>=cap or snapshot()['disk_free']<8*1024**3:raise RuntimeError('RESOURCE_CAP: preserve incomplete jobs; no success-based stopping')
    # Complete all selection roles for all seeds before the first official-test inference.
    for seed in [0,1,2]:
        root=RUN/f'cases/seed_{seed}';plan=root/'planning/plan.json'
        if not plan.exists():
            budget();code=execute(f'seed{seed}_plan',['--mode','plan','--model',RUN/f'plaintext/seed_{seed}/model.json','--data',RUN/'inputs/selection.csv','--source',RUN/'DATA_SOURCE.json','--out',root/'planning']);assert code==0
        candidates=read(root/'planning/candidates.json')
        for i,c in enumerate(candidates):
            p=root/f'candidate_specs/{i:02d}.json'
            if not p.exists():write(p,c)
        if not (root/'direct/result.json').exists():
            budget();code=execute(f'seed{seed}_direct',['--mode','direct','--plan',plan,'--out',root/'direct']);assert code==0
        order=list(range(len(candidates)))
        if seed==1:order.reverse()
        if seed==2:order=order[2:]+order[:2]
        for i in order:
            out=root/f'finite/candidate_{i:02d}'
            if not (out/'result.json').exists():
                budget();code=execute(f'seed{seed}_finite{i}',['--mode','candidate','--plan',plan,'--candidate',root/f'candidate_specs/{i:02d}.json','--out',out]);assert code==0
        pick_roles(seed)
    frozen={seed:pick_roles(seed) for seed in [0,1,2]}
    audit_jobs=[]
    for batch in range(protocol['audit']['batches']):
        for seed in [0,1,2]:
            root=RUN/f'cases/seed_{seed}';unique={}
            for name,c in frozen[seed]['roles'].items():
                if c:unique.setdefault(c['id'],name)
            order=list(unique.items());shift=(batch+seed)%len(order);order=order[shift:]+order[:shift]
            for cid,name in order:audit_jobs.append((seed,batch,cid,name))
    if not (RUN/'AUDIT_JOB_PLAN.json').exists():write(RUN/'AUDIT_JOB_PLAN.json',dict(locked_before_first_audit_utc=utc(),jobs=audit_jobs,roles_sha256={str(s):sha(RUN/f'cases/seed_{s}/FROZEN_SELECTION_ROLES.json') for s in [0,1,2]}))
    for seed,batch,cid,name in audit_jobs:
        root=RUN/f'cases/seed_{seed}';out=root/f'audit/{cid}/batch_{batch:02d}'
        if not (out/'result.json').exists():
            budget();code=execute(f'seed{seed}_audit{batch}_{name}',['--mode','audit','--plan',root/'planning/plan.json','--candidate',root/f'role_candidates/{name}.json','--data',RUN/f'inputs/audit_{batch:02d}.csv','--out',out]);assert code==0
    for seed in [0,1,2]:
        root=RUN/f'cases/seed_{seed}';roles=frozen[seed]['roles'];proposed=roles['proposed']
        if not proposed:continue
        unique={}
        for name,c in roles.items():
            if name!='proposed' and c:unique.setdefault(c['id'],name)
        for cid,name in unique.items():
            for k in [1,2,3]:
                out=root/f'timing/{cid}/keyset_{k}'
                if not (out/'result.json').exists():
                    budget();code=execute(f'seed{seed}_timing{k}_{name}',['--mode','timing','--plan',root/'planning/plan.json','--candidate',root/'role_candidates/proposed.json','--other',root/f'role_candidates/{name}.json','--data',RUN/'inputs/audit_00.csv','--keyset',k,'--out',out]);assert code==0
    write(RUN/'MAIN_COMPLETED.json',dict(utc=utc(),invocation_wall_seconds=time.monotonic()-start,audit_jobs=len(audit_jobs),automatic_followup=False))
if __name__=='__main__':main()
