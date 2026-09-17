from __future__ import annotations
import json,unittest
import composite_full82_repaired_r047 as c
import final_full82_validation_v5_r047 as parent

class Tests(unittest.TestCase):
    def test_case_partition_is_exact(self):
        self.assertFalse(set(c.REPAIR_CASES)&set(c.COMPONENT_CASES))
        self.assertEqual(set(c.REPAIR_CASES)|set(c.COMPONENT_CASES),
                         {'N01','N02','N03','N04','N05','N06','N07','N08','N09','N10','N11','N12','R01','R02'})
    def test_component_slots_total_38_and_exact(self):
        parent_scope,_,_,_=parent.fixed_scope(); expected=[s for s in parent_scope['slots'] if s['case_id'] in c.COMPONENT_CASES]
        actual=[]
        for case in c.COMPONENT_CASES: actual.extend(c.component_scope(case)[0]['slots'])
        self.assertEqual(len(actual),38); self.assertEqual([(s['id'],s['model'],s['user_text']) for s in actual],
                                                           [(s['id'],s['model'],s['user_text']) for s in expected])
    def test_each_component_guard_bounded(self):
        for case in c.COMPONENT_CASES:
            s,_,_,_=c.component_scope(case); self.assertLessEqual(s['reserved_upper_micro_cny'],5_000_000)
            self.assertEqual(s['automatic_paid_retries'],0)
    def test_repair_runtime_matches_current(self):
        b=c.repair_runtime_binding(); self.assertEqual(b['runtime_hashes'],c.current_runtime_hashes())
    def test_repair_review_is_not_independent_acceptance(self):
        r=c.common.read_json(c.REPAIR_REVIEW); self.assertEqual(r['verdict_counts'],{'PASS':176})
        self.assertFalse(r['independent_acceptance_claim']); self.assertFalse(r['full82_acceptance_claim'])

def main():
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'tests':result.testsRun,'passed':result.wasSuccessful(),'target_calls':0}))
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__': raise SystemExit(main())
