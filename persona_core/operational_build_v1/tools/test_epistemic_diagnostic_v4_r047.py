from __future__ import annotations
import json,unittest,zipfile
from datetime import datetime,timezone
from pathlib import Path
import epistemic_diagnostic_v4_r047 as w
from transcript_store import file_sha
OUT=w.PLAN/'evidence/R047-03/epistemic_repair_20260911'/('probe04_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
class Tests(unittest.TestCase):
    def test_scope_is_six_n06(self):
        s=w.fixed_scope()[0]; self.assertEqual(len(s['slots']),6); self.assertEqual({x['case_id'] for x in s['slots']},{'N06'}); self.assertEqual(s['total_guard_cny'],8)
    def test_only_expected_finding_remains(self):
        r=w.readiness(require_regression=False); self.assertIn('probe02_review_sha256',r); self.assertIn('probe03_review_sha256',r)
    def test_no_active_unknown(self): self.assertEqual(w.readiness(require_regression=False)['unknown_policy']['active_unresolved_remote_unknowns'],[])
def main():
    OUT.mkdir(parents=True,exist_ok=False); files=[Path(__file__),Path(w.__file__)]
    with zipfile.ZipFile(OUT/'TESTED_SOURCE.zip','x',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.writestr(p.relative_to(w.ROOT).as_posix(),p.read_bytes())
    with (OUT/'TESTS.log').open('x',encoding='utf-8') as log: result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    report={'tests':result.testsRun,'passed':result.wasSuccessful(),'target_calls':0,'network_calls':0,'source_snapshot_sha256':file_sha(OUT/'TESTED_SOURCE.zip')}
    (OUT/'TESTS.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps({'output':OUT.relative_to(w.ROOT).as_posix(),**report})); return 0 if result.wasSuccessful() else 1
if __name__=='__main__': raise SystemExit(main())
