"""Only the already approved post-selection stages. No retry or further experiment generation."""
from pathlib import Path
import subprocess,time,sys,os
RUN=Path(__file__).resolve().parents[1];ROOT=RUN.parents[1]
while not (RUN/'FROZEN_SELECTIONS.json').exists():time.sleep(10)
for script,args in [('audit.py',['prepare']),('audit.py',['audit']),('audit.py',['timing']),('size_probe.py',[])]:
    cmd=[sys.executable,str(RUN/'scripts'/script),*args]
    p=subprocess.run(cmd,cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    if p.returncode:raise SystemExit(p.returncode)
