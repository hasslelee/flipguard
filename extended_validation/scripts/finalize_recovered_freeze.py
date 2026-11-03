#!/usr/bin/env python3
"""Admit the verified historical archive after documented live-state recovery.

Archive integrity, restored operational files, and Git bookkeeping drift are
separate conclusions. Never label the entire live .git directory unchanged.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/home/ckks2/flipguard')
DEST = ROOT / 'archive/freeze_20260905'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def git(*args):
    return subprocess.check_output(['git', '-C', str(SOURCE), *args],
        env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})


def durable_write(path, data):
    with path.open('x') as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


def main():
    final = ROOT / 'baseline/FREEZE_MANIFEST.json'
    assert not final.exists(), 'A completed freeze must never be overwritten'
    log = DEST / 'restored_verification_retry1.log'
    log_text = log.read_text()
    assert 'Every archive payload verified; checking source state' in log_text
    assert log_text.rstrip().endswith('AssertionError: Source inventory changed')
    # The streaming verifier reached this line only after checking membership,
    # all original SHA-256 payloads, symlink targets, modes and hard-link targets.
    raw_check = read(ROOT / 'docs/review/SOURCE_STATE_FINAL.json')
    drift = read(ROOT / 'docs/review/GIT_METADATA_DRIFT.json')
    recovery = read(ROOT / 'docs/review/OPERATIONAL_STATE_RECOVERY.json')
    assert raw_check['entries'] == 1274177 and not raw_check['removed']
    assert recovery['status'] == 'RESTORED_TO_INITIAL_INVENTORY'
    repaired = {x['path'] for x in recovery['checks']}
    assert set(drift['outside_git_metadata']) == repaired
    assert set(drift['changed_payloads']) <= repaired
    assert set(drift['changed_modes_or_sizes']) <= repaired
    assert all(p.startswith('.git/refs/codex/turn-diffs/captures/') for p in raw_check['added'])
    for row in drift['metadata_checks']:
        if row['path'].startswith('.git/'):
            assert row['same_sha256'] and row['same_size'] and row['same_mode']
    for row in recovery['checks']:
        assert sha(SOURCE / row['path']) == row['original_sha256']
    services = read(ROOT / 'docs/review/LEGACY_AUTOSTART_STOPPED.json')
    for row in services['services']:
        text = subprocess.check_output(['systemctl', '--user', 'show', row['unit'],
            '-p', 'ActiveState', '-p', 'UnitFileState'], text=True)
        assert 'ActiveState=inactive' in text and 'UnitFileState=enabled' not in text
    state = read(DEST / 'freeze_state.json')
    assert git('rev-parse', 'HEAD').decode().strip() == state['head']
    assert git('branch', '--show-current').decode().strip() == state['branch']
    assert git('remote', '-v').decode() == state['remote']
    assert git('status', '--porcelain=v1', '-z', '--untracked-files=all') == (DEST / 'git_status_before.bin').read_bytes()
    assert git('diff', '--binary', 'HEAD') == (DEST / 'git_diff_before.patch').read_bytes()
    archive = DEST / 'flipguard_complete_restored.tar.zst'
    checksum = (DEST / 'restored_archive.sha256').read_text().split()
    assert len(checksum) == 2 and len(checksum[0]) == 64
    assert checksum[1] == str(archive.relative_to(ROOT))
    pdf_hash = sha(ROOT / 'baseline/journal_final_20260905.pdf')
    assert pdf_hash == sha(Path('/home/ckks2/Downloads/정보보호학회논문지_이기찬_0905.pdf'))
    inventory = read(ROOT / 'docs/review/WORKSPACE_INVENTORY.json')
    resolution = {
        'status': 'RESEARCH_PAYLOAD_RESTORED_GIT_BOOKKEEPING_DRIFT_RECORDED',
        'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'full_inventory_check': 'docs/review/SOURCE_STATE_FINAL.json',
        'operational_files_restored': len(repaired),
        'scientific_artifact_or_production_code_payload_changes_detected': 0,
        'git_object_mtime_changes_at_full_check': sum(r['path'].startswith('.git/') for r in drift['metadata_checks']),
        'new_codex_capture_refs_at_full_check': raw_check['added'],
        'git_object_payloads_unchanged': True,
        'head_branch_remote_status_diff_unchanged': True,
        'legacy_autostart_services_disabled': len(services['services']),
        'live_git_byte_for_byte_unchanged_claim': False,
        'directory_metadata_and_access_times_in_scope': False,
        'original_archive_payloads_verified': 1274177,
    }
    durable_write(ROOT / 'docs/review/SOURCE_STATE_RESOLUTION.json', resolution)
    state.update(
        status='VERIFIED_ARCHIVE', completed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        entries=1274177,
        inventory={k: {'files': v['entries'], 'bytes': v['logical_bytes']} for k, v in inventory['directories'].items()},
        logical_bytes=sum(v['logical_bytes'] for v in inventory['directories'].values()),
        archive_path=str(archive.relative_to(ROOT)), archive_sha256=checksum[0],
        archive_bytes=archive.stat().st_size,
        manifest_path=str((DEST / 'workspace_manifest.jsonl').relative_to(ROOT)),
        manifest_sha256=sha(DEST / 'workspace_manifest.jsonl'), final_pdf_sha256=pdf_hash,
        archive_payload_verification='Every original regular-file payload, symlink, mode and member matched the initial inventory',
        verification_log=str(log.relative_to(ROOT)), verification_log_sha256=sha(log),
        verification_script_sha256=sha(ROOT / 'scripts/verify_restored_freeze.py'),
        live_source_resolution=resolution,
        storage='Independent local compressed archive, not uploaded and not a separate-device backup',
        generated_cache_incident='967 generated Python cache files quarantined and removed; see docs/review/CACHE_RESTORATION.json',
        reboot_incident='Host reboot interrupted one verification pass and restarted legacy services. Five services were disabled; seven operational files were restored after preserving post-reboot versions.',
        git_bookkeeping='592 original Git-object mtimes changed and one Codex capture ref appeared at the full recheck; object payloads and HEAD/branch/remote/porcelain/diff matched. Internal bookkeeping was not deleted or retimed.',
        superseded_attempt='archive/freeze_20260905/attempt1_with_generated_caches.tar.gz',
        source_final_record='docs/review/SOURCE_STATE_RESOLUTION.json',
    )
    durable_write(DEST / 'freeze_state_verified.json', state)
    durable_write(final, state)
    print(json.dumps({k: v for k, v in state.items() if k not in ['inventory', 'live_source_resolution']}, indent=2))


if __name__ == '__main__':
    main()
