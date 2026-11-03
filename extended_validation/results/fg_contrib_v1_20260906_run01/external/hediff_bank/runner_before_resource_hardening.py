#!/usr/bin/env python3
"""One bounded official HEDiff problem case, serialized with internal CKKS."""
import csv,fcntl,json,os,signal,subprocess,time
from pathlib import Path
from run_fg_contrib_v1 import ROOT,RUN,PROTOCOL,read,write,sha,utc,snapshot,check_budget,call,literal_id,verify

IMAGE='flipguard/mlir16-seal4:audit-v1';PKG=ROOT/'work/fg_contrib_v1_20260906/external_packages';OUT=RUN/'external/hediff_bank';WORK=ROOT/'work/fg_contrib_v1_20260906'
def docker(args,network='none'):
 return ['docker','run','--rm','--network',network,'--cpus','4','--memory','8g','--user',f'{os.getuid()}:{os.getgid()}','-v',f'{ROOT}:{ROOT}','-w',str(ROOT),'-e',f'PYTHONPATH={PKG}','-e','PYTHONDONTWRITEBYTECODE=1','-e','OPENBLAS_NUM_THREADS=1','-e','OMP_NUM_THREADS=4','--entrypoint','python3',IMAGE,*map(str,args)]
def run_command(name,cmd,timeout):
 stem=RUN/'commands'/name;end=Path(str(stem)+'.end.json')
 if end.exists():return read(end)['exit_code']
 check_budget();stem.parent.mkdir(exist_ok=True);write(Path(str(stem)+'.start.json'),dict(command=cmd,cwd=str(ROOT),environment=snapshot(),source_lock_sha256=sha(OUT/'EXTERNAL_PROTOCOL.json')));begin=time.monotonic()
 with Path(str(stem)+'.log').open('x') as log:
  p=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  try:code=p.wait(timeout=timeout);status='PROCESS_COMPLETED' if code==0 else 'EXECUTION_FAILURE'
  except subprocess.TimeoutExpired:
   # docker run is synchronous; stop named containers is avoided. kill process
   # group then preserve timeout. No research is started after such a failure.
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   code=124;status='TIMEOUT'
 write(end,dict(command=cmd,exit_code=code,status=status,wall_seconds=time.monotonic()-begin,after=snapshot(),result_exists=False));print(name,status,flush=True);return code
def elapsed_external():
 return sum(read(p)['wall_seconds'] for p in (RUN/'commands').glob('external_*.end.json'))
def stage_budget():
 if elapsed_external()>8400:raise RuntimeError('EXTERNAL_BUDGET: connection1200 plus native7200 exhausted')
def prepare_protocol():
 OUT.mkdir(parents=True,exist_ok=True);p=OUT/'EXTERNAL_PROTOCOL.json'
 if p.exists():return
 sources=[q for q in (WORK/'hediff_source').glob('*.py')]+[WORK/'HEDiff_tree.json',WORK/'elasm_tree.json',WORK/'external_data/SOURCE.json',WORK/'external_data/bank-additional-full.csv',ROOT/'scripts/hediff_bank_contrib_v1.py',Path(__file__).resolve()]
 spec=dict(protocol_id='FG_CONTRIB_V1_EXTERNAL_HEDIFF_BANK_20260906',parent_protocol_sha256=sha(PROTOCOL),locked_utc=utc(),implementation='official reviewed class and train/test methods extracted without top-level side effects; original pretrained weights and .npy are absent',model='20->256, t*t+t, ->2; public100epoch Adam, batch64, shuffleFalse, seed20260906',why='same polynomial in original plaintext and official CKKS; public small trainer; no sigmoid approximation, convolution compiler or bootstrapping development',official_commit='ffeed7f131d4b55698a08798927777b44f508099',elasm_review_commit='3c37c11b29ca480525bb6681e0254bdf90029425',image_id='sha256:1a8881917d4262312b7263d66139dbb4550a5d43f796a04dcecaa55c99f9c1ff',image_python='3.10.12',package_plan={'torch':'1.13.1+cpu','tenseal':'0.3.14','numpy':'1.23.5','scikit-learn':'1.1.3','imbalanced-learn':'0.12.3','pandas':'2.1.1'},connection_attempts=3,connection_seconds=1200,native_seconds=7200,source_bindings={str(p.relative_to(ROOT)):sha(p) for p in sources},input_rule='official normalization/NearMiss/shuffle42 then final20percent test; selection positions0..15, audit16..47, development48..175; training original80percent, no checkpoint/seed selection',test_exposure='official full-source preprocessing and NearMiss precede split; accuracy descriptive, not leakage-free independent prediction confirmation',threshold='development-only maxabs FP16 roundtrip of common scalar score; RMSE secondary; no CKKS/audit-based adjustment',projection={'z':'original_logit0-original_logit1','score':'.5+.197*z','binary_label':'1-original_label','tie':'binary>=.5 maps to original0, same lowest-index tie','hidden_identity':'t*t+t=(t+.5)^2-.25','numeric_meaning':'same real polynomial score; original float32 rounding vs common float64 and algebraic execution differences recorded separately'},original_ckks={'log_n':13,'prime_bits':[31,26,26,26,26,26,26,31],'scale':26,'galois_keys':True,'own_condition':'SEAL default128; original settings preserved','common_security_alignment':'NOT_IDENTICAL: QP218 exceeds frozen V2N13 limit214; do not apply a cross-backend performance or identical-security claim'},common_selection={'roles':['B','C','A'],'start_scale_AB':30,'blocks':1,'keys':3,'max_candidates':4,'meaning':'same independent A/B and unchanged C on exact scalar projection; one external exploratory block, no two-block stability claim'},audit={'keys':3,'inputs':32,'aliases':'one per parameter-distinct selected config','native_original_first_selection':True,'all_method_selection_frozen_before_audit':True},stress={'inputs':16,'first_audit_positions':list(range(16,32)),'keys':3,'steps':20,'radius':.05,'step':.05/20,'categorical_columns_frozen':[1,2,3,4,5,6,7,8,9,14],'validity':'normalized coordinate-box diagnostic only; no assertion of real customer feasibility or synthetic labels','HE_feedback':False},timing={'common_backend_only':True,'inputs':2,'input_rule':'first2 fixed audit inputs','warmup':1,'measure':6,'key_blocks':3,'reason_for_two_inputs':'256-hidden-unit scalar backend is much more expensive; predeclared external diagnostic reduction applied equally to all arms; original timing scheduler otherwise unchanged','original_vs_common_timing_causal_claim':False},new_compiler=False,new_bootstrap=False,expected_native_seconds=[3600,7200],resource_stop='preserve remaining jobs as incomplete; no favourable-result extension')
 write(p,spec)
def setup():
 complete=OUT/'CONNECTION_COMPLETE.json'
 if complete.exists():return True
 PKG.mkdir(parents=True,exist_ok=True);start=elapsed_external();limit=1200
 packages=['numpy==1.23.5','scipy==1.10.1','scikit-learn==1.1.3','pandas==2.1.1','imbalanced-learn==0.12.3','tenseal==0.3.14','tqdm==4.66.5','typing_extensions==4.12.2']
 for attempt in range(1,4):
  remaining=limit-(elapsed_external()-start)
  if remaining<=0:break
  install=['-m','pip','install','--disable-pip-version-check','--no-cache-dir','--retries','1','--timeout','30','--target',PKG,*packages]
  code=run_command(f'external_connect{attempt}_packages',docker(install,'bridge'),min(600,remaining))
  if code:continue
  remaining=limit-(elapsed_external()-start)
  if remaining<=0:break
  install=['-m','pip','install','--disable-pip-version-check','--no-cache-dir','--no-deps','--retries','1','--timeout','30','--target',PKG,'torch==1.13.1+cpu','--index-url','https://download.pytorch.org/whl/cpu']
  code=run_command(f'external_connect{attempt}_torch',docker(install,'bridge'),min(600,remaining))
  if code:continue
  code=run_command(f'external_connect{attempt}_imports',docker(['-c','import torch,tenseal,numpy,pandas,sklearn,imblearn;print(torch.__version__,tenseal.__version__,numpy.__version__,pandas.__version__,sklearn.__version__,imblearn.__version__)']),60)
  if not code:write(complete,dict(attempt=attempt,seconds=elapsed_external()-start,utc=utc(),compiled_new_compiler=False));return True
 write(OUT/'CONNECTION_BLOCKED.json',dict(utc=utc(),reason='bounded original-compatible library connection failed; internal comparison retained',attempt_budget=3,seconds=elapsed_external()-start));return False
def main():
 prepare_protocol()
 lease=(WORK/'native.lock').open('a');print('waiting for serial native lease',flush=True);fcntl.flock(lease,fcntl.LOCK_EX)
 verify()
 if not (RUN/'TIMING_PHASE_COMPLETED.json').exists():raise RuntimeError('internal pipeline did not finish; inspect before external heavy work')
 if not setup():return
 script=ROOT/'scripts/hediff_bank_contrib_v1.py'
 if not (OUT/'TRAINING_COMPLETE.json').exists():
  stage_budget();code=run_command('external_train_public_procedure',docker([script,'train']),1200)
  if code:write(OUT/'MODEL_BLOCKED.json',dict(reason='public procedure training or semantics check failed; no seed/architecture replacement',exit_code=code));return
 stage_budget();code=run_command('external_native_selection',docker([script,'selection']),1200)
 if code:write(OUT/'NATIVE_BLOCKED.json',dict(reason='official CKKS selection-input execution failed',exit_code=code));return
 for role in ['configuration_selection','independent_evaluation','stress']:
  call('external_materialize_'+role,['--mode','materialize','--model',OUT/'model.json','--data',OUT/(role+'.csv'),'--out',OUT/'materialized'/role])
 sel=OUT/'materialized/configuration_selection/prepared.csv';call('external_plan',['--mode','new-plan','--model',OUT/'model.json','--data',sel,'--out',OUT/'planning']);plan=OUT/'planning/plan.json'
 if not plan.exists():write(OUT/'COMMON_BLOCKED.json',dict(reason='exact projection unsupported by unchanged contract/planner'));return
 tau=read(OUT/'INPUT_MODEL_LOCK.json')['numeric_thresholds']['max_abs'];roles={}
 for role in ['B','C','A']:
  stage_budget();r=call('external_select_'+role,['--mode','select','--legacy-plan',plan,'--role',role,'--start-scale','30','--threshold',str(tau),'--keyset','0','--out',OUT/'selection'/role]);roles[role]=r.get('selected') if r else None
 unique={}
 for role,c in roles.items():
  if not c:continue
  lid=literal_id(c)
  if lid not in unique:
   p=OUT/'candidates'/f'{lid}.json'
   if not p.exists():write(p,c)
   unique[lid]=dict(candidate=c,path=str(p),roles=[])
  unique[lid]['roles'].append(role)
 frozen=OUT/'FROZEN_SELECTION.json'
 if not frozen.exists():write(frozen,dict(utc=utc(),roles=roles,unique=unique,no_retuning=True))
 for stage in ['audit','stress']:
  stage_budget();run_command('external_native_'+stage,docker([script,stage]),1200)
 for lid,u in unique.items():
  stage_budget();call('external_audit_'+lid,['--mode','audit','--legacy-plan',plan,'--candidate',u['path'],'--data',OUT/'materialized/independent_evaluation/prepared.csv','--out',OUT/'audit'/lid])
 for lid,u in unique.items():
  stage_budget();call('external_stress_'+lid,['--mode','raw-stress','--legacy-plan',plan,'--candidate',u['path'],'--data',OUT/'materialized/stress/prepared.csv','--out',OUT/'stress'/lid])
 ref=roles.get('C')
 if ref:
  data=OUT/'paired_two_inputs.csv'
  if not data.exists():
   lines=(OUT/'materialized/independent_evaluation/prepared.csv').read_text().splitlines();data.write_text('\n'.join(lines[:3])+'\n')
  refid=literal_id(ref);comps=[lid for lid in unique if lid!=refid] or [refid]
  for k in [1,2,3]:
   for lid in comps:
    stage_budget();call(f'external_timing_{lid}_k{k}',['--mode','timing','--legacy-plan',plan,'--candidate',unique[refid]['path'],'--other',unique[lid]['path'],'--data',data,'--keyset',str(k),'--out',OUT/'timing'/lid/f'key_{k}'])
 write(OUT/'EXTERNAL_COMPLETED.json',dict(utc=utc(),wall_seconds_commands=elapsed_external(),automatic_followup=False,scientific_success_not_implied=True))
if __name__=='__main__':
 try:main()
 except Exception as e:
  p=OUT/f'EXTERNAL_STOP_{time.time_ns()}.json';write(p,dict(utc=utc(),reason=repr(e),automatic_retry=False));raise
