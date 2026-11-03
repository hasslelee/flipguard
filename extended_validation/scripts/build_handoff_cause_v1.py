#!/usr/bin/env python3
"""Regenerate current sync for the completed plaintext-only cause analysis."""
import datetime,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SYNC=ROOT/'docs/project_sync';DOC=ROOT/'docs/research/fg_cause_v1_20260906';RUN=ROOT/'results/fg_cause_v1_20260906_run01'
def main():
 prior=json.loads((DOC/'history/sync_RESEARCH_STATE.json').read_text())
 assert (DOC/'REPORT_KO.md').exists() and (DOC/'ANALYSIS.json').exists()
 summary=dict(status='COMPLETED_PLAINTEXT_CAUSE_ANALYSIS',source_checkpoint='e2c0054e7778da8f099b1e49ee7b584b2b29bc30',new_ckks=0,retraining=0,C_changed=False,AB_decision_improvement='unobserved, preserved',Bank_C_stress=dict(flips=1,condition_violations=6,affected_condition_inputs=3),candidate_pool=684,future_audit_reserve=684,future_audit_outputs_computed=0,quartile_and_uniform_min_margin=0.1279571776304232,quartile_additional_low_margin_coverage='not observed under locked plaintext sampling rule',minimal_proposal='review existing inactive same-tier precision-slack policy; not activated',incremental_value_over_B='not established',automatic_followup=False)
 state={**prior,'updated_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'current_protocol_id':'FG_CAUSE_V1_20260906','current_run_id':RUN.name,'status':summary['status'],'active_experiments':[],'automatic_followup_enabled':False,'next_scope':'Stop. User confirmation required before implementing C variant or any new CKKS. Bank quartile experiment not executed.','report':str((DOC/'REPORT_KO.md').relative_to(ROOT)),'cause_analysis':summary}
 (SYNC/'RESEARCH_STATE.json').write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n')
 text='''# A/B/C 원인 분석 완료 인계

최신 사용자 지시가 이전 실행 승인에 우선한다. 현재 작업은 완료된 원시 자료와 고정 모델의 평문 계산을 이용한 원인 분석이다. **새 CKKS·재학습·데이터 확대·C 변경 구현은 승인되지 않았다.** 제안했던 Bank 마진 사분위 선택 실험도 실행하지 않는다.

- 위치 `/home/ckks2/deciprotect`; 기준 checkpoint `e2c0054e7778da8f099b1e49ee7b584b2b29bc30`에서 clean 확인.
- 최종 PDF `baseline/journal_final_20260905.pdf`, SHA256 `0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85`.
- Protocol `FG_CAUSE_V1_20260906`, run `fg_cause_v1_20260906_run01`, 상태 **COMPLETED_PLAINTEXT_CAUSE_ANALYSIS**.
- 원본 FlipGuard에서 코드/인터프리터 실행 금지. baseline/archive/PDF/완료 실험과 기존 C 불변. archive 전송/전수 재해시 금지.

읽을 문서는 `docs/research/fg_cause_v1_20260906/REPORT_KO.md` 하나와 연결 집계표다. 기존 완료한 `fg_contrib_v1_20260906/REPORT_KO.md`를 덮어쓰지 않았다. 새 결과는 기존 판정 개선 미관측을 성공으로 바꾸지 않는다.

확인 결과:

- 이진 네 모델의 주 최대오차 조건은 같은 관측 출력의 적용 영역 판정/마진 조건을 함의한다. 모든 A/B는 첫 후보에서 종료했다. Fashion에는 포함 관계가 없지만 실제 오차가 작아 둘 다 통과했다. HTRU2 선형 S22는 수용 집합이 달라도 실제 선택이 같았던 사례다. RMSE는 별도 논리다.
- Bank C 합성 stress 판정 변화1회/조건위반6회(3입력)를 그대로 보존한다. 6197 키2의 반대 방향 클래스 오차가 작은 gap을 뒤집었다. 전체 hidden 최대는 선택보다 작았다. 중간 CKKS 오차 미기록으로 연산 단계별 원인은 미분리다. 합성 정답/공동 고객 타당성은 미확정이다.
- 미사용 원본1368개를 출력 계산 전에 후보684/향후 감사684로 분리했다. 감사 예약의 출력·마진은 계산하지 않았다. 후보에 margin<.1인11개가 있지만 고정 hash 균등16/개발사분위4×4는 모두 놓쳤다. 두 정책14개 공통, 최소margin .127957 동일, 초기 평문 scale 추정21도 동일하다. 분위 규칙을 바꿔 좋은 결과를 고르지 않는다.
- Bank S20과 B30은 같은 N13/Q5/P1 경로여서 비용 감소가 없었다. Fashion0 C의 QP218은 N13한도214를 넘어 N14가 되어 약2배 느렸다. 네 표형 비용 이득은 N 감소와 정확성 요구/적용 범위 차이를 함께 보고한다.
- 최소 검토안은 기존 비활성 `maximizePrecisionWithinMinLogNTier` 정책 하나다. 활성화/실행하지 않았다. B보다 추가 가치가 있다는 증거는 없다. 입력 층화·보안 완화·하향 N 탐색을 함께 넣지 않는다. Fashion0의 N 증가 문제는 별도 미해결이다.

분석 검증: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/verify_fg_cause_v1.py`. `--write` 분석기는 새 파일 전용 배타 쓰기이므로 완료 폴더에서 재실행하지 않는다. source/input/protocol 연결은 새 run의 READ_BINDINGS, SUPPLEMENT_READ_BINDINGS, SOURCE_REVIEW, FINAL_VERIFICATION이다.

**다음 행동: 보고서의 변경 내용과 검증 계획을 사용자에게 보고하고 종료. C 변형 구현 또는 새 암호화 실험은 사용자 확인 전까지 하지 않는다.** 기존 전체자료 정규화·NearMiss 이력은 계속 명시하고 새 키/슬롯을 독립 입력이나 위험 상한으로 세지 않는다.
'''
 for name in ['CHATGPT_HANDOFF.md','CODEX_HANDOFF.md']:(SYNC/name).write_text(text)
 (SYNC/'PROJECT_SYNC_INDEX.md').write_text('''# Current project sync

Precedence: latest explicit user direction and preservation; final journal PDF; immutable protocols/raw results and bound source; verified analysis; earlier proposals.

Current task FG_CAUSE_V1_20260906 is complete: plaintext-only cause analysis following completed A/B/C bundle at e2c0054e7778da8f099b1e49ee7b584b2b29bc30. Read CHATGPT_HANDOFF.md, RESEARCH_STATE.json and docs/research/fg_cause_v1_20260906/REPORT_KO.md. No active experiments. Do not implement/activate a C variant or run CKKS without user confirmation. Bank quartile experiment remains unexecuted.

Preserve A/B no decision improvement, Bank C stress failure and mixed costs. Cost savings do not substitute for decision improvement. The existing inactive same-tier precision policy is a proposal for review, not a new implemented method or international contribution. Incremental value over B is unknown.

Never execute in /home/ckks2/flipguard or modify baseline/archive/PDF/completed evidence/C. No archive upload/full rehash. Candidate684/future-audit684 split is locked; future-audit outputs and margins remain unread. No audit retuning or independent-sample claims from key repeats/slots. Offline configuration selection intentionally uses plaintext references; historical DP runtime/queue/risk work remains separate. Update current sync at task completion; preserve completed packs.
''')
 (SYNC/'OPEN_ISSUES.md').write_text('''# Current evidence limits

1. A/B core decision improvement remains unobserved. Binary max-error inclusion and first-candidate termination constrain what this comparison can show; multiclass/RMSE require separate arguments.
2. Bank C stress: one decision change, six sufficient-condition violations on three inputs; synthetic ground truth and joint customer validity unknown. Encrypted intermediate errors are unavailable. Whole-source preprocessing/NearMiss before split precludes leakage-free claims.
3. Candidate pool contains small-margin originals but locked quartile4x4 and uniform16 omit the tail and have identical plaintext initial estimates. Do not execute the old quartile proposal or retune its sampling seed.
4. Bank same structural tier has no observed cost saving. Fashion0 QP218 crosses cap214, causing N doubling. Lower scale is not intrinsically faster; higher scale is not guaranteed to preserve more decisions.
5. Review only: existing inactive same-tier precision slack. No C activation/implementation. B30 already suffices in Bank at similar measured cost; added value remains unknown. Fashion0 lower-cost-tier search is a separate unresolved change, not bundled.
6. Fresh audit reserve684 has no computed logits/margins. Use the committed pool lock; no test/stress winner inserted into selection. Future CKKS/implementation needs explicit user confirmation.
7. Previous EVA outcomes, FHE-Agent correction, frozen PDF wording issues, original model unavailability and cross-backend security differences remain as in completed reports. No new global risk/optimality/international-competitiveness claim.
''')
 oldlog=(DOC/'history/sync_SYNC_CHANGELOG.md').read_text();(SYNC/'SYNC_CHANGELOG.md').write_text(oldlog+'\n2026-09-06 FG_CAUSE_V1 completed: read-only existing raw CKKS and plaintext model cause analysis; split unused Bank identities before candidate outputs; preserved audit reserve; reviewed existing inactive precision-slack policy without activation; no new HE/training/C edits. Current handoff supersedes earlier automatic experiment direction. Completed reports unchanged.\n')
 names=['PROJECT_SYNC_INDEX.md','CHATGPT_HANDOFF.md','CODEX_HANDOFF.md','RESEARCH_STATE.json','OPEN_ISSUES.md','SYNC_CHANGELOG.md']
 (SYNC/'SHA256SUMS').write_text(''.join(hashlib.sha256((SYNC/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in names))
if __name__=='__main__':main()
