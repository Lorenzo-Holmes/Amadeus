from __future__ import annotations
import json,unittest
from fault_recovery_matrix_r047 import matrix
class Tests(unittest.TestCase):
    def test_current_history_is_fully_classified(self):
        r=matrix(); self.assertTrue(r['pass']); self.assertEqual(r['raw_unknown_count'],r['classified_historical_unknown_count']); self.assertEqual(r['active_unresolved_remote_unknowns'],[])
    def test_no_historical_unknown_can_be_resent(self): self.assertTrue(matrix()['all_old_slots_no_resend'])
def main():
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests)); print(json.dumps({'tests':r.testsRun,'passed':r.wasSuccessful(),'target_calls':0})); return 0 if r.wasSuccessful() else 1
if __name__=='__main__': raise SystemExit(main())
