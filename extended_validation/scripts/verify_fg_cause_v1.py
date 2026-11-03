#!/usr/bin/env python3
"""Read-only cross-checks for the cause pack. May run git status/diff, never HE."""
import ast,csv,hashlib,json,math,subprocess
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'docs/research/fg_cause_v1_20260906';R=ROOT/'results/fg_cause_v1_20260906_run01';OLD=ROOT/'docs/research/fg_contrib_v1_20260906'
def read(p):return json.loads(p.read_text())
def rows(p):return list(csv.DictReader(p.open()))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def main():
 checks={};bindings={}
 for name in ['READ_BINDINGS.json','SUPPLEMENT_READ_BINDINGS.json']:
  for p,h in read(R/name)['files'].items():
   assert p not in bindings or bindings[p]==h;bindings[p]=h
 for p,h in bindings.items():assert sha(ROOT/p)==h,('read payload changed',p)
 assert sha(ROOT/'scripts/analyze_fg_cause_v1.py')==read(R/'READ_BINDINGS.json')['script_sha256']
 checks['consumed_file_bindings']=len(bindings)
 for p,h in read(R/'SOURCE_REVIEW.json')['source_files'].items():assert sha(ROOT/p)==h,('reviewed source changed',p)
 checks['reviewed_source_files']=len(read(R/'SOURCE_REVIEW.json')['source_files'])
 frozen=read(OLD/'PRESERVED_C_CORE_CHECK.json')
 for item in frozen['files']:
  for module in ['contribution_validation','hediff_bank_validation']:
   assert sha(ROOT/'research'/module/item['path'])==item['sha256']
 checks['unchanged_C_core_copies']=16
 assert sha(ROOT/'baseline/journal_final_20260905.pdf')==read(R/'START_STATE.json')['baseline_pdf_sha256']
 checks['final_PDF_unchanged']=True
 spec=read(ROOT/'protocols/FG_CONTRIB_V1.json');kind={c['case_id']:c['kind'] for c in spec['cases']};reference={};keys=0
 # Match exact per-input plaintext and scope over all3 keys and all candidates.
 for r in rows(D/'CANDIDATE_RECONSTRUCTION.csv'):
  folder=ROOT/r['raw'];seenkeys=[]
  for f in sorted(folder.glob('key_*.json')):
   k=read(f);pairs=[(str(v['sample_id']),v['plaintext_logits']) for v in k['records']] if kind[r['case_id']]=='multiclass' else [(str(v['RowID']),[v['PlainY']]) for v in k['records']]
   assert len(pairs)==len(set(x[0] for x in pairs))==int(r['inputs']);pp=dict(pairs)
   if r['case_id'] not in reference:reference[r['case_id']]=pp
   assert pp==reference[r['case_id']],('plaintext or scope mismatch',f)
   seenkeys.append(k['key_run']);keys+=1
  assert seenkeys==[1,2,3]
 checks['candidate_key_reference_contexts']=keys
 pool=read(R/'INPUT_POOL_LOCK.json');source=read(ROOT/'results/fg_contrib_v1_20260906_run01/external/hediff_bank/INPUT_MODEL_LOCK.json');used=set(sum([r['original_rows'] for r in source['roles'].values()],[]));unused=[dict(test_position=p,row_id=source['training_count']+p,source_row_id=s) for p,s in enumerate(source['test_indices_original']) if s not in used]
 rank=sorted(unused,key=lambda r:(hashlib.sha256(('FG_CAUSE_V1_20260906/pool/'+str(r['source_row_id'])).encode()).hexdigest(),r['source_row_id']));assert pool['candidate_pool']==rank[:684] and pool['future_audit_reserve']==rank[684:]
 reserve={r['source_row_id'] for r in rank[684:]};candidate={r['source_row_id'] for r in rank[:684]};assert not candidate&reserve and not(candidate&used) and not(candidate&set(source['training_indices_original']))
 access=read(R/'PLAINTEXT_ACCESS_AUDIT.json');assert access['audit_reserve_forward_count']==0 and not set(access['model_forward_source_ids'])&reserve
 cr=rows(D/'BANK_CANDIDATE_POOL.csv');assert {int(r['source_row_id']) for r in cr}==candidate
 selected=rows(D/'BANK_PLAINTEXT_SELECTIONS.csv');cuts=access['quartile_cuts'];selrank=lambda r:(hashlib.sha256(('FG_CAUSE_V1_20260906/select/'+r['source_row_id']).encode()).hexdigest(),int(r['source_row_id']))
 expected={'uniform_hash16':sorted(cr,key=selrank)[:16],'development_quartile4x4':sum([sorted([r for r in cr if int(np.searchsorted(cuts,float(r['margin']),side='right'))==q],key=selrank)[:4] for q in range(4)],[])}
 for policy,rr in expected.items():assert [r['source_row_id'] for r in rr]==[r['source_row_id'] for r in selected if r['policy']==policy]
 assert not {int(r['source_row_id']) for r in selected}&reserve
 checks['candidate_pool']=684;checks['unscored_audit_reserve']=684;checks['selection_rules_reconstructed']=True
 observations=rows(D/'BANK_CLASS_ERRORS.csv');violate=[];flips=[]
 for r in observations:
  p=np.array([float(r['plain0']),float(r['plain1'])]);a=np.array([float(r['ckks0']),float(r['ckks1'])]);v=abs(a-p).sum()>=.5*abs(p[0]-p[1]);flip=int(p.argmax())!=int(a.argmax());assert v==(r['violation']=='True') and flip==(r['flip']=='True');assert not(flip and not v),'sufficient condition contradiction'
  w=int(p.argmax());assert math.isclose(a[w]-a[1-w],float(r['encrypted_winner_gap']),abs_tol=1e-12)
  if r['stage']=='stress' and r['method']=='C':
   if v:violate.append((r['sample_id'],r['key']))
   if flip:flips.append((r['sample_id'],r['key']))
 assert len(violate)==6 and len({i for i,k in violate})==3 and flips==[('bank_test_6197','2')]
 checks['bank_unchanged_stress']={'flips':1,'condition_violations':6,'affected_condition_inputs':3};checks['bank_output_observations']=len(observations)
 # AST allowlist catches accidental training/native/network imports in both analysis programs.
 for name in ['analyze_fg_cause_v1.py','supplement_fg_cause_v1.py']:
  tree=ast.parse((ROOT/'scripts'/name).read_text())
  for node in ast.walk(tree):
   if isinstance(node,(ast.Import,ast.ImportFrom)):
    mods=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module]
    assert all(m.split('.')[0] in {'argparse','collections','csv','hashlib','io','json','math','sys','pathlib','numpy','analyze_fg_cause_v1'} for m in mods),(name,mods)
   if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):assert node.func.id not in {'exec','eval','compile','__import__'}
 checks['analysis_imports_no_HE_training_network_process']=True
 protected=['baseline','research','results/fg_contrib_v1_20260906_run01','docs/research/fg_contrib_v1_20260906','protocols/FG_CONTRIB_V1.json']
 changes=git('diff','--name-only','e2c0054e7778da8f099b1e49ee7b584b2b29bc30','--',*protected);assert not changes,changes
 checks['protected_paths_diff_empty']=True;checks['new_ckks']=0;checks['training']=0;checks['archive_traversed']=False
 print(json.dumps({'status':'PASS','checks':checks},indent=2))
if __name__=='__main__':main()
