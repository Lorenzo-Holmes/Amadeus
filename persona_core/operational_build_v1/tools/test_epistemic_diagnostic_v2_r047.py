"""Offline contract tests for the post-quarantine independent diagnostic."""
from __future__ import annotations
import json
import unittest
import zipfile
from datetime import datetime,timezone
from pathlib import Path
import epistemic_diagnostic_v2_r047 as d
from transcript_store import file_sha

OUT=d.PLAN/'evidence/R047-03/epistemic_repair_20260911'/('probe02_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))

class Probe02Tests(unittest.TestCase):
    def test_fixed_scope_is_26_and_only_remaining_domains(self):
        scope=d.fixed_scope()[0]
        self.assertEqual(len(scope['slots']),26)
        self.assertEqual({s['case_id'] for s in scope['slots']},set(d.CASE_IDS))
        self.assertTrue(all(s['model']=='deepseek-v4-flash' for s in scope['slots']))
    def test_guard_covers_fixed_reserve_without_unbounded_budget(self):
        scope=d.fixed_scope()[0]
        self.assertLessEqual(scope['reserved_upper_micro_cny'],d.GUARD_CNY*1_000_000)
        self.assertEqual(scope['total_guard_cny'],35)
        self.assertEqual(scope['automatic_paid_retries'],0)
    def test_old_unknown_is_quarantined_not_resolved_or_retryable(self):
        ready=d.readiness(require_current_regression=False)
        old=ready['quarantined_predecessor_call']
        self.assertEqual(old['call_id'],d.OLD_UNKNOWN_CALL)
        self.assertEqual(old['remote_outcome'],'UNKNOWN')
        self.assertFalse(old['resend_allowed'])
        self.assertTrue(old['new_independent_batch_allowed'])
    def test_no_active_unclassified_unknown_remains(self):
        self.assertEqual(d.readiness(require_current_regression=False)['unknown_policy']['active_unresolved_remote_unknowns'],[])
    def test_n01_n02_omission_is_bound_to_complete_partial_reviews(self):
        ready=d.readiness(require_current_regression=False)
        self.assertIn('PARTIAL_SEMANTIC_REVIEW.json',ready['partial_review'])
        self.assertEqual(ready['old_probe_counts'],{'RESPONSE_CAPTURED':14,'SUBMITTED_STATUS_UNKNOWN':1})
    def test_scope_contains_no_old_call_identity_or_old_batch(self):
        encoded=json.dumps(d.fixed_scope()[0],ensure_ascii=False)
        self.assertNotIn(d.OLD_UNKNOWN_CALL,encoded)
        self.assertNotIn('APCORE-R047-EPISTEMIC-DIAGNOSTIC-01',encoded)

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__),Path(d.__file__),Path(d.unknowns.__file__)]
    with zipfile.ZipFile(OUT/'TESTED_SOURCE.zip','x',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.writestr(p.relative_to(d.ROOT).as_posix(),p.read_bytes())
    with (OUT/'TESTS.log').open('x',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Probe02Tests))
    report={'tests':result.testsRun,'passed':result.wasSuccessful(),'target_calls':0,'network_calls':0,
            'source_snapshot_sha256':file_sha(OUT/'TESTED_SOURCE.zip')}
    (OUT/'TESTS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'output':OUT.relative_to(d.ROOT).as_posix(),**report}))
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
