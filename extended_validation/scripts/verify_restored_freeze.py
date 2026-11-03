#!/usr/bin/env python3
"""Verify the restored archive against the original pre-research inventory.

Read-only for the predecessor. Preserve the superseded attempt and its incident
records. This verifier never generates or modifies predecessor bytecode.
"""
import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/home/ckks2/flipguard')
DEST = ROOT / 'archive/freeze_20260905'


def sha_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def git(*args):
    return subprocess.check_output(
        ['git', '-C', str(SOURCE), *args],
        env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})


def progress(message):
    print(message, flush=True)
    try:
        os.fsync(sys.stdout.fileno())
    except OSError:
        pass  # Interactive stdout need not be a regular file.


def main():
    final = ROOT / 'baseline/FREEZE_MANIFEST.json'
    if final.exists():
        raise SystemExit('Refusing to overwrite a completed freeze manifest')
    manifest = DEST / 'workspace_manifest.jsonl'
    archive = DEST / 'flipguard_complete_restored.tar.zst'
    state = json.loads((DEST / 'freeze_state.json').read_text())
    entries = {}
    inventory = collections.defaultdict(lambda: {'files': 0, 'bytes': 0})
    for line in manifest.open():
        row = json.loads(line)
        entries[row['path']] = row
        bucket = inventory[row['path'].split('/')[0]]
        bucket['files'] += 1
        bucket['bytes'] += row['size']
    progress(f'Loaded original inventory: {len(entries)} entries')
    seen = set()
    with subprocess.Popen(['zstd', '-dc', str(archive)], stdout=subprocess.PIPE) as process:
        with tarfile.open(fileobj=process.stdout, mode='r|') as tf:
            for member in tf:
                # Streamed regular payloads do not need prior TarInfo objects.
                # Hard links are checked using the original inventory below.
                tf.members.clear()
                if member.isdir():
                    continue
                rel = str(Path(member.name).relative_to(SOURCE.name))
                assert rel not in seen, f'Duplicate archive entry: {rel}'
                expected = entries[rel]
                assert member.mode == expected['mode'] & 0o7777, rel
                if member.issym():
                    assert expected['kind'] == 'symlink', rel
                    assert expected['target'] == member.linkname, rel
                elif member.islnk():
                    target = str(Path(member.linkname).relative_to(SOURCE.name))
                    assert expected['kind'] == entries[target]['kind'] == 'file', rel
                    assert expected['sha256'] == entries[target]['sha256'], rel
                elif member.isfile():
                    assert expected['kind'] == 'file' and expected['size'] == member.size, rel
                    h = hashlib.sha256()
                    with tf.extractfile(member) as f:
                        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
                            h.update(block)
                    assert h.hexdigest() == expected['sha256'], rel
                else:
                    raise RuntimeError(f'Unexpected archive entry: {member.name}')
                seen.add(rel)
                if len(seen) % 100000 == 0:
                    progress(f'Archive verified: {len(seen)} entries')
        assert process.wait() == 0, 'zstd decompression failed'
    assert seen == set(entries), 'Archive membership differs from original inventory'
    progress('Every archive payload verified; checking source state')
    current = set()
    changed = []
    for parent, dirs, files in os.walk(SOURCE, followlinks=False):
        for name in files + [d for d in dirs if Path(parent, d).is_symlink()]:
            p = Path(parent, name)
            rel = p.relative_to(SOURCE).as_posix()
            current.add(rel)
            row = entries.get(rel)
            if row is None:
                continue
            st = p.lstat()
            if (st.st_size, st.st_mode, st.st_mtime_ns) != (row['size'], row['mode'], row['mtime_ns']):
                changed.append(rel)
            if row['kind'] == 'symlink' and os.readlink(p) != row['target']:
                changed.append(rel)
    source_check = {
        'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'entries': len(entries), 'metadata_changed': sorted(set(changed)),
        'added': sorted(current - set(entries)), 'removed': sorted(set(entries) - current),
        'scope': 'Regular files and symlinks; atime and directory metadata excluded',
        'payload_verification': 'Every archive payload matched the original SHA-256 inventory',
    }
    source_check['status'] = 'UNCHANGED' if not any(source_check[k] for k in ['metadata_changed', 'added', 'removed']) else 'CHANGED'
    (ROOT / 'docs/review/SOURCE_STATE_FINAL.json').write_text(json.dumps(source_check, indent=2) + '\n')
    assert source_check['status'] == 'UNCHANGED', 'Source inventory changed'
    assert git('status', '--porcelain=v1', '-z', '--untracked-files=all') == (DEST / 'git_status_before.bin').read_bytes(), 'Source Git status changed'
    assert git('diff', '--binary', 'HEAD') == (DEST / 'git_diff_before.patch').read_bytes(), 'Source diff changed'
    assert git('rev-parse', 'HEAD').decode().strip() == state['head'], 'Source HEAD changed'
    assert git('branch', '--show-current').decode().strip() == state['branch'], 'Source branch changed'
    assert git('remote', '-v').decode() == state['remote'], 'Source remote changed'
    pdf_hash = sha_file(ROOT / 'baseline/journal_final_20260905.pdf')
    assert pdf_hash == sha_file('/home/ckks2/Downloads/정보보호학회논문지_이기찬_0905.pdf'), 'Final PDF copy differs'
    progress('Source state and PDF unchanged; hashing completed archive')
    state.update(
        status='VERIFIED', completed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        entries=len(entries), inventory=dict(inventory),
        logical_bytes=sum(row['size'] for row in entries.values()),
        manifest_path=str(manifest.relative_to(ROOT)), manifest_sha256=sha_file(manifest),
        archive_path=str(archive.relative_to(ROOT)), archive_sha256=sha_file(archive),
        archive_bytes=archive.stat().st_size, final_pdf_sha256=pdf_hash,
        verification='Every archived file payload, symlink, mode and membership matched the original inventory; source file metadata, membership, Git status, diff, HEAD, branch and remote unchanged',
        storage='Independent local compressed archive; not uploaded to GitHub; not a separate-device disaster-recovery backup',
        recovered_incident='Version inspection generated 967 new Python cache files. They were quarantined, hash-checked and removed. Existing source files were never modified. Directory metadata and access times are outside the preservation claim.',
        superseded_attempt='archive/freeze_20260905/attempt1_with_generated_caches.tar.gz',
        incident_record='docs/review/CACHE_RESTORATION.json',
        source_final_record='docs/review/SOURCE_STATE_FINAL.json',
        infrastructure_retry_record='docs/review/VERIFICATION_INTERRUPTION.json',
    )
    payload = json.dumps(state, indent=2, ensure_ascii=False) + '\n'
    for output in (DEST / 'freeze_state_verified.json', final):
        with output.open('x') as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
    progress(json.dumps({k: v for k, v in state.items() if k != 'inventory'}, indent=2))


if __name__ == '__main__':
    main()
