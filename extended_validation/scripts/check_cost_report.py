#!/usr/bin/env python3
"""Read-only check of frozen raw DP03 evidence and its published numeric derivation."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from verify_cost_diagnostic import ROOT, DEFAULT_RUN, require, verify


def main():
    report=ROOT/'docs/research'/DEFAULT_RUN
    for line in (report/'DERIVED_SHA256SUMS').read_text().splitlines():
        expected,name=line.split('  ',1)
        require(hashlib.sha256((report/name).read_bytes()).hexdigest()==expected, f'Derived payload mismatch: {name}')
    summary,_,_,trials,_=verify(ROOT/'results'/DEFAULT_RUN)
    require(summary==json.loads((report/'summary.json').read_text()), 'Recomputed summary differs from published derivation')
    windows=defaultdict(int)
    for trial in trials:
        if trial['batch_size']==128 and trial['arm']=='two_stage':
            windows[trial['seed'],trial['repeat'],trial['offset']//256]+=trial['high_batches_completed']
    histogram=Counter(windows.values())
    require(histogram=={0:22,1:6,2:8}, 'Proposed adjacent-two-window occupancy statement differs')
    print(json.dumps(dict(status='PASS',raw_payload_files=summary['verified_payload_files'],
                          bound_parent_files=summary['verified_bound_parent_files'],
                          arm_trials=summary['arm_trials'],native_calls=summary['native_calls'],
                          row_observations=summary['row_observations'],derived_numeric_files=6,
                          proposed_two_batch_windows=len(windows),
                          conditional_batch_count_bound=sum(v>0 for v in windows.values()),
                          queue_experiment_executed=False)))


if __name__=='__main__': main()
