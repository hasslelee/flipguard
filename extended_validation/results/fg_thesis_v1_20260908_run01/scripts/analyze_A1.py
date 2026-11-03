"""Reclassify already-frozen outputs; no execution, model fitting, or retuning."""
from pathlib import Path
import json,csv,hashlib,collections,math,numpy as np
ROOT=Path('/home/ckks2/deciprotect');OLD=ROOT/'results/fg_contrib_v1_20260906_run01';RUN=ROOT/'results/fg_thesis_v1_20260908_run01';DOC=ROOT/'docs/research/fg_thesis_v1_20260908'
spec=json.load(open(RUN/'protocol.json'));settings=spec['settings']
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
groups=collections.defaultdict(list);bindings={};aliases={}
frozen=read(OLD/'FROZEN_SELECTIONS.json')
for c in frozen['cases']:
 cid=c['case_id'];valid={r['literal_id'] for r in c['roles'] if r['role'] in ['A30','B30','C'] and r['literal_id']}
 for lid in valid:
  aliases[cid+'/'+lid]=[f"block{r['block']}/{r['role']}" for r in c['roles'] if r['literal_id']==lid and r['role'] in ['A30','B30','C']]
  for p in (OLD/'cases'/cid/'audit'/lid).glob('batch_*/key_*.json'):groups[(cid,'audit',lid)].append(p)
  for p in (OLD/'cases'/cid/'stress'/lid).glob('key_*.json'):groups[(cid,'stress',lid)].append(p)
 for p in (OLD/'cases'/cid).glob('selection/block_*/*/result.json'):
  if p.parent.name not in ['A30','B30','C']:continue
  r=read(p)
  if not r['selected']:continue
  cand=r['selected']['id'];tr=next(t for t in p.parent.glob('trial_*/trial.json') if read(t)['candidate']['id']==cand)
  groups[(cid,'selection',p.parent.parent.name+'/'+p.parent.name)]+=list(tr.parent.glob('key_*.json'))
bank=OLD/'external/hediff_bank'
for stage in ['audit','stress']:
 for p in (bank/stage).glob('*/key_*.json'):groups[('hediff_bank',stage,p.parent.name)].append(p)
for role in ['A','B','C']:
 for p in (bank/'selection'/role).glob('trial_*/key_*.json'):groups[('hediff_bank','selection',role)].append(p)
rows=[]
for (cid,stage,config),files in sorted(groups.items()):
 gaps=[];errs=[];flips=[];sids=[];maxabs=[];true=[];contexts=[]
 for path in sorted(files):
  j=read(path);bindings[str(path.relative_to(ROOT))]=sha(path);rs=j['records']
  if not rs:continue
  tab='PlainY' in rs[0]
  p=np.array([[r['PlainY']] if tab else r['plaintext_logits'] for r in rs],float)
  a=np.array([[r['CKKSY']] if tab else r['ckks_logits'] for r in rs],float)
  assert np.isfinite(p).all() and np.isfinite(a).all() and p.shape==a.shape
  e=abs(a-p)
  if tab:
   gap=abs(p[:,0]-.5);f=(p[:,0]>=.5)!=(a[:,0]>=.5);rat=np.divide(e[:,0],gap,out=np.full(len(rs),np.inf),where=gap>0);pred=(p[:,0]>=.5).astype(int)
  else:
   pred=p.argmax(axis=1);ii=np.arange(len(rs));dist=p[ii,pred,None]-p
   costs=e[ii,pred,None]+e;mask=np.arange(p.shape[1])[None,:]!=pred[:,None]
   gap=np.where(mask,dist,np.inf).min(axis=1);rat=np.divide(costs,dist,out=np.full_like(costs,np.inf),where=dist>0);rat[~mask]=0;rat=rat.max(axis=1);f=pred!=a.argmax(axis=1)
  gaps.extend(gap);errs.extend(rat);flips.extend(f);maxabs.extend(e.max(axis=1));sids.extend(str(r['RowID'] if tab else r['sample_id']) for r in rs);true.extend(pred==np.array([r['Label'] if tab else r['label'] for r in rs]));contexts.append(str(path.relative_to(ROOT)))
 g=np.array(gaps);e=np.array(errs);f=np.array(flips);aerr=np.array(maxabs);ids=np.array(sids);common=g>.01
 assert len(g)>0
 n=len(set(sids));unique_g={i:float(m) for i,m in zip(ids,g)}
 for st in settings:
  app=g>st['delta'];vio=e>=st['rho'];usage=e/st['rho'];finite=usage[app & np.isfinite(usage)]
  rows.append(dict(case_id=cid,stage=stage,configuration_or_role=config,aliases=';'.join(aliases.get(cid+'/'+config,[])),setting=st['id'],rho=st['rho'],delta=st['delta'],unique_inputs=n,applicable_inputs=len(set(ids[app])),boundary_inputs=len(set(ids[~app])),applicable_fraction=len(set(ids[app]))/n,key_contexts=len(contexts),input_key_observations=len(g),applicable_observations=int(app.sum()),all_flip_events=int(f.sum()),applicable_flip_events=int((f&app).sum()),boundary_flip_events=int((f&~app).sum()),applicable_error_events=int((vio&app).sum()),applicable_unique_flips=len(set(ids[f&app])),applicable_unique_error_inputs=len(set(ids[vio&app])),common_inputs=len(set(ids[common])),common_flip_events=int((f&common).sum()),common_error_events=int((vio&common).sum()),max_abs=float(aerr.max()),max_budget_usage=float(finite.max()) if len(finite) else None,p95_budget_usage=float(np.quantile(finite,.95)) if len(finite) else None,min_margin=min(unique_g.values()),median_margin=float(np.median(list(unique_g.values()))),plaintext_accuracy=None if stage=='stress' else float(np.mean(true)),scope='fixed old output reclassification; no reselection or new audit; key repeats not independent inputs'))
by=collections.defaultdict(list)
for r in rows:by[(r['case_id'],r['stage'],r['configuration_or_role'])].append(r)
for key,rr in by.items():
 assert len(rr)==6 and len({r['all_flip_events'] for r in rr})==1 and len({r['common_flip_events'] for r in rr})==1,key
with (DOC/'A1_SENSITIVITY.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,rows[0]);w.writeheader();w.writerows(rows)
(RUN/'A1_READ_BINDINGS.json').write_text(json.dumps(bindings,indent=2)+'\n')
summary={'groups':len(groups),'settings':6,'rows':len(rows),'raw_key_files':len(bindings),'cases':sorted({r['case_id'] for r in rows}),'all_flip_invariant_across_rho_delta':True,'common_domain_delta':.01,'new_CKKS':0,'scope':'selected A30/B30/C common-backend outputs; native TenSEAL original comparisons retained separately','excluded':'unselected diagnostics and A40/B40-only configurations; no archive expansion'}
(RUN/'A1_COMPLETED.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary)
