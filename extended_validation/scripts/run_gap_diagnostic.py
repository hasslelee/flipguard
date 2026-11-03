#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from deciprotect.difference import pairwise_residuals,difference_gate
from deciprotect.decision import calibration_radius,reference_decision,interval_gate
from run_pilot import write_json,digest


def main():
    run=ROOT/'results/dp_gap_diagnostic_v1_20260905';run.mkdir()
    write_json(run/'run_binding.json',{'protocol_sha256':digest(ROOT/'protocols/DP_GAP_DIAGNOSTIC_V1.json'),'script_sha256':digest(__file__),'difference_source_sha256':digest(ROOT/'src/deciprotect/difference.py'),'new_ckks_executions':0,'formal_claim':False})
    rows=[]
    for p in sorted((ROOT/'results/dp_pilot_v1a_20260905').glob('*square_mlp12*/plaintext.json')):
        case=p.parent;reference=json.loads(p.read_text());lock=json.loads((case/'deployment_lock.json').read_text());scale=lock['low_scale']
        cal=json.loads((case/f'calibration_s{scale}.json').read_text());test=json.loads((case/f'test_s{scale}.json').read_text())
        residual=pairwise_residuals(reference['calibration']['logits'],[m['logits'] for m in cal['measurements']]);q=calibration_radius(residual,.025)
        abs_q=lock['radius'][str(scale)];abs_q=float('inf') if abs_q=='INFINITY' else abs_q
        ref=reference_decision(reference['test']['logits'])
        for k,m in enumerate(test['measurements']):
            d=difference_gate(m['logits'],q);old=interval_gate(m['logits'],abs_q)
            rows.append({'case_id':case.name,'key_repeat':k,'inputs':len(ref),'box_accepted':int((old>=0).sum()),'difference_accepted':int((d>=0).sum()),
                         'difference_flip_events':int(((d>=0)&(d!=ref)).sum()),'pairwise_radius':q if np.isfinite(q) else 'INFINITY',
                         'twice_box_radius':2*abs_q if np.isfinite(abs_q) else 'INFINITY','parent_deployment_sha256':digest(case/'deployment_lock.json')})
    write_json(run/'summary.json',{'role':'OFFLINE_EXPLORATORY_ONLY','rows':rows,'new_ckks_executions':0,'inherits_iid_audit':False})
    write_json(run/'evidence_manifest.json',{p.name:digest(p) for p in sorted(run.iterdir()) if p.is_file()})
    print(json.dumps({'cases':len(rows)//3,'additional_accepted_key_observations':sum(r['difference_accepted']-r['box_accepted'] for r in rows),'difference_flip_events':sum(r['difference_flip_events'] for r in rows)},indent=2))


if __name__=='__main__':main()
