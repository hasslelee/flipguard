"""Paired key-block summaries; no outlier removal and no invented equivalence threshold."""
from pathlib import Path
import json,collections,math,csv,statistics
import numpy as np
import run as r
from analyze_new import csvout

def main():
    rows=[];raw=[];arms=[];groups=collections.defaultdict(list)
    schedule=r.read(r.RUN/'AUDIT_SCHEDULE.json')
    fr=r.read(r.RUN/'FROZEN_SELECTIONS.json')['records']
    def roles(cid,lid):return ';'.join(sorted({x['role'] for x in fr if x['case']==cid and x['literal_id']==lid and x['phase']=='B'}))
    for job in schedule['timing_jobs']:
        p=r.RUN/'timing'/job['id']/'result.json'
        if not p.exists():continue
        j=r.read(p);pairs=collections.defaultdict(dict)
        for rec in j['records']:
            assert rec['measurement_run']>=1
            key=(rec['measurement_run'],rec.get('row_index',0));pairs[key][rec['arm_id']]=rec
            raw.append({'case':job['case'],'reference_literal':job['reference'],'comparator_literal':job['comparator'],
                'reference_roles':roles(job['case'],job['reference']),'comparator_roles':roles(job['case'],job['comparator']),
                'key_block':job['key_block'],'source':str(p),**rec})
        rr=[];diff=[]
        for key,z in pairs.items():
            assert set(z)=={'reference_C','comparator'}
            for a in z.values():
                he=a.get('eval_only_ms',a.get('evaluation_only_ms'))
                assert abs(a['total_ms']-(a['encode_encrypt_ms']+he+a['decrypt_decode_ms']))<1e-4
            rr.append(z['comparator']['total_ms']/z['reference_C']['total_ms'])
            diff.append(z['comparator']['total_ms']-z['reference_C']['total_ms'])
        row={'case':job['case'],'reference_literal':job['reference'],'comparator_literal':job['comparator'],
            'reference_roles':roles(job['case'],job['reference']),'comparator_roles':roles(job['case'],job['comparator']),
            'key_block':job['key_block'],'paired_observations':len(rr),
            'comparator_over_C_geomean':float(np.exp(np.log(rr).mean())),
            'paired_absolute_difference_mean_ms':float(np.mean(diff)),'paired_absolute_difference_median_ms':float(np.median(diff)),
            'paired_difference_min_ms':min(diff),'paired_difference_max_ms':max(diff),
            'unit':'one-input call' if 'spambase' in job['case'] else 'fixed20-input batch',
            'warmup_runs':1,'measurement_runs':6,'source':str(p),'source_sha256':r.sha(p)}
        for arm in j['arms']:
            rs=[z for z in j['records'] if z['arm_id']==arm['id']];t=[z['total_ms'] for z in rs]
            row[arm['id']+'_mean_ms']=float(np.mean(t));row[arm['id']+'_median_ms']=float(np.median(t))
            setup=arm.get('setup_ms',arm.get('setup_keygen_ms'))
            if 'plain_y' in rs[0]:
                pp=np.array([v['plain_y'] for v in rs]);cc=np.array([v['ckks_y'] for v in rs]);gg=abs(pp-.5);app=gg>.001
                flips=(pp>=.5)!=(cc>=.5);bad=abs(cc-pp)>=.5*gg
                assert all(bool(v['decision_flip'])==bool(f) for v,f in zip(rs,flips))
                assert not np.any(flips & app & ~bad)
                timed={'timed_applicable_flip_events':int((flips&app).sum()),'timed_boundary_flip_events':int((flips&~app).sum()),'timed_all_flip_events':int(flips.sum()),'timed_applicable_error_events':int((bad&app).sum()),'timed_applicable_input_run_observations':int(app.sum()),'timed_boundary_input_run_observations':int((~app).sum()),'timed_outcome_scope':'recomputed scalar outputs; repeated encryption under one reused arm-key context, not fresh audit or independent samples'}
            else:
                timed={'timed_applicable_flip_events':sum(v['decision_flips'] for v in rs),'timed_boundary_flip_events':0 if sum(v['v_amb'] for v in rs)==0 else None,'timed_all_flip_events':sum(v['decision_flips'] for v in rs) if sum(v['v_amb'] for v in rs)==0 else None,'timed_applicable_error_events':sum(v['reserve_policy_violations'] for v in rs),'timed_applicable_input_run_observations':sum(v['v_cert'] for v in rs),'timed_boundary_input_run_observations':sum(v['v_amb'] for v in rs),'timed_outcome_scope':'recorded multiclass harness applicable-only aggregates; boundary flips unknown if any boundary inputs; no per-input logits in time records, not independent reconstruction or fresh audit'}
            arms.append({'case':job['case'],'pair_id':job['id'],'arm_id':arm['id'],'key_block':job['key_block'],
                'literal_id':job['reference'] if arm['id']=='reference_C' else job['comparator'],
                'roles':roles(job['case'],job['reference'] if arm['id']=='reference_C' else job['comparator']),
                'log_n':arm['log_n'],'scale_bits':arm['log_default_scale'],'Q_count':len(arm['log_q']),'P_count':len(arm['log_p']),
                'setup_ms':setup,'observations':len(t),'pdf_mean_ms':float(np.mean(t)),'pdf_median_ms':float(np.median(t)),
                'pdf_min_ms':min(t),'pdf_max_ms':max(t),'encode_encrypt_mean_ms':float(np.mean([z['encode_encrypt_ms'] for z in rs])),
                'he_mean_ms':float(np.mean([z.get('eval_only_ms',z.get('evaluation_only_ms')) for z in rs])),
                'decrypt_decode_mean_ms':float(np.mean([z['decrypt_decode_ms'] for z in rs])),
                'setup_plus_first_measured_ms':setup+t[0],
                'setup_plus_measured_sum_ms':setup+sum(t),'network_ms':None,'queue_ms':None,
                'setup_plus_interpretation':'setup plus measured calls; warmup exists and is excluded, not process wall',
                'measurement_unit':row['unit'],**timed})
        rows.append(row);groups[(job['case'],job['reference'],job['comparator'])].append(row)
    summary=[]
    for key,z in groups.items():
        ratios=[x['comparator_over_C_geomean'] for x in z]
        summary.append({'case':key[0],'reference_literal':key[1],'comparator_literal':key[2],
            'reference_roles':z[0]['reference_roles'],'comparator_roles':z[0]['comparator_roles'],'key_blocks':len(z),
            'key_ratio_values':json.dumps(ratios),'equal_key_geomean_ratio':float(np.exp(np.log(ratios).mean())),
            'key_ratio_min':min(ratios),'key_ratio_max':max(ratios),
            'C_key_median_ms':float(np.median([x['reference_C_median_ms'] for x in z])),
            'comparator_key_median_ms':float(np.median([x['comparator_median_ms'] for x in z])),
            'mean_paired_absolute_difference_ms':float(np.mean([x['paired_absolute_difference_mean_ms'] for x in z])),
            'unit':z[0]['unit'],'statistical_scope':'descriptive three key blocks on one host; no population-risk or equivalence claim'})
    csvout('TIMING_KEY_BLOCKS.csv',rows);csvout('TIMING_ARMS.csv',arms);csvout('TIMING_RAW.csv',raw);csvout('TIMING_SUMMARY.csv',summary)
    sizes=[]
    keycosts=list(csv.DictReader(open(r.ROOT/'docs/research/fg_thesis_v1_20260908/KEY_COSTS.csv')))
    for p in sorted((r.RUN/'material_sizes').glob('*/*.json')):
        j=r.read(p);cid=p.parent.name;lid=p.stem
        matching=[x for x in keycosts if x['phase']=='audit' and x['case']==cid and x['job']==lid]
        for k in sorted({tuple(x[y] for y in ['stage','input_ciphertexts_per_batch','output_ciphertexts_per_batch','initial_level','final_level','valid_inputs_per_batch','available_slots']) for x in matching}):
            stage,inc,outc,initial,final,valid,available=k;by={v['level']:v['bytes'] for v in j['ciphertext_by_level']}
            sizes.append({'case':cid,'literal_id':lid,'stage':stage,'log_n':j['log_n'],'valid_inputs_per_batch':valid,'available_slots':available,
                'initial_level':initial,'final_level':final,'input_ciphertexts_per_batch':inc,'output_ciphertexts_per_batch':outc,
                'measured_one_input_ciphertext_bytes':by[int(initial)],'measured_one_output_level_ciphertext_bytes':by[int(final)],
                'derived_input_ciphertexts_bytes':by[int(initial)]*int(inc),'derived_output_ciphertexts_bytes':by[int(final)]*int(outc),
                'measured_public_key_bytes':j['public_key_bytes'],'measured_relinearization_key_bytes':j['relinearization_key_bytes'],
                'measured_rotation_key_count':0,'rotation_path_in_this_bundle':False,
                'key_serialization_ms_single_probe':j['key_serialization_ms'],
                'scope':'actual generated material serialization; ciphertext size at observed levels; aggregate by actual counts, not a network measurement',
                'source':str(p),'source_sha256':r.sha(p)})
    csvout('MATERIAL_SIZES.csv',sizes)
    r.write(r.RUN/'TIMING_VERIFIED.json',{'utc':r.now(),'pairs':len(rows),'pair_groups':len(summary),'arm_blocks':len(arms),
        'retained_observations':len(raw),'material_rows':len(sizes),'matching_formula_verified':True,
        'unmeasured_network_and_queue':'null, not zero','legacy_labels':'embedded prior V17/Bank_B3 wording is inherited harness metadata, not current selector; AUDIT_SCHEDULE and aliases are authoritative'})

if __name__=='__main__':main()
