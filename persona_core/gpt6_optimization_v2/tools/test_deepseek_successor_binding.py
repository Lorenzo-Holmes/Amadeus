"""Neutral offline contracts; no target sampling, credential or rubric answers."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'persona_core/operational_runtime_v1'),str(Path(__file__).parent),str(ROOT/'persona_core/operational_build_v1/tools')]
import copy,hashlib,json,socket,unittest,uuid
from contextlib import ExitStack
from unittest.mock import patch
import provider as p
import provider_deepseek_formal as ds
import provider_contract as pc
import provider_adapters as adapters
import provider_transport as pt
import evaluation_runner as runner
from transcript_store import TranscriptStore,create_sandbox
from operations import open_chat

TEXT='The observation supports a conditional explanation; it does not prove completion.'
KEY='OFFLINE_NEUTRAL_SENTINEL'

def usage(i=100,o=10,c=20,r=4):
    return {'input_tokens':i,'output_tokens':o,'total_tokens':i+o,
        'input_tokens_details':{'cached_tokens':c},'output_tokens_details':{'reasoning_tokens':r}}

def response(model=ds.MODEL,status='completed',text=TEXT,stats=None):
    result={'id':'resp_neutral','model':model,'status':status,
        'output':[{'type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':text}]}],
        'usage':usage() if stats is None else stats}
    if status=='failed':result['error']={'code':'authored_failure','message':'Neutral failure.'}
    if status=='incomplete':result['incomplete_details']={'reason':'max_output_tokens'}
    return result

def wire(value=None):
    value=value or response()
    events=[{'type':'response.created','response':{'id':value['id'],'model':value['model'],'status':'in_progress'}},
        {'type':'response.output_text.delta','delta':value['output'][-1]['content'][0]['text']},
        {'type':'response.'+value['status'],'response':value}]
    return b''.join(b'event: '+e['type'].encode()+b'\ndata: '+pc.canonical(dict(e,sequence_number=i))+b'\n\n' for i,e in enumerate(events))

def offline_config(base):
    base.mkdir(parents=True,exist_ok=False)
    files=runner.source_bindings();p1=runner.GOAL/'architecture_scope_reconciliation_20260920_01/CONTRACT_FREEZE_MANIFEST.json'
    files.update(runner.read(p1)['files']);files[runner.relative(p1)]=runner.sha(p1)
    source=base/'SOURCE.json';runner.write_new(source,{'freeze_id':base.name,'status':'OFFLINE_TEST_ONLY','files':files})
    config=runner.read(runner.GOAL/'bounded_boundary_p2_p3_20260920_01/FORMAL_ACCEPTANCE_CONFIG.json')
    config.update(acceptance_source_freeze=base.name,acceptance_source_manifest=ds.reference(source))
    cfg=base/'acceptance.json';runner.write_new(cfg,config)
    route=base/'route.json';runner.write_new(route,ds.route())
    transport=base/'transport.json';runner.write_new(transport,ds.configuration()['transport_policy'])
    folder=ROOT/ds.DIRECTORY;price=folder/'OFFICIAL_PRICING_EVIDENCE.json';auth=folder/'EXECUTION_AUTHORIZATION.json'
    suite=runner.load_suite('external44',ds.MODEL,ds.MODEL,allow_single_model=True)
    scope=ds.build_scope(base.name,suite,runner.read(price),runner.read(transport),runner.read(route),
        authorization_file=auth,pricing_file=price,acceptance_config_file=cfg)
    scope['semantic_acceptance_binding']=runner.build_acceptance_binding(scope,suite,cfg,
        rubric_path=runner.GOAL/'external_failure_v1/PRIVATE_RUBRIC.json',offline=True)
    return scope,cfg,transport,route,auth,price

class DeepSeekSuccessorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=ROOT/'work/deepseek_successor/tests'/('run_'+uuid.uuid4().hex)
        cls.scope,cls.cfg,cls.transport,cls.route,cls.auth,cls.price=offline_config(cls.base)

    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for name in ('connect','connect_ex'):
            self.stack.enter_context(patch.object(socket.socket,name,side_effect=AssertionError('OFFLINE_NETWORK_FORBIDDEN')))
        self.keys=self.stack.enter_context(patch.object(ds.DeepSeekFormalAdapter,'credential',side_effect=AssertionError('OFFLINE_CREDENTIAL_FORBIDDEN')))
        self.scope=copy.deepcopy(type(self).scope);self.adapter=ds.DeepSeekFormalAdapter();self.sent=[]

    def payload(self,messages=None):
        return pc.canonical(self.adapter.serialize(self.scope,ds.MODEL,messages or [{'role':'user','content':'Neutral 雪.'}]))

    def send(self,value=None,fault=None,status=200,http=None):
        base=self.base/('runtime_'+uuid.uuid4().hex);create_sandbox(base)
        store=TranscriptStore(base);self.addCleanup(store.close);slot=self.scope['slots'][0]
        h=store.open_session(self.scope['principal_id'],slot['entity_label'],'PRODUCT_RUNTIME')
        chat=open_chat(store,h,self.scope);shown=[]
        def transport(payload,key):
            self.sent.append(payload)
            if fault:raise fault
            w=pc.canonical(http) if http else wire(value)
            return pt.TransportResult(status,self.adapter.decode_http_result(self.scope,w,status),w)
        result=chat.send_text(slot['user_text'],'neutral-once',slot_id=slot['id'],display=shown.append,
            transport=transport,credential_reader=lambda:KEY)
        return store,h,chat,slot,result,shown,transport

    def test_scope_valid(self):p.scope_check(self.scope)
    def test_registry_preserved(self):
        self.assertEqual(set(adapters.registry().adapters),{'deepseek','local_fixture','openrouter'})
        self.assertIsInstance(adapters.select(self.scope),ds.DeepSeekFormalAdapter)
    def test_old_r16_not_candidate(self):
        bad=copy.deepcopy(self.scope);bad['slots'][0]['model']='deepseek-v4-pro'
        with self.assertRaises(ValueError):p.scope_check(bad)
    def test_same_model_requires_opt_in(self):
        with self.assertRaises(ValueError):runner.load_suite('external44',ds.MODEL,ds.MODEL)
    def test_original_roles_preserved(self):
        self.assertEqual([s['id'] for s in self.scope['slots'] if s['model_role']=='SECONDARY'],['N09_S1','N09_S2'])
        self.assertEqual(len(self.scope['slots']),44)
    def test_wrong_returned_model(self):
        for m in ['deepseek-v4-pro','deepseek-v4-flash','deepseek-flash-20260910',None]:
            with self.subTest(model=m),self.assertRaises(ValueError):self.adapter.validate_model(ds.MODEL,m)
    def test_route_and_fallback_rejected(self):
        for key,value in [('endpoint','https://openrouter.ai/api/v1/responses'),('network_route_policy',dict(ds.route(),mode='SYSTEM_PROXY'))]:
            bad=copy.deepcopy(self.scope);bad[key]=value
            with self.assertRaises(ValueError):p.scope_check(bad)
    def test_scope_drift_rejected(self):
        for key,value in [('source_binding',{}),('max_input_bytes',32768),('max_output_tokens',16384),('request_timeout_seconds',120),('automatic_paid_retries',1),('tools_allowed',True),('criteria_count',175)]:
            bad=copy.deepcopy(self.scope);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):p.scope_check(bad)
    def test_schedule_drift_rejected(self):
        for key,value in [('user_text','Changed'),('model_role','SECONDARY'),('host_action_before','RESTART_SAME_SESSION')]:
            bad=copy.deepcopy(self.scope);bad['slots'][0][key]=value
            with self.assertRaises(ValueError):p.scope_check(bad)
    def test_configuration_ref_drift(self):
        self.scope['identity_references']['configuration']['sha256']='0'*64
        with self.assertRaises(ValueError):p.scope_check(self.scope)
    def test_closed_serializer(self):
        self.assertEqual(set(json.loads(self.payload())),{'model','input','stream','reasoning','max_output_tokens','top_p'})
        self.keys.assert_not_called()
    def test_unsupported_fields_rejected(self):
        for k in ['tools','store','truncation','previous_response_id','seed','temperature','metadata']:
            value=json.loads(self.payload());value[k]=None
            with self.assertRaises(ValueError):ds.input_guard_receipt(self.scope,pc.canonical(value),self.scope['slots'][0]['id'])
    def test_byte_boundary(self):
        overhead=len(pc.canonical([{'role':'user','content':''}]))
        self.payload([{'role':'user','content':'a'*(24576-overhead)}])
        with self.assertRaises(ValueError):self.payload([{'role':'user','content':'a'*(24577-overhead)}])
    def test_unicode_no_normalization(self):
        msgs=[{'role':'system','content':'中\n雪🙂\te\u0301'},{'role':'assistant','content':'条件推断'},{'role':'user','content':'x'}]
        self.assertEqual(json.loads(self.payload(msgs))['input'],msgs)
    def test_invalid_role_rejected(self):
        with self.assertRaises(ValueError):self.payload([{'role':'developer','content':'x'}])
    def test_multimodal_rejected(self):
        with self.assertRaises(ValueError):self.payload([{'role':'user','content':[]}])
    def test_duplicate_json_rejected(self):
        with self.assertRaises(ValueError):ds.strict_json('{"a":1,"a":2}')
    def test_host_receipt_not_token_proof(self):
        receipt=ds.input_guard_receipt(self.scope,self.payload(),self.scope['slots'][0]['id'])
        self.assertIsNone(receipt['input_tokens_pre_request']);self.assertFalse(receipt['exact_token_proof'])
    def test_no_count_or_openai_dependency(self):
        import provider_openai as oa
        with patch.object(oa,'count_input_tokens',side_effect=AssertionError('NO_COUNT')) as count:
            self.send();count.assert_not_called()
    def test_full_context_reservation(self):
        self.assertEqual(ds.reserve(self.scope,ds.MODEL,1),2462144)
        self.assertEqual(ds.reserve(self.scope,ds.MODEL,24576)*44,108334336)
    def test_native_usage_preserved(self):
        body=json.loads(self.adapter.decode(self.scope,wire()))
        self.assertEqual(body['native_usage'],usage());self.assertEqual(body['native_response'],response())
    def test_native_accounting(self):
        a=ds.accounting(usage(),self.scope,ds.MODEL)
        self.assertEqual(a['estimate_micro_cny'],241);self.assertEqual(a['reasoning_tokens'],4);self.assertFalse(a['billing_certified'])
    def test_invalid_usage_rejected(self):
        for v in [None,{},dict(usage(),input_tokens=True),dict(usage(),total_tokens=1),dict(usage(),input_tokens_details={})]:
            self.assertIsNotNone(ds.accounting(v,self.scope,ds.MODEL)['rejection'])
    def test_usage_envelope_exceeded(self):
        self.assertEqual(ds.accounting(usage(i=1100001),self.scope,ds.MODEL)['rejection'],'DEEPSEEK_USAGE_ENVELOPE_EXCEEDED')
    def test_output_budget_includes_reasoning(self):
        self.assertIsNotNone(ds.accounting(usage(o=32769),self.scope,ds.MODEL)['rejection'])
    def test_stream_truncation_unknown(self):
        for w in [wire()[:-5],wire()+wire()]:
            with self.assertRaises(ValueError):self.adapter.decode(self.scope,w)
    def test_stream_sequence_rejected(self):
        with self.assertRaises(ValueError):self.adapter.decode(self.scope,wire().replace(b'"sequence_number":1',b'"sequence_number":0'))
    def test_wire_receipt_mismatch(self):
        with self.assertRaises(pt.TransportFault):adapters.verified_result(self.adapter,self.scope,pt.TransportResult(200,b'{}',wire()))
    def test_http_length_terminal_known(self):
        body=json.loads(self.adapter.decode_http_result(self.scope,pc.canonical({'error':{'code':'context_length_exceeded','message':'Input exceeds context.'}}),400))
        self.assertEqual(self.adapter.terminal(self.scope,body)[2],'TERMINAL_KNOWN_INPUT_LIMIT_REJECTION')
    def test_http_ambiguous_unknown(self):
        with self.assertRaises(ValueError):self.adapter.decode_http_result(self.scope,b'{}',500)
    def test_successful_display_and_receipt(self):
        store,h,chat,slot,result,shown,_=self.send()
        self.assertEqual(result['status'],'DISPLAYED');self.assertEqual(shown,[TEXT])
        row=store.db.execute('SELECT * FROM provider_calls').fetchone()
        receipt=json.loads(store.db.execute('SELECT contract_json FROM provider_call_contracts').fetchone()[0])
        self.assertEqual(receipt['native_usage'],usage());self.assertEqual(receipt['input_safety_receipt']['request_sha256'],row['request_sha256'])
        self.assertIsNone(store.db.execute("SELECT name FROM sqlite_master WHERE name='provider_input_counts'").fetchone())
        summary=p.ProviderJournal(store).summary(self.scope['batch_id'])
        self.assertEqual(summary['known_usage_count'],1);self.assertEqual(summary['provider_id'],'deepseek')
    def test_completed_scope9_row_reaches_full_evaluator_path(self):
        """Real mock-wire -> DB -> display -> evaluator -> review -> next-slot path."""
        root,store,manifest,prep,send=self.completed_harness()
        first,second=self.scope['slots'][:2]
        send(first)
        rows,batch=runner.validate_rows(store.db,root,manifest,self.scope,prep)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['http_status'],200)
        self.assertTrue(runner.completed(rows[0]))
        self.assertEqual(rows[0]['assistant_text'],TEXT)
        self.assertIn('evaluation_provenance',rows[0])
        self.assertEqual(batch['stopped'],0)
        self.assertEqual(store.db.execute('SELECT status FROM display_journal').fetchone()[0],'DISPLAY_ACK')
        with self.assertRaisesRegex(runner.RunnerError,'REVIEW_REQUIRED'):
            runner.require_successor_review_prefix(root,manifest,self.scope,prep)
        self.assertEqual(len(self.sent),1)
        self.write_synthetic_review(root,manifest,rows[0])
        runner.require_successor_review_prefix(root,manifest,self.scope,prep)
        send(second)
        rows,_=runner.validate_rows(store.db,root,manifest,self.scope,prep)
        self.assertEqual(len(rows),2)
        self.assertTrue(all(runner.completed(r) and r['http_status']==200 for r in rows))
        summary=p.ProviderJournal(store).summary(self.scope['batch_id'])
        self.assertEqual(summary['known_usage_count'],2)
        self.assertEqual(len(self.sent),2)
        self.keys.assert_not_called()

    def completed_harness(self):
        root=self.base/('completed_harness_'+uuid.uuid4().hex)
        create_sandbox(root/'runtime')
        store=TranscriptStore(root/'runtime');self.addCleanup(store.close)
        slot=self.scope['slots'][0]
        h=store.open_session(self.scope['principal_id'],slot['entity_label'],'PRODUCT_RUNTIME')
        chat=open_chat(store,h,self.scope)
        binding=self.scope['semantic_acceptance_binding']
        prep={'semantic_acceptance_binding':binding,'sessions':{slot['case_id']:{
            'session_id':h.session_id,'entity_id':h.entity_id,'mode':h.mode
        }}}
        manifest={'capture_mode':runner.OFFLINE,'formal_validation':True,
            'semantic_acceptance_binding':binding,'source_manifest_sha256':runner.sha(self.base/'SOURCE.json')}
        for key in ('semantic_acceptance_mode','acceptance_policy_version','acceptance_source_freeze',
                    'trusted_semantic_runtime_version','provider_config_identity',
                    'dataset_identity','rubric_identity'):
            manifest[key]=binding[key]
        def transport(payload,key):
            self.sent.append(payload)
            w=wire()
            return pt.TransportResult(200,self.adapter.decode_http_result(self.scope,w,200),w)
        def send(current):
            path=root/'displays'/(current['id']+'.txt')
            path.parent.mkdir(parents=True,exist_ok=True)
            result=chat.send_text(current['user_text'],'mock-'+current['id'],slot_id=current['id'],
                display=lambda text:path.write_bytes((text+'\n').encode('utf-8')),
                transport=transport,credential_reader=lambda:KEY)
            self.assertEqual(result['status'],'DISPLAYED')
        return root,store,manifest,prep,send

    def write_synthetic_review(self,root,manifest,row,*,unclear=False,major=0):
        routes=runner.read(ROOT/self.scope['identity_references']['criterion_routing']['path'])['criteria']
        applicable=[r for r in routes if r['turn_id']==row['slot_id']]
        checks=[{'criterion_id':r['criterion_id'],'gate_a':'PASS',
            'gate_b':'PASS' if r['route']=='BOTH' else 'NOT_APPLICABLE_BY_FROZEN_ROUTE',
            'evidence':'AUTHORED HARNESS ASSERTION ONLY; NOT TARGET MODEL QUALITY'} for r in applicable]
        if unclear:checks[0]['gate_a']='UNCLEAR'
        value={'slot_id':row['slot_id'],'raw_sha256':row['raw_sha256'],
            'displayed_sha256':hashlib.sha256(row['assistant_text'].encode('utf-8')).hexdigest(),
            'source_manifest_sha256':manifest['source_manifest_sha256'],
            'criteria':checks,'blocking_major':major,'critical':0}
        path=root/'reviews'/(row['slot_id']+'.json')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(pc.canonical(value))

    def test_completed_row_missing_http_projection_mutant_is_rejected(self):
        root,store,manifest,prep,send=self.completed_harness()
        send(self.scope['slots'][0])
        original=runner.call_rows
        def missing(db,scope):
            return [{k:v for k,v in r.items() if k!='http_status'} for r in original(db,scope)]
        with patch.object(runner,'call_rows',side_effect=missing):
            with self.assertRaisesRegex(KeyError,'http_status'):
                runner.validate_rows(store.db,root,manifest,self.scope,prep)
        self.assertEqual(len(self.sent),1)

    def test_completed_chain_unclear_major_and_unknown_never_authorize_next_slot(self):
        root,store,manifest,prep,send=self.completed_harness()
        send(self.scope['slots'][0])
        rows,_=runner.validate_rows(store.db,root,manifest,self.scope,prep)
        for unclear,major in ((True,0),(False,1)):
            self.write_synthetic_review(root,manifest,rows[0],unclear=unclear,major=major)
            with self.assertRaisesRegex(runner.RunnerError,'QUALITY_OR_INTEGRITY_STOP'):
                runner.require_successor_review_prefix(root,manifest,self.scope,prep)
        self.write_synthetic_review(root,manifest,rows[0])
        with store.transaction():
            store.db.execute("UPDATE provider_calls SET status='SUBMITTED_STATUS_UNKNOWN'")
        with self.assertRaisesRegex(runner.RunnerError,'STOPPED_OR_UNKNOWN'):
            runner.require_successor_review_prefix(root,manifest,self.scope,prep)
        self.assertEqual(len(self.sent),1)

    def test_completed_row_wire_tamper_stops_evaluator(self):
        root,store,manifest,prep,send=self.completed_harness()
        send(self.scope['slots'][0])
        with store.transaction():
            store.db.execute('UPDATE transport_wire_captures SET wire_bytes=?',(b'corrupted mock wire',))
        with self.assertRaisesRegex(runner.RunnerError,'WIRE_CHANGED'):
            runner.validate_rows(store.db,root,manifest,self.scope,prep)
        self.assertEqual(len(self.sent),1)
    def test_no_paid_retry_after_capture(self):
        store,h,chat,slot,result,shown,transport=self.send()
        chat.send_text(slot['user_text'],'neutral-once',slot_id=slot['id'],transport=transport,credential_reader=lambda:KEY)
        self.assertEqual(len(self.sent),1)
    def test_timeout_quarantine_no_retry(self):
        store,h,chat,slot,result,shown,transport=self.send(fault=pt.TransportFault('INACTIVITY_TIMEOUT',b'',200))
        self.assertEqual(result['status'],'SUBMITTED_STATUS_UNKNOWN')
        chat.send_text(slot['user_text'],'neutral-once',slot_id=slot['id'],transport=transport,credential_reader=lambda:KEY)
        self.assertEqual(len(self.sent),1);self.assertEqual(shown,[])
        self.assertEqual(store.db.execute('SELECT stopped FROM call_batches').fetchone()[0],1)
    def test_wrong_model_stops_batch(self):
        store,h,chat,slot,result,shown,_=self.send(response(model='deepseek-v4-pro'))
        self.assertNotEqual(result['status'],'DISPLAYED');self.assertEqual(shown,[])
        self.assertEqual(store.db.execute('SELECT stopped FROM call_batches').fetchone()[0],1)
    def test_incomplete_stops_batch(self):
        store,h,chat,slot,result,shown,_=self.send(response(status='incomplete'))
        self.assertNotEqual(result['status'],'DISPLAYED');self.assertEqual(shown,[])
    def test_length_rejection_stops_batch(self):
        store,h,chat,slot,result,shown,_=self.send(status=400,http={'error':{'code':'context_length_exceeded','message':'Too long'}})
        row=store.db.execute('SELECT * FROM provider_calls').fetchone()
        self.assertEqual(row['status'],'RESPONSE_REJECTED_TERMINAL_KNOWN')
        self.assertEqual(row['error_category'],'TERMINAL_KNOWN_INPUT_LIMIT_REJECTION');self.assertEqual(shown,[])
    def test_next_turn_requires_review(self):
        row={'slot_id':self.scope['slots'][0]['id'],'raw_sha256':'x','assistant_text':TEXT,'provider_status':'RESPONSE_CAPTURED','status':'COMPLETE'}
        with patch.object(runner,'validate_rows',return_value=([row],{'stopped':0})),patch.object(runner,'completed',return_value=True),patch.object(runner,'readonly_db'):
            with self.assertRaisesRegex(ValueError,'REVIEW_REQUIRED'):runner.require_successor_review_prefix(self.base,{'source_manifest_sha256':'x'},self.scope,{})
    def test_nonzero_retries_not_allowed(self):
        self.scope['automatic_paid_retries']=True
        with self.assertRaises(ValueError):p.scope_check(self.scope)
    def test_source_membership_bound(self):
        self.assertIn('provider_deepseek_formal.py',{p.name for p in runner.source_files()})
    def active_driver_fixture(self, mode):
        evidence=self.base/('active_driver_audit_'+uuid.uuid4().hex)
        root=evidence/'G6_V2_neutral';root.mkdir(parents=True)
        runner.write_new(root/'ACTIVE_RUN.json',{'pid':12345})
        runner.write_new(root/'MANIFEST.json',{'capture_mode':mode})
        runner.write_new(root/'MANIFEST_SEAL.json',{'sha256':runner.sha(root/'MANIFEST.json')})
        return evidence,root
    def test_sealed_offline_marker_with_reused_live_pid_is_not_paid(self):
        from formal_binding_preflight import active_paid_driver_count
        evidence,_=self.active_driver_fixture(runner.OFFLINE)
        with patch.object(runner,'process_alive',return_value=True):
            self.assertEqual(active_paid_driver_count(evidence),0)
    def test_live_target_driver_remains_blocking(self):
        from formal_binding_preflight import active_paid_driver_count
        evidence,_=self.active_driver_fixture(runner.TARGET)
        with patch.object(runner,'process_alive',return_value=True):
            self.assertEqual(active_paid_driver_count(evidence),1)
    def test_unsealed_or_unknown_live_driver_identity_remains_blocking(self):
        from formal_binding_preflight import active_paid_driver_count
        for mode in (runner.OFFLINE,'UNKNOWN_MODE'):
            with self.subTest(mode=mode):
                evidence,root=self.active_driver_fixture(mode)
                if mode==runner.OFFLINE:
                    (root/'MANIFEST.json').write_bytes(b'{"capture_mode":"AUTHORED_OFFLINE_ONLY","tampered":true}')
                with patch.object(runner,'process_alive',return_value=True):
                    self.assertEqual(active_paid_driver_count(evidence),1)
        evidence,root=self.active_driver_fixture(runner.OFFLINE)
        (root/'MANIFEST_SEAL.json').unlink()
        with patch.object(runner,'process_alive',return_value=True):
            self.assertEqual(active_paid_driver_count(evidence),1)
    def test_full_zero_provider_preflight(self):
        from formal_binding_preflight import deepseek_successor_preflight
        report=deepseek_successor_preflight(self.cfg,self.transport,self.route,authorization_file=self.auth,pricing_file=self.price)
        self.assertEqual(report['status'],'READY');self.assertEqual(len(report['slot_checks']),44)
        self.assertEqual(report['provider_call_invocations'],0);self.assertEqual(len(report['initial_context_checks']),7)

if __name__=='__main__':unittest.main(verbosity=2)
