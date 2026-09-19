"""Offline contract tests for the bounded independent-review repair probe."""
from __future__ import annotations

import json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / 'persona_core/operational_build_v1/tools'
sys.path.insert(0, str(TOOLS))
import external_review_repair_probe_r047 as probe


class Tests(unittest.TestCase):
    def test_fixed_denominator_and_models(self):
        scope, cases, _, _ = probe.fixed_scope()
        self.assertEqual(len(scope['slots']), 44)
        self.assertEqual(sum(s['model'] == 'deepseek-v4-flash' for s in scope['slots']), 42)
        self.assertEqual(sum(s['model'] == 'deepseek-v4-pro' for s in scope['slots']), 2)
        self.assertEqual([c['id'] for c in cases['cases']], list(probe.CASE_IDS))

    def test_exact_final03_inputs_and_roles_are_preserved(self):
        scope, _, _, _ = probe.fixed_scope()
        parent = probe.common.read_json(probe.FINAL03 / 'EXECUTION_SCOPE.json')
        expected = [(s['id'], s['model'], s['user_text']) for s in parent['slots'] if s.get('case_id') in probe.CASE_IDS]
        actual = [(s['id'], s['model'], s['user_text']) for s in scope['slots']]
        self.assertEqual(actual, expected)

    def test_guard_is_bounded_below_confirmation_threshold(self):
        scope, _, _, _ = probe.fixed_scope()
        self.assertEqual(scope['schema_version'], 'apcore-provider-scope-2')
        self.assertEqual(scope['max_output_tokens'], 16384)
        self.assertEqual(scope['reserved_upper_micro_cny'], 12_386_304)
        self.assertEqual(scope['total_guard_cny'], 15)
        self.assertLess(scope['total_guard_cny'], 20)
        self.assertEqual(scope['automatic_paid_retries'], 0)

    def test_extended_capacity_flags_are_not_silently_carried(self):
        scope, _, _, _ = probe.fixed_scope()
        for key in ('capacity_policy_id', 'output_budget_includes_reasoning', 'automatic_capacity_escalation'):
            self.assertNotIn(key, scope)


def main() -> int:
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'tests': result.testsRun, 'passed': result.wasSuccessful(), 'target_calls': 0}))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
