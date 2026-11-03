"""Local client orchestration; runtime inputs exclude oracle scores and labels."""
import math
import time
import numpy as np
from .decision import interval_gate, reference_decision

ARMS = ('fixed_high', 'fixed_high_gate', 'two_stage')


class BackendFailure(RuntimeError):
    def __init__(self, message, record):
        super().__init__(message)
        self.record = record


def execute_arm(inputs, input_ids, context, arm, low_radius, high_radius, invoke):
    """invoke(stage, client-owned features, metadata) performs a local CKKS call.

    Retrying gathers original model-space features on the client. No server-side
    plaintext repacking or conversion of a low-scale ciphertext is performed.
    A returned -1 denotes abstention; None denotes execution failure.
    """
    if arm not in ARMS:
        raise ValueError('Unknown diagnostic arm')
    x = np.asarray(inputs, dtype=float)
    if len(x) != len(input_ids) or not len(x):
        raise ValueError('Aligned nonempty inputs required')
    started = time.perf_counter_ns()
    timings = {'client_gate_or_decision_ms': 0., 'retry_selection_ms': 0.,
               'retry_input_materialize_ms': 0.}
    events = [dict(context, request_id=f'{context["original_batch_id"]}:{arm}:row{i}',
                   arm=arm, input_id=str(uid), row_in_batch=i,
                   low_returned=False, retry_requested=False, retry_execution_started=False,
                   high_returned=False, final_abstained=False, execution_failed=False,
                   final_decision=None, low_key_context_id=None, high_key_context_id=None,
                   low_parameter_id=None, high_parameter_id=None,
                   low_native_call_id=None, high_native_call_id=None)
              for i, uid in enumerate(input_ids)]
    calls = []

    def call(stage, values, indices):
        metadata = dict(context, arm=arm, stage=stage)
        try:
            record = invoke(stage, values, metadata)
        except BackendFailure as exc:
            record = exc.record
        calls.append(record)
        native = record.get('native') or {}
        counts = native.get('cost', {}).get('counts', {})
        executed = counts.get('server_evaluations_started', 0) > 0 if native else None
        for i in indices:
            events[i][f'{stage}_key_context_id'] = native.get('key_context_id') or None
            events[i][f'{stage}_parameter_id'] = native.get('parameter_id') or None
            events[i][f'{stage}_native_call_id'] = record['call_id']
            if stage == 'high' and arm == 'two_stage':
                events[i]['retry_execution_started'] = executed
        if record['status'] != 'SUCCESS':
            for i in indices:
                events[i]['execution_failed'] = True
            return None
        return native['client_decrypted_logits']

    indices = list(range(len(x)))
    if arm in ('fixed_high', 'fixed_high_gate'):
        logits = call('high', x, indices)
        if logits is not None:
            t = time.perf_counter_ns()
            decisions = reference_decision(logits) if arm == 'fixed_high' else interval_gate(logits, high_radius)
            timings['client_gate_or_decision_ms'] += (time.perf_counter_ns()-t)/1e6
            for i, d in enumerate(decisions):
                events[i].update(final_decision=int(d), high_returned=bool(d >= 0), final_abstained=bool(d < 0))
    else:
        logits = call('low', x, indices)
        if logits is not None:
            t = time.perf_counter_ns()
            decisions = interval_gate(logits, low_radius)
            timings['client_gate_or_decision_ms'] += (time.perf_counter_ns()-t)/1e6
            t = time.perf_counter_ns()
            pending = np.flatnonzero(decisions < 0).tolist()
            timings['retry_selection_ms'] += (time.perf_counter_ns()-t)/1e6
            for i, d in enumerate(decisions):
                events[i].update(low_returned=bool(d >= 0), retry_requested=bool(d < 0), final_decision=int(d))
            if pending and math.isfinite(high_radius):
                t = time.perf_counter_ns()
                retry_inputs = x[pending]  # Client-owned original features, not decrypted low logits.
                timings['retry_input_materialize_ms'] += (time.perf_counter_ns()-t)/1e6
                high_logits = call('high', retry_inputs, pending)
                if high_logits is not None:
                    t = time.perf_counter_ns()
                    high_decisions = interval_gate(high_logits, high_radius)
                    timings['client_gate_or_decision_ms'] += (time.perf_counter_ns()-t)/1e6
                    for i, d in zip(pending, high_decisions):
                        events[i].update(final_decision=int(d), high_returned=bool(d >= 0), final_abstained=bool(d < 0))
                else:
                    for i in pending:
                        events[i]['final_decision'] = None
            elif pending:
                for i in pending:
                    events[i]['final_abstained'] = True
    wall_ms = (time.perf_counter_ns()-started)/1e6
    return {'context': context, 'arm': arm, 'events': events, 'calls': calls,
            'client_timings_ms': timings, 'instrumented_local_wall_ms': wall_ms,
            'network_ms': None, 'queue_wait_ms': None, 'risk_admission': False}
