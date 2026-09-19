"""Reuse intact wrapper guard cases with this explicitly different capacity."""
from __future__ import annotations
from datetime import datetime, timezone
import repair_revision_r047_v6 as revision
import test_repair_wrapper_r047_v5 as harness

harness.wrapper = revision
harness.REAL = revision.REV
harness.OUT = revision.REV / ('wrapper_tests_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))


class CapacityWrapperTests(harness.WrapperTests):
    def test_main_and_switch_roles_explicit_original_texts_unchanged(self):
        parent = revision.common.load_frozen()[0]
        scope = revision.load_revision()[0]
        self.assertEqual(len(scope['slots']), 82)
        self.assertEqual([s['user_text'] for s in scope['slots']], [s['user_text'] for s in parent['slots']])
        self.assertEqual(sum(s['model'] == 'deepseek-v4-flash' for s in scope['slots']), 76)
        self.assertTrue(all(s['model'] == 'deepseek-v4-pro' for s in scope['slots'] if '_S' in s['id']))
        self.assertEqual(scope['reasoning_effort'], 'max')
        self.assertEqual(scope['max_output_tokens'], 131072)
        self.assertEqual(scope['request_timeout_seconds'], 1200)
        self.assertEqual(scope['reserved_upper_micro_cny'], 121282560)
        self.assertEqual(scope['total_guard_cny'], 125)
        self.assertFalse(scope['automatic_capacity_escalation'])
    def test_diagnostic_is_not_upgraded_to_full_or_independent_acceptance(self):
        readiness = revision.verify_ready()
        self.assertEqual(len(readiness['raw_unknown_rows_with_specific_local_proof']), 1)
        review = revision.common.read_json(revision.DIAGNOSTIC_REVIEW)
        self.assertFalse(review['full_82_acceptance_complete'])
        self.assertFalse(review['independent_review_complete'])
        self.assertFalse(review['capacity_increase_is_proven_cause'])
    def test_previous_local_reconciliation_is_required(self):
        from unittest.mock import patch
        from transcript_store import StoreGuard
        with patch.object(revision.diagnostic_revision, 'verify_local_disposition', side_effect=StoreGuard('AUTHORED_MISSING_PROOF')):
            with self.assertRaises(StoreGuard):
                revision.verify_ready()


harness.WrapperTests = CapacityWrapperTests

if __name__ == '__main__':
    raise SystemExit(harness.main())
