#!/usr/bin/env python3
"""Stored-output quality for the original63 additional cases, never new HE."""
import importlib.util,json
from pathlib import Path
ROOT=Path('/home/ckks2/deciprotect')
s=importlib.util.spec_from_file_location('evidence',ROOT/'scripts/analyze_journal_evidence_v1.py')
e=importlib.util.module_from_spec(s);s.loader.exec_module(e)
legacy=e.rows(e.DOC/'evidence_tables/ADDITIONAL_63_CASES.csv')
bind=e.js(e.LEG/'LEGACY_SOURCE_BINDINGS.json');out=[];meta=[]
for index,r in enumerate(legacy,1):
    sp=Path(r['selection_source']);ap=Path(r['audit_source'])
    selection=e.unwrap(e.js(sp,bind.get(str(sp))));audit=e.unwrap(e.js(ap,bind.get(str(ap))))
    c=selection['plan']['contract'];mp=e.rawpath(c['model_artifact']['path']);m=e.js(mp,c['model_artifact']['sha256']);mh=e.bindings[str(mp)]['sha256']
    multi='multiclass_decision' in c;packed='packed' in r['group']
    if multi:
        sm=e.js(e.rawpath(m['split_manifest']['path']),m['split_manifest']['sha256'])
        vp=e.rawpath(c['validation_data']['path']);dp=e.OLD/'datasets/journal_multiclass_extension_v1/mnist/locked_audit.csv'
    elif packed:
        sm=e.js(mp.parent/'extraction_manifest.json');vp=e.rawpath(c['validation_data']['path']);dp=e.rawpath(audit['audit_contract']['validation_data']['path'])
    else:
        sm=e.js(mp.parent/'manifest.json');vp=e.rawpath(c['source_data']['path']);dp=mp.parent/'independent_evaluation.csv'
        assert sm['model_sha256'].removeprefix('sha256:')==mh
    sample_sets=[]
    for role,t,p,raw in [('selection',selection['trials'][-1],vp,sp),('separate',e.trial(audit),dp,ap)]:
        metrics,pred=e.metrics(t);labels,_=e.label_map(p)
        if not packed:
            expected=sm['partitions']['configuration_validation' if role=='selection' else 'locked_audit']['sha256'] if multi else sm['roles']['configuration_selection' if role=='selection' else 'independent_evaluation']['sha256']
            assert e.bindings[str(p)]['sha256']==expected.removeprefix('sha256:')
        elif role=='selection':assert e.bindings[str(p)]['sha256']==c['validation_data']['sha256'].removeprefix('sha256:')
        q=e.quality(r['case_id'],role,pred,labels,p,mh)
        out.append({**q,'group':r['group'],**metrics,'raw_output_source':str(raw),'raw_output_sha256':e.bindings[str(raw)]['sha256'],'label_sha256':e.bindings[str(p)]['sha256']})
        sample_sets.append(set(labels))
    assert not sample_sets[0]&sample_sets[1]
    meta.append({'case_id':r['case_id'],'group':r['group'],'model_source':str(mp),'model_sha256':mh,
                 'architecture':m.get('architecture',{'model_type':m.get('model_type'),'input_dim':m.get('input_dim'),'output':m.get('polynomial_score')}),
                 'training':m.get('training',{'seed':m.get('training_seed'),'train_rows':m.get('train_samples'),'procedure':'as-run build_v17_plaintext_suite.py'}),
                 'stored_quality':m.get('plaintext_accuracy',sm.get('quality_independent_evaluation',{})),
                 'quality_scope':'additional63; never merged into primary68','convergence_claim':False})
    if index%15==0:print(f'ADDITIONAL {index}/63',flush=True)
e.table('ADDITIONAL_63_QUALITY_BY_ROLE.csv',out);e.table('ADDITIONAL_63_MODEL_METADATA.csv',meta)
e.dump(e.RUN/'ADDITIONAL_QUALITY_READ_BINDINGS.json',e.bindings)
e.dump(e.RUN/'ADDITIONAL_QUALITY_VALIDATION.json',{'cases':len(legacy),'role_rows':len(out),'selection_separate_disjoint_cases':len(legacy),'separate_protected_flip_observations':sum(r['protected_flips'] for r in out if r['role']=='separate'),'separate_protected_error_violations':sum(r['protected_error_violations'] for r in out if r['role']=='separate'),'new_model_inference':0,'new_ckks':0,'retraining':0})
print('ADDITIONAL_QUALITY_COMPLETE',flush=True)
