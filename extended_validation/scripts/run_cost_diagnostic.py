#!/usr/bin/env python3
"""Execute the fixed DP03_COST_DIAG_V1 budget using frozen parent inputs."""
import argparse
import datetime as dt
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import random
import shutil
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from deciprotect.cost_diagnostic import ARMS, BackendFailure, execute_arm


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, obj):
    with Path(p).open('x') as f:
        json.dump(obj, f, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        f.write('\n')


def environment():
    cpu = [int(x) for x in Path('/proc/stat').read_text().splitlines()[0].split()[1:9]]
    mem = {line.split(':')[0]: line.split(':')[1].strip() for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemAvailable:', 'MemTotal:'))}
    return {'utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'loadavg': os.getloadavg(),
            'cpu_ticks_user_nice_system_idle_iowait_irq_softirq_steal': cpu, 'memory': mem,
            'cpu_count': os.cpu_count()}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--run-id',required=True)
    ap.add_argument('--binary',required=True)
    args=ap.parse_args()
    if not args.run_id.replace('_','').replace('-','').isalnum():
        raise SystemExit('Invalid run ID')
    protocol_path=ROOT/'protocols/DP03_COST_DIAG_V1.json'
    protocol=json.loads(protocol_path.read_text())
    run=ROOT/'results'/args.run_id
    run.mkdir()
    for name in ('inputs','native','calls','trials','logs','as_run_source'):
        (run/name).mkdir()
    binary=Path(args.binary).resolve()
    parents={}; parent_hashes={}
    for seed in protocol['training_seeds']:
        model_id=f'spambase__logistic_linear__{seed}'
        parent=ROOT/protocol['parent_run']/model_id
        lock=json.loads((parent/'deployment_lock.json').read_text())
        model=json.loads((parent/'model.json').read_text())
        low_input=json.loads((parent/'inputs/test_s18.json').read_text())
        high_input=json.loads((parent/'inputs/test_s30.json').read_text())
        assert low_input['inputs']==high_input['inputs']
        assert low_input['layers']==high_input['layers']==model['layers']
        assert sha(parent/'model.json')==lock['model_sha256']
        assert lock['low_scale']==18 and lock['high_scale']==30
        data=json.loads((parent/'data_manifest.json').read_text())
        parent_outputs={s:json.loads((parent/f'test_s{s}.json').read_text()) for s in (18,30)}
        parents[seed]={'model_id':model_id,'layers':model['layers'],'inputs':np.asarray(low_input['inputs']),
                       'input_ids':data['split_source_row_ids']['test'],'lock':lock,'outputs':parent_outputs}
        assert parents[seed]['inputs'].shape==(842,57)
        for rel in ('model.json','deployment_lock.json','data_manifest.json','plaintext.json',
                    'inputs/test_s18.json','inputs/test_s30.json','test_s18.json','test_s30.json'):
            p=parent/rel;parent_hashes[str(p.relative_to(ROOT))]=sha(p)
    blocks=[]
    for seed in protocol['training_seeds']:
        for repeat in range(protocol['key_repetitions']):
            for size in protocol['batch_sizes']:
                for offset in range(0,842,size):
                    blocks.append({'seed':seed,'repeat':repeat,'batch_size':size,'offset':offset,'stop':min(offset+size,842)})
    rng=random.Random(protocol['order_seed']);rng.shuffle(blocks)
    permutations=list(itertools.permutations(ARMS));rng.shuffle(permutations)
    schedule=[]
    for n, block in enumerate(blocks):
        for position, arm in enumerate(permutations[n%6]):
            schedule.append(dict(block,arm=arm,block_order=n,arm_position=position,trial_order=len(schedule)))
    assert len(schedule)==protocol['budget']['planned_arm_trials']
    write(run/'execution_order.json',schedule)
    source_files=[protocol_path,Path(__file__),ROOT/'src/deciprotect/decision.py',ROOT/'src/deciprotect/cost_diagnostic.py',
                  *sorted((ROOT/'cmd/deciprotect-ckks').glob('*.go')),ROOT/'go.mod',ROOT/'go.sum',ROOT/'requirements-lock.txt']
    for p in source_files:
        dest=run/'as_run_source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    start_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    write(run/'run_binding.json',{'protocol_sha256':sha(protocol_path),'execution_order_sha256':sha(run/'execution_order.json'),
        'source_head':start_head,'source_worktree_patch_recorded':True,'sources':{str(p.relative_to(ROOT)):sha(p) for p in source_files},
        'parent_artifacts':parent_hashes,'binary_sha256':sha(binary),'binary_path':str(binary.relative_to(ROOT)),
        'command':sys.argv,'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),
        'go_version':subprocess.check_output(['go','version'],text=True).strip(),
        'thread_environment':{k:os.environ.get(k) for k in ('GOMAXPROCS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','PYTHONDONTWRITEBYTECODE')},
        'started_environment':environment(),'confirmatory':False,'risk_admission':False})
    (run/'source_worktree.patch').write_bytes(subprocess.check_output(['git','diff','--binary','HEAD','--','cmd/deciprotect-ckks','src/deciprotect'],cwd=ROOT))
    native_calls=0;finished=0;failed_trials=0;started=time.monotonic()
    for item in schedule:
        if time.monotonic()-started>protocol['budget']['total_wall_budget_seconds']:
            break
        parent=parents[item['seed']]
        batch_id=f's{item["seed"]}_r{item["repeat"]}_b{item["batch_size"]}_o{item["offset"]}'
        context={'original_batch_id':batch_id,'model_id':parent['model_id'],'seed':str(item['seed']),
                 'repeat':str(item['repeat']),'batch_size':str(item['batch_size']),'offset':str(item['offset']),
                 'client_owner_id':f'local_pilot_client_s{item["seed"]}'}
        pre=environment()

        def invoke(stage, values, metadata):
            nonlocal native_calls
            native_calls+=1
            assert native_calls<=protocol['budget']['max_native_calls']
            scale=18 if stage=='low' else 30
            call_id=f't{item["trial_order"]:04d}_{stage}'
            request=run/'inputs'/f'{call_id}.json';output=run/'native'/f'{call_id}.json'
            t=time.perf_counter_ns()
            write(request,{'layers':parent['layers'],'inputs':np.asarray(values).tolist(),'scale':scale,'repeats':1,'context':metadata})
            input_json_ms=(time.perf_counter_ns()-t)/1e6
            command=[str(binary),'--cost-diagnostic','--input',str(request),'--output',str(output)]
            t=time.perf_counter_ns();returncode=None;exception=None
            try:
                with (run/'logs'/f'{call_id}.log').open('x') as log:
                    completed=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=protocol['budget']['native_timeout_seconds'])
                returncode=completed.returncode
            except subprocess.TimeoutExpired as exc:
                exception=str(exc)
            process_ms=(time.perf_counter_ns()-t)/1e6
            t=time.perf_counter_ns()
            native=json.loads(output.read_text()) if output.exists() else None
            output_json_ms=(time.perf_counter_ns()-t)/1e6
            success=returncode==0 and native is not None and native['status']=='SUCCESS'
            if success:
                assert native['request_sha256']==sha(request)
                p=native['parameter'];expected=parent['outputs'][scale]
                assert all(p[k]==expected[k] for k in ('q','p','log_n','scale','slots'))
                assert len(native['client_decrypted_logits'])==len(values)
            record={'call_id':call_id,'status':'SUCCESS' if success else 'EXECUTION_FAILURE','context':metadata,
                'stage':stage,'scale':scale,'valid_rows':len(values),'command':command,'return_code':returncode,'exception':exception,
                'input_json_write_ms':input_json_ms,'process_wall_ms':process_ms,'output_json_read_ms':output_json_ms,
                'request_sha256':sha(request),'native_output_sha256':sha(output) if output.exists() else None,'native':native}
            write(run/'calls'/f'{call_id}.json',record)
            if not success: raise BackendFailure('native execution failed',record)
            return record

        radius=parent['lock']['radius']
        result=execute_arm(parent['inputs'][item['offset']:item['stop']],parent['input_ids'][item['offset']:item['stop']],
            context,item['arm'],radius['18'],radius['30'],invoke)
        result.update(schedule=item,environment_before=pre,environment_after=environment())
        write(run/'trials'/f't{item["trial_order"]:04d}.json',result)
        finished+=1;failed_trials+=int(any(e['execution_failed'] for e in result['events']))
        if finished%12==0:
            print(f'COST_PROGRESS {finished}/{len(schedule)} arm trials; native calls={native_calls}; failed arm trials={failed_trials}',flush=True)
    write(run/'execution_summary.json',{'status':'COMPLETED' if finished==len(schedule) else 'BUDGET_STOP',
        'planned_arm_trials':len(schedule),'completed_arm_trials':finished,'native_calls':native_calls,
        'failed_arm_trials':failed_trials,'unexecuted_schedule_entries':schedule[finished:],
        'wall_seconds':time.monotonic()-started,'finished_environment':environment(),'risk_admission':False})
    # Verify only bound parent files, never the complete predecessor archive.
    assert all(sha(ROOT/p)==h for p,h in parent_hashes.items())
    write(run/'cost_evidence_manifest.json',{str(p.relative_to(run)):sha(p) for p in sorted(run.rglob('*')) if p.is_file()})
    print(f'COST_FINISHED {finished} arm trials, {native_calls} native calls',flush=True)


if __name__=='__main__':main()
