#!/usr/bin/env python3
"""Independent arithmetic reanalysis; predecessor paths are strictly read-only."""
import csv
import hashlib
import json
import math
from pathlib import Path
from collections import Counter, defaultdict

ROOT=Path(__file__).resolve().parents[1]
OLD=Path('/home/ckks2/flipguard')


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def rows(p,delimiter=','):
    return list(csv.DictReader(p.open(),delimiter=delimiter))


def unwrap(v):
    while isinstance(v,dict) and 'result' in v: v=v['result']
    return v


def trial(v):
    v=unwrap(v)
    return v['trials'][-1] if 'trials' in v else v.get('trial',v.get('audit_trial',v))


def main():
    report=ROOT/'docs/review'; bindings=[];mismatches=[]
    for name,base in [('docs/audit/model_family_expansion_v17/final_vm1x6_release_r3/manifest.json',None),('docs/evidence/model_family_expansion_v17/final_vm1x6/manifest.json',OLD)]:
        p=OLD/name;v=json.loads(p.read_text())
        for row in v['files']:
            f=(base or p.parent)/row['path'];actual=sha(f);expected=row['sha256'].removeprefix('sha256:')
            bindings.append({'path':str(f.relative_to(OLD)),'sha256':actual,'matches':actual==expected})
            if actual!=expected:mismatches.append(str(f))
    coverage=[];read_sources={};unsupported=[];boundary_details=[]
    for row in rows(OLD/'v34_primary_coverage_by_case.tsv','\t'):
        p=OLD/row['source_path'];v=trial(json.loads(p.read_text()));read_sources[row['source_path']]=sha(p)
        ledger=v.get('sample_ledger') or v.get('aggregation',{}).get('observations')
        if not ledger:
            unsupported.append({'case_id':row['case_id'],'stage':row['stage'],'source':row['source_path'],'keys':list(v)})
            continue
        ids={};eligible=set();boundary=set();protected_flips=0;boundary_events=0;boundary_flip_ids=set();all_flip_ids=set();error_violations=0
        for obs in ledger:
            ident=str(obs['sample_id']);key=obs.get('key_repeat',obs.get('key_run'));ids.setdefault(ident,set()).add(key)
            if 'plain_logits' in obs:
                plain=obs['plain_logits'];enc=obs['ckks_logits']
                order=sorted(range(len(plain)),key=lambda i:plain[i],reverse=True)
                top,runner=order[:2]
                margin=plain[top]-plain[runner];cert=margin>.001
                flip=top!=max(range(len(enc)),key=lambda i:enc[i])
                err=[abs(a-b) for a,b in zip(plain,enc)]
                violation=any(err[top]+err[j]>=.5*(plain[top]-plain[j]) for j in range(len(plain)) if j!=top)
            else:
                plain=obs.get('plaintext_score',obs.get('plain_score'))
                if plain is None: raise RuntimeError('Unknown scalar ledger schema')
                margin=abs(plain-obs['threshold']);cert=margin>.001
                flip=(plain>=obs['threshold'])!=(obs['ckks_score']>=obs['threshold'])
                violation=abs(plain-obs['ckks_score'])>=.5*margin
            assert cert==obs['certifiable'],(row['case_id'],ident)
            (eligible if cert else boundary).add(ident)
            if flip:all_flip_ids.add(ident)
            if cert:protected_flips+=int(flip);error_violations+=int(violation)
            elif flip:
                boundary_events+=1;boundary_flip_ids.add(ident)
                boundary_details.append({'case_id':row['case_id'],'stage':row['stage'],'sample_id':ident,'key_repeat':key,'margin':margin,
                                         'plaintext_score':plain,'ckks_score':obs.get('ckks_score'),'threshold':obs.get('threshold'),'source':row['source_path']})
        assert all(len(keys)==3 for keys in ids.values())
        item={'case_id':row['case_id'],'stage':row['stage'],'task_group':row['task_group'],'inputs':len(ids),'eligible':len(eligible),'boundary':len(boundary),'coverage':len(eligible)/len(ids),
              'protected_flip_events':protected_flips,'protected_error_violations':error_violations,'boundary_flip_events':boundary_events,'boundary_unique_flips':len(boundary_flip_ids),
              'all_unique_flips':len(all_flip_ids),'source':row['source_path']}
        assert item['inputs']==int(row['total_inputs']) and item['eligible']==int(row['v_delta'])
        coverage.append(item)
    summary={}
    for stage in ['selection','separate']:
        group=[r for r in coverage if r['stage']==stage]
        sums={k:sum(r[k] for r in group) for k in ['inputs','eligible','boundary','protected_flip_events','protected_error_violations','boundary_flip_events','boundary_unique_flips','all_unique_flips']}
        sums.update(cases=len(group),pooled_coverage=sums['eligible']/sums['inputs'],minimum_coverage=min(r['coverage'] for r in group))
        summary[stage]=sums
    inv=rows(OLD/'docs/reports/comparison_extension_v18/PRIMARY_68_CASE_INVENTORY.csv')
    facts=json.loads((OLD/'docs/reports/comparison_extension_v18/PAPER_FACTS_V18_LOCKED.json').read_text())
    topology=Counter((r['dataset'],r['model_id']) for r in inv)
    answer={'status':'PASS' if not mismatches else 'INTEGRITY_BLOCK','verified_manifest_files':len(bindings),'manifest_mismatches':mismatches,
            'raw_all_task_coverage':summary,'not_recomputed_sources':unsupported,
            'comparison':{'cases':len(inv),'dataset_model_clusters':len(topology),'same_final_and_fastest_finite_candidate':sum(r['full_method_selected_candidate']==r['formal_reference_candidate'] for r in inv),
                          'full_evaluations':sum(int(r['full_method_candidate_evaluations']) for r in inv),'finite_evaluations':facts['finite_reference']['finite_reference_evaluations'],
                          'minimum_error_baseline_violating_cases':facts['traditional_objectives']['minimum_error_union_unstable_cases']},
            'limits':'Coverage and flips independently recomputed from scalar scores or multiclass logits. Source paths follow the frozen V34 inventory and their individual hashes are recorded. Key repeats are not independent inputs.',
            'source_sha256':read_sources}
    (report/'legacy_reanalysis.json').write_text(json.dumps(answer,indent=2)+'\n')
    for name,rs in [('all_coverage_recomputed.csv',coverage),('manifest_verification.csv',bindings),('boundary_flip_events.csv',boundary_details)]:
        with (report/name).open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
    print(json.dumps({k:v for k,v in answer.items() if k!='source_sha256'},indent=2))


if __name__=='__main__':main()
