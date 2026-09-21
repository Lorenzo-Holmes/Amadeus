from __future__ import annotations
import json,shutil,unittest
import long_run_storage_stress_r047 as s
OUT=s.PLAN/'evidence/R047-04/long_run_storage_stress_test_static'
class Tests(unittest.TestCase):
    def test_small_contract_run(self):
        if OUT.exists(): shutil.rmtree(OUT)
        OUT.mkdir(parents=True); r=s.run(OUT,turn_count=1000,retrieval_count=100); self.assertTrue(r['pass']); self.assertEqual(r['provider_calls'],0); shutil.rmtree(OUT)
def main():
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests)); print(json.dumps({'tests':r.testsRun,'passed':r.wasSuccessful(),'target_calls':0})); return 0 if r.wasSuccessful() else 1
if __name__=='__main__': raise SystemExit(main())
