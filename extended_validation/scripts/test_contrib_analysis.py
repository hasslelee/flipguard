"""Checks cases where disagreement, conservative error and scope differ."""
import unittest
from analyze_fg_contrib_v1 import verdict

class EvidenceSemantics(unittest.TestCase):
 def test_same_binary_decision_can_violate_error_condition(self):
  r=verdict([.6],[.69]);self.assertFalse(r['flip']);self.assertTrue(r['protected_error_violation'])
 def test_boundary_flip_is_not_application_flip(self):
  r=verdict([.5001],[.4999]);self.assertTrue(r['flip']);self.assertFalse(r['applicable']);self.assertFalse(r['protected_flip'])
 def test_all_competitors_checked_not_only_runner_up(self):
  # Original winner and runner-up errors vanish; third class grows enough to
  # violate the reserve while remaining below the original winning logit.
  r=verdict([1.,.8,0.],[1.,.8,.6]);self.assertFalse(r['flip']);self.assertTrue(r['protected_error_violation'])
 def test_tie_is_outside_application_domain(self):
  r=verdict([1.,1.],[1.,1.]);self.assertFalse(r['applicable']);self.assertFalse(r['flip'])
 def test_strict_error_boundary(self):
  r=verdict([1.,0.],[1.,.5]);self.assertFalse(r['flip']);self.assertTrue(r['protected_error_violation'])
 def test_reject_nonfinite(self):
  with self.assertRaises(AssertionError):verdict([1.,0.],[float('nan'),0.])

if __name__=='__main__':unittest.main()
