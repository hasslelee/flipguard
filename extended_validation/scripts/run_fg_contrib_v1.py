#!/usr/bin/env python3
"""Finite serial experiment driver. Scientific failures are durable results."""
import argparse, datetime, fcntl, hashlib, json, os, resource, signal, subprocess, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'results/fg_contrib_v1_20260906_run01'
BIN=ROOT/'bin/contribution-case'
PROTOCOL=ROOT/'protocols/FG_CONTRIB_V1.json'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def snapshot():
 mem={l.split(':')[0]:l.split(':')[1].strip() for l in Path('/proc/meminfo').read_text().splitlines()}
 return dict(utc=utc(),load=os.getloadavg(),mem_available=mem['MemAvailable'],swap_free=mem['SwapFree'],free_disk=os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize)
def limit():resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
def used_seconds():return sum(read(p)['wall_seconds'] for p in (RUN/'commands').glob('*.end.json'))
def check_budget():
 s=read(PROTOCOL)['resource']
 if used_seconds()>=s['native_total_cap_seconds']:raise RuntimeError('RESOURCE_CAP native wall')
 if snapshot()['free_disk']<s['minimum_free_disk_gib']*1024**3:raise RuntimeError('RESOURCE_CAP free disk')
 if sum(p.stat().st_size for p in RUN.rglob('*') if p.is_file())>s['storage_cap_gib']*1024**3:raise RuntimeError('RESOURCE_CAP new storage')
def call(name,args,timeout=1800):
 out=Path(args[args.index('--out')+1]);result=out/'result.json'
 if result.exists():return read(result)
 stem=RUN/'commands'/name;end=Path(str(stem)+'.end.json')
 if end.exists():return None  # preserve failed call; never silently retry with favourable fresh keys
 check_budget();stem.parent.mkdir(exist_ok=True);command=[str(BIN),*map(str,args)]
 before=snapshot();write(Path(str(stem)+'.start.json'),dict(command=command,cwd=str(ROOT),environment=before,binary_sha256=sha(BIN),source_lock_sha256=sha(RUN/'SOURCE_LOCK.json')))
 begin=time.monotonic()
 with Path(str(stem)+'.log').open('x') as log:
  p=subprocess.Popen(['/usr/bin/time','-v',*command],cwd=ROOT,env={**os.environ,'GOMAXPROCS':'4','GOMEMLIMIT':'6GiB','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT,preexec_fn=limit,start_new_session=True)
  try:code=p.wait(timeout=timeout);status='PROCESS_COMPLETED' if code==0 else 'EXECUTION_FAILURE'
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   code=124;status='TIMEOUT'
 rec=dict(command=command,exit_code=code,status=status,wall_seconds=time.monotonic()-begin,before=before,after=snapshot(),result_exists=result.exists())
 write(end,rec);print(json.dumps(dict(job=name,status=status,wall_seconds=round(rec['wall_seconds'],3))),flush=True)
 if code and 'identity mismatch' in Path(str(stem)+'.log').read_text():raise RuntimeError('INTEGRITY_BLOCK identity mismatch')
 return read(result) if result.exists() else None
def literal_id(c):return hashlib.sha256(json.dumps(c['parameters'],sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]
def lock():
 paths=[p for p in (ROOT/'research/contribution_validation').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
 paths += [BIN,PROTOCOL,Path(__file__).resolve(),ROOT/'scripts/prepare_fg_contrib_v1.py',RUN/'INPUT_BINDINGS.json']
 write(RUN/'SOURCE_LOCK.json',dict(utc=utc(),files={str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)},start_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),build_command='GOMAXPROCS=4 go -C research/contribution_validation build -o ../../bin/contribution-case ./cmd/contribution-case'))
def verify():
 for f,h in read(RUN/'SOURCE_LOCK.json')['files'].items():assert sha(ROOT/f)==h,('SOURCE_LOCK_MISMATCH',f)
 for f,h in read(RUN/'INPUT_BINDINGS.json').items():assert sha(ROOT/f)==h,('INPUT_BINDING_MISMATCH',f)
def generate(c,scale,guard=0,tag='diagnostic'):
 out=RUN/'cases'/c['case_id']/tag/f'S{scale}_Qguard{guard}'
 r=call(f"{c['case_id']}_{tag}_generate_S{scale}_Q{guard}",['--mode','generate','--legacy-plan',c['plan'],'--scale',str(scale),'--q-guard',str(guard),'--out',out/'generation'])
 if r and not r['failure']:
  p=out/'candidate.json'
  if not p.exists():write(p,r['candidate'])
  return p
 return None
def preflight(spec):
 dest=RUN/'PREFLIGHT.json'
 if dest.exists():return
 candidates={}
 for c in spec['cases']:candidates[c['case_id']]=generate(c,30,tag='preflight')
 results=[]
 for c in [spec['cases'][0],spec['cases'][4]]:
  p=candidates[c['case_id']]
  if p is None:results.append(dict(case_id=c['case_id'],status='GENERATION_FAILURE'));continue
  out=RUN/'preflight'/c['case_id']
  if c['kind']=='tabular':
   data=ROOT/'results/fg_expand_v1_20260905_run01/preflight'/c['case_id']/'smoke.prepared.csv'
   args=['--mode','audit','--legacy-plan',c['plan'],'--candidate',p,'--data',data,'--out',out]
  else:
   plan=ROOT/'results/fg_expand_v2_20260905_run01/development/seed_0_plan/plan.json'
   args=['--mode','candidate','--legacy-plan',plan,'--candidate',p,'--out',out]
  r=call(c['case_id']+'_plumbing',args);results.append(dict(case_id=c['case_id'],status=r['status'] if r else 'EXECUTION_FAILURE',keys=r['keys'] if r else 0))
 write(dest,dict(utc=utc(),adapters=results,static_cases=len(candidates),scientific_rejection_allowed=True,plumbing_complete=all(r.get('keys')==3 for r in results)))
 if not all(r.get('keys')==3 for r in results):raise RuntimeError('PREFLIGHT infrastructure needs inspection')
def select(spec):
 for block in range(spec['selection']['blocks']):
  for ci,c in enumerate(spec['cases']):
   order=spec['roles'][:];shift=(ci+block)%len(order);order=order[shift:]+order[:shift]
   if block==1:order.reverse()
   for role in order:
    out=RUN/'cases'/c['case_id']/f'selection/block_{block}'/role['id']
    args=['--mode','select','--legacy-plan',c['plan'],'--role',role['role'],'--threshold',str(c['thresholds']['max_abs']),'--keyset',str(block),'--out',out]
    if role['start_scale'] is not None:args+=['--start-scale',str(role['start_scale'])]
    call(f"{c['case_id']}_select_b{block}_{role['id']}",args)
 freeze(spec)
def freeze(spec):
 dest=RUN/'FROZEN_SELECTIONS.json'
 if dest.exists():return read(dest)
 cases=[];hashes={}
 for c in spec['cases']:
  unique={};roles=[];reference=None
  def add(candidate,role):
   if not candidate:return None
   lid=literal_id(candidate)
   if lid not in unique:
    p=RUN/'cases'/c['case_id']/'frozen_candidates'/f'{lid}.json';write(p,candidate)
    unique[lid]=dict(literal_id=lid,candidate=candidate,path=str(p),roles=[])
   unique[lid]['roles'].append(role);return lid
  for block in range(spec['selection']['blocks']):
   for role in spec['roles']:
    p=RUN/'cases'/c['case_id']/f'selection/block_{block}'/role['id']/'result.json';r=read(p) if p.exists() else None
    if p.exists():hashes[str(p.relative_to(ROOT))]=sha(p)
    lid=add(r.get('selected') if r else None,f"block{block}/{role['id']}")
    roles.append(dict(block=block,role=role['id'],literal_id=lid,outcome=r['outcome'] if r else 'INCOMPLETE'))
    if role['id']=='C' and reference is None and lid:reference=lid
  if c['case_id'].startswith('spambase__linear'):
   for label in ['numeric','proposed']:add(read(RUN/f'legacy_fixed/{label}.json'),'legacy_fixed_'+label)
  cases.append(dict(case_id=c['case_id'],roles=roles,unique=unique,reference_C=reference))
 result=dict(utc=utc(),cases=cases,selection_result_hashes=hashes,retuning=0,all_selections_precede_audit=True)
 write(dest,result);return result
def diagnostic(spec):
 assert (RUN/'FROZEN_SELECTIONS.json').exists()
 for scale in spec['diagnostic']['scales']:
  for c in spec['cases']:
   p=generate(c,scale)
   if p:
    out=p.parent/'execution';call(f"{c['case_id']}_diagnostic_S{scale}",['--mode','candidate','--legacy-plan',c['plan'],'--candidate',p,'--out',out])
 for c in spec['cases']:
  for block in range(2):
   for rid,start in [('B30',30),('B40',40)]:
    p=RUN/'cases'/c['case_id']/f'selection/block_{block}'/rid/'result.json'
    if not p.exists() or read(p)['selected'] is not None:continue
    for step in [4,5]:
     scale=start+4*step
     if scale>52:continue
     tag=f'extra_b{block}_{rid}';cand=generate(c,scale,tag=tag)
     if cand:call(f"{c['case_id']}_{tag}_S{scale}",['--mode','candidate','--legacy-plan',c['plan'],'--candidate',cand,'--out',cand.parent/'execution'])
def audit(spec):
 frozen=freeze(spec);by={c['case_id']:c for c in frozen['cases']};jobs=[]
 for batch in range(20):
  for ci,c in enumerate(spec['cases']):
   if batch>=len(c['audit']):continue
   order=list(by[c['case_id']]['unique'].values())
   if not order:continue
   shift=(batch+ci)%len(order);order=order[shift:]+order[:shift]
   for u in order:jobs.append(dict(case=c['case_id'],batch=batch,literal_id=u['literal_id'],candidate=u['path'],data=c['audit'][batch],plan=c['plan']))
 p=RUN/'AUDIT_JOBS.json'
 if not p.exists():write(p,dict(utc=utc(),selection_sha256=sha(RUN/'FROZEN_SELECTIONS.json'),jobs=jobs))
 for j in jobs:
  out=RUN/'cases'/j['case']/f"audit/{j['literal_id']}/batch_{j['batch']:02d}"
  call(f"{j['case']}_audit_{j['literal_id']}_b{j['batch']:02d}",['--mode','audit','--legacy-plan',j['plan'],'--candidate',j['candidate'],'--data',j['data'],'--out',out])
def timing(spec):
 frozen=freeze(spec);by={c['case_id']:c for c in frozen['cases']};jobs=[]
 for k in [1,2,3]:
  for c in spec['cases']:
   f=by[c['case_id']];ref=f['reference_C'];unique=f['unique'];pairs=[]
   if ref:
    others=[v for v in unique if v!=ref] or [ref]
    pairs=[(ref,v,'main') for v in others]
   if c['case_id'].startswith('spambase__linear'):
    a=literal_id(read(RUN/'legacy_fixed/proposed.json'));b=literal_id(read(RUN/'legacy_fixed/numeric.json'))
    if not any(x==a and y==b for x,y,_ in pairs):pairs.append((a,b,'legacy_fixed'))
   for a,b,label in pairs:jobs.append(dict(case=c['case_id'],key=k,reference=a,comparator=b,label=label,plan=c['plan'],data=c['audit'][0],candidate=unique[a]['path'],other=unique[b]['path']))
 p=RUN/'TIMING_JOBS.json'
 if not p.exists():write(p,dict(utc=utc(),jobs=jobs))
 for j in jobs:
  tag=f"{j['reference']}_vs_{j['comparator']}";out=RUN/'cases'/j['case']/f"timing/{tag}/key_{j['key']}"
  call(f"{j['case']}_timing_{tag}_k{j['key']}",['--mode','timing','--legacy-plan',j['plan'],'--candidate',j['candidate'],'--other',j['other'],'--data',j['data'],'--keyset',str(j['key']),'--out',out])
def main():
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['lock','preflight','select','diagnostic','audit','timing','internal']);a=p.parse_args()
 if a.phase=='lock':lock();return
 lease=ROOT/'work/fg_contrib_v1_20260906/native.lock';lease.parent.mkdir(exist_ok=True);f=lease.open('a');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 verify();spec=read(PROTOCOL)
 phases=['preflight','select','diagnostic','audit','timing'] if a.phase=='internal' else [a.phase]
 for phase in phases:
  started=utc()
  try:globals()[phase](spec)
  except Exception as e:
   p=RUN/f'STOP_{phase}_{time.time_ns()}.json';write(p,dict(utc=utc(),error=repr(e),phase=phase,automatic_followup=False));raise
  dest=RUN/f'{phase.upper()}_PHASE_COMPLETED.json'
  if not dest.exists():write(dest,dict(started=started,finished=utc(),native_seconds_so_far=used_seconds(),completion_means_schedule_exhausted_not_scientific_success=True))
if __name__=='__main__':main()
