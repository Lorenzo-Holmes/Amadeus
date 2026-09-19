"""Offline contract tests for probe_03."""
from __future__ import annotations
import json,sqlite3,unittest,zipfile
from datetime import datetime,timezone
from pathlib import Path
import epistemic_diagnostic_v3_r047 as w
from transcript_store import file_sha

OUT=w.PLAN/'evidence/R047-03/epistemic_repair_20260911'/('probe03_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
class Tests(unittest.TestCase):
    def test_scope_is_fixed14_and_under_threshold(self):
        scope=w.fixed_scope()[0]
        self.assertEqual(len(scope['slots']),14); self.assertEqual({s['case_id'] for s in scope['slots']},{'N08','N11','R02'})
        self.assertEqual(scope['total_guard_cny'],19); self.assertLess(scope['reserved_upper_micro_cny'],20_000_000)
    def test_probe02_unknown_is_quarantined(self):
        r=w.readiness(require_regression=False)
        self.assertEqual(r['quarantined_probe02_call']['call_id'],w.OLD_UNKNOWN)
        self.assertFalse(r['quarantined_probe02_call']['resend_allowed'])
    def test_probe02_terminal_counts_are_preserved(self):
        r=w.readiness(require_regression=False)
        self.assertEqual(r['probe02_counts'],{'RESPONSE_CAPTURED':12,'SUBMITTED_STATUS_UNKNOWN':1})
    def test_no_active_unknown_remains(self):
        self.assertEqual(w.readiness(require_regression=False)['unknown_policy']['active_unresolved_remote_unknowns'],[])
    def test_no_reconfirm_required_below20(self):
        self.assertLess(w.GUARD_CNY,20)

def main():
    OUT.mkdir(parents=True,exist_ok=False); files=[Path(__file__),Path(w.__file__)]
    with zipfile.ZipFile(OUT/'TESTED_SOURCE.zip','x',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.writestr(p.relative_to(w.ROOT).as_posix(),p.read_bytes())
    with (OUT/'TESTS.log').open('x',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    report={'tests':result.testsRun,'passed':result.wasSuccessful(),'target_calls':0,'network_calls':0,'source_snapshot_sha256':file_sha(OUT/'TESTED_SOURCE.zip')}
    (OUT/'TESTS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'output':OUT.relative_to(w.ROOT).as_posix(),**report})); return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
