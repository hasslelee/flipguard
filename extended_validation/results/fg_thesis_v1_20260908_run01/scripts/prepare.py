from pathlib import Path
import json,csv,hashlib,datetime,subprocess,os,shutil
ROOT=Path('/home/ckks2/deciprotect');RUN=ROOT/'results/fg_thesis_v1_20260908_run01'
DOC=ROOT/'docs/research/fg_thesis_v1_20260908'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
old=read(ROOT/'protocols/FG_CONTRIB_V1.json');cases=old['cases']
bank=ROOT/'results/fg_contrib_v1_20260906_run01/external/hediff_bank'
cases.append(dict(case_id='hediff_bank',kind='bank',model=str(bank/'model.json'),plan=str(bank/'planning/plan.json'),selection=str(bank/'configuration_selection.csv'),audit=[str(bank/'independent_evaluation.csv')],development=str(bank/'development.csv'),selection_inputs=16,audit_inputs=32,thresholds={'max_abs':None}))
settings=[{'id':'base','rho':.5,'delta':.001},{'id':'rho025','rho':.25,'delta':.001},{'id':'rho075','rho':.75,'delta':.001},{'id':'delta0','rho':.5,'delta':0},{'id':'delta0001','rho':.5,'delta':.0001},{'id':'delta01','rho':.5,'delta':.01}]
ids={c['case_id']:c for c in cases}
spam=next(c['case_id'] for c in cases if c['case_id'].startswith('spambase__linear'))
sm=next(c['case_id'] for c in cases if c['case_id'].startswith('spambase__mlp'))
hm=next(c['case_id'] for c in cases if c['case_id'].startswith('htru2__mlp'))
a2=[spam,sm,'fashion_seed0'];a3=[spam,hm];b=[sm,'fashion_seed0','hediff_bank']
subsets=[]
for cid in a3:
 c=ids[cid];rs=list(csv.DictReader(open(c['development'])));held=list(csv.DictReader(open(Path(c['model']).parent/'independent_evaluation.csv')))
 assert len(rs)==256 and len({r['row_id'] for r in rs})==256
 assert not ({r['row_id'] for r in rs}&{r['row_id'] for r in held})
 for seed in [0,1,2]:
  order=sorted(rs,key=lambda r:(hashlib.sha256(f'FG_THESIS_V1_20260908/selection/{seed}/{r["row_id"]}'.encode()).hexdigest(),r['row_id']))
  for n in [16,64,256]:
   p=RUN/'inputs'/cid/f'order{seed}_n{n}.raw.csv';p.parent.mkdir(parents=True,exist_ok=True)
   if p.exists(): assert list(csv.DictReader(p.open()))==order[:n]
   else:
    with p.open('x',newline='') as f:w=csv.DictWriter(f,rs[0].keys());w.writeheader();w.writerows(order[:n])
   subsets.append({'case_id':cid,'input_order_seed':seed,'n':n,'raw':str(p),'sha256':sha(p),'pool':c['development'],'pool_sha256':sha(c['development']),'audit_overlap':0,'nested':True,'key_block':0,'prepared':str(p.parent/p.name.replace('.raw.csv','.prepared/prepared.csv'))})
durations=[]
for p in (ROOT/'results/fg_contrib_v1_20260906_run01/commands').glob('*.end.json'):
 j=read(p)
 if any(cid in p.name for cid in a2+b) and any(x in p.name for x in ['select','audit','timing']):durations.append({'job':p.name,'seconds':j['wall_seconds']})
native_estimate={'basis':'existing command elapsed times, conservative per-job upper bounds; not observed new outcomes','A2_selection_seconds':18*4*120,'A2_A3_audit_seconds':30*3*120,'A3_selection_seconds':18*4*120,'B_selection_seconds':24*4*120,'B_audit_seconds':12*3*120,'paired_time_and_artifact_seconds':7200,'sum_upper_envelope_seconds':sum([18*4*120,30*3*120,18*4*120,24*4*120,12*3*120,7200]),'expected_less_than_upper':'aliases deduplicate audits; past all A/B first acceptance; no reliance on this as stopping rule'}
# 51,120 s envelope is below the single 24-hour cap; no post-result grid reduction.
spec={'protocol_id':'FG_THESIS_V1_20260908','run_id':RUN.name,'locked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'authorization_source':str(RUN/'provenance/00_CODEX_EXECUTE_KO.md'),'authorization_sha256':sha(RUN/'provenance/00_CODEX_EXECUTE_KO.md'),'source_module':'research/thesis_validation_v1','cases':cases,'settings':settings,'A1':{'source':'old frozen output only, all input denominator retained','case_ids':list(ids),'common_applicability':'margin > .01 shared across six settings; tie excluded','events':'decision changes independent of rho at fixed output; delta excludes events rather than repairs them'},'A2':{'cases':a2,'settings':[s['id'] for s in settings],'selection_key_blocks':1,'keys_per_candidate':3,'max_encrypted_candidates':4,'selection_inputs':'unchanged original 32/500; no Cprime','audits':{'tabular':256,'fashion_seed0':1000},'audit_fashion_rows':'first two existing official-test batches audit_00 and audit_01; row order fixed before new outputs; already exposed'},'A3':{'cases':a3,'sizes':[16,64,256],'input_order_seeds':[0,1,2],'pool':'existing development256 only','subsets':subsets,'rho':.5,'delta':.001,'max_candidates':4,'keys_per_candidate':3,'selection_key_blocks_per_subset':1,'audit_inputs':256,'prefix_B':[1,2,4],'key_blocks_not_input_seeds':True},'B':{'cases':b,'roles':['C','Cprime','B30','B30slack'],'selection_blocks':2,'selection_order':'rotate by case index+block, reverse on block1; all four methods scheduled if static auxiliary differs and passes independence/structure checks','keys_per_candidate':3,'max_candidates':4,'rho':.5,'delta':.001,'Cprime':'existing maximize_within_min_log_n before first encrypted candidate; unchanged repair; added static structural validation is counted in selection cost','B30':'unchanged independent start30 and +4; same acceptance','B30slack':'separate auxiliary; independent facts only; increase scale by1 up to50 while same N/Q/P/path/level count; before each B candidate execution, no HE-driven tuning','static_cases':list(ids),'audits':{'hediff_bank':'reserved684 only after all compared configurations frozen; old32 and exposed synthetic16 separate','spambase_mlp':256,'fashion_seed0':1000},'fashion_size_reason':'original per-batch runtime and total upper bound; no score/margin/error based choice','reservation_open_prerequisites':['source/code/rules/selection/model/metrics/batch/key plan hashed','all compared methods selected using original selection data only or final nonselection recorded','FROZEN_SELECTIONS.json immutable; no post-open rule or configuration change'],'reservation_batches':'three batches of228 in locked reservation rank order; 3 fresh keys per distinct literal per batch','reservation_uncertainty':'existing management says unscored; no global access-log proof; previous whole-source normalization and NearMiss exposure retained','stress':'all old16, exposure regression only; no true-label claim','adoption':'decision-error improvement, numerical slack, cost improvement and inconclusive execution separated; no after-the-fact tolerance','extra_algorithm':False},'C_IDS':{'status':'official download access verification in progress','source':'https://research.unsw.edu.au/projects/unsw-nb15-dataset','requirement':'official feature CSV from official source; no third-party substituted corpus','on_unavailable':'DEFERRED_SOURCE_ACCESS; internal A/B continue; prepare explicit nonexecuted plan','models':['linear_poly3','square_mlp_hidden32'],'training_seeds':[0,1,2],'max_models':6,'selection_inputs':64,'audit_inputs':2048,'roles':['A30','B30','C'],'Cprime_in_IDS':False,'no_test_preprocessing':True},'timing':{'inputs':20,'warmup':1,'measure':6,'key_blocks':3,'pairing':'same-time balanced order; each distinct comparator versus reference C; aliases share result','pdf_latency':'encode/encrypt + HE + decrypt/decode','setup':'separate, included equally in end-to-end sums','network':None,'queue':None,'no_outlier_removal':True},'resource':{'native_total_cap_seconds':86400,'per_process_limit_seconds':1800,'address_space_gib':8,'go_memory_limit':'6GiB','GOMAXPROCS':4,'min_available_memory_gib':2,'minimum_free_disk_gib':8,'new_run_storage_cap_gib':8,'serial_native':True,'no_paid_resources':True},'estimate':native_estimate,'stop':'exhaust finite schedule or resource cap; do not create another experiment; thesis writing and judgement mandatory','historical_reuse':'old A/B/C and cause reports, not rerun as new discovery','independent_device':'no separately authorized physical device in current session; prepare bundle, mark not run'}
write(ROOT/'protocols/FG_THESIS_V1_20260908.json',spec)
write(RUN/'PRIOR_RUNTIME_BASIS.json',durations)
shutil.copyfile(ROOT/'protocols/FG_THESIS_V1_20260908.json',RUN/'protocol.json')
print({'protocol':spec['protocol_id'],'A2_jobs':18,'A3_jobs':18,'B_max_selection_jobs':24,'native_envelope_hours':native_estimate['sum_upper_envelope_seconds']/3600,'A3_pool_overlap':0})
