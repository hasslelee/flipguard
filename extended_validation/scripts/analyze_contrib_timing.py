#!/usr/bin/env python3
"""Reconstruct matched latency records. Descriptive estimates, no iid claims."""
import collections,math
from pathlib import Path
from run_fg_contrib_v1 import ROOT,RUN,read

def summarize(path,case,reference,comparator,key_block,expected=None):
 j=read(path);protocol=j['protocol'];batch='selected_inputs' in protocol
 assert protocol['warmup_runs']==1 and protocol['measurement_runs']==6
 metadata={a['id']:a for a in j['arms']};assert set(metadata)=={'reference_C','comparator'}
 if expected is not None:
  assert set(expected)==set(metadata)
  for arm,candidate in expected.items():
   a=metadata[arm];p=candidate['parameters'];assert a['candidate_id']==candidate['id']
   assert all(a[k]==p[k] for k in ['log_n','log_q','log_p','log_default_scale']),('timing frozen parameters',case,arm)
 n=protocol['selected_inputs'] if batch else protocol['selected_rows']
 unit='one fixed input batch' if batch else 'one fixed input'
 raw=[];pairs=collections.defaultdict(dict)
 for r in j['records']:
  enc=r['encode_encrypt_ms'];he=r['evaluation_only_ms'] if batch else r['eval_only_ms'];dec=r['decrypt_decode_ms'];pdf=enc+he+dec
  assert pdf>0 and all(math.isfinite(x) and x>=0 for x in [enc,he,dec])
  match=(r['measurement_run'],None if batch else r['row_id']);arm=r['arm_id']
  assert arm in ['reference_C','comparator'] and arm not in pairs[match]
  assert r['candidate_id']==metadata[arm]['candidate_id'],'timing record/arm identity'
  v=dict(case_id=case,reference=reference,comparator=comparator,key_block=key_block,arm=arm,candidate_id=r['candidate_id'],measurement_run=r['measurement_run'],row_id=match[1],order_position=r['order_position'],selected_inputs=n,unit=unit,encode_encrypt_ms=enc,he_ms=he,decrypt_decode_ms=dec,pdf_inference_ms=pdf,native_total_ms=r['total_ms'],native_other_ms=r['total_ms']-pdf,raw=str(Path(path).relative_to(ROOT)))
  pairs[match][arm]=v;raw.append(v)
 assert len(pairs)==6*(1 if batch else n) and all(set(p)=={'reference_C','comparator'} for p in pairs.values())
 logs=[math.log(p['comparator']['pdf_inference_ms']/p['reference_C']['pdf_inference_ms']) for p in pairs.values()]
 arms=[]
 for a in j['arms']:
  rr=[r for r in raw if r['arm']==a['id']];setup=a['setup_keygen_ms'] if batch else a['setup_ms']
  arms.append(dict(arm=a['id'],candidate_id=a['candidate_id'],setup_parameter_key_ms=setup,measurements=len(rr),**{k:sum(r[k] for r in rr)/len(rr) for k in ['encode_encrypt_ms','he_ms','decrypt_decode_ms','pdf_inference_ms','native_total_ms','native_other_ms']}))
 return dict(case_id=case,reference=reference,comparator=comparator,key_block=key_block,paired_observations=len(pairs),unit=unit,selected_inputs=n,comparator_over_C_pdf_geomean=math.exp(sum(logs)/len(logs)),mean_pdf_difference_ms=sum(p['comparator']['pdf_inference_ms']-p['reference_C']['pdf_inference_ms'] for p in pairs.values())/len(pairs),arms=arms,raw=str(Path(path).relative_to(ROOT)),key_policy='fresh parameter-compatible key per arm, reused for warmup and six measurement passes; matching key ordinal is not identical secret key'),raw

def analyze_timing():
 blocks=[];raw=[];planned=[]
 frozen={c['case_id']:c['unique'] for c in read(RUN/'FROZEN_SELECTIONS.json')['cases']}
 if (RUN/'TIMING_JOBS.json').exists():planned=read(RUN/'TIMING_JOBS.json')['jobs']
 for j in planned:
  p=RUN/'cases'/j['case']/f"timing/{j['reference']}_vs_{j['comparator']}/key_{j['key']}/result.json"
  if not p.exists():continue
  u=frozen[j['case']];expected={'reference_C':u[j['reference']]['candidate'],'comparator':u[j['comparator']]['candidate']}
  b,r=summarize(p,j['case'],j['reference'],j['comparator'],j['key'],expected);b['comparison_label']=j['label'];blocks.append(b);raw+=r
 groups=collections.defaultdict(list)
 for b in blocks:groups[(b['case_id'],b['reference'],b['comparator'])].append(b)
 summary=[]
 for (c,a,b),vv in groups.items():
  ratios=[v['comparator_over_C_pdf_geomean'] for v in vv]
  summary.append(dict(case_id=c,reference=a,comparator=b,key_blocks=len(vv),complete_key_blocks=len(vv)==3,ratio_comparator_over_C=math.exp(sum(map(math.log,ratios))/len(ratios)),key_block_ratios=ratios,key_block_ratio_min=min(ratios),key_block_ratio_max=max(ratios),unit=vv[0]['unit'],selected_inputs=vv[0]['selected_inputs'],interpretation='descriptive equal-key geometric ratio; >1 means reference C faster; key repeats and input slots are not independent environments',statistical_superiority_claim=False,equivalence_claim=False))
 return dict(planned_jobs=len(planned),completed_jobs=len(blocks),blocks=blocks,summary=summary,records=raw,network=None,queue=None,estimator='within each key block, equal-weight geometric mean of comparator/C matched PDF phase-sum ratios; equal geometric weight across key blocks; report each block, no significance or equivalence declaration',legacy_metadata_correction='Copied V17 protocol strings mentioning B3/fastest_SAFE are inherited labels only. FG_CONTRIB_V1, FROZEN_SELECTIONS and TIMING_JOBS bind actual roles and choices; no B3 selection was executed here.')
