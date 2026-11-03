#!/usr/bin/env python3
"""Check frozen research payloads and independently rebuild reported outcomes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from deciprotect.decision import interval_gate, reference_decision, decision_metrics
from deciprotect.risk import admit_risk


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true',help='Compare to the completed report without writing it')
    args=parser.parse_args()
    payloads=0;cases=0;bound_requests=0
    freeze=read(ROOT/'baseline/FREEZE_MANIFEST.json')
    assert freeze['status']=='VERIFIED_ARCHIVE'
    assert sha(ROOT/'baseline/journal_final_20260905.pdf')==freeze['final_pdf_sha256']
    for manifest in sorted((ROOT/'results').rglob('evidence_manifest.json')):
        for rel,expected in read(manifest).items():
            p=manifest.parent/rel
            assert p.is_file() and sha(p)==expected, str(p)
            payloads+=1
            if p.suffix=='.json':
                obj=read(p)
                if isinstance(obj,dict) and 'request_sha256' in obj:
                    request=p.parent/'inputs'/p.name
                    assert request.is_file() and sha(request)==obj['request_sha256'],str(request)
                    req=read(request)
                    assert len(obj['measurements'])==req['repeats'],str(p)
                    assert all(len(m['logits'])==len(req['inputs']) for m in obj['measurements']),str(p)
                    bound_requests+=1
    parent=ROOT/'results/dp_pilot_v1a_20260905'
    for p in sorted(parent.glob('*/summary.json')):
        case=p.parent;summary=read(p);lock=read(case/'deployment_lock.json');data=read(case/'data_manifest.json');reference=read(case/'plaintext.json')['test'];splits=data['split_source_row_ids']
        flat=sum(splits.values(),[]);assert len(flat)==len(set(flat)),case
        assert sha(case/'model.json')==lock['model_sha256']
        assert sha(ROOT/'protocols/DP_PILOT_V1A.json')==lock['protocol_sha256']
        low=read(case/f'test_s{lock["low_scale"]}.json');high=read(case/'test_s30.json')
        q=lambda k:float('inf') if lock['radius'][str(k)]=='INFINITY' else lock['radius'][str(k)]
        for key in range(3):
            low_logits=low['measurements'][key]['logits'];high_logits=high['measurements'][key]['logits'];d=interval_gate(low_logits,q(lock['low_scale']));cascade=d.copy();pending=np.flatnonzero(d<0)
            fallback=case/f'fallback_key{key}_s30.json'
            if len(pending) and np.isfinite(q(30)):
                obj=read(fallback);cascade[pending]=interval_gate(obj['measurements'][0]['logits'],q(30))
            assert cascade.tolist()==summary['fallbacks'][key]['decisions']
            arms={f'fixed_scale{lock["low_scale"]}':reference_decision(low_logits),'fixed_scale30':reference_decision(high_logits),'low_envelope_abstain':d,'two_stage_envelope':cascade}
            for arm,decisions in arms.items():
                expected=decision_metrics(reference['logits'],decisions,reference['labels']);record=next(m for m in summary['metrics'] if m['arm']==arm and m['key_repeat']==key)
                assert all(record[k]==v for k,v in expected.items()),(case,arm,key)
        cases+=1
    iid=ROOT/'results/dp_iid_audit_v1_20260905';summary=read(iid/'summary.json');binding=read(iid/'run_binding.json');draws=read(iid/'locked_draws.json')['population_indices']
    assert sha(iid/'population.json')==binding['population_sha256'] and sha(iid/'locked_draws.json')==binding['draws_sha256']
    events=[json.loads(s) for s in (iid/'observations.jsonl').read_text().splitlines()]
    assert len(events)==600 and [e['population_index'] for e in events]==draws
    accepted=sum(e['returned_decision']>=0 for e in events)
    wrong=sum(e['returned_decision']>=0 and e['returned_decision']!=e['reference'] for e in events)
    assert accepted==summary['accepted'] and wrong==summary['accepted_disagreements']
    # Verify every decision against actual decrypted ciphertext outputs, never event flags alone.
    lock=read(parent/'spambase__logistic_linear__20260905/deployment_lock.json')
    layers=read(parent/'spambase__logistic_linear__20260905/model.json')['layers']
    population=np.array(read(iid/'population.json')['inputs'])
    reference_logits=population
    for layer in layers:
        reference_logits=reference_logits@np.array(layer['weights']).T+np.array(layer['bias'])
        if layer['square']:reference_logits=reference_logits**2
    reference_labels=reference_decision(reference_logits)
    for event in events:
        assert int(reference_labels[event['population_index']])==event['reference']
        i=event['trial'];lo=read(iid/f'trial_{i:04d}_low.json');d=int(interval_gate(lo['measurements'][0]['logits'],lock['radius']['18'])[0])
        if d<0:
            hi=read(iid/f'trial_{i:04d}_high.json');d=int(interval_gate(hi['measurements'][0]['logits'],lock['radius']['30'])[0])
        assert d==event['returned_decision']
    assert admit_risk(wrong,600,.01,independent_units=True,hypotheses=2)==summary['joint_risk']
    assert admit_risk(wrong,accepted,.01,independent_units=True,hypotheses=2)==summary['selective_risk']
    result={'status':'PASS','verified_payload_files':payloads,'pilot_cases_independently_recomputed':cases,'iid_trials_recomputed':len(events),
            'missing_request_files':0,'request_output_bindings_verified':bound_requests,
            'ckks_output_json_preserved':True,'executable_rebuild_required_on_clean_clone':True,
            'frozen_journal_pdf_sha256_verified':True,
            'scope':'Artifact consistency and arithmetic, not external validation of model or population assumptions'}
    report=ROOT/'docs/research/VERIFICATION.json'
    if args.check:
        assert read(report)==result, 'Recomputed verification differs from the preserved report'
    else:
        report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
