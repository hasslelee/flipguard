#!/usr/bin/env python3
"""Check the new evidence tables, preserve sources, and package only this task."""
import csv,hashlib,json,math,re,subprocess,zipfile
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('/home/ckks2/deciprotect');DOC=ROOT/'docs/research/fg_journal_evidence_v1_20260906';RUN=ROOT/'results/fg_journal_evidence_v1_20260906_run01'
T=DOC/'evidence_tables';checks=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def js(p):return json.loads(Path(p).read_text())
def rows(n):return list(csv.DictReader((T/n).open()))
def check(n,ok,detail=None):
    checks.append({'check':n,'pass':bool(ok),'detail':detail});assert ok,(n,detail)
def dump(p,obj):
    with Path(p).open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def write(p,s):
    with Path(p).open('x') as f:f.write(s.strip()+'\n')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True)

start=js(RUN/'START_STATE.json');head=git('rev-parse','HEAD').strip();status=git('status','--short')
check('HEAD_unchanged',head==start['head'],head)
check('tracked_and_staged_changes_absent',git('diff','--name-only')=='' and git('diff','--cached','--name-only')=='')
initial=set(start['initial_status'].splitlines());check('initial_untracked_entries_preserved',initial<=set(status.splitlines()))
allowed={'?? docs/research/fg_journal_evidence_v1_20260906/','?? results/fg_journal_evidence_v1_20260906_run01/'}
scripts=['analyze_journal_evidence_v1.py','collect_journal_evidence_details_v1.py','collect_journal_additional_quality_v1.py','write_journal_evidence_documents_v1.py','verify_package_journal_evidence_v1.py']
allowed|={'?? scripts/'+n for n in scripts};check('new_git_entries_in_authorized_scope',set(status.splitlines())-initial<=allowed)
check('final_PDF_identity',sha(ROOT/'baseline/journal_final_20260905.pdf')=='0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85')
lock=js(ROOT/'results/fg_journal_review_v1_20260906_run01/PAPER_REVIEW_LOCK.json')
paper=ROOT/'docs/research/fg_journal_review_v1_20260906/JOURNAL_REVIEW_HANDOFF/PAPER_ONLY'
for n in ('PAPER_ONLY_REVIEW_KO.md','CLAIM_EVIDENCE.csv'):
    check('preserved_review_'+n,sha(paper/n)==lock['files'][n])
for r in rows('SOURCE_CLOSURE.csv'):
    check('as_run_source_'+r['relative_source'],sha(r['read_path'])==r['sha256']==r['as_run_sha256'].removeprefix('sha256:'))
check('bound_analysis_source',all(r['match'] and sha(r['source'])==r['as_run_sha256'].removeprefix('sha256:') for r in js(T/'ADDITIONAL_SOURCE_CLOSURE.json')))
for n in scripts:compile((ROOT/'scripts'/n).read_text(),n,'exec')
check('analysis_reporting_scripts_compile_without_cache',True)

c=rows('CANDIDATE_SPECIFICATIONS.csv');counts=Counter(r['role'] for r in c)
check('actual_candidate_denominators',counts=={'direct':89,'finite':537},dict(counts))
check('actual_three_key_runs_each',all(int(r['key_runs_completed'])==3 for r in c))
check('candidate_materializations_all_finite',all(r['security_admission']=='PASS' and r['status'] in ('SAFE','REJECTED') and int(r['key_observations'])>0 for r in c))
check('candidate_literal_fingerprints',all(hashlib.sha256(json.dumps({'parameters':json.loads(r['literal_spec_json']),'path':r['execution_path']},sort_keys=True,separators=(',',':')).encode()).hexdigest()==r['literal_path_sha256'] for r in c))
check('finite_result_counts',Counter(r['status'] for r in c if r['role']=='finite')=={'SAFE':477,'REJECTED':60})
check('finite_case_count_distribution',Counter(Counter(r['case_id'] for r in c if r['role']=='finite').values())=={8:67,1:1})
first=[r for r in c if r['role']=='direct' and int(r['evaluation_ordinal'])==1]
check('initial_internal_failures',sum(int(r['protected_flips'])>0 for r in first)==20 and sum(int(r['protected_error_violations'])>0 for r in first)==21)
diag=rows('CANDIDATE_ID_LITERAL_RECONCILIATION.csv')
check('ID_and_literal_distinction',sum(r['fastest_executable_different_id']=='True' for r in diag)==23 and sum(r['fastest_executable_different_parameters_path']=='True' for r in diag)==21 and sum(r['acceptable_same_parameters_path']=='True' for r in diag)==65)
scope=rows('CASE_SCOPE_AND_QUALITY.csv');check('scope_role_rows',len(scope)==136)
for role,n,a,b in [('selection',18385,16081,2304),('separate',18367,16049,2318)]:
    rr=[r for r in scope if r['stage']==role]
    check('primary_scope_'+role,all(sum(int(r[k]) for r in rr)==v for k,v in [('inputs',n),('applicable',a),('boundary',b),('key_observations',3*n)]))
    check('protected_final_zero_'+role,all(int(r['protected_flips'])==int(r['protected_error_violations'])==0 for r in rr))
quality=rows('MODEL_QUALITY_BY_ROLE.csv');check('primary_quality_201_rows',len(quality)==201)
for r in quality+rows('ADDITIONAL_63_QUALITY_BY_ROLE.csv'):
    matrix=json.loads(r['confusion_true_pred']);cc=json.loads(r['class_counts']);n=int(r['n']);correct=sum(v for k,v in matrix.items() if k.split('->')[0]==k.split('->')[1])
    check('quality_denominator_'+r['case_id']+'_'+r['role'],sum(matrix.values())==sum(cc.values())==n and correct==int(r['correct']) and abs(correct/n-float(r['accuracy']))<1e-15)
a=js(RUN/'ANALYSIS.json');check('plaintext_replay_checks',len(a['checks'])==65 and all(r['pass'] and r['max_abs_gap']<1e-10 for r in a['checks']))
add=js(RUN/'ADDITIONAL_QUALITY_VALIDATION.json');check('additional_negative_preserved',add['cases']==63 and add['role_rows']==126 and add['separate_protected_flip_observations']==0 and add['separate_protected_error_violations']==1)
check('additional_vs_depth',len(rows('ADDITIONAL_63_CASES.csv'))==63 and len(rows('DEPTH_5_CONDITIONS.csv'))==5 and sum(int(r['jobs']) for r in rows('RUN_CLASSIFICATION.csv'))==204)
tm=rows('TIMING_BY_CASE.csv');check('paired_observation_count',len(tm)==68 and sum(int(r['paired_ratios']) for r in tm)==23454)
cost=rows('COST_COMPONENTS_AND_SETUP.csv');check('cost_arms_136',len(cost)==136 and sum(int(r['observations']) for r in cost)==46908 and all(int(r['key_contexts'])==3 for r in cost))
cr=js(T/'COST_RECONCILIATION.json');check('cost_equal_cluster_point',abs(cr['paired_point_recomputed']-1.000540931232697)<1e-14)
check('cost_stage_common66',cr['common_stage_timer_cases']==66 and abs(cr['direct_total_ms']-13754260.638)<1e-6 and abs(cr['finite_total_ms']-167825454.593)<1e-6)
example=js(T/'WORKED_EXAMPLE_ARITHMETIC.json');check('example_sensitivity',abs(example['aggregate_sensitivity']-2.576)<1e-12)
z=js(T/'ACTUAL_DECISION_REPAIR_EXAMPLE.json');i=z['initial_observation'];f=z['selected_observation']
check('real_input_repair_example',i['decision_margin']>.001 and i['decision_flip'] and i['error_violation'] and not f['decision_flip'] and not f['error_violation'] and i['sample_id']==f['sample_id']=='226')
for r in rows('PATCH_ANCHORS.csv'):
    text=(ROOT/f"results/fg_journal_review_v1_20260906_run01/pdf_page_{int(r['page']):02d}.txt").read_text()
    check('PDF_anchor_'+r['patch_id']+'_'+r['anchor_role'],re.sub(r'\s+','',r['anchor']) in re.sub(r'\s+','',text))
check('manuscript_insertion_units',len(re.findall(r'^## P\d+', (DOC/'MANUSCRIPT_PATCH_KO.md').read_text(),re.M))==12)

# Consolidated provenance: previous summaries' hash bindings are retained, not
# replaced by a fresh full archive scan. Only files actually used are indexed.
binding_names=['READ_BINDINGS.json','DETAIL_READ_BINDINGS.json','ADDITIONAL_QUALITY_READ_BINDINGS.json'];combined={}
for name in binding_names:
    for p,v in js(RUN/name).items():
        if p in combined:check('consistent_binding_'+p,combined[p]['sha256']==v['sha256'])
        combined[p]=v
check('no_reserved_or_archive_reads',not any('/archive/' in p or 'fg_cause_v1_20260906_run01' in p for p in combined))
check('no_secret_artifact_reads',not any(Path(p).suffix in ('.pem','.key','.p12') for p in combined))
dump(RUN/'REAGGREGATION_VALIDATION.json',{'status':'PASS','created_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'new_ckks_runs':0,'new_parameter_generation':0,'new_training_runs':0,'reserved_684_access':False,'bootstrap_interval':'reused existing validated frozen interval; point reaggregated','limitations':['finite pre-generation failures not individually logged','two primary multiclass direct selection wall clocks missing','exact-prime binding limited to two primary multiclass candidates','no universal stability or global optimality claim']})
dump(RUN/'END_STATE.json',{'head':head,'status':status,'tracked_changes':[],'staged_changes':[],'initial_untracked_preserved':True,'modified_prior_reports':False,'targeted_old_hash_checks':'final PDF, two locked review files, cited as-run source files only; no old ZIP CRC/full archive scan','new_roots':[str(DOC),str(RUN)],'new_scripts':scripts,'push_or_upload':False,'automatic_followup':False})

prov=DOC/'provenance';prov.mkdir();code=DOC/'reproduction_scripts';code.mkdir();sync=DOC/'project_sync';sync.mkdir()
copied=[]
def cp(source,target,role):
    b=Path(source).read_bytes()
    with Path(target).open('xb') as f:f.write(b)
    copied.append({'file':str(Path(target).relative_to(DOC)),'source':str(source),'source_sha256':hashlib.sha256(b).hexdigest(),'kind':'byte-identical copy','role':role})
for n in ['START_STATE.json','ANALYSIS.json','ADDITIONAL_QUALITY_VALIDATION.json','REAGGREGATION_VALIDATION.json','END_STATE.json']+binding_names:
    cp(RUN/n,prov/n,'new task provenance or reaggregation validation')
for n in scripts:cp(ROOT/'scripts'/n,code/n,'new task analysis/report/validation source; no original HE execution')
cp('/home/ckks2/Downloads/CKKS_최종논문_기존증거보강_Codex_실행지시.md',prov/'USER_EXECUTION_REQUEST.md','current explicit task instruction')
# Two small existing records preserve original dataset-source hashes as well as
# the generated table's separately named file-source hashes.
for n in ['base_mlp100','base_lenet5_small']:
    p=Path('/home/ckks2/flipguard/results/model_family_expansion_v17/plaintext/multiclass_quality')/n/'quality.json'
    cp(p,DOC/'source_excerpts'/f'EXISTING_FULL_TEST_{n}.json','existing plaintext quality; model hash bound to primary case')
write(sync/'PROJECT_SYNC_INDEX.md','''# 이번 기존 증거 보강의 인계

최신 사용자 지시, 최종 PDF, 동결 protocol/raw와 대응 소스, 재집계 순으로 해석한다. 기존 현재 sync와 완료 묶음을 보존하기 위해 이 작업의 sync만 새 폴더에 작성했다.

MANUSCRIPT_PATCH_KO.md의 12개 삽입·교체안과 보충자료를 검토한다. PDF에 자동 적용하지 않았고 이전 PAPER_ONLY 심사를 수정하지 않았다. 완료된 A/B/C 무차이와 Bank 실패를 유지한다. C′·Bank 사분위 선택·예약684 사용은 미실행이며 이번 ZIP 전달 이후 자동 확장하지 않는다.
''')
write(sync/'CHATGPT_HANDOFF.md','''# 최종 논문 기존 증거 보강 완료 인계

기존 CKKS 결과와 평문 산술로 초기 합성 예시, 626행 구성 명세(89+537), 주요68·추가63 모델의 역할별 품질과 분모, 136개 시간 arm의 실제 비용 성분을 채웠다. 원고용 문안 12개는 MANUSCRIPT_PATCH_KO.md에 있다.

핵심 구분: 유한집합은 제안 초기 마진 합성에 의존한다. 최속 실행의 다른 ID23 중 실제 파라미터 차이는21, 최속수용과C는65/68에서 같은 구성이다. 추가63모델과깊이5그래프는 별개다. 주요 분모와 89/537은 원래 값과 일치한다. A/B 추가 판정 개선과 C′의 B 대비 추가 가치는 미확인이다.

보안 사후검사의 한정 범위, 누락된2MC 선택시간·수렴 로그와 미생성 branch 로그는 보충자료에 적었다. 새 CKKS·소수 생성·재학습·C변경·예약 감사 접근·push는 없다. 재집계 검증은 provenance/REAGGREGATION_VALIDATION.json, ZIP 무결성은 ZIP 옆 검증 파일을 사용한다. 사용자가 원고 반영이나 별도 실험을 결정하기 전 자동 후속 실행은 없다.
''')
dump(sync/'RESEARCH_STATE.json',{'task_id':start['task_id'],'status':'DOCUMENT_AND_EXISTING_EVIDENCE_COMPLETE','head':head,'manuscript_applied':False,'new_ckks':0,'new_training':0,'new_parameter_generation':0,'C_changed':False,'reserved_684_used':False,'automatic_followup':False})
write(DOC/'DATA_DICTIONARY_KO.md','''# 집계표와 계산 규칙

CSV의 수치·식별자 원본은 각 행의 source/raw_source/label_source/model_source 및 SHA/JSON pointer에 연결된다. SHA가 행에 없으면 provenance의 READ_BINDINGS 세 파일에서 그 정확한 경로를 찾는다. 새 숫자를 산출한 함수는 reproduction_scripts에 실제 포함했다. source_excerpts의 복사·발췌 내역은 evidence_tables/SOURCE_COPY_MANIFEST.json과 최상위 MANIFEST.json에 있다.

| Table group | Fields and calculation |
| --- | --- |
| CANDIDATE_SPECIFICATIONS | 전체 저장 parameters와 path를 canonical JSON으로 묶어 SHA. 실제 trial별 전체 입력 ledger, key index별 관측. 이진 margin>0.001, abs error>=0.5margin이면 위반. 다중 클래스는 모든 경쟁자의 두 실제 절대오차 합/(0.5×평문 점수차)의 최댓값>=1이면 위반. 실제 argmax 변화와 구분. |
| CANDIDATE_COUNT / ID_LITERAL_RECONCILIATION | 실제 실행 가능한 모든 finite 후보 중 mean_total_ms 최솟값과 SAFE 중 최솟값. 동률은 원래 trial_index 순. ID와 전체 parameters/path의 일치를 각각 계산. |
| CASE_SCOPE_AND_QUALITY | 선택된 후보의 입력 ID 중복 제거, 모든 키에서 같은 평문인지 검증. 전체/적용/경계 입력 및 키 관측, 전체 출력 범위, 전체 최대오차, 적용 영역 최대 예산 사용률. 경계 판정 변화는 따로 집계. |
| MODEL_QUALITY_BY_ROLE | 정답–예측 confusion의 대각합/n. balanced accuracy는 실제 클래스별 recall 평균, macroF1은 클래스별 F1 평균. 키 관측을 중복하지 않음. training65는 동결 모델 평문 산술, 나머지는 저장 출력. |
| MODEL_TASK_AND_TRAINING / MODEL_METADATA | 저장 모델 구조·학습·전처리 metadata와 SHA. 없는 종료·수렴 판단을 만들어 넣지 않음. MC의 online epoch metric은 최종 모델 train 정확도로 대체하지 않음. |
| ADDITIONAL_63_* | 원래 추가 그룹 30+24+6+3, 선택/별도126행. 주요68과 분리. 원래 출력/레이블 및 모델 SHA 연결. |
| MODEL_SUMMARY | 동일 dataset/model의 별도 역할을 합계. 정답률·적용비율·사례별 시간 중앙값의 범위. 서로 다른 분할의 정답률을 단일 독립 실험으로 합하지 않음. |
| INPUT_UNITS | dataset/role 내부 고유 source ID 수. 모델/분할/키/슬롯 반복과 구분하며 다른 MNIST export 사이의 전역 독립성은 주장하지 않음. |
| TIMING_BY_CASE | keyset/measurement_run/row(또는batch)를 대응시킨 finite/direct 기하평균. 절대시간은 전체 해당 arm 기록의 중앙값. 조정 전후는 별도 선택 단계 mean_total_ms 비율. |
| COST_COMPONENTS_AND_SETUP | 실제 기록된 성분별 평균, 총시간 평균/중앙값, 키 문맥당 준비비 평균. 총시간에서 성분 합을 뺀 잔여는 특정 원인으로 배정하지 않음. setup은 추론 total 밖. network·별도gate는 미측정. |
| SYNTHESIS / WORKED_EXAMPLE | 원래 contract·policy·literal·trial 재사용. 고정모델/선택 입력으로 노드 구간을 복원하고 민감도·ceil 정밀도만 평문 산술로 확인. actual primes 생성 없음. |
| SECURITY_CHECK_SCOPE | 기존 reconciliation의 후보 ID+literal을 주요 선택2후보와 직접 연결. 기존 실제Q/QP·estimator 결과만 재사용. |
| EXISTING_FULL_TEST_PLAINTEXT_QUALITY | 저장된10,000평문 결과. source_sha256은 이번 집계에서 읽은 quality.json의 파일 SHA이며 원래 데이터셋 SHA와 다름. 원래 필드를 보존한 두 사본도 source_excerpts/EXISTING_FULL_TEST_*.json에 제공. |
| PATCH_ANCHORS | 최종 PDF 기존 page text의 공백 제거 문자열과 앞/대상/뒤 발췌 대조. 조판용 쪽 번호이며 새 PDF를 생성하지 않음. |
| COMPARISON_EVIDENCE_SCOPE | 원래PDF/완료후속/문헌 확인을 구분한 기존 기록 전사. 이번 새 비교나 성능 실험이 아님. |

생성되지 않은 후보와 누락된 timing은 0행으로 위장하지 않는다. 원래 run_manifest의 시작 상태와 최종 run_status의 완료 목록은 시점이 다른 기록이다. 통계 신뢰구간은 기존 검증치를 재사용했고 이번에는 대응 추정치와 총계를 검증했다.
''')
write(DOC/'README_KO.md','''# 최종 논문 기존 증거 보강 v1

먼저 MANUSCRIPT_PATCH_KO.md의 12개 문안과 CLAIM_STATUS_AND_GAPS_KO.md를 읽는다. 상세 절차·수치·재현 명령은 REPRODUCTION_SUPPLEMENT_KO.md, 집계표 의미는 DATA_DICTIONARY_KO.md에 있다.

이번 묶음은 원래 PDF를 보존한 제출용 보강안이다. 기존 PDF와 이전72파일 심사 ZIP을 다시 묶지 않았다. 실제 집계표·소스 발췌·분석 코드를 포함하지만 대량 원시 출력/데이터셋은 제외했으므로 암호화 실험 전체를 ZIP 하나로 재실행할 수 있다는 주장은 하지 않는다. 원래 파일을 사용할 집계 재현 경로와 SHA는 provenance에 있다.

MANIFEST.json은 포함 파일마다 바이트 크기·SHA-256·복사/발췌/생성 방식과 출처를 기록한다. SHA256SUMS는 MANIFEST까지 포함하고 자기 자신은 제외한다. ZIP은 이 새 폴더의 작은 묶음만 담으며 ZIP 옆 ZIP_VALIDATION.json이 재개봉 CRC·파일별 해시 검증을 기록한다. 원격 전송은 하지 않았다.
''')

# Package allowlist: generated documents/tables, public source excerpts, and
# provenance. No archive, virtual environments, raw datasets or reserved data.
payload=sorted(p for p in DOC.rglob('*') if p.is_file());allowed_ext={'.md','.json','.csv','.txt','.go','.py'}
check('package_extensions',all(p.suffix in allowed_ext for p in payload))
check('package_no_symlinks',all(not p.is_symlink() and p.resolve()==p for p in payload))
for p in payload:
    b=p.read_bytes();check('no_private_key_pem_'+str(p.relative_to(DOC)),b'-----BEGIN PRIVATE KEY-----' not in b and b'-----BEGIN RSA PRIVATE KEY-----' not in b)
source_copies={r['file']:r for r in js(T/'SOURCE_COPY_MANIFEST.json')};source_copies.update({r['file']:r for r in copied})
entries=[]
for p in payload:
    rel=str(p.relative_to(DOC));original=source_copies.get(rel)
    if original:
        kind=original['kind'];sources=[{'path':original['source'],'sha256':original['source_sha256'],'line_ranges':original.get('line_ranges')}]
    else:
        kind='generated report, reaggregation, or metadata';sources=[{'path':'provenance/'+n,'relationship':'bounded source bindings; row source fields and DATA_DICTIONARY specify derivation'} for n in binding_names]
    entries.append({'file':rel,'bytes':p.stat().st_size,'sha256':sha(p),'kind':kind,'sources':sources,'derivation':'DATA_DICTIONARY_KO.md and reproduction_scripts; original path/field references retained'})
manifest={'task_id':start['task_id'],'head':head,'source_pdf_sha256':'0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85','created_utc':datetime.now(timezone.utc).isoformat(),'payload_file_count':len(entries),'files':entries,'manifest_self_hash':'excluded from its own entries; included in SHA256SUMS','exclusions':['previous review ZIP/PDF copies','archive','raw datasets and large encrypted results','reserved Bank684 rows or outputs','secret keys/tokens','virtual environments/cache/fonts'],'upload_status':'local only'}
dump(DOC/'MANIFEST.json',manifest);payload.append(DOC/'MANIFEST.json')
with (DOC/'SHA256SUMS').open('x') as f:
    for p in sorted(payload):f.write(sha(p)+'  '+str(p.relative_to(DOC))+'\n')
payload.append(DOC/'SHA256SUMS')
zip_path=DOC/'CKKS_JOURNAL_EVIDENCE_20260906_v1.zip'
with zipfile.ZipFile(zip_path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(payload):z.write(p,'CKKS_JOURNAL_EVIDENCE_V1/'+str(p.relative_to(DOC)))
with zipfile.ZipFile(zip_path) as z:
    assert z.testzip() is None
    expected={'CKKS_JOURNAL_EVIDENCE_V1/'+str(p.relative_to(DOC)):sha(p) for p in payload}
    assert len(z.namelist())==len(expected) and set(z.namelist())==set(expected)
    for n,h in expected.items():assert hashlib.sha256(z.read(n)).hexdigest()==h
    assert json.loads(z.read('CKKS_JOURNAL_EVIDENCE_V1/MANIFEST.json'))==manifest
zip_result={'status':'PASS','zip':str(zip_path),'bytes':zip_path.stat().st_size,'files':len(payload),'sha256':sha(zip_path),'crc_reopen':'PASS','every_entry_sha256':'PASS','manifest_payload_hashes':'PASS','PDF_not_repacked':True,'local_transfer_status':'created locally; no upload','new_experiments':0,'generated_utc':datetime.now(timezone.utc).isoformat()}
dump(DOC/'ZIP_VALIDATION.json',zip_result)
write(DOC/(zip_path.name+'.sha256'),zip_result['sha256']+'  '+zip_path.name)
dump(RUN/'PACKAGE_VALIDATION.json',zip_result)
print(json.dumps(zip_result,ensure_ascii=False),flush=True)
