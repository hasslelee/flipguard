#!/usr/bin/env python3
"""Copy an explicit, bounded followup allowlist; never open reserved data.

Run only after PAPER_REVIEW_LOCK.json exists. No model imports or executions.
All writes are exclusive and confined to this task's new directories.
"""
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/home/ckks2/deciprotect')
DOC = ROOT / 'docs/research/fg_journal_review_v1_20260906'
RUN = ROOT / 'results/fg_journal_review_v1_20260906_run01'
PACK = DOC / 'JOURNAL_REVIEW_HANDOFF'
FOLLOW = PACK / 'FOLLOWUP_SEPARATE'
HEAD = '54671293e5f6532f2423f5bf473ea714555ee9f4'
CAUSE = 'docs/research/fg_cause_v1_20260906/'
COMMON = 'research/contribution_validation/'
BANK = 'research/hediff_bank_validation/'
ENV = dict(os.environ, GIT_OPTIONAL_LOCKS='0', PYTHONDONTWRITEBYTECODE='1')
entries = []


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(rel):
    # Never open the manifest carrying reserved identities, or raw data pools.
    assert not any(x in rel for x in (
        'INPUT_POOL_LOCK.json', 'PLAINTEXT_ACCESS_AUDIT.json',
        'BANK_CANDIDATE_POOL.csv', 'BANK_INPUT_PLAINTEXT.csv',
        'BANK_PLAINTEXT_SELECTIONS.csv', 'archive/', '.venv/', '.env'))
    p = ROOT / rel
    assert p.resolve().is_relative_to(ROOT) and not p.is_symlink()
    assert all(not q.is_symlink() for q in p.parents if q.is_relative_to(ROOT))
    return p.read_bytes()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, env=ENV).decode()


def origin(rel):
    return {
        'original_path': str(ROOT / rel),
        'original_sha256': sha(read(rel)),
        'last_change_commit': git('log', '-1', '--format=%H', '--', rel).strip() or None,
        'checkout_head': HEAD,
    }


def write(name, data, transformation, role, sources=None, detail=None):
    p = FOLLOW / name
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode()
    with p.open('xb') as f:
        f.write(data)
    entry = {
        'path': str(p.relative_to(PACK)), 'sha256': sha(data), 'bytes': len(data),
        'role': role, 'transformation': transformation, 'sources': sources or [],
        'authored_in_current_task': transformation in ('generated', 'numbered_excerpt'),
    }
    if detail:
        entry['detail'] = detail
    entries.append(entry)
    return entry


def copy(rel, name, role):
    return write(name, read(rel), 'byte_identical_copy', role, [origin(rel)])


def dump(name, obj, sources=None, role='followup metadata'):
    return write(name, json.dumps(obj, ensure_ascii=False, indent=2) + '\n',
                 'generated', role, sources)


def excerpt(rel, name, ranges):
    lines = read(rel).decode().splitlines()
    sources = [origin(rel)]
    text = f'# Numbered source excerpt\n\nOriginal: `{rel}`\n\n'
    text += f'SHA-256: `{sources[0]["original_sha256"]}`\n\n'
    text += f'Last change: `{sources[0]["last_change_commit"]}`; checkout: `{HEAD}`.\n\n'
    text += f'Original has {len(lines)} lines. Included inclusive ranges: {ranges}; all other lines omitted here. Full source is included separately.\n\n'
    for a, b in ranges:
        assert 1 <= a <= b <= len(lines)
        text += f'## Lines {a}–{b}\n\n```text\n'
        text += '\n'.join(f'{i:4d} | {lines[i-1]}' for i in range(a, b+1))
        text += '\n```\n\n'
    return write(name, text, 'numbered_excerpt', 'read-only source excerpt', sources,
                 {'included_line_ranges': ranges, 'original_line_count': len(lines)})


def main():
    assert git('rev-parse', 'HEAD').strip() == HEAD
    lock = json.loads((RUN / 'PAPER_REVIEW_LOCK.json').read_text())
    for rel, digest in lock['files'].items():
        assert sha((PACK / 'PAPER_ONLY' / rel).read_bytes()) == digest
    assert not FOLLOW.exists(), 'new output only; never overwrite completed collection'
    FOLLOW.mkdir()
    copy(CAUSE + 'REPORT_KO.md', 'CAUSE_REPORT_KO.md', 'completed cause report; followup only')
    tables = ['AB_RELATIONS.csv', 'CANDIDATE_RECONSTRUCTION.csv', 'SYNTHESIS_PATHS.csv',
              'BANK_STAGE_SUMMARY.csv', 'BANK_POLICY_COVERAGE.csv', 'BANK_POLICY_ANALYSIS_ONLY.csv',
              'BANK_SELECTION_ALTERNATIVES.csv', 'COST_CAUSES.csv', 'OBSERVED_ALTERNATIVES.csv']
    for name in tables:
        copy(CAUSE + name, 'supporting_tables/' + name, 'existing aggregate; no reanalysis')

    report = read(CAUSE + 'REPORT_KO.md').decode().splitlines(keepends=True)
    first = next(i for i, s in enumerate(report) if s.startswith('### 우선안 하나:'))
    last = next(i for i, s in enumerate(report) if s.startswith('## 8.'))
    src = origin(CAUSE + 'REPORT_KO.md')
    preamble = ('# 기존 C/C′/B30 제안 및 검증 계획 원문 발췌\n\n'
                f'출처: `{src["original_path"]}`; 원문 {first+1}–{last}행.\n\n'
                f'원문 SHA-256: `{src["original_sha256"]}`; 변경 커밋: `{src["last_change_commit"]}`.\n\n'
                '아래는 기존 §6 우선안과 §7의 연속 원문이다. 새 계획이나 암호화 protocol을 작성한 것이 아니며 이번 실행 승인의 대상도 아니다. 원문 전체는 CAUSE_REPORT_KO.md에 포함한다.\n\n---\n\n')
    write('PROPOSED_VALIDATION_PLAN.md', preamble + ''.join(report[first:last]),
          'verbatim_excerpt_with_provenance_header', 'existing unexecuted plan and rejection conditions',
          [src], {'included_line_ranges': [[first+1, last]]})

    sources = [
        COMMON + 'internal/ckksplanner/synthesis.go',
        COMMON + 'internal/ckksplanner/synthesis_test.go',
        COMMON + 'internal/ckksplanner/contract_test.go',
        COMMON + 'internal/ckksplanner/contract.go',
        COMMON + 'internal/ckksplanner/direct_policy.go',
        COMMON + 'internal/ckksplanner/security_policy.go',
        COMMON + 'internal/ckksplanner/concrete_security.go',
        COMMON + 'internal/ckksplanner/independent.go',
        COMMON + 'internal/ckksplanner/independent_test.go',
        COMMON + 'internal/ckksbackend/profile.go',
        COMMON + 'cmd/contribution-case/main.go',
        BANK + 'internal/ckksplanner/synthesis.go',
        BANK + 'internal/ckksplanner/bank_contract.go',
        BANK + 'internal/ckksplanner/bank_executor.go',
        BANK + 'internal/bankadapter/model.go',
        BANK + 'internal/ckksbackend/bank_adapter.go',
        BANK + 'cmd/contribution-case/main.go',
        COMMON + 'go.mod', BANK + 'go.mod',
    ]
    for rel in sources:
        copy(rel, 'source/' + rel, 'unchanged policy, dependency, caller or test source')
    excerpt(COMMON + 'internal/ckksplanner/synthesis.go', 'numbered_excerpts/synthesis.md',
            [[12,100], [201,286], [288,627], [654,792], [817,896], [946,979]])
    excerpt(COMMON + 'internal/ckksplanner/synthesis_test.go', 'numbered_excerpts/synthesis_tests.md', [[164,230]])
    excerpt(COMMON + 'internal/ckksplanner/contract_test.go', 'numbered_excerpts/test_fixture.md',
            [[363, len(read(COMMON + 'internal/ckksplanner/contract_test.go').decode().splitlines())]])
    excerpt(COMMON + 'internal/ckksbackend/profile.go', 'numbered_excerpts/backend_profile.md', [[1,49]])
    excerpt(BANK + 'cmd/contribution-case/main.go', 'numbered_excerpts/bank_call_path.md', [[91,150], [197,261]])
    excerpt(COMMON + 'internal/ckksplanner/independent.go', 'numbered_excerpts/independent_generator.md', [[12,24], [98,126]])

    history_paths = [COMMON + 'internal/ckksplanner/synthesis.go',
                     BANK + 'internal/ckksplanner/synthesis.go',
                     COMMON + 'internal/ckksplanner/synthesis_test.go', CAUSE + 'REPORT_KO.md']
    history = '\n\n'.join('PATH ' + p + '\n' + git('log', '--follow', '--format=%H %aI %s', '--name-status', '--', p)
                          for p in history_paths)
    write('POLICY_HISTORY_GIT.txt', history, 'generated', 'DeciProtect Git history; import is not original authorship',
          [origin(p) for p in history_paths])
    imported = subprocess.check_output(['git', 'show',
        'ee8ecda22ec2a7db2eec550bb18ec51dc32fb0e6:baseline/source/internal/ckksplanner/synthesis.go'], cwd=ROOT, env=ENV)
    assert imported == read(COMMON + 'internal/ckksplanner/synthesis.go')
    equal_sources = []
    for p in ['research/selection_extension', 'research/fashion_extension', 'research/hediff_bank_validation']:
        for f in ['synthesis.go', 'synthesis_test.go', 'contract_test.go']:
            rel = p + '/internal/ckksplanner/' + f
            base = COMMON + 'internal/ckksplanner/' + f
            equal_sources.append({**origin(rel), 'equal_to': base,
                                  'byte_identical': read(rel) == read(base)})

    # Only preexisting metadata/logs. Do NOT rerun any of their listed commands.
    for rel, dest in [
        ('docs/research/fg_contrib_v1_20260906/LOCAL_VALIDATION.json', 'CONTRIB_LOCAL_VALIDATION.json'),
        ('docs/research/fg_contrib_v1_20260906/PRESERVED_C_CORE_CHECK.json', 'PRESERVED_C_CORE_CHECK.json'),
        ('docs/research/fg_expand_v1_20260905/VALIDATION.json', 'EXPAND1_VALIDATION.json'),
        ('docs/research/fg_expand_v1_20260905/validation_logs/copied_selection_tests.txt', 'EXPAND1_SELECTION_TEST_LOG.txt'),
        ('docs/research/fg_expand_v2_20260905/validation_logs/fashion_native_tests.json', 'EXPAND2_FASHION_TEST_RECORD.json'),
        ('docs/research/fg_expand_v2_20260905/validation_logs/fashion_native_tests.txt', 'EXPAND2_FASHION_TEST_LOG.txt'),
        ('results/fg_cause_v1_20260906_run01/FINAL_VERIFICATION.json', 'CAUSE_FINAL_VERIFICATION.json'),
        ('protocols/FG_CAUSE_V1_20260906.json', 'CAUSE_PROTOCOL.json'),
    ]:
        copy(rel, 'existing_records/' + dest, 'stored validation or management record, not newly executed')
    fvrel = 'results/fg_cause_v1_20260906_run01/FINAL_VERIFICATION.json'
    prrel = 'protocols/FG_CAUSE_V1_20260906.json'
    fv = json.loads(read(fvrel)); protocol = json.loads(read(prrel))
    locked_path = 'results/fg_cause_v1_20260906_run01/INPUT_POOL_LOCK.json'
    access_path = 'results/fg_cause_v1_20260906_run01/PLAINTEXT_ACCESS_AUDIT.json'
    dump('RESERVATION_METADATA.json', {
        'scope': 'existing management records only; no reserved identities, rows, labels, logits or margins opened or recomputed',
        'source_protocol_id': protocol['protocol_id'],
        'source_protocol_created_utc': protocol['created_utc'],
        'candidate_count_recorded': fv['checks']['candidate_pool'],
        'audit_reserve_count_recorded': fv['checks']['unscored_audit_reserve'],
        'pool_rule_verbatim': protocol['pool_rule'],
        'selection_rank_verbatim': protocol['selection_rank'],
        'audit_rule_verbatim': protocol['audit_reserve_rule'],
        'preprocessing_caveat_verbatim': protocol['preprocessing'],
        'recorded_verification': {'created_utc': fv['created_utc'], 'status': fv['status'],
                                  'unscored_audit_reserve': fv['checks']['unscored_audit_reserve'],
                                  'selection_rules_reconstructed': fv['checks']['selection_rules_reconstructed']},
        'protected_records_not_opened': [
            {'original_path': str(ROOT / p), 'sha256_from_existing_verification_not_rehashed': fv['new_pack_files'][p],
             'last_change_commit_from_git_metadata': git('log', '-1', '--format=%H', '--', p).strip(),
             'contents_included': False, 'contents_opened_this_task': False}
            for p in (locked_path, access_path)],
        'use_history_limit': 'Existing cause verification records 684 unscored at its timestamp. No global access-log proof or later-use inference is made. This task did not open the reserve; it did not inspect reserve data to prove non-use.',
        'future_use': 'Existing C/Cprime/B30 proposal only; no new activation, execution approval or audit opening in this task.',
    }, [origin(fvrel), origin(prrel), src])

    dump('CODE_INDEX.json', {
        'checkout_head': HEAD,
        'source_files': [e for e in entries if e['path'].startswith('FOLLOWUP_SEPARATE/source/')],
        'numbered_excerpts': [e for e in entries if '/numbered_excerpts/' in e['path']],
        'cross_module_source_identity': equal_sources,
        'history': {'earliest_observed_import_commit': 'ee8ecda22ec2a7db2eec550bb18ec51dc32fb0e6',
                    'imported_path': 'baseline/source/internal/ckksplanner/synthesis.go',
                    'imported_sha256': sha(imported), 'equal_to_current': True,
                    'copy_commit': '1a9404faa220a773555a387dc4ede809fdc8d6ca',
                    'original_policy_authorship_date': 'unconfirmed in inspected DeciProtect history',
                    'disable_reason': 'not recorded in inspected sources, caller settings, relevant documents and imported history',
                    'disable_transition': 'not observed; earliest imported and current defaults both none'},
        'tests': {'executed_this_task': False,
                  'same_tier_test_names': ['TestSynthesizeMaximizesPrecisionWithinMinimumLogNTier', 'TestSynthesizeLinearSameTierCeilingIsScale26'],
                  'test_name_caveat': 'Second test name says Scale26 but assertion expects scale25; source preserved, not silently corrected.',
                  'stored_evidence': 'EXPAND1 selection and EXPAND2 Fashion commands include TestSynthesize regex, exit0 package logs. Source equality checked. Logs are not individual verbose test traces or Bank Cprime encrypted evidence.',
                  'current_contrib_local_validation': 'TestIndependent subset does not run the same-tier tests.'},
        'new_parameter_generation': False, 'new_Cprime_implementation': False,
    }, role='source, caller, default, history and stored-test index')
    with (RUN / 'FOLLOWUP_COLLECTION_INDEX.json').open('x') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2); f.write('\n')
    print(json.dumps({'copied_and_extracted_files': len(entries), 'paper_lock_unchanged': True,
                      'reserve_contents_read': False, 'no_reanalysis_or_HE': True}))


if __name__ == '__main__':
    main()
