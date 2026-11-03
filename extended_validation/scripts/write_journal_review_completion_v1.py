#!/usr/bin/env python3
"""Write completion and regenerated sync in the new task output only.

Latest user direction preserves all existing files. Do not overwrite the
previous current sync/dispatcher; deliver this new completion sync explicitly.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/home/ckks2/deciprotect')
DOC = ROOT / 'docs/research/fg_journal_review_v1_20260906'
RUN = ROOT / 'results/fg_journal_review_v1_20260906_run01'
SYNC = DOC / 'project_sync'
ENV = dict(os.environ, GIT_OPTIONAL_LOCKS='0', PYTHONDONTWRITEBYTECODE='1')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x') as f:
        f.write(value)


def dump(p, value):
    write(p, json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, env=ENV).decode()


def main():
    v = json.loads((RUN/'PACKAGE_VERIFICATION.json').read_text())
    lock = json.loads((RUN/'PAPER_REVIEW_LOCK.json').read_text())
    assert v['status']=='PASS'
    assert git('rev-parse','HEAD').strip()=='54671293e5f6532f2423f5bf473ea714555ee9f4'
    assert not git('diff','--name-only') and not git('diff','--cached','--name-only')
    pack = DOC/'JOURNAL_REVIEW_HANDOFF'
    for n,digest in lock['files'].items():
        assert sha(pack/'PAPER_ONLY'/n)==digest
    text = f'''# PDF 한정 심사와 후속 자료 수집 완료 인계

이번 작업 `FG_JOURNAL_REVIEW_V1_20260906`은 완료됐다. 새 실험은 활성화하지 않는다. 최신 사용자 지시에 따라 기존 파일은 모두 보존하고 이 새 출력 폴더에 완료 sync/ChatGPT 인계본을 생성했다. 기존 `docs/project_sync/` 및 `scripts/build_handoff.py`는 이전 원인 분석 상태 그대로 보존했다. 이 파일을 이번 문서 작업의 최신 인계로 읽는다.

작업 위치 `/home/ckks2/deciprotect`, 확인·유지한 HEAD `54671293e5f6532f2423f5bf473ea714555ee9f4`. 이전 clean 기록을 재사용하고 완료 시 기존 tracked/staged diff 없음과 HEAD 불변을 확인했다. commit/push/upload 없음.

## PDF 한정 심사

유일한 내용 근거는 `baseline/journal_final_20260905.pdf`다. SHA-256 `0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85`, 1,217,432바이트, 12쪽. 원본·baseline·기존 출처 기록이 일치한다. 전쪽 본문·표·그림·식·참고문헌 및 제한을 직접 읽고 전쪽 렌더링을 확인했다. 기존 점수·이전 원고·후속 결과·코드·외부 새 문헌은 주 심사의 근거가 아니다. 후속 결과를 알고 있으므로 블라인드 심사가 아니다.

주제 유지, **대폭 수정 후 재검토**. 실제 내부 제거 비교와 별도 입력 검증, 범위·실패 공개는 강점이다. 초기 합성·유한 후보 집합의 재현 설명, 평문 모델 품질·적용 범위, 강한 추가 가치 주장에 대응하는 대표 대안 비교가 핵심 보완점이다. 방법을 교체하거나 전역 보장·최적성을 요구하는 판단이 아니다. 세부는 `JOURNAL_REVIEW_HANDOFF/PAPER_ONLY/PAPER_ONLY_REVIEW_KO.md` 및 주장22행 표에 있다.

심사 해시 `{lock['files']['PAPER_ONLY_REVIEW_KO.md']}`. PAPER_ONLY 19개 파일은 후속 코드 자료를 읽기 전 `{lock['locked_utc']}`에 고정했다. 이후 해시 변화 없음.

## 별도 후속 기술자료

기존 cause 보고서 사본, 집계표9개, 원문 계획 발췌, 소스20개 및 발췌6개, 기존 검증·테스트·관리 기록을 포함한다. `FOLLOWUP_SEPARATE/POLICY_CONTEXT_KO.md`는 주 심사와 구별되는 새 기술 설명이다. 원인 분석 자체를 재실행하지 않았다.

비활성 옵션은 실제 존재하고 현재 C 기본값은 none이다. 최초 backend 유효 합성 뒤 같은 N에서 scale 여유를 쓰며, repair에는 다시 적용하지 않는다. 같은 구조적 등급이 실제 지연 동등성을 뜻하지 않는다. Bank caller에서 별도 concrete-security helper의 추가 호출을 확인하지 못했으며 함수 존재와 실행을 구분했다. 기존 선언 Q/QP admission은 보존했다. C′ 선택 literal·암호화 결과는 없고 B 대비 추가 가치는 미확인이다. 원래 도입 경위·기본 비활성 이유도 확인한 이력에 미기록이다.

예약684개의 기존 관리 개수·규칙·기록 해시만 수집했다. 식별자를 담는 예약 manifest와 접근 목록은 열거나 복사하지 않았다. 실제 예약 행·레이블·점수·마진은 미열람·미계산·미포함. 기존 관리 기록 이상의 전역 미사용 증명은 하지 않는다.

## 제출물과 검증

ZIP: `{v['zip_path']}`

크기 {v['zip_bytes']:,}바이트, 파일 {v['zip_file_count']}개, 압축 전 {v['uncompressed_bytes']:,}바이트.
SHA-256: `{v['zip_sha256']}`.
다시 열어 CRC, 명시 목록, 모든 파일 해시, 원문 사본 동일성, PDF 기준 일치, 심사 잠금 보존을 확인했다. 상세는 `results/fg_journal_review_v1_20260906_run01/PACKAGE_VERIFICATION.json`이다. 로컬 파일 생성 완료이며 외부 서비스로 전달·공개한 상태가 아니다.

새 CKKS, 재학습, C/C′ 변경·활성화, 정책 선택 입력 변경, 예약 감사 사용, 원격 push를 하지 않았다. 원본 FlipGuard 실행, archive 탐색·전수 해시·전송도 하지 않았다. 기존 C/최종 PDF/baseline/완료 보고서·결과/현재 관리 파일 불변. 이 문서 작업을 마치고 종료한다. 새 변경이나 암호화 검증을 자동 실행하지 않는다.
'''
    write(SYNC/'CHATGPT_HANDOFF.md',text)
    write(SYNC/'CODEX_HANDOFF.md',text)
    write(SYNC/'PROJECT_SYNC_INDEX.md', '''# 이번 문서 작업의 완료 sync

최신 명시 사용자 지시가 우선한다. 기존 파일 보존을 위해 이 sync는 새 작업 폴더에 생성했다. 이전 현재 sync/dispatcher는 덮어쓰지 않았다. `CHATGPT_HANDOFF.md`와 `RESEARCH_STATE.json`을 이번 완료 상태로 읽는다.

PDF 한정 심사의 내용 근거는 확인한 최종 PDF뿐이다. 후속 자료는 PAPER_ONLY 잠금 뒤 수집한 별도 기술자료다. 두 평가를 혼합하지 않는다. 원본 FlipGuard/baseline/archive/C/완료 보고서·결과는 불변이다. 새 실험·C′ 활성화·예약 감사 개봉은 없다. 패키지 검증 완료 후 종료한다.
''')
    dump(SYNC/'RESEARCH_STATE.json', {
        'task':'FG_JOURNAL_REVIEW_V1_20260906','status':'COMPLETED_REVIEW_COLLECTION_VERIFIED_ZIP',
        'active_experiments':False,'source_head':'54671293e5f6532f2423f5bf473ea714555ee9f4',
        'paper_only_review':str(pack/'PAPER_ONLY/PAPER_ONLY_REVIEW_KO.md'),
        'paper_only_verdict':'대폭 수정 후 재검토; 주제 유지',
        'followup_report':str(pack/'FOLLOWUP_SEPARATE/POLICY_CONTEXT_KO.md'),
        'zip':v,'original_sync_preserved':True,'reason':'Latest user direction: preserve existing files; all new deliverables in a separate output folder.',
        'next_action':'Stop. No method change, CKKS, reserved audit, retraining, push or upload authorized.'})
    write(SYNC/'OPEN_ISSUES.md', '''# 이번 작업 이후 남은 사항 — 실행 예약 아님

- PDF 한정 심사 의견의 우선순위3개는 설명·증거 보완 권고이며 이번에 실험하지 않았다.
- 비활성 옵션의 원래 도입 경위·비활성 이유, 실제 C′ literal/실행 결과, B 대비 추가 가치는 미확인이다.
- 기존 C/C′/B30 문서는 제안이다. 신규 암호화 protocol과 총 실행 상한은 아직 확정되지 않았다.
- 예약684개 미사용은 기존 관리 기록 시점·범위로 제한한다. 예약 내용은 계속 미개봉이다.
- ZIP은 로컬 생성 및 검증 완료. 외부 업로드나 원격 전달은 실행하지 않았다.
''')
    write(SYNC/'SYNC_CHANGELOG.md', '# 완료 기록\n\n'+datetime.now(timezone.utc).isoformat()+' — PDF-only review locked before followup collection; actual files packaged and ZIP verified. New task-local sync generated; existing sync preserved.\n')
    with (SYNC/'SHA256SUMS').open('x') as f:
        for p in sorted(SYNC.iterdir()):
            if p.name!='SHA256SUMS': f.write(sha(p)+'  '+p.name+'\n')
    dump(RUN/'COMMANDS_AND_SCOPE.json', {
        'actual_new_artifact_commands': [
            'PYTHONDONTWRITEBYTECODE=1 python3 scripts/write_journal_pdf_review_tables_v1.py',
            'PYTHONDONTWRITEBYTECODE=1 python3 scripts/collect_journal_review_followup_v1.py',
            'PYTHONDONTWRITEBYTECODE=1 python3 scripts/package_journal_review_v1.py',
            'PYTHONDONTWRITEBYTECODE=1 python3 scripts/write_journal_review_completion_v1.py'],
        'pdf_processing':'Direct pdftotext -layout extraction, page-level text and pdftoppm PNG rendering at130dpi; images visually inspected before review lock.',
        'syntax_validation':'compile(source, path, exec) before running the new collection/packaging/completion scripts; no bytecode cache written',
        'read_only_operations':['targeted cat/sed/rg and source reads','git rev-parse/status/log/show/diff within DeciProtect','targeted SHA-256 for source/copy provenance'],
        'review_lock':str(RUN/'PAPER_REVIEW_LOCK.json'),
        'new_HE_training_or_plaintext_inference':False,'reserve_content_opened':False,
        'old_analysis_and_test_commands_executed':False,
        'scope_note':'The copied old reports contain past commands; those are documentary evidence, not commands executed now.',
        'existing_files_modified':[],'commit_push_upload':False})
    status=git('status','--porcelain=v1','--untracked-files=normal')
    write(RUN/'END_STATUS.txt',status)
    assert not git('diff','--name-only') and not git('diff','--cached','--name-only')
    script_names=['write_journal_pdf_review_tables_v1.py','collect_journal_review_followup_v1.py',
                  'package_journal_review_v1.py','write_journal_review_completion_v1.py']
    new_files=[p for p in DOC.rglob('*') if p.is_file()]+[p for p in RUN.rglob('*') if p.is_file()]
    new_files += [ROOT/'scripts'/n for n in script_names]
    dump(RUN/'COMPLETION_VERIFICATION.json', {
        'status':'PASS','created_utc':datetime.now(timezone.utc).isoformat(),
        'head':git('rev-parse','HEAD').strip(),'tracked_changes':[],'staged_changes':[],
        'new_output_roots':[str(DOC),str(RUN)],'new_scripts':script_names,
        'new_file_inventory_excluding_this_inventory':[
            {'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size}
            for p in sorted(new_files)],
        'pdf_review_lock_preserved':True,'verified_zip_sha256':v['zip_sha256'],
        'sync_generated_at':str(SYNC),'old_current_sync_unchanged':True,
        'completion_is_document_review_and_collection_only':True,
        'automatic_followup':False})
    print(json.dumps({'status':'COMPLETED','new_sync':str(SYNC),'tracked_changes':[],
                      'zip_sha256':v['zip_sha256']},ensure_ascii=False))


if __name__=='__main__':
    main()
