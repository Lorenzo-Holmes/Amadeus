"""Offline tests for historical remote-UNKNOWN quarantine semantics."""
from __future__ import annotations
import json
import sqlite3
import unittest
import zipfile
from datetime import datetime,timezone
from pathlib import Path
import unknown_quarantine_r047 as q
from transcript_store import file_sha

OUT=q.BASE/'epistemic_repair_20260911'/('quarantine_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))

def mini_journal(base,name,rows):
    path=base/name/'live/runtime.sqlite3';path.parent.mkdir(parents=True)
    db=sqlite3.connect(path)
    db.execute('CREATE TABLE provider_calls(call_id TEXT,batch_id TEXT,slot_id TEXT,status TEXT,error_category TEXT,submitted_at_utc TEXT)')
    db.executemany('INSERT INTO provider_calls VALUES(?,?,?,?,?,?)',[(a,b,c,d,e,str(i)) for i,(a,b,c,d,e) in enumerate(rows)])
    db.commit();db.close();return path

class QuarantineTests(unittest.TestCase):
    def setUp(self):self.root=OUT/self._testMethodName;self.root.mkdir(parents=True)
    def test_project_quarantine_validates_real_unknown_without_resolving_it(self):
        values=q.validated_quarantined_unknowns()
        item=values['call_b0a10f775d26445cb6402b8a012917bc']
        self.assertEqual(item['remote_outcome'],'UNKNOWN')
        self.assertFalse(item['resend_allowed'])
        self.assertTrue(item['new_independent_batch_allowed'])
    def test_project_scan_has_no_active_unknown_after_quarantine(self):
        state=q.project_unknown_status()
        self.assertEqual(state['active_unresolved_remote_unknowns'],[])
        ids={r['call_id'] for r in state['allowed_historical_unknowns']}
        self.assertIn('call_b0a10f775d26445cb6402b8a012917bc',ids)
        self.assertIn('call_65df5a4dbb844432bdad8e63a8c68db5',ids)
    def test_unlisted_unknown_still_blocks(self):
        mini_journal(self.root,'future',[('new','b','s','SUBMITTED_STATUS_UNKNOWN','TimeoutError')])
        state=q.scan_unknowns(self.root,set())
        self.assertEqual([x['call_id'] for x in state['active_unresolved_remote_unknowns']],['new'])
    def test_test_allowlist_does_not_rewrite_row(self):
        path=mini_journal(self.root,'historical',[('old','b','s','SUBMITTED_STATUS_UNKNOWN','StoreGuard')])
        state=q.scan_unknowns(self.root,{'old'})
        self.assertEqual(state['active_unresolved_remote_unknowns'],[])
        db=sqlite3.connect(path)
        try:self.assertEqual(db.execute('SELECT status FROM provider_calls').fetchone()[0],'SUBMITTED_STATUS_UNKNOWN')
        finally:db.close()
    def test_nested_fixture_not_scanned(self):
        mini_journal(self.root/'offline','caseA',[('fixture','b','s','SUBMITTED_STATUS_UNKNOWN','Authored')])
        self.assertEqual(q.scan_unknowns(self.root,set())['raw_unknowns'],[])
    def test_multiroot_project_scan_covers_r047_04(self):
        state=q.project_unknown_status()
        roots={row['evidence_root'] for row in state['raw_unknowns']}
        self.assertIn('evidence/R047-03',roots)
        self.assertIn('evidence/R047-04',roots)
        r04=[row for row in state['raw_unknowns'] if row['evidence_root']=='evidence/R047-04']
        self.assertTrue(any(row['slot_id']=='N07_T1' for row in r04))

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__),Path(q.__file__)]
    with zipfile.ZipFile(OUT/'TESTED_SOURCE.zip','x',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.writestr(p.relative_to(q.ROOT).as_posix(),p.read_bytes())
    with (OUT/'TESTS.log').open('x',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(QuarantineTests))
    report={'tests':result.testsRun,'passed':result.wasSuccessful(),'target_calls':0,'network_calls':0,
            'semantic_acceptance':False,'source_snapshot_sha256':file_sha(OUT/'TESTED_SOURCE.zip')}
    (OUT/'TESTS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'output':OUT.relative_to(q.ROOT).as_posix(),**report}))
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
