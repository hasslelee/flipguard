#!/usr/bin/env python3
"""Describe only completed observations; preserve missing work and role aliases."""
import collections, csv, datetime, json, math, re
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'docs/research/fg_expand_v2_20260905'
RUN=ROOT/'results/fg_expand_v2_20260905_run01'
NAMES={'initial':'초기','proposed':'제안','finite_fastest_acceptable':'유한 최속 수용','finite_fastest_executable':'유한 최속 실행','numeric_rmse':'수치 RMSE','numeric_max_abs':'수치 최대오차'}
COMPONENTS=['encode_encrypt_ms','evaluation_only_ms','decrypt_decode_ms','adapter_io_ms','total_ms']
def read(p):return json.loads(p.read_text())
def fmt(x,d=3):return '미측정' if x is None else f'{x:,.{d}f}'
def config(c):
    if not c:return '미선택'
    p=c['parameters'];return f"N=2^{p['log_n']}, Q{len(p['log_q'])}, P{len(p['log_p'])}, S{p['log_default_scale']}"
def csvout(path,rows):
    with path.open('x',newline='') as f:
        fields=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def textout(name,body):
    with (DOC/name).open('x') as f:f.write(body)
def input_type_table(summary):
    lines=['| seed·수치 기준 | 수치 조건 통과·판정 변화 | 그중 제안 보존 | 양쪽 판정 보존 | 제안 적용 판정 변화 | 제안 오차만 위반 | 제안 적용 밖 |', '|---|---:|---:|---:|---:|---:|---:|']
    columns=['numeric_batch_condition_pass_flip','numeric_batch_condition_pass_flip_proposed_preserved_all_keys','both_decisions_preserved_all_keys','proposed_applicable_decision_flip','proposed_error_violation_without_applicable_flip','proposed_outside_domain']
    for c in summary['cases']:
        for method in ['numeric_rmse','numeric_max_abs']:
            counts={t['type']:t['case_input_pairs'] for t in c['input_types'] if t['method']==method}
            lines.append(f"| {c['seed']}·{NAMES[method]} | "+' | '.join(f'{counts[k]:,}' for k in columns)+' |')
    return lines
def quality_note(summary):
    dev='/'.join(f"{100*c['development']['class_recall'][6]:.1f}" for c in summary['cases'])
    audit='/'.join(f"{100*c['audit'][c['roles']['proposed']['id']]['plaintext_class_recall'][6]:.1f}" for c in summary['cases'])
    return f'평문 모델의 class 6 재현율은 개발 {dev}%, test {audit}%다. 특히 seed 1·2의 약점은 개발 자료에서도 확인된다. 전체 정답률만으로 모든 클래스의 품질이 양호하다고 볼 수 없으며, CKKS 판정 일치는 이 분류 약점을 해결하지 않는다. 고정 모델의 계산 충실도 평가라는 범위를 유지하고 test 결과에 따른 재학습·seed 교체는 수행하지 않았다.'
def main():
    s=read(DOC/'summary.json');methods=list(csv.DictReader((DOC/'METHOD_CASE_RESULTS.csv').open()));costs=[];training=[]
    for case in s['cases']:
        seed=case['seed'];model=read(RUN/f'plaintext/seed_{seed}/model.json')
        history=[read(RUN/f'plaintext/seed_{seed}/epoch_{i:02d}.json') for i in range(1,9)]
        training.append(dict(seed=seed,training_seconds=model['training']['training_seconds'],first_loss=history[0]['epoch']['mean_training_loss'],last_loss=history[-1]['epoch']['mean_training_loss'],development_accuracy=case['development']['accuracy']))
        blocks=collections.defaultdict(list)
        for p in (RUN/f'cases/seed_{seed}/timing').glob('*/keyset_*/result.json'):
            b=read(p);blocks[b['arms'][1]['candidate_id']].append(b)
        for cid,bs in blocks.items():
            for arm in ['proposed','comparator']:
                records=[r for b in bs for r in b['records'] if r['arm_id']==arm];setup=[a['setup_keygen_ms'] for b in bs for a in b['arms'] if a['id']==arm]
                values={k:float(np.mean([r[k] for r in records])) for k in COMPONENTS}
                costs.append(dict(seed=seed,comparison_candidate_id=cid,arm=arm,keysets=len(bs),measurement_records=len(records),valid_inputs_per_batch=20,setup_keygen_mean_ms=float(np.mean(setup)),setup_keygen_sum_ms=sum(setup),harness_residual_mean_ms=values['total_ms']-sum(values[k] for k in COMPONENTS if k!='total_ms'),pdf_defined_inference_mean_ms=sum(values[k] for k in COMPONENTS[:3]),amortized_pdf_inference_ms_per_input=sum(values[k] for k in COMPONENTS[:3])/20,pdf_geometric_comparator_over_proposed=case['pdf_inference_ratios_comparator_over_proposed'][cid],amortized_total_ms_per_input=values['total_ms']/20,geometric_comparator_over_proposed=case['timing_ratios_comparator_over_proposed'][cid],measured_applicable_flip_events=sum(r['decision_flips'] for r in records),measured_error_events=sum(r['reserve_policy_violations'] for r in records),**values))
    csvout(DOC/'COST_BREAKDOWN.csv',costs);csvout(DOC/'TRAINING_SUMMARY.csv',training)
    commands=[read(p) for p in (RUN/'commands').glob('*.json')];native_seconds=sum(c['wall_seconds'] for c in commands)
    nonzero=[{'command':c['command'],'exit_code':c['exit_code'],'wall_seconds':c['wall_seconds']} for c in commands if c['exit_code']!=0]
    rss=[]
    for p in (RUN/'commands').glob('*.log'):
        m=re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)',p.read_text())
        if m:rss.append(int(m[1]))
    calendar_seconds=(datetime.datetime.fromisoformat(read(RUN/'MAIN_COMPLETED.json')['utc'])-datetime.datetime.fromisoformat(read(RUN/'MAIN_STARTED.json')['utc'])).total_seconds() if (RUN/'MAIN_COMPLETED.json').exists() else None
    accounting={'whole_main_calendar_elapsed_seconds':calendar_seconds,'data_download_and_csv_preparation_wall_seconds':None,'source_build_wall_seconds':None,'native_main_command_wall_seconds_all_attempts':native_seconds,'native_commands':len(commands),'nonzero_native_commands':nonzero,'max_native_peak_rss_kib':max(rss) if rss else None,'training':training,'network_seconds':None,'queue_wait_seconds':None,'one_time_setup_included_in_audit_total':True,'setup_excluded_from_paired_total_for_both_arms':True,'main_status':s['status']}
    with (DOC/'COST_ACCOUNTING.json').open('x') as f:json.dump(accounting,f,indent=2);f.write('\n')
    lines=['# 최종 논문 방법의 두 번째 확대 결과', '',f"상태: **{s['status']}**. 프로토콜 `FG_EXPAND_V2_MAIN_20260905`, 실행 `{RUN.name}`. 원본 FlipGuard, 최종 PDF, baseline/archive 및 완료된 첫 확대 결과는 보존했다. 이번 문서는 기존 오프라인 구성 선택 방법의 확대 검증이며 새 실행 중 유보·재계산 알고리즘을 제안하지 않는다.",'',
    '## 연구 질문에 대한 관측', '',
    '수치 정확성 조건과 입력별 판정·마진 오차 조건의 차이는 같은 후보 범위에서 비교했다. 초기 합성과 공통 후보 생성은 기존 마진 정보를 사용한다. 따라서 수치 대조군은 완전히 판정 정보를 쓰지 않는 선행 방법의 재현이 아니다. 개발 FP16 반올림에서 고정한 RMSE/최대오차 기준이며, 전체 유한 후보 평가 후 선택한 대표 조건 비교다.', '']
    lines+=['수용 조건 자체의 비교에는 같은 유한 집합과 같은 시간 argmin을 쓰는 유한 최속 수용 대 수치 최속을 사용한다. 최초 SAFE direct와 전체 유한 argmin의 차이는 탐색 규칙/예산 차이도 포함한다.', '', '| seed·수치 기준 | 평가 후보 | 양쪽 통과 | 수치만 통과 | 제안만 통과 | 양쪽 거절 |', '|---|---:|---:|---:|---:|---:|']
    for c in s['cases']:
        for a in c['acceptance_set_comparisons']:
            lines.append(f"| {c['seed']}·{a['numerical_criterion']} | {a['candidates']} | {a['both_pass']} | {a['numerical_only']} | {a['proposal_only']} | {a['both_fail']} |")
    same_sets=all(a['same_observed_acceptance_set'] for c in s['cases'] for a in c['acceptance_set_comparisons'])
    lines+=['',('이번 전체 유한 후보에서 두 수치 기준과 제안 기준의 통과 집합은 동일했다. 수용 조건 차이에 따른 후보 배제/추가 효과는 관측되지 않았다. direct와 유한 최속의 구성 차이가 있다면 이를 조건 차이의 효과로 귀속하지 않는다.' if same_sets else '수용 집합이 다른 사례의 후보 ID와 원래 수치/제안 조건 통과를 ACCEPTANCE_SET_COMPARISON.csv 및 FINITE_CANDIDATES.csv로 연결한다.'),'']
    for c in s['cases']:
        p=c['roles'].get('proposed');pid=p['id'] if p else None
        matches=[NAMES[n] for n in ['initial','finite_fastest_acceptable','finite_fastest_executable','numeric_rmse','numeric_max_abs'] if c['roles'].get(n) and c['roles'][n]['id']==pid]
        a=c['audit'].get(pid,{})
        lines.append(f"- seed {c['seed']}: 제안 {config(p)}, 실제 선택 {c['direct_trials']}후보. 같은 구성 역할: {', '.join(matches) or '없음'}. 제안 별도 완료 {a.get('inputs',0):,}/10,000, 적용 판정 변화 {a.get('applicable_flip_events','미평가')}회·오차 위반 {a.get('applicable_error_events','미평가')}회, 경계 변화 {a.get('boundary_flip_events','미평가')}회.")
    lines+=['','같은 구성을 선택한 경우 이번 후보 범위에서 수용 조건 차이에 따른 구성 개선은 관측되지 않은 것이다. 더 많은 시험 입력의 보존은 적용 범위를 보강하지만 그 자체로 수치 조건 대비 우월성을 입증하지 않는다. 구성 차이가 있더라도 독립 paired 측정으로 확인한 비용만 기술하며, 선택 때 관측한 최솟값을 성능 개선으로 쓰지 않는다.', '',
    '## 방법·입력·모델', '',
    '최종 PDF `baseline/journal_final_20260905.pdf`의 SHA-256은 `0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85`다. 실제 PDF의 다중 클래스 조건·선택·평가·외부 비교를 다시 확인했다. [함수별 대응과 사전 결정](RESEARCH_QUESTION_AND_METHOD_KO.md)에 호출 경로와 수정 범위를 정리했다.', '',
    'Fashion-MNIST 공식 train 60,000에서 학습 54,500·개발 5,000·선택 500을 분리하고 공식 test 10,000을 별도 평가로 고정했다. 원래 784→100→10 제곱 MLP와 학습 규칙을 유지했다. 새 데이터셋 1개, 새 구조 0개, 새 학습 모델 3개이며 같은 데이터·구조의 seed 0/1/2다. 선택은 500고유 입력·1,500사례–입력 쌍이다. 별도 계획은 10,000고유 입력·30,000사례–입력 쌍이며 방법 역할을 합쳐 분모를 부풀리지 않는다.', '',
    '모든 경쟁 클래스에 대한 오차합이 점수차의 0.5배보다 작고 판정도 같아야 수용한다. top-two gap≤0.001 및 동점은 적용 영역 밖이며 동점 판정은 가장 낮은 클래스 index다. 판정 변화와 보수적 오차 조건 위반은 별개의 사건이다. 공식 픽셀과 모든 CSV·역할·배치 소속도 독립적으로 재검증했다.', '',
    '| seed | 개발 정답률 | 첫→마지막 epoch 손실 | 학습 시간(초) |', '|---|---:|---:|---:|']
    for t in training:lines.append(f"| {t['seed']} | {t['development_accuracy']:.2%} | {t['first_loss']:.6f} → {t['last_loss']:.6f} | {t['training_seconds']:.3f} |")
    lines+=['','다운로드·CSV 생성·빌드의 전체 준비 wall time은 별도 타이머가 없어 미측정이다. 학습 시간은 model metadata에 기록된 원래 학습 함수 구간이며 전체 프로세스 자원 기록은 train_seed*.log에 있다. 손실은 학습 중 누적 값이고 개발 정답률은 별도 개발 자료다. 8epoch 완료를 수렴 보증으로 해석하지 않는다. 고정 test를 이용한 학습 중단·seed 교체·허용값 변경은 없다. 클래스별 recall·혼동행렬은 `summary.json`과 원시 개발 품질 파일에 있다. [학습 곡선](TRAINING_CURVES.pdf)은 모든 seed와 epoch를 포함한다.', '', quality_note(s), '',
    '## 선택과 별도 입력 결과', '',
    '`METHOD_CASE_RESULTS.csv`는 각 방법의 출처, 원래 조건과 통과 여부, 제안 조건 통과 여부, 후보 수, 전체/적용/경계 입력, 수치 오차, 모델 정답률, alias와 모델 SHA를 연결한다. `FINITE_CANDIDATES.csv`에는 거절·수치 통과 여부를 포함한 전체 후보가 있다. 아래 변화/위반은 각각 세 키 합산 사건 수이며 괄호 안은 적어도 한 키에서 발생한 고유 사례–입력 수다.', '',
    '| seed·방법 | 구성 | 평가 후보 수 | 별도 전체/적용/경계 | 적용 판정 변화(고유) | 적용 오차 위반(고유) | 경계 변화(고유) | 평문 정답률 |', '|---|---|---:|---|---:|---:|---:|---:|']
    for r in methods:
        if not r.get('candidate_id'):
            lines.append(f"| {r['seed']}·{NAMES[r['method']]} | 미선택 | — | 미평가 | — | — | — | — |");continue
        c={'parameters':json.loads(r['parameters'])};n=int(r['inputs'])
        if not n:
            lines.append(f"| {r['seed']}·{NAMES[r['method']]} | {config(c)} | {r['actual_candidates_evaluated']} | 미평가 | — | — | — | — |");continue
        lines.append(f"| {r['seed']}·{NAMES[r['method']]} | {config(c)} | {r['actual_candidates_evaluated']} | {n}/{r['applicable']}/{r['boundary']} | {r['applicable_flip_events']} ({r['applicable_flip_inputs']}) | {r['applicable_error_events']} ({r['applicable_error_inputs']}) | {r['boundary_flip_events']} ({r['boundary_flip_inputs']}) | {float(r['plaintext_accuracy']):.2%} |")
    lines+=['','같은 후보의 역할은 정확성 원시 결과를 공유한다. 이는 별개의 암호화 실행이나 추가 독립 표본이 아니다. 한 500입력 배치는 784입력 암호문·10출력 암호문이며 입력 하나가 slot 하나에 대응한다. 나머지 N/2−500은 padding이다. 후보·배치마다 새 키 3개로, 전체 완료한 후보 하나는 60키 문맥/30,000입력–키 관측을 가진다. 이를 3전역 키 또는 30,000독립 시험으로 표현하지 않는다.', '',
    f"모든 선택 역할에서 공통으로 평가를 완료한 사례–입력은 {s['common_evaluated_audit_case_inputs']:,}/30,000이다. 미완료 batch 및 timing block은 `summary.json`의 `missing_batches`와 `missing_timing_blocks`에 남긴다. 미평가 결과를 0회로 채우지 않는다.", '',
    '## 비용', '',
    f"본 실행의 native 명령 wall time 합은 {native_seconds:,.3f}초 ({native_seconds/3600:.3f}시간), 비정상 종료 명령은 {len(nonzero)}개다. 첫 중단 시도도 포함했다. 관측한 최대 native RSS는 {fmt((max(rss)/1024) if rss else None)}MiB다. 이는 프로세스 peak이며 전체 시스템 메모리 peak는 아니다. 환경과 명령 전후 상태는 `HOST_ENVIRONMENT.json`, `MAIN_STARTED.json`, `commands/*.json`에 있다.", '',
    '| seed | 계약·합성·유한 후보 생성 wall(초) | direct 완료 wall(초) | direct 모든 시도 wall(초) | 유한 전체 wall(초) |', '|---|---:|---:|---:|---:|']
    for c in s['cases']:
        t=c['selection_costs'];lines.append(f"| {c['seed']} | {fmt(t.get('plan_all_attempt_wall_seconds'))} | {fmt(t.get('direct_completed_wall_seconds'))} | {fmt(t.get('direct_all_attempt_wall_seconds'))} | {fmt(t.get('finite_all_attempt_wall_seconds'))} |")
    lines+=['','초기 구성은 합성 산출물을 그대로 사용하는 기준이다. 표의 초기 1후보는 사후 비교를 위해 실제 평가한 수이며, 초기 선택 자체에 암호화 수용 검사가 필수라는 뜻이 아니다. 유한 최속 수용·최속 실행·두 수치 기준은 동일한 유한 평가 자료를 공유하며 그 비용을 방법 수만큼 곱하지 않는다. 계약 준비 명령은 공통 합성과 유한 후보 생성을 함께 수행한다. direct와 유한 비교군 사이에서 그 비용을 이중 계산하지 않으며 순수 direct 합성만의 비용으로 단정하지 않는다. direct 선택 비용은 공통 준비+direct 후보 평가로 추적 가능하고, 유한 비교군은 공통 준비+전체 후보 평가의 추가 예산이 필요하다. 후보별 원시 native 비용도 남겼다.', '',
    'paired 비용은 기존 V17의 20입력 배치·예열 1회·측정 6회·키 블록 3개다. 아래 값은 완료된 측정 record의 산술평균(ms/배치), 비율은 키/반복에 동일 가중치를 둔 기하평균(대조/제안)이다. 같은 구성 대조도 새 키 arm으로 실제 재실행한다. 1보다 큰 비율은 이 유한 반복에서 제안 쪽이 짧았다는 뜻이며 모집단 성능 우월성 검정은 아니다.', '',
    '| seed·대조 구성·arm | 키 준비 | 인코딩·암호화 | 동형 계산 | 복호화·디코딩 | 잔여 | 원시 배치 총 | PDF 추론 합 | PDF 입력당 | 원시 비율 / PDF 비율 |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in costs:
        c=next(v for case in s['cases'] if case['seed']==r['seed'] for v in case['roles'].values() if v and v['id']==r['comparison_candidate_id'])
        lines.append(f"| {r['seed']}·{config(c)}·{r['arm']} | {fmt(r['setup_keygen_mean_ms'])} | {fmt(r['encode_encrypt_ms'])} | {fmt(r['evaluation_only_ms'])} | {fmt(r['decrypt_decode_ms'])} | {fmt(r['harness_residual_mean_ms'])} | {fmt(r['total_ms'])} | {fmt(r['pdf_defined_inference_mean_ms'])} | {fmt(r['amortized_pdf_inference_ms_per_input'])} | {r['geometric_comparator_over_proposed']:.6f} / {r['pdf_geometric_comparator_over_proposed']:.6f} |")
    lines+=['', f"완료된 paired 측정 arm-record {sum(r['measurement_records'] for r in costs)}개에서 적용 판정 변화는 {sum(r['measured_applicable_flip_events'] for r in costs)}회, 오차 위반은 {sum(r['measured_error_events'] for r in costs)}회였다. 이 시간 반복 관측은 별도 시험 입력/키 분모에 합산하지 않는다. 예열은 위 측정 record 집계에 포함하지 않는다."]
    for r in costs:
        if r['measured_applicable_flip_events'] or r['measured_error_events']:
            lines.append(f"- 시간 측정 위반 보존: seed {r['seed']}, {r['comparison_candidate_id']}, {r['arm']}: 변화 {r['measured_applicable_flip_events']}회/오차 {r['measured_error_events']}회. 해당 시간은 삭제하지 않으며 이 실행의 보존 성공이나 성능 향상을 주장하지 않는다.")
    lines+=['','`COST_BREAKDOWN.csv`와 `TIMING_SETUP.csv`는 실제 완료한 키 블록 수와 비용을 제공한다. 준비는 두 arm 모두 배치 총시간에서 제외하여 따로 제시했다. 각 block의 키는 예열/측정 동안 재사용한다. 정확성 실행의 total은 키 준비를 포함하므로 이 paired total과 다르다. 미분리 잔여에는 원래 harness의 평문 참조·기록 준비·GC 등이 들어가며 통신이나 gate 비용으로 임의 분류하지 않는다. PDF 추론 합은 인코딩·암호화+동형 계산+복호화·디코딩이며, 원시 total과 그 비율을 모두 보존했다. 이 분해 계획은 감사/paired 실행 전에 `ANALYSIS_TIME_BOUNDARIES.json`에 남겼다. MLP adapter I/O는 실행상 0이며 네트워크·직렬화 전송·운영 큐 대기는 미측정(null)이다. 입력당 환산값은 batch amortization이며 단일 요청 latency가 아니다.', '',
    '## 실제 입력 유형과 기존 결과 보강', '',
    '`INPUT_TYPE_EXAMPLES.json`은 수치 batch/key 조건 통과 후 판정이 다른 입력, 같은 입력의 제안 결과, 양쪽 보존 입력, 제안 실패/오차 위반/적용 밖 입력을 원시 경로·candidate·key·logits로 연결한다. 유형 집계는 고유 입력 기준이며 조건이 겹칠 수 있다. 관측되지 않은 유형은 0이며 해당 유형을 만들기 위한 입력·허용값 조정은 없다. 선택에서 수치 기준을 통과했다는 사실과 test batch에서도 해당 수치 기준을 통과했다는 사실을 구분한다.', '']
    lines+=input_type_table(s)
    lines+=['','[첫 확대 추가 분석](FIRST_EXPANSION_ADDENDUM_KO.md)은 기존 원시 자료만 사용했다. 적용 820사례–입력/2,460키 관측, 초기 변화 70고유/201회·오차 228고유/675회, 선택 후 적용 0회·경계 1회를 재확인했다. 201→0은 내부 초기/선택 구성 비교다. Spambase MLP의 선택 적용 영역은 11/32이며 출력 스케일·16특징·학습/개발/선택/별도 마진 분포를 추가 공개했다. scale24의 최대오차가 더 큰 SAFE 후보와 scale28의 더 작은 최대오차에도 거절된 후보는 같은 출력·입력으로 확인했다. 그러나 실제 최소 최대오차 후보는 네 사례 모두 SAFE였으므로 최소오차 선택 일반의 실패라는 주장은 지지되지 않는다. 첫 확대의 개발 FP16 기준 사후 재분석에서는 두 선형의 수치 선택이 S32·Q8·N14였다. Spambase 선형의 원래 제안 선택 S24·Q7·N13과 구성 차이가 있었지만, 해당 수치 선택 후보의 별도 감사/paired 비교는 새로 실행하지 않아 미확인이다. Spambase MLP는 같은 후보의 기존 감사만 재사용했다. 구성 선택 중 관측한 시간 차이를 최종 성능 개선으로 표현하지 않는다.', '',
    '## 실제 선행 방법과의 비교', '',
    '[공식 EVA native 비교](EXTERNAL_COMPARISON_KO.md)는 기존 공통 다항식에서 원래 scale30/range20 설정으로 실제 compiler/SEAL 실행을 수행한 결과다. 제안 방법도 원래 정책으로 독립 선택했다. 별도 500중 공통 적용 498입력·1,494키 관측에서 양쪽 판정/오차 위반은 모두 0이다. 경계 변화는 EVA 1회, 제안 2회이며 각각 고유 1입력이다. EVA의 최대오차/RMSE가 더 작았다. 원래 S20의 과거 실패를 이번 A의 실패로 바꾸지 않는다.', '',
    '같은 수식·가중치·입력·출력 의미를 확인했지만 SEAL/Lattigo의 packing·일정·키 분포와 보안 assessment가 동일하지 않다. 같은 128bit 목표의 실제 외부 결과로 분류하고 선택 조건만의 인과적 속도 비교는 보류한다. Fashion 전체 그래프를 EVA에 새로 연결하지 않았으며, 그것이 지원 불가능하다고 판정한 것은 아니다. 기존 HEIR 이식·EVA native·CoreLab 실행·문헌만 확인한 대상은 [관련 연구 기준표](RELATED_WORK_CRITERIA_KO.md)에서 구분했다.', '',
    '[FHE-Agent 정정](FHE_AGENT_CORRECTION_KO.md)은 arXiv:2511.18653v1 §4.1/4.3의 활성화 고정 설명을 반영한다. 같은 판본 §5.3 표현과의 불일치도 남겼고 공식 실행 구현에서 확인하지 못한 부분은 미확인이다. 이전 문서의 일반화는 정정 기록으로 대체하며 최종 PDF는 수정하지 않는다.', '',
    '## 보존·실패·검증 한계', '',
    '수정은 새 `research/fashion_extension` 복사본의 Fashion 데이터/모델 식별 연결, 명령 wrapper, 새 분석/검증/보고 스크립트, 현재 인계/로드맵/CI다. 원래 학습·Adam, 다중 클래스 인증, 합성·조정·보안 정책, 실제 CKKS 연산 및 V17 paired 함수는 바이트 동일성을 확인했다. 전체 변경과 보존 검사는 `VALIDATION.json`, `PRESERVATION.json`, `CHANGED_FILES.txt`에 기록한다.', '',
    '중첩 실행으로 중단한 첫 Fashion 시도, 필드명 reader 오류와 append-only 수정, seed 1 source-commit 설명 필드 오타를 보존했다. 완료된 키 결과를 지우거나 유리한 측정만 선택하지 않았다. source-commit 오타는 모델을 다시 쓰지 않고 실제 trainer hash로 정정했다. 소스 lock의 trainer 외 파일은 후속 컴파일 수정 이력과 구분한다. native 과학적 거절, 프로세스 중단, reader 오류를 하나의 실패율로 합치지 않는다.', '',
    '분모는 유한 입력과 실제 키 문맥에 한정된다. Fashion 한 데이터·한 구조의 세 초기값이며 일반 CKKS·새 키·미래 입력에 대한 위험 상한이나 통계적 동등성을 보장하지 않는다. 평문 분류 정답률, 모델 근사, CKKS 판정 일치, 공격 무결성은 서로 다른 문제다. 원시 점수·구성·모델·프로토콜 hash와 독립 검증을 보존하지만 테스트 통과를 연구 효과로 대신하지 않는다.', '',
    '## 이번 묶음의 종료', '',
    '이번 결과는 내부 조건 비교, 새 분포/학습 초기값 적용 범위, 실제 외부 실행 비교를 구분하여 기존 논문의 설명과 평가 범위를 보강한다. 보강 문단은 `MANUSCRIPT_ADDENDUM_KO.md`에 별도로 남기며 PDF에 삽입하지 않는다. 이 묶음 이후 다른 모델·데이터셋·compiler·운영 큐의 대규모 실험은 자동 실행하지 않는다. 재현 절차는 [REPRODUCTION.md](REPRODUCTION.md), 전체 방법별 수치와 실행 범위는 `summary.json` 및 CSV를 기준으로 한다.', '',
    '다음 최소 검토 후보는 첫 확대 Spambase 선형의 수치 선택 S32·Q8·N14와 제안 선택 S24·Q7·N13에 대한 고정 구성 감사/paired 비교 한 건이다. 이미 관측한 선택 차이가 별도 판정과 비용에도 이어지는지를 확인할 수 있다. 새 실행을 한다면 새 protocol/run ID를 사용하고, 이미 노출된 입력의 재평가임을 명시하며 새로운 독립 입력의 확증으로 표현하지 않는다. 허용값·모델·후보를 다시 고르지 않는다. 이 제안은 이번에 실행한 결과가 아니며 자동 착수하지 않는다.', '']
    textout('REPORT_KO.md','\n'.join(lines))
    paragraphs=['# 최종 PDF에 대한 최소 보강 문단안', '', '최종 PDF에는 삽입하지 않은 별도 제안이다. 기존 본문의 수식·장절·용어를 복원하거나 재구성하지 않는다. 보고서/CSV는 재현 부록이고 아래 문단만 본문 수준의 후보로 둔다.', '', '## §5.1–5.2 평가 범위 보강', '', '기존 다중 클래스 제곱 MLP를 유지하면서 Fashion-MNIST와 세 학습 초기값으로 적용 범위를 확대하였다. 공식 학습 자료에서 학습·개발·구성 선택 입력을 분리하였으며, 시험 자료는 선택 완료 후 고정 구성의 별도 평가에 사용하였다. 세 초기값은 하나의 데이터·모델 구조에 대한 반복 사례로 구분하였다. 평가 입력과 키 관측을 따로 집계하고 적용 영역 밖의 판정 변화도 보존하였다.', '']
    for c in s['cases']:
        p=c['roles'].get('proposed');a=c['audit'].get(p['id'],{}) if p else {}
        paragraphs.append(f"초기값 {c['seed']}에서는 선택 후보 {c['direct_trials']}개를 평가하였고, 별도 완료 입력 {a.get('inputs',0):,}개 중 적용 입력 {a.get('applicable','미평가')}개에서 판정 변화 {a.get('applicable_flip_events','미평가')}회와 입력별 오차 조건 위반 {a.get('applicable_error_events','미평가')}회를 관측하였다. 경계 영역 판정 변화는 {a.get('boundary_flip_events','미평가')}회였다.")
    paragraphs+=['', '## §5.5 수치 조건과의 비교', '', '동일한 모델과 유한 후보 범위에서 개발 출력으로 미리 정한 수치 오차 기준을 적용하여 구성을 선택하고 제안 수용 조건과 비교하였다. 공통 초기 합성에는 마진 정보가 포함되어 있으므로 이 비교는 후보 범위 안의 수용 조건에 관한 결과다. 전체 후보 평가 후의 최속 선택은 제한된 후보 수에서 최초 수용 구성을 찾는 절차와 예산이 다르며, 구성 선택 비용과 별도 추론 비용을 구분하였다.', '', ('평가한 유한 후보에서는 수치 기준과 제안 기준의 수용 집합이 같아 수용 조건 차이에 의한 선택 개선은 관측되지 않았다. 이는 새 데이터에 대한 관측 범위를 보강하지만 수치 기준 대비 일률적 우월성을 뒷받침하지는 않는다.' if same_sets else '수용 집합과 선택 구성의 차이는 사례별로 공개하였으며 수치 오차 조건 통과와 입력별 판정/오차 조건 통과를 구분하였다.'), '', '## §5.7 외부 비교 범위 보강', '', '기존 공통 다항식에서 공식 EVA의 원래 설정에 따른 암호화 실행과 제안 절차의 독립 선택을 비교하였다. 별도 적용 영역 498입력에서 세 키 관측의 판정 변화와 입력별 오차 위반은 양쪽 모두 없었고, EVA의 수치 오차가 더 작았다. 적용 영역 밖에서는 각각 한 입력에서 판정 변화가 관측되었다. 두 경로의 배치와 실행 일정이 달라 시간 차이를 수용 조건만의 효과로 해석하지 않았다.', '', '관련 연구의 정확도 평가와 구성 수용 조건은 구분한다. FHE-Agent의 활성화 고정 설명을 인정하며 입력별 판정 마진을 선택에 반영하는지에 한정하여 차이를 논의한다. 별도 FHE_AGENT_CORRECTION_KO.md는 완료된 선행 문서의 설명 정정이고 최종 PDF의 자동 수정이 아니다.', '']
    textout('MANUSCRIPT_ADDENDUM_KO.md','\n'.join(paragraphs))
    fig,axes=plt.subplots(1,2,figsize=(8.2,3.1),layout='constrained')
    for seed in [0,1,2]:
        hist=[read(RUN/f'plaintext/seed_{seed}/epoch_{i:02d}.json')['epoch'] for i in range(1,9)]
        axes[0].plot(range(1,9),[e['mean_training_loss'] for e in hist],marker='o',ms=3,label=f'seed {seed}')
        axes[1].plot(range(1,9),[100*e['validation_accuracy'] for e in hist],marker='o',ms=3,label=f'seed {seed}')
    axes[0].set_ylabel('Online training loss');axes[1].set_ylabel('Development accuracy (%)')
    for ax in axes:ax.set_xlabel('Epoch');ax.grid(alpha=.2);ax.legend(frameon=False)
    for ext in ['pdf','png']:
        p=DOC/f'TRAINING_CURVES.{ext}'
        if p.exists():raise FileExistsError(p)
        fig.savefig(p,dpi=200)
    plt.close(fig);print('BOUNDED_REPORT_WRITTEN',s['status'])
if __name__=='__main__':main()
