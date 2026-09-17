from __future__ import annotations
import json,unittest
from longitudinal_assessment_r047 import assess_records

def rec(day,seq,calls,turns,*,restart=False,switch=False,retrieval=False):
    return {'observed_local_date':day,'candidate_release_id':'R','session_ids':['S'],'bad_or_unresolved_calls':[],
      'real_restart_observed':restart,'same_session_model_switch_observed':switch,'commitment_retrieval_observed':retrieval,
      'runtime_logical_summary':{'state':{'genesis_sha256':'G'},'next_sequence':seq,'provider_calls':calls,'turns':turns}}
class Tests(unittest.TestCase):
    def test_three_day_pass(self):
        r=assess_records([rec('2026-09-12',2,1,1),rec('2026-09-13',6,5,5,restart=True),rec('2026-09-14',10,9,9,switch=True,retrieval=True)]); self.assertEqual(r['overall_conclusion'],'PASS')
    def test_missing_switch_blocks(self):
        r=assess_records([rec('2026-09-12',2,1,1),rec('2026-09-13',3,2,2,restart=True),rec('2026-09-14',4,3,3,retrieval=True)]); self.assertIn('SAME_SESSION_MODEL_SWITCH_NOT_OBSERVED',r['blockers'])
    def test_mixed_session_blocks(self):
        a=rec('2026-09-12',2,1,1); b=rec('2026-09-13',3,2,2); b['session_ids']=['X']; c=rec('2026-09-14',4,3,3,restart=True,switch=True,retrieval=True); self.assertIn('SESSION_CONTINUITY_FAILED',assess_records([a,b,c])['blockers'])
def main():
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests)); print(json.dumps({'tests':r.testsRun,'passed':r.wasSuccessful(),'target_calls':0})); return 0 if r.wasSuccessful() else 1
if __name__=='__main__': raise SystemExit(main())
