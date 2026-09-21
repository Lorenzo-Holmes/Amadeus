from __future__ import annotations

import json
import unittest

import final_full82_validation_v4_r047 as v4
import final_full82_validation_v3_r047 as v3


class Tests(unittest.TestCase):
    def test_exact_frozen_inputs_and_roles_preserved(self):
        a, _, _, _ = v3.fixed_scope()
        b, _, _, _ = v4.fixed_scope()
        self.assertEqual([(s['id'], s['case_id'], s['model'], s['user_text'], s['entity_label']) for s in a['slots']],
                         [(s['id'], s['case_id'], s['model'], s['user_text'], s['entity_label']) for s in b['slots']])

    def test_denominator_and_models(self):
        scope, _, _, _ = v4.fixed_scope()
        self.assertEqual(len(scope['slots']), 82)
        self.assertEqual(sum(s['model'] == 'deepseek-v4-flash' for s in scope['slots']), 76)
        self.assertEqual(sum(s['model'] == 'deepseek-v4-pro' for s in scope['slots']), 6)

    def test_guard_and_reserve(self):
        scope, _, _, _ = v4.fixed_scope()
        self.assertEqual(scope['schema_version'], 'apcore-provider-scope-2')
        self.assertEqual(scope['max_output_tokens'], 16384)
        self.assertEqual(scope['total_guard_cny'], 25)
        self.assertEqual(scope['reserved_upper_micro_cny'], 24_256_512)
        self.assertEqual(scope['automatic_paid_retries'], 0)

    def test_extended_capacity_flags_removed(self):
        scope, _, _, _ = v4.fixed_scope()
        for key in ('capacity_policy_id', 'output_budget_includes_reasoning', 'automatic_capacity_escalation'):
            self.assertNotIn(key, scope)

    def test_repair_evidence_is_bound_and_not_independent_acceptance(self):
        value = v4.repair_evidence()
        review = v4.common.read_json(v4.REPAIR_REVIEW)
        self.assertEqual(review['verdict_counts'], {'PASS': 176})
        self.assertTrue(review['all_repair_case_quality_targets_met'])
        self.assertFalse(review['independent_acceptance_claim'])
        self.assertIn('repair_review_sha256', value)


def main():
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'tests': result.testsRun, 'passed': result.wasSuccessful(), 'target_calls': 0}))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
