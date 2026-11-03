#!/usr/bin/env python3
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'src'))
from run_pilot import encrypted, plain, write_json, digest
from deciprotect.decision import interval_gate, reference_decision


def main():
    parent=ROOT/'results/dp_pilot_v1a_20260905';run=ROOT/'results/dp_stress_v1_20260905';run.mkdir()
    protocol=json.loads((ROOT/'protocols/DP_STRESS_V1.json').read_text());rng=np.random.default_rng(protocol['generator_seed'])
    write_json(run/'run_binding.json',{'protocol_sha256':digest(ROOT/'protocols/DP_STRESS_V1.json'),'source_sha256':digest(__file__),'binary_sha256':digest(ROOT/'bin/deciprotect-ckks'),'role':'EXPLORATORY'})
    summaries=[]
    for model in protocol['models']:
        source=parent/model;locked=json.loads((source/'deployment_lock.json').read_text());layers=json.loads((source/'model.json').read_text())['layers'];low=locked['low_scale'];high=locked['high_scale']
        x=np.array(json.loads((source/'inputs'/f'development_s{low}.json').read_text())['inputs']);labels=reference_decision(plain(layers,x))
        zeros=x[labels==0];ones=x[labels==1];boundary=[]
        for i in range(32):
            a=zeros[i%len(zeros)];b=ones[i%len(ones)];left,right=0.,1.
            for _ in range(48):
                middle=(left+right)/2
                if reference_decision(plain(layers,np.array([a+middle*(b-a)])))[0]==0:left=middle
                else:right=middle
            center=(left+right)/2
            for eps in [-.01,-.0001,-.000001,0,.000001,.0001,.01]:boundary.append(np.clip(a+(center+eps)*(b-a),-5,5))
        groups={'boundary':np.array(boundary),'shift_sigma05':np.clip(x[:256]+rng.normal(0,.5,size=x[:256].shape),-5,5)}
        for name,z in groups.items():
            case=run/f'{model}__{name}';case.mkdir();(case/'inputs').mkdir()
            ref=plain(layers,z);reference=reference_decision(ref)
            write_json(case/'reference.json',{'logits':ref.tolist(),'labels':None,'label_accuracy':'NOT_DEFINED_SYNTHETIC','parent_deployment_sha256':digest(source/'deployment_lock.json')})
            lo=encrypted(case,f'low_s{low}',layers,z,low);hi=encrypted(case,f'high_s{high}',layers,z,high)
            metrics=[]
            for k in range(3):
                zl=np.array(lo['measurements'][k]['logits']);zh=np.array(hi['measurements'][k]['logits']);ql=locked['radius'][str(low)];qh=locked['radius'][str(high)]
                d=interval_gate(zl,ql);pending=np.flatnonzero(d<0);final=d.copy();fallback_ms=0.
                if len(pending):
                    fallback=encrypted(case,f'fallback_{k}',layers,z[pending],high,repeats=1);fallback_ms=fallback['measurements'][0]['total_ms']
                    final[pending]=interval_gate(fallback['measurements'][0]['logits'],qh)
                metrics.append({'key_repeat':k,'inputs':len(z),'fixed_low_flips':int((reference_decision(zl)!=reference).sum()),'fixed_high_flips':int((reference_decision(zh)!=reference).sum()),
                    'low_accepted':int((d>=0).sum()),'low_accepted_flips':int(((d>=0)&(d!=reference)).sum()),'low_envelope_exceedances':int((np.max(np.abs(zl-ref),axis=1)>ql).sum()),
                    'high_envelope_exceedances':int((np.max(np.abs(zh-ref),axis=1)>qh).sum()),'cascade_accepted':int((final>=0).sum()),'cascade_flips':int(((final>=0)&(final!=reference)).sum()),
                    'cascade_abstained':int((final<0).sum()),'fallback_rows':len(pending),'fallback_ms':fallback_ms,'low_ms':lo['measurements'][k]['total_ms'],'high_all_ms':hi['measurements'][k]['total_ms']})
            summary={'case_id':case.name,'role':'SYNTHETIC_STRESS_NOT_POPULATION_EVIDENCE','metrics':metrics};write_json(case/'summary.json',summary)
            write_json(case/'evidence_manifest.json',{str(p.relative_to(case)):digest(p) for p in sorted(case.rglob('*')) if p.is_file()})
            summaries.append(summary);print('STRESS_COMPLETE',case.name,metrics,flush=True)
    write_json(run/'run_summary.json',{'completed_cases':len(summaries),'status':'EXPLORATORY_COMPLETE','confirmatory_claims':0})


if __name__=='__main__':main()
