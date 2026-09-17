"""Offline gate tests for the probe_02 continuation driver."""
from __future__ import annotations
import json, sqlite3, unittest, zipfile
from datetime import datetime, timezone
from pathlib import Path
import continue_epistemic_probe02_r047 as cont
import epistemic_diagnostic_v2_r047 as probe
import execute_r047 as generic
from transcript_store import file_sha

OUT=probe.PLAN/'evidence/R047-03/epistemic_repair_20260911'/('probe02_cont_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))

class ContinuationTests(unittest.TestCase):
    def test_generic_bug_is_not_used_by_continuation(self):
        source=Path(cont.__file__).read_text(encoding='utf-8')
        self.assertNotIn("N01_T1','N01_T2','N01_T3",source)
        self.assertIn("scope['slots'][:3]",source)
    def test_generic_rest_gate_is_scope_relative(self):
        source=Path(generic.__file__).read_text(encoding='utf-8')
        self.assertNotIn("N01_T1','N01_T2','N01_T3",source)
        self.assertIn("scope['slots'][:3]",source)
    def test_continuation_is_bound_to_probe02_only(self):
        self.assertEqual(cont.BATCH,'APCORE-R047-EPISTEMIC-DIAGNOSTIC-02')
        self.assertEqual(probe.GUARD_CNY,35)
    def test_old_unknown_remains_nonresendable(self):
        manifest=probe.common.read_json(probe.REV/'MANIFEST.json')
        self.assertFalse(manifest['old_unknown_resend_allowed'])
        self.assertFalse(manifest['old_batch_resume_allowed'])
    def test_current_real_first3_is_clean(self):
        db=sqlite3.connect((probe.LIVE/'runtime.sqlite3').as_uri()+'?mode=ro',uri=True)
        try:
            scope=probe.load()[0]; ids=[s['id'] for s in scope['slots'][:3]]
            rows=db.execute('SELECT slot_id,status FROM provider_calls WHERE batch_id=? AND slot_id IN (?,?,?)',
                            (cont.BATCH,*ids)).fetchall()
            self.assertEqual(set(rows),{(ids[0],'RESPONSE_CAPTURED'),(ids[1],'RESPONSE_CAPTURED'),(ids[2],'RESPONSE_CAPTURED')})
            unknown=db.execute("SELECT slot_id FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchall()
            self.assertEqual(unknown,[('N08_T1',)])
        finally: db.close()
    def test_probe02_terminal_history_is_preserved(self):
        db=sqlite3.connect((probe.LIVE/'runtime.sqlite3').as_uri()+'?mode=ro',uri=True)
        try:
            self.assertEqual(db.execute('SELECT count(*) FROM provider_calls').fetchone()[0],13)
            self.assertEqual(db.execute("SELECT count(*) FROM provider_calls WHERE status='RESPONSE_CAPTURED'").fetchone()[0],12)
            self.assertEqual(db.execute('SELECT stopped FROM call_batches WHERE batch_id=?',(cont.BATCH,)).fetchone()[0],1)
        finally:db.close()

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__),Path(cont.__file__),Path(probe.__file__)]
    with zipfile.ZipFile(OUT/'TESTED_SOURCE.zip','x',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.writestr(p.relative_to(probe.ROOT).as_posix(),p.read_bytes())
    with (OUT/'TESTS.log').open('x',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContinuationTests))
    report={'tests':result.testsRun,'passed':result.wasSuccessful(),'target_calls':0,'network_calls':0,
            'source_snapshot_sha256':file_sha(OUT/'TESTED_SOURCE.zip')}
    (OUT/'TESTS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'output':OUT.relative_to(probe.ROOT).as_posix(),**report}))
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
