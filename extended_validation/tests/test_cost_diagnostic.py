import unittest
import numpy as np
from deciprotect.cost_diagnostic import execute_arm, BackendFailure


class CostFlowTest(unittest.TestCase):
    def run_flow(self, low, high, high_radius=.1, fail_high=False):
        seen=[]
        def invoke(stage, inputs, context):
            seen.append((stage, np.asarray(inputs).copy()))
            native={'client_decrypted_logits': low if stage=='low' else high,
                    'key_context_id':stage+'-key', 'parameter_id':stage+'-params',
                    'cost':{'counts':{'server_evaluations_started':1}}}
            r={'status':'SUCCESS','native':native,'call_id':stage+'-call'}
            if stage=='high' and fail_high:
                r['status']='EXECUTION_FAILURE'
                raise BackendFailure('controlled failure',r)
            return r
        result=execute_arm([[10,11],[20,21],[30,31]],['a','b','c'],
            {'original_batch_id':'batch','model_id':'model'},'two_stage',.5,high_radius,invoke)
        return result,seen

    def test_retry_is_not_abstention_and_uses_original_client_features(self):
        r,seen=self.run_flow([[1],[.1],[-.1]],[[1],[-1]])
        self.assertEqual(sum(e['retry_requested'] for e in r['events']),2)
        self.assertEqual(sum(e['final_abstained'] for e in r['events']),0)
        np.testing.assert_array_equal(seen[1][1],[[20,21],[30,31]])
        self.assertEqual([e['final_decision'] for e in r['events']],[1,1,0])
        self.assertEqual(sum(e['retry_execution_started'] for e in r['events']),2)

    def test_requested_but_unexecutable_is_separate(self):
        r,seen=self.run_flow([[1],[.1],[-.1]],None,high_radius=float('inf'))
        self.assertEqual(len(seen),1)
        self.assertEqual(sum(e['retry_requested'] for e in r['events']),2)
        self.assertEqual(sum(e['retry_execution_started'] for e in r['events']),0)
        self.assertEqual(sum(e['final_abstained'] for e in r['events']),2)

    def test_execution_failure_is_not_abstention(self):
        r,_=self.run_flow([[1],[.1],[-.1]],None,fail_high=True)
        self.assertEqual(sum(e['execution_failed'] for e in r['events']),2)
        self.assertEqual(sum(e['final_abstained'] for e in r['events']),0)
        self.assertEqual([e['final_decision'] for e in r['events']],[1,None,None])

    def test_no_retry_when_low_returns_all(self):
        r,seen=self.run_flow([[1],[1],[-1]],None)
        self.assertEqual(len(seen),1)
        self.assertFalse(any(e['retry_requested'] for e in r['events']))


if __name__=='__main__':unittest.main()
