"""Continue exactly A3/B/freeze after the currently running A2 schedule."""
from pathlib import Path
import json,time,subprocess,os
R=Path('/home/ckks2/deciprotect/results/fg_thesis_v1_20260908_run01');ROOT=R.parents[1]
jobs=json.load(open(R/'NATIVE_SCHEDULE.json'))['selection_jobs']
deadline=time.monotonic()+86400
while not all((R/'commands'/(j['id']+'.end.json')).exists() for j in jobs if j['phase']=='A2'):
 if time.monotonic()>deadline:raise RuntimeError('A2 continuation deadline; no new experiment')
 time.sleep(10)
for phase in ['A3','B','freeze']:
 print('START_FIXED_PHASE',phase,flush=True)
 subprocess.run(['python3',str(R/'scripts/run.py'),phase],cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},check=True)
print('ALL_SELECTIONS_FROZEN; RESERVED_AUDIT_NOT_OPENED',flush=True)
