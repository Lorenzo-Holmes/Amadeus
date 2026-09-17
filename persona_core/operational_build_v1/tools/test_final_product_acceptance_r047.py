from __future__ import annotations
import json,unittest
from final_product_acceptance_r047 import evaluate
class Tests(unittest.TestCase):
    def test_ready(self): self.assertTrue(evaluate({'overall_conclusion':'PASS','gate_can_pass':True},{'overall_conclusion':'PASS'},{'candidate_release_id':'x'},{'active_unresolved_remote_unknowns':[]})['ready_for_product_acceptance'])
    def test_missing_review_blocks(self): self.assertIn('NEW_INDEPENDENT_REVIEW_RETURN_MISSING',evaluate(None,{'overall_conclusion':'PASS'},{}, {'active_unresolved_remote_unknowns':[]})['blockers'])
    def test_unknown_blocks(self): self.assertIn('ACTIVE_REMOTE_UNKNOWN_PRESENT',evaluate({'overall_conclusion':'PASS','gate_can_pass':True},{'overall_conclusion':'PASS'},{}, {'active_unresolved_remote_unknowns':[{}]})['blockers'])
def main():
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests)); print(json.dumps({'tests':r.testsRun,'passed':r.wasSuccessful(),'target_calls':0})); return 0 if r.wasSuccessful() else 1
if __name__=='__main__': raise SystemExit(main())
