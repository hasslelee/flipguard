"""Generate final documents from completed tables and explicitly reviewed conclusions."""
import csv,json,collections,statistics
from pathlib import Path
import run as r
RUN=r.RUN;DOC=r.ROOT/'docs/research/fg_thesis_v1_20260908'
def rows(name):return list(csv.DictReader(open(DOC/name)))
def num(x,digits=3):
    if x in [None,'']:return '미측정/해당 없음'
    try:return f'{float(x):.{digits}f}'
    except (ValueError,TypeError):return str(x)
def table(headers,data):return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(label(x).replace('|','/').replace('\n',' ') for x in row)+' |' for row in data)+'\n'
def put(name,text):
    with (DOC/name).open('x') as f:f.write(text.strip()+'\n')
def short(c):
    return {'spambase__linear_poly3__split0_seed0':'Spambase 선형','spambase__mlp_square_linear_score__split0_seed0':'Spambase MLP','htru2__mlp_square_linear_score__split0_seed0':'HTRU2 MLP','hediff_bank':'Bank','fashion_seed0':'Fashion seed0'}.get(c,c)
def label(x):
    return str(x).replace('Cprime','C′').replace('B30slack','B30+slack').replace('existing_audit','기존 별도').replace('reserved684','예약684').replace('exposed_synthetic','노출 합성16').replace('one-input call','1입력 호출').replace('fixed20-input batch','20입력 배치').replace('NO_APPLICABLE_SELECTION_DOMAIN','적용 입력 없음').replace('EXECUTION_FAILURE','실행 실패').replace('NO_SELECTION','상한 내 미선택').replace('SELECTED','선택')
def main():
    assert (RUN/'MATERIAL_SIZE_COMPLETED.json').exists() and (RUN/'TIMING_VERIFIED.json').exists()
    conclusions=r.read(RUN/'REVIEWED_CONCLUSIONS.json');s=rows('SELECTION_METRICS.csv');a=rows('AUDIT_METRICS.csv');t=rows('TIMING_SUMMARY.csv');ar=rows('TIMING_ARMS.csv')
    fr=r.read(RUN/'FROZEN_SELECTIONS.json')['records'];new=r.read(RUN/'NEW_METRICS_VERIFIED.json');binding=r.read(RUN/'provenance/SUBMISSION_PDF_BINDING.json')
    fail=rows('FAILURES.csv');proc=rows('PROCESS_COSTS.csv');hours=sum(float(x['wall_seconds']) for x in proc)/3600;maxrss=max(int(x['peak_rss_kib']) for x in proc if x['peak_rss_kib'])/1024
    a2=table(['사례','설정 ρ/δ','선택 S/log₂N','후보 평가','선택 프로세스 초','결과'],[[short(x['case']),f"{x['rho']}/{x['delta']}",(f"{x.get('scale_bits','')}/{x.get('log_n','')}" if x['outcome']=='SELECTED' else '미선택'),x['encrypted_candidates'],num(float(x['selection_wall_ms'])/1000),x['outcome']] for x in s if x['phase']=='A2'])
    a3_identity={(x['case'],str(x['order']),str(x['selection_source_rows'])):x for x in r.read(RUN/'A3_INPUT_SEPARATION_CHECK.json')['subset_checks']}
    a3=table(['사례','해시 순서/행 수','고유 모델 입력 벡터','감사와 공유 벡터','선택 S/log₂N','후보 평가','선택 프로세스 초'],[[short(x['case']),f"{x['input_order_seed']}/{x['selection_inputs']}",a3_identity[(x['case'],x['input_order_seed'],x['selection_inputs'])]['distinct_selection_vectors'],a3_identity[(x['case'],x['input_order_seed'],x['selection_inputs'])]['shared_vectors_with_old_audit'],f"{x.get('scale_bits','')}/{x.get('log_n','')}",x['encrypted_candidates'],num(float(x['selection_wall_ms'])/1000)] for x in s if x['phase']=='A3'])
    b=table(['사례','방법/키 블록','선택 S/log₂N/Q/P개수','후보 평가','선택 프로세스 초','분석 ms'],[[short(x['case']),f"{x['role']}/{x['block']}",f"{x.get('scale_bits','')}/{x.get('log_n','')}/{x.get('Q_count','')}/{x.get('P_count','')}",x['encrypted_candidates'],num(float(x['selection_wall_ms'])/1000),num(x['analysis_ms'])] for x in s if x['phase']=='B'])
    def aliases(x):return ','.join(sorted({z['role'] for z in fr if z['phase']=='B' and z['case']==x['case'] and z['literal_id']==x['literal_id']})) or 'A2/A3 C'
    aud=table(['사례·자료','방법/별칭','S/log₂N','전체/적용/경계 입력','키 문맥/입력–키','적용 판정 불일치/조건 위반','경계 판정 불일치','최대 예산 사용률'],[[short(x['case'])+' '+x['stage'],aliases(x),f"{x['scale_bits']}/{x['log_n']}",f"{x['unique_inputs']}/{x['applicable_inputs']}/{x['boundary_inputs']}",f"{x['key_contexts']}/{x['input_key_observations']}",f"{x['applicable_flip_events']}/{x['applicable_error_events']}",x['boundary_flip_events'],num(x['max_budget_usage'],6)] for x in a if x['setting']=='base'])
    main_b_audits=[x for x in a if x['setting']=='base' and ((x['case']=='hediff_bank' and x['stage']=='reserved684') or (x['case']!='hediff_bank' and x['stage']=='existing_audit')) and any(z['phase']=='B' and z['case']==x['case'] and z['literal_id']==x['literal_id'] for z in fr)]
    numerical=table(['사례','방법','최대 절대오차','RMSE','기존 최대오차 허용값','해당 수치 기준 통과','평문 정답률'],[[short(x['case']),aliases(x),format(float(x['max_abs']),'.6g'),format(float(x['rmse']),'.6g'),format(float(x['A_development_maxabs_threshold']),'.6g'),('통과' if x['passes_A_maxabs_each_key']=='True' else '불통과'),num(100*float(x['plaintext_accuracy']),2)+'%'] for x in main_b_audits])
    sensitivity=table(['사례·설정','S/log₂N','전체/적용','전체 판정 불일치','적용 판정 불일치/조건 위반','공통 영역 입력/판정 불일치'],[[short(x['case'])+' '+x['setting'],f"{x['scale_bits']}/{x['log_n']}",f"{x['unique_inputs']}/{x['applicable_inputs']}",x['all_flip_events'],f"{x['applicable_flip_events']}/{x['applicable_error_events']}",f"{x['common_inputs']}/{x['common_flip_events']}"] for x in a if x['stage']=='existing_audit' and any(z['phase']=='A2' and z['case']==x['case'] and z['literal_id']==x['literal_id'] and z['setting']==x['setting'] for z in fr)])
    timing=table(['사례','비교군','비교군/C 기하평균','키 블록 범위','C/비교군 중앙값 ms','평균 대응 차이 ms','단위'],[[short(x['case']),x['comparator_roles'],num(x['equal_key_geomean_ratio'],5),f"{num(x['key_ratio_min'],5)}–{num(x['key_ratio_max'],5)}",f"{num(x['C_key_median_ms'])}/{num(x['comparator_key_median_ms'])}",num(x['mean_paired_absolute_difference_ms']),x['unit']] for x in t])
    costrows=[]
    group=collections.defaultdict(list)
    for x in ar:group[(x['case'],x['roles'])].append(x)
    for (cid,role),zs in sorted(group.items()):
        costrows.append([short(cid),role,len(zs),*[num(statistics.median(float(z[k]) for z in zs)) for k in ['setup_ms','encode_encrypt_mean_ms','he_mean_ms','decrypt_decode_mean_ms','pdf_median_ms','harness_wall_minus_pdf_mean_ms','harness_wall_median_ms']]])
    timed_outcomes=table(['사례','방법','arm–키 문맥','반복 적용 판정 불일치','반복 적용 오차 위반'],[[short(cid),role,len(zs),sum(int(z['timed_applicable_flip_events']) for z in zs),sum(int(z['timed_applicable_error_events']) for z in zs)] for (cid,role),zs in sorted(group.items())])
    decomposition=table(['사례','방법','arm–키 블록','준비 ms','인코딩·암호화 ms','HE ms','복호화·디코딩 ms','PDF 시간 중앙값 ms','wall 잔차 ms','harness wall 중앙값 ms'],costrows)
    sizes=rows('MATERIAL_SIZES.csv')
    sz=[]
    for x in sizes:
        if x['stage'] not in ['existing_audit','reserved684']:continue
        if x['case']=='hediff_bank' and x['stage']!='reserved684':continue
        matching=[z for z in fr if z['phase']=='B' and z['case']==x['case'] and z['literal_id']==x['literal_id']]
        if not matching:continue
        sz.append([short(x['case']),','.join(sorted({z['role'] for z in matching})),x['valid_inputs_per_batch'],f"{x['input_ciphertexts_per_batch']}/{x['output_ciphertexts_per_batch']}",num(int(x['derived_input_ciphertexts_bytes'])/1048576,3),num(int(x['derived_output_ciphertexts_bytes'])/1048576,3),num(int(x['measured_public_key_bytes'])/1048576,3),num(int(x['measured_relinearization_key_bytes'])/1048576,3)])
    size_table=table(['사례','방법','배치 유효 입력','입력/출력 암호문 수','입력 산출 MiB','출력 산출 MiB','공개키 MiB','재선형화키 MiB'],sz)
    trial=rows('TRIAL_METRICS.csv');states=collections.Counter(x['status'] for x in trial)
    count_text=f"선택 시도 {len(s)}건 중 선택 {sum(x['outcome']=='SELECTED' for x in s)}건, 적용 입력 없음 {sum(x['outcome']=='NO_APPLICABLE_SELECTION_DOMAIN' for x in s)}건이다. 실제 암호화 후보 평가는 {len(trial)}회이며 원시 후보 상태는 {dict(states)}다. 이 후보 상태를 입력 사건 수나 실행 프로세스 실패 수로 합치지 않는다."
    # The arm rows include repeated C references for different paired comparisons; not independent models.
    experiments=f'''# 설정 민감도와 정밀도 여유 옵션의 제한된 실제 검증

{conclusions['research_findings']}

## 1. 범위와 실행 단위

표에서 S는 기본 스케일의 log₂ 값이며 log₂N은 환 차수의 지수다. Q/P 개수와 비트 합은 다른 값이다.

새 protocol은 `FG_THESIS_V1_20260908`, run은 `results/fg_thesis_v1_20260908_run01`이다. A2 18, A3 18, B 24개의 고정 선택 작업을 모두 시도했다. B는 세 모델×네 방법×두 선택 키 블록이며 네 번째 방법은 독립 B30+slack 보조군이다. 정적 C/C′ 비교는 기존7모델과 Bank에서 수행했다. 새 학습 모델은0개다. 실제 새 선택·감사는 기존5모델을 재사용한다. 원래 일곱 모델 전체의 A/B/C 비교를 반복한 것이 아니다.

기록된 실험 native 호출의 누적 경과시간은 {hours:.3f}시간으로 사전 상한24시간 이내다. 이는 CPU 시간 합이나 서비스 시간 아닌 외부 프로세스의 경과시간 합이다. 연결 검사와 자료 크기 probe, 정적 계획·자료 준비의 native 호출도 포함한다. 실행기의 charged_native 소계가 제외했던 정적34호출의2.786초도 최종 합계와 상한 대조에 더했다. 원래 실행 기록은 고치지 않았다. peak RSS의 관측 최대는 {maxrss:.1f}MiB였다. 한 번에 암호화 실험 프로세스 하나를 실행했고, 주소 공간8GiB·Go메모리 목표6GiB·여유 메모리2GiB·여유 디스크8GiB·새 자료8GiB 한도를 사용했다. `PROCESS_COSTS.csv`에는 종료코드, 실행 순서, 환경 부하와 불리한 측정도 남겼다. 문서·집계 작업과 한 차례 자료 크기 probe 빌드를 선택 실행과 병행한 이력은 `CONCURRENT_WORK_NOTE.json`에 있다. 다른 응용도 실행 중인 단일 VM이므로 독점 환경의 벤치마크라고 표현하지 않는다.

{count_text}

감사 자체는99개 새 키 문맥과29,196 구성–입력–키 관측이다. 방법·구성·키를 합친 일반 감사의 고유 사례–입력은2,484개, 원본 고유 입력은2,228개다. 여기서 고유 입력은 원본 행 ID 단위이며 수치적으로 서로 다른 특징 벡터 수를 뜻하지 않는다. 노출 합성16개는 이 분모에서 분리했다. 선택 후보의222키 기록과 감사99키 기록은 총321개 원시 파일로 연결되며 독립 모집단 표본321개를 뜻하지 않는다. 연결 smoke 검사의2입력·3키·6관측은 `CONNECTION_CHECK_INDEX.json`으로 분리했다.

## 2. 실제 구현과 보존

공통 후보 생성·수용·조정·보안 코드는 기존 복사본과 일치한다(`CORE_RULE_EQUIVALENCE.json`). 변경은 격리한 모듈의 명령 연결과 `thesis_variant.go`에 한정한다. C′는 기존 비활성 정밀도 여유 함수를 첫 암호화 평가 전에 호출한다. 기존 정책의 scale 비트 상한50을 유지하며 같은 N 안의 모든 가능한 파라미터에 대한 최적성을 주장하지 않는다. C 경로는 기본 정책을 사용하며 상한4·세 키·첫 수용 종료·실패 후 조정을 유지했다. C′는 비교 구조 검증을 위해 기본 합성을 한 번 추가로 호출하며 이 정적 비용도 C′의 실제 선택 시간에 들어 있다. 기존 함수의 비활성화 이유는 미기록 상태다.

B30+slack은 독립 facts만 전달받는 별도 보조 규칙이다. C의 WorkloadContract나 마진 예산을 생성기에 전달하지 않는다. 기존 B30의 출발30/+4 순서는 유지하며 각 후보에서 같은 N/Q/P개수/경로/요구레벨 안에서 scale을1씩 증가시키는 정적 보조 검토를 한다. C 전용 함수와 동일한 구현이라고 부르지 않는다. 동일 literal은 감사 별칭으로 합쳤다.

`METHOD_SOURCE_MAP.csv`가 실제 함수·행·소스 해시를 연결한다. 새 후보의 실제 Q/P 소수와 분포·보안 수용은 `SECURITY_PARAMETERS.csv`와 각 `concrete_*.json`에 있다. 예를 들어 Bank C′의 선언 QP 합은210비트이지만 실제 소수 곱의 올림 log₂ 값은211비트로, 기존214비트 한도와 별도로 대조했다. static 후보 카운터, 생성 호출, 실제 암호화 후보 평가, 키 문맥과 입력–키 관측을 구별했다. 기존 정적 카운터만으로 모든 내부 시도 총수를 안다고 주장하지 않는다. `INITIAL_ANALYSIS.csv`에 오차 예산·민감도·초기 비트·백엔드 상승·여유 비트와 카운터의 범위를 기록했다.

실제 인코딩·암호화·동형연산·복호화를 실행했으나 클라이언트와 서버 역할은 같은 프로세스가 수행한 로컬 벤치마크다. 분리된 네트워크 배포나 운영 중 평문 oracle gate의 구현을 주장하지 않는다.

새 투고본은 `{binding['source']}`이며 SHA-256은 `{binding['sha256']}`이다. 실제12쪽 PDF의 방법·범위를 읽고5쪽을 렌더링하여 선택 상한, 수용과 조정 설명을 확인했다. 역사적 실행 기준0905 PDF와 완료 원고·실험은 변경하지 않았다. 투고본을 새로 교정하지 않았다.

## 3. A1: 기존 고정 출력의 재분류

`A1_SENSITIVITY.csv`는77그룹×6설정, 기존573키 파일에서462행을 만들었다. 표형4·Fashion3·Bank의 선택/일반/스트레스 자료 중 기존 선택 A30/B30/C 구성을 포함한다. 새 CKKS·재선택은0회다. native TenSEAL Bank는 원래float32와 공통float64 참조를 별도로 둔36행으로 분리했다. 참조 계산 차이를 CKKS 오차와 합치지 않는다.

고정 출력의 전체 판정 변화 수와 마진>0.01 공통 영역의 판정 변화 수는 여섯 설정에서 변하지 않았다. 기존 Spambase 선형 C 감사는 기본 적용235/256에서0판정 변화였지만, δ=0에서는256/256에 기존 경계의3판정 변화와7오차 위반 사건이 포함됐다. δ=0.01이면 적용91/256으로 줄었다. Spambase MLP는 기본75/256에서 δ=0.01의2/256으로 줄었다. Fashion 세 모델의 δ=0.01 적용 수는9,984/9,985/9,985이며 출력은 그대로다. 이는 적용 범위 변화이지 오류를 고친 실행이 아니다. ρ 변화도 허용 여유의 분류만 바꾼다.

## 4. A2: 고정 여섯 설정에서 실제 C 재선택

선택 시간은 실제 CLI 호출 경계의 경과시간으로 분석·파라미터 준비·키 생성·후보 실행·수용·결과 기록을 포함한다. 호출 전 Python의 출처 해시 확인과 일정 관리, 전체 빌드/가상환경 준비는 이 열 밖에 있다. 내부 native·분석·gate 시간은 별도 CSV에 보존하므로 이를 운영 서비스 전체 비용과 동일시하지 않는다.

{a2}
{conclusions['A2_interpretation']}

공통 적용 영역은 같은 평문에서 마진>0.01로 정의하였다. 동일 literal의 감사는 공유했고 별칭 수를 독립 입력·키 수로 더하지 않았다. δ=0에서도 평문 동점은 경계다.

{sensitivity}

## 5. A3: 선택 입력 수와 상한 접두 분석

기존 개발 후보256개의 원본 행 ID를 원래 감사256개와 분리하고, 입력 ID에 대한 사전 SHA-256 정렬 세 가지에서 중첩16/64/256을 만들었다. 실패 입력 삽입, 사분위 추출, 작은 마진 우선 추출은 하지 않았다. 풀 자체는 이미 사용된 개발 자료이므로 새 미사용 모집단이 아니다. 사전 중복 검사는 원본 행 ID 수준에 머물렀다. 실행 후 모델 입력 공간을 확인하니 Spambase의 개발256행은240벡터, 감사256행은241벡터였으며10벡터가 공유되어 감사25행이 해당했다. HTRU2는 각256벡터이며 공유0이다. 따라서 Spambase A3를 완전히 미관측된 특징 벡터의 독립 검증으로 해석할 수 없다. 입력 수에 따른 선택·비용의 관측은 보존하지만 분리의 범위를 낮춰 기록한다. 발견 뒤 행을 삭제·교체하거나 재실행하지 않았다(`A3_INPUT_SEPARATION_CHECK.json`).

{a3}
{conclusions['A3_interpretation']}

상한1/2/4 결과는 실제 순차 선택 궤적의 접두 구간으로 재집계했다(`PREFIX_CAP.csv`). 별도의 상한별 실행이나4이후 외삽이 아니다. 입력 추출 순서와 키 블록은 다른 단위다.

## 6. B: C/C′/B30 및 독립 보조군

새 Bank 비교는 고정20→256→2 모델의 공통 Lattigo 어댑터에서 수행했다. 원래 활성화 t²+t를 이동된 제곱으로 계산하는 기존 어댑터와 가중치를 유지하며, 모든 비교군에 같은 공통 float64 참조를 적용했다. 실수 계산식의 동등성을 원래 float32 구현과의 비트 일치라고 표현하지 않는다. 이번 공식 TenSEAL 새 실행은0회이며, 과거 공식 절차의 결과는 기존 증거와 A1 재분석으로 구별한다.

{b}
{conclusions['B_selection_interpretation']}

### 구성 고정과 예약 개봉

`SOURCE_LOCK.json`과`EXECUTION_BINDING.json` 뒤에 모든 선택을 완료하고 `FROZEN_SELECTIONS.json`을 저장했다. 평가 코드·지표·실제 선택 구성·감사 배치·키·시간 규칙을 `AUDIT_PREOPEN_LOCK.json`으로 묶은 다음에만 `RESERVATION_OPEN_STARTED.json`을 남기고 예약 자료를 읽었다. 예약684개는 원래 고정 순서의3배치×228개이며 서로 다른 선택 literal마다 배치당 새 키3개다. 이 감사는 여러 방법의 동일 고정 비교 한 번이며 후속 튜닝에 사용하지 않았다.

예약 개봉 전 NumPy2.2.6의 `repr(numpy.float64)`가 Go에서 읽을 수 없는 `np.float64(...)` 문자열을 만드는 준비 코드 결함을 확인했다. 잠긴 원래 감사 실행 코드는 변경하지 않았다. `repr(float(v))`로 숫자를 직렬화하는 동일 준비 함수 사본을 별도 해시와 `RESERVATION_FORMAT_PREOPEN_AMENDMENT.json`으로 먼저 고정한 뒤 한 번 개봉했다. 행·정규화 값·모델·구성·조건·반복은 바꾸지 않았고 암호화 실패 뒤의 재시도도 아니다. 기존 감사 실행기는 교정 경로가 만든 해시 고정 READY 입력을 그대로 사용했다.

기존 관리 기록상 미점수화684개였지만 전체 시스템 접근을 증명하는 감사 로그는 없다. 전체 원자료의 complete-case·LabelEncoder·float32 minmax·NearMiss 이력을 유지했다. 기존176개 입력과 재구성 정규화가 비트 단위로 일치하는지 확인했고 NearMiss를 다시 실행하지 않았다. 따라서 누수 없는 새 고객 모집단이라는 주장은 하지 않는다. 원래 일반32와 노출 합성16을 따로 기록했다. 합성 정답은 주장하지 않는다. 예약684개와 기존 선택·개발·일반 감사176개의 원본 행 및 정규화20차원 벡터 중복은0이며 예약 내부 벡터도684종이었다. 이 사후 확인은 전체 학습 자료나 모든 과거 후보에 대한 비노출 증명이 아니다(`BANK_INPUT_IDENTITY_CHECK.json`).

{aud}
{conclusions['audit_interpretation']}

{numerical}

수치 기준 표는 과거 개발 자료에서 고정한 모델별 최대 절대오차 허용값을 같은 출력 단위에 적용한 사후 비교다. 이번 B/C/C′의 선택 조건을 수치 기준으로 바꾼 것이 아니다. Bank는 예약684개, 나머지는 지정한 기존 감사 전체를 쓴다. 모든 실행 키에서 수치 기준을 통과했는지와 판정 조건을 통과했는지를 분리했다. 조건 통과가 두 방법의 실제 오차 크기까지 같다는 뜻은 아니다.

오차 충분조건의 재집계와 SAFE 상태를 대조했고, 조건이 성립한 상태에서 판정이 뒤집힌 관측은 없었다. 이는 미래 입력의 위험 보장이 아니다. 실패한 프로세스와 부분 키 파일이 있으면 `FAILURES.csv`와 원시 인덱스에 보존한다.

## 7. 비용과 자료 크기

대응 시간은 동일20입력에서 예열1회 뒤6회, 세 새 키 블록으로 측정하였다. 표형은 입력별 호출이고 Fashion/Bank는20입력 배치다. 방법별 키는 파라미터에 맞게 따로 만들며 같은 arm의 반복에서 재사용한다. 추론 호출 순서를 교대하고 모든 측정을 보존했다. 준비는 기존 harness의 arm 등록 순서(C→비교군)로 수행하며 준비 순서까지 균형화했다고 주장하지 않는다. 준비 구간은 파라미터·키·실행 객체 생성으로, 일부 모델/CSV 로딩과 프로세스 관리 비용은 밖에 있다. 이를 포함한 프로세스 경과시간은 별도 실행 기록에 남겼다. 키 블록 안에서 대응 비율의 기하평균을 구하고, 세 블록을 같은 비중으로 합쳤다. 입력이나 슬롯을 독립 통계 표본으로 세지 않았다. 직접 대응쌍은 각 비교군–C이며 C′–B30을 별도의 직접 대응쌍으로 측정하지 않았다. 두 군의 상대적 효율은 각각의 C 대비 대응값과 절대 시간에서 제한적으로 해석하며, 두 비율의 몫을 새로운 독립 대응 실험으로 부르지 않는다.

{timing}
{decomposition}

사전 protocol의 주 지표인 PDF 시간은 기록된 인코딩·암호화+HE+복호화·디코딩의 합이다. 원시 `total_ms`는 바깥쪽 경과시간이며 다중 클래스 경로에서는 평문 참조 계산·기록 구성·명시적 GC 등이 더 포함된다. 처음 집계 코드가 두 값의 일치를 가정하여 중단됐으나 실제 호출 경계를 확인하고 주 지표를 사전 정의대로 계산했다. 원시 시간·실패 로그는 보존했으며 새 측정은 하지 않았다(`TIMING_FORMULA_CORRECTION.json`). 기록 wall과 주 지표의 양의 차이를 별도 잔차로 남겼다. 잔차 내부 원인별 시간은 각각 측정하지 않았으므로 gate나 네트워크 시간으로 단정하지 않는다. 앞선 진행 안내의 비율은 wall 미리보기였으며 최종 표의 주 비율은 사전 정의의 성분 합이다.

위 분해표는 각 arm–키 블록 평균의 중앙값이며 각 열의 중앙값 합이 PDF 시간 중앙값과 정확히 같을 필요는 없다. C 참조는 비교 쌍마다 다시 측정되므로 반복 C행 수를 새 모델 수로 세지 않는다. `TIMING_KEY_BLOCKS.csv`·`TIMING_ARMS.csv`·`TIMING_RAW.csv`가 절대값·범위·준비 비용과 대응 기록을 보존한다. 키 준비를 한 군에서만 빼지 않았다. 새 원시 harness의 과거 V17/Bank_B3 문자열은 상속된 서식이며 현재 선택 방법은 새 schedule/alias가 기준이다.

{conclusions['cost_interpretation']}

{timed_outcomes}

이 표는 시간 측정 중 같은 arm–키에서6회 반복한 사건이다. 주 감사의 고유 입력·새 키 분모에 더하지 않는다. 표형은 기록된 스칼라 출력에서 재계산했으며, 다중 클래스는 시간 harness가 저장한 적용 영역의 판정·오차 조건 집계값이다. 경계 입력이 있는 경우 그 판정 사건이 기록되지 않은 값을0으로 채우지 않는다. 시간 파일에 클래스별 출력이 없어 그 부분을 입력별로 독립 재구성했다고 하지 않는다.

![비용과 오차 여유](CPRIME_COST_AND_SLACK.png)

그림의 가로축은 C 대비 대응 추론 시간 비율이고, 세로축은 기본 적용 영역(ρ=0.5, δ=0.001)에서의 최대 오차 예산 사용률이다. 패널의 수는 적용/전체 입력 수다. 가로선은 세 키 블록 비율의 관측 범위로 신뢰구간이 아니다. C의 가로축1은 정규화 기준이며 시간 변동이0이라는 뜻이 아니다. 동일 literal의 방법은 하나의 점으로 표시했다.

`MATERIAL_SIZES.csv`는 새 공개키·재선형화키와 degree1 암호문을 실제 생성·직렬화하여 얻은 크기다. 비밀키는 직렬화하거나 저장하지 않았다. 입력값0인 별도 자료 크기 probe로 레벨별 한 암호문 크기를 측정하고 실제 추론의 암호문 수·초기/최종 레벨로 합계 크기를 산출했다. 출력 암호문의 scale 등 메타데이터까지 probe와 비트 단위로 같은지 확인한 값은 아니며, 실제 추론 암호문 전체를 직렬화·전송한 측정과 구별한다. 이번 대표 모델은 회전키0개이며 기존 회전 경로 전체의 크기 결과가 아니다. 측정하지 않은 네트워크와 큐 대기는0이 아닌 미측정이다. 추론 중 adapter I/O의 기록상0은 네트워크0을 뜻하지 않는다.

{size_table}

크기 표는 감사의 실제 배치 크기를 표시하며, 앞의 시간 비교는20입력 기준이다. 크기 probe의 단일 관측을 크기 변동의 통계 검증으로 표현하지 않는다.

## 8. 응용과 환경의 미실시 범위

공식 UNSW 자료 설명과 공유 링크를 확인했으나 특징 CSV를 확보하지 못했다. 익명 공유 페이지는 파일 목록 없는 응용 화면이었고 공식 API는403 accessDenied였다. 지시문5절에 따라 IDS 부분을 보류했다. 새 IDS 학습·암호화 실험은각0이며 Kaggle 대체본, PCAP 처리나 추가 데이터셋을 사용하지 않았다. 실행 가능한 A/B 작업은 계속했다. 별도 물리 장비는 제공되지 않아 독립 환경 검증도 미실시다. 같은 VM의 반복을 별도 장비 검증으로 부르지 않는다. `DEFERRED_EXECUTION_BUNDLE.json`에 한정된 다음 실행 규격과 필요한 연결을 남겼으며 자동 실행하지 않는다. 회전 경로의 기존 모델·선택250·감사250 사본은 원본을 실행하지 않고 관리 해시와 일치하는217,863바이트만 준비했다. 기존 표형·Fashion 의존성은 이미 protocol과 소스 잠금에 연결된다. 회전 경로가 요구하는 MNIST 원자료와 추출 manifest, 새 장비·명령 연결은 아직 검증되지 않았으므로 이 준비 자료를 자족적인 실행 환경이나 독립 장비 재현 완료라고 부르지 않는다(`INDEPENDENT_DEVICE_PREPARATION.json`).

## 9. 검증과 종료

{conclusions['completion_interpretation']}

단위·엄격한 부등호·동점 경계·모든 경쟁 클래스·별칭·실행 실패를 점검했다. 완료 후 읽기 전용 재검증 명령은 `/home/ckks2/deciprotect`에서 `PYTHONDONTWRITEBYTECODE=1 python3 results/fg_thesis_v1_20260908_run01/scripts/verify_final.py --check-only`이다. 원시 키 파일321개와 대응 시간 파일24개의 해시도 재대조하며 새 암호화 실행이나 결과 덮어쓰기를 하지 않는다. 코드 테스트 통과는 성능 개선이나 위험 보장이 아니다. `NEW_METRICS_VERIFIED.json`, `TIMING_VERIFIED.json`, `FINAL_VERIFICATION.json`과 ZIP manifest가 검증 근거다. 사용자 변경을 reset하지 않았고 원격 push·업로드·archive 전송·전수 재해시를 하지 않았다.
'''
    put('THESIS_EXPERIMENTS_KO.md',experiments)
    put('CPRIME_DECISION_KO.md',f'''# C′ 채택 판단

**판정: {conclusions['adoption_label']}**

{conclusions['adoption_reason']}

## 유지한 절차와 바뀐 부분

C의 고정 모델·마진 조건·보안 기준·첫 수용·상한4·세 키·실패 조정은 유지했다. 바뀐 것은 기존 비활성 정밀도 여유 옵션을 첫 암호화 평가 전에 별도 경로로 연결한 점이다. 같은 N/Q/P개수/실행 경로/요구 레벨과 동일 contract의 packing·회전 요구를 확인했다. C′는 큰 N을 줄이지 않는다. 기존 C의 코드나 완료 결과를 소급 수정하지 않았다.

## 대조군과 비교한 추가 가치

{conclusions['incremental_value']}

{timing}

{conclusions['adoption_limits']}

## 채택하지 않을 조건과 이번 종료

사전에 정한 분류대로 실행 오류 때문에 비교가 성립하지 않은 부분은 판단 불가다. 구조 변경·새 위반·큰 비용 증가·실질적 이득 부재는 보편적 채택의 근거가 될 수 없다. 수치 여유만 증가한 결과는 판정 오류 감소로 부르지 않는다. 관측 후 임의의 비용 무손해 허용률을 만들지 않았다. 이미 성공한 B보다 추가 가치가 약한 경우도 그대로 남긴다.

{conclusions['stop_statement']}

원시 근거는 `AUDIT_METRICS.csv`, `INITIAL_ANALYSIS.csv`, `SELECTION_METRICS.csv`, `TIMING_SUMMARY.csv`, `MATERIAL_SIZES.csv`와 실제 raw index에 연결된다.
''')
    status=f'''# 연구 상태와 학위 집필 범위

{conclusions['research_findings']}

**C′: {conclusions['adoption_label']}**. {conclusions['completion_interpretation']}

| 구분 | 실제 수행과 종료 상태 |
|---|---|
| 학회 원고 | 사용자가 지정한0908 투고본을 내용 기준으로 확인. 기존 PDF·v1/v2 원고 보존, 재교정 없음 |
| 기존 A/B/C·원인 분석 | 완료 상태 유지. 기존 판정 개선 미관측·Bank 실패·혼합 비용 보존 |
| A1 | 기존573키 파일/77그룹×6설정과 별도 native Bank 재분석 완료. 새 선택이 아님 |
| A2 | 고정18선택 작업 모두 시도. 빈 적용 영역은 별도 미선택 사유 |
| A3 | 2모델×3순서×3크기의18선택 작업. Spambase는 행 ID 분리이나 특징 벡터 공유10종이 있어 완전한 입력 비노출 검증으로 해석 불가 |
| B | 3모델×4방법×2블록24선택 작업, literal 고정 후 감사·대응 시간 |
| Bank 예약 | 구성·지표·규칙을 먼저 고정한 뒤684개 한 번의 비교에 사용. 사용 완료 상태로 기록 |
| 새 IDS | 공식 특징 CSV 접근 차단으로 보류. 학습0·새 CKKS0, 타 자료 대체 없음 |
| 독립 물리 환경 | 장비 미제공으로 미실시. 실행 규격·필요 연결만 준비 |
| 산출물 | 실제 학위 MD/TXT 초안, 결과/채택 보고서, 표·원시 인덱스·코드 diff·검증·ZIP |

새 native 누적{hours:.3f}시간/상한24시간. 새 학습0. 이번 실제 CKKS는 기존5모델 재사용이며 정적 검토8모델, 기존 주요68·추가63·깊이5조건·확대4+3과 합쳐 새 모델 수를 부풀리지 않는다. 실행 상세와 보류 사유는 `THESIS_EXPERIMENTS_KO.md`에 있다.

{conclusions['stop_statement']}

학위 초안은 실제 배경·방법·기존 결과와 새 결과를 포함한다. 학교별 서식·지도교수 검토는 문서 마감 단계이며 새 실험 자동 착수 조건이 아니다. 강한 국제적 신규성이나 학위 심사 통과를 선언하지 않는다.
'''
    put('THESIS_STATUS_AND_SCOPE_KO.md',status)
    base=(DOC/'THESIS_BASE_TEXT_KO.md').read_text()
    # Replace source appendix position so new empirical sections precede references.
    maintext,refs=base.split('## 기존 근거의 출처',1)
    newsections=f'''### 5.6 설정과 선택 자료의 민감도

{conclusions['A2_interpretation']}

{a2}

기존 고정 출력 재분류에서 Spambase 선형의 적용 영역은 δ=0/0.001/0.01에서256/235/91개였다. δ=0으로 넓힌 영역에는 기존 경계의 판정 변화3회가 포함되었다. 출력의 변화와 평가 범위의 변화를 구분해야 한다.

{conclusions['A3_interpretation']}

{a3}

### 5.7 정밀도 여유 옵션의 제한된 비교

{conclusions['B_selection_interpretation']}

{aud}

{conclusions['audit_interpretation']}

예약684개는 구성·코드·지표·배치와 키 규칙을 고정한 뒤 처음 점수화한 것으로 기존 관리 기록에 연결된다. 그러나 전수 정규화와 NearMiss의 기존 이력이 있어 누수 없는 새 모집단의 검증이라고 표현하지 않는다. 이전 합성16개는 노출 회귀 점검이며 정답 미확정 상태를 유지한다.

### 5.8 실행 비용과 실제 평가 범위

{timing}

{conclusions['cost_interpretation']}

{numerical}

위 수치 기준은 기존 개발 자료의 모델별 허용값에 대한 사후 평가이며 새 선택 정책이 아니다.

모든 시간은 동일 입력을 사용하는 대응 비교이며 준비 비용은 따로 기록하였다. 세 키 블록의 비율 범위와 절대 차이를 제시했으며 위험 상한이나 시간 동등성의 증명으로 사용하지 않았다. 공개키·재선형화키는 실제로 생성·직렬화하여 크기를 측정하였다. 암호문 총량은 별도0입력 probe에서 측정한 레벨별 암호문 크기와 실제 추론의 암호문 개수로 산출한 값이며, 추론 중 암호문 전체를 직렬화·전송한 측정과 구별한다. 네트워크와 서비스 대기는 미측정이다. 빌드와 가상환경 준비의 전체 경과시간도 추론 비용에 포함하지 않았으며, 이를0으로 둔 서비스 전체 비용을 보고하지 않는다.

공식 침입 탐지 특징 CSV는 접근 권한 문제로 확보하지 못해 새 데이터 평가를 수행하지 않았다. 별도 물리 장비도 확보되지 않았다. 따라서 이번 후속 실험은 기존 모델과 단일 VM의 검증 범위를 넘지 않는다. 이 미실시 부분을 예상 성공으로 채우지 않는다.

## 제6장 논의와 결론

### 6.1 확인한 효과와 무차이의 의미

{conclusions['research_findings']}

판정 관련 조건을 내부 수용에 사용한 효과와 독립 수치 기준보다 추가 이점이 있다는 주장은 분리해야 한다. 학회 주요 실험은 같은 초기 합성에서 검사와 조정의 필요성을 보여준다. 반면 후속 A/B에서는 강한 수치 조건과 첫 후보 수용 아래 차이가 관측되지 않았다. 이는 무의미한 결과가 아니라 어떤 기준에서 판정 조건이 추가 선택력을 갖지 못하는지 보여 주는 근거다.

### 6.2 정밀도 여유의 채택 범위

{conclusions['adoption_reason']}

{conclusions['incremental_value']}

{conclusions['adoption_limits']}

### 6.3 보호 범위와 남는 한계

선택 입력의 작은 오차는 미래 입력의 오차 상계가 아니다. 적용 영역을 좁히면 성공률이 높아 보일 수 있으므로 전체·적용·경계 분모가 함께 필요하다. 작은 마진, 초기 오차 추정, 실제 N 경계, 키에 따른 오차 방향은 서로 다른 원인이다. 모든 문제를 하나의 스케일 조정으로 해결했다고 주장할 수 없다. 지원 그래프·packing·분포·단일 환경의 범위도 유지한다.

### 6.4 결론

{conclusions['completion_interpretation']}

본 연구는 판정 일관성을 고정 모델의 CKKS 구성 선택과 연결하고, 실제 선택과 별도 입력 관측으로 그 효과와 범위를 확인하였다. 이론적 입력별 충분조건과 유한한 검증 결과를 구분하면, 성공 사례뿐 아니라 무차이·경계·비용 손해도 구성 선택 연구의 결과로 설명할 수 있다. {conclusions['stop_statement']}

## 참고 근거와 재현 자료
{refs}

이번 실제 결과의 표·코드·명령·식별자는 별도 실험 보고서와 제출 묶음에 수록하였다. 본문은 관리용 해시 대신 연구 절차와 관측 단위를 중심으로 작성하였다.
'''
    abstract=f'''## 초록

CKKS를 이용한 암호화 추론에서는 작은 수치 오차도 임곗값이나 클래스 순서를 바꾸어 평문 모델과 다른 판정을 만들 수 있다. 본 연구는 고정 모델의 계산 그래프와 구성 선택용 입력에서 얻은 판정 마진을 이용해 초기 구성을 합성하고, 실제 암호화 실행의 판정 일치와 입력별 오차 조건으로 구성을 수용하는 오프라인 절차를 다룬다. 학회 주요68사례의 내부 검사·조정 효과와 이후 독립 수치 대조군에서의 무차이를 구별하고, 같은 판정 목적 아래 선택 비용과 추론 비용을 평가하였다.

이번 제한된 후속 검증에서는 기존5모델을 재사용하여 설정 민감도, 선택 입력 수, 정밀도 여유 옵션을 실제 실행하였다. Bank 예약684개 중 기본 적용 영역683개에서 입력당 세 키 반복을 합한 C의 판정 불일치8회(고유5입력)가 관측된 반면 C′와 B30은0회였다. 이는 C의 제한적 보강 근거이며 B30보다 추가 판정 이점이 있다는 결과는 아니다. 선택 설정을 바꾸어도 같은 구성이 나올 수 있었고, 적용 영역을 넓히면 기존 경계 실패가 포함되었다. {conclusions['adoption_label']}이라는 판단에 따라 옵션의 적용 범위를 정리하였다. 입력별 충분조건과 유한한 실행 관측을 구별하며, 모든 미래 입력·키에 대한 무조건 보장이나 전체 구성 공간의 최적성을 주장하지 않는다.

주요어: CKKS, 암호화 추론, 판정 일관성, 구성 선택, 판정 마진

'''
    maintext=maintext.replace('## 제1장 문제와 연구 목적',abstract+'## 제1장 문제와 연구 목적',1)
    draft=maintext+newsections
    put('THESIS_DRAFT_KO.md',draft);put('THESIS_DRAFT_KO.txt',draft)
    print('WROTE five final documents')

if __name__=='__main__':main()
