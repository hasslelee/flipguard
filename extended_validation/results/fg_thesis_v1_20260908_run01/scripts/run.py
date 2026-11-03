"""Finite serial native schedule; files and failures are append-only."""
from pathlib import Path
import argparse,json,hashlib,os,subprocess,resource,time,signal,datetime,fcntl,collections
ROOT=Path('/home/ckks2/deciprotect');RUN=ROOT/'results/fg_thesis_v1_20260908_run01';SRC=ROOT/'research/thesis_validation_v1';PROTOCOL=ROOT/'protocols/FG_THESIS_V1_20260908.json'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def used():return sum(read(p)['wall_seconds'] for p in (RUN/'commands').glob('*.end.json') if read(p)['charged_native'])
def snapshot():
 mem={s.split(':')[0]:int(s.split(':')[1].strip().split()[0])*1024 for s in Path('/proc/meminfo').read_text().splitlines() if s.split(':')[1].strip().split()[0].isdigit()}
 return {'utc':now(),'available_memory_bytes':mem['MemAvailable'],'free_disk_bytes':os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize,'load':os.getloadavg()}
def limits():resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
def call(name,args,bank=False,charged=True):
 stem=RUN/'commands'/name;end=Path(str(stem)+'.end.json');out=Path(args[args.index('--out')+1]);result=out/'result.json'
 if end.exists():return read(result) if result.exists() else None
 assert not result.exists(),('orphan result',result)
 verify();sp=read(PROTOCOL);ss=snapshot();remaining=sp['resource']['native_total_cap_seconds']-used()
 if remaining<=0 or ss['available_memory_bytes']<2*1024**3 or ss['free_disk_bytes']<8*1024**3:raise RuntimeError('RESOURCE_STOP')
 # Never launch a full-duration call beyond the remaining cumulative cap.
 timeout=min(1800,remaining) if charged else 120
 command=[str(RUN/'bin'/('bank-case' if bank else 'contribution-case')),*map(str,args)]
 write(Path(str(stem)+'.start.json'),{'command':command,'cwd':str(ROOT),'environment':ss,'timeout_seconds':timeout,'charged_native':charged,'source_lock_sha256':sha(RUN/'SOURCE_LOCK.json'),'protocol_sha256':sha(PROTOCOL)})
 start=time.monotonic()
 with Path(str(stem)+'.log').open('x') as log:
  proc=subprocess.Popen(['/usr/bin/time','-v',*command],cwd=ROOT,env={**os.environ,'GOMAXPROCS':'4','GOMEMLIMIT':'6GiB','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT,preexec_fn=limits,start_new_session=True)
  try:code=proc.wait(timeout=timeout)
  except subprocess.TimeoutExpired:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
   code=124
 elapsed=time.monotonic()-start
 write(end,{'command':command,'exit_code':code,'wall_seconds':elapsed,'charged_native':charged,'result_exists':result.exists(),'before':ss,'after':snapshot(),'status':'COMPLETED' if code==0 else 'EXECUTION_FAILURE'})
 print(json.dumps({'job':name,'exit':code,'seconds':round(elapsed,3),'native_hours':round(used()/3600,3)}),flush=True)
 return read(result) if result.exists() else None
def lock():
 paths=[p for p in SRC.rglob('*') if p.is_file() and p.suffix in ['.go','.mod','.sum']]+list((RUN/'bin').iterdir())+[PROTOCOL]
 spec=read(PROTOCOL)
 for c in spec['cases']:
  paths += [Path(c[k]) for k in ['model','plan','selection','development']]
  paths += [Path(x) for x in c['audit'][:2]]
 paths += [Path(s['raw']) for s in spec['A3']['subsets']]
 write(RUN/'SOURCE_LOCK.json',{'utc':now(),'files':{str(p):sha(p) for p in sorted(set(paths))},'reserved_audit_payload_opened':False})
def verify():
 if (RUN/'EXECUTION_BINDING.json').exists():
  for p,h in read(RUN/'EXECUTION_BINDING.json')['files'].items():assert sha(Path(p))==h,('EXECUTION_BINDING_MISMATCH',p)
 for p,h in read(RUN/'SOURCE_LOCK.json')['files'].items():assert sha(Path(p))==h,('SOURCE_LOCK_MISMATCH',p)
def schedule():
 sp=read(PROTOCOL);cs={c['case_id']:c for c in sp['cases']};jobs=[]
 for ci,cid in enumerate(sp['A2']['cases']):
  st=sp['settings'][ci:]+sp['settings'][:ci]
  for s in st:jobs.append({'id':f"A2_{cid}_{s['id']}",'phase':'A2','case':cid,'role':'C','block':0,'rho':s['rho'],'delta':s['delta'],'setting':s['id'],'data':None})
 for s in sp['A3']['subsets']:
  jobs.append({'id':f"A3_{s['case_id']}_order{s['input_order_seed']}_n{s['n']}",'phase':'A3','case':s['case_id'],'role':'C','block':0,'rho':.5,'delta':.001,'setting':f"order{s['input_order_seed']}_n{s['n']}",'data':s['prepared'],'n':s['n'],'input_order_seed':s['input_order_seed']})
 for block in range(2):
  for ci,cid in enumerate(sp['B']['cases']):
   roles=sp['B']['roles'][:];shift=(ci+block)%len(roles);roles=roles[shift:]+roles[:shift]
   if block:roles.reverse()
   for role in roles:jobs.append({'id':f'B_{cid}_block{block}_{role}','phase':'B','case':cid,'role':role,'block':block,'rho':.5,'delta':.001,'setting':'base','data':None})
 write(RUN/'NATIVE_SCHEDULE.json',{'created_utc':now(),'selection_jobs':jobs,'audit_policy':sp['B']['audits'],'timing':sp['timing'],'conditional_aux':'B30slack static feasibility recorded; if identical to B30 retain alias rather than extra independent audit'})
def static():
 for c in read(PROTOCOL)['cases']:
  for variant in ['C','Cprime']:
   args=['--mode','plan','--legacy-plan',c['plan'],'--out',RUN/'static'/c['case_id']/variant]
   if variant=='Cprime':args+=['--cprime']
   call(f"static_{c['case_id']}_{variant}",args,c['kind']=='bank',False)
def materialize():
 for s in read(PROTOCOL)['A3']['subsets']:
  c=next(c for c in read(PROTOCOL)['cases'] if c['case_id']==s['case_id'])
  call(f"materialize_{s['case_id']}_{s['input_order_seed']}_{s['n']}",['--mode','materialize','--model',c['model'],'--data',s['raw'],'--out',Path(s['prepared']).parent],charged=False)
def select(phase):
 assert (RUN/'A1_COMPLETED.json').exists(),'A1 before new HE'
 cs={c['case_id']:c for c in read(PROTOCOL)['cases']}
 for j in read(RUN/'NATIVE_SCHEDULE.json')['selection_jobs']:
  if j['phase']!=phase:continue
  c=cs[j['case']];role=j['role'];args=['--mode','select','--legacy-plan',c['plan'],'--role','C' if role=='Cprime' else 'B' if role.startswith('B30') else role,'--keyset',str(j['block']),'--rho',str(j['rho']),'--delta',str(j['delta']),'--out',RUN/'selection'/j['id']]
  if j['data']:args+=['--data',j['data']]
  if role=='Cprime':args+=['--cprime']
  if role=='B30slack':args+=['--b-slack']
  call(j['id'],args,c['kind']=='bank')
def freeze():
 records=[];by=collections.defaultdict(dict)
 for j in read(RUN/'NATIVE_SCHEDULE.json')['selection_jobs']:
  p=RUN/'selection'/j['id']/'result.json'
  if not (RUN/'commands'/f"{j['id']}.end.json").exists():raise RuntimeError('selection not attempted: '+j['id'])
  r=read(p) if p.exists() else {};c=r.get('selected');rec={**j,'result':str(p),'outcome':r.get('outcome','EXECUTION_FAILURE'),'result_sha256':sha(p) if p.exists() else None,'literal_id':None}
  if c:
   lid=hashlib.sha256(json.dumps({'parameters':c['parameters'],'path':c['path']},sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]
   candpath=RUN/'frozen'/j['case']/(lid+'.json')
   if not candpath.exists():write(candpath,c)
   rec['literal_id']=lid;rec['candidate_path']=str(candpath);rec['candidate_sha256']=sha(candpath)
  records.append(rec)
 write(RUN/'FROZEN_SELECTIONS.json',{'utc':now(),'protocol_sha256':sha(PROTOCOL),'source_lock_sha256':sha(RUN/'SOURCE_LOCK.json'),'records':records,'reserved_audit_not_opened':True,'post_freeze_retuning':False})
if __name__=='__main__':
 import collections
 ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['lock','schedule','static','materialize','A2','A3','B','freeze']);a=ap.parse_args()
 with (RUN/'native.lock').open('a') as f:
  fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  if a.phase in ['lock','schedule','static','materialize','freeze']:globals()[a.phase]()
  else:select(a.phase)
