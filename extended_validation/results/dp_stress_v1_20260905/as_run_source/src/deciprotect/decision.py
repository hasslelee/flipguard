"""Client-side interval decision gate with no access to plaintext reference."""
import math
import numpy as np


def reference_decision(logits):
    z = np.asarray(logits, dtype=float)
    if z.ndim != 2 or z.shape[1] == 0 or not np.isfinite(z).all():
        raise ValueError('Expected a finite nonempty logit matrix')
    return (z[:, 0] >= 0).astype(int) if z.shape[1] == 1 else z.argmax(axis=1)


def interval_gate(decrypted_logits, error_radius):
    z = np.asarray(decrypted_logits, dtype=float)
    decision = reference_decision(z)
    q = float(error_radius)
    if math.isnan(q) or q < 0:
        raise ValueError('Error radius must be nonnegative')
    if math.isinf(q):
        return np.full(len(z), -1, dtype=int)
    if z.shape[1] == 1:
        accept = ((z[:, 0] - q) >= 0) | ((z[:, 0] + q) < 0)
    else:
        # Strict interval separation deliberately abstains on ties, even q=0.
        top = z[np.arange(len(z)), decision]
        rivals = z.copy()
        rivals[np.arange(len(z)), decision] = -np.inf
        accept = top - rivals.max(axis=1) > 2 * q
    return np.where(accept, decision, -1)


def calibration_radius(errors, alpha):
    e = np.asarray(errors, dtype=float)
    if e.ndim != 1 or not len(e) or not np.isfinite(e).all() or (e < 0).any():
        raise ValueError('Finite nonnegative calibration errors required')
    if not 0 < alpha < 1:
        raise ValueError('alpha must be in (0,1)')
    rank = math.ceil((len(e) + 1) * (1 - alpha))
    return math.inf if rank > len(e) else float(np.partition(e, rank - 1)[rank - 1])


def decision_metrics(plain_logits, decisions, labels):
    ref = reference_decision(plain_logits)
    d = np.asarray(decisions)
    y = np.asarray(labels)
    if d.shape != ref.shape or y.shape != ref.shape or len(ref) == 0:
        raise ValueError('Aligned nonempty rows required')
    accept = d >= 0
    wrong = accept & (d != ref)
    n = len(ref)
    return {'inputs': n, 'accepted': int(accept.sum()), 'abstained': int((~accept).sum()),
            'coverage': float(accept.mean()), 'accepted_disagreements': int(wrong.sum()),
            'joint_disagreement_rate': float(wrong.mean()),
            'selective_disagreement_rate': float(wrong[accept].mean()) if accept.any() else None,
            'plaintext_accuracy': float((ref == y).mean()),
            'accepted_label_accuracy': float((d[accept] == y[accept]).mean()) if accept.any() else None,
            'label_accuracy_with_abstention_as_failure': float((accept & (d == y)).mean())}
