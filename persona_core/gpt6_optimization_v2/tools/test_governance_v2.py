"""Pure offline governance regressions. No network, credentials or target model."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import governance_v2 as g


def facts(**changes):
    value = dict(critical=0, model_blocking_major=0, state_integrity_major=0, quality_unclear=0,
                 benchmark_contamination=False, unauthorized_state_promotion=False,
                 rubric_unchanged=True, evidence_preserved=True, source_identity_confirmed=True,
                 all_affected_requests_audited=True, local_defect_proven=True,
                 provider_outcome='TERMINAL_KNOWN', failure_layer='EVALUATOR')
    value.update(changes)
    return value


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.policy = g.load(g.ROOT / g.POLICY)
        # Synthetic fixture references are deliberately empty in this isolated unit test.
        self.policy['preserved_acceptance_references'] = []
        self.write(g.POLICY, self.policy)
        self.write(g.CANONICAL, {})
        self.write('evidence/item.json', {'immutable': True})
        self.write('manifest.json', {'files': {'evidence/item.json':
            g.sha((self.root / 'evidence/item.json').read_bytes())}, 'closed_directories': ['evidence']})
        self.lineage = {'root_id': 'fixed-root', 'candidate_id': 'fixed-candidate',
                        'configuration_sha256': 'a' * 64, 'benchmark_sha256': 'b' * 64,
                        'replacement_allocations': 0}

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(g.canonical_bytes(value))

    def payload(self, **changes):
        value = {'schema_version': 'TEST_CHECKPOINT', 'status': 'OFFLINE_ONLY',
                 'paid_requests_allowed': False, 'scientific_invariants': dict(g.INVARIANTS),
                 'draw_lineage': copy.deepcopy(self.lineage), 'private_raw_text': 'MUST_NOT_PUBLISH',
                 'integrity_manifests': [g.reference(self.root, 'manifest.json')],
                 'test_summary': {'passed': 1, 'raw': 'MUST_NOT_PUBLISH'}}
        value.update(changes)
        return value

    def sync(self, value=None):
        expected = g.sha((self.root / g.CANONICAL).read_bytes())
        return g.commit_state(self.root, value or self.payload(), expected)

    def test_scientific_invariants_exact(self):
        g.validate_policy(self.policy)
        for key in g.INVARIANTS:
            bad = copy.deepcopy(self.policy)
            bad['scientific_invariants'][key] -= 1
            with self.subTest(key=key), self.assertRaises(g.GovernanceError):
                g.validate_policy(bad)

    def test_no_automatic_retry_or_history_overwrite(self):
        for key in ('unknown_auto_resend', 'provider_auto_retry', 'retry_until_pass',
                    'historical_raw_overwrite', 'historical_revision_rewrite'):
            bad = copy.deepcopy(self.policy)
            bad['scientific_invariants'][key] = True
            with self.subTest(key=key), self.assertRaises(g.GovernanceError):
                g.validate_policy(bad)

    def test_severity_overrides_evaluator_label(self):
        for key in ('critical', 'model_blocking_major', 'state_integrity_major'):
            self.assertEqual(g.classify_failure(facts(**{key: 1}))['action'], 'HARD_STOP')
        for key in ('benchmark_contamination', 'unauthorized_state_promotion'):
            self.assertEqual(g.classify_failure(facts(**{key: True}))['action'], 'HARD_STOP')

    def test_unknown_or_missing_terminal_is_hard_stop(self):
        for outcome in ('UNKNOWN', 'AMBIGUOUS', None):
            self.assertEqual(g.classify_failure(facts(provider_outcome=outcome))['action'], 'HARD_STOP')

    def test_missing_fields_are_not_zero(self):
        value = facts()
        del value['critical']
        self.assertEqual(g.classify_failure(value)['action'], 'HARD_STOP')
        self.assertEqual(g.classify_failure(facts(critical=False))['action'], 'HARD_STOP')

    def test_local_defect_can_continue_without_paid_calls(self):
        result = g.classify_failure(facts())
        self.assertEqual(result['action'], 'LOCAL_REPAIR_CONTINUE')
        self.assertFalse(result['paid_requests_allowed'])

    def test_unclear_blocks_replacement_not_offline_diagnosis(self):
        value = facts(quality_unclear=1)
        self.assertEqual(g.classify_failure(value)['action'], 'LOCAL_REPAIR_CONTINUE')
        self.assertIn('UNRESOLVED_QUALITY_OBSERVATION',
                      g.replacement_blockers(value, {}, self.lineage, self.policy))

    def test_no_submission_preflight_defect_is_local(self):
        self.assertEqual(g.classify_failure(facts(provider_outcome='NOT_SUBMITTED'))['action'],
                         'LOCAL_REPAIR_CONTINUE')

    def test_billing_unknown_is_not_provider_unknown(self):
        self.assertEqual(g.classify_failure(facts(actual_billed='UNKNOWN'))['action'],
                         'LOCAL_REPAIR_CONTINUE')

    def test_replacement_cap_and_current_authorization(self):
        used = dict(self.lineage, replacement_allocations=1)
        blockers = g.replacement_blockers(facts(), {}, used, self.policy)
        self.assertIn('REPLACEMENT_CAP_REACHED_OR_UNKNOWN', blockers)
        self.assertIn('NO_PAID_VALIDATION_AUTHORIZATION_IN_THIS_TASK', blockers)

    def test_path_traversal_is_rejected(self):
        for path in ('../secret', '/absolute', 'C:/secret', 'a\\b', ''):
            with self.subTest(path=path), self.assertRaises(g.GovernanceError):
                g.local_path(self.root, path)

    def test_json_duplicate_key_is_rejected(self):
        path = self.root / 'bad.json'
        path.write_text('{"a":1,"a":2}', encoding='utf-8')
        with self.assertRaises(g.GovernanceError):
            g.load(path)

    def test_manifest_hash_does_not_hide_mutated_leaf(self):
        ref = g.reference(self.root, 'manifest.json')
        self.assertEqual(g.verify_manifest(self.root, ref)['status'], 'MATCH')
        self.write('evidence/item.json', {'immutable': False})
        self.assertEqual(g.verify_manifest(self.root, ref)['status'], 'MISMATCH')

    def test_rewritten_manifest_fails_pinned_digest(self):
        ref = g.reference(self.root, 'manifest.json')
        self.write('manifest.json', {'files': {'evidence/item.json': '0' * 64}})
        with self.assertRaisesRegex(g.GovernanceError, 'REFERENCE_HASH_MISMATCH'):
            g.verify_manifest(self.root, ref)

    def test_closed_directory_detects_addition(self):
        ref = g.reference(self.root, 'manifest.json')
        self.write('evidence/new.json', {})
        result = g.verify_manifest(self.root, ref)
        self.assertEqual(result['added_count'], 1)
        self.assertEqual(result['status'], 'MISMATCH')

    def test_checkpoint_and_public_view_are_deterministic(self):
        first = self.sync()
        second = self.sync()
        self.assertEqual(first['checkpoint'], second['checkpoint'])
        path = self.root / first['checkpoint']['path']
        public = path.parent / 'PUBLIC_SUMMARY.json'
        self.assertNotIn('MUST_NOT_PUBLISH', public.read_text())
        self.assertEqual(g.resume(self.root)['status'], 'OFFLINE_ONLY')

    def test_cas_conflict_keeps_current_state(self):
        before = (self.root / g.CANONICAL).read_bytes()
        with self.assertRaisesRegex(g.GovernanceError, 'STATE_CAS_CONFLICT'):
            g.commit_state(self.root, self.payload(), '0' * 64)
        self.assertEqual(before, (self.root / g.CANONICAL).read_bytes())

    def test_existing_writer_lock_is_not_stolen(self):
        lock = (self.root / g.CANONICAL).with_suffix('.lock')
        lock.write_bytes(b'another writer')
        with self.assertRaises(FileExistsError):
            self.sync()
        self.assertEqual(lock.read_bytes(), b'another writer')

    def test_failed_replace_preserves_previous_pointer(self):
        before = (self.root / g.CANONICAL).read_bytes()
        with patch.object(g.os, 'replace', side_effect=OSError('synthetic crash')):
            with self.assertRaises(OSError):
                self.sync()
        self.assertEqual(before, (self.root / g.CANONICAL).read_bytes())

    def test_policy_drift_blocks_resume(self):
        self.sync()
        self.write(g.POLICY, dict(self.policy, changed=True))
        with self.assertRaisesRegex(g.GovernanceError, 'REFERENCE_HASH_MISMATCH'):
            g.resume(self.root)

    def test_lineage_rename_cannot_reset_replacement_budget(self):
        self.sync()
        payload = self.payload()
        payload['draw_lineage']['root_id'] = 'renamed-campaign'
        with self.assertRaisesRegex(g.GovernanceError, 'DRAW_LINEAGE_CHANGED'):
            self.sync(payload)

    def test_replacement_counter_cannot_decrease(self):
        payload = self.payload()
        payload['draw_lineage']['replacement_allocations'] = 1
        self.sync(payload)
        with self.assertRaisesRegex(g.GovernanceError, 'DRAW_COUNTER_RESET'):
            self.sync(self.payload())

    def test_sync_never_rewrites_legacy_machine_files(self):
        names = ['GOAL_STATE.json', 'TASK_GRAPH.json', 'RECOVERY_CURSOR.json', 'VALIDATION_MATRIX.json']
        for name in names:
            self.write(g.G6 + '/' + name, {'legacy': name})
        before = {n: (self.root / g.G6 / n).read_bytes() for n in names}
        self.sync()
        self.assertEqual(before, {n: (self.root / g.G6 / n).read_bytes() for n in names})

    def test_paid_state_is_never_published_by_offline_sync(self):
        with self.assertRaisesRegex(g.GovernanceError, 'PAID_STATE_WRITE_FORBIDDEN'):
            self.sync(self.payload(paid_requests_allowed=True))

    def test_changed_test_file_is_always_selected(self):
        matrix = g.load(g.ROOT / g.MATRIX)
        result = g.plan_tests([g.G6 + '/tools/test_deepseek_successor_binding.py'], matrix)
        self.assertIn('test_deepseek_successor_binding.py', result['tests'])
        self.assertFalse(result['full_component_suite'])

    def test_unknown_change_is_conservative_and_rubric_is_protected(self):
        matrix = g.load(g.ROOT / g.MATRIX)
        result = g.plan_tests(['persona_core/unknown_dependency.py'], matrix)
        self.assertTrue(result['full_component_suite'])
        self.assertTrue(result['legacy_suite_or_dependency_review'])
        protected = g.plan_tests([g.G6 + '/external_failure_v1/PRIVATE_RUBRIC.json'], matrix)
        self.assertTrue(protected['hard_stop_protected_paths'])


if __name__ == '__main__':
    unittest.main()
