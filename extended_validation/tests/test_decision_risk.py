import math
import unittest
import numpy as np
from deciprotect.decision import interval_gate, calibration_radius, decision_metrics
from deciprotect.risk import binomial_upper, required_zero_failure_units, admit_risk


class DecisionRiskTests(unittest.TestCase):
    def test_binary_intervals_and_threshold_convention(self):
        self.assertEqual(interval_gate([[-1], [-.5], [0], [.5], [1]], .5).tolist(), [0, -1, -1, 1, 1])

    def test_multiclass_all_competitors_and_ties(self):
        self.assertEqual(interval_gate([[3, 1, 0], [1, 1, 0], [1, .2, .3]], .5).tolist(), [0, -1, -1])

    def test_gate_preserves_all_interval_corner_decisions(self):
        import itertools
        rng = np.random.default_rng(19)
        z = rng.normal(size=(1000, 4))
        d = interval_gate(z, .15)
        for sign in itertools.product([-1, 1], repeat=4):
            ref = (z + .15 * np.array(sign)).argmax(axis=1)
            self.assertTrue(np.all(d[d >= 0] == ref[d >= 0]))

    def test_fail_closed(self):
        for z, q in [([[math.nan]], 1), ([[1]], math.nan), ([[1]], -1)]:
            with self.assertRaises(ValueError): interval_gate(z, q)
        self.assertEqual(interval_gate([[10]], math.inf).tolist(), [-1])
        self.assertEqual(interval_gate([[1, 1]], 0).tolist(), [-1])

    def test_too_few_calibration_rows(self):
        self.assertTrue(math.isinf(calibration_radius([0] * 20, .025)))
        self.assertEqual(calibration_radius(list(range(100)), .025), 98)

    def test_zero_failure_does_not_mean_zero_risk(self):
        self.assertAlmostEqual(binomial_upper(0, 23), 1 - .05 ** (1 / 23))
        n = required_zero_failure_units(.01)
        self.assertEqual(n, 299)
        self.assertLessEqual(binomial_upper(0, n), .01)
        self.assertGreater(binomial_upper(0, n - 1), .01)

    def test_multiplicity_and_dependence(self):
        self.assertFalse(admit_risk(0, 1000000, .01, independent_units=False)['admitted'])
        self.assertGreater(required_zero_failure_units(.01, hypotheses=12), 299)
        self.assertFalse(admit_risk(0, 299, .01, independent_units=True, hypotheses=12)['admitted'])

    def test_no_coverage_is_not_perfect_selective_accuracy(self):
        m = decision_metrics([[1], [-1]], [-1, -1], [1, 0])
        self.assertIsNone(m['selective_disagreement_rate'])
        self.assertEqual(m['coverage'], 0)


if __name__ == '__main__': unittest.main()
