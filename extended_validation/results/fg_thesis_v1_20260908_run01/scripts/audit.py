"""Finite post-selection audit. Reservation access is fail-closed until pre-open bindings exist."""
import sys,csv,json,hashlib,collections,fcntl,os
from pathlib import Path
import numpy as np
import run as r
import metrics
RUN=r.RUN;ROOT=r.ROOT;DOC=ROOT/'docs/research/fg_thesis_v1_20260908'
OLD=ROOT/'results/fg_contrib_v1_20260906_run01/external/hediff_bank'

def verify_preopen():
    r.verify()
    for p,h in r.read(RUN/'PREPARED_INPUT_LOCK.json')['files'].items():assert r.sha(p)==h
    if (RUN/'AUDIT_PREOPEN_LOCK.json').exists():
        for p,h in r.read(RUN/'AUDIT_PREOPEN_LOCK.json')['files'].items():assert r.sha(p)==h,('PREOPEN_MISMATCH',p)

def size_guard():
    # Bound newly created evidence, not archive or old results.
    total=sum(p.stat().st_size for p in RUN.rglob('*') if p.is_file())
    if total>8*1024**3:raise RuntimeError('NEW_STORAGE_CAP_8GIB')

def prepare():
    verify_preopen();assert metrics.selftest()
    fr=r.read(RUN/'FROZEN_SELECTIONS.json');sp=r.read(r.PROTOCOL)
    assert len(fr['records'])==60
    for x in fr['records']:
        if x['literal_id']:assert r.sha(x['candidate_path'])==x['candidate_sha256']
    configs=collections.defaultdict(dict)
    for x in fr['records']:
        if x['literal_id']:configs[x['case']][x['literal_id']]=x['candidate_path']
    bank_roles={x['role'] for x in fr['records'] if x['case']=='hediff_bank' and x['phase']=='B' and x['literal_id']}
    reserve_eligible={'C','Cprime','B30'}.issubset(bank_roles)
    r.write(RUN/'BANK_RESERVED_GATE.json',{'utc':r.now(),'selected_roles':sorted(bank_roles),'eligible':reserve_eligible,
        'reason':'all main configurations fixed' if reserve_eligible else 'main comparison missing selection; defer reserved subset, continue independent audits'})
    # Fixed old normal data for timing: no reservation outputs used for timing design.
    timingbank=RUN/'inputs/bank_timing_old20.csv'
    with (OLD/'independent_evaluation.csv').open() as f:
        rd=csv.DictReader(f);fields=rd.fieldnames;rows=list(rd)[:20]
    if not timingbank.exists():
        with timingbank.open('x',newline='') as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
    jobs=[];timing=[];cs={c['case_id']:c for c in sp['cases']}
    for cid,confs in sorted(configs.items()):
        c=cs[cid]
        batches=[('existing_audit',i,p) for i,p in enumerate(c['audit'][:2])]
        if c['kind']=='bank':
            batches += [('exposed_synthetic',0,str(OLD/'stress.csv'))]
            if reserve_eligible:batches += [('reserved684',i,str(RUN/f'inputs/reserved684/batch_{i:02d}.csv')) for i in range(3)]
        for stage,bi,data in batches:
            # Round-robin literal order by batch; never keyed to measured outcomes.
            lids=sorted(confs);shift=bi%len(lids);lids=lids[shift:]+lids[:shift]
            for lid in lids:
                jobs.append({'id':f'audit_{cid}_{stage}_{bi}_{lid}','case':cid,'literal_id':lid,
                    'candidate':confs[lid],'stage':stage,'batch':bi,'data':data,'keys':3,
                    'mode':'raw-stress' if stage=='exposed_synthetic' else 'audit'})
        if cid in sp['B']['cases']:
            br=[x for x in fr['records'] if x['phase']=='B' and x['case']==cid and x['literal_id']]
            # Distinct actually selected C references, with all other B literals. Identical arm -> alias.
            refs=sorted({x['literal_id'] for x in br if x['role']=='C'})
            others=sorted({x['literal_id'] for x in br if x['role']!='C'})
            for ref in refs:
                for other in others:
                    if ref==other:continue
                    # Existing paired harness requires positive key-block ordinals.
                    for key in range(1,4):
                        timing.append({'id':f'timing_{cid}_{ref}_{other}_key{key}','case':cid,
                            'reference':ref,'comparator':other,'candidate':confs[ref],'other':confs[other],
                            'key_block':key,'data':str(timingbank) if c['kind']=='bank' else c['audit'][0]})
    schedule={'utc':r.now(),'frozen_sha256':r.sha(RUN/'FROZEN_SELECTIONS.json'),'audit_jobs':jobs,
        'timing_jobs':timing,'metrics':'strict margin>delta; all competitor error sums<rho*gap; no pooled risk bound',
        'failure_policy':'retain partial key evidence and execution failures, no configuration change or rerun',
        'reserved_order':'existing reservation rank order; three contiguous batches228; 3 fresh contexts per literal/batch',
        'reference_conditions_for_raw_audit':{'rho':.5,'delta':.001},
        'settings_reporting':'A2 raw outputs reclassified at each selected setting; audit is shared across identical literals'}
    r.write(RUN/'AUDIT_SCHEDULE.json',schedule)
    paths=[Path(__file__),Path(metrics.__file__),RUN/'FROZEN_SELECTIONS.json',RUN/'AUDIT_SCHEDULE.json',
           RUN/'SOURCE_LOCK.json',RUN/'EXECUTION_BINDING.json',RUN/'PREPARED_INPUT_LOCK.json',timingbank,
           OLD/'stress.csv',ROOT/'results/fg_cause_v1_20260906_run01/READ_BINDINGS.json']+[Path(p) for co in configs.values() for p in co.values()]
    paths += list((RUN/'sizeprobe').glob('*.go'))+list((RUN/'sizeprobe').glob('go.*'))
    paths += [RUN/'bin/size-probe',RUN/'scripts/size_probe.py',RUN/'BANK_RESERVED_GATE.json']
    r.write(RUN/'AUDIT_PREOPEN_LOCK.json',{'utc':r.now(),'files':{str(p):r.sha(p) for p in paths},
        'reserved_payload_opened':False,'rules_and_all_selections_frozen':True,
        'metadata_prior_unscored':684,'prior_full_source_preprocessing_exposure':True,
        'no_policy_retuning_after_open':True,'B_auxiliary_included':'B30slack'})

def reserve():
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
            rows.append({'row_id':rr['row_id'],'source_row_id':sid,'label':label,'original_label':label,**{f'x_{j}':repr(v) for j,v in enumerate(x)}})
        if not p.exists():
            with p.open('x',newline='') as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
        else:
            with p.open() as f:assert list(csv.DictReader(f))==[{k:str(v) for k,v in row.items()} for row in rows]
        files[str(p)]=r.sha(p)
    r.write(RUN/'RESERVATION_READY.json',{'utc':r.now(),'files':files,'rows':684,'batches':3,
        'source_sha256':r.sha(source),'pool_sha256':r.sha(pool),'old_rows_exactly_verified':checked,
        'preprocessing':'whole-source complete-case LabelEncoder and float32 minmax reused; prior NearMiss membership reused; no NearMiss rerun',
        'exposure':'previously unscored according to management, not preprocessing-independent population'})

def execute(phase):
    verify_preopen();schedule=r.read(RUN/'AUDIT_SCHEDULE.json');cs={c['case_id']:c for c in r.read(r.PROTOCOL)['cases']}
    jobs=schedule['audit_jobs'] if phase=='audit' else schedule['timing_jobs']
    for j in jobs:
        verify_preopen();size_guard();c=cs[j['case']]
        if phase=='audit':
            if j['stage']=='reserved684':reserve()
            args=['--mode',j['mode'],'--legacy-plan',c['plan'],'--candidate',j['candidate'],'--data',j['data'],
                  '--out',RUN/'audit'/j['case']/j['literal_id']/j['stage']/f"batch_{j['batch']:02d}"]
        else:
            args=['--mode','timing','--legacy-plan',c['plan'],'--candidate',j['candidate'],'--other',j['other'],
                  '--data',j['data'],'--keyset',str(j['key_block']),'--out',RUN/'timing'/j['id']]
        r.call(j['id'],args,c['kind']=='bank')
    r.write(RUN/f'{phase.upper()}_COMPLETED.json',{'utc':r.now(),'attempted_jobs':len(jobs),'native_seconds':r.used()})

if __name__=='__main__':
    with (RUN/'native.lock').open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        phase=sys.argv[1]
        if phase in ['prepare','reserve']:globals()[phase]()
        else:execute(phase)
