"""Record the approved non-CKKS reducers, document generation and local verification."""
from pathlib import Path
import sys,os,subprocess,time
import run as r
steps={
 'analyze':[('analyze_new.py',[]),('analyze_timing.py',[]),('plot_results.py',[])],
 'analyze_timing_fix':[('analyze_timing.py',[]),('plot_results.py',[])],
 'draft':[('write_reports.py',[])],
 'finalize':[('update_sync.py',[]),('verify_final.py',[]),('package.py',[]),('verify_final.py',['--check-only'])],
}
phase=sys.argv[1];assert phase in steps
assert (r.RUN/'MATERIAL_SIZE_COMPLETED.json').exists(),'finish finite native stages first'
folder=r.RUN/'postprocess_log';folder.mkdir(exist_ok=True)
for i,(script,args) in enumerate(steps[phase],1):
 executable=str(r.ROOT/'.venv/bin/python') if script=='plot_results.py' else sys.executable
 cmd=[executable,str(r.RUN/'scripts'/script),*args]
 name=f'{phase}_{i}_{Path(script).stem}'
 assert not (folder/(name+'.end.json')).exists(),'preserve completed postprocessing'
 r.write(folder/(name+'.start.json'),{'utc':r.now(),'command':cmd,'cwd':str(r.ROOT),'source_sha256':r.sha(r.RUN/'scripts'/script),'new_CKKS':False})
 t=time.monotonic()
 with (folder/(name+'.log')).open('x') as f:
  proc=subprocess.run(cmd,cwd=r.ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=f,stderr=subprocess.STDOUT)
 elapsed=time.monotonic()-t
 r.write(folder/(name+'.end.json'),{'utc':r.now(),'command':cmd,'exit_code':proc.returncode,'wall_seconds':elapsed,'log_sha256':r.sha(folder/(name+'.log')),'new_CKKS':False})
 print(name,proc.returncode,round(elapsed,3),flush=True)
 print((folder/(name+'.log')).read_text(),flush=True)
 if proc.returncode:raise SystemExit(proc.returncode)
