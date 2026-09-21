"""Exercise the actual bounded diagnostic driver with labelled offline replies."""
from __future__ import annotations
import contextlib
import copy
import io
import json
import shutil
import sqlite3
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
import epistemic_diagnostic_r047 as w
import execute_r047 as driver
from provider import canonical
from transcript_store import StoreGuard

REAL=w.REV
OUT=REAL/('tests_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
OPEN=driver.open_chat


def activate(path):w.REV=path;w.LIVE=path/'live'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def tree(root):return {p.relative_to(root).as_posix():w.common.file_sha(p) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
def transport_chat(store,handle,scope):
    chat=OPEN(store,handle,scope)
    send=chat.send_text
    def transport(payload,key):
        request=json.loads(payload)
        with (w.REV/'OFFLINE_CALLS.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'model':request['model'],'origin':'AUTHORED_TEST_FIXTURE'})+'\n')
        return 200,canonical({'model':'deepseek-flash','choices':[{'finish_reason':'stop','message':{'content':'这是明确标记的离线测试答复。'}}],
                             'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120}})
    def bound(*args,**kwargs):return send(*args,**kwargs,transport=transport,credential_reader=lambda:'AUTHORED_OFFLINE_NOT_SECRET')
    chat.send_text=bound
    return chat
def run_first():
    with patch.object(driver,'open_chat',transport_chat),contextlib.redirect_stdout(io.StringIO()):
        return w.dispatch('execute',['--phase','first'])
def count():
    path=w.REV/'OFFLINE_CALLS.jsonl'
    return len(path.read_text().splitlines()) if path.exists() else 0
def db():return sqlite3.connect(w.LIVE/'runtime.sqlite3')


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=OUT/'base';cls.base.mkdir()
        for name in ('MANIFEST.json','EXECUTION_SCOPE.json','OFFICIAL_PREFLIGHT.json'):shutil.copy2(REAL/name,cls.base/name)
        activate(cls.base)
        with contextlib.redirect_stdout(io.StringIO()):w.dispatch('prepare',[])
        activate(REAL)
    def setUp(self):
        self.path=OUT/self._testMethodName
        shutil.copytree(self.base,self.path);activate(self.path)
    def tearDown(self):activate(REAL)
    def test_preparation_has_no_real_or_authored_target_turns(self):
        scope=w.load()[0]
        self.assertEqual(len(scope['slots']),38)
        with db() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM provider_calls').fetchone()[0],0)
            for identity in read(w.LIVE/'FIXTURE_PREPARATION.json')['sessions'].values():
                self.assertEqual(c.execute('SELECT count(*) FROM turns WHERE session_id=?',(identity['session_id'],)).fetchone()[0],0)
    def test_prepare_cannot_replace_existing_runtime(self):
        before=tree(w.REV)
        with self.assertRaises(StoreGuard):w.dispatch('prepare',[])
        self.assertEqual(tree(w.REV),before)
    def test_first_phase_reentry_does_not_resubmit(self):
        self.assertEqual(run_first(),0);self.assertEqual(run_first(),0)
        self.assertEqual(count(),3)
    def test_unknown_blocks_before_new_transport(self):
        self.assertEqual(run_first(),0)
        with db() as c:c.execute("UPDATE provider_calls SET status='SUBMITTED_STATUS_UNKNOWN' WHERE slot_id='N01_T1'")
        self.assertEqual(run_first(),2);self.assertEqual(count(),3)
    def test_stopped_batch_not_unlocked(self):
        with db() as c:c.execute('UPDATE call_batches SET stopped=1')
        self.assertEqual(run_first(),2);self.assertEqual(count(),0)
        with db() as c:self.assertEqual(c.execute('SELECT stopped FROM call_batches').fetchone()[0],1)
    def test_stale_driver_requires_reconciliation(self):
        with db() as c:c.execute("INSERT INTO metadata VALUES('r047_active_driver',?)",('{"run_id":"stale","pid":-1}',))
        self.assertEqual(run_first(),2);self.assertEqual(count(),0)
        with db() as c:self.assertIn('stale',c.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone()[0])
    def test_mutated_scope_rejected_even_with_rebound_hash(self):
        scope=read(w.REV/'EXECUTION_SCOPE.json');scope['slots'][0]['user_text']='tampered'
        (w.REV/'EXECUTION_SCOPE.json').write_text(json.dumps(scope),encoding='utf-8')
        manifest=read(w.REV/'MANIFEST.json');manifest['scope_sha256']=w.common.file_sha(w.REV/'EXECUTION_SCOPE.json')
        (w.REV/'MANIFEST.json').write_text(json.dumps(manifest),encoding='utf-8')
        with self.assertRaises(StoreGuard):w.load()
    def test_audit_keeps_38_and_rejects_authored_capture_as_real(self):
        self.assertEqual(run_first(),0)
        with contextlib.redirect_stdout(io.StringIO()):w.dispatch('audit',[])
        path=next((w.REV/'evidence/R047-02').glob('audit_*/CAPTURE_AUDIT.json'))
        audit=read(path)
        self.assertEqual(audit['frozen_denominator'],38)
        self.assertEqual(len(audit['records']),38)
        self.assertFalse(audit['complete_captures_and_delivery'])
        self.assertFalse(audit['full82_acceptance_claim'])
        self.assertTrue(any(f['code']=='AUTHORED_CAPTURE_NOT_REAL_TARGET' for f in audit['binding_findings']))
        self.assertFalse(audit['quality_gate_passed'])


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    before=tree(w.parent.LIVE)
    with (OUT/'TESTS.log').open('x',encoding='utf-8') as f:
        result=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DiagnosticTests))
    unchanged=before==tree(w.parent.LIVE)
    report={'tests':result.testsRun,'passed':result.wasSuccessful() and unchanged,'errors':len(result.errors),'failures':len(result.failures),
            'parent_live_unchanged':unchanged,'target_network_calls':0,'authored_fixture_answers_only':True,
            'source_bindings':w.common.source_bindings()}
    w.dump(OUT/'TESTS.json',report)
    print(json.dumps({'output':OUT.relative_to(w.ROOT).as_posix(),**{k:report[k] for k in ('tests','passed','errors','failures','target_network_calls')}}))
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
