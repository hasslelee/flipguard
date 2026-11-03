import unittest
import numpy as np
from deciprotect.difference import pairwise_residuals,difference_gate
from deciprotect.decision import interval_gate


class DifferenceTests(unittest.TestCase):
    def test_common_mode_error_cancels(self):
        plain=np.array([[3.,2.,0.]])
        he=plain+1000
        q=pairwise_residuals(plain,he[None,:,:])[0]
        self.assertEqual(q,0)
        self.assertEqual(difference_gate(he,q).tolist(),[0])
        self.assertEqual(interval_gate(he,1000).tolist(),[-1])

    def test_differential_error_can_change_class(self):
        plain=np.array([[1.,.9]])
        he=np.array([[.8,1.1]])
        q=pairwise_residuals(plain,he[None,:,:])[0]
        self.assertEqual(difference_gate(he,q).tolist(),[-1])

    def test_all_pairs_bounded_preserve_any_returned_class(self):
        rng=np.random.default_rng(30)
        plain=rng.normal(size=(1000,10));err=rng.uniform(-.2,.2,size=plain.shape)+rng.normal(size=(1000,1))*100
        he=plain+err
        pred=difference_gate(he,.4)
        self.assertTrue(np.all(pred[pred>=0]==plain.argmax(axis=1)[pred>=0]))

    def test_binary_scalar_rejected(self):
        with self.assertRaises(ValueError):difference_gate([[1]],1)


if __name__=='__main__':unittest.main()
