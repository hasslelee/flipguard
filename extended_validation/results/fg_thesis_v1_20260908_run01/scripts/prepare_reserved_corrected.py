"""Pre-open serialization-only correction; frozen audit executor and scientific rules unchanged."""
from audit import *
def reserve_corrected():
    verify_preopen();assert (RUN/'AUDIT_PREOPEN_LOCK.json').exists()
    if (RUN/'RESERVATION_READY.json').exists():
        for p,h in r.read(RUN/'RESERVATION_READY.json')['files'].items():assert r.sha(p)==h
        return
    roles={x['role'] for x in r.read(RUN/'FROZEN_SELECTIONS.json')['records'] if x['case']=='hediff_bank' and x['phase']=='B' and x['literal_id']}
    assert {'C','Cprime','B30'}.issubset(roles),'Bank main comparison lacks selected configuration'
    pool=ROOT/'results/fg_cause_v1_20260906_run01/INPUT_POOL_LOCK.json'
    source=ROOT/'work/fg_contrib_v1_20260906/external_data/bank-additional-full.csv'
    if not (RUN/'RESERVATION_OPEN_STARTED.json').exists():
        r.write(RUN/'RESERVATION_OPEN_STARTED.json',{'utc':r.now(),'preopen_sha256':r.sha(RUN/'AUDIT_PREOPEN_LOCK.json'),
            'pool_path':str(pool),'source_path':str(source),'purpose':'one frozen final comparison, no tuning',
            'existing_management_unscored':684,'global_access_proof_available':False})
    # First payload access occurs only below the persisted lock and access event.
    assert r.sha(pool)=='9183f5188ffac717dc2059fac9a7eb75eab666cbda9aeb31fc0d6d4a1d2c17fb'
    # Expected source digest is reused from the completed cause-analysis READ_BINDINGS record.
    assert r.sha(source)=='74adfc578bf77a7ff4bb1ba4a9f8709d9e3c6907342959c2c8416847e0afb4d8','HISTORICAL_BANK_SOURCE_MISMATCH'
    lock=r.read(pool);reserved=lock['future_audit_reserve'];assert len(reserved)==684
    with source.open() as f:original=list(csv.DictReader(f,delimiter=';'))
    cols=list(original[0])[:-1];assert len(cols)==20
    complete=[(i,x) for i,x in enumerate(original) if all(v not in ['unknown',''] for v in x.values())]
    assert len(complete)==30488
    cats=[1,2,3,4,5,6,7,8,9,14]
    enc={j:{s:n for n,s in enumerate(sorted({x[cols[j]] for _,x in complete}))} for j in cats}
    raw=np.asarray([[enc[j][x[cols[j]]] if j in cats else float(x[cols[j]]) for j in range(20)] for _,x in complete],dtype=np.float32)
    lo=raw.min(0);hi=raw.max(0);lookup={i:n for n,(i,_) in enumerate(complete)}
    def normalized(sid):return ((raw[lookup[int(sid)]]-lo)/(hi-lo)).astype(float)
    # Verify the historical preprocessing exactly, without refitting a new experimental transform.
    checked=0
    for name in ['configuration_selection.csv','development.csv','independent_evaluation.csv']:
        with (OLD/name).open() as f:
            for row in csv.DictReader(f):
                x=np.asarray([float(row[f'x_{j}']) for j in range(20)])
                assert np.array_equal(x,normalized(row['source_row_id'])),('PREPROCESSING_MISMATCH',name,row['row_id'])
                assert int(row['label'])==int(original[int(row['source_row_id'])]['y']=='yes')
                checked+=1
    out=RUN/'inputs/reserved684';out.mkdir(parents=True,exist_ok=True)
    fields=['row_id','label','original_label','source_row_id']+[f'x_{j}' for j in range(20)]
    files={}
    for bi in range(3):
        p=out/f'batch_{bi:02d}.csv';rows=[]
        for rr in reserved[bi*228:(bi+1)*228]:
            sid=int(rr['source_row_id']);label=int(original[sid]['y']=='yes');x=normalized(sid)
            rows.append({'row_id':rr['row_id'],'source_row_id':sid,'label':label,'original_label':label,**{f'x_{j}':repr(float(v)) for j,v in enumerate(x)}})
        if not p.exists():
            with p.open('x',newline='') as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
        else:
            with p.open() as f:assert list(csv.DictReader(f))==[{k:str(v) for k,v in row.items()} for row in rows]
        files[str(p)]=r.sha(p)
    r.write(RUN/'RESERVATION_READY.json',{'utc':r.now(),'files':files,'rows':684,'batches':3,
        'source_sha256':r.sha(source),'pool_sha256':r.sha(pool),'old_rows_exactly_verified':checked,
        'preprocessing':'whole-source complete-case LabelEncoder and float32 minmax reused; prior NearMiss membership reused; no NearMiss rerun',
        'exposure':'previously unscored according to management, not preprocessing-independent population'})

if __name__=='__main__':
    amendment=r.read(RUN/'RESERVATION_FORMAT_PREOPEN_AMENDMENT.json')
    assert r.sha(Path(__file__))==amendment['corrected_preparer_sha256']
    assert r.sha(RUN/'scripts/audit.py')==amendment['original_audit_sha256']
    assert not (RUN/'RESERVATION_OPEN_STARTED.json').exists()
    reserve_corrected()
    ready=r.read(RUN/'RESERVATION_READY.json')
    checked=0
    for path in ready['files']:
        with open(path) as f:
            for row in csv.DictReader(f):
                for j in range(20):
                    v=float(row[f'x_{j}']);assert np.isfinite(v) and 0<=v<=1
                checked+=1
    assert checked==684
    r.write(RUN/'RESERVATION_FORMAT_VERIFICATION.json',{'utc':r.now(),'numeric_csv_rows':checked,'amendment_sha256':r.sha(RUN/'RESERVATION_FORMAT_PREOPEN_AMENDMENT.json'),'ready_sha256':r.sha(RUN/'RESERVATION_READY.json'),'scientific_rules_changed':False,'original_audit_executor_changed':False})
    print('Reserved CSV prepared once after locks;684 valid numeric rows;176 historical rows bit-identical',flush=True)
