#!/usr/bin/env python3
"""Generate current direction without altering completed research evidence."""
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SYNC=ROOT/'docs/project_sync'
EXP=ROOT/'docs/research/fg_expand_v1_20260905'


def main():
    if (ROOT/"docs/research/fg_cause_v1_20260906/ANALYSIS.json").exists():
        from build_handoff_cause_v1 import main as build_cause
        build_cause()
        return
    if (ROOT/'protocols/FG_CONTRIB_V1.json').exists():
        from build_handoff_contrib_v1 import main as build_contrib
        build_contrib()
        return
    if (ROOT/'protocols/FG_EXPAND_V2_MAIN.json').exists():
        from build_handoff_v2 import main as build_v2
        build_v2()
        return
    state_path=SYNC/'RESEARCH_STATE.json'
    old=json.loads(state_path.read_text()) if state_path.exists() else {}
    history=old.get('historical_protocol_results') or {k:old[k] for k in ['pilot_v1a_completed_cases','pilot_v1_static_failures_preserved','synthetic_stress_cases','gap_diagnostic_cases','gap_diagnostic_added_acceptances','iid_audit','dp03_cost_diagnostic','journal_review_score','thesis_extension_readiness_score','verification'] if k in old}
    summary_path=EXP/'summary.json'
    summary=json.loads(summary_path.read_text()) if summary_path.exists() else None
    complete=bool(summary and summary['completed_cases']==summary['planned_cases'])
    status='FIRST_EXPANSION_COMPLETED_EXPLORATORY' if complete else 'FIRST_EXPANSION_IN_PROGRESS'
    state=dict(project='DeciProtect',research_purpose='Expansion of final journal PDF offline decision-agreement CKKS configuration selection',updated_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),predecessor='/home/ckks2/flipguard',new_repository='https://github.com/hasslelee/deciprotect',visibility='private',freeze=json.loads((ROOT/'baseline/FREEZE_MANIFEST.json').read_text()),current_protocol_id='FG_EXPAND_V1_20260905',current_run_id='fg_expand_v1_20260905_run01',status=status,active_experiments=[] if complete else ['FG_EXPAND_V1_20260905 four prespecified cases only'],automatic_followup_enabled=False,next_scope='Proposed only: Fashion-MNIST existing square MLP100 across three training seeds; support and bounded budget must be fixed in a new protocol; no automatic execution',excluded_from_current_default=['DP-03 queue/recomputation followup','runtime abstention optimization','new operational risk guarantee'],historical_protocol_results=history,open_claims=['generalization beyond applicable observed inputs','robustness to splits and training seeds on new data','larger multiclass/image evaluation','independent hardware'],report='docs/research/fg_expand_v1_20260905/REPORT_KO.md',pdf_wording_issue='Page7 section5.1: raw 63 additional model cases and 5 separate depth conditions; no manuscript correction applied')
    if summary:
        state['first_expansion']={k:summary[k] for k in ['completed_cases','planned_cases','recorded_candidate_key_observations','recorded_timing_key_pass_observations','unique_inputs_by_role','latency_aggregates']}
    state_path.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n')
    handoff=f'''# 기존 판정 일치 기반 구성 선택 연구 인계

최신 사용자 결정은 최종 검수한 논문지 PDF의 방법을 확대 검증하는 것이다.
DeciProtect는 작업 폴더·저장소 이름이다. 재계산 queue·유보 정책·새 위험 보장을
현재 연구의 핵심이나 선행 과제로 삼지 않는다. 완료한 과거 결과는 보존한다.

- 작업: `/home/ckks2/deciprotect`; 원본 FlipGuard 코드/인터프리터 실행 금지.
- GitHub: https://github.com/hasslelee/deciprotect (private).
- 기준: `baseline/journal_final_20260905.pdf`, SHA-256
  `0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85`.
  사용자 Downloads 지정·기존 복사 기록·동결 manifest와 연결하여 확인했다.
- 상태: **{status}**. Protocol `FG_EXPAND_V1_20260905`, run `fg_expand_v1_20260905_run01`.
- 자동 후속 실행은 꺼져 있다. 종료 후 새 대규모 실험을 시작하지 않는다.

방법은 입력별 판정·오차 조건을 이용한 오프라인 구성 선택이다.
rho=.5, delta=.001, 최대4후보, 기존 조정·128bit Q/QP 보안 정책을 유지한다.
선택자는 평문 기준 점수를 읽는다. 운영 중 oracle gate로 혼동하지 않는다.
구성 선택·유한 탐색·키 준비와 PDF 정의의 추론 비용을 분리한다.

첫 묶음: Spambase/HTRU2 × 기존 다항식/MLP4 네 사례, 사례마다 선택32·별도256입력·
3개 새 키. 같은 데이터의 두 모델은 같은 입력이므로 별도1,024 사례–입력 쌍과
고유512입력을 구분한다. Spambase는 노출된 자료이며 확증 실험으로 표현하지 않는다.

기존 자산: 주요68 + 추가모델63 + 별도 깊이5조건. 다중 클래스·CNN·학습 seed 반복은
이미 있다. PDF7쪽 §5.1의 63개 표현과 원시 분류 차이는 별도 보고했으며 PDF나 동결
표를 수정하지 않았다. 기존 68개 결과를 덮어쓰지 않는다.

먼저 읽을 자료:

- `docs/research/fg_expand_v1_20260905/PDF_METHOD_MAP_KO.md`
- `docs/research/fg_expand_v1_20260905/LEGACY_ASSETS_KO.md`, `LEGACY_CASES.csv`
- `docs/research/fg_expand_v1_20260905/RELATED_WORK_KO.md`
- `docs/research/fg_expand_v1_20260905/DECISIONS_AND_MATRIX_KO.md`
- `docs/research/fg_expand_v1_20260905/REPORT_KO.md` (완료 시 최종 결과)
- `docs/research/THESIS_ROADMAP.md`

과거 DP 파일럿·IID600회·gap·stress·DP-03는 해당 protocol의 역사적 결과다.
위험 상한이나 비용 정의를 이전하지 않는다. 당시 모의심사 점수는 과거 기록이며
현재 점수를 올리거나 졸업논문 완성을 선언하지 않았다.

보존: baseline·archive·원본·완료 evidence 불변, archive 업로드/전수 재해시 금지.
새 protocol/run ID 사용. 불리한 결과·실행 실패·제외 입력 유지. 제출 PDF 수정이나
삭제된 수식/의사코드/용어 자동 복원 없음. 기존 archive 복구 경위는
`docs/review/SOURCE_STATE_RESOLUTION.json`에 보존되어 있으며 이번에 반복하지 않았다.
'''
    if summary:
        lines=[]
        for c in summary['cases']:
            if c['status']!='COMPLETED':lines.append(f"- {c['case_id']}: {c['status']}");continue
            a=c['audit_roles'].get('direct',{})
            lines.append(f"- {c['case_id']}: 선택 {c['direct_trials']} / 유한 {c['finite_trials']}, 별도 적용 {a.get('eligible')}/{a.get('inputs')}, 판정 변화 {a.get('protected_flip_events')}, 오차 위반 {a.get('protected_error_violations')}, 경계 판정 변화 {a.get('boundary_flip_events')}; 선택 비용 {c['selection_cost_ms']['direct_selection_total_ms']/1000:.3f}s.")
        handoff+='\n## 첫 묶음의 실제 결과\n\n'+'\n'.join(lines)+'\n\n원시 점수로 재계산: `.venv/bin/python scripts/analyze_fg_expand_v1.py --check`.\n'
    for name in ['CHATGPT_HANDOFF.md','CODEX_HANDOFF.md']:(SYNC/name).write_text(handoff)
    (SYNC/'OPEN_ISSUES.md').write_text('''# Current open issues

1. New data need more split/training-seed and separate-input evidence. First four-case slice is exploratory.
2. Report applicable coverage with every pass count; never retune delta or model scaling from audit failures.
3. Separate selection, inference and setup costs. CI including one does not establish equivalence.
4. PDF p7 section5.1: 63 additional model cases and 5 depth conditions are separate in raw inventory. Wording proposal only.
5. CHET publication metadata verified; publication PDF unavailable. Earlier arXiv text is a different version.
6. Related compilers also evaluate error/accuracy. Do not claim prior work universally ignored decisions.
7. One VM is one environment. Old DP risk/queue questions are historical, not automatic next tasks.
8. Archive remains local; original and completed artifacts untouched. No automatic follow-up experiment.
''')
    log=SYNC/'SYNC_CHANGELOG.md';text=log.read_text() if log.exists() else '# Sync changelog\n'
    marker='FG_EXPAND_V1 latest user direction'
    if marker not in text:
        text+='\n2026-09-05 '+marker+': Restored final PDF offline configuration-selection objective; preserved historical DP results; added PDF provenance/method map, model/depth inventory, primary literature review, fixed four-case expansion and separate selection/inference cost evidence. No queue follow-up or manuscript overwrite.\n';log.write_text(text)
    files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SYNC.glob('*')) if p.is_file() and p.name!='SHA256SUMS'}
    (SYNC/'SHA256SUMS').write_text(''.join(f'{v}  {k}\n' for k,v in files.items()))
    print(status)


if __name__=='__main__':main()
