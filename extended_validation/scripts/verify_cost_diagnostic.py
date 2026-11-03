#!/usr/bin/env python3
"""Read-only DP03 cost evidence audit; optionally create a NEW derived directory.

Reconstruct binary decisions independently of the operational gate/orchestrator.
Plaintext reference scores and labels are loaded only here, after measurement.
No CKKS invocation, training, archive traversal, or completed-result writes.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import itertools
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = 'dp03_cost_diag_v1_20260905'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def binary_gate(rows, radius=None):
    out = []
    for row in rows:
        require(len(row) == 1, 'Only the frozen binary linear model is supported')
        z = row[0]
        out.append(int(z >= 0) if radius is None or z-radius >= 0 or z+radius < 0 else -1)
    return out


def csv_write(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def verify(run):
    manifest = read(run/'cost_evidence_manifest.json')
    actual = {str(p.relative_to(run)) for p in run.rglob('*') if p.is_file()}
    require(actual == set(manifest) | {'cost_evidence_manifest.json'}, 'Manifest membership mismatch')
    for path, expected in manifest.items():
        require(sha(run/path) == expected, f'Payload mismatch: {path}')
    binding = read(run/'run_binding.json')
    for path, expected in binding['parent_artifacts'].items():
        require(sha(ROOT/path) == expected, f'Bound parent changed: {path}')
    for path, expected in binding['sources'].items():
        require(sha(run/'as_run_source'/path) == expected, f'As-run source mismatch: {path}')
    protocol_path = run/'as_run_source/protocols/DP03_COST_DIAG_V1.json'
    require(sha(protocol_path) == binding['protocol_sha256'], 'Protocol binding mismatch')
    require(sha(ROOT/'protocols/DP03_COST_DIAG_V1.json') == binding['protocol_sha256'], 'Frozen protocol changed')
    p = read(protocol_path)
    schedule = read(run/'execution_order.json')
    require(sha(run/'execution_order.json') == binding['execution_order_sha256'], 'Order binding mismatch')
    blocks = [dict(seed=s, repeat=k, batch_size=b, offset=o, stop=min(o+b,842))
              for s in p['training_seeds'] for k in range(p['key_repetitions'])
              for b in p['batch_sizes'] for o in range(0,842,b)]
    rng = random.Random(p['order_seed']); rng.shuffle(blocks)
    permutations = list(itertools.permutations(p['arms'])); rng.shuffle(permutations)
    planned = []
    for n, block in enumerate(blocks):
        for pos, arm in enumerate(permutations[n % 6]):
            planned.append(dict(block, arm=arm, block_order=n, arm_position=pos, trial_order=len(planned)))
    require(schedule == planned, 'Actual schedule differs from protocol')
    execution = read(run/'execution_summary.json')
    require(execution['status'] == 'COMPLETED' and not execution['unexecuted_schedule_entries'], 'Incomplete budget: do not claim complete comparison')
    parents = {}
    for seed in p['training_seeds']:
        base = ROOT/p['parent_run']/f'spambase__logistic_linear__{seed}'
        low = read(base/'inputs/test_s18.json'); high = read(base/'inputs/test_s30.json')
        lock = read(base/'deployment_lock.json'); model = read(base/'model.json')
        reference = read(base/'plaintext.json')['test']
        ids = read(base/'data_manifest.json')['split_source_row_ids']['test']
        require(ids == reference['source_row_ids'], 'Oracle/input order mismatch')
        require(low['inputs'] == high['inputs'] and len(ids) == 842, 'Parent input mismatch')
        require(low['layers'] == high['layers'] == model['layers'], 'Parent model mismatch')
        require(sha(base/'model.json') == lock['model_sha256'], 'Model lock mismatch')
        parents[seed] = dict(inputs=low['inputs'], ids=ids, layers=model['layers'], lock=lock,
                             reference=binary_gate(reference['logits']), labels=reference['labels'],
                             parameters={s:read(base/f'test_s{s}.json') for s in (18,30)})
    rows = []; calls = []; trial_rows = []; totals = {}; group_totals = {}; keys = set(); param_ids = defaultdict(set)
    key_groups = defaultdict(list)
    env_load = []; busy_fractions = []; native_seen = set()
    for item in schedule:
        tid = f't{item["trial_order"]:04d}'
        t = read(run/'trials'/f'{tid}.json')
        require(t['schedule'] == item, 'Trial order mismatch')
        require(t['network_ms'] is None and t['queue_wait_ms'] is None and t['risk_admission'] is False, 'Invalid operational cost/risk scope')
        parent = parents[item['seed']]; off = item['offset']; stop = item['stop']; arm = item['arm']
        x = parent['inputs'][off:stop]; ids = parent['ids'][off:stop]; radius = parent['lock']['radius']
        batchid = f's{item["seed"]}_r{item["repeat"]}_b{item["batch_size"]}_o{off}'
        expected_context = dict(original_batch_id=batchid, model_id=f'spambase__logistic_linear__{item["seed"]}',
                                seed=str(item['seed']), repeat=str(item['repeat']), batch_size=str(item['batch_size']),
                                offset=str(off), client_owner_id=f'local_pilot_client_s{item["seed"]}')
        require(t['context'] == expected_context and t['arm'] == arm, 'Trial context mismatch')
        require(len(t['events']) == len(x), 'Wrong event denominator')
        by_stage = {c['stage']:c for c in t['calls']}
        require(len(by_stage) == len(t['calls']), 'Duplicate stage call')
        pending = []
        if arm == 'two_stage':
            require('low' in by_stage, 'Missing low call')
            low_decisions = binary_gate(by_stage['low']['native']['client_decrypted_logits'], radius['18'])
            pending = [i for i,d in enumerate(low_decisions) if d == -1]
            require(set(by_stage) == ({'low','high'} if pending else {'low'}), 'Retry call selection mismatch')
            final = low_decisions.copy()
            if pending:
                hd = binary_gate(by_stage['high']['native']['client_decrypted_logits'], radius['30'])
                require(len(hd) == len(pending), 'High output length mismatch')
                for i,d in zip(pending,hd): final[i] = d
        else:
            require(set(by_stage) == {'high'}, 'Fixed-high arm must execute only high')
            final = binary_gate(by_stage['high']['native']['client_decrypted_logits'], None if arm == 'fixed_high' else radius['30'])
        require(len(final) == len(x), 'Decision length mismatch')
        components = Counter(); native_sum = 0.; high_batches = 0; high_rows = 0
        for stage, call in by_stage.items():
            cid = call['call_id']; native = call['native']; counts = native['cost']['counts']; ms = native['cost']['milliseconds']
            require(cid == f'{tid}_{stage}' and cid not in native_seen, 'Native call identity mismatch')
            native_seen.add(cid)
            require(read(run/'calls'/f'{cid}.json') == call, 'Nested/standalone call mismatch')
            require(read(run/'native'/f'{cid}.json') == native, 'Nested/standalone native mismatch')
            require(call['status'] == native['status'] == 'SUCCESS' and call['return_code'] == 0 and call['exception'] is None,
                    'Execution failure: successful-run cost reconstruction is not applicable; retain and audit failure separately')
            require(sha(run/'native'/f'{cid}.json') == call['native_output_sha256'], 'Native output hash mismatch')
            request_path = run/'inputs'/f'{cid}.json'; request = read(request_path)
            require(sha(request_path) == call['request_sha256'] == native['request_sha256'], 'Request hash mismatch')
            ctx = dict(expected_context, arm=arm, stage=stage)
            require(call['context'] == request['context'] == native['context'] == ctx, 'Native context mismatch')
            values = [x[i] for i in pending] if stage == 'high' and arm == 'two_stage' else x
            require(request['inputs'] == values and request['layers'] == parent['layers'], 'Original client retry/model input mismatch')
            scale = 18 if stage == 'low' else 30; params = native['parameter']; slots = 2048 if stage == 'low' else 4096
            require(request['scale'] == call['scale'] == scale and request['repeats'] == 1, 'Scale/key-repeat mismatch')
            require(all(params[k] == parent['parameters'][scale][k] for k in ('q','p','log_n','scale','slots')), 'Frozen parameter mismatch')
            ph = hashlib.sha256(json.dumps(params,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
            require(ph == native['parameter_id'], 'Parameter identity mismatch')
            require(len(native['key_context_id']) == 64 and native['key_context_id'] not in keys, 'Fresh-key identity collision/reuse')
            keys.add(native['key_context_id']); param_ids[scale].add(ph)
            expected_counts = dict(valid_rows=len(values), physical_slots_per_ciphertext=slots,
                                   input_ciphertexts=57, input_allocated_slots=57*slots,
                                   input_active_values=57*len(values), input_padding_values=57*(slots-len(values)),
                                   key_pairs_generated=1,relinearization_keys_generated=1,output_ciphertexts=1,
                                   output_decoded_slots=slots,server_evaluations_started=1,server_evaluations_completed=1,
                                   weight_plaintext_encodes=57,ct_pt_multiply=57,ct_add=56,rescale=1,bias_add=1,final_level=0)
            require(all(counts.get(k) == v for k,v in expected_counts.items()), 'Packing/operator count mismatch')
            require(call['valid_rows'] == len(values) == len(native['client_decrypted_logits']), 'Active row mismatch')
            require(all(v is None for v in native['unmeasured'].values()), 'Unmeasured wire/queue costs must remain null')
            residual = native['native_total_ms'] - sum(ms.values())
            require(residual >= -1e-6 and all(v >= 0 for v in ms.values()), 'Native timer partition overlaps')
            outside = call['process_wall_ms'] - native['native_total_ms']
            require(outside >= 0, 'Native total exceeds measured subprocess wall')
            native_sum += native['native_total_ms']
            components['setup_ms'] += sum(ms[k] for k in ('parameter_validation_build_ms','key_generation_ms','client_context_init_ms','server_context_init_ms'))
            components['input_pack_ms'] += ms['client_pack_and_plaintext_allocate_ms']
            components['input_encode_ms'] += ms['client_encode_ms']
            components['input_encrypt_ms'] += ms['client_encrypt_ms']
            components['server_model_prepare_ms'] += ms['server_model_prepare_ms']
            components['homomorphic_ops_ms'] += ms['homomorphic_ops_ms']
            components['decrypt_decode_gate_ms'] += sum(ms[k] for k in ('client_decrypt_ms','client_decode_ms','client_output_allocate_scatter_ms'))
            components['observer_identity_ms'] += ms['observer_key_identity_ms']+ms['observer_parameter_identity_ms']
            components['native_unassigned_ms'] += residual
            components['json_file_io_ms'] += call['input_json_write_ms']+call['output_json_read_ms']
            components['subprocess_outside_native_ms'] += outside
            if stage == 'high': high_batches += 1; high_rows += len(values)
            if arm == 'two_stage' and stage == 'high':
                key_groups[item['seed'],item['repeat'],item['batch_size']].append((cid,len(values),native['key_context_id']))
            calls.append(dict(trial_id=tid,arm=arm,batch_size=item['batch_size'],seed=item['seed'],repeat=item['repeat'],
                              original_batch_id=batchid,call_id=cid,stage=stage,
                              key_context_id=native['key_context_id'],parameter_id=ph,**counts,
                              native_total_ms=native['native_total_ms'],process_wall_ms=call['process_wall_ms'],
                              input_json_write_ms=call['input_json_write_ms'],output_json_read_ms=call['output_json_read_ms'],
                              native_unassigned_ms=residual,subprocess_outside_native_ms=outside,**ms))
        require(set(t['client_timings_ms']) == {'client_gate_or_decision_ms','retry_selection_ms','retry_input_materialize_ms'}, 'Unexpected client timer schema')
        components['decrypt_decode_gate_ms'] += t['client_timings_ms']['client_gate_or_decision_ms']
        components['retry_select_materialize_ms'] += t['client_timings_ms']['retry_selection_ms']+t['client_timings_ms']['retry_input_materialize_ms']
        components['client_harness_unassigned_ms'] = t['instrumented_local_wall_ms'] - sum(components.values())
        require(components['client_harness_unassigned_ms'] >= -1e-6, 'Local timer partition overlaps')
        event_counts = Counter(inputs=len(x),high_batches_started=high_batches,high_batches_completed=high_batches,high_valid_rows=high_rows,
                               native_calls=len(by_stage),original_batch_trials=1)
        for i,e in enumerate(t['events']):
            retry = i in pending; d = final[i]
            expected = dict(low_returned=arm=='two_stage' and not retry,retry_requested=retry,
                            retry_execution_started=retry,high_returned=d>=0 and (arm!='two_stage' or retry),
                            final_abstained=d<0,execution_failed=False,final_decision=d)
            require(all(e[k] == v for k,v in expected.items()), 'Recomputed event disposition mismatch')
            require(all(e[k] == v for k,v in expected_context.items()), 'Event context mismatch')
            require(e['input_id'] == str(ids[i]) and e['row_in_batch'] == i and e['request_id'] == f'{batchid}:{arm}:row{i}', 'Row identity mismatch')
            for stage in ('low','high'):
                c = by_stage.get(stage) if stage=='low' or arm!='two_stage' or retry else None
                for field in ('key_context_id','parameter_id'):
                    require(e[f'{stage}_{field}'] == (c['native'][field] if c else None), 'Event key/parameter link mismatch')
                require(e[f'{stage}_native_call_id'] == (c['call_id'] if c else None), 'Event call link mismatch')
            disagreement = d >= 0 and d != parent['reference'][off+i]
            label_error = d >= 0 and d != parent['labels'][off+i]
            event_counts.update({k:int(expected[k]) for k in ('low_returned','retry_requested','retry_execution_started','high_returned','final_abstained','execution_failed')})
            event_counts.update(returned=int(d>=0),accepted_disagreements=int(disagreement),accepted_label_errors=int(label_error))
            rows.append(dict(trial_id=tid,**e,post_audit_reference_decision=parent['reference'][off+i],
                             post_audit_label=parent['labels'][off+i],accepted_disagreement=disagreement,accepted_label_error=label_error))
        require(event_counts['returned']+event_counts['final_abstained']+event_counts['execution_failed'] == len(x), 'Disposition partition mismatch')
        metrics = dict(event_counts,**components,native_total_ms=native_sum,instrumented_local_wall_ms=t['instrumented_local_wall_ms'])
        trial_rows.append(dict(trial_id=tid,**item,**metrics))
        totals.setdefault((item['batch_size'],arm),Counter()).update(metrics)
        group_totals.setdefault((item['batch_size'],arm,item['seed'],item['repeat']),Counter()).update(metrics)
        env_load.extend([t['environment_before']['loadavg'][0],t['environment_after']['loadavg'][0]])
        pre=t['environment_before']['cpu_ticks_user_nice_system_idle_iowait_irq_softirq_steal']
        post=t['environment_after']['cpu_ticks_user_nice_system_idle_iowait_irq_softirq_steal']
        delta=[b-a for a,b in zip(pre,post)]
        if sum(delta)>0: busy_fractions.append(1-(delta[3]+delta[4])/sum(delta))
    require(len(native_seen) == execution['native_calls'] and len(trial_rows) == execution['completed_arm_trials'] == 216, 'Execution summary mismatch')
    require(execution['failed_arm_trials'] == 0, 'Failure summary mismatch')
    require(len(list((run/'calls').glob('*.json'))) == len(calls) and len(list((run/'trials').glob('*.json'))) == len(trial_rows), 'Unscheduled calls/trials')
    require(all(len(v)==1 for v in param_ids.values()), 'Unexpected parameter contexts')
    arm_summary=[]
    for (b,arm),v in sorted(totals.items()):
        require(v['inputs'] == 7578, 'Cell denominator mismatch')
        arm_summary.append(dict(batch_size=b,arm=arm,**v,model_repeat_blocks=9,
                                retry_request_rate=v['retry_requested']/v['inputs'],
                                retry_execution_rate=v['retry_execution_started']/v['inputs'],
                                final_abstention_rate=v['final_abstained']/v['inputs'],
                                mean_ms_per_842_inputs={k:x/9 for k,x in v.items() if k.endswith('_ms')}))
    pooling=[]
    for seed in p['training_seeds']:
        for repeat in range(p['key_repetitions']):
            for b in p['batch_sizes']:
                groups=key_groups[seed,repeat,b]; n=sum(v[1] for v in groups)
                pooling.append(dict(seed=seed,repeat=repeat,batch_size=b,retry_rows=n,
                                    measured_high_batches=len(groups),actual_distinct_high_keys=len({g[2] for g in groups}),
                                    mergeable_executed_batches=0,
                                    conditional_batches_if_client_delays_and_uses_one_shared_high_key=(n+4095)//4096,
                                    caveat='Hypothetical whole-842 client window, changed key lifecycle; batch-count bound only, no measured saving or queue'))
    summary=dict(schema='DP03_COST_AUDIT_V1',status='PASS',run_id=run.name,protocol_id=p['protocol_id'],
                 evidence_manifest_sha256=sha(run/'cost_evidence_manifest.json'),protocol_sha256=binding['protocol_sha256'],
                 verifier_sha256=sha(Path(__file__)),source_head=binding['source_head'],
                 verified_payload_files=len(manifest),verified_bound_parent_files=len(binding['parent_artifacts']),
                 arm_trials=len(trial_rows),native_calls=len(calls),row_observations=len(rows),fresh_key_contexts=len(keys),
                 parameter_contexts={str(k):sorted(v) for k,v in param_ids.items()},execution_failure_trials=0,
                 cells=arm_summary,pooling_bounds=pooling,network_ms=None,queue_wait_ms=None,
                 ciphertext_wire_serialization_ms=None,confirmatory=False,risk_admission=False,
                 environment=dict(cpu_count=execution['finished_environment']['cpu_count'],loadavg_1min_range=[min(env_load),max(env_load)],
                                  host_busy_fraction_range=[min(busy_fractions),max(busy_fractions)],
                                  note='Host-wide proc/stat deltas, not exclusive process CPU time or isolated hardware'),
                 scope='Three frozen models and three key repetitions; descriptive observations, no IID sample count, CI, service latency, or transferred 600-trial risk bound')
    blocks_out=[dict(batch_size=k[0],arm=k[1],seed=k[2],repeat=k[3],**v) for k,v in sorted(group_totals.items())]
    return summary,rows,calls,trial_rows,blocks_out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--run-id',default=DEFAULT_RUN)
    ap.add_argument('--output',type=Path,help='Optional NEW directory for derived evidence; existing directories are refused')
    args=ap.parse_args()
    result=verify(ROOT/'results'/args.run_id)
    summary,rows,calls,trials,blocks=result
    if args.output:
        output=args.output.resolve()
        require(output.is_relative_to(ROOT/'docs/research'), 'Derived output must be a new docs/research directory')
        output.mkdir(parents=True,exist_ok=False)
        (output/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
        for name,data in [('requests',rows),('native_calls',calls),('trials',trials),('model_repeat_blocks',blocks),('pooling_bounds',summary['pooling_bounds'])]:
            csv_write(output/f'{name}.csv',data)
        (output/'DERIVED_SHA256SUMS').write_text(''.join(f'{sha(f)}  {f.name}\n' for f in sorted(output.iterdir())))
    print(json.dumps({k:summary[k] for k in ('status','arm_trials','native_calls','row_observations','verified_payload_files','verified_bound_parent_files')}))


if __name__=='__main__': main()
