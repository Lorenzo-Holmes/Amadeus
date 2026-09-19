from __future__ import annotations
import json,unittest
import build_repaired_release_r047 as r

class Tests(unittest.TestCase):
    def test_repaired_evidence_gate(self):
        value=r.validate_repaired_evidence(); self.assertIn('reviewer_package_sha256',value)
    def test_candidate_scope(self):
        s=r.candidate_scope('TESTSTAMP'); self.assertEqual(len(s['slots']),16)
        self.assertEqual(sum(x['model']=='deepseek-v4-flash' for x in s['slots']),15); self.assertEqual(sum(x['model']=='deepseek-v4-pro' for x in s['slots']),1)
        self.assertEqual(s['slots'][8]['id'],'USER_09'); self.assertEqual(s['slots'][8]['model'],'deepseek-v4-pro')
        self.assertEqual(s['reserved_upper_micro_cny'],2_875_392); self.assertEqual(s['total_guard_cny'],3.0); self.assertEqual(s['automatic_paid_retries'],0)

def main():
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'tests':result.testsRun,'passed':result.wasSuccessful(),'target_calls':0,'candidate_built':False}))
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__': raise SystemExit(main())
