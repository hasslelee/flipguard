"""Update mutable project handoff after the finite bundle, preserving exact prior sync copies."""
import json,shutil
from pathlib import Path
import run as r
def main():
    c=r.read(r.RUN/'REVIEWED_CONCLUSIONS.json');s=r.ROOT/'docs/project_sync';old=r.RUN/'provenance/project_sync_previous';old.mkdir(parents=True,exist_ok=True)
    for path,h in r.read(r.RUN/'SYNC_PREWRITE_BINDINGS.json')['files'].items():assert r.sha(path)==h,('INTERVENING_SYNC_EDIT_PRESERVE_AND_REVIEW',path)
    for name in ['PROJECT_SYNC_INDEX.md','CHATGPT_HANDOFF.md','RESEARCH_STATE.json']:
        target=old/name;assert not target.exists();shutil.copyfile(s/name,target)
    j=r.read(s/'RESEARCH_STATE.json')
    j.update(updated_at_utc=r.now(),current_protocol_id='FG_THESIS_V1_20260908',current_run_id=r.RUN.name,
        status='COMPLETED_FINITE_THESIS_BUNDLE_WITH_DECLARED_DEFERRALS',active_experiments=[],automatic_followup_enabled=False,
        next_scope='Thesis writing and advisor review. No automatic CKKS, training, new data/method or Bank quartile run. Reserved684 is now used and must never be relabelled fresh.',
        report='docs/research/fg_thesis_v1_20260908/THESIS_EXPERIMENTS_KO.md',
        pdf_wording_issue='Historical0905 editorial note retained in the prior-state copy. User-designated0908 submission is complete; journal editing was not reopened.')
    j['historical_sections_note']='Existing cause_analysis/contribution/historical_protocol_results describe their own completion times; their unscored-reserve and inactive-policy fields are historical. Current reservation use and isolated Cprime status are in thesis_validation.'
    j['thesis_validation']={'protocol':'protocols/FG_THESIS_V1_20260908.json','run':str(r.RUN.relative_to(r.ROOT)),
        'user_approval':'explicit finite implementation/CKKS/thesis bundle; historical no-approval notes superseded only within this scope',
        'submission_pdf':r.read(r.RUN/'provenance/SUBMISSION_PDF_BINDING.json'),
        'original_C_modified':False,'isolated_variant':'research/thesis_validation_v1','adoption':c['adoption_label'],
        'findings':c['research_findings'],'new_training_models':0,'actual_new_CKKS_fixed_models':5,
        'A2_selection_jobs':18,'A3_selection_jobs':18,'B_selection_jobs':24,
        'Bank_reserve684':'used once after all compared configurations/rules/metrics were bound; old preprocessing exposure retained',
        'IDS':'deferred official feature CSV access, zero new models or CKKS',
        'independent_device':'not executed, no distinct authorized physical host',
        'native_seconds':sum(r.read(p)['wall_seconds'] for p in (r.RUN/'commands').glob('*.end.json')),'charged_native_seconds':r.used(),'cap_seconds':86400,'automatic_followup':False,
        'deliverables':'docs/research/fg_thesis_v1_20260908','previous_sync_snapshot':str(old.relative_to(r.ROOT))}
    (s/'RESEARCH_STATE.json').write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
    index='''# Current project sync

Precedence: latest explicit user instruction and preservation; user-designated0908 submission for manuscript content; historical0905 PDF and bound code/protocols for old execution; frozen raw evidence and verified analysis; historical proposals.

FG_THESIS_V1_20260908 is complete as a finite bundle with declared IDS/source and independent-device deferrals. Read CHATGPT_HANDOFF.md, RESEARCH_STATE.json and docs/research/fg_thesis_v1_20260908/THESIS_EXPERIMENTS_KO.md. No active experiments or automatic follow-up. The earlier Cprime/no-CKKS approval state was historical; this bundle was explicitly approved and executed in a separate module. Original C and all completed evidence remain unchanged.

Bank reserved684 was opened only after all selection results and audit rules were locked, and has now been used. Never treat it as a fresh reserve or tune from its results. Bank quartile selection remains unexecuted. Preserve A/B no-decision-improvement findings, Bank failures, numerical-versus-decision distinctions and mixed costs. Read CPRIME_DECISION_KO.md for the actual limited adoption judgment; do not infer a new international contribution.

The journal manuscript is complete and was not re-edited. Continue thesis writing only within the documented scope. No new CKKS/training/datasets/methods/remote activity without a new user instruction. Never execute in /home/ckks2/flipguard or modify baseline/archive/completed results. No archive upload or full rehash; no reset of user changes. Source/model/input hashes and exact local raw paths are in the new evidence pack. Prior sync files are preserved in the run provenance folder.
'''
    (s/'PROJECT_SYNC_INDEX.md').write_text(index)
    handoff=f'''# DeciProtect 학위 연구 인계 — 유한 검증 묶음 종료

{c['research_findings']}

**C′ 판단: {c['adoption_label']}**

{c['adoption_reason']}

{c['completion_interpretation']}

- 현재 protocol: `protocols/FG_THESIS_V1_20260908.json`
- 실행/원시 자료: `results/fg_thesis_v1_20260908_run01`
- 보고서·학위 초안·ZIP: `docs/research/fg_thesis_v1_20260908`
- 주 보고서: `THESIS_EXPERIMENTS_KO.md`
- 채택 판단: `CPRIME_DECISION_KO.md`
- 실제 본문: `THESIS_DRAFT_KO.md` / `.txt`
- 새 소스: `research/thesis_validation_v1`; 이전 C 모듈과 결과는 보존
- 선택18+18+24작업을 시도했으며, 빈 적용 영역과 실행 실패/과학적 위반을 구분했다.
- Bank 예약684개는 이제 사용 완료다. 개봉 시점·구성·지표·배치·키 잠금은 `AUDIT_PREOPEN_LOCK.json` 및 예약 접근 기록에 있다. 전수 전처리·NearMiss 이력을 제거하지 않는다.
- IDS 공식 특징 CSV 접근은 차단돼 새 학습/CKKS0. 별도 물리 장비 검증은 미실시다. 현재 성공 증거로 세지 않는다.
- 키·슬롯·방법 별칭을 독립 입력이나 새 모델로 세지 않는다. 테스트 통과는 성능/위험 보장이 아니다.

{c['stop_statement']}

원래 학회원고와 A/B/C·원인 분석을 처음부터 반복하지 않는다. 이전 인계의 미승인 문장은 당시 상태이고, 현재 승인 묶음은 종료됐다. 추가 실험은 자동 시작하지 않는다. 원격 push/업로드는 하지 않았다.
'''
    (s/'CHATGPT_HANDOFF.md').write_text(handoff)
    r.write(r.RUN/'SYNC_UPDATE.json',{'utc':r.now(),'prior_files':{p.name:r.sha(p) for p in old.iterdir()},
        'new_files':{n:r.sha(s/n) for n in ['PROJECT_SYNC_INDEX.md','CHATGPT_HANDOFF.md','RESEARCH_STATE.json']},
        'completed_reports_overwritten':False})
    print('Updated current sync; exact prior files preserved')
if __name__=='__main__':main()
