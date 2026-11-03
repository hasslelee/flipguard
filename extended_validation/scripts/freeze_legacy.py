#!/usr/bin/env python3
"""Preserve the complete local predecessor without writing to it.

Archives may contain local credentials/configuration: archive/ is NEVER pushed.
Run once. Manifest + full tar payload verification detect inconsistent snapshots.
"""
import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
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
    return subprocess.check_output(['git', '-C', str(SOURCE), *args], env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})


def main():
    manifest = DEST / 'workspace_manifest.jsonl'
    archive = DEST / 'flipguard_complete.tar.gz'
    if manifest.exists() or archive.exists():
        raise SystemExit('Refusing to overwrite an existing freeze attempt')
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    before_status = git('status', '--porcelain=v1', '-z', '--untracked-files=all')
    (DEST / 'git_status_before.bin').write_bytes(before_status)
    (DEST / 'git_diff_before.patch').write_bytes(git('diff', '--binary', 'HEAD'))
    state = {'started_at_utc': started, 'source': str(SOURCE), 'head': git('rev-parse', 'HEAD').decode().strip(),
             'branch': git('branch', '--show-current').decode().strip(), 'remote': git('remote', '-v').decode(),
             'status': 'IN_PROGRESS', 'all_workspace_bytes_included': True}
    (DEST / 'freeze_state.json').write_text(json.dumps(state, indent=2))
    entries = {}
    by_top = collections.defaultdict(lambda: {'files': 0, 'bytes': 0})
    with manifest.open('x') as out:
        for parent, dirs, files in os.walk(SOURCE, followlinks=False):
            dirs.sort()
            names = sorted(files + [d for d in dirs if Path(parent, d).is_symlink()])
            for name in names:
                p = Path(parent, name)
                rel = p.relative_to(SOURCE).as_posix()
                st = p.lstat()
                row = {'path': rel, 'size': st.st_size, 'mode': st.st_mode, 'mtime_ns': st.st_mtime_ns}
                if p.is_symlink():
                    row.update(kind='symlink', target=os.readlink(p))
                elif p.is_file():
                    row.update(kind='file', sha256=sha_file(p))
                    after = p.stat()
                    if (st.st_size, st.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise RuntimeError(f'File changed while hashing: {rel}')
                else:
                    raise RuntimeError(f'Unsupported special file: {rel}')
                entries[rel] = row
                by_top[rel.split('/')[0]]['files'] += 1
                by_top[rel.split('/')[0]]['bytes'] += st.st_size
                out.write(json.dumps(row, ensure_ascii=False) + '\n')
                if len(entries) % 20000 == 0:
                    print(f'Hashed {len(entries)} entries', flush=True)
    print(f'Manifest complete: {len(entries)} entries; archiving', flush=True)
    with (DEST / 'archive_creation.log').open('x') as log:
        subprocess.run(['tar', '-I', 'gzip -1', '-cf', str(archive), '-C', str(SOURCE.parent), SOURCE.name],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    print('Verifying every archived file against the manifest', flush=True)
    seen = set()
    with tarfile.open(archive, 'r|gz') as tf:
        for member in tf:
            if member.isdir():
                continue
            rel = str(Path(member.name).relative_to(SOURCE.name))
            expected = entries[rel]
            if member.issym():
                assert expected['kind'] == 'symlink' and expected['target'] == member.linkname, rel
            elif member.islnk():
                target = str(Path(member.linkname).relative_to(SOURCE.name))
                assert expected['sha256'] == entries[target]['sha256'], rel
            elif member.isfile():
                h = hashlib.sha256()
                f = tf.extractfile(member)
                for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
                    h.update(block)
                assert h.hexdigest() == expected['sha256'], rel
            else:
                raise RuntimeError(f'Unexpected archive entry: {member.name}')
            seen.add(rel)
    assert seen == set(entries), 'Archive membership mismatch'
    assert git('status', '--porcelain=v1', '-z', '--untracked-files=all') == before_status, 'Source Git state changed'
    state.update(status='VERIFIED', completed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                 entries=len(entries), inventory=dict(by_top), manifest_sha256=sha_file(manifest),
                 archive_sha256=sha_file(archive), archive_bytes=archive.stat().st_size,
                 final_pdf_sha256=sha_file(ROOT / 'baseline/journal_final_20260905.pdf'),
                 verification='Every archived regular-file payload and symlink matched; Git status unchanged',
                 storage='Local independent compressed copy; no hard links to source; no original files changed')
    (DEST / 'freeze_state.json').write_text(json.dumps(state, indent=2, ensure_ascii=False) + '\n')
    (ROOT / 'baseline/FREEZE_MANIFEST.json').write_text(json.dumps(state, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({k: v for k, v in state.items() if k != 'inventory'}, indent=2), flush=True)


if __name__ == '__main__':
    main()
