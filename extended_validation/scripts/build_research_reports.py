#!/usr/bin/env python3
import csv
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from deciprotect.risk import required_zero_failure_units


def read(p):return json.loads(p.read_text())
def write_table(p,rows):
    with p.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    report=ROOT/'docs/research';fig=report/'figures';fig.mkdir(exist_ok=True)
    cases=[read(p) for p in sorted((ROOT/'results/dp_pilot_v1a_20260905').glob('*/summary.json'))]
    rows=[]
    for v in cases:
        for arm in sorted({m['arm'] for m in v['metrics']}):
            ms=[m for m in v['metrics'] if m['arm']==arm]
            rows.append({'case_id':v['case_id'],'dataset':v['dataset'],'model':v['model'],'seed':v['seed'],'arm':arm,
                         'case_inputs':ms[0]['inputs'],'key_observations':sum(m['inputs'] for m in ms),'accepted_key_observations':sum(m['accepted'] for m in ms),
                         'mean_coverage':np.mean([m['coverage'] for m in ms]),'flip_key_events':sum(m['accepted_disagreements'] for m in ms),
                         'plaintext_accuracy':ms[0]['plaintext_accuracy'],'mean_batch_ms':np.mean([m['measured_batch_total_ms'] for m in ms])})
    write_table(report/'PILOT_TABLE.csv',rows)
    stress=[]
    for p in sorted((ROOT/'results/dp_stress_v1_20260905').glob('*/summary.json')):
        v=read(p);ms=v['metrics'];stress.append({'case_id':v['case_id'],'case_inputs':ms[0]['inputs'],'key_observations':sum(m['inputs'] for m in ms),
              'fixed_low_flip_events':sum(m['fixed_low_flips'] for m in ms),'fixed_high_flip_events':sum(m['fixed_high_flips'] for m in ms),
              'cascade_flip_events':sum(m['cascade_flips'] for m in ms),'cascade_accepted_observations':sum(m['cascade_accepted'] for m in ms),
              'cascade_coverage':sum(m['cascade_accepted'] for m in ms)/sum(m['inputs'] for m in ms)})
    write_table(report/'STRESS_TABLE.csv',stress)
    sample=[{'target_risk':risk,'hypotheses':m,'family_confidence':.95,'independent_zero_failure_units':required_zero_failure_units(risk,hypotheses=m)} for risk in [.01,.001,.0001] for m in [1,2,12,68]]
    write_table(report/'SAMPLE_COMPLEXITY.csv',sample)
    iid=read(ROOT/'results/dp_iid_audit_v1_20260905/summary.json');events=[json.loads(l) for l in (ROOT/'results/dp_iid_audit_v1_20260905/observations.jsonl').read_text().splitlines()]
    correction=sum(e['low_decision']!=e['reference'] and e['returned_decision']==e['reference'] for e in events)
    low_wrong_abstained=sum(e['low_decision']!=e['reference'] and e['returned_decision']<0 for e in events)
    lines=['# DeciProtect 초기 실행 결과','',
      '이 보고서는 기존 논문을 바꾸지 않는 새 연구의 첫 checkpoint다. 아래 파일럿, 합성 스트레스, 독립 위험 감사는 서로 다른 실험이며 한 성공률로 합치지 않는다.','',
      '## 신규 자료와 모델','',
      '공식 UCI 자료를 사용했다. Spambase 원본 4,601행은 특징 중복·상충 레이블 처리 후 4,204행이다. 학습/개발/보정/평가는 seed별 2,102/630/630/842행이다. Wine은 178행이며 89/26/27/36행이다. 세 seed의 분할은 서로 겹칠 수 있으므로 독립된 새 데이터셋 세 개로 세지 않는다.',
      '', '선형 logistic 분류기와 hidden 12의 square MLP를 각각 학습했다. square MLP의 200회 L-BFGS-B는 여섯 사례 모두 수렴 조건에 도달하지 못했다. 결과를 삭제하지 않았으며, 완전히 수렴한 최종 모델이라고 표현하지 않는다. 평문 accuracy는 아래 표와 raw 결과에 기록했다.',
      '', '## 정규 입력 파일럿', '', '| Dataset / model | Cases | Mean returned fraction | Returned flip events | Low / high timing interpretation |','|---|---:|---:|---:|---|']
    for ds in ['spambase','wine']:
        for model in ['logistic_linear','square_mlp12']:
            group=[r for r in rows if r['dataset']==ds and r['model']==model and r['arm']=='two_stage_envelope']
            lines.append(f'| {ds} / {model} | {len(group)} | {np.mean([r["mean_coverage"] for r in group]):.4f} | {sum(r["flip_key_events"] for r in group)} | Descriptive shared-VM measurements |')
    lines += ['', 'Spambase의 고정 저정밀도 선형 모델에서는 총 3회의 판정 반전이 관측됐고, 두 단계 방식은 842입력×6모델-seed 사례의 모든 입력을 세 키 실행에서 반환하면서 반전 0회를 보였다. 이는 5,052개의 독립 원자료가 아니라 5,052개 사례-입력 쌍이며, 반복 키를 포함하면 15,156개 관측이다. 고정 30비트 대조군도 이 자료에서 반전이 없었다.',
      '', 'Wine은 보정 입력 27개로 97.5% order statistic의 요구 순위 28을 만족하지 못해 구간을 무한대로 두고 모두 유보했다. 반전 0회를 성공으로 계산하지 않는다. 입력을 숨기거나 alpha를 완화해서 결과를 개선하지 않았다.',
      '', '초기 DP_PILOT_V1의 18비트 square MLP 여섯 사례는 logN=13에서 필요한 18비트 소수 3개를 만들지 못해 암호화 전에 실패했다. 그 기록을 보존했다. V1A에서는 암호화 결과와 무관한 생성 제약에 따라 MLP의 낮은 scale을 22로 정했다. 선형 모델의 재실행은 새로운 독립 과학적 증거로 합산하지 않는다.',
      '', '## 비용상의 음성 결과','',
      '재계산 대상 입력이 적어도, 현재 feature-ciphertext 배치 실행의 비용은 입력 수에 비례해 줄지 않았다. Spambase 선형 세 사례의 평균 배치 시간은 두 단계 방식 약 297–305ms, 고정 30비트 약 201–211ms였다. MLP는 양쪽 logN이 같아 낮은 scale의 이점도 작았다. 따라서 현재 naive cascade의 일반적인 속도 우월성 가설은 지지되지 않는다. 시간은 archive 작업과 공유 VM에서 수집한 기술적 수치이며 정식 성능 검정이 아니다.',
      '', '## 경계와 분포 이동 스트레스','', '| Case | Inputs | Low flips / key observations | High flips | Cascade flips | Cascade coverage |','|---|---:|---:|---:|---:|---:|']
    for s in stress:
        lines.append(f'| {s["case_id"].replace("spambase__","")} | {s["case_inputs"]} | {s["fixed_low_flip_events"]}/{s["key_observations"]} | {s["fixed_high_flip_events"]} | {s["cascade_flip_events"]} | {s["cascade_coverage"]:.4f} |')
    lines += ['', '합성 경계 입력에는 정답 레이블이 없다. 표는 고정된 평문 모델과의 일치만 뜻한다. 선형 모델 경계 스트레스에서 반환된 판정에도 3회의 오류가 존재한다. 표본 기반 오차 구간은 전역적인 결정 보존 certificate가 아니다. 이 결과를 이용한 보정값 재조정은 하지 않았다.',
      '', '## 독립 입력·키 600회 감사','',
      f'대상 모집단은 정규 입력 842행과 합성 경계 224행, 이동 입력 256행으로 미리 고정한 1,322행의 균등 분포다. 여기서 복원 추출한 입력과 새로운 키·암호화 난수를 매회 사용했다. {iid["trials"]}회 중 {iid["accepted"]}회 반환, {iid["abstained"]}회 유보, 반환 판정 오류 {iid["accepted_disagreements"]}회였다. 관측 반환율은 {iid["coverage"]:.1%}다.',
      '', f'같은 {iid["trials"]}회에서 고정 저정밀도는 {iid["fixed_low_disagreements"]}회 판정이 달랐다. 이 중 {correction}회는 고정밀도 재계산 후 올바른 기준 판정으로 반환했고, {low_wrong_abstained}회는 유보했다.',
      '', f'두 주장에 Bonferroni 보정한 가족 신뢰수준 95%에서 joint 위험의 단측 상한은 {iid["joint_risk"]["upper_bound"]:.8f}, 반환 조건부 위험의 상한은 {iid["selective_risk"]["upper_bound"]:.8f}이다. 둘 다 사전 목표 0.01을 통과했다. 시행 600개에서 뽑힌 고유 모집단 index는 {iid["unique_population_indices_drawn"]}개이며, 중복 추출은 이 유한 모집단 확률 실험의 일부다.',
      '', '**허용 주장:** 고정한 유한 모집단·모델·단일입력 실행·키 분포에서 두 위험 목표에 대한 감사가 통과했다. **허용하지 않는 주장:** 새로운 실제 스팸 분포에서 1% 보장, 모든 입력 무반전, packed batch에서 같은 보장, 암호학적 안전성 또는 정답 정확도 보장.',
      '', '## 결과로 정해진 다음 연구','',
      '위험 제어와 유보 규칙의 실증은 시작됐지만 비용 이점은 미해결이다. 다음 단계는 같은 모델·키 영역에서의 재계산 batching과 queue 비용, 충분한 새 calibration 자료, 시간/도메인 이동, 강한 대조군과 독립 환경이다. 이는 새 protocol에서 수행하며 현재 결과를 덮어쓰지 않는다.',
      '', '표 원본: PILOT_TABLE.csv, STRESS_TABLE.csv, SAMPLE_COMPLEXITY.csv. 검증: VERIFICATION.json. 프로토콜과 raw 결과는 각각 protocols/와 results/에 있다.']
    (report/'INITIAL_RESULTS.md').write_text('\n'.join(lines)+'\n')
    # Exportable plots: keep dependent observations descriptive, without invalid CIs.
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    f,ax=plt.subplots(1,2,figsize=(10,3.8))
    types=['Spambase\nlinear','Spambase\nsquare MLP','Wine\nlinear','Wine\nsquare MLP'];pairs=[('spambase','logistic_linear'),('spambase','square_mlp12'),('wine','logistic_linear'),('wine','square_mlp12')]
    for arm,offset,color in [('low_envelope_abstain',-.18,'#4c78a8'),('two_stage_envelope',.18,'#59a14f')]:
        vals=[np.mean([r['mean_coverage'] for r in rows if (r['dataset'],r['model'])==pair and r['arm']==arm]) for pair in pairs]
        label={'low_envelope_abstain':'Low stage with abstention','two_stage_envelope':'Two-stage policy'}[arm]
        ax[0].bar(np.arange(4)+offset,vals,.36,label=label,color=color)
    ax[0].set_xticks(range(4),types);ax[0].set_ylabel('Returned fraction');ax[0].set_ylim(0,1.08);ax[0].legend(fontsize=7);ax[0].set_title('Pilot coverage (no population guarantee)')
    for i in [2,3]:ax[0].text(i,.035,'0%\ninsufficient\ncalibration',ha='center',fontsize=8)
    ns=np.arange(1,10001);ax[1].plot(ns,1-.025**(1/ns));ax[1].axhline(.01,color='#e15759',linestyle='--',label='1% target');ax[1].set_xscale('log');ax[1].set_yscale('log');ax[1].set_xlabel('Independent zero-failure trials');ax[1].set_ylabel('One-sided risk upper bound');ax[1].set_title('97.5% one-sided binomial bound');ax[1].legend()
    f.tight_layout()
    for ext in ['svg','pdf','png']:f.savefig(fig/f'coverage_and_evidence.{ext}',dpi=180)
    plt.close(f)
    f,ax=plt.subplots(figsize=(6.5,4));p=np.linspace(0,.05,300)
    for batch in [1,16,128,512]:ax.plot(p,1-(1-p)**batch,label=f'batch={batch}')
    ax.set_xlabel('Per-request retry probability (independence model)');ax.set_ylabel('Probability of paying a full fallback batch');ax.legend();f.tight_layout()
    for ext in ['svg','pdf','png']:f.savefig(fig/f'batch_retry_cost.{ext}',dpi=180)
    plt.close(f)
    print('Reports and figures generated')


if __name__=='__main__':main()
