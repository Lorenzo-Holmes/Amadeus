"""No-network discovery tests for cross-batch unknown-request protection."""
from __future__ import annotations
import json
import unittest
import zipfile
from datetime import datetime,timezone
from pathlib import Path
import repair_revision_r047_v6 as gate
from transcript_store import file_sha

OUT=gate.PLAN/'evidence/R047-03/epistemic_repair_20260911'/('live_guard_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.base=OUT/self._testMethodName;self.base.mkdir(parents=True)
    def live(self,name):
        p=self.base/name/'live';p.mkdir(parents=True);(p/'runtime.sqlite3').write_bytes(b'OFFLINE_DISCOVERY_ONLY_NOT_A_DB')
        return p.parent
    def test_new_diagnostic_name_is_included(self):
        p=self.live('epistemic_probe_01');self.assertEqual(gate.direct_live_roots(self.base),[p])
    def test_arbitrary_future_name_cannot_bypass_guard(self):
        p=self.live('future-named-diagnostic');self.assertEqual(gate.direct_live_roots(self.base),[p])
    def test_historical_repair_and_capacity_names_still_included(self):
        a=self.live('repair_06');b=self.live('capacity_probe_01');self.assertEqual(gate.direct_live_roots(self.base),sorted([a,b]))
    def test_nested_offline_fixtures_are_not_direct_live(self):
        self.live('tests/caseA');self.assertEqual(gate.direct_live_roots(self.base),[])
    def test_journal_must_be_a_file(self):
        p=self.base/'invalid/live/runtime.sqlite3';p.mkdir(parents=True)
        self.assertEqual(gate.direct_live_roots(self.base),[])
    def test_discovery_neither_creates_nor_modifies_files(self):
        p=self.live('sourceA');before=file_sha(p/'live/runtime.sqlite3')
        self.assertEqual(gate.direct_live_roots(self.base),[p])
        self.assertEqual(file_sha(p/'live/runtime.sqlite3'),before)


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(OUT/'TESTED_SOURCE.zip','x',zipfile.ZIP_DEFLATED) as z:
        for p in (Path(__file__),Path(gate.__file__)):z.writestr(p.relative_to(gate.ROOT).as_posix(),p.read_bytes())
    with (OUT/'TESTS.log').open('x',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DiscoveryTests))
    report={'tests':result.testsRun,'passed':result.wasSuccessful(),'target_calls':0,'semantic_acceptance':False,
            'source_snapshot_sha256':file_sha(OUT/'TESTED_SOURCE.zip')}
    (OUT/'TESTS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'output':OUT.relative_to(gate.ROOT).as_posix(),**report}))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
