"""Exact one-sided bounds, admitted ONLY for justified independent units."""
import math
from scipy.stats import beta


def binomial_upper(failures, trials, alpha=0.05):
    if isinstance(failures, bool) or isinstance(trials, bool) or not isinstance(failures, int) or not isinstance(trials, int):
        raise ValueError('Counts must be integers')
    if trials < 0 or not 0 <= failures <= trials or not 0 < alpha < 1:
        raise ValueError('Invalid counts or alpha')
    if trials == 0 or failures == trials:
        return 1.0
    if failures == 0:
        return -math.expm1(math.log(alpha) / trials)
    return float(beta.ppf(1 - alpha, failures + 1, trials - failures))


def required_zero_failure_units(target_risk, alpha=0.05, hypotheses=1):
    if not 0 < target_risk < 1 or not 0 < alpha < 1 or not isinstance(hypotheses, int) or hypotheses < 1:
        raise ValueError('Invalid risk specification')
    return math.ceil(math.log(alpha / hypotheses) / math.log1p(-target_risk))


def admit_risk(failures, trials, target_risk, *, independent_units, alpha=0.05, hypotheses=1):
    if not 0 < target_risk < 1 or not isinstance(hypotheses, int) or hypotheses < 1:
        raise ValueError('Invalid target or multiplicity')
    bound = binomial_upper(failures, trials, alpha / hypotheses)
    if not independent_units:
        return {'status': 'UNSUPPORTED_SAMPLING_UNIT', 'upper_bound': None, 'admitted': False}
    return {'status': 'ADMITTED' if bound <= target_risk else 'INSUFFICIENT_EVIDENCE',
            'upper_bound': bound, 'admitted': bound <= target_risk}
