#!/usr/bin/env python3
"""Reconstruct paired latencies from raw records, never saved pair summaries."""
import csv
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OLD=Path('/home/ckks2/flipguard')


def main():
    inv=list(csv.DictReader((OLD/'docs/reports/comparison_extension_v18/PRIMARY_68_CASE_INVENTORY.csv').open()))
    out=[];clusters=defaultdict(list);identical_parameters=0;total_pairs=0
    for row in inv:
        p=OLD/row['formal_latency_record'];v=json.loads(p.read_text())
        a=v['direct_candidate'];b=v['finite_fastest_safe_candidate']
        same=a['parameters']==b['parameters'] and a.get('path')==b.get('path');identical_parameters+=same
        paired=defaultdict(dict)
        if 'keysets' in v:
            blocks=[(x['keyset'],x['measurement']['records']) for x in v['keysets']]
        else: blocks=[(None,v['records'])]
        for key,records in blocks:
            for rec in records:
                pair=(key if key is not None else rec['keyset'],rec['measurement_run'],rec.get('row_id','whole_batch'))
                arm=rec['arm_id'];assert arm not in paired[pair],(p,pair,arm)
                paired[pair][arm]=rec['total_ms']
        ratios=[]
        for pair,arms in paired.items():
            assert set(arms)=={'direct','finite_fastest_safe'} and all(x>0 for x in arms.values()),(p,pair)
            ratios.append(arms['finite_fastest_safe']/arms['direct'])
        mean_log=sum(map(math.log,ratios))/len(ratios);total_pairs+=len(ratios)
        # Preserve the published cluster labels and deterministic resampling order.
        dataset='multiclass' if row['dataset']=='mnist_10class' else ('packed_cnn_lite_binary01_v17' if 'packed_cnn' in row['model_id'] else row['dataset'])
        clusters[(dataset,row['model_id'])].append(mean_log)
        out.append({'case_id':row['case_id'],'raw_pairs':len(ratios),'ratio':math.exp(mean_log),'identical_parameters':same,'raw_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    values=[sum(v)/len(v) for _,v in sorted(clusters.items())]
    rng=random.Random(20260824);boot=[]
    for _ in range(10000):
        sampled=[rng.choice(values) for _ in values];boot.append(math.exp(sum(sampled)/len(sampled)))
    estimate=math.exp(sum(values)/len(values));ci=np.quantile(boot,[.025,.975]).tolist()
    result={'raw_pairs':total_pairs,'cases':len(out),'clusters':len(values),'estimate':estimate,'bootstrap_seed':20260824,'bootstrap_replicates':10000,
            'ci95':ci,'identical_parameter_cases':identical_parameters,'identical_candidate_id_cases':sum(r['full_method_selected_candidate']==r['formal_reference_candidate'] for r in inv),
            'superiority_supported':not ci[0]<=1<=ci[1], 'point_matches_frozen':abs(estimate-1.000540931232697)<1e-12,
            'ci_matches_frozen':max(abs(ci[0]-.9999674747655278),abs(ci[1]-1.0011217812090207))<1e-12}
    assert result['point_matches_frozen'] and result['ci_matches_frozen'] and total_pairs==23454
    (ROOT/'docs/review/latency_recomputed.json').write_text(json.dumps(result,indent=2)+'\n')
    with (ROOT/'docs/review/latency_recomputed_by_case.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
