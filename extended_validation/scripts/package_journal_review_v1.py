#!/usr/bin/env python3
"""Package only explicit review/collection files and independently reopen ZIP.

No model, crypto, network, or original experiment execution. New outputs only.
"""
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import zipfile

ROOT = Path('/home/ckks2/deciprotect')
DOC = ROOT / 'docs/research/fg_journal_review_v1_20260906'
RUN = ROOT / 'results/fg_journal_review_v1_20260906_run01'
PACK = DOC / 'JOURNAL_REVIEW_HANDOFF'
HEAD = '54671293e5f6532f2423f5bf473ea714555ee9f4'
ZIP = DOC / 'CKKS_JOURNAL_REVIEW_HANDOFF_20260906_v1.zip'
ENV = dict(os.environ, GIT_OPTIONAL_LOCKS='0', PYTHONDONTWRITEBYTECODE='1')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, obj):
    with path.open('x') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2); f.write('\n')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, env=ENV).decode()


def origin(path):
    p = Path(path)
    assert p.is_file() and not p.is_symlink()
    if p.is_relative_to(ROOT):
        commit = git('log', '-1', '--format=%H', '--', str(p.relative_to(ROOT))).strip() or None
    else:
        commit = None
    return {'original_path': str(p), 'original_sha256': sha(p.read_bytes()),
            'last_change_commit': commit, 'checkout_head': HEAD if p.is_relative_to(ROOT) else None}


def entry(rel, role, transformation, sources, **extra):
    p = PACK / rel
    assert p.is_file() and not p.is_symlink()
    return {'path': rel, 'role': role, 'transformation': transformation,
            'sources': sources, 'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size, **extra}


def main():
    assert git('rev-parse', 'HEAD').strip() == HEAD
    assert not git('diff', '--name-only') and not git('diff', '--cached', '--name-only'), 'Existing tracked files must remain unchanged'
    lockpath = RUN / 'PAPER_REVIEW_LOCK.json'
    lock = json.loads(lockpath.read_text())
    records = json.loads((RUN / 'FOLLOWUP_COLLECTION_INDEX.json').read_text())
    # Small dependency added during the final read-only caller check.
    context_rel = 'research/hediff_bank_validation/internal/ckksbackend/context.go'
    context_source = ROOT / context_rel
    context_dest = PACK / 'FOLLOWUP_SEPARATE/source' / context_rel
    with context_dest.open('xb') as f:
        f.write(context_source.read_bytes())
    context_entry = entry(str(context_dest.relative_to(PACK)), 'Bank context caller dependency; no inferred concrete-security check',
                          'byte_identical_copy', [origin(context_source)])
    records.append(context_entry)
    # Finalize the new, not-yet-packaged index; never touch prior research files.
    index_path = PACK / 'FOLLOWUP_SEPARATE/CODE_INDEX.json'
    code_index = json.loads(index_path.read_text())
    code_index['source_files'].append(context_entry)
    code_index['final_caller_check'] = 'Bank executor/context has no observed call to AssessConcreteSecurity; existence of the helper does not establish execution.'
    index_path.write_text(json.dumps(code_index, ensure_ascii=False, indent=2)+'\n')
    for record in records:
        if record['path'] == 'FOLLOWUP_SEPARATE/CODE_INDEX.json':
            record['sha256'] = sha(index_path.read_bytes())
            record['bytes'] = index_path.stat().st_size
            record['detail'] = 'Finalized with one additional context dependency before packaging.'
    pdf = origin(ROOT / 'baseline/journal_final_20260905.pdf')
    assert pdf['original_sha256'] == '0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85'
    idsrc = [origin(ROOT / 'baseline/FREEZE_MANIFEST.json'),
             origin(ROOT / 'docs/research/fg_expand_v1_20260905/PDF_PROVENANCE.json')]
    for name, digest in lock['files'].items():
        p = PACK / 'PAPER_ONLY' / name
        assert sha(p.read_bytes()) == digest
        if name.endswith('.pdf'):
            kind, role, src = 'byte_identical_copy', 'user-designated final PDF', [pdf]
        elif name == 'PDF_IDENTITY.json':
            kind, role, src = 'generated', 'identity only; no review content derived from provenance', [pdf] + idsrc
        elif name == 'PDF_PAGE_TEXT.txt':
            kind, role, src = 'pdftotext_layout_extraction', 'unrepaired direct text extraction, all 12 pages', [pdf]
        elif name.startswith('page_images/'):
            kind, role, src = 'pdftoppm_png_render_130_dpi', 'direct PDF page render, visually inspected', [pdf]
        else:
            kind, role, src = 'generated', 'PDF-only mock review or evidence table; not blind', [pdf]
        records.append(entry('PAPER_ONLY/' + name, role, kind, src,
                             frozen_before_followup=True, authoring_commit=None if kind != 'byte_identical_copy' else pdf['last_change_commit']))
    with (PACK / 'PAPER_REVIEW_LOCK.json').open('xb') as f:
        f.write(lockpath.read_bytes())
    records.append(entry('PAPER_REVIEW_LOCK.json', 'pre-followup PDF review hash lock', 'byte_identical_copy', [origin(lockpath)]))
    follow = PACK / 'FOLLOWUP_SEPARATE'
    context_sources = [origin(ROOT / 'docs/research/fg_cause_v1_20260906/REPORT_KO.md'),
                       origin(follow / 'CODE_INDEX.json'), origin(follow / 'RESERVATION_METADATA.json')]
    context_sources += [s for e in records if '/source/' in e['path'] for s in e['sources']]
    records.append(entry('FOLLOWUP_SEPARATE/POLICY_CONTEXT_KO.md', 'new followup technical context, separate from paper review',
                         'generated', context_sources, authoring_commit=None))
    records.append(entry('README_KO.md', 'delivery guide and preservation scope', 'generated',
                         [origin(lockpath), origin(follow / 'POLICY_CONTEXT_KO.md')], authoring_commit=None))

    names = sorted(e['path'] for e in records)
    assert len(names) == len(set(names))
    actual = []
    for p in PACK.rglob('*'):
        assert not p.is_symlink(), f'symlink not permitted: {p}'
        if p.is_file():
            actual.append(str(p.relative_to(PACK)))
    assert sorted(actual) == names, 'Unexpected or missing package payload'
    for e in records:
        p = PACK / e['path']
        assert sha(p.read_bytes()) == e['sha256'] and p.stat().st_size == e['bytes']
        if e['transformation'] == 'byte_identical_copy':
            assert len(e['sources']) == 1
            s = e['sources'][0]
            # These are explicit copied sources, never reserved manifests.
            assert not any(t in s['original_path'] for t in ('INPUT_POOL_LOCK.json', 'PLAINTEXT_ACCESS_AUDIT.json', '/archive/'))
            assert p.read_bytes() == Path(s['original_path']).read_bytes()

    # Semantic structure checks, not new research/model tests.
    rows = {}
    for name, count in [('CLAIM_EVIDENCE.csv',22),('REVIEW_ISSUES.csv',6),('PAGE_REVIEW_LOG.csv',12)]:
        with (PACK / 'PAPER_ONLY' / name).open() as f:
            data = list(csv.DictReader(f))
        assert len(data) == count
        rows[name] = len(data)
    metadata = json.loads((follow / 'RESERVATION_METADATA.json').read_text())
    assert metadata['audit_reserve_count_recorded'] == 684
    assert all(not a['contents_opened_this_task'] and not a['contents_included'] for a in metadata['protected_records_not_opened'])
    assert not any(PurePosixPath(n).name in ('INPUT_POOL_LOCK.json','PLAINTEXT_ACCESS_AUDIT.json',
                                           'BANK_CANDIDATE_POOL.csv','BANK_INPUT_PLAINTEXT.csv',
                                           'BANK_PLAINTEXT_SELECTIONS.csv') for n in names)
    for n in names:
        p = PurePosixPath(n)
        assert not p.is_absolute() and '..' not in p.parts
        assert not any(t in p.parts for t in ('.git','.venv','archive','__pycache__','.cache'))

    manifest = {'package_id': 'FG_JOURNAL_REVIEW_V1_20260906',
                'created_utc': datetime.now(timezone.utc).isoformat(), 'checkout_head': HEAD,
                'new_authored_files_uncommitted': True, 'remote_delivery': 'not performed',
                'review_frozen_at': lock['locked_utc'],
                'manifest_policy': 'All payload files listed; MANIFEST.json and SHA256SUMS.txt excluded to avoid self reference. SHA256SUMS includes MANIFEST; ZIP hash recorded outside ZIP.',
                'content_file_count': len(records), 'content_bytes': sum(e['bytes'] for e in records),
                'files': sorted(records, key=lambda x:x['path'])}
    write_json(PACK / 'MANIFEST.json', manifest)
    names.append('MANIFEST.json'); names.sort()
    with (PACK / 'SHA256SUMS.txt').open('x') as f:
        for n in names:
            f.write(sha((PACK/n).read_bytes()) + '  ' + n + '\n')
    names.append('SHA256SUMS.txt'); names.sort()
    with zipfile.ZipFile(ZIP, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for n in names:
            z.write(PACK/n, arcname='JOURNAL_REVIEW_HANDOFF/'+n)
    with zipfile.ZipFile(ZIP) as z:
        expected = ['JOURNAL_REVIEW_HANDOFF/'+n for n in names]
        assert z.namelist() == expected and len(expected)==len(set(expected))
        assert z.testzip() is None
        for info, n in zip(z.infolist(), names):
            assert not stat.S_ISLNK(info.external_attr >> 16)
            assert z.read(info) == (PACK/n).read_bytes()
        embedded_manifest = json.loads(z.read('JOURNAL_REVIEW_HANDOFF/MANIFEST.json'))
        for e in embedded_manifest['files']:
            assert sha(z.read('JOURNAL_REVIEW_HANDOFF/'+e['path'])) == e['sha256']
        for line in z.read('JOURNAL_REVIEW_HANDOFF/SHA256SUMS.txt').decode().splitlines():
            digest, n = line.split('  ', 1)
            assert sha(z.read('JOURNAL_REVIEW_HANDOFF/'+n)) == digest
        assert sha(z.read('JOURNAL_REVIEW_HANDOFF/PAPER_ONLY/journal_final_20260905.pdf')) == pdf['original_sha256']
        for n, digest in lock['files'].items():
            assert sha(z.read('JOURNAL_REVIEW_HANDOFF/PAPER_ONLY/'+n)) == digest
    digest = sha(ZIP.read_bytes())
    with Path(str(ZIP)+'.sha256').open('x') as f:
        f.write(digest+'  '+ZIP.name+'\n')
    summary = {
        'status': 'PASS', 'verified_utc': datetime.now(timezone.utc).isoformat(),
        'zip_path': str(ZIP), 'zip_bytes': ZIP.stat().st_size, 'zip_sha256': digest,
        'zip_file_count': len(names), 'uncompressed_bytes': sum((PACK/n).stat().st_size for n in names),
        'manifest_content_file_count': len(records),
        'checks': {'reopened_zip': True, 'crc_all_members': True, 'exact_allowlist': True,
                   'no_duplicate_or_unsafe_paths_or_symlinks': True,
                   'all_entry_bytes_match_filesystem': True, 'all_manifest_and_sha256sums_match': True,
                   'all_copies_match_originals': True, 'embedded_pdf_matches_baseline': True,
                   'all_19_paper_lock_hashes_unchanged': True, 'table_rows': rows,
                   'reserved_data_not_opened_or_included': True, 'existing_tracked_diff_empty': True},
        'preservation_scope': 'Targeted source/copy verification and tracked diff; no full archive rehash or global access-audit claim',
        'source_head_unchanged': git('rev-parse', 'HEAD').strip()==HEAD,
        'new_ckks': 0, 'retraining': 0, 'new_Cprime_activation': False,
        'remote_push_or_upload': False,
        'command': 'PYTHONDONTWRITEBYTECODE=1 python3 scripts/package_journal_review_v1.py',
    }
    write_json(RUN / 'PACKAGE_VERIFICATION.json', summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
