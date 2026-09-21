from __future__ import annotations
import json,unittest
import simulated_time_stress_r047 as s
class Tests(unittest.TestCase):
    def test_simulated_dates_never_qualify_extra_day(self):
        r=s.scenarios(); self.assertTrue(r['pass']); self.assertFalse(r['counts_for_real_natural_day']); self.assertTrue(r['candidate_bytes_unchanged'])
def main():
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests)); print(json.dumps({'tests':r.testsRun,'passed':r.wasSuccessful(),'target_calls':0})); return 0 if r.wasSuccessful() else 1
if __name__=='__main__': raise SystemExit(main())
