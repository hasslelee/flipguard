#!/usr/bin/env python3
"""Official EVA compiler/native SEAL; inherited precision, no decision-based tuning."""
import hashlib, importlib.util, json, os, platform, time
from pathlib import Path
ROOT=Path('/work')
R=ROOT/'results/fg_expand_v2_20260905_run01/external'
W=ROOT/'work/fg_expand_v2_20260905'
spec=importlib.util.spec_from_file_location('old_eva',W/'run_eva_shared_polynomial_v8.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
OUT=R/'eva';OUT.mkdir()
def write(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
start=time.perf_counter();compiled,parameters,signature=old.compile_program(30);compile_seconds=time.perf_counter()-start
dot=OUT/'compiled.dot';dot.write_text(compiled.to_DOT())
candidate=f'eva_official_s30_{sha(dot)[:16]}'
selection=dict(candidate_id=candidate,input_scale_bits=30,output_range_bits=20,precision_origin='pre-existing V8 predeclared scale30; official EVA README demonstrates scale30. V8 range20 preserved. No search based on these outputs.',provider_commit='4cd3254c9c51340ae30c451495ce5378135758c0',compiler_config={'balance_reductions':'true','rescaler':'always','lazy_relinearize':'true','security_level':'128','quantum_safe':'false','warn_vec_size':'false'},poly_modulus_degree=int(parameters.poly_modulus_degree),prime_bits=list(parameters.prime_bits),compile_seconds=compile_seconds,compiled_sha256=sha(dot),own_condition='native compiler/backend feasibility with declared scale/range and SEAL security_level128; no extra empirical decision/MAE cutoff invented',comparison_type='official implementation native encrypted execution on shared fixed polynomial; not reproduction of full paper benchmarks',security_alignment='same128bit target; native SEAL distribution/estimator and Lattigo SecurityV2 not established identical',latency_causal_comparison=False,python=platform.python_version(),eva_module=os.environ.get('PYTHONPATH'))
write(OUT/'FROZEN_SELECTION.json',selection)
for role,name in [('configuration_validation','configuration_validation.csv'),('locked_audit','locked_audit.csv')]:
    rows=old.load_rows(R/'inputs'/name);records,summary=old.run_phase(role,30,rows,compiled,parameters,signature,3)
    for r in records:r['candidate_id']=candidate
    old.write_csv(OUT/(role+'.csv'),records)
    summary['status_is_our_posthoc_condition']=True;summary['native_execution_completed']=True
    write(OUT/(role+'_summary.json'),summary)
write(OUT/'COMPLETED.json',dict(candidate_id=candidate,automatic_followup=False))
print(json.dumps(selection))
