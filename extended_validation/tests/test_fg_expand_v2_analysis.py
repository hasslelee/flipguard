import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_fg_expand_v2 import metrics

class MulticlassEvidenceTests(unittest.TestCase):
    def observe(self,p,z):
        return metrics([dict(plaintext_logits=p+[-10.]*(10-len(p)),ckks_logits=z+[-10.]*(10-len(z)),label=0)])
    def test_same_decision_can_violate_strict_reserve(self):
        a=self.observe([1.,0.],[.75,.25])
        self.assertFalse(a['flip'][0]);self.assertTrue(a['viol'][0])
    def test_every_competitor_matters(self):
        a=self.observe([2.,1.,0.],[2.,1.,1.5])
        self.assertFalse(a['flip'][0]);self.assertTrue(a['viol'][0])
    def test_plaintext_tie_is_boundary_with_lowest_index_rule(self):
        a=self.observe([1.,1.],[.9,1.])
        self.assertFalse(a['app'][0]);self.assertTrue(a['flip'][0]);self.assertFalse(a['viol'][0]);self.assertEqual(a['cap'][0],0.)
    def test_margin_floor_equality_excluded(self):
        a=self.observe([.001,0.],[0.,.001])
        self.assertFalse(a['app'][0]);self.assertTrue(a['flip'][0]);self.assertFalse(a['viol'][0])
if __name__=='__main__':unittest.main()
