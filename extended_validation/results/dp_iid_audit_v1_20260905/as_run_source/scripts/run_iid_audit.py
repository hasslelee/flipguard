#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'src'))
from run_pilot import write_json, digest, encrypted, plain
from deciprotect.decision import interval_gate, reference_decision
from deciprotect.risk import admit_risk


def main():
    protocol=json.loads((ROOT/'protocols/DP_IID_AUDIT_V1.json').read_text())
    run=ROOT/'results/dp_iid_audit_v1_20260905';run.mkdir();(run/'inputs').mkdir()
    parent=ROOT/'results/dp_pilot_v1a_20260905/spambase__logistic_linear__20260905'
    lock=json.loads((parent/'deployment_lock.json').read_text());layers=json.loads((parent/'model.json').read_text())['layers']
    sources=[parent/'inputs/test_s18.json',ROOT/'results/dp_stress_v1_20260905/spambase__logistic_linear__20260905__boundary/inputs/low_s18.json',ROOT/'results/dp_stress_v1_20260905/spambase__logistic_linear__20260905__shift_sigma05/inputs/low_s18.json']
    population=np.concatenate([np.array(json.loads(p.read_text())['inputs']) for p in sources]);assert len(population)==1322
    write_json(run/'population.json',{'inputs':population.tolist(),'weights':'uniform over row indices','source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in sources}})
    rng=np.random.default_rng(protocol['input_sampling_seed']);indices=rng.integers(0,len(population),size=protocol['trials']).tolist()
    write_json(run/'locked_draws.json',{'population_indices':indices})
    write_json(run/'run_binding.json',{'protocol_sha256':digest(ROOT/'protocols/DP_IID_AUDIT_V1.json'),'deployment_sha256':digest(parent/'deployment_lock.json'),'population_sha256':digest(run/'population.json'),'draws_sha256':digest(run/'locked_draws.json'),'binary_sha256':digest(ROOT/'bin/deciprotect-ckks'),'script_sha256':digest(__file__),'independent_units':'fresh sampled input and fresh keys per trial','boundaries_do_not_use_labels':True})
    accepted=failures=low_flips=0;started=time.monotonic()
    with (run/'observations.jsonl').open('x') as log:
        for i,idx in enumerate(indices):
            x=population[idx:idx+1];ref=int(reference_decision(plain(layers,x))[0])
            lo=encrypted(run,f'trial_{i:04d}_low',layers,x,18,repeats=1);low_logits=lo['measurements'][0]['logits']
            low_dec=int(reference_decision(low_logits)[0]);d=int(interval_gate(low_logits,lock['radius']['18'])[0]);fallback=False
            if d<0:
                hi=encrypted(run,f'trial_{i:04d}_high',layers,x,30,repeats=1);d=int(interval_gate(hi['measurements'][0]['logits'],lock['radius']['30'])[0]);fallback=True
            wrong=d>=0 and d!=ref;accepted+=int(d>=0);failures+=int(wrong);low_flips+=int(low_dec!=ref)
            row={'trial':i,'population_index':idx,'reference':ref,'low_decision':low_dec,'returned_decision':d,'accepted':d>=0,'wrong_accepted':wrong,'fallback':fallback}
            log.write(json.dumps(row)+'\n');log.flush()
            if (i+1)%50==0:print(f'IID_PROGRESS {i+1}/600 accepted={accepted} wrong={failures}',flush=True)
    n=len(indices)
    summary={'trials':n,'unique_population_indices_drawn':len(set(indices)),'population_size':len(population),'accepted':accepted,'abstained':n-accepted,'accepted_disagreements':failures,
             'fixed_low_disagreements':low_flips,'coverage':accepted/n,'joint_risk':admit_risk(failures,n,.01,independent_units=True,hypotheses=2),
             'selective_risk':admit_risk(failures,accepted,.01,independent_units=True,hypotheses=2),'wall_seconds':time.monotonic()-started,
             'scope':'FINITE_1322_ROW_OPERATIONAL_POPULATION_ONLY','real_world_generalization':False,'worst_case_preservation':False}
    write_json(run/'summary.json',summary)
    write_json(run/'evidence_manifest.json',{str(p.relative_to(run)):digest(p) for p in sorted(run.rglob('*')) if p.is_file()})
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
