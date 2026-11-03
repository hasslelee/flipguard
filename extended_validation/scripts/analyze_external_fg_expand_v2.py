#!/usr/bin/env python3
"""Recompute external comparison independently from native score ledgers."""
import argparse,csv,json,math
from pathlib import Path
import numpy as np
from analyze_fg_expand_v2 import same_derived
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'results/fg_expand_v2_20260905_run01'
OUT=ROOT/'docs/research/fg_expand_v2_20260905'
def read(p):return json.loads(p.read_text())
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();r=RUN/'external';res=[];examples=[]
    for provider in ['eva','proposed']:
        for role in ['configuration_validation','locked_audit']:
            source=list(csv.DictReader((r/'inputs'/f'{role}.csv').open()));expected={x['row_id']:.5+.197*(.8*float(x['x_0'])-.5*float(x['x_1'])+1.2*float(x['x_2'])-.3)-.004*(.8*float(x['x_0'])-.5*float(x['x_1'])+1.2*float(x['x_2'])-.3)**3 for x in source}
            if provider=='eva':
                raw=list(csv.DictReader((r/'eva'/f'{role}.csv').open()));rs=[dict(id=x['row_id'],key=int(x['context_index']),p=float(x['plaintext_score']),y=float(x['decrypted_score'])) for x in raw];tim=[]
                for key in [1,2,3]:
                    t=next(x for x in raw if int(x['context_index'])==key);tim.append({n:float(t[n]) for n in ['keygen_ms','encrypt_ms','evaluate_ms','decrypt_ms','total_ms']})
                tc={n:sum(t[n] for t in tim) for n in tim[0]};configuration=read(r/'eva/FROZEN_SELECTION.json')
            else:
                j=read(r/'proposed'/('selection.json' if role=='configuration_validation' else 'audit.json'));t=j['trials'][-1] if role=='configuration_validation' else j;rs=[dict(id=x['sample_id'],key=x['key_repeat'],p=x['plaintext_score'],y=x['ckks_score']) for x in t['sample_ledger']];tc={};configuration=t['candidate']['parameters']
            assert len(rs)==1500 and len({(x['id'],x['key']) for x in rs})==1500
            assert {(x['id'],x['key']) for x in rs}=={(sid,key) for sid in expected for key in [1,2,3]}
            for x in rs:assert abs(x['p']-expected[x['id']])<1e-12
            app={x['id'] for x in rs if abs(x['p']-.5)>.001};bound={x['id'] for x in rs}-app;fl=[x for x in rs if (x['p']>=.5)!=(x['y']>=.5)];viol=[x for x in rs if x['id'] in app and abs(x['p']-x['y'])>=.5*abs(x['p']-.5)];es=np.array([x['p']-x['y'] for x in rs])
            row=dict(provider=provider,role=role,unique_inputs=len(app)+len(bound),applicable=len(app),boundary=len(bound),key_observations=len(rs),applicable_flip_events=sum(x['id'] in app for x in fl),applicable_flip_inputs=len({x['id'] for x in fl if x['id'] in app}),boundary_flip_events=sum(x['id'] in bound for x in fl),boundary_flip_inputs=len({x['id'] for x in fl if x['id'] in bound}),applicable_error_events=len(viol),applicable_error_inputs=len({x['id'] for x in viol}),max_abs_all=float(abs(es).max()),max_abs_applicable=max(abs(x['p']-x['y']) for x in rs if x['id'] in app),rmse_all=float(np.sqrt(np.mean(es**2))),configuration=configuration,native_batch_cost_sums_ms=tc);res.append(row)
            for x in fl+viol:examples.append(dict(provider=provider,role=role,**x))
    payload=dict(rows=res,events=examples,statistical_claim=False,same_plaintext_graph='z=.8*x0-.5*x1+1.2*x2-.3; score=.5+.197*z-.004*z^3',same128bit_target_but_identical_security_assumptions_unverified=True,speed_comparison_claim=False,A_selection='official EVA compile scale30range20,no decision gate added',B_selection='original DirectPolicyV2 independent selection',prior_inputs_exposed=True,execution_incident='external selection timing overlaps aborted Fashion attempt; counts/errors retained; timing only diagnostic')
    if args.check:assert same_derived(read(OUT/'EXTERNAL_RESULTS.json'),payload)
    else:
        with (OUT/'EXTERNAL_RESULTS.json').open('x') as f:json.dump(payload,f,indent=2);f.write('\n')
    print('EXTERNAL_NUMERICAL_AND_DECISION_RECOMPUTATION_PASS')
if __name__=='__main__':main()
