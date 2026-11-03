#!/usr/bin/env python3
"""Write reviewable prose from the completed, existing-evidence reaggregation."""
from pathlib import Path
import csv,json,hashlib,re
ROOT=Path('/home/ckks2/deciprotect');D=ROOT/'docs/research/fg_journal_evidence_v1_20260906';T=D/'evidence_tables'
def put(n,s):
    with (D/n).open('x') as f:f.write(s.strip()+'\n')
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def readcsv(n):return list(csv.DictReader((T/n).open()))
scope=json.loads((ROOT/'results/fg_journal_evidence_v1_20260906_run01/ANALYSIS.json').read_text())

patches=[
('P01',2,'I. 서론','결과에 미치는 영향이 다르기 때문이다.','예를 들어 평문 점수가 0.5001이고 임곗값이 0.5','본 논문은 판정 경계까지의 거리인 마진을 입력별','예시 문단 끝에 삽입',
 '이 예시는 작은 수치 오차가 판정을 바꿀 수 있다는 일반 현상을 설명한다. 예시의 마진 0.0001은 본 실험의 경계값 0.001보다 작으므로, 이후 실험에서 판정 안정성을 평가한 입력 범위에는 포함되지 않는다.'),
('P02',3,'§2.2','정한 마진 비율','판정 경계에 너무 가까운 입력은 데이터의 작은','포함되지 않는 입력은 경계 입력으로 기록','식 (3) 직전의 경계 제외 설명 교체',
 '판정 경계에 가까운 고정 입력도 CKKS 오차에 의해 판정이 바뀔 수 있다. 본 연구는 이 가능성을 부정하지 않고 평가 범위를 명시적으로 제한한다. 구성 선택용 입력 중 마진이 사전에 정한 경계값 δ보다 큰 입력만 Vδ에 포함하며, 나머지는 경계 입력으로 구분한다.'),
('P03',4,'§2.3, 식 (4), Fig. 2','순위 변화에 대한 여유를','다중 클래스 과제에서는 평문 최고 점수와 가장','MLP-100과 LeNet-5-small에 식 (4)를','적용 영역 설명 뒤에 한 문장 삽입',
 '적용 영역을 정하는 마진은 최고 점수와 두 번째 점수의 차이지만, 식 (4)의 수용 검사는 평문 선택 클래스를 제외한 모든 경쟁 클래스에 적용한다.'),
('P04',5,'§3.2','전체 CKKS 구성 공간을 모두 평가하기는 어렵','비교 집합 전체를 동일한','각 사례에서는 모든 기준을 만족','537회 문장 앞뒤의 비교 집합 설명에 삽입',
 '비교 집합의 생성 규칙은 실험 전에 고정하였다. 각 사례에서는 제안 기법과 같은 초기 합성 규칙을 사용한 뒤, 스케일 지수를 4비트씩 최대 세 단계 높인 구성과 각 단계에서 Q 소수 하나를 추가한 구성을 생성하였다. 보안 및 백엔드 제약을 통과해 실제 평가된 구성은 67개 사례에서 각각 8개, LeNet-5-small에서 1개로 총 537개였다. 이 집합은 선택용 입력의 마진을 사용하는 초기 합성에 의존하며, 제안 기법이 최종 선택한 구성으로 범위를 다시 정하지는 않았다. 따라서 537회는 사례별 후보 평가 묶음의 합이며, 전체 CKKS 공간의 독립적 탐색이나 서로 다른 전역 파라미터 537종을 뜻하지 않는다.'),
('P05',6,'§4.2','분석적 보증은 아니다.','연산별 계산 규칙과','추정한 정밀도에 Table 2의 초기 스케일 하한과','재현성 자료 참조 문장을 아래 문단과 예시 표로 교체',
 '''Banknote의 다항식 모델 한 분할을 예로 들면, 선택용 입력 275개의 최소 판정 마진은 0.00277960, 출력 오차 예산은 0.00138980, 오차 확대 추정값은 2.576이었다. 이로부터 정밀도 11비트를 산정하고 Table 2의 여유와 하한을 적용해 초기 스케일 지수 18을 얻었다. 백엔드의 소수 생성 제약을 반영한 실제 최초 구성은 스케일 지수 20이었으며, 최초 암호화 평가 후 기존 조정 규칙에 따라 24로 높였다. 이 사례는 조정된 21개 사례 중 고정된 사례 식별자 순서의 첫 적격 사례로, 전체 효과의 추정이 아닌 절차 설명용이다.

Table S1. Worked example of configuration synthesis and adjustment

| Item | Initial encrypted evaluation | After adjustment |
| --- | --- | --- |
| Scale exponent | 20 | 24 |
| log₂N / number of Q primes | 13 / 7 | 13 / 7 |
| Q bit lengths | 23, 20×6 | 27, 24×6 |
| P bit length / total QP bits | 30 / 173 | 30 / 201 |
| Decision changes / error violations | 11 / 43 | 0 / 0 |

두 결과의 분모는 각각 적용 입력 275개를 세 키 집합에서 실행한 825개 관측이다. 같은 입력의 평문 점수 0.50277960에 대해 최초 CKKS 점수는 0.49070810, 선택 구성의 점수는 0.50269778이었다. 해당 입력의 마진은 적용 범위에 들어가며, 선택 구성에서 판정과 오차 조건이 함께 유지됐다. 서로 다른 구성에서는 각각 새 키를 사용했다.

상세 계산과 원시 기록 대응은 제출용 보충자료 「최종 논문 기존 증거 재현 보충자료 v1」의 `REPRODUCTION_SUPPLEMENT_KO.md` 및 `evidence_tables/SYNTHESIS_WORKED_EXAMPLE.json`에 제시한다. 이 자료는 현재 로컬 제출 첨부안이며 외부 공개본은 아니다.'''),
('P06',4,'§3.1, Table 2','128비트 이상으로 정하였다.','보안 적합성 판정은 Table 2에 명시한','이진 과제에서는','보안 적합성 설명 뒤에 삽입',
 '구성 생성·조정 시의 선언 비트 수 검사와 백엔드 유효성 검사는 구분하였다. 실제 소수에 대한 별도 사후 검증은 수행된 구성과 검사 시점을 보충자료에 명시하며, 일부 구성의 사후 검증을 모든 실행의 동일한 검증으로 확대하지 않는다.'),
('P07',6,'§4.3','암호화 실행으로 판정 결과와 입력별 오차를 확인한','모든 선택용 입력과 세 키 집합에서 기준을 만족','출력 오차가 한계를 넘으면 스케일 지수','모든 입력에서 기준 만족 문장 교체',
 '선택용 입력 전체를 실행하되, 판정 일치와 입력별 오차 기준은 Vδ에 포함된 입력과 세 키 집합 모두에 적용한다. 경계 입력의 결과는 별도로 기록하며 이 수용 판정의 분모에 넣지 않는다.'),
('P08',7,'§5.1, Table 4','주요 평가의 모델별 구성은 Table 4와 같다.','각 교차검증 분할에서 독립적으로 다시 학습하였다.','MLP-100,','모델 설명 뒤에 과제 및 품질 표 삽입',
 '''Iris는 원래 클래스 0과 1만 남긴 이진 과제, Digits와 표형 MNIST는 짝수를 1, 홀수를 0으로 구분하는 과제로 사용하였다. Banknote와 WDBC는 원래 이진 레이블을 유지하였다. 표형 MNIST는 전체 원자료에서 균형 표집한 2,500개 영상을 4×4 특징으로 축소한 자료이며, 공식 학습·시험 분할을 유지한 MLP-100과 LeNet-5-small의 10개 클래스 과제와 구분한다. packed CNN-lite는 숫자 0과 1의 이진 과제이다.

Table S2. Plaintext accuracy on configuration-selection and separate inputs

| Model family | Cases | Selection accuracy (%) | Separate-input accuracy (%) |
| --- | --- | --- | --- |
| Polynomial | 25 | 80.0–100.0 | 80.2–100.0 |
| 1-layer MLP | 25 | 85.4–100.0 | 84.4–100.0 |
| 2-layer MLP | 15 | 85.2–100.0 | 85.8–100.0 |
| MLP-100 | 1 | 97.0 | 97.6 |
| LeNet-5-small | 1 | 98.8 | 98.6 |
| Packed CNN-lite | 1 | 98.0 | 99.2 |

범위는 해당 사례들의 최솟값과 최댓값이며, 정답률은 경계 입력을 포함한 전체 입력의 평문 예측을 정답과 비교한 값이다. 판정 일치는 평문 예측이 정답인지를 뜻하지 않는다. 학습 설정, 역할별 클래스 수·혼동행렬 및 사례별 적용 비율은 보충자료에 제시한다. 특히 Table 5에서 이미 밝힌 WDBC 2층 MLP의 낮은 적용 비율은 이 정답률과 별도로 해석한다.'''),
('P09',7,'§5.2','겹치지 않도록 나누었다.','전처리 파라미터와 판정 임','MLP-100,','전처리와 임곗값의 출처 문장 교체',
 '표형 모델의 특징 선택, 표준화와 출력 스케일은 각 분할의 학습용 입력에서만 정하였다. 이진 판정 임곗값은 출력 정의에 따라 표형 모델에서 0.5, packed CNN-lite에서 0으로 고정했으며, 별도 평가용 입력으로 조정하지 않았다.'),
('P10',7,'§5.1, Table 5 및 §5.6','사례 수와 구성 평가 횟수는 다른 단위다.','주요 평가와 별개로 모델 본체와 출력부의 통제 조','5.2 비교 방법과 측정 절차','63개에 깊이 그래프가 포함된 것으로 읽히는 문장 교체',
 '''주요 평가와 별개로 모델 본체·출력부의 통제 조합 30개, 표형 모델의 학습 초기값 반복 24개, 다중 클래스 모델의 반복 6개, packed CNN-lite의 반복 3개로 총 63개 모델 사례를 추가 분석하였다. Fig. 6의 곱셈 깊이 1, 2, 4, 6, 8은 이 63개와 별도의 계산 그래프 5조건이다.

Table 5의 Additional analysis 63 cases 행은 유지하고, 다음 행을 별도로 추가한다.

| Evaluation set | Size | Scope |
| --- | --- | --- |
| Depth sensitivity | 5 graph conditions | Fig. 6; separate from 63 model cases |'''),
('P11',9,'§5.4–5.5, Table 7','이 값은 암호화 추론 시간만 비교','95% 신뢰구간은 1을 포함','통계적으로 유의한 차이를','95% 신뢰구간 문장 교체 및 아래 설명 삽입',
 '''기준 구성/제안 구성 지연시간 비율은 1.00054093, 95% 신뢰구간은 [0.99996747, 1.00112178]이었다. 신뢰구간은 1을 포함하므로 기존 결론과 같이 유의한 차이를 검출하지 못했으며, 지연시간이 동등함을 입증한 것은 아니다.

기준 구성과 제안 구성은 68개 중 65개 사례에서 전체 파라미터와 실행 경로가 같았다. Table 7의 최속 실행 구성에서 다른 선택 23개는 식별자 기준이며, 그중 21개가 실제 파라미터·실행 경로의 차이이고 2개는 같은 구성의 식별자 차이였다. 기준 위반 18개 사례에는 판정 변화와 오차 조건 위반이 함께 관측됐으며, 오차 조건만 위반한 사례는 없었다. 이는 사례 단위 분류이며 해당 사례의 모든 위반 입력이 판정도 바뀌었다는 뜻은 아니다.

조정 21사례의 최종/초기 지연시간 비율 1.004508은 선택 과정에서 각 구성과 세 키에 기록된 평균 추론시간의 사례별 비율 중앙값이다. Table 7의 별도 대응 시간 측정과 달리 선택 단계의 관측 비교이며, 추가 후보 평가 전체 비용을 포함하지 않는다.'''),
('P12',10,'§5.7','외부 도구 결과는 실행 범위와 출력 형식이 달라','보조 자료로 활용하였다.','HEIR의 동일 다항식 워크','외부 결과 첫 설명 뒤에 삽입',
 'HEIR 결과는 외부 산출·설정을 공통 백엔드에 연결한 이식 비교이고, EVA 결과는 공식 EVA/SEAL 경로의 실제 암호화 실행이다. EVA S20은 지정한 초기 입력 스케일의 보조 관측으로, EVA의 원래 선택 절차가 항상 이 구성을 고른다는 뜻은 아니다. 서로 다른 도구의 실행 일정·슬롯 배치·보안 평가 가정을 같다고 두지 않으며, 이 결과만으로 선택 기준의 우월성을 판단하지 않는다.')]

# Anchors are short extracts, not fabricated full sentences. The layout extractor
# interleaves columns; validate each whitespace-normalized anchor on its page.
anchors=[];parts=['# 최종 논문 최소 삽입·교체 문안 v1\n\n기준: `baseline/journal_final_20260905.pdf`, SHA-256 `0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85`. 아래는 **구현·기존 기록 확인에 따른 보강안**이며 PDF나 기존 원고에 적용하지 않았다. 이전 PDF 한정 심사는 수정하지 않았다. 표 S1·S2는 삽입 검토용 임시 번호이며 최종 조판 시 번호만 정리한다. 삭제된 수식·의사코드는 복구하지 않는다.\n\n앞·대상·뒤 문장은 위치를 찾을 수 있는 짧은 발췌로 표시한다. 문안은 원래 절에 넣을 최소 단위이며 후속 A/B/C 결과는 별도 문서에서만 다룬다.']
for ident,page,section,before,target,after,action,body in patches:
    txt=(ROOT/f'results/fg_journal_review_v1_20260906_run01/pdf_page_{page:02d}.txt').read_text();flat=re.sub(r'\s+','',txt)
    for label,text in [('before',before),('target',target),('after',after)]:
        ok=re.sub(r'\s+','',text) in flat
        anchors.append({'patch_id':ident,'page':page,'section':section,'anchor_role':label,'anchor':text,'matched':ok})
    parts.append(f'## {ident} · {page}쪽 {section}\n\n앞 문장 발췌: “{before}”\n\n대상 문장 발췌: “{target}”\n\n뒤 문장 발췌: “{after}”\n\n작업: {action}.\n\n**삽입·교체 문안**\n\n{body}')
put('MANUSCRIPT_PATCH_KO.md','\n\n'.join(parts))
with (T/'PATCH_ANCHORS.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=anchors[0]);w.writeheader();w.writerows(anchors)
print('ANCHOR_MISSES',json.dumps([r for r in anchors if not r['matched']],ensure_ascii=False))

groups=readcsv('MODEL_SUMMARY.csv')
summary_table=table(['Dataset / model','Cases','Separate n / applicable / boundary','Accuracy % (min–max)','Coverage % (min–max)','Selected median ms (min–max)','Unit'],[
 [r['dataset']+' / '+r['model_id'],r['cases'],f"{r['separate_inputs']} / {r['applicable']} / {r['boundary']}",f"{100*float(r['accuracy_min']):.2f}–{100*float(r['accuracy_max']):.2f}",f"{100*float(r['coverage_min']):.2f}–{100*float(r['coverage_max']):.2f}",f"{float(r['direct_median_ms_min']):.3f}–{float(r['direct_median_ms_max']):.3f}",r['timing_unit']] for r in groups])
put('REPRODUCTION_SUPPLEMENT_KO.md',r'''
# 최종 논문 기존 증거 재현 보충자료 v1

문서 ID: FG_JOURNAL_EVIDENCE_V1_20260906. 기준 PDF와 원래 구성 선택 방법을 유지하는 **구현·동결 기록 확인 및 기존 평문 산술 재집계**다. 새 CKKS·소수 생성·학습·모델 refit·C/C′ 변경은 없다. 본 파일의 내부 식별자와 상세 산식은 본문에 자동 삽입하지 않는다. 로컬 제출 첨부용 v1이며 공개 저장소·외부 서비스에 게시하지 않았다.

## 1. 증거의 우선순위와 실행 소스 연결

최종 PDF의 SHA-256은 `0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85`다. 작업 시작 HEAD는 `54671293e5f6532f2423f5bf473ea714555ee9f4`. 사용자 지시, 이 PDF, 당시 protocol·raw와 대응 소스, 검증된 재집계 순으로 사용했다. 이전 PAPER_ONLY의 심사 내용·해시는 보존했고 여기에 코드를 근거로 보충한 내용을 소급 주입하지 않았다.

`SOURCE_CLOSURE.csv`의 12개 파일과 `ADDITIONAL_SOURCE_CLOSURE.json`에 대해 실제 읽은 소스 바이트를 당시 source snapshot의 개별 SHA에 맞췄다. 원래 `source_snapshots/v17_final_vm1x6_20260811T050104Z/manifest.json`의 source tree digest는 `2095f4bf8bf3a30997bf1c526b8bea74f99e353d3ae43bf89df2104a80b187cd`, scientific execution digest는 `495ca799cd110c6180b5bf981bebf8339d31d895c71c20d6db02ea34acc88c57`이다. 실행 소스 closure commit은 `cefc44b0d7e351db2a34886dd758a2d31a3e4c12`; 후속 집계 commit `86b0403208abbc741a65934358a5dea4a66e4d88`과 구분한다. 당시 Git HEAD만으로 미커밋 실행 소스를 설명하지 않는다. 과거 전체 314파일 재해시를 반복하지 않았다.

읽기 경로의 `baseline/source`가 최근 복사본이라는 이유만으로 과거 증거가 되는 것은 아니다. 이번에 인용한 파일은 위 대응을 거쳤다. 학습 builder와 frozen raw는 원본 FlipGuard에서 **파일만 읽었고**, 원본 스크립트·Go 프로그램·인터프리터를 그 위치에서 실행하지 않았다. 원래 baseline/source 문맥에 있는 비활성 정책 함수가 원래 C에서 활성 실행됐다는 뜻도 아니다. 예시의 실제 plan은 `precision_slack_mode=none`이다.

원시 자료 참조는 절대 경로·SHA·필드 또는 JSON pointer로 연결했다. `READ_BINDINGS.json`, `DETAIL_READ_BINDINGS.json`, `ADDITIONAL_QUALITY_READ_BINDINGS.json`은 이번에 사용한 범위의 출처 목록이다. 두 다중 클래스 사례의 inventory/legacy split 명칭 차이는 `CASE_ID_ALIASES.csv`에 보존했다. 별개 모델이나 추가 사례로 세지 않고 같은 raw 경로와 실제 contract split을 확인했다.

## 2. 초기 합성과 한 단계 조정의 실제 사례

선정 규칙: 주요 68 중 조정된 21개를 case ID 사전순으로 정렬하고 원시 plan·trial·입력 추적이 갖춰진 첫 사례를 사용한다. 최대 개선 사례를 고르지 않았다.

- case: `primary|banknote|linear_poly3|outer_fold_0_training_seed_0`.
- 고정 모델 SHA: `e1fe81715d04bd32b62c60de8e3cc1edbf3c8940f1c5254206b9299265338de1`.
- 모델 경로: `/home/ckks2/flipguard/results/model_family_expansion_v17/plaintext/primary/banknote/linear_poly3/fold_0/training_seed_0/model.json`.
- raw 선택 경로: `/home/ckks2/flipguard/results/model_family_expansion_v17/runs/v17_final_vm1x6_20260811T050104Z/primary/banknote/linear_poly3/fold_0/training_seed_0/selection.json`; SHA `6a85ea8bfbb6c41e8ae8fde0153b276a7d625a247e39fc5661327d442a0abe87`.
- 학습/선택/별도 입력: 822/275/275. 선택 275개 모두 margin>0.001. 입력 특징 4, 출력 `0.5+0.197z−0.004z³`, threshold=0.5. 유효 요구 슬롯 1; 스칼라 복제 실행이다.

계산은 `BuildTabularWorkloadContract` → `AnalyzeBoundsAndSensitivity` → `aggregateOperationSensitivity` → `Synthesize` → `synthesizeBackendValidRescaleCandidate` / `synthesizeRescaleCandidate` → `Profile` → 실제 trial → `RepairCandidate`로 이어진다. 파일과 줄이 포함된 발췌는 `source_excerpts/`에 있다.

| Step | Actual value / calculation | Evidence |
| --- | --- | --- |
| 평문 관측 범위 | 정규화 입력 max abs 3.5423741437354272; z ∈ [−0.8936325467103716, 0.5915879201071373]; 출력 max abs 0.6157146533330677 | contract.calibration, WORKED_EXAMPLE_NODE_RANGES.csv |
| 판정 예산 | 최소 적용 마진 0.0027796012554593963 × ρ0.5 = 0.0013898006277296981 | contract.decision |
| 민감도 합 | 다항식 도함수 절댓값 최댓값 0.197; 상수배 4·합산 3·bias 합산 1개 노드의 각 민감도 0.197, 출력 노드 1 → 합 2.576 | 기존 IR과 순수 평문 구간 복원 |
| 단위 오차 예산 | 0.0013898006277296981 / 2.576 ≈ 0.000539519 | SYNTHESIS_WORKED_EXAMPLE.json의 정밀값 |
| 정밀도·분석 scale | ceil(−log₂(unit budget))=11; max(11+3,18)=18 | Table2와 frozen policy |
| 정적 백엔드 보정 | 기록된 attempts=3, lift=2 → 최초 실제 scale20 | initial_candidate.backend_* |
| 실제 연산 단계 | IR 곱셈 깊이2와 backend rescale 소요6은 다름; terminal scale exponent1 → Q 7개 | contract.graph / deployment |
| 첫 Q / P | message bits0; 첫 Q=S+0+1+2=23, 뒤 6개20; P=max(30,23)=30 | synthesis.go |
| 보안·환 차수 | Q143, QP173; N12 cap106은 부족, N13 cap214 통과 → N8192 | initial_candidate.security |
| 최초 암호화 trial | 275×3=825 관측; 판정 변화11, 오차 위반43 → REJECTED | trials[0].sample_ledger |
| 기존 조정 | scale20→24; Q=[27,24,24,24,24,24,24], P=[30]; Q171, QP201; N13 유지 | trials[1].candidate |
| 두 번째 trial | 825 관측; 판정 변화0, 오차 위반0 → SAFE; 후보2회/키 실행6회 | trials[1].sample_ledger |

정적 보정의 실패 시도별 소수/오류 문자열은 이 선택 기록에 저장되지 않았다. attempt3/lift2와 frozen retry 규칙으로 분석 단계와 실제 최초 구성을 구분했으며 소수 생성기를 재실행하지 않았다. 코드의 max scale50은 초과 시 실패시키는 상한이며 무조건 50으로 낮춰 통과시키는 규칙이 아니다. 분석 helper에 전달된 0.05 분위값은 원래 primary contract의 예산 출처가 아니다. primary는 δ보다 큰 마진의 최솟값을 별도로 계산한다.

입력226, key-repeat index1의 기존 기록은 `ACTUAL_DECISION_REPAIR_EXAMPLE.json`에 담았다. 평문0.5027796012554594; 최초0.4907081033856266, 오차0.012071497869832803; 선택0.5026977750559247, 오차0.00008182619953467363; 한계0.0013898006277296981. 최초의 flip/error는 모두 참, 선택은 둘 다 거짓이다. key index1의 대응이며 서로 다른 후보에서 같은 비밀키를 썼다는 주장은 하지 않는다. 입력을 재생성하거나 실패를 만들지 않았다.

이 민감도는 관측 입력 구간과 구현 DAG의 초기 추정이다. 실제 CKKS 전역 오차 보증, 모든 미래 입력의 충분조건 충족, 최소비용 최적성으로 확대하지 않는다.

## 3. 보안 검사의 시점과 적용 범위

`DefaultSecurityEnvelope`와 당시 plan은 secret `ring.Ternary(P=2/3)`, error `ring.DiscreteGaussian(sigma=3.2,bound=19.2)`를 기록한다. 원래 conservative 기준은 Security Guidelines Table5.2, classical Category128, logN12/13/14/15의 모듈러스 한도106/214/430/868이다. ciphertext Q와 evaluation-key QP가 각각 한도를 통과해야 한다. 표의 sigma3.19와 runtime3.2의 차이를 exact-distribution 동등성으로 쓰지 않는다.

| Check | Stage | Confirmed scope / limitation |
| --- | --- | --- |
| 선언 Q/QP 비트 검사 | 합성·조정, 실제 trial 앞 | 이번 예시 및 실행된 후보의 admission 필드; 표 기반 구성 수용 |
| backend literal 유효성 | Profile/parameter construction | NTT용 소수 및 backend 실행 가능성; lattice 보안 estimator 자체가 아님 |
| 실제 소수 사후 검사 | 기존 journal multiclass reconciliation | 기존4후보 중 주요 MLP-100·LeNet 선택2후보의 ID와 literal을 직접 일치시킴 |
| 후속 Bank의 별도 helper 호출 | 기존 정책 자료의 읽기 전용 확인 | 이번에 새 호출 실행으로 확인하지 않음; 함수 존재만으로 실행 판정하지 않음 |

`SECURITY_CHECK_SCOPE.json`에 일치한 두 주요 후보의 Q/QP 실제 로그값과 기존 사후 기록을 담았다. MLP-100 실제 QP193.99920762616645, LeNet856.0000005968122; 기존 두 classical estimator 모델의 최소치는 각각145.229851075969와132.046927836598비트다. 4후보 사후 검증 전부를 주요68 또는 후속 Bank의 검증으로 세지 않는다. runtime Gaussian truncation을 estimator가 정확히 모델링하지 않았고 quantum 비용은 평가하지 않았다는 기존 제한을 유지한다. Banknote 예시의 exact-prime 사후 검사 연결은 이번 한정 자료에서 확립하지 못했다. 이것은 선언 admission 실패나 보안 위반을 관측했다는 뜻이 아니다.

## 4. 89회와 537회의 실제 규격

원래 protocol의 `candidate_space.json` 사본과 당시 `BuildV17DepthCompleteFiniteSet`을 함께 확인했다. `B3` 등 내부 이름은 보충자료에서만 사용한다. B3는 C의 동일 contract와 기본 초기 합성을 호출해 첫 후보를 만든 후 numerical repair를 최대3번(+4비트씩) 진행하고 각 단계에 level guard0/1을 만든다. 허용 경로는 원래 contract의 rescale이다. legacy 7 profiles×2 paths14행은 별도 진단이며 537에 넣지 않는다.

생성 규칙은 암호화 실행 전 고정됐지만 사례 literal은 선택용 평문을 분석한 contract에서 생성된다. 주 caller는 C 선택 후 B3를 실행하되 원래 contract를 넘긴다. C의 최종 선택 결과를 보고 후보 하한을 바꾸지 않는다. 반면 contract의 마진 예산을 사용하므로 주석의 “graph facts alone”를 판정 정보로부터 독립한 생성기로 읽으면 안 된다. 이번 후속 A/B 독립 생성기와도 다르다.

| Accounting | Direct procedure | Frozen finite comparison |
| --- | --- | --- |
| 사례 수 | 68 | 68 |
| 실제 후보 평가 묶음 | 89 | 537 = 67×8+1 |
| 실제 키 실행 | 267 | 1,611 |
| SAFE / REJECTED | 68 / 21 | 477 / 60 |
| 실행된 묶음의 backend/security 실패 | 0 | 0 |
| 평가된 후보마다 키 반복 | 3 | 3 |

537행 모두 실제3키 출력 관측을 가진다. 생성 전 탈락을0으로 평가한 것이 아니다. LeNet은 초기 S44, Q18/P54, 선언 QP856/N15에서1개만 생성·평가됐다. 같은 S에 Q하나를 더하면900, S를48로 높인 기본 QP는932로, N15 한도868을 넘는다. 이는 저장 literal과 규칙의 산술 설명이며 생성되지 않은 각각의 branch가 별도 보안 실패 로그로 남았다고 하지 않는다. 생성 불가 branch별 상세목록은 미기록이다. 미생성·미실행을 암호화 실패나 별도 후보 평가로 합산하지 않는다.

생성기 `seen`은 candidate ID 중복을 제거한다. 전체 literal+path를 새로 비교한 결과도 사례 내부537쌍이 모두 다르지만, 서로 다른 사례의 동일 파라미터까지 전역 중복 제거한537종은 아니다. direct와 finite에 공통 literal이 있으면 실행 역할과 키가 다르므로 실제 평가 묶음은 각각 보존한다. 그 숫자를 독립 입력 수로 해석하지 않는다. 후보 원본 literal은 저장된 ParametersLiteral 규격 전체이며, 실제 Q/P 소수값을 이번에 새로 materialize한 값이 아니다.

`CANDIDATE_SPECIFICATIONS.csv`는 direct89+finite537=626행이고 case/model/split, raw SHA/pointer, literal JSON, N/Q/P/S, 경로, 생성이유, 보안, status, 실제 키·입력 관측, flip/error를 담는다. `CANDIDATE_COUNT_AND_COMPARATORS.csv`는 사례별 합계와 후보 수용/선택을 연결한다. 표형에서도 숫자 지표만으로 수용했다고 바꾸지 않는다.

최속 실행 후보의 판정 변화 사례18와 오차 위반 사례18의 교집합은18, 오차만 위반한 사례0이다. 후보와 C의 식별자 차이23 중 실제 literal/path 차이는21, 명칭만 다른 경우2다. 그21 중 기준 위반18, 기준을 통과하면서 실제 구성이 다른 경우3이다. 최속 수용 후보는 C와 ID가63/68, literal/path가65/68에서 같다. 나머지3은 Digits 1층 MLP fold4(S20 대24), Iris 다항식 fold3(S20 대24), 표형 MNIST 1층 MLP fold1(S20 대28)이다. 표기의 등식은 비밀키나 난수·시간 관측의 동일성을 뜻하지 않는다.

89/537의 83.43%는 후보 평가 횟수 감소다. 전체 선택시간 감소율, 후보별 균일비용, 전역 최속 선택 또는 독립 대조군 대비 개선으로 바꾸지 않는다.

## 5. 데이터·모델·분할과 평문 품질

| Dataset path meaning | Original task / features | Partition and treatment |
| --- | --- | --- |
| banknote | 원자료 0/1 label 유지, 4특징 | 각 5-fold에서 학습/선택/별도 분리; label값의 의미를 이름만으로 추정하지 않음 |
| wdbc | sklearn breast-cancer 0/1 target 유지, 30중16특징 | 학습 자료만 표준화·특징 순위 계산 |
| iris_binary | Iris target<2만 유지, 4특징 | 제3클래스 제외; 원래3클래스 문제의 정답률이 아님 |
| digits_binary | 짝수1/홀수0, 64중16특징 | 전체10종 숫자의 parity 과제; 표준화·특징 선택은 학습만 |
| mnist_pool16 | 짝수1/홀수0, 28×28→4×4 평균풀링16특징 | 전체70,000 원자료에서 class별1250행 hash표집; 공식train/test 분리 유지 아님 |
| mnist_10class | 원래10종 숫자, 784입력 | 공식train60,000과 test10,000 분리 유지; CKKS는 아래500/500 |
| mnist_binary01 | 숫자0/1, 4×4, threshold0 | 공식train에서 학습·개발·선택, 공식test에서 별도 입력 |

표형65는 5데이터×5fold의 다항식25, 1층MLP25와 Banknote/WDBC/MNIST16의 2층MLP15다. StratifiedKFold(5,shuffle=True,random_state=1701)의 외부20%를 별도 입력으로 고정하고 나머지의25%를 stratified split(seed2701+fold)으로 선택용에 둔다. 약60/20/20비율이며 선택용과 별도 행은 사례 내부에서 겹치지 않는다. 표준화 평균·표준편차, 최대16특징의 로지스틱 가중치 순위, 출력 정규화는 학습 역할에서만 계산한다. 학습seed0이며 후속 확대의 NearMiss 등 절차를 가져오지 않았다.

다항식의 선형 본체는 LogisticRegression(liblinear,C1,max_iter2000). 특징 순위 계산도 liblinear/max_iter2000이다. MLP는 4 또는8→4 제곱 은닉층, full-batch Adam1200epoch, 초기 가중치 N(0,0.08), bias0, lr0.003, beta0.9/0.999, epsilon1e−8, L2=1e−4, 전체 gradient norm cap5다. 고정 횟수 종료이며 수렴 판정/early stopping 결과는 아니다. 선형 모델의 실제 n_iter·ConvergenceWarning은 모델 artifact에 저장되지 않아 경고가 없었다고 단정하지 않는다. 정규화된 학습 logits 최대 절댓값의 역수를 출력 가중치/bias에 적용한다. 다항식은 `0.5+0.197z−0.004z³`, MLP의 선형 score는 `0.5+0.197z`; threshold0.5는 고정 출력 정의다.

MLP-100은784→100(square)→10, LeNet은28×28을32×32 zero-pad한 뒤 conv6(5×5)→square→avgpool2→conv16(5×5)→square→avgpool2→400→120(square)→64(square)→10이다. Table4의2FC는 두 은닉 affine층이며10출력 head는 따로 있다. 공통 모델seed5354592293955390513, Adam8epoch,batch64,beta0.9/0.999,epsilon1e−8,L2=1e−5,gradient cap5, lr는MLP0.001/LeNet0.0005, epoch마다×0.9, early_stopping=False다. 60,000 중 모델 학습55,000/검증5,000이고 공식test의 각클래스 hash순위0–49를 구성선택500,50–99를 별도500으로 둔다. 두 모델의 같은 영상 반복을 새 독립 영상으로 세지 않는다.

저장된 공식test10,000 평문 정확도는MLP97.76%,LeNet98.91%; balanced accuracy0.9774123089233575/0.9888295109137069,macroF1 0.9774991428126858/0.9889637861165234다. test의 클래스 수는[980,1135,1032,1010,982,892,958,1028,974,1009]이며 두 모델에 같다. 이10,000은 암호화 평가 수가 아니다. 각500 역할의 정답률은 실제 저장된 평문 logits와 해당 label을 이번에 다시 연결했다. epoch training_history의 온라인 정답률은 고정 최종모델의 training 재추론 정답률과 구분한다.

packed CNN-lite는 mean7×7 풀링, valid2×2 filter4, square,36개 출력의 선형 head다. 학습12,165,개발250,구성선택250,별도250. 모델seed5065504290027946322, Adam24epoch/batch64/lr0.01/beta0.9/0.999/epsilon1e−8/L2=0.0001,updates4584. 학습 정답12008/12165, 개발249/250, 선택245/250, 별도248/250이 기록돼 있다. 학습 score 최대값49.25859809230995의 역수0.020301024363828087로 정규화했다. 기존 모델 파일의 scalar adapter 범위 문구와 V17의 새 spatial packing adapter는 구분한다. 가중치는 같고 V17 실제 실행은 영상당16슬롯·11회전·8회전키다. 20개 영상의 시간 묶음을 유효 슬롯 수나 독립 키 수로 바꾸지 않는다.

주요68의 `MODEL_QUALITY_BY_ROLE.csv`는 136개 선택/별도 역할의 **저장 평문 출력 재집계**, 표형65 학습 역할의 **동결 모델·전처리만 사용한 평문 산술 복원**을 구분한다. 산술 구현은 같은 선택 입력의 원래 score와 최대 차이1e−10 미만인지65모델 전부 확인했다. 학습·평가 label의 일치, 분할 불중복, 클래스별 recall/혼동행렬과 balanced accuracy/macroF1도 포함한다. 정답률은 전체 입력, CKKS 수용 조건은 적용 입력으로 분모가 다르다. training manifest의 z>=0 품질 수치를 무조건 score>=0.5 결과로 대체하지 않았다.

### 주요68의 모델별 별도 입력 요약

'''+summary_table+r'''

각 행 시간 범위는 사례별 원시 시간 중앙값의 최솟값–최댓값이다. 서로 다른 데이터셋의 정확도 범위를 하나의 모델 일반화 정답률로 해석하지 않는다. 특히 2층 표형 MNIST 적용774/2500, WDBC159/569는 낮은 적용 범위를 드러낸다. 최저 WDBC 사례의 선택20/114,별도23/113도 `CASE_SCOPE_AND_QUALITY.csv`에 남겼다.

## 6. 분모, 추가63과 깊이5조건

| Role | Case–input pairs | Applicable | Boundary | Key-summed observations | Protected flips / error violations |
| --- | --- | --- | --- | --- | --- |
| Primary selection | 18,385 | 16,081 | 2,304 | 55,155 | 0 / 0 for final selections |
| Primary separate | 18,367 | 16,049 | 2,318 | 55,101 | 0 / 0 |

위 입력은 사례별 입력의 합이다. 같은 원자료 행이 서로 다른 모델/분할·역할에서 재등장한다. `INPUT_UNITS.csv`는 dataset/role 내부 고유 source ID 수를 별도로 제공하며 MNIST의 다른 export 간에도 무조건 독립으로 합하지 않는다. 키3반복과 슬롯 반복은 입력 수나 독립 표본 수를 늘리지 않는다. 경계 결과도 CSV에 보존하되 보호범위 실패와 합치지 않는다. 최종 PDF의 적용 범위를 전역 보장으로 넓히지 않는다.

`ADDITIONAL_63_CASES.csv`의30 body/head 조합+24표형seed+6다중클래스seed+3packedseed=63과 `DEPTH_5_CONDITIONS.csv`의5행은 별개다. run_status의204작업은 주요68+추가63+깊이5+시간68로 일치한다. `ADDITIONAL_63_QUALITY_BY_ROLE.csv`126행과 모델 metadata63행에 이 추가 사례의 저장 평문 정답률·클래스·선택/별도 범위를 별도로 채웠다. 주효과/주요68에 합하지 않았다. 깊이5는 별도 계산 그래프이며 학습된63모델 또는 independent-input audit5개로 바꾸지 않는다.

추가분석의 Banknote `mlp_square_poly3`, fold3/seed0에서는 별도274입력 중 입력1068의 key1만 오차 조건을 위반했다. 평문0.5196440056932156, CKKS0.508866189688053, threshold0.5; 오차0.010777816005162588 > 한계0.00982200284660778이나 둘 다 양성이다. `ADDITIONAL_ERROR_ONLY_CASE.json`이 원시 사건과 연결한다. 이는 충분조건 위반이며 충분조건 자체의 수학적 반례가 아니다. 이 결과를 보고 선택 구성을 변경하지 않았다.

## 7. 기존 비용 계측의 정확한 범위

동결 formal 측정:65표형은 입력별, MLP/LeNet/packed3은 고정20입력 batch invocation별이다. 각 방법 arm은 파라미터 호환 키 문맥을 새로 만들고 같은 블록 안에서 재사용한다. 3키×예비1회 제외×측정6회, 순서교대, 이상치 제거 없음. 실제 총23,454대응비는 입력당 비율23,400과 batch비54를 합한 관측 수이며 독립 표본 수는 아니다.

각 사례의 로그비 평균, 같은 데이터셋–모델 사례의 로그비 평균,16조합을 같은 비중으로 평균한 뒤 exp한 추정치1.000540931232697를 이번 raw에서 재확인했다. 95% CI [0.9999674747655278,1.0011217812090207]는 이미 검증된 기존16조합 bootstrap10,000회/seed20260824 결과를 재사용했다. 통계적 유의차 미검출은 동등성 또는 손해0의 증명이 아니다.

`COST_COMPONENTS_AND_SETUP.csv`136행은68×2arms의 실제 준비비, 인코딩/암호화, 동형연산, 복호화/디코딩, 기록된 adapter I/O, 총시간의 평균과 총시간 중앙값을 제공한다. 평균 분해를 사용해 중앙값끼리 더하는 오류를 피했고, 총시간에서 기록 성분을 뺀 차이는 특정 원인으로 임의 배정하지 않았다. network와 별도 gate 시간은 미측정이다. 로컬 adapter_io의0은 측정 기록의0이며 네트워크0이라는 뜻이 아니다.

예시 Banknote 선택 arm의 준비비는 키 문맥당 평균38.463877ms; 입력당 인코딩/암호화27.077922ms,동형연산25.255139ms,복호화/디코딩11.491638ms,총평균63.832042ms/중앙값63.564785ms다. 키 준비는 총 추론시간에 포함되지 않는다. LeNet은20입력 묶음 중앙값3,626,987.250ms로 실제 비용이 매우 크며, MLP-100은18,094.536ms, packed는2,321.761ms다. 원래 느린 구현의 절대 비용을 생략하거나20입력 batch를 단일 입력 시간으로 보고하지 않는다.

조정21의 최종/초기1.0045077568931444는 선택 단계 평균 추론시간의 사례별 비율 중앙값이다. formal paired CI와 다른 자료이며 후보 간 키·실행 시점이 다르다. 선택 전체 비용은 별도의 stage wall 기록을 사용한다. 공통66사례 direct13,754,260.638ms,finite167,825,454.593ms,합계비12.201706730010272; 사례별 비율 중앙값12.398599026421792,IQR[7.493242059725233,14.95910619899486]. 이 합계는 병렬화된 서비스 완료시간이 아니다.

65표형 direct 타이머는 합성부터 키/실행/조정/결과 쓰기까지 포함하고 입력 준비·contract 구성은 제외한다. packed direct는 plan 합성까지 타이머 밖이라는 차이가 있다. 두 frozen multiclass의 direct stage wall은 미기록이라 양쪽 공통66에서 제외했다. 합성 단독·훈련·전체 준비 비용을0으로 채우지 않았다. 역사적13.8441은 finite68/direct66의 분모 불일치 합계비이므로 주 비교로 쓰지 않는다. 해당 기존 주석 사본과 실제66집계가 함께 제공된다.

## 8. 후속 비교와 이번 원고 보강의 분리

`COMPARISON_EVIDENCE_SCOPE.csv`와 `CLAIM_STATUS_AND_GAPS_KO.md`는 원래 논문의 내부 제거/유한집합/외부 보조 결과와 이미 완료한 후속 비교를 분리한다. 후속 A/B/C와 HEDiff Bank를 다시 실행하지 않았다. A/B 무차이, Bank C 합성 스트레스 실패, 비용 증감의 혼재는 그대로 유지한다. 비용 감소로 판정 개선 미관측을 대체하지 않는다.

기존 원문 검토의 FHE-Agent2511.18653v1 §4.1/§4.3 활성화 고정 정정을 재사용했다. §5.3의 판본 내 불일치와 실제 구현 미확인은 유지한다. HECATE/FHE-Agent처럼 정확성을 선택 제약으로 쓰는 연구와 HEDiff처럼 판정 이탈을 검사하는 연구를 배제하지 않는다. 새 기능/미지원 여부를 추가로 단정하지 않아 이번 전수 문헌검색·설치·외부 호출은 필요하지 않았다.

C′ 정책과 C/C′/B30 계획은 이전 FOLLOWUP_SEPARATE에 확보 완료다. 이번에 다시 도입 경위를 탐색하거나 구현/활성화하지 않았다. logN 동일성이 실제 같은 비용이라는 보장은 없고, 미실행 Bank S33을 선택 결과로 쓰지 않는다. 예약684의 실제 행·label·score·margin은 읽지 않았다.

## 9. 재집계 명령과 파일 역할

이번 실제 실행 명령은 모두 `/home/ckks2/deciprotect`에서 수행한 아래 세 스크립트다. 각 파일은 Python 표준 라이브러리만 사용하고 CKKS/모델 학습 모듈을 import하지 않는다.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/analyze_journal_evidence_v1.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/collect_journal_evidence_details_v1.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/collect_journal_additional_quality_v1.py
```

기존 산출물에 같은 명령을 재실행하면 배타적 생성(`open x`)이 덮어쓰기를 거부한다. 재현 시에는 충돌하지 않는 새 폴더를 **먼저** 만들고 출력 경로를 지정한다. 예시 명령은 이번에 다시 실행하지 않았다.

```bash
cd /home/ckks2/deciprotect
export FG_EVIDENCE_DOC=/home/ckks2/deciprotect/docs/research/fg_journal_evidence_replay_run02
export FG_EVIDENCE_RUN=/home/ckks2/deciprotect/results/fg_journal_evidence_replay_run02
mkdir "$FG_EVIDENCE_DOC"
mkdir "$FG_EVIDENCE_RUN"
mkdir "$FG_EVIDENCE_DOC/evidence_tables" "$FG_EVIDENCE_DOC/source_excerpts"
PYTHONDONTWRITEBYTECODE=1 python3 scripts/analyze_journal_evidence_v1.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/collect_journal_evidence_details_v1.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/collect_journal_additional_quality_v1.py
```

생성 경로는 지정된 DeciProtect docs/research와 results 아래만 허용한다. 보충 ZIP은 보고서·전체626행 후보 명세·집계·필요 발췌와 검증 코드를 담고, 원래 대량 raw와 데이터셋 전체는 넣지 않는다. 따라서 ZIP만으로 CKKS 실험을 재실행할 수 있다고 하지 않는다. 위 집계 재현에는 manifest에 지정한 원래 로컬 raw/모델 파일이 필요하다. 상세 Q/P 소수 재생성이나 암호화 명령은 이번 실행 목록에 없다.

초기 분석은 다중 클래스 alias 조인 두 위치에서 중단됐으며 `ATTEMPT_01.json`과 `analysis_attempt_02/FAILURE.json`에 보존했다. 원시 파일이나 불리한 과학적 결과를 버린 것이 아니라 동일 frozen 사례 명칭을 연결한 집계 프로그램의 오류 수정이다. 최종 검증은 수정 후 전체 사례로 완료했다. 분석 후 출력 경로 환경변수만 추가했으며 산술·집계 규칙은 유지했다.
''')

comparison=[
 ['PDF-internal','§3.2·§5.3','동일 초기 합성에서 판정/오차 수용 검사 제거','초기20사례 flip+error,1사례 error only; 최종0/0','초기 합성 자체에는 마진 정보가 남음','내부 수용검사와 조정의 영향; 모든 수치 기준/외부방법 대비 우월성 아님','최종 PDF; 후보 direct89 명세'],
 ['PDF-finite','§3.2·§5.5','제안 초기 생성 규칙에 의존하는 유한집합537 실제 CKKS','89회로68사례 선택; finite477SAFE/60REJECTED; 최속 실행18사례 위반','67×8,LeNet1; literal/path65사례 동일 최속수용','고정 범위의 평가 효율과 선택 적합성; 전역최적 아님','CANDIDATE_SPECIFICATIONS.csv; CANDIDATE_ID_LITERAL_RECONCILIATION.csv'],
 ['PDF-EVA','§5.7','공식 EVA/SEAL 실제 S20 암호화','500입력×3키 중133flip,114고유 입력','선택용 입력의 지정S20 관측; 원래 최적화 선택 실패로 일반화 불가','외부 경로에서도 판정 관측의 필요; 모든 EVA 기준의 실패 아님','EXISTING_RELATED_WORK_CRITERIA_KO.md; PDF p10'],
 ['PDF-HEIR','§5.7','외부 설정/산출의 공통 Lattigo 이식','500입력×3키에서0flip/error,maxabs5.0791e-8','N14/S45; 공식 native NN 실행 아님; 시간주장 차단 보존','해당 다항식 이식 관측; 같은 실행 일정/속도우위 아님','EXISTING_RELATED_WORK_CRITERIA_KO.md; PDF p10'],
 ['Completed-EVA-native','후속 fg_expand_v2','공식 compiler/native SEAL S30/range20 대 독립 C','별도500/적용498에서 양쪽0flip/error; 경계EVA1/C2; EVA수치오차 더 작음','같은 출력 의미, backend/packing/security assessment 다름','실제 외부 비교 완료; 판정 개선 미관측, 선택조건만의 인과적 속도효과 불가','EXISTING_EXPANSION_EXTERNAL_EXCERPT.txt'],
 ['Completed-A-B','후속 fg_contrib_v1','독립 동일 후보 생성 A30/B30; 수용기준 비교','7모델×2선택블록14/14 동일; 판정 개선 미관측','표형4 주 maxabs 조건의 포함관계; MC/RMSE는 별도 해석','실행한 비교를 없는 것으로 보지 않음; 무차이 유지','EXISTING_CONTRIBUTION_REPORT_EXCERPT.txt'],
 ['Completed-B-C','후속 fg_contrib_v1','단순 판정선택 대 최종PDF 대응 C','C 후보 수 감소0/동일10/증가4; 선택비용 유리5모델/불리2; Fashionseed0 N14 증가','요구수치조건·적용범위 차이,2블록 탐색적 비용','비용 이득/손해 증거; 추가 판정 개선으로 대체 불가','EXISTING_CONTRIBUTION_REPORT_EXCERPT.txt'],
 ['Completed-HEDiff-Bank','후속 fg_contrib_v1','공식 Bank 절차/forward 실제 native + 공통 정확한2logit C 연결','native 이탈0; C 합성 적용영역 flip1/error6키 사건','공개절차 재학습; 원래 가중치/corpus 아님; native와C보안기준차이; 합성정답·고객타당성 미확정','외부 원래문제 해결 판단불가, C 불리한 관측 보존','EXISTING_EXTERNAL_DESIGN_KO.md; EXISTING_CONTRIBUTION_REPORT_EXCERPT.txt'],
 ['Existing-CoreLab','관련 자료','공식 연결 수치 실행','70/72계획,14000수치관측,2실패','같은 분류 출력 계약/가중치/입력 미확립','수치 실행 자산; 판정 선택 직접 비교로 세지 않음','EXISTING_RELATED_WORK_CRITERIA_KO.md'],
 ['Existing-literature','§2.4 보강자료','기존 원문·제한적 구현 확인','FHE-Agent 활성화 고정 정정; 정확성 제약을 쓰는 선행방법 존재','일부 전문/공식구현 미확인; 본문 부재≠구현 부재','정확성을 처음 고려했다는 주장 금지','EXISTING_FHE_AGENT_CORRECTION_KO.md; EXISTING_RELATED_WORK_CRITERIA_KO.md']]
headers=['evidence_group','paper_or_followup_location','implementation_level','observed_result','conditions_and_limits','supported_and_unsupported_use','source_in_bundle']
with (T/'COMPARISON_EVIDENCE_SCOPE.csv').open('x',newline='') as f:
    w=csv.writer(f);w.writerow(headers);w.writerows(comparison)

put('CLAIM_STATUS_AND_GAPS_KO.md',r'''
# 기존 증거 보강의 완료 항목과 남은 판단 v1

**최종 논문의 구성 선택 절차는 바꾸지 않고 설명·재현성 공백을 실제 값으로 채웠다.** 89/537회, 주요 68사례, 선택·별도 평가의 적용 입력 분모는 원시 기록과 일치했다. 과거 심사 점수는 재사용하지 않았고 PDF 한정 심사도 바꾸지 않았다. 이번 산출물은 원고 반영 검토용이며 PDF에 적용하지 않았다.

## 기존 방법 변경 없이 보완한 내용

| Claim / gap | Status | Evidence and manuscript action |
| --- | --- | --- |
| 초기 합성의 입력·연산 규칙 | 보강 완료 | Banknote 첫 적격 조정 사례의 예산·민감도·scale 18→백엔드 20→조정 24, Q/P/N, 실제 평가와 입력 226; P05 |
| 비교 537회의 범위·난이도 | 보강 완료, 의존성 명시 | 67×8+1; SAFE 477 / REJECTED 60; C 초기 마진 예산을 공유하는 생성기; 전체 626행 구성 명세; P04 |
| Table 7의 다른 선택 23사례 | 정의 보강 | ID 차이 23, 실제 파라미터·경로 차이 21, 명칭만 차이 2. 최속 수용 구성은 65/68에서 C와 같음; P11 |
| 최속 실행 기준 위반 18사례 | 보강 완료 | 18사례 모두 판정 변화와 오차 위반 관측, 오차만 위반한 사례 0. 사례 단위이며 개별 사건의 동일성은 아님 |
| 과제 정의·평문 품질·학습 분리 | 보강 완료 | 실제 이진 레이블 변환과 전처리 학습 범위. 주요 68의 역할별 품질 201행, 추가 63의 역할별 품질 126행; P08–09 |
| 주요 분모와 낮은 적용 범위 | 재확인 | 선택 18,385/16,081, 별도 18,367/16,049. WDBC의 20/114, 23/113 보존 |
| 추가 63과 깊이 5의 관계 | 문장 정정 필요 | 모델 63사례와 별도 그래프 5조건. Table 5에 별도 행 추가, §5.1에 분해 문장; P10 |
| 동기 예시·경계 제외·다중 클래스 | 문장 정정·명료화 | 서론 마진 0.0001은 δ 밖. 경계 판정 변화의 CKKS 원인 가능성을 부정하지 않음. top-two 영역과 모든 경쟁 클래스 검사 구분; P01–03, P07 |
| CI·절대시간·준비비 | 보강 완료 | CI는 1 포함. 136개 arm의 비용 분해와 66사례 선택시간. 조정 21사례의 관측비와 공식 대응 시간비 분리; P11 |
| 보안 검사 범위 | 범위 명료화 | 당시 소스 대응 및 선언·백엔드 유효성·기존 사후검사 구분. 주요 다중 클래스 2후보만 실제 소수 기록과 연결; P06 |

새 계산은 입력·모델·키 단위를 보존했다. 임곗값 고정과 전처리 학습을 구분한 P09는 실제 생성 코드에 따른 표현 정정이다. 원고의 주요 성과를 바꾼 새 실험 결과가 아니다.

## 기록 부재 또는 확인 범위가 제한된 부분

| Item | Precisely missing / limitation | Handling |
| --- | --- | --- |
| 정적 재시도 세부 | attempts=3/lift=2는 있으나 실패 시도별 실제 소수·오류 문자열 미기록 | 최초 S20과 원래 재시도 규칙까지만 설명; 새 생성 없음 |
| 미생성 후보 | LeNet 생성 1개는 확정. 정적 탈락 분기별 개별 로그 없음 | 보안 한도의 산술과 실제 후보 수 분리; 7건의 실제 실행 실패로 쓰지 않음 |
| 선형 모델 수렴 | 모델별 n_iter·warning 미저장 | max_iter=2000과 미확인 표시; 무경고·수렴 단정 금지 |
| 다중 클래스 최종모델의 학습 정답률 | epoch 중 온라인 지표와 최종모델의 학습집합 재평가는 다름 | 기존 검증·test·선택·별도 품질 사용; 학습 평가를 새로 실행하지 않음 |
| 단계별 전체 준비비 | 다중 클래스 2사례의 직접 선택 wall time 미기록. 합성 단독·네트워크·gate 비용 미분리 | 공통 66사례와 실제 arm 준비비만 보고; 결측을 0으로 채우지 않음 |
| 실제 소수 검사 범위 | 기존 4후보 중 주요 다중 클래스 2후보 연결. 주요 68 전부·Banknote 예시·후속 Bank의 모든 호출은 입증 못함 | 선언 검사와 사후 범위 분리. 함수 미호출만으로 보안 위반 단정 금지 |
| 외부 원문·구현 | CHET 전문 등 기존 접근 제한, FHE-Agent 실행 artifact 미확인 | 기존 원문 정정 재사용. 본문 부재와 구현 부재 구분 |

원시 모듈러스·수렴로그가 없다는 이유로 새 모델이나 CKKS를 실행하지 않았다. 현재 범위에서 확인한 자료 부재는 무한 archive 탐색으로 대체하지 않았다.

## 비교 기여의 현재 상태

원래 PDF의 비교는 내부 조건 제거, 동일 합성에 의존한 유한집합, EVA 지정 S20·HEIR 이식 보조 관측이다. 후속 A/B/C와 실제 EVA native, HEDiff Bank는 이미 완료돼 있다. 구체 결과와 구현 수준은 `evidence_tables/COMPARISON_EVIDENCE_SCOPE.csv`에 분리했다.

- A와 B: 주 비교 14/14블록의 선택이 같았고 추가 판정 개선은 미관측이다. 수치 기준의 포함 관계와 첫 후보 수용 등 원인은 완료된 원인 분석을 유지한다. 허용값을 바꿔 A를 실패시키지 않는다.
- B와 C: 후보 평가 횟수는 감소 0, 동일 10, 증가 4블록이다. 선택·추론 비용은 조건별 이득과 손해가 존재한다. Fashion seed0의 N 증가와 비용 손해를 보존한다. 이를 판정 개선의 부재 대신 성공으로 쓰지 않는다.
- 실제 외부 비교: 후속 EVA S30의 적용 영역에서는 양쪽 모두 판정 변화·오차 위반이 0이었다. 경계에서는 C 2키 사건, EVA 1키 사건이 있었고 EVA의 수치 오차가 더 작았다. HEDiff Bank에서는 native 판정 이탈 0, C의 합성 적용 영역 판정 변화 1·오차 위반 6키 사건이었다. 원래 가중치·발견 corpus 재현이 아니므로 기존 문제 해결 여부는 판단 불가다.
- 원래 내부 비교: 주요 68의 초기 실패 후 조정과 적용 영역 별도 입력의 0/0은 그 범위에서 유효한 관측이다. 초기 구성에 마진 정보가 남으므로 모든 선행 수치 기준 대비 효과를 입증한 것으로 해석하지 않는다.

일반화하는 새 원고에 후속 결과를 통합한다면 §5.7 뒤에 다음 범위 문장을 검토할 수 있다. **현재 PDF에는 미적용**이다.

> 후속 공통 후보 비교에서는 수치 오차 기준과 판정 관련 기준이 같은 구성을 선택하여 판정 개선이 관측되지 않은 조건도 있었다. 제안 절차의 비용 변화는 모델과 정밀도 요구에 따라 이득과 손해가 함께 나타났고, 외부 공통 모델의 합성 입력에서는 제안 구성도 적용 영역에서 판정이 달라졌다. 따라서 내부 초기 구성에 대한 조정 효과를 모든 수치 정확성 기준이나 외부 방법에 대한 우월성으로 확대하지 않는다.

이는 같은 방법의 확장 주장에 알려진 실패와 무차이를 함께 반영하기 위한 제한 초안이다. 후속 자료는 심사 당시 PDF에 없는 비교와 현재 저장소에서 이미 완료한 비교를 구별하는 근거다.

## 남은 결정과 실제 새 실험의 필요성

1. **현재 논문의 설명·출처·표 보강은 새 암호화 실험 없이 가능하다.** P01–P12를 저자가 검토해 반영할 수 있다. ID 차이 23·실제 구성 차이 21, 추가 63·별도 깊이 5, 고정 임곗값의 표현을 우선 정리한다.
2. **보안 사후검사의 범위나 소실된 과거 시간은 설명만으로 새 수행 사실이 되지 않는다.** 모든 구성의 실제 소수 검증을 주장하려면 소수 자료와 당시 검사 출력의 추가 연결이 필요하다. 일부 단독 시간은 별도 측정 없이는 복원할 수 없다. 최종 PDF의 현재 한정 주장을 유지한다면 새 전면 실험의 필수조건으로 만들 필요는 없다.
3. **C′가 B보다 추가 가치가 있는지는 미확인이다.** 검토용 변형과 C/C′/B30 계획은 이미 확보됐지만 실행되지 않았다. 이 추가 주장을 선택할 때만 사전 고정 후 별도 CKKS 검증이 필요하다. 이번 자료 보강이나 이미 끝난 A/B/C의 반복으로 답했다고 하지 않는다. 예약 684 사용·Bank 사분위 선택·C′ 활성화는 시작하지 않는다.

현재 결론은 **기존 방법 변경 없이 평가 설명·재현성은 상당 부분 보완했고, 독립 수치 기준·단순 B 대비 추가 판정 기여와 미실행 변형의 추가 가치는 확인되지 않았다**는 것이다. 긍정·동일·불리·판단 불가를 구분한다. 본 묶음의 ZIP 검증 후 종료한다.
''')
print('DOCUMENTS_WRITTEN',flush=True)
