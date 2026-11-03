"""One serial public-material size measurement per distinct selected literal."""
from pathlib import Path
import os,sys,subprocess,time,fcntl
import run as r
import audit

def main():
    audit.verify_preopen();seen=set()
    for x in r.read(r.RUN/'FROZEN_SELECTIONS.json')['records']:
        key=(x['case'],x['literal_id'])
        if not x['literal_id'] or key in seen:continue
        seen.add(key);audit.size_guard()
        target=r.read(x['candidate_path'])['parameters']
        matches=[p for p in Path(x['result']).parent.glob('concrete_*.json') if r.read(p)['declared']==target]
        assert matches;public=matches[0]
        name='size_'+x['case']+'_'+x['literal_id'];stem=r.RUN/'commands'/name
        if Path(str(stem)+'.end.json').exists():continue
        remaining=86400-r.used();assert remaining>60
        ss=r.snapshot();assert ss['available_memory_bytes']>2*1024**3 and ss['free_disk_bytes']>8*1024**3
        out=r.RUN/'material_sizes'/x['case']/(x['literal_id']+'.json');out.parent.mkdir(parents=True,exist_ok=True)
        cmd=[str(r.RUN/'bin/size-probe'),'--concrete',str(public),'--out',str(out)]
        r.write(Path(str(stem)+'.start.json'),{'command':cmd,'before':ss,'charged_native':True,
            'preopen_sha256':r.sha(r.RUN/'AUDIT_PREOPEN_LOCK.json'),'public_parameter_sha256':r.sha(public)})
        t=time.monotonic()
        with Path(str(stem)+'.log').open('x') as f:
            try:
                p=subprocess.run(['/usr/bin/time','-v',*cmd],cwd=r.ROOT,stdout=f,stderr=subprocess.STDOUT,
                    env={**os.environ,'GOMAXPROCS':'4','GOMEMLIMIT':'6GiB'},preexec_fn=r.limits,timeout=60);code=p.returncode
            except subprocess.TimeoutExpired:code=124
        elapsed=time.monotonic()-t
        r.write(Path(str(stem)+'.end.json'),{'command':cmd,'exit_code':code,'wall_seconds':elapsed,
            'charged_native':True,'status':'COMPLETED' if code==0 else 'EXECUTION_FAILURE','before':ss,'after':r.snapshot(),'result_exists':out.exists()})
        print(name,code,round(elapsed,3),flush=True)
    r.write(r.RUN/'MATERIAL_SIZE_COMPLETED.json',{'unique_case_literals':len(seen),'utc':r.now(),
        'scope':'separate material probes; degree1 ciphertext level sizes, actual public/relinearization keys; no secret serialization or network measurement'})

if __name__=='__main__':
    with (r.RUN/'native.lock').open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);main()
