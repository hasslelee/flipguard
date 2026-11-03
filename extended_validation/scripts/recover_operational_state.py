#!/usr/bin/env python3
"""Undo only seven legacy-daemon operational writes, preserving both versions.

The user requested the predecessor to be frozen. Its old user services restarted
on host reboot. They must be disabled before this bounded restoration runs.
Never restore arbitrary files or modify frozen experiment packs with this script.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/home/ckks2/flipguard')
RECOVERY = ROOT / 'archive/operational_state_recovery'
PATHS = {
    'external/v7/status/provider_queue.json',
    'external/v7/status/resource_state.json',
    'external/v7/status/heartbeat.txt',
    'external/v8/status/master_state.json',
    'external/v7/status/resource_samples.csv',
    'external/v8/logs/master_exception.log',
    'external/v7/status/master_state.json',
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    receipt = ROOT / 'docs/review/OPERATIONAL_STATE_RECOVERY.json'
    if receipt.exists():
        raise SystemExit('Refusing to repeat completed operational restoration')
    stopped = json.loads((ROOT / 'docs/review/LEGACY_AUTOSTART_STOPPED.json').read_text())
    for row in stopped['services']:
        state = subprocess.check_output(['systemctl', '--user', 'show', row['unit'],
            '-p', 'ActiveState', '-p', 'UnitFileState'], text=True)
        assert 'ActiveState=inactive' in state and 'UnitFileState=enabled' not in state
    original = {}
    for line in (ROOT / 'archive/freeze_20260905/workspace_manifest.jsonl').open():
        row = json.loads(line)
        if row['path'] in PATHS:
            original[row['path']] = row
    assert set(original) == PATHS
    before = {r['path']: r for r in json.loads((RECOVERY / 'post_reboot_manifest.json').read_text())}
    # Validate every original and quarantined payload before making any repair.
    for rel in sorted(PATHS):
        source = SOURCE / rel
        staged = RECOVERY / 'staged/flipguard' / rel
        assert source.is_file() and not source.is_symlink()
        assert original[rel]['kind'] == 'file'
        assert sha(staged) == original[rel]['sha256'], rel
        assert sha(source) == before[rel]['post_reboot_sha256'], 'Writer still active: ' + rel
        assert sha(RECOVERY / 'post_reboot' / rel) == before[rel]['post_reboot_sha256']
    checks = []
    for rel in sorted(PATHS):
        source = SOURCE / rel
        staged = RECOVERY / 'staged/flipguard' / rel
        replacement = staged.with_name(staged.name + '.verified_replacement')
        shutil.copyfile(staged, replacement)
        os.chmod(replacement, original[rel]['mode'] & 0o7777)
        os.utime(replacement, ns=(source.stat().st_atime_ns, original[rel]['mtime_ns']))
        with replacement.open('rb') as f:
            os.fsync(f.fileno())
        # Atomic replacement cannot modify another hard-link path's payload.
        os.replace(replacement, source)
        directory_fd = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        st = source.stat()
        assert sha(source) == original[rel]['sha256']
        assert (st.st_size, st.st_mode, st.st_mtime_ns) == (
            original[rel]['size'], original[rel]['mode'], original[rel]['mtime_ns'])
        checks.append({'path': rel, 'original_sha256': original[rel]['sha256'],
                       'post_reboot_sha256': before[rel]['post_reboot_sha256'],
                       'restored_sha256': sha(source), 'original_metadata_restored': True})
    result = {'status': 'RESTORED_TO_INITIAL_INVENTORY',
        'completed_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'scope': 'Exactly seven legacy operational status/log files; scientific results, manuscript and production code were not rewritten',
        'reason': 'Restore the user-designated freeze after old services restarted on host reboot',
        'post_reboot_versions_preserved': 'archive/operational_state_recovery/post_reboot',
        'services_record': 'docs/review/LEGACY_AUTOSTART_STOPPED.json',
        'git_object_timestamps_or_capture_refs_modified_by_recovery': False,
        'checks': checks}
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'checks'}, indent=2))


if __name__ == '__main__':
    main()
