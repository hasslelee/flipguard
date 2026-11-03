#!/usr/bin/env python3
"""Final read-only integrity checks; optional one-time new evidence manifest."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from run_fg_contrib_v1 import ROOT,RUN,read,sha,write,verify,utc

DOC=ROOT/'docs/research/fg_contrib_v1_20260906'
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',action='store_true');a=p.parse_args();verify()
 out=RUN/'external/hediff_bank';expected=dict(read(out/'EXTERNAL_PROTOCOL.json')['source_bindings'])
 for p in sorted(out.glob('SOURCE_AMENDMENT_*.json')):
  j=read(p);assert expected[j['path']]==j['old_sha256'];expected[j['path']]=j['new_sha256']
 for p,h in expected.items():assert sha(ROOT/p)==h,('external source',p)
 for p,h in read(out/'EXACT_ADAPTER_SOURCE_LOCK.json')['files'].items():assert sha(ROOT/p)==h,('external native source',p)
 if (out/'INPUT_MODEL_LOCK.json').exists():
  for p,h in read(out/'INPUT_MODEL_LOCK.json')['files'].items():assert sha(out/p)==h,('external input/model binding',p)
 assert sha(ROOT/'baseline/journal_final_20260905.pdf')=='0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85'
 frozen=read(RUN/'FROZEN_SELECTIONS.json')
 for p,h in frozen['selection_result_hashes'].items():assert sha(ROOT/p)==h,('selection freeze changed',p)
 if (RUN/'STRESS_RULE_LOCK.json').exists():
  j=read(RUN/'STRESS_RULE_LOCK.json');assert sha(ROOT/'scripts/stress_fg_contrib_v1.py')==j['script_sha256'];assert sha(RUN/'FROZEN_SELECTIONS.json')==j['selection_freeze_sha256']
 for p in (RUN/'stress').glob('*/INPUT_LOCK.json'):
  j=read(p)
  for name,h in j['inputs'].items():assert sha(p.parent/name)==h,('stress input changed',p,name)
 # Restrict preservation check to tracked existing evidence/source. Do not
 # traverse/hash archive or run any original FlipGuard code/interpreter.
 changes=subprocess.check_output(['git','diff','--name-only','b4950499987e06a08075b4a8413ef216e9ab3471','--','baseline','archive','research','results','docs/research','protocols'],cwd=ROOT,text=True).splitlines()
 new_prefixes=('research/contribution_validation/','research/hediff_bank_validation/','results/fg_contrib_v1_20260906_run01/','docs/research/fg_contrib_v1_20260906/')
 changed=[p for p in changes if not p.startswith(new_prefixes) and p!='protocols/FG_CONTRIB_V1.json'];assert not changed,changed
 archives=subprocess.check_output(['git','ls-files','--','archive'],cwd=ROOT,text=True).splitlines();assert not archives,'archive tracked'
 starts=list((RUN/'commands').glob('*.start.json'));missing=[]
 for p in starts:
  end=Path(str(p).replace('.start.json','.end.json'))
  if not end.exists():missing.append(str(p.relative_to(ROOT)))
 manifest_path=RUN/'EVIDENCE_MANIFEST.json'
 if manifest_path.exists():
  for p,h in read(manifest_path)['files'].items():assert sha(ROOT/p)==h,('evidence payload mismatch',p)
 checks=dict(utc=utc(),current_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),source_and_input_locks=True,external_source_chain=True,selection_freeze=True,final_pdf=True,existing_frozen_tracked_changes=changed,archive_tracked=archives,started_commands=len(starts),missing_end_records=missing,full_archive_rehash=False,original_flipguard_execution=False,tests_are_not_performance_or_risk_evidence=True)
 if a.manifest:
  assert not missing,'unfinished commands cannot be finalized'
  assert (DOC/'SUMMARY.json').exists(),'independent results/report must be reviewed first'
  excluded={'EVIDENCE_MANIFEST.json','FINAL_VERIFICATION.json'}
  paths=[p for p in RUN.rglob('*') if p.is_file() and p.name not in excluded]
  paths += [p for p in DOC.iterdir() if p.is_file()]
  paths += list((ROOT/'scripts').glob('*contrib*.py'))
  files={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))}
  write(manifest_path,dict(utc=utc(),files=files,scope='this new evidence pack and its analyzers/reports only; no archive/baseline full rehash',execution_base_head=read(RUN/'SOURCE_LOCK.json')['start_head'],current_head=checks['current_head'],traceability_note='Binaries embed base HEAD plus vcs.modified=true. Executed source contents are bound by SOURCE_LOCK, independently of later commit movement.'))
  write(RUN/'FINAL_VERIFICATION.json',checks)
 print(json.dumps(checks,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
