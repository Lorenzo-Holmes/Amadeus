"""Offline reporting tests: unknown usage never becomes a zero-valued total."""
from __future__ import annotations
import json
import unittest
import zipfile
from datetime import datetime,timezone
from pathlib import Path
import audit_captures_r047 as audit
from transcript_store import file_sha

OUT=audit.PLAN/'evidence/R047-03/epistemic_repair_20260911'/('accounting_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))


class AccountingTests(unittest.TestCase):
    def row(self,status,amount=None):return {'status':status,'peak_usage_estimate_micro_cny':amount}
    def test_zero_submitted_is_known_zero_not_capture_completion(self):
        r=audit.usage_totals([self.row('NOT_SUBMITTED')])
        self.assertEqual(r['peak_usage_estimate_cny'],0)
        self.assertNotIn('complete_captures_and_delivery',r)
    def test_captured_known_usage_has_exact_subtotal(self):
        r=audit.usage_totals([self.row('RESPONSE_CAPTURED',1200),self.row('RESPONSE_CAPTURED',800)])
        self.assertEqual(r['peak_usage_estimate_cny'],0.002)
        self.assertTrue(r['estimate_complete'])
    def test_unknown_submission_makes_total_null(self):
        r=audit.usage_totals([self.row('RESPONSE_CAPTURED',1200),self.row('SUBMITTED_STATUS_UNKNOWN')])
        self.assertIsNone(r['peak_usage_estimate_cny'])
        self.assertEqual(r['known_peak_usage_subtotal_cny'],0.0012)
        self.assertEqual(r['unestimated_submitted_call_count'],1)
    def test_legacy_rejected_missing_usage_is_not_zero(self):
        r=audit.usage_totals([self.row('RESPONSE_REJECTED')])
        self.assertIsNone(r['peak_usage_estimate_cny'])
        self.assertFalse(r['estimate_complete'])
    def test_rejected_with_valid_usage_still_counts(self):
        r=audit.usage_totals([self.row('RESPONSE_REJECTED',2700)])
        self.assertEqual(r['peak_usage_estimate_cny'],0.0027)
    def test_local_zero_only_when_explicitly_estimated(self):
        r=audit.usage_totals([self.row('LOCAL_REJECTED_BEFORE_NETWORK',0)])
        self.assertEqual(r['peak_usage_estimate_cny'],0)
        self.assertTrue(r['estimate_complete'])
    def test_missing_estimate_stays_unknown_despite_success_status(self):
        r=audit.usage_totals([self.row('RESPONSE_CAPTURED')])
        self.assertFalse(r['estimate_complete'])
        self.assertIsNone(r['peak_usage_estimate_cny'])
    def test_unsubmitted_does_not_fake_unknown_charge(self):
        r=audit.usage_totals([self.row('RESPONSE_CAPTURED',1000)]+[self.row('NOT_SUBMITTED')]*23)
        self.assertEqual(r['unestimated_submitted_call_count'],0)
        self.assertEqual(r['peak_usage_estimate_cny'],0.001)


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    sources=[Path(__file__),Path(audit.__file__)]
    with zipfile.ZipFile(OUT/'TESTED_SOURCE.zip','x',zipfile.ZIP_DEFLATED) as z:
        for p in sources:z.writestr(p.relative_to(audit.ROOT).as_posix(),p.read_bytes())
    with (OUT/'TESTS.log').open('x',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AccountingTests))
    report={'tests':result.testsRun,'passed':result.wasSuccessful(),'target_calls':0,'semantic_acceptance':False,
            'source_snapshot_sha256':file_sha(OUT/'TESTED_SOURCE.zip')}
    (OUT/'TESTS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'output':OUT.relative_to(audit.ROOT).as_posix(),**report}))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
