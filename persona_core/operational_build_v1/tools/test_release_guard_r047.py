"""Offline fail-closed release guard tests; no provider or candidate launch."""
from __future__ import annotations
import json
import sqlite3
import unittest
import zipfile
from datetime import datetime,timezone
from pathlib import Path
import build_release_r047 as release
from transcript_store import file_sha

OUT=release.PLAN/'evidence/R047-05'/('guard_tests_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))

def journal(base,name,rows):
    path=base/name/'live/runtime.sqlite3';path.parent.mkdir(parents=True)
    db=sqlite3.connect(path)
    db.execute('CREATE TABLE provider_calls(call_id TEXT,batch_id TEXT,slot_id TEXT,status TEXT,error_category TEXT)')
    db.executemany('INSERT INTO provider_calls VALUES(?,?,?,?,?)',rows);db.commit();db.close()
    return path

class ReleaseGuardTests(unittest.TestCase):
    def setUp(self):
        self.root=OUT/self._testMethodName;self.root.mkdir(parents=True)
    def test_captured_only_is_release_clean(self):
        journal(self.root,'repair_x',[('c1','b','s','RESPONSE_CAPTURED',None)])
        self.assertEqual(release.unresolved_remote_requests(self.root,set()),[])
    def test_unknown_blocks_release(self):
        journal(self.root,'diagnostic_new',[('c2','b2','s2','SUBMITTED_STATUS_UNKNOWN','TimeoutError')])
        rows=release.unresolved_remote_requests(self.root,set())
        self.assertEqual([r['call_id'] for r in rows],['c2'])
    def test_arbitrary_future_direct_name_is_scanned(self):
        journal(self.root,'future_name_999',[('c3','b3','s3','SUBMITTED_STATUS_UNKNOWN','StoreGuard')])
        self.assertEqual(release.unresolved_remote_requests(self.root,set())[0]['call_id'],'c3')
    def test_explicit_reconciled_call_can_be_excluded(self):
        journal(self.root,'old_local',[('c4','b4','s4','SUBMITTED_STATUS_UNKNOWN','StoreGuard')])
        self.assertEqual(release.unresolved_remote_requests(self.root,{'c4'}),[])
    def test_explicit_quarantined_historical_unknown_can_be_excluded(self):
        journal(self.root,'historical_remote',[('c5','b5','s5','SUBMITTED_STATUS_UNKNOWN','TimeoutError')])
        self.assertEqual(release.unresolved_remote_requests(self.root,set(),{'c5'}),[])
    def test_reconciliation_does_not_hide_another_unknown(self):
        journal(self.root,'mixed',[('old','b','s1','SUBMITTED_STATUS_UNKNOWN','StoreGuard'),
                                  ('new','b','s2','SUBMITTED_STATUS_UNKNOWN','TimeoutError')])
        self.assertEqual([r['call_id'] for r in release.unresolved_remote_requests(self.root,{'old'})],['new'])
    def test_nested_fixture_is_not_a_direct_live_root(self):
        journal(self.root/'offline_tests','caseA',[('fixture','b','s','SUBMITTED_STATUS_UNKNOWN','Authored')])
        self.assertEqual(release.unresolved_remote_requests(self.root,set()),[])
    def test_real_project_has_no_active_unclassified_unknown_after_quarantine(self):
        state=release.unknowns.project_unknown_status()
        self.assertEqual(state['active_unresolved_remote_unknowns'],[])
        quarantined=[r for r in state['allowed_historical_unknowns'] if r.get('classification')=='QUARANTINED_REMOTE_UNKNOWN']
        self.assertEqual({r['call_id'] for r in quarantined},{
            'call_b0a10f775d26445cb6402b8a012917bc',
            'call_9ee0cd0ce3d14527bf00b62866181aee',
            'call_4276419fb5b04676b61b4383b2ce8cdb',
            'call_4b009b21f57c434695112afad82a88df',
            'call_2c79fefc358d427ebf1add2acb405523',
            'call_1c8d685185f34c149a4e6588ebbbd9eb',
        })

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__),Path(release.__file__)]
    with zipfile.ZipFile(OUT/'TESTED_SOURCE.zip','x',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.writestr(p.relative_to(release.ROOT).as_posix(),p.read_bytes())
    with (OUT/'TESTS.log').open('x',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReleaseGuardTests))
    report={'tests':result.testsRun,'passed':result.wasSuccessful(),'target_calls':0,'candidate_built':False,
            'source_snapshot_sha256':file_sha(OUT/'TESTED_SOURCE.zip')}
    (OUT/'TESTS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'output':OUT.relative_to(release.ROOT).as_posix(),**report}))
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
