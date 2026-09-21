from __future__ import annotations
import json, unittest, zipfile
from datetime import datetime, timezone
from pathlib import Path
import final_full82_validation_v2_r047 as w
from transcript_store import StoreGuard, file_sha

OUT = w.PLAN/'evidence/R047-03/epistemic_repair_20260911'/('final82v2_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))


class Tests(unittest.TestCase):
    def test_scope_is_fresh_exact82_with_same_roles_and_guard(self):
        scope = w.fixed_scope()[0]
        self.assertEqual(len(scope['slots']), 82)
        self.assertEqual(scope['batch_id'], w.BATCH)
        self.assertEqual(scope['total_guard_cny'], 125)
        self.assertEqual(sum(s['model']=='deepseek-v4-flash' for s in scope['slots']), 76)
        self.assertEqual(sum(s['model']=='deepseek-v4-pro' for s in scope['slots']), 6)
        self.assertLessEqual(scope['reserved_upper_micro_cny'], 125_000_000)
    def test_parent_final01_failure_is_definitive_and_terminal(self):
        failure = w.parent_failure()
        self.assertEqual((failure['captured'], failure['rejected'], failure['not_submitted'], failure['unknown']), (5,1,76,0))
        self.assertEqual(failure['failed_slot'], 'N01_T6')
        self.assertEqual(failure['error_category'], 'EMPTY_RESPONSE')
    def test_targeted_closeout_remains_152_pass(self):
        r = w.targeted_closeout()
        self.assertEqual((r['reviewed_turns'], r['criteria'], r['pass']), (38,152,152))
    def test_no_active_remote_unknown_blocks_fresh_revision(self):
        self.assertEqual(w.readiness(require_regression=False)['unknown_policy']['active_unresolved_remote_unknowns'], [])
    def test_parent_batch_identity_is_not_new_batch(self):
        self.assertNotEqual(w.BATCH, 'APCORE-R047-FINAL-FULL82-01')
        encoded = json.dumps(w.fixed_scope()[0], ensure_ascii=False)
        self.assertNotIn('call_5c54e55063f2490e9f034a4a0ce1d485', encoded)
    def test_execution_requires_new_exact_authorization(self):
        if (w.REV/'EXECUTION_AUTHORIZATION.json').exists():
            self.skipTest('Real final02 authorization exists')
        if not w.REV.exists():
            w.REV.mkdir(parents=True)
            made = True
        else:
            made = False
        try:
            with self.assertRaises(StoreGuard):
                w.execution_authorization(w.fixed_scope()[0])
        finally:
            if made and not any(w.REV.iterdir()):
                w.REV.rmdir()


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    files = [Path(__file__), Path(w.__file__)]
    with zipfile.ZipFile(OUT/'TESTED_SOURCE.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.writestr(path.relative_to(w.ROOT).as_posix(), path.read_bytes())
    with (OUT/'TESTS.log').open('x', encoding='utf-8') as log:
        result = unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    report = {'tests': result.testsRun, 'passed': result.wasSuccessful(), 'target_calls': 0, 'network_calls': 0,
              'source_snapshot_sha256': file_sha(OUT/'TESTED_SOURCE.zip')}
    (OUT/'TESTS.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'output': OUT.relative_to(w.ROOT).as_posix(), **report}))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
