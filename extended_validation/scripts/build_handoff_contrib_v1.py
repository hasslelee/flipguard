#!/usr/bin/env python3
"""Update only the current sync; previous current sync is preserved in history."""
import datetime,hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];SYNC=ROOT/'docs/project_sync';DOC=ROOT/'docs/research/fg_contrib_v1_20260906';RUN=ROOT/'results/fg_contrib_v1_20260906_run01'
def read(p):return json.loads(p.read_text())
def main():
 old=read(SYNC/'RESEARCH_STATE.json');summary=read(DOC/'SUMMARY.json') if (DOC/'SUMMARY.json').exists() else None
 status=summary['status'] if summary else 'CONTRIBUTION_VALIDATION_RUNNING'
 phases={name:(RUN/f'{name.upper()}_PHASE_COMPLETED.json').exists() for name in ['preflight','select','diagnostic','audit','timing']}
 nselection=len(list((RUN/'cases').glob('*/selection/block_*/*/result.json')))
 state={**old,'updated_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'current_protocol_id':'FG_CONTRIB_V1_20260906','current_run_id':RUN.name,'status':status,'active_experiments':[] if summary else ['explicitly approved finite seven-model A/B/C comparison, one HEDiff case, bounded common stress'],'automatic_followup_enabled':False,'next_scope':'After this explicitly authorized bundle, stop. No new dataset/model/method experiment without a new user direction.','report':str((DOC/'REPORT_KO.md' if summary else DOC/'METHOD_AND_SCOPE_KO.md').relative_to(ROOT)),'research_question':'A versus B: numerical versus decision acceptance; B versus C: additional value of unchanged PDF synthesis and bounded repair','contribution_validation':dict(summary=summary,selection_completed=nselection,selection_planned=70,internal_phase_markers=phases,external='results/fg_contrib_v1_20260906_run01/external/hediff_bank/EXTERNAL_PROTOCOL_EXACT_LOGITS.json',source='research/contribution_validation',external_source='research/hediff_bank_validation',approval='Latest user explicitly authorized implementation and execution of finite attached contribution-validation directive; do not request per-model/seed approval')}
 (SYNC/'RESEARCH_STATE.json').write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n')
 text=f'''# CKKS 기여 검증 실행 인계

상태: **{status}**. 작업 위치는 `/home/ckks2/deciprotect`이다.
사용자가 첨부 기여 검증 지시문의 구현·실제 CKKS·분석을 명시적으로 승인했다.
이전 자동 후속 금지는 승인된 이번 묶음을 막지 않는다. 이번 묶음 이후 새 연구로 자동 확장하지 않는다.
원본 FlipGuard 코드·인터프리터 실행, baseline/archive/PDF/완료 결과 변경, archive 전송은 금지한다.

기준 PDF: `baseline/journal_final_20260905.pdf`, SHA-256
`0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85`.
시작 HEAD: `b4950499987e06a08075b4a8413ef216e9ab3471`, clean 확인.
Protocol `FG_CONTRIB_V1_20260906`, run `{RUN.name}`.
방법은 최종 PDF의 오프라인 구성 선택이다. DP 재계산·유보·큐·새 위험 보장으로 전환하지 않는다.

A/B는 독립 그래프·출력 범위 기반 생성기, 시작 scale30/40, 매 제안+4를 공유한다.
A는 개발 FP16 최대오차 기준, B는 C와 같은 판정·입력별 오차 조건을 사용한다.
C의 초기 합성·보안·수용·조정·4후보 상한은 유지한다. B의 수용 검사에서 마진 사용은 의도된 설계다.
7개 기존 모델, 2개 선택 블록, 후보당3새키, 최대4후보. 실제 선택 {nselection}/70.
전 선택 고정 뒤 scale7개×7모델 진단, 선택된 파라미터별 별도256/10000입력 감사,
20입력·예열1·측정6·키3 대응 시간, 평문 공통 스트레스16입력×20단계 순서이다.
기존 Spambase 정확한 S32Q8N14와 S24Q7N13의 새 감사·대응 시간도 포함한다.

허용값·후보·입력은 감사 결과로 조정하지 않는다. 표형4모델 주 수치 허용값은 rho*delta보다
작아서 적용 영역 오차 조건을 논리적으로 포함한다. A/B 무차이를 제안 기법의 승리로 해석하지 않는다.
슬롯·키·시간 반복은 독립 환경 수가 아니다. 이미 노출된 시험 입력은 새 독립 확증이 아니다.
수치오차·판정불일치·보수적 오차조건 위반·모델 정답률·실행 실패를 구분한다.

외부는 HEDiff Bank 공개 절차 단일 재학습(원래 가중치 미공개)이다. 공식 TenSEAL 원래 설정과
두 logit을 유지하는 별도 Lattigo 연결을 구분한다. t²+t=(t+.5)²−.25 항등식으로 기존 제곱 연산을
재사용하고 logit을 스칼라 점수로 변환하지 않는다. 원래float32·공통float64·CKKS 차이는 별도다.
원래 QP218은 우리 V2 N13 한도214와 달라 동일 보안 정책이나 cross-backend 인과적 시간 비교를 하지 않는다.
외부 연결3회/1200초, 외부 훈련·native7200초; 기록된 전체 실행 명령 wall 합계43200초 상한.
연결·준비·훈련을 순수 동형연산 시간으로 부르지 않는다. 새 compiler/bootstrap 개발은 없다.

먼저 읽기:
- `docs/research/fg_contrib_v1_20260906/METHOD_AND_SCOPE_KO.md`
- `protocols/FG_CONTRIB_V1.json`
- `results/fg_contrib_v1_20260906_run01/SOURCE_LOCK.json`, `INPUT_BINDINGS.json`, `FROZEN_SELECTIONS.json`(생성 후)
- `results/fg_contrib_v1_20260906_run01/internal.log`와 `commands/*.start.json`/`*.end.json`
- `results/fg_contrib_v1_20260906_run01/external/hediff_bank/EXTERNAL_PROTOCOL_EXACT_LOGITS.json`
- `docs/research/fg_contrib_v1_20260906/REPORT_KO.md`(완료 후)

실행 중이면 기존 native 프로세스와 `work/fg_contrib_v1_20260906/native.lock`을 먼저 확인한다.
완료 결과를 재실행하지 않는다. 내부 driver는 선택→진단→감사→시간을 직렬 실행하며
외부 driver는 같은 lease를 기다린다. 실제 실행 명령과 단계 로그는 commands에 있다.
읽기 전용 재집계: `PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/analyze_fg_contrib_v1.py`.
외부 재집계: 동일 환경에서 `scripts/analyze_external_contrib_v1.py`.
`--write`는 새 최종 파생 산출물을 쓰므로 완료 후 무작정 반복하지 않는다.

과거 201→0, Fashion 무차이, EVA native의 경계 결과, FHE-Agent 정정은 이전 보고서에 보존한다.
이전 현재 인계는 `docs/research/fg_contrib_v1_20260906/history/`에 보존했다.
검증 통과를 성능 개선·위험 보장·국제 경쟁력 점수로 표현하지 않는다.
'''
 if summary:
  text+='\n이번 유한 실행 묶음은 종료했다. 자동으로 새 실험을 시작하거나 완료 산출물을 재실행하지 않는다.\n\n'
  for item in summary.get('judgments',[]):text+=f"- {item['question']}: **{item['status']}**. {item['scope']}\n"
  text+='\n최종 수치·반대 증거·다음 최소 제안은 `docs/research/fg_contrib_v1_20260906/SUMMARY.json`과 `REPORT_KO.md`를 따른다. 다음 제안은 실행 승인이 아니며 자동 구현하지 않는다.\n'
 for name in ['CHATGPT_HANDOFF.md','CODEX_HANDOFF.md']:(SYNC/name).write_text(text)
 (SYNC/'OPEN_ISSUES.md').write_text('''# Current evidence limits

1. A/B now have independent candidate generation. Main FP16 tolerances remain representative engineering criteria, not a named prior-method reproduction or proof of application adequacy.
2. In four tabular models the main numerical tolerance already implies the application-domain margin condition. Separate logical inclusion, actual same outcomes and observed differences.
3. A-B acceptance effects and B-C procedure effects must be judged separately. Selection count, selection wall cost and chosen-configuration inference cost are different outcomes.
4. Seven existing trained models, two selection key blocks and one VM do not establish independent-environment generalization. Previously exposed audit inputs and repeated keys/slots give no new risk guarantee.
5. HEDiff original weights/corpus are unavailable. Public-procedure retraining and original native settings are distinct from the exact two-logit common-backend adapter. Original SEAL admission and frozen V2 QP policy are not identical.
6. Stress is a fixed common plaintext-only coordinate-box diagnostic. Synthetic truth and joint real-world feature validity are not established. Empty application scope is not successful protection.
7. Preserve previous EVA outcomes, FHE-Agent correction and frozen PDF wording issues. No retrospective retuning or automatic compiler/bootstrap/model/data extension.
8. Inspect raw command failures and remaining jobs before claiming completion; copied legacy metadata labels are superseded by this protocol and frozen job bindings.
''')
 (SYNC/'PROJECT_SYNC_INDEX.md').write_text('''# Current project sync

Precedence: latest explicit user authorization and preservation; verified final journal PDF; immutable protocols/raw results and bound execution source; independently reconstructed reports; earlier suggestions.

Current work is FG_CONTRIB_V1: explicitly authorized finite seven-model A/B/C comparison, independent A/B candidate generation, unchanged final-PDF C, one HEDiff external case, and bounded common plaintext-only stress. Read CHATGPT_HANDOFF.md, RESEARCH_STATE.json and docs/research/fg_contrib_v1_20260906/METHOD_AND_SCOPE_KO.md. No repeated per-model approval is required. After this bundle, no automatic expansion.

A/B generation may not inherit C margins, budgets or scale floors. B intentionally uses margins in acceptance. A-B acceptance effects and B-C procedure effects are distinct. Numerical conditions, disagreement, conservative error violations, application coverage and cost are separate. Preserve no-difference and adverse outcomes.

Never execute in /home/ckks2/flipguard or alter baseline/archive/finalPDF/completed evidence. No archive upload or full rehash. No audit retuning, no independent-sample claims from key repeats or slots. Current offline plaintext references do not imply a runtime oracle gate. Historical DP queue/risk results and prior V1/V2 expansion results remain separate. Update this current sync and regenerate handoff at completion.
''')
 log=SYNC/'SYNC_CHANGELOG.md';body=log.read_text();marker='FG_CONTRIB_V1 explicit execution approval'
 if marker not in body:log.write_text(body+'\n2026-09-06 '+marker+': independent A/B implementation and finite native seven-model comparison; unchanged C, bounded exact-logit HEDiff connection and common stress. Previous current sync preserved in contribution history.\n')
 if summary:
  finished='FG_CONTRIB_V1 finite bundle completed';body=log.read_text()
  if finished not in body:log.write_text(body+'\n2026-09-06 '+finished+': actual seven-model A/B/C selections, full selected-configuration audits, paired timing, official HEDiff public-procedure Bank execution and common stress independently reconstructed. Preserve A/B no-change, mixed C costs and external C stress failure. See REPORT_KO.md and SUMMARY.json. No automatic follow-up.\n')
 files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SYNC.iterdir()) if p.is_file() and p.name!='SHA256SUMS'}
 (SYNC/'SHA256SUMS').write_text(''.join(f'{h}  {p}\n' for p,h in files.items()));print(status,nselection)
if __name__=='__main__':main()
