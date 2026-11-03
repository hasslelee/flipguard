"""Bounded evidence verification, never archive scanning or experimental reruns."""
import json,os,subprocess,hashlib,csv,sys,zipfile,io
from pathlib import Path
import run as r
import audit,metrics,verify_input_identity
def main():
    audit.verify_preopen();assert metrics.selftest()
    identity_check=verify_input_identity.check()
    start=r.read(r.RUN/'START_STATE.json');preserved=[]
    for path,h in r.read(r.RUN/'CONNECTION_CHECK_INDEX.json')['files'].items():assert r.sha(path)==h
    for p,h in start['preserved_bindings'].items():
        assert r.sha(r.ROOT/p)==h,('PRESERVED_FILE_MISMATCH',p);preserved.append(p)
    fr=r.read(r.RUN/'FROZEN_SELECTIONS.json');assert len(fr['records'])==60
    for x in fr['records']:
        assert (r.RUN/'commands'/(x['id']+'.end.json')).exists()
        if x['result_sha256']:assert r.sha(x['result'])==x['result_sha256']
        if x['literal_id']:assert r.sha(x['candidate_path'])==x['candidate_sha256']
    schedule=r.read(r.RUN/'AUDIT_SCHEDULE.json')
    for x in schedule['audit_jobs']+schedule['timing_jobs']:assert (r.RUN/'commands'/(x['id']+'.end.json')).exists()
    table_dir=r.ROOT/'docs/research/fg_thesis_v1_20260908'
    raw_index=list(csv.DictReader(open(table_dir/'RAW_INDEX.csv')))
    for item in raw_index:assert r.sha(item['path'])==item['sha256'],('RAW_KEY_PAYLOAD_MISMATCH',item['path'])
    timing_index=list(csv.DictReader(open(table_dir/'TIMING_KEY_BLOCKS.csv')))
    for item in timing_index:assert r.sha(item['source'])==item['source_sha256'],('PAIRED_TIME_PAYLOAD_MISMATCH',item['source'])
    audit_table=list(csv.DictReader(open(r.ROOT/'docs/research/fg_thesis_v1_20260908/AUDIT_METRICS.csv')))
    assert all(x['complete_key_count']=='True' for x in audit_table)
    timing_verified=r.read(r.RUN/'TIMING_VERIFIED.json')
    assert timing_verified['pairs']==len(schedule['timing_jobs'])
    expected_material={(x['case'],x['literal_id']) for x in fr['records'] if x['literal_id']}
    assert all((r.RUN/'material_sizes'/case/(lid+'.json')).exists() for case,lid in expected_material)
    # Public parameter identity and source count: new raw keys only.
    checked=0
    for cp in (r.RUN/'selection').glob('*/concrete_*.json'):
        cr=r.read(cp);ordinal=cp.stem.split('_')[-1]
        assert cr['actual_security']['final_admission']=='PASS' and cr['backend_valid']
        for kp in cp.parent.glob(f'trial_{ordinal}/key_*.json'):
            k=r.read(kp);assert k['q']==cr['concrete']['q'] and k['p']==cr['concrete']['p'];checked+=1
    for cp in (r.RUN/'audit').glob('*/*/*/batch_*/concrete.json'):
        cr=r.read(cp);assert cr['actual_security']['final_admission']=='PASS'
        for kp in cp.parent.glob('key_*.json'):
            k=r.read(kp);assert k['q']==cr['concrete']['q'] and k['p']==cr['concrete']['p'];checked+=1
    gate=r.read(r.RUN/'BANK_RESERVED_GATE.json')
    if gate['eligible']:
        ready=r.read(r.RUN/'RESERVATION_READY.json');assert ready['rows']==684 and ready['old_rows_exactly_verified']==176
        for p,h in ready['files'].items():assert r.sha(p)==h
        pre=r.read(r.RUN/'AUDIT_PREOPEN_LOCK.json');opened=r.read(r.RUN/'RESERVATION_OPEN_STARTED.json')
        assert fr['utc']<=pre['utc']<=opened['utc'] and opened['preopen_sha256']==r.sha(r.RUN/'AUDIT_PREOPEN_LOCK.json')
        amendment=r.read(r.RUN/'RESERVATION_FORMAT_PREOPEN_AMENDMENT.json');fmt=r.read(r.RUN/'RESERVATION_FORMAT_VERIFICATION.json')
        assert pre['utc']<=amendment['utc']<=opened['utc']
        assert r.sha(amendment['corrected_preparer'])==amendment['corrected_preparer_sha256']
        assert amendment['original_preopen_lock_sha256']==r.sha(r.RUN/'AUDIT_PREOPEN_LOCK.json')
        assert amendment['frozen_selections_sha256']==r.sha(r.RUN/'FROZEN_SELECTIONS.json')
        assert fmt['ready_sha256']==r.sha(r.RUN/'RESERVATION_READY.json') and fmt['numeric_csv_rows']==684
    for item in r.read(r.RUN/'INDEPENDENT_DEVICE_PREPARATION.json')['staged_files']:assert r.sha(item['copy'])==item['sha256']
    pdf=r.read(r.RUN/'provenance/SUBMISSION_PDF_BINDING.json')
    assert r.sha(pdf['copy'])==r.sha(pdf['source'])==pdf['sha256']
    docs=r.ROOT/'docs/research/fg_thesis_v1_20260908'
    names=['THESIS_STATUS_AND_SCOPE_KO.md','THESIS_EXPERIMENTS_KO.md','CPRIME_DECISION_KO.md','THESIS_DRAFT_KO.md','THESIS_DRAFT_KO.txt']
    for name in names:assert (docs/name).stat().st_size>500
    assert (docs/'THESIS_DRAFT_KO.md').read_bytes()==(docs/'THESIS_DRAFT_KO.txt').read_bytes()
    all_native=sum(r.read(p)['wall_seconds'] for p in (r.RUN/'commands').glob('*.end.json'))
    run_bytes=sum(p.stat().st_size for p in r.RUN.rglob('*') if p.is_file())
    assert all_native<=86400 and run_bytes<=8*1024**3
    env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=r.ROOT,env=env,text=True).strip()
    status=subprocess.check_output(['git','status','--short'],cwd=r.ROOT,env=env,text=True)
    result={'utc':r.now(),'result':'VERIFIED_WITH_SCIENTIFIC_OUTCOMES_PRESERVED','source_and_execution_bindings_match':True,
        'frozen_selected_results_match':True,'old_files_bounded_hash_checked':len(preserved),'old_file_mismatches':0,
        'raw_key_parameter_records_checked':checked,'raw_key_payload_hashes_verified':len(raw_index),'paired_time_payload_hashes_verified':len(timing_index),'all_selection_commands_attempted':60,
        'audit_jobs_attempted':len(schedule['audit_jobs']),'timing_jobs_attempted':len(schedule['timing_jobs']),
        'all_audit_key_counts_complete':True,'all_paired_time_results_complete':True,'material_case_literals_complete':len(expected_material),
        'native_seconds':all_native,'charged_native_seconds':r.used(),'native_cap_seconds':86400,'new_run_bytes':run_bytes,'new_run_cap_bytes':8*1024**3,'reservation_open_gate_verified':gate['eligible'],
        'submission_pdf_copy_identical':True,'post_run_input_identity_checks':identity_check,'head':head,'start_head':start['head'],'head_unchanged':head==start['head'],'status':status,'user_changes_reset':False,
        'archive_scan_or_full_rehash':False,'remote_upload':False,'scientific_pass_not_inferred_from_tests':True,
        'document_hashes':{name:r.sha(docs/name) for name in names}}
    if '--check-only' in sys.argv[1:]:
        prior=r.read(r.RUN/'FINAL_VERIFICATION.json')
        assert result['document_hashes']==prior['document_hashes'],'DOCUMENT_PAYLOAD_MISMATCH'
        result['mode']='READ_ONLY_RECHECK_NO_CKKS_NO_WRITES'
        zip_record=docs/'ZIP_VERIFICATION.json'
        if zip_record.exists():
            zr=r.read(zip_record);assert r.sha(zr['path'])==zr['sha256']
            with zipfile.ZipFile(zr['path']) as z:
                assert z.testzip() is None
                for row in csv.DictReader(io.StringIO(z.read('MANIFEST.csv').decode('utf-8'))):
                    assert hashlib.sha256(z.read(row['zip_path'])).hexdigest()==row['sha256']
            result['local_zip_recheck']='PASS'

    else:r.write(r.RUN/'FINAL_VERIFICATION.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='status'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
