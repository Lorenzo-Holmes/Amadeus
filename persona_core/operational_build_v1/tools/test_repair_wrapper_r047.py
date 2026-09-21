"""Actual isolated prepare/driver paths using explicitly authored provider replies."""
from __future__ import annotations
import contextlib,copy,hashlib,io,json,os,shutil,sqlite3,subprocess,sys,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
import repair_revision_r047 as wrapper
import execute_r047 as driver
from provider import canonical
from transcript_store import StoreGuard

ROOT=wrapper.ROOT
REAL_REV=wrapper.REV
OUT=REAL_REV/('wrapper_tests_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
CHECKS=[]
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def hashes(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
def activate(rev):wrapper.REV=Path(rev);wrapper.LIVE=wrapper.REV/'live'
def clone_config(destination):
    destination.mkdir(parents=True)
    for name in ['EXECUTION_SCOPE.json','REVISION.json','OFFICIAL_PREFLIGHT.json']:
        shutil.copy2(REAL_REV/name,destination/name)
def offline_chat(store,handle,scope):
    chat=ORIGINAL_OPEN_CHAT(store,handle,scope)
    actual_send=chat.send_text
    def transport(payload,key):
        body=json.loads(payload)
        with (wrapper.REV/'OFFLINE_TRANSPORT_COUNT.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps({'model':body['model'],'origin':'AUTHORED_TEST_FIXTURE','pid':os.getpid()})+'\n')
        return 200,canonical({'model':body['model'],'choices':[{'finish_reason':'stop','message':{'content':'这是明确标记的离线流程测试答复。'}}],
            'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120}})
    def send(*args,**kwargs):
        return actual_send(*args,**kwargs,transport=transport,credential_reader=lambda:'AUTHORED_NOT_A_CREDENTIAL')
    chat.send_text=send
    return chat
ORIGINAL_OPEN_CHAT=driver.open_chat
def run_driver(phase):
    with patch.object(driver,'open_chat',offline_chat):
        return wrapper.dispatch('execute',['--phase',phase])
def captured_count(rev):
    p=rev/'OFFLINE_TRANSPORT_COUNT.jsonl'
    return len(p.read_text().splitlines()) if p.exists() else 0
def db(rev):return sqlite3.connect(rev/'live/runtime.sqlite3')

class WrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=OUT/'prepared_base'
        clone_config(cls.base)
        activate(cls.base)
        with contextlib.redirect_stdout(io.StringIO()):wrapper.dispatch('prepare',[])
        cls.prepared_hashes=hashes(cls.base/'live')
    def setUp(self):
        self.rev=OUT/self._testMethodName
        shutil.copytree(self.base,self.rev)
        activate(self.rev)
    def tearDown(self):activate(REAL_REV)
    def test_real_prepare_isolated_no_calls_no_original_mutation(self):
        with db(self.rev) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM provider_calls').fetchone()[0],0)
            self.assertEqual(connection.execute('SELECT batch_id FROM call_batches').fetchone()[0],wrapper.BATCH)
        self.assertTrue((self.rev/'PREPARE_COMPLETE.json').is_file())
        before=hashes(self.rev)
        with self.assertRaises(StoreGuard):wrapper.dispatch('prepare',[])
        self.assertEqual(hashes(self.rev),before)
    def test_exclusive_stale_prepare_intent_rejects_before_runtime_creation(self):
        empty=OUT/'intent_only'
        clone_config(empty)
        activate(empty)
        wrapper.dump(empty/'PREPARE_INTENT.json',{'pid':-1,'status':'unreconciled'})
        with self.assertRaises(FileExistsError):wrapper.dispatch('prepare',[])
        self.assertFalse((empty/'live').exists())
    def test_first_driver_real_capture_then_second_run_no_resend(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_driver('first'),0)
            self.assertEqual(run_driver('first'),0)
        self.assertEqual(captured_count(self.rev),3)
        with db(self.rev) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM provider_calls').fetchone()[0],3)
            self.assertEqual(connection.execute('SELECT DISTINCT capture_origin FROM provider_calls').fetchone()[0],'AUTHORED_PROVIDER_TEST_FIXTURE')
        self.assertEqual(driver.LIVE,wrapper.original.LIVE)
    def test_stale_driver_lease_refuses_without_transport_or_clearing(self):
        marker=canonical({'run_id':'unreconciled','pid':-1}).decode()
        with db(self.rev) as connection:connection.execute("INSERT INTO metadata VALUES('r047_active_driver',?)",(marker,))
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(run_driver('first'),2)
        self.assertEqual(captured_count(self.rev),0)
        with db(self.rev) as connection:
            self.assertEqual(connection.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone()[0],marker)
    def test_unknown_submission_blocks_further_calls(self):
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(run_driver('first'),0)
        with db(self.rev) as connection:
            connection.execute("UPDATE provider_calls SET status='SUBMITTED_STATUS_UNKNOWN' WHERE slot_id='N01_T1'")
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(run_driver('first'),2)
        self.assertEqual(captured_count(self.rev),3)
        with db(self.rev) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchone()[0],1)
    def test_named_official_preflight_required_not_old_fallback(self):
        (self.rev/'OFFICIAL_PREFLIGHT.json').rename(self.rev/'REMOVED_FOR_TEST.json')
        with self.assertRaises(FileNotFoundError):run_driver('first')
        self.assertEqual(captured_count(self.rev),0)
    def test_scope_semantic_mutation_with_rebound_filehash_rejected(self):
        value=read(self.rev/'EXECUTION_SCOPE.json')
        value['slots'][0]['user_text']='changed fixed user input'
        (self.rev/'EXECUTION_SCOPE.json').write_text(json.dumps(value),encoding='utf-8')
        manifest=read(self.rev/'REVISION.json')
        manifest['scope_file_sha256']=wrapper.original.file_sha(self.rev/'EXECUTION_SCOPE.json')
        (self.rev/'REVISION.json').write_text(json.dumps(manifest),encoding='utf-8')
        with self.assertRaises(StoreGuard):wrapper.load_revision()
        child=subprocess.run([sys.executable,'-B','-O',str(Path(__file__)),'--load-only',str(self.rev)],cwd=ROOT,capture_output=True,text=True)
        self.assertNotEqual(child.returncode,0)
        self.assertIn('Repair scope differs beyond',child.stderr)
    def test_parent_taxonomy_separate_and_audit_never_calls_fixture_real(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_driver('first'),0)
            wrapper.dispatch('audit',[])
        audits=list((self.rev/'evidence/R047-02').glob('audit_*/CAPTURE_AUDIT.json'))
        self.assertEqual(len(audits),1)
        audit=read(audits[0])
        self.assertTrue(audit['known_development_regression'])
        self.assertFalse(audit['new_heldout_claim'])
        self.assertEqual(len(audit['records']),82)
        self.assertTrue(all(r['evaluation_phase']==wrapper.KNOWN for r in audit['records']))
        self.assertTrue(any(f['code']=='AUTHORED_CAPTURE_NOT_REAL_TARGET' for f in audit['binding_findings']))
        review_input=read(audits[0].parent/'N01_REVIEW_INPUT.json')
        self.assertEqual(review_input['case']['parent_classification'],'NEW_AT_FREEZE')
        self.assertEqual(review_input['case']['current_evaluation_classification'],wrapper.KNOWN)
        self.assertFalse(review_input['new_heldout_claim'])

def main():
    if len(sys.argv)>1 and sys.argv[1]=='--load-only':
        activate(Path(sys.argv[2]));wrapper.load_revision();return
    OUT.mkdir(parents=True,exist_ok=False)
    before=hashes(wrapper.original.LIVE)
    original_scope=wrapper.original.file_sha(wrapper.original.FREEZE/'EXECUTION_SCOPE.json')
    with (OUT/'TESTS.log').open('x',encoding='utf-8') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(WrapperTests))
    unchanged=hashes(wrapper.original.LIVE)==before
    report={'at_utc':datetime.now(timezone.utc).isoformat(),'tests':result.testsRun,'passed':result.wasSuccessful() and unchanged,
        'original_live_files_unchanged':unchanged,'original_scope_unchanged':original_scope==wrapper.original.file_sha(wrapper.original.FREEZE/'EXECUTION_SCOPE.json'),
        'real_repair_runtime_created':(REAL_REV/'live').exists(),'target_network_calls':0,
        'all_replies':'AUTHORED_PROVIDER_TEST_FIXTURE','semantic_acceptance_proven':False,
        'tested_sources':wrapper.original.source_bindings()}
    wrapper.dump(OUT/'TESTS.json',report)
    print(json.dumps({'output':str(OUT.relative_to(ROOT)),'tests':result.testsRun,'passed':report['passed'],'original_live_unchanged':unchanged,'target_calls':0}))
    raise SystemExit(0 if report['passed'] else 1)
if __name__=='__main__':main()
