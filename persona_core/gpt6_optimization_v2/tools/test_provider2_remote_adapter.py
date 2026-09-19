"""Authored native protocol and journal tests; all HTTP is in memory."""
from __future__ import annotations
import copy
import io
import json
from pathlib import Path
import sqlite3
import sys
import unittest
import uuid
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'persona_core/operational_runtime_v1'),str(Path(__file__).parent)]
import provider as p
import provider_adapters as a
import provider_contract as c
import provider_openrouter as o
import provider_transport as pt
import provider2_remote_validation as driver
from transcript_store import TranscriptStore, create_sandbox
OUT=ROOT/'persona_core/operational_build_v1/evidence'/('PROVIDER2_REMOTE_OFFLINE_'+uuid.uuid4().hex)
KEY='AUTHORED_CREDENTIAL_SENTINEL_ONLY'


def chunk(delta=None,finish=None,usage=None,**extra):
    result={'id':'gen-authored','model':o.MODEL,'provider':'OpenAI','created':1,
        'choices':[{'index':0,'delta':delta or {},'finish_reason':finish}]}
    if usage is not None: result['usage']=usage
    result.update(extra); return result


def usage(): return {'prompt_tokens':20,'completion_tokens':10,'total_tokens':30,
    'prompt_tokens_details':{'cached_tokens':3},'completion_tokens_details':{'reasoning_tokens':0},'cost':0.0001}


def wire(text='A blue cube rests on a white table.', finish='stop', stats=True, reasoning=None, error=False, done=True, model=None, tools=False):
    delta={'content':text,'role':'assistant'}
    if reasoning is not None: delta['reasoning']=reasoning
    if tools: delta['tool_calls']=[{'id':'tool-authored'}]
    events=[chunk(delta)]
    events.append(chunk(finish='error' if error else finish,**({'error':{'code':'server_error','message':'AUTHORED_ERROR_TEXT'}} if error else {})))
    if stats is not False:
        events.append(chunk(finish=finish,usage=usage() if stats is True else stats))
    if error: events=events[:2]
    if model:
        for event in events:event['model']=model
    return b': keepalive\r\n\r\n'+b''.join(b'data: '+pt.encode(e)+b'\r\n\r\n' for e in events)+(b'data: [DONE]\r\n\r\n' if done else b'')


class ContractTests(unittest.TestCase):
    def setUp(self): self.scope=o.make_scope('AUTHORED'); self.adapter=o.OpenRouterAdapter()
    def test_exact_serialization_and_disabled_fallbacks(self):
        body=self.adapter.serialize(self.scope,o.MODEL,[{'role':'user','content':'neutral'}])
        self.assertEqual(set(body),{'model','messages','max_tokens','stream','stream_options','temperature','provider'})
        self.assertFalse(body['provider']['allow_fallbacks']); self.assertEqual(body['provider']['only'],['openai'])
        self.assertEqual(body['stream_options'],{'include_usage':True}); p.scope_check(self.scope)
    def test_native_routing_and_temperature_are_bound(self):
        for key in ('provider','temperature'):
            bad=copy.deepcopy(self.scope); bad['generation_config'][key]={} if key=='provider' else 1
            with self.assertRaises(ValueError): p.scope_check(bad)
            self.assertNotEqual(c.generation_identity(bad,o.MODEL,[]),c.generation_identity(self.scope,o.MODEL,[]))
    def test_provider_model_route_source_protocol_distinct_identity(self):
        initial=c.generation_identity(self.scope,o.MODEL,[])
        for key,value in [('provider_id','deepseek'),('api_protocol','responses'),('endpoint','https://invalid.invalid'),
            ('source_binding',{}),('network_route_policy',o.route('DIRECT_NO_PROXY'))]:
            bad=copy.deepcopy(self.scope); bad[key]=value
            with self.subTest(key=key): self.assertNotEqual(initial,c.generation_identity(bad,o.MODEL,[]))
        self.assertNotEqual(initial,c.generation_identity(self.scope,'another-model',[]))
    def test_no_arbitrary_endpoints_or_routes(self):
        for value in ['https://api.deepseek.com','http://openrouter.ai/api/v1/chat/completions','https://user:secret@openrouter.ai/']:
            bad=copy.deepcopy(self.scope); bad['endpoint']=value
            with self.assertRaises(ValueError): p.scope_check(bad)
    def test_capabilities_source_reasoning_and_retry_rejected(self):
        changes=[('source_binding',{}),('thinking',{'type':'enabled'}),('automatic_paid_retries',1),('capabilities',{})]
        for key,value in changes:
            bad=copy.deepcopy(self.scope); bad[key]=value
            with self.assertRaises(ValueError): p.scope_check(bad)
    def test_bounded_unestimated_exception_only_for_new_adapter(self):
        self.assertIsNone(self.adapter.rates(self.scope,o.MODEL)); self.assertIsNone(self.adapter.reserve(self.scope,o.MODEL,100))
        with self.assertRaises(ValueError): a.DeepSeekAdapter().validate_spend(self.scope)
        for key,value in [('max_input_bytes',4097),('max_output_tokens',8193),('slots',self.scope['slots'][:1])]:
            bad=copy.deepcopy(self.scope); bad[key]=value
            with self.assertRaises(ValueError): self.adapter.validate_spend(bad)
    def test_fixed_model_and_alias_validation(self):
        for model in o.MODEL_ALIASES: self.adapter.validate_model(o.MODEL,model)
        with self.assertRaises(ValueError): self.adapter.validate_model(o.MODEL,'deepseek-v4-pro')
    def test_worker_contract_closed_schema(self):
        value=self.adapter.worker_contract(self.scope); a.validate_worker_contract(value)
        value['credential']=KEY
        with self.assertRaises(ValueError): a.validate_worker_contract(value)
    def test_payload_schema_prevents_tools_or_model_fallback(self):
        body=self.adapter.serialize(self.scope,o.MODEL,[{'role':'user','content':'neutral'}])
        for field in ('tools','models','plugins'):
            bad={**body,field:[]}
            with self.assertRaises(ValueError): o.validate_payload(pt.encode(bad))


class ParserTests(unittest.TestCase):
    def test_fragmentation_and_duplicate_finish_usage_chunk(self):
        data=wire(); expected=o.decode_http(data,200)
        for step in (1,3,17,8192):
            parser=o.OpenRouterAssembly(pt.Lifecycle())
            for offset in range(0,len(data),step): parser.feed(data[offset:offset+step])
            self.assertEqual(parser.body(),expected)
    def test_usage_normalizes_cache_without_invented_cost(self):
        data=json.loads(o.decode_http(wire(),200)); self.assertEqual(c.validate_usage(data['usage']),(3,17))
        self.assertNotIn('cost',data['usage']); self.assertIsNone(c.estimate_usage(data['usage'],None))
    def test_completed_and_incomplete_terminal(self):
        for finish,status in [('stop','completed'),('length','incomplete'),('content_filter','incomplete'),('tool_calls','incomplete')]:
            self.assertEqual(json.loads(o.decode_http(wire(finish=finish),200))['provider_terminal']['status'],status)
    def test_explicit_error_is_failed_without_done(self):
        result=o.decode_http(wire(error=True,done=False),200)
        self.assertEqual(json.loads(result)['provider_terminal']['status'],'failed')
        self.assertNotIn(b'AUTHORED_ERROR_TEXT',result)
    def test_http_json_error_known_html_error_unknown(self):
        result=o.decode_http(pt.encode({'error':{'code':402,'message':KEY}}),402)
        self.assertEqual(json.loads(result)['provider_terminal']['status'],'failed'); self.assertNotIn(KEY.encode(),result)
        for data in (b'<html>Error</html>',b'{}',b'{'):
            with self.assertRaises(ValueError): o.decode_http(data,502)
    def test_disconnect_does_not_gain_terminal(self):
        with self.assertRaises(ValueError): o.decode_http(wire(done=False),200)
    def test_identity_change_is_untrusted(self):
        bad=wire().replace(b'"gen-authored"',b'"gen-other"',1)
        with self.assertRaises(ValueError): o.decode_http(bad,200)
    def test_content_after_finish_is_untrusted(self):
        bad=wire().replace(b'data: [DONE]',b'data: '+pt.encode(chunk({'content':'late'}))+b'\r\n\r\ndata: [DONE]')
        with self.assertRaises(ValueError): o.decode_http(bad,200)
    def test_trailing_partial_record_is_untrusted(self):
        with self.assertRaises(ValueError): o.decode_http(wire()+b'data: {',200)
    def test_reasoning_never_becomes_visible_answer(self):
        body=json.loads(o.decode_http(wire(text='',reasoning='private reasoning'),200))
        self.assertEqual(body['choices'][0]['message']['content'],'')
        with self.assertRaisesRegex(ValueError,'EMPTY_RESPONSE'): c.usable_reply(body)
    def test_malformed_usage_preserves_terminal_for_journal(self):
        for stats in ({'prompt_tokens':True,'completion_tokens':2,'total_tokens':3},
            {'prompt_tokens':20,'completion_tokens':-1,'total_tokens':19},
            {'prompt_tokens':20,'completion_tokens':10,'total_tokens':31},
            {'prompt_tokens':20,'completion_tokens':10,'total_tokens':30,'prompt_tokens_details':'invalid'},
            {'prompt_tokens':20,'completion_tokens':10,'total_tokens':30,'prompt_tokens_details':{'cached_tokens':21}}):
            body=json.loads(o.decode_http(wire(stats=stats),200)); self.assertEqual(body['provider_terminal']['status'],'completed')
            with self.assertRaises((ValueError,TypeError)): c.validate_usage(body['usage'])
    def test_forged_body_fails_parent_native_wire_check(self):
        with self.assertRaises(pt.TransportFault): a.verified_result(o.OpenRouterAdapter(),o.make_scope('TEST'),pt.TransportResult(200,b'{}',wire()))


class Response(io.BytesIO):
    status=200; chunked=True
    def read1(self,n): return self.read(min(n,19))
class Opener:
    def __init__(self,data,status=200): self.data=data; self.status=status; self.count=0
    def open(self,request,timeout):
        self.count+=1
        assert request.full_url==o.ENDPOINT and request.get_method()=='POST'
        response=Response(self.data); response.status=self.status; return response


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.scope=o.make_scope('TEST'); self.adapter=o.OpenRouterAdapter()
        self.payload=pt.encode(self.adapter.serialize(self.scope,o.MODEL,[{'role':'user','content':'neutral'}]))
    def test_one_native_exchange_with_worker_dispatch(self):
        opener=Opener(wire()); events=[]
        result=o.http_exchange(self.payload,KEY,self.scope['transport_policy'],self.adapter.worker_contract(self.scope),events.append,lambda _:opener)
        self.assertEqual(opener.count,1); a.verified_result(self.adapter,self.scope,result)
        self.assertTrue({'worker_started','provider_finish','stream_done','worker_terminal'} <= {e['event'] for e in events})
    def test_disconnect_never_retries(self):
        opener=Opener(wire(done=False))
        with self.assertRaises(pt.TransportFault): o.http_exchange(self.payload,KEY,self.scope['transport_policy'],self.adapter.worker_contract(self.scope),opener_factory=lambda _:opener)
        self.assertEqual(opener.count,1)
    def test_exception_diagnostic_redacts_messages(self):
        class Failed:
            def open(self,*args,**kwargs): raise OSError('Bearer '+KEY)
        events=[]
        with self.assertRaises(pt.TransportFault) as captured:
            o.http_exchange(self.payload,KEY,self.scope['transport_policy'],self.adapter.worker_contract(self.scope),events.append,lambda _:Failed())
        self.assertNotIn(KEY,str(captured.exception)); self.assertNotIn(KEY,json.dumps(events))
    def test_http_known_error_validated_in_parent(self):
        opener=Opener(pt.encode({'error':{'code':402,'message':KEY}}),402)
        result=o.http_exchange(self.payload,KEY,self.scope['transport_policy'],self.adapter.worker_contract(self.scope),opener_factory=lambda _:opener)
        a.verified_result(self.adapter,self.scope,result); self.assertNotIn(KEY.encode(),result.body)
    def test_child_dispatch_returns_bound_receipt(self):
        import base64
        frame={'payload':self.payload.decode(),'credential':KEY,'transport_policy':self.scope['transport_policy'],
            'adapter_contract':self.adapter.worker_contract(self.scope)}
        class Stderr: buffer=io.BytesIO()
        with patch.object(o,'http_exchange',return_value=pt.TransportResult(200,o.decode_http(wire(),200),wire())),patch.object(sys,'stderr',Stderr()):
            output=pt.child_result(frame,'authored-frame-hash')
        data=json.loads(output[len(pt.RESULT_HEADER):]); self.assertEqual(data['frame_sha256'],'authored-frame-hash')
        self.assertEqual(data['kind'],'terminal'); self.assertEqual(base64.b64decode(data['wire']),wire())


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.root=create_sandbox(OUT/self._testMethodName); self.store=TranscriptStore(self.root)
        self.journal=p.ProviderJournal(self.store); self.scope=o.make_scope('JOURNAL'); self.journal.register_batch(self.scope)
        self.handle=self.store.open_session(self.scope['principal_id'],self.scope['slots'][0]['entity_label'],'CHARACTER_SIMULATION')
    def tearDown(self): self.store.close()
    def prepare(self,slot=0):
        s=self.scope['slots'][slot]; turn=self.store.begin_turn(self.handle,s['user_text'],s['id'])
        return s,turn,{'turn_id':turn['turn_id'],'mode':self.handle.mode,'messages':[{'role':'user','content':s['user_text']}]}
    def submit(self,prepared=None,data=None,status=200):
        s,turn,context=prepared or self.prepare(); data=wire() if data is None else data
        def transport(payload,key):
            with sqlite3.connect(self.root/'runtime.sqlite3') as db:
                assert db.execute('SELECT status FROM provider_calls WHERE turn_id=?',(turn['turn_id'],)).fetchone()[0]=='SUBMITTED_STATUS_UNKNOWN'
            return pt.TransportResult(status,o.decode_http(data,status),data)
        return self.journal.call(self.handle,turn['turn_id'],self.scope['batch_id'],s['id'],context,transport=transport,credential_reader=lambda:KEY)
    def test_journal_first_capture_identity_and_unestimated_accounting(self):
        result=self.submit(); self.assertEqual(result['status'],'RESPONSE_CAPTURED')
        self.assertEqual(result['provider_binding']['provider_id'],'openrouter'); self.assertEqual(result['usage_status'],'KNOWN')
        summary=self.journal.summary('JOURNAL'); self.assertFalse(summary['estimate_complete']); self.assertIsNone(summary['peak_usage_estimate_cny'])
    def test_malformed_usage_known_rejection(self):
        self.assertEqual(self.submit(data=wire(stats={'prompt_tokens':True}))['status'],'RESPONSE_REJECTED_TERMINAL_KNOWN')
    def test_missing_usage_known_rejection(self):
        self.assertEqual(self.submit(data=wire(stats=False))['status'],'RESPONSE_REJECTED_TERMINAL_KNOWN')
    def test_reasoning_only_known_rejection(self):
        self.assertEqual(self.submit(data=wire(text='',reasoning='reasoning'))['status'],'RESPONSE_REJECTED_TERMINAL_KNOWN')
    def test_length_known_rejection_with_known_usage(self):
        result=self.submit(data=wire(finish='length')); self.assertEqual(result['status'],'RESPONSE_REJECTED_TERMINAL_KNOWN'); self.assertEqual(result['usage_status'],'KNOWN')
    def test_failed_stream_known_rejection(self):
        self.assertEqual(self.submit(data=wire(error=True,done=False))['status'],'RESPONSE_REJECTED_TERMINAL_KNOWN')
    def test_wrong_model_known_rejection(self):
        result=self.submit(data=wire(model='unexpected-model')); self.assertEqual(result['status'],'RESPONSE_REJECTED_TERMINAL_KNOWN')
    def test_tools_known_rejection(self):
        self.assertEqual(self.submit(data=wire(tools=True))['status'],'RESPONSE_REJECTED_TERMINAL_KNOWN')
    def test_http_failure_known_rejection_and_secret_redacted(self):
        result=self.submit(data=pt.encode({'error':{'code':401,'message':KEY}}),status=401)
        self.assertEqual(result['status'],'RESPONSE_REJECTED_TERMINAL_KNOWN'); self.assertNotIn(KEY,'\n'.join(self.store.db.iterdump()))
    def test_secret_echo_known_rejection_and_private_wire_redaction(self):
        result=self.submit(data=wire(text=KEY)); self.assertEqual(result['error_category'],'SECRET_ECHO_QUARANTINED')
        self.assertNotIn(KEY,'\n'.join(self.store.db.iterdump()))
    def test_disconnect_unknown_never_resubmits_or_opens_long_slot(self):
        prepared=self.prepare(); first=self.submit(prepared,data=wire(done=False)); self.assertEqual(first['status'],'SUBMITTED_STATUS_UNKNOWN')
        s,turn,context=prepared
        second=self.journal.call(self.handle,turn['turn_id'],'JOURNAL',s['id'],context,
            transport=lambda *args:self.fail('retry'),credential_reader=lambda:self.fail('credential reload'))
        self.assertEqual(first['call_id'],second['call_id'])
        with self.assertRaises(ValueError): self.submit(self.prepare(1))
        self.assertEqual(self.journal.summary('JOURNAL')['calls_submitted'],1)
    def test_isolated_journal_does_not_modify_another_journal(self):
        self.submit(data=wire(done=False)); other=TranscriptStore(create_sandbox(OUT/(self._testMethodName+'_second')))
        try:
            p.ProviderJournal(other); self.assertEqual(other.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0],0)
        finally: other.close()
        self.assertEqual(self.journal.summary('JOURNAL')['remote_outcome_unknown_count'],1)
    def test_immutable_scope_rejects_provider_or_model_reassignment(self):
        self.submit(); bad=copy.deepcopy(self.scope); bad['provider_id']='local_fixture'
        with self.assertRaises(ValueError): self.journal.register_batch(bad)


class DriverTests(unittest.TestCase):
    def test_fixed_existing_intent_prevents_any_submission(self):
        dest=OUT/'existing_intent'; dest.mkdir(parents=True)
        with patch.object(driver,'DESTINATION',dest),patch.object(driver,'verify_source',return_value={'freeze_id':driver.FREEZE_ID}), \
             patch.object(o.OpenRouterAdapter,'credential',return_value=KEY),patch.object(p.ProviderJournal,'call',side_effect=AssertionError('resubmission')):
            with self.assertRaises(FileExistsError): driver.run()
    def test_unknown_driver_stops_after_one_submission(self):
        dest=OUT/'unknown_driver'
        original=p.ProviderJournal.call
        def invoke(journal,*args,**kwargs):
            def disconnected(*_): raise pt.TransportFault('INACTIVITY_TIMEOUT',wire(done=False),200)
            return original(journal,*args,transport=disconnected,credential_reader=lambda:KEY,**kwargs)
        with patch.object(driver,'DESTINATION',dest),patch.object(driver,'verify_source',return_value={'freeze_id':driver.FREEZE_ID}), \
             patch.object(driver,'sha',return_value='authored-hash'),patch.object(o.OpenRouterAdapter,'credential',return_value=KEY), \
             patch.object(p.ProviderJournal,'call',invoke):
            result=driver.run()
        self.assertEqual(result['status'],'STOPPED_UNKNOWN'); self.assertEqual(result['remote_generation_requests'],1)
        self.assertEqual(result['new_remote_unknown_count'],1); self.assertFalse((dest/'LONG_SYNTHETIC_RESULT.json').exists())
    def test_success_driver_consumes_exactly_two_slots(self):
        dest=OUT/'two_slot_driver'; original=p.ProviderJournal.call
        def invoke(journal,*args,**kwargs):
            result=original(journal,*args,transport=lambda *_:pt.TransportResult(200,o.decode_http(wire(),200),wire()),credential_reader=lambda:KEY,**kwargs)
            self.assertEqual(result['capture_origin'],'AUTHORED_PROVIDER_TEST_FIXTURE')
            return result
        def assessed(store,handle,turn_id,call,slot):
            return {'slot':slot,'passed':True,'status':call['status'],'terminal_known':True,'visible_characters':10000,'usage_status':'KNOWN'}
        with patch.object(driver,'DESTINATION',dest),patch.object(driver,'verify_source',return_value={'freeze_id':driver.FREEZE_ID}), \
             patch.object(driver,'sha',return_value='authored-hash'),patch.object(o.OpenRouterAdapter,'credential',return_value=KEY), \
             patch.object(p.ProviderJournal,'call',invoke),patch.object(driver,'assess',assessed):
            result=driver.run()
            with self.assertRaises(FileExistsError): driver.run()
        self.assertTrue(result['passed']); self.assertEqual(result['remote_generation_requests'],2)
        self.assertEqual([r['slot'] for r in result['results']],['SHORT_SYNTHETIC','LONG_SYNTHETIC'])


if __name__=='__main__': unittest.main(verbosity=2)
