"""Offline formal-driver tests; synthetic catalogs never encode benchmark truth."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'persona_core/operational_runtime_v1'),str(Path(__file__).parent),
              str(ROOT/'persona_core/operational_build_v1/tools')]
import copy
import json
import os
import shutil
import sqlite3
import unittest
import uuid
from dataclasses import asdict,replace
from unittest.mock import patch
import evaluation_runner as runner
from semantic_types import *
from semantic_binding import *
from semantic_acceptance_fixtures import scenario
from semantic_renderer import render
from semantic_validator import validate
from accepted_output import load_record,session_mode,project_turn,raw_text_for_audit,SemanticAcceptance
from trusted_admission_adapter import TrustedAdmissionAdapter
from transcript_store import TranscriptStore
from operations import open_chat

def catalog(state):
    value=state.public_state()
    return {'version':ADAPTER_VERSION,**{k:value[k] for k in ('entities','sources','evidence','rules','candidates','universes')},
        'scopes':[{'scope':{'path':path},'label_id':label} for path,label in state.scope_names], 'user_report':None}

class FormalMock:
    """Real prepare/load_suite/worker/evaluator; only the transport is substituted."""
    def __init__(self,case='possible',*,config=None):
        self.name='integration_mock_'+uuid.uuid4().hex
        self.root=runner.revision_root(self.name)
        self.work=ROOT/'work/formal_acceptance_tests'/self.name
        self.work.mkdir(parents=True)
        self.case=case; self.calls=[]; self.behavior='valid'
        self.state,self.plan=scenario(case)
        self.catalog_path=self.work/'catalog.json'
        runner.write_new(self.catalog_path,catalog(self.state) if case!='unparsed' else
                         runner.read(runner.CODE/'trusted_semantic_catalog.json'))
        files=runner.source_bindings()
        files[runner.relative(self.catalog_path)]=runner.sha(self.catalog_path)
        self.freeze=self.work/'source.json'
        runner.write_new(self.freeze,{'freeze_id':'OFFLINE_TYPED_FIXTURE_'+self.name,'files':files,'status':'OFFLINE_TEST_ONLY'})
        self.config_path=self.work/'acceptance.json'
        self.config={'semantic_acceptance_mode':'TRUSTED','acceptance_policy_version':VERSION,
            'acceptance_source_freeze':'OFFLINE_TYPED_FIXTURE_'+self.name,
            'acceptance_source_manifest':{'path':runner.relative(self.freeze),'sha256':runner.sha(self.freeze)},
            'trusted_semantic_runtime_version':RUNTIME_VERSION,
            'semantic_source':{'path':runner.relative(self.catalog_path),'sha256':runner.sha(self.catalog_path)}}
        if config is not None: self.config=config(self.config)
        runner.write_new(self.config_path,self.config)
        self.transport_policy=self.work/'transport.json'
        runner.write_new(self.transport_policy,{'version':'apcore-transport-lifecycle-1','connect_timeout_seconds':15,
            'read_timeout_seconds':120,'worker_deadline_seconds':595})
        from provider_network_route import VERSION as ROUTE_VERSION,HOST
        self.route_policy=self.work/'route.json'
        runner.write_new(self.route_policy,{'version':ROUTE_VERSION,'mode':'DIRECT_NO_PROXY','host':HOST})

    def prepare(self):
        result=runner.prepare(self.name,suite='external44',offline=True,primary='deepseek-v4-pro',secondary='deepseek-flash',
            formal_validation=True,acceptance_config_file=self.config_path,api_protocol='responses',
            transport_policy_file=self.transport_policy,network_route_policy_file=self.route_policy)
        self.manifest,self.scope,self.prep=runner.read_contract(self.root)
        return result

    def transport(self,payload,credential):
        request=json.loads(payload); self.calls.append(request)
        contracts=[m for m in request['input'] if m['content'].startswith('Host semantic proposal contract:\n')]
        if len(contracts)!=1: raise AssertionError('REQUEST_CONTRACT_NOT_SENT')
        contract=json.loads(contracts[0]['content'].split('\n',1)[1])
        inv=contract['trusted_inventory']
        state=replace(self.state,identity=tuple(inv['identity']),unparsed_sha256=tuple(inv['unparsed_sha256']))
        plan=replace(self.plan,context_digest=contract['context_digest'])
        visible=render(validate(plan,state),state).text if self.case!='unparsed' else '我确定所有问题都已解决。'
        if self.behavior=='strengthening': visible='模块甲肯定是故障的唯一原因。'
        if self.behavior=='closure': visible='只剩 A/B，全部其他可能已经排除。'
        if self.behavior=='plan_strengthening':
            plan=replace(plan,claims=(replace(plan.claims[0],strength=Strength(Epistemic.CERTAIN)),))
        if self.behavior=='qualify':
            plan=replace(plan,claims=(replace(plan.claims[0],modality=Modality.ASSERTED,unresolved_dependencies=()),))
        value={'kind':'PROPOSED_SEMANTIC_PLAN','plan':asdict(plan) if self.case!='unparsed' else None,'visible_text':visible}
        if self.behavior=='forged': value.update(certificate_valid=True,closure_complete=True)
        return 200,runner.canonical({'model':request['model'],'responses_api_status':'completed',
            'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120},
            'choices':[{'finish_reason':'stop','message':{'content':canonical(value)}}]})

    def worker(self,n=1):
        lease=self.root/'ACTIVE_RUN.json'
        if not lease.exists(): runner.write_new(lease,{'run_id':self.name,'pid':os.getppid(),'at_utc':runner.now()})
        with patch.object(runner,'authored_transport',self.transport):
            return runner.worker(self.name,'segment_000',self.name,max_turns=n)

    def store(self): return TranscriptStore(self.root/'runtime')

    def rows(self):
        with runner.readonly_db(self.root) as db:
            return runner.validate_rows(db,self.root,self.manifest,self.scope,self.prep)[0]

    def close(self):
        for root,base in ((self.root,runner.EVIDENCE),(self.work,ROOT/'work/formal_acceptance_tests')):
            resolved=root.resolve()
            assert resolved.parent==base.resolve() and resolved.name.startswith('G6_V2_integration_mock_' if root==self.root else 'integration_mock_')
            if resolved.exists(): shutil.rmtree(resolved)

class FormalIntegrationTests(unittest.TestCase):
    def setUp(self): self.fixtures=[]
    def tearDown(self):
        for f in self.fixtures: f.close()
    def fixture(self,case='possible'):
        f=FormalMock(case); self.fixtures.append(f); f.prepare(); return f
    def output(self,case='possible',behavior='valid',n=1):
        f=self.fixture(case); f.behavior=behavior
        result=f.worker(n); self.assertEqual(result['status'],'PAUSED_KNOWN_PREFIX',result)
        return f,f.rows()

    def test_formal_revision_config_binding(self):
        f=self.fixture(); m=f.manifest; b=f.scope['semantic_acceptance_binding']
        self.assertTrue(m['formal_validation']); self.assertEqual(m['semantic_acceptance_binding'],b)
        self.assertEqual(m['semantic_acceptance_mode'],'TRUSTED')
        self.assertEqual((m['expected_turn_count'],m['expected_criteria_count']),(44,176))
        self.assertEqual(m['capture_mode'],runner.OFFLINE)
        self.assertEqual(m['provider_config_identity'],provider_identity(f.scope))
        self.assertEqual(m['dataset_identity']['sha256'],runner.sha(runner.GOAL/'external_failure_v1/CASES.json'))
        self.assertEqual(m['rubric_identity']['sha256'],runner.sha(runner.GOAL/'external_failure_v1/PRIVATE_RUBRIC.json'))

    def test_trusted_session_creation_and_adapter_injection(self):
        f=self.fixture(); store=f.store()
        try:
            for entry in f.prep['sessions'].values():
                h=store.resume(f.scope['principal_id'],entry['session_id']); chat=open_chat(store,h,f.scope)
                self.assertEqual(chat.acceptance_mode,session_mode(store.db,h.session_id)); self.assertEqual(chat.acceptance_mode,'TRUSTED')
                self.assertIsInstance(chat.acceptance.admit,TrustedAdmissionAdapter)
        finally: store.close()

    def test_policy_and_source_identity_persisted_in_session_and_turn(self):
        f,rows=self.output(); row=rows[0]
        with runner.readonly_db(f.root) as db:
            b=session_binding(db,row['session_id']); record=load_record(db,row['turn_id'])
        self.assertEqual(b,record['acceptance_identity']); self.assertEqual(b['acceptance_policy_version'],VERSION)
        self.assertEqual(b['acceptance_source_freeze'],f.config['acceptance_source_freeze'])

    def test_semantic_plan_contract_reaches_provider_request(self):
        f,rows=self.output(); request=f.calls[0]
        msg=next(m['content'] for m in request['input'] if m['content'].startswith('Host semantic proposal'))
        c=json.loads(msg.split('\n',1)[1]); self.assertEqual(c['response_kind'],'PROPOSED_SEMANTIC_PLAN')
        self.assertEqual(c['host_only_authority'],'AUTHORIZED_CLAIMS')
        self.assertEqual(c['context_digest'],rows[0]['accepted_output']['trusted_semantic_state'] and
            rows[0]['accepted_output']['source_runtime_identity']['trusted_context_digest'])
        self.assertFalse(any('PRIVATE_RUBRIC' in m['content'] for m in request['input']))

    def test_valid_output_allows_and_persists_raw_separately(self):
        f,rows=self.output(); row=rows[0]; record=row['accepted_output']
        self.assertEqual(record['acceptance_disposition'],'ALLOW'); self.assertTrue(record['accepted_semantic_plan'])
        self.assertNotEqual(row['raw_assistant_text'],row['assistant_text'])
        with runner.readonly_db(f.root) as db:
            raw=db.execute('SELECT raw_provider_response,raw_assistant_text FROM semantic_raw_outputs').fetchone()
        self.assertEqual(json.loads(raw[0])['choices'][0]['message']['content'],row['raw_assistant_text'])
        self.assertEqual(raw[1],row['raw_assistant_text'])

    def test_illegal_visible_strengthening_downgraded(self):
        f,rows=self.output(behavior='strengthening'); row=rows[0]; r=row['accepted_output']
        self.assertEqual(r['acceptance_disposition'],'DOWNGRADE'); self.assertIn('肯定',row['raw_assistant_text'])
        self.assertNotIn('肯定',row['assistant_text']); self.assertIn('可能',row['assistant_text'])
        self.assertTrue(r['acceptance_audit']['raw_provider_violation']); self.assertFalse(r['acceptance_audit']['guard_escape'])

    def test_illegal_plan_strengthening_host_downgrades(self):
        f,rows=self.output(behavior='plan_strengthening'); r=rows[0]['accepted_output']
        self.assertEqual(r['acceptance_disposition'],'DOWNGRADE')
        self.assertEqual(r['accepted_semantic_plan'][0]['strength']['epistemic'],Epistemic.POSSIBLE)

    def test_qualify_action_preserves_conditions(self):
        f,rows=self.output('conditional','qualify'); r=rows[0]['accepted_output']
        self.assertEqual(r['acceptance_disposition'],'QUALIFY'); self.assertIn('如果',r['accepted_assistant_text'])

    def test_illegal_closure_with_unresolved_remainder(self):
        f,rows=self.output('unknown_remainder','closure'); r=rows[0]['accepted_output']
        self.assertTrue(r['trusted_semantic_state']['universes'][0]['unresolved_remainder'])
        self.assertFalse(any(c['closure_certificate'] for c in r['certificates']))
        self.assertNotIn('只剩',r['accepted_assistant_text']); self.assertNotIn('完整候选',r['accepted_assistant_text'])
        self.assertFalse(r['acceptance_audit']['guard_escape'])

    def test_forged_model_certificates_are_rejected(self):
        f,rows=self.output(behavior='forged'); r=rows[0]['accepted_output']
        self.assertEqual(r['acceptance_disposition'],'BLOCK'); self.assertFalse(r['certificate_refs'])
        self.assertEqual(r['validation_result']['reason'],'PROPOSAL_ENVELOPE_FIELDS')

    def test_unparsed_has_no_authority_and_readable_low_permission_answer(self):
        f,rows=self.output('unparsed'); r=rows[0]['accepted_output']
        self.assertEqual(r['acceptance_audit']['semantic_admission_status'],'UNPARSED')
        self.assertFalse(r['accepted_semantic_plan']); self.assertFalse(r['certificate_refs'])
        self.assertEqual(r['acceptance_disposition'],'BLOCK'); self.assertIn('补充明确的条件或来源',r['accepted_assistant_text'])

    def test_display_consumer(self):
        f,rows=self.output(behavior='strengthening'); row=rows[0]
        slot=f.scope['slots'][0]['id']
        self.assertEqual((f.root/'displays'/f'{slot}.txt').read_text(encoding='utf-8'),row['assistant_text']+'\n')

    def test_history_consumer(self):
        f,rows=self.output(behavior='strengthening'); store=f.store()
        try:
            h=store.resume(f.scope['principal_id'],rows[0]['session_id'])
            row=store.conversation_recent(h,1,purpose='history')[0]
            self.assertEqual(row['assistant_text'],rows[0]['accepted_assistant_text'])
            self.assertEqual(row['raw_assistant_text'],rows[0]['raw_assistant_text'])
        finally: store.close()

    def test_next_turn_never_reintroduces_strengthening(self):
        f,rows=self.output(behavior='strengthening',n=2)
        with runner.readonly_db(f.root) as db:
            context=json.loads(db.execute('SELECT context_json FROM provider_calls WHERE turn_id=?',(rows[1]['turn_id'],)).fetchone()[0])
        self.assertEqual(context['prompt_history_projection'][0]['assistant'],rows[0]['assistant_text'])
        self.assertNotIn('模块甲肯定是故障的唯一原因',canonical(context['messages']))
        self.assertIn(rows[0]['assistant_text'],canonical(context['messages']))

    def test_memory_observation_and_event_candidate_consume_accepted(self):
        f,rows=self.output(behavior='strengthening'); tid=rows[0]['turn_id']
        with runner.readonly_db(f.root) as db:
            events=[json.loads(r[0]) for r in db.execute('SELECT event_json FROM runtime_events')]
            event=next(e for e in events if e['payload'].get('turn_id')==tid)
            candidates=[json.loads(r[0]) for r in db.execute('SELECT payload_json FROM event_candidates')]
            candidate=next(c for c in candidates if c.get('turn_id')==tid)
        for payload in (event['payload'],candidate):
            self.assertEqual(payload['assistant_text'],rows[0]['assistant_text'])
            self.assertEqual(payload['output_provenance'],'HOST_ACCEPTED_OUTPUT')
            self.assertNotIn('肯定',payload['assistant_text'])

    def test_evaluator_provenance_preserves_provider_error(self):
        f,rows=self.output(behavior='strengthening'); e=rows[0]['evaluation_provenance']
        self.assertEqual(e['product_semantic_target'],'accepted_assistant_text')
        self.assertEqual(e['raw_text'],rows[0]['raw_assistant_text']); self.assertEqual(e['accepted_text'],rows[0]['assistant_text'])
        self.assertTrue(e['raw_provider_violation']); self.assertTrue(e['guard_containment']); self.assertFalse(e['guard_escape'])
        self.assertEqual(e['guard_action'],'DOWNGRADE')
        capture=runner.read(runner.capture_snapshot(f.root)); self.assertEqual(capture['turns'][0]['evaluation_provenance'],e)
        self.assertFalse(capture['eligible_for_target_evaluation'])

    def test_candidate_input_uses_formal_accepted_record(self):
        import candidate_day_v2 as candidate
        f,rows=self.output(behavior='strengthening')
        selected=next(r for r in candidate._journal_rows(f.root/'runtime/runtime.sqlite3') if r['turn_id']==rows[0]['turn_id'])
        candidate.verify_raw(selected); self.assertEqual(selected['assistant_text'],rows[0]['assistant_text'])
        self.assertEqual(raw_text_for_audit(selected),rows[0]['raw_assistant_text'])

    def test_blind_input_uses_formal_accepted_projection(self):
        import blind_review_v2 as blind
        f,rows=self.output(behavior='strengthening')
        with runner.readonly_db(f.root) as db:
            raw=runner.call_rows(db,f.scope)[0]
            selected=blind.g.accepted_projection(db,raw,'blind')
        self.assertEqual(selected['assistant_text'],rows[0]['assistant_text'])
        self.assertNotIn('肯定',selected['assistant_text'])

    def test_audit_review_retains_both_texts(self):
        f,rows=self.output(behavior='strengthening'); store=f.store()
        try:
            h=store.resume(f.scope['principal_id'],rows[0]['session_id']); chat=open_chat(store,h,f.scope)
            row=chat.inspect_last(); self.assertEqual(row['raw_assistant_text'],rows[0]['raw_assistant_text'])
            self.assertEqual(row['assistant_text'],rows[0]['assistant_text'])
            self.assertEqual(store.conversation_turn(h,row['turn_id'],purpose='review')['assistant_text'],rows[0]['assistant_text'])
        finally: store.close()

    def test_restart_recovers_raw_accepted_identity_validation_without_call(self):
        f,rows=self.output(behavior='strengthening'); store=f.store()
        try:
            h=store.resume(f.scope['principal_id'],rows[0]['session_id']); chat=open_chat(store,h,f.scope)
            slot=f.scope['slots'][0]
            with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):
                result=chat.send_text(slot['user_text'],f.scope['batch_id']+':'+slot['id'],slot_id=slot['id'])
            self.assertEqual(result['status'],'ALREADY_DISPLAYED'); self.assertEqual(result['text'],rows[0]['assistant_text'])
            self.assertEqual(load_record(store.db,rows[0]['turn_id']),rows[0]['accepted_output'])
        finally: store.close()
        self.assertEqual(len(f.calls),1)

    def test_formal_mock_driver_end_to_end_and_frozen_inputs_preserved(self):
        f,rows=self.output(n=2)
        self.assertEqual(len(rows),2); self.assertTrue(all(r['output_provenance']=='HOST_ACCEPTED_OUTPUT' for r in rows))
        self.assertTrue(all(r['capture_origin']=='AUTHORED_PROVIDER_TEST_FIXTURE' for r in rows))
        self.assertEqual(runner.status(f.name)['generated_target_captures'],0)
        self.assertEqual(f.scope['slots'],runner.load_suite('external44','deepseek-v4-pro','deepseek-flash')['slots'])

    def test_formal_offline_missing_config_fails_before_allocation(self):
        name='integration_mock_'+uuid.uuid4().hex
        with self.assertRaisesRegex(BindingError,'FORMAL_ACCEPTANCE_CONFIG_REQUIRED'):
            runner.prepare(name,suite='external44',offline=True,formal_validation=True)
        self.assertFalse(runner.revision_root(name).exists())

    def test_paid_external_entry_missing_config_fails_before_pricing_or_allocation(self):
        name='integration_mock_'+uuid.uuid4().hex
        with patch.object(runner,'checked_pricing',side_effect=AssertionError('MUST_NOT_REACH_PRICING')):
            with self.assertRaisesRegex(BindingError,'FORMAL_ACCEPTANCE_CONFIG_REQUIRED'):
                runner.prepare(name,suite='external44')
        self.assertFalse(runner.revision_root(name).exists())

    def test_zero_call_formal_preflight_uses_actual_driver(self):
        from formal_binding_preflight import preflight
        f=FormalMock(); self.fixtures.append(f)
        result=preflight(f.config_path,f.transport_policy,f.route_policy)
        try:
            self.assertEqual(result['status'],'TRUSTED_ACCEPTANCE_EXTERNAL44_BINDING_READY')
            self.assertEqual(result['provider_call_invocations'],0); self.assertEqual(result['provider_call_rows'],0)
            self.assertEqual(len(result['request_checks']),7); self.assertFalse(result['paid_revision_created'])
        finally:
            root=(ROOT/result['mock_revision_path']).resolve()
            self.assertEqual(root.parent,runner.EVIDENCE.resolve()); self.assertTrue(root.name.startswith('G6_V2_binding_preflight_'))
            shutil.rmtree(root)

    def test_formal_off_configuration_refused(self):
        f=FormalMock(config=lambda c:dict(c,semantic_acceptance_mode='OFF')); self.fixtures.append(f)
        with self.assertRaisesRegex(BindingError,'MODE_MISMATCH'): f.prepare()
        self.assertFalse(f.root.exists())

    def test_missing_adapter_refuses_direct_chat_construction(self):
        from chat import ChatService
        f=self.fixture(); store=f.store()
        try:
            sid=next(iter(f.prep['sessions'].values()))['session_id']; h=store.resume(f.scope['principal_id'],sid)
            with self.assertRaisesRegex(BindingError,'ADAPTER_REQUIRED'):
                ChatService(store,h,f.scope,semantic_acceptance_mode='TRUSTED',
                    semantic_acceptance_binding=f.scope['semantic_acceptance_binding'],semantic_acceptance=SemanticAcceptance())
        finally: store.close()

    def test_existing_formal_session_cannot_resume_without_binding(self):
        from chat import ChatService
        f=self.fixture(); store=f.store()
        try:
            sid=next(iter(f.prep['sessions'].values()))['session_id']; h=store.resume(f.scope['principal_id'],sid)
            stripped={k:v for k,v in f.scope.items() if k not in {'formal_validation','semantic_acceptance_binding'}}
            with self.assertRaisesRegex(BindingError,'EXPLICIT_FORMAL_ACCEPTANCE_REQUIRED'): ChatService(store,h,stripped)
        finally: store.close()

    def test_missing_persistence_refuses_worker_before_call(self):
        f=self.fixture(); store=f.store()
        store.db.execute('DROP TABLE accepted_outputs'); store.close()
        result=f.worker(); self.assertEqual(result['status'],'STOPPED_RECONCILE_REQUIRED')
        self.assertEqual(result['failure_layer'],'PERSISTENCE'); self.assertFalse(f.calls)

    def test_binding_fields_fail_closed(self):
        f=self.fixture(); original=f.scope['semantic_acceptance_binding']
        for key in original:
            bad=copy.deepcopy(original); del bad[key]
            with self.subTest(key=key),self.assertRaises(BindingError): validate_binding(bad,f.scope)
        for key in ('acceptance_policy_version','acceptance_source_freeze','evaluator_contract_version',
                    'persistence_version','admission_adapter_version','request_contract_version','provider_config_identity'):
            bad=copy.deepcopy(original); bad[key]='INVALID'
            with self.subTest(key=key),self.assertRaises(BindingError): validate_binding(bad,f.scope)
        bad=copy.deepcopy(original); bad['consumers'].remove('history')
        with self.assertRaisesRegex(BindingError,'CONSUMERS_REQUIRED'): validate_binding(bad,f.scope)

    def test_session_policy_and_binding_are_immutable(self):
        f=self.fixture(); store=f.store()
        try:
            for sql in ('DELETE FROM semantic_session_binding',"UPDATE semantic_session_policy SET mode='OFF'"):
                with self.assertRaises(sqlite3.IntegrityError): store.db.execute(sql)
        finally: store.close()

    def test_guard_escape_detected(self):
        f,rows=self.output(behavior='strengthening')
        from formal_acceptance import evaluator_provenance
        bad=copy.deepcopy(rows[0]); bad['assistant_text']=bad['raw_assistant_text']
        with self.assertRaisesRegex(BindingError,'GUARD_ESCAPE_DETECTED'):
            evaluator_provenance(bad,f.scope['semantic_acceptance_binding'])

    def test_missing_evaluator_provenance_rejected(self):
        f,rows=self.output()
        from formal_acceptance import evaluator_provenance
        bad=copy.deepcopy(rows[0]); del bad['accepted_output']
        with self.assertRaisesRegex(BindingError,'ACCEPTED_EVALUATOR_BINDING_REQUIRED'):
            evaluator_provenance(bad,f.scope['semantic_acceptance_binding'])

    def test_missing_accepted_record_never_falls_back_to_raw(self):
        f,rows=self.output(); store=f.store()
        try:
            store.db.execute('DROP TRIGGER accepted_no_delete')
            store.db.execute('DELETE FROM accepted_outputs')
            h=store.resume(f.scope['principal_id'],rows[0]['session_id'])
            for purpose in ('display','history','next_turn_context','memory','evaluation','candidate','blind','audit','review'):
                with self.subTest(purpose=purpose),self.assertRaisesRegex(SemanticError,'ACCEPTED_OUTPUT_REQUIRED'):
                    store.conversation_turn(h,rows[0]['turn_id'],purpose=purpose)
        finally: store.close()

    def test_formal_reopen_does_not_recreate_missing_persistence(self):
        f=self.fixture(); store=f.store()
        try:
            sid=next(iter(f.prep['sessions'].values()))['session_id']; h=store.resume(f.scope['principal_id'],sid)
            store.db.execute('DROP TABLE accepted_outputs')
            with self.assertRaisesRegex(BindingError,'ACCEPTED_PERSISTENCE_REQUIRED'): open_chat(store,h,f.scope)
            self.assertIsNone(store.db.execute("SELECT name FROM sqlite_master WHERE name='accepted_outputs'").fetchone())
        finally: store.close()

    def test_changed_catalog_fails_before_any_provider_call(self):
        f=self.fixture(); f.catalog_path.write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(BindingError,'SOURCE_IDENTITY_CHANGED'): f.worker()
        self.assertFalse(f.calls)

    def test_mock_freeze_cannot_authorize_paid_preparation(self):
        from formal_acceptance import build_binding
        f=self.fixture()
        with self.assertRaisesRegex(BindingError,'FORMAL_FROZEN_SOURCE_REQUIRED'):
            build_binding(f.scope,runner.load_suite('external44','deepseek-v4-pro','deepseek-flash'),f.config_path,
                          rubric_path=runner.GOAL/'external_failure_v1/PRIVATE_RUBRIC.json',offline=False)

    def test_validator_failure_has_own_layer(self):
        f=self.fixture()
        with patch('accepted_output.validate_with_fallback',side_effect=RuntimeError('INJECTED')): result=f.worker()
        self.assertEqual(result['failure_layer'],'VALIDATOR'); self.assertFalse((f.root/'displays').exists())

    def test_certificate_failure_has_own_layer(self):
        from semantic_validator import validate_with_fallback
        f=self.fixture()
        def invalid(plan,state): return replace(validate_with_fallback(plan,state),_seal=object())
        with patch('accepted_output.validate_with_fallback',side_effect=invalid): result=f.worker()
        self.assertEqual(result['failure_layer'],'CERTIFICATE'); self.assertFalse((f.root/'displays').exists())

    def test_consumer_failure_has_own_layer(self):
        f=self.fixture()
        with patch('formal_acceptance.evaluator_provenance',side_effect=BindingError('CONSUMER','INJECTED')): result=f.worker()
        self.assertEqual(result['failure_layer'],'CONSUMER')

    def test_evaluation_failure_has_own_layer(self):
        f=self.fixture()
        with patch('formal_acceptance.evaluator_provenance',side_effect=BindingError('EVALUATION','INJECTED')): result=f.worker()
        self.assertEqual(result['failure_layer'],'EVALUATION')

    def test_transport_unknown_retains_stop_layer_and_no_retry(self):
        f=self.fixture(); count=[]
        def fail(payload,credential): count.append(1); raise ConnectionError('SYNTHETIC_CONNECTION_FAILURE')
        f.transport=fail; result=f.worker()
        self.assertEqual(result['failure_layer'],'TRANSPORT'); self.assertEqual(len(count),1)
        self.assertEqual(result['status'],'STOPPED_RECONCILE_REQUIRED')

    def test_provider_rejection_has_own_layer(self):
        f=self.fixture(); count=[]
        def reject(payload,credential): count.append(1); return 400,b'{"error":{"type":"invalid_request"}}'
        f.transport=reject; result=f.worker()
        self.assertEqual(result['failure_layer'],'PROVIDER'); self.assertEqual(len(count),1)

    def test_renderer_failure_classified_and_no_raw_display(self):
        f=self.fixture()
        with patch('accepted_output.render',side_effect=SemanticError('INJECTED_RENDERER_FAILURE')):
            result=f.worker()
        self.assertEqual(result['failure_layer'],'RENDERER'); self.assertEqual(len(f.calls),1)
        self.assertFalse((f.root/'displays').exists())
        with runner.readonly_db(f.root) as db:
            self.assertIsNotNone(db.execute('SELECT raw_response FROM provider_calls').fetchone()[0])
            self.assertEqual(db.execute('SELECT count(*) FROM accepted_outputs').fetchone()[0],0)

    def test_persistence_failure_classified_and_no_raw_display(self):
        f=self.fixture()
        with patch('accepted_output.persist',side_effect=sqlite3.OperationalError('INJECTED')): result=f.worker()
        self.assertEqual(result['failure_layer'],'PERSISTENCE'); self.assertFalse((f.root/'displays').exists())

    def test_ordinary_unbound_sessions_remain_off(self):
        from chat import ChatService
        f=self.fixture(); store=f.store()
        try:
            h=store.open_session('ordinary','ordinary'); stripped={k:v for k,v in f.scope.items()
                if k not in {'formal_validation','semantic_acceptance_binding'}}
            stripped['batch_id']='ordinary_'+uuid.uuid4().hex; stripped['principal_id']='ordinary'
            chat=ChatService(store,h,stripped); self.assertEqual(chat.acceptance_mode,'OFF')
            self.assertIsNone(session_binding(store.db,h.session_id))
        finally: store.close()

if __name__=='__main__': unittest.main(verbosity=2)
