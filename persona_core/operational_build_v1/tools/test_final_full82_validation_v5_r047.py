from __future__ import annotations
import json, unittest
import final_full82_validation_v5_r047 as v5
import final_full82_validation_v4_r047 as v4

class Tests(unittest.TestCase):
    def test_inputs_and_roles_preserved(self):
        a,_,_,_=v4.fixed_scope(); b,_,_,_=v5.fixed_scope()
        self.assertEqual([(s['id'],s['case_id'],s['model'],s['user_text'],s['entity_label']) for s in a['slots']],
                         [(s['id'],s['case_id'],s['model'],s['user_text'],s['entity_label']) for s in b['slots']])
    def test_scope_v3_timeout_only_capacity_change(self):
        s,_,_,_=v5.fixed_scope()
        self.assertEqual(s['schema_version'],'apcore-provider-scope-3')
        self.assertEqual(s['request_timeout_seconds'],600)
        self.assertEqual(s['max_output_tokens'],16384)
        self.assertEqual(s['capacity_policy_id'],'EXTENDED_MAX_REASONING_20260911')
        self.assertTrue(s['output_budget_includes_reasoning'])
        self.assertFalse(s['automatic_capacity_escalation'])
    def test_guard_and_counts(self):
        s,_,_,_=v5.fixed_scope()
        self.assertEqual(len(s['slots']),82); self.assertEqual(s['total_guard_cny'],25)
        self.assertEqual(s['reserved_upper_micro_cny'],24_256_512); self.assertEqual(s['automatic_paid_retries'],0)
    def test_parent_failure_and_quarantine_bind(self):
        p=v5.parent_failure()
        self.assertEqual(p['failed_slot'],'N04_T6'); self.assertEqual(p['captured'],23)
        self.assertEqual(p['unknown'],1); self.assertEqual(p['not_submitted'],58)
    def test_repair_review_still_clean(self):
        r=v5.final04.common.read_json(v5.final04.REPAIR_REVIEW)
        self.assertEqual(r['verdict_counts'],{'PASS':176}); self.assertTrue(r['all_repair_case_quality_targets_met'])

def main():
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'tests':result.testsRun,'passed':result.wasSuccessful(),'target_calls':0}))
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__': raise SystemExit(main())
