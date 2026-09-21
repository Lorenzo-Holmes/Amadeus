"""Zero-call construction and authored-probe entry use the actual runtime."""
from pathlib import Path
from contextlib import ExitStack
import socket,sys,unittest,uuid
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'persona_core/operational_runtime_v1'),str(Path(__file__).parent)]
import structural_preflight as sp
import structural_test_support as f
import calibration_journal as cj
from transcript_store import TranscriptStore
from operations import open_chat

class StructuralPreflightTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for name in ('connect','connect_ex'):
            self.stack.enter_context(patch.object(socket.socket,name,side_effect=AssertionError('NO_NETWORK')))
        self.base=ROOT/'work/deepseek_successor/structural_tests'/uuid.uuid4().hex
        self.probe={'id':'LOCAL_PROBE','input':'给定这一步算式为2+3，请复述其结果。','authored_draft':'结果是5。'}
        self.scope=f.scope_fixture(self.base/'config',probes=[self.probe])
        self.root=self.base/'scope'
        self.sessions=sp.prepare_smoke(self.root,self.scope)

    def test_prepared_scope_constructs_both_stages_without_submission(self):
        import provider
        with patch.object(provider.ProviderJournal,'call',side_effect=AssertionError('NO_CALL')) as first, \
             patch.object(cj,'run_input',side_effect=AssertionError('NO_CALIBRATION')) as second:
            result=sp.inspect_prepared(self.root,self.scope,self.sessions)
        first.assert_not_called();second.assert_not_called()
        self.assertEqual(result['status'],'READY')
        self.assertEqual(len(result['slot_checks']),44)
        self.assertEqual(len(result['initial_context_checks']),44)
        self.assertEqual(len(result['authored_probe_checks']),1)
        self.assertEqual(result['provider_call_rows'],0);self.assertEqual(result['calibration_call_rows'],0)

    def test_probe_uses_one_real_mock_wire_stage_no_display_no_observation(self):
        store=TranscriptStore(self.root/'runtime');self.addCleanup(store.close)
        if store:
            h=store.resume(self.scope['principal_id'],self.sessions[self.probe['id']])
            supplied,messages=sp.probe_input(store,h,self.scope,self.probe)
            sent=[];case={'draft':self.probe['authored_draft'],'final':self.probe['authored_draft'],'decision':'KEEP'}
            transport=f.transport_for(self.scope,case,sent)
            result=cj.run_input(store,h,self.scope,self.probe['id'],supplied,messages,
                transport=transport,credential_reader=lambda:f.wire_fixture.KEY)
            self.assertEqual(result['decision'],'KEEP');self.assertEqual(len(sent),1)
            self.assertEqual(cj.counts(store.db,self.scope['batch_id']),
                {'product_turns_submitted':0,'draft_calls':0,'calibration_calls':1,'total_provider_requests':1})
            self.assertEqual(store.db.execute('SELECT count(*) FROM runtime_events').fetchone()[0],0)
            self.assertEqual(store.db.execute('SELECT count(*) FROM display_journal').fetchone()[0],0)
            cj.run_input(store,h,self.scope,self.probe['id'],supplied,messages,
                transport=transport,credential_reader=lambda:f.wire_fixture.KEY)
            self.assertEqual(len(sent),1)

    def test_probe_cannot_replace_preregistered_draft(self):
        store=TranscriptStore(self.root/'runtime');self.addCleanup(store.close)
        h=store.resume(self.scope['principal_id'],self.sessions[self.probe['id']])
        supplied,messages=sp.probe_input(store,h,self.scope,self.probe)
        supplied['DRAFT']='新的未登记初稿'
        with self.assertRaisesRegex(ValueError,'SUPPLIED_IDENTITY'):
            cj.run_input(store,h,self.scope,self.probe['id'],supplied,messages)
        self.assertEqual(cj.counts(store.db,self.scope['batch_id'])['total_provider_requests'],0)

    def test_revision_read_recognizes_stage_scope_and_run_requires_one_turn(self):
        import evaluation_runner as er
        binding=self.scope['semantic_acceptance_binding']
        prep={'semantic_acceptance_binding':binding,'sessions':{s['case_id']:{'session_id':self.sessions[s['id']]}
              for s in self.scope['slots']}}
        f.write(self.root/'PREPARATION.json',prep)
        manifest={'revision_id':'structural_offline_read','formal_validation':True,'capture_mode':er.OFFLINE,
                  'offline_construction_root':er.relative(self.root),'semantic_acceptance_binding':binding,
                  'artifacts':{n:er.sha(self.root/n) for n in ('SCOPE.json','PREPARATION.json')}}
        manifest.update({k:binding[k] for k in ('semantic_acceptance_mode','acceptance_policy_version',
            'acceptance_source_freeze','trusted_semantic_runtime_version','provider_config_identity','dataset_identity','rubric_identity')})
        f.write(self.root/'MANIFEST.json',manifest)
        f.write(self.root/'MANIFEST_SEAL.json',{'sha256':er.sha(self.root/'MANIFEST.json')})
        self.assertEqual(er.read_contract(self.root),(manifest,self.scope,prep))
        self.assertEqual(er.segment_worker_deadline(self.scope,1),1320)
        self.assertEqual(er.segment_worker_deadline(dict(self.scope,schema_version='apcore-provider-scope-9'),1),720)
        with patch.object(er,'verify_sources',return_value=(manifest,self.scope,prep)):
            with self.assertRaisesRegex(ValueError,'ONE_TURN_THEN_REVIEW'):
                er.run('unused_offline',execute=False,max_turns=2)

if __name__=='__main__':unittest.main()
