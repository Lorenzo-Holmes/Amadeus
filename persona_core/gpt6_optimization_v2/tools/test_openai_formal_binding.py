"""OB-01..30: authored offline fixtures, no keys/network/quality judgments.

The local proof calculator in this module is a MOCK, installed only with patch.
It is intentionally absent from production's empty reviewed proof registry.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'persona_core/operational_runtime_v1'),str(Path(__file__).parent),str(ROOT/'persona_core/operational_build_v1/tools')]
import copy, hashlib, json, socket, unittest, uuid, subprocess
from contextlib import ExitStack
from unittest.mock import patch
import provider as p
import provider_openai as oa
import provider_contract as pc
import provider_adapters as adapters
import provider_transport as pt
import evaluation_runner as runner
from transcript_store import TranscriptStore,create_sandbox
from operations import open_chat
from accepted_output import project_turn
from semantic_binding import provider_identity

KEY='OFFLINE_AUTHOR_SENTINEL_ONLY'
TEXT='If the measurements agree, compare their differences before drawing a conclusion.'
PROOF='0'*64


def usage(i=100,c=20,w=30,o=10,r=4):
    return {'input_tokens':i,'input_tokens_details':{'cached_tokens':c,'cache_write_tokens':w},
            'output_tokens':o,'output_tokens_details':{'reasoning_tokens':r},'total_tokens':i+o}


def response(model=oa.MODELS[0],status='completed',text=TEXT,stats=True):
    result={'id':'resp_neutral','object':'response','model':model,'status':status,
        **{k:v for k,v in oa.generation_options().items() if k not in ('stream','include')},
        'output':[{'id':'msg_neutral','type':'message','role':'assistant','status':'completed',
            'content':[{'type':'output_text','text':text,'annotations':[]}]}],
        'usage':usage() if stats is True else stats}
    if status=='failed': result['error']={'code':'authored_failure','message':'neutral'}
    if status=='incomplete': result['incomplete_details']={'reason':'max_output_tokens'}
    return result


def wire(value=None,*,delta=True,crlf=False):
    value=value or response(); events=[{'type':'response.created','response':{'id':value['id'],'model':value['model'],'status':'in_progress'}}]
    if delta and value['output'] and value['output'][-1].get('type')=='message' and value['output'][-1]['content'][0].get('type')=='output_text':
        idx=len(value['output'])-1
        events.append({'type':'response.output_text.delta','output_index':idx,'content_index':0,
            'item_id':value['output'][idx]['id'],'delta':value['output'][idx]['content'][0]['text']})
    events.append({'type':'response.'+value['status'],'response':value})
    sep=b'\r\n' if crlf else b'\n'
    return b''.join(b'event: '+e['type'].encode()+sep+b'data: '+pc.canonical(dict(e,sequence_number=i))+sep+sep for i,e in enumerate(events))


def mock_proof(scope,value):
    payload=pc.canonical(value); msgs=value['input']
    return {'version':'APCORE_INPUT_BOUND_RECEIPT_1','request_sha256':hashlib.sha256(payload).hexdigest(),
        'messages_sha256':pc.digest(msgs),'model_id':value['model'],'source_binding':scope['source_binding'],
        'scope_sha256':pc.digest(scope),'proof_reference_sha256':PROOF,'host_bytes':len(pc.canonical(msgs)),
        'message_count':len(msgs),'content_token_count':1000,'framing_upper_tokens':27672,'input_upper_tokens':28672,
        'tokenizer':'AUTHORED_MOCK_NOT_REAL','tokenizer_version':'OFFLINE_ONLY','tokenizer_artifact_sha256':PROOF,
        'count_method':'AUTHORED_MOCK_NOT_A_PROOF'}


def offline_config(base):
    base.mkdir(parents=True,exist_ok=True)
    files=runner.source_bindings()
    p1=runner.GOAL/'architecture_scope_reconciliation_20260920_01/CONTRACT_FREEZE_MANIFEST.json'
    files.update(runner.read(p1)['files']); files[runner.relative(p1)]=runner.sha(p1)
    freeze=base/'SOURCE.json'; runner.write_new(freeze,{'freeze_id':base.name,'status':'OFFLINE_TEST_ONLY','files':files})
    config=runner.read(runner.GOAL/'bounded_boundary_p2_p3_20260920_01/FORMAL_ACCEPTANCE_CONFIG.json')
    config.update(acceptance_source_freeze=base.name,acceptance_source_manifest=oa.reference(freeze))
    configpath=base/'acceptance.json'; runner.write_new(configpath,config)
    transport=base/'transport.json'; runner.write_new(transport,{'version':pt.VERSION,'connect_timeout_seconds':15,'read_timeout_seconds':120,'worker_deadline_seconds':595})
    route=base/'route.json'; runner.write_new(route,oa.route())
    # Test authorization is bound to this explicitly authored work artifact.
    auth=base/'authorization.json'; runner.write_new(auth,{'status':'PROJECT_COMPLETION_SPEND_AUTHORIZED_AS_NEEDED',
        'candidate_id':oa.CANDIDATE,'batch_design_id':'APCORE_SUCCESSOR_EXTERNAL44_ASTRA_SOL_MAX_SINGLE_BATCH_1',
        'max_fresh_revisions':1,'max_generation_requests':44,'automatic_paid_retries':0,'count_api_requests':44,'count_retry_policy':0})
    price=ROOT/oa.CONTRACT_DIR/'OFFICIAL_PRICING_EVIDENCE.json'
    suite=runner.load_suite('external44',*oa.MODELS)
    scope=runner.build_successor_scope(base.name,suite,runner.read(price),runner.read(transport),runner.read(route),
        authorization_file=auth,pricing_file=price,acceptance_config_file=configpath)
    scope['semantic_acceptance_binding']=runner.build_acceptance_binding(scope,suite,configpath,
        rubric_path=runner.GOAL/'external_failure_v1/PRIVATE_RUBRIC.json',offline=True)
    return scope,configpath,transport,route,auth,price


class OpenAIFormalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=ROOT/'work/openai_formal_binding/tests'/('run_'+uuid.uuid4().hex)
        cls.scope,cls.config,cls.transport,cls.route,cls.auth,cls.price=offline_config(cls.base)

    def setUp(self):
        self.stack=ExitStack(); self.addCleanup(self.stack.close)
        for name in ('connect','connect_ex'):
            self.stack.enter_context(patch.object(socket.socket,name,side_effect=AssertionError('OFFLINE_NETWORK_FORBIDDEN')))
        self.keyguard=self.stack.enter_context(patch.object(oa.OpenAIAdapter,'credential',side_effect=AssertionError('OFFLINE_KEY_FORBIDDEN')))
        self.scope=copy.deepcopy(type(self).scope); self.adapter=oa.OpenAIAdapter(); self.sent=[]

    def payload(self,model=None):
        return pc.canonical(self.adapter.serialize(self.scope,model or oa.MODELS[0],[{'role':'user','content':'Neutral 雪 test.'}]))

    def enable_mock_proof(self):
        self.stack.enter_context(patch.object(oa,'LOCAL_INPUT_PROOFS',{PROOF:mock_proof}))
        self.stack.enter_context(patch.object(oa,'count_input_tokens',return_value={
            'response':{'object':'response.input_tokens','input_tokens':28672},'http_status':200,'response_sha256':PROOF}))
        self.scope['input_bound_proof']={'proof_reference_sha256':PROOF}
        self.scope['semantic_acceptance_binding']['provider_config_identity']=provider_identity(self.scope)

    def chat(self):
        root=self.base/('runtime_'+uuid.uuid4().hex); create_sandbox(root)
        store=TranscriptStore(root); self.addCleanup(store.close)
        slot=self.scope['slots'][0]; handle=store.open_session(self.scope['principal_id'],slot['entity_label'],'PRODUCT_RUNTIME')
        return store,handle,open_chat(store,handle,self.scope),slot

    def send(self,value=None,*,fault=None,display=True):
        self.enable_mock_proof(); store,handle,chat,slot=self.chat(); shown=[]
        def transport(payload,key):
            self.sent.append(payload)
            if fault: raise fault
            w=wire(value); return pt.TransportResult(200,oa.decode_http(w,200),w)
        result=chat.send_text(slot['user_text'],'neutral-test',slot_id=slot['id'],
            display=shown.append if display else None,transport=transport,credential_reader=lambda:KEY)
        return store,handle,chat,slot,result,shown,transport

    def test_ob01_exact_models(self):
        self.assertEqual(set(adapters.registry().adapters), {'deepseek','local_fixture','openrouter'})
        self.assertEqual(set(adapters.registry(include_formal=True).adapters), {'deepseek','local_fixture','openrouter','openai'})
        self.assertIsInstance(adapters.select(self.scope), oa.OpenAIAdapter)
        self.assertIsInstance(adapters.select(self.adapter.worker_contract(self.scope)), oa.OpenAIAdapter)
        with self.assertRaisesRegex(ValueError,'PROVIDER_NOT_REGISTERED'):
            adapters.select(dict(self.scope,schema_version=pc.SCOPE_VERSION))
        for model in oa.MODELS: oa.validate_payload(self.payload(model))
        for model in ('gpt-6','GPT-6-astra','gpt-6-astra-20260921','deepseek-v4-pro',None):
            with self.subTest(model=model),self.assertRaises(ValueError): self.adapter.validate_model(model,model)
        self.keyguard.assert_not_called()

    def test_ob02_exact_roles_and_schedule(self):
        p.scope_check(self.scope)
        slots=self.scope['slots']; self.assertEqual(len(slots),44)
        self.assertEqual([s['id'] for s in slots if s['model']==oa.MODELS[1]],['N09_S1','N09_S2'])
        for key,value in [('model',oa.MODELS[1]),('host_action_before','RESTART_SAME_SESSION')]:
            bad=copy.deepcopy(self.scope); bad['slots'][0][key]=value
            with self.assertRaises(ValueError): p.scope_check(bad)

    def test_ob03_closed_golden_serialization(self):
        for model in oa.MODELS:
            value=json.loads(self.payload(model)); self.assertEqual(set(value),set(oa.template()))
            self.assertEqual(value['input'],[{'role':'user','content':'Neutral 雪 test.'}])
            self.assertEqual(pc.canonical(value),self.payload(model))

    def test_ob04_unknown_fields_and_types(self):
        value=json.loads(self.payload())
        for field in oa.frozen_contract()['REQUEST_SERIALIZATION_CONTRACT.json']['explicit_not_sent']:
            bad=copy.deepcopy(value); bad[field]=None
            with self.subTest(field=field),self.assertRaises(ValueError): oa.validate_payload(pc.canonical(bad))
        for field,badvalue in [('reasoning',{'effort':'max','mode':'standard','extra':True}),('stream',1),('max_output_tokens',True),('text',None)]:
            bad=copy.deepcopy(value); bad[field]=badvalue
            with self.assertRaises(ValueError): oa.validate_payload(pc.canonical(bad))
        with self.assertRaises(ValueError): oa.strict_json('{"a":1,"a":2}')

    def test_ob05_reasoning_echo(self):
        for bad in ({'effort':'high','mode':'standard'}, {'effort':'max'}, None):
            value=response(); value['reasoning']=bad
            with self.assertRaises(ValueError): self.adapter.verify_effective_identity(self.scope,{'native_response':value},oa.MODELS[0])

    def test_ob06_fragmentation_and_conflicts(self):
        w=wire(response(text='雪\nneutral'),crlf=True); expected=oa.decode_http(w,200)
        for i in range(len(w)+1):
            parser=oa.OpenAIAssembly(pt.Lifecycle()); parser.feed(w[:i]); parser.feed(w[i:]); self.assertEqual(parser.body(),expected)
        for bad in (w+w,w.replace(b'"sequence_number":1',b'"sequence_number":0'),w.replace(b'"delta":"',b'"delta":"wrong')):
            with self.assertRaises(ValueError): oa.decode_http(bad,200)
        multiline=w.replace(b'"sequence_number":0,',b'"sequence_number":0,\r\ndata: ')
        self.assertEqual(oa.decode_http(multiline,200),expected)

    def test_ob07_visible_only(self):
        value=response(); value['output'].insert(0,{'id':'reason_neutral','type':'reasoning','summary':[],'encrypted_content':'opaque'})
        body=json.loads(oa.decode_http(wire(value),200)); self.assertEqual(body['choices'][0]['message']['content'],TEXT)
        for content in ([{'type':'refusal','refusal':'no'}],[]):
            v=response(); v['output'][0]['content']=content
            b=json.loads(oa.decode_http(wire(v,delta=False),200)); self.assertIsNotNone(b['provider_terminal']['reason'])

    def test_ob08_usage_decimal_and_native(self):
        native=usage(); result=pc.formal_accounting(native,self.scope,oa.MODELS[0],28672,TEXT)
        self.assertEqual(result['usd_estimate'],'0.001395'); self.assertEqual(result['estimate_micro_cny'],12276)
        self.assertEqual(result['native_usage'],native); self.assertFalse(result['billing_certified'])
        for key,value in [('input_tokens',True),('total_tokens',2),('output_tokens',-1)]:
            bad=copy.deepcopy(native); bad[key]=value
            self.assertEqual(pc.formal_accounting(bad,self.scope,oa.MODELS[0],28672)['accounting_status'],'INVALID_OR_MISSING_USAGE')

    def test_ob09_reasoning_is_not_double_billed(self):
        a=pc.formal_accounting(usage(r=0),self.scope,oa.MODELS[0],28672)
        b=pc.formal_accounting(usage(r=10),self.scope,oa.MODELS[0],28672)
        self.assertEqual(a['usd_estimate'],b['usd_estimate']); self.assertEqual(b['nonreasoning_output_tokens'],0)
        self.assertIsNone(b['official_visible_tokens'])

    def test_ob10_cache_buckets_and_missing_write(self):
        for c,w in ((0,0),(0,100),(100,0),(20,30)):
            result=pc.formal_accounting(usage(c=c,w=w),self.scope,oa.MODELS[0],28672)
            self.assertEqual(result['uncached_input_tokens']+c+w,100)
        v=usage(); del v['input_tokens_details']['cache_write_tokens']
        result=pc.formal_accounting(v,self.scope,oa.MODELS[0],28672)
        self.assertIsNone(result['cache_write_tokens']); self.assertTrue(result['reserve_retained']); self.assertIsNotNone(result['rejection'])

    def test_ob11_completed_journal_display(self):
        store,h,chat,slot,result,shown,_=self.send()
        self.assertEqual(result['status'],'DISPLAYED'); self.assertEqual(shown,[TEXT])
        call=store.db.execute('SELECT * FROM provider_calls').fetchone(); self.assertEqual(call['status'],'RESPONSE_CAPTURED')
        self.assertIsNone(json.loads(store.db.execute('SELECT contract_json FROM provider_call_contracts').fetchone()[0])['accounting']['rejection'])

    def test_ob12_incomplete_not_displayed(self):
        store,*rest=self.send(response(status='incomplete')); self.assertEqual(rest[4],[])
        self.assertEqual(store.db.execute('SELECT status FROM provider_calls').fetchone()[0],'RESPONSE_REJECTED_TERMINAL_KNOWN')
        self.assertEqual(store.db.execute('SELECT stopped FROM call_batches').fetchone()[0],1)

    def test_ob13_failed_and_empty(self):
        for value in (response(status='failed',stats=None),response(text=''),response(stats=None)):
            store,h,chat,slot,result,shown,_=self.send(value)
            self.assertEqual(shown,[]); self.assertEqual(store.db.execute('SELECT status FROM provider_calls').fetchone()[0],'RESPONSE_REJECTED_TERMINAL_KNOWN')

    def test_ob14_unknown_keeps_wire_reserve(self):
        fault=pt.TransportFault('INACTIVITY_TIMEOUT',b'data: partial',200)
        store,h,chat,slot,result,shown,_=self.send(fault=fault)
        row=store.db.execute('SELECT * FROM provider_calls').fetchone()
        self.assertEqual(row['status'],'SUBMITTED_STATUS_UNKNOWN'); self.assertEqual(row['reserve_micro_cny'],17571840)
        self.assertEqual(store.db.execute('SELECT wire_bytes FROM transport_wire_captures').fetchone()[0],b'data: partial')
        self.assertEqual(shown,[])

    def test_ob15_no_retry(self):
        for code in (429,500):
            with self.assertRaises(ValueError): oa.decode_http(b'{"error":{"code":"error"}}',code)
        store,h,chat,slot,result,shown,transport=self.send(fault=pt.TransportFault('INACTIVITY_TIMEOUT',b'',None))
        before=len(self.sent)
        call=store.db.execute('SELECT * FROM provider_calls').fetchone()
        again=p.ProviderJournal(store).call(h,call['turn_id'],self.scope['batch_id'],slot['id'],json.loads(call['context_json']),transport=transport,
            credential_reader=lambda:(_ for _ in ()).throw(AssertionError('KEY_ON_RETRY')))
        self.assertEqual(again['status'],'SUBMITTED_STATUS_UNKNOWN'); self.assertEqual(len(self.sent),before)

    def test_ob16_raw_wire_and_native_preserved(self):
        store,*_=self.send(); row=store.db.execute('SELECT * FROM provider_calls').fetchone()
        native=json.loads(row['raw_response'])['native_response']; self.assertEqual(native,response())
        w=store.db.execute('SELECT * FROM transport_wire_captures').fetchone()
        self.assertEqual(hashlib.sha256(w['wire_bytes']).hexdigest(),w['wire_sha256'])
        self.assertEqual(hashlib.sha256(row['raw_response']).hexdigest(),row['raw_sha256'])

    def test_ob17_display_projection(self):
        store,h,chat,slot,result,shown,_=self.send()
        row=dict(store.db.execute('SELECT t.*,p.raw_sha256 FROM turns t JOIN provider_calls p USING(turn_id)').fetchone())
        for purpose in ('history','evaluation','next_turn_context'):
            self.assertEqual(project_turn(store.db,row,purpose)['assistant_text'],TEXT)

    def test_ob18_accepted_identity(self):
        store,h,chat,slot,result,shown,_=self.send()
        row=dict(store.db.execute('SELECT t.*,p.raw_sha256 FROM turns t JOIN provider_calls p USING(turn_id)').fetchone())
        accepted=project_turn(store.db,row,'evaluation')['accepted_output']
        self.assertEqual(accepted['acceptance_identity'],self.scope['semantic_acceptance_binding'])
        bad=copy.deepcopy(self.scope); bad['semantic_acceptance_binding']['display_policy_version']='forged'
        with self.assertRaises(ValueError): open_chat(store,h,bad)

    def test_ob19_state_effect_separate(self):
        store,h,chat,slot,result,shown,_=self.send()
        cid=chat.admission.propose(h,'FACT_LEARNED',{'text':'The hypothesis is proven.'},key=uuid.uuid4().hex,source_turn_ids=[result['turn_id']])
        decision=chat.admission.decide(h,cid,None)
        self.assertIn(decision.verdict,('HOLD','REJECT'))
        # The legitimate utterance observation is distinct from a factual effect.
        self.assertEqual(store.db.execute("SELECT count(*) FROM runtime_events WHERE event_type NOT IN ('UTTERANCE_OBSERVED')").fetchone()[0],0)

    def test_ob20_identity_mutations(self):
        for key in self.scope['identity_references']:
            bad=copy.deepcopy(self.scope); bad['identity_references'][key]['sha256']='f'*64
            with self.subTest(key=key),self.assertRaises(ValueError): p.scope_check(bad)
        for key,value in [('source_binding',{}),('evaluation_schema','other'),('gate_denominators',{'A':1,'B':0}),('schedule_identity','bad')]:
            bad=copy.deepcopy(self.scope); bad[key]=value
            with self.assertRaises(ValueError): p.scope_check(bad)
        for key,value in [('fx_cny_per_usd','1'),('fee_fraction','0')]:
            bad=copy.deepcopy(self.scope); bad['spend_policy'][key]=value
            with self.assertRaises(ValueError): p.scope_check(bad)

    def test_ob21_restart_after_journal_and_terminal(self):
        for fault in (pt.TransportFault('PROCESS_EXIT_UNKNOWN',b'partial',None),None):
            store,h,chat,slot,result,shown,transport=self.send(fault=fault)
            call=store.db.execute('SELECT * FROM provider_calls').fetchone(); count=len(self.sent)
            root=store.root; sid=h.session_id; store.close()
            restored=TranscriptStore(root); self.addCleanup(restored.close)
            rh=restored.resume(self.scope['principal_id'],sid)
            again=p.ProviderJournal(restored).call(rh,call['turn_id'],self.scope['batch_id'],slot['id'],json.loads(call['context_json']),
                transport=transport,credential_reader=lambda:(_ for _ in ()).throw(AssertionError('KEY_ON_RECOVERY')))
            self.assertEqual(again['call_id'],call['call_id']); self.assertEqual(len(self.sent),count)

    def test_ob22_slot_idempotency(self):
        store,h,chat,slot,result,shown,transport=self.send(); count=len(self.sent)
        again=chat.send_text(slot['user_text'],'neutral-test',slot_id=slot['id'],display=shown.append,transport=transport,credential_reader=lambda:KEY)
        self.assertEqual(again['turn_id'],result['turn_id']); self.assertEqual(len(self.sent),count)

    def test_ob23_wrong_role_model(self):
        store,h,chat,slot,result,shown,_=self.send(response(model=oa.MODELS[1]))
        self.assertEqual(shown,[]); self.assertEqual(store.db.execute('SELECT status FROM provider_calls').fetchone()[0],'RESPONSE_REJECTED_TERMINAL_KNOWN')

    def test_ob24_fallback_and_route(self):
        for key,value in [('provider_id','other'),('endpoint','https://example.invalid/responses'),('network_route_policy',dict(oa.route(),mode='SYSTEM_PROXY'))]:
            bad=copy.deepcopy(self.scope); bad[key]=value
            with self.assertRaises(ValueError): p.scope_check(bad)

    def test_ob25_count_policy_fail_before_key(self):
        self.scope['count_endpoint']='https://invalid.example/count'
        with self.assertRaises(ValueError): self.chat()
        self.keyguard.assert_not_called()
        self.scope=copy.deepcopy(type(self).scope)
        self.enable_mock_proof(); payload=self.payload(); receipt=oa.local_input_bound(self.scope,payload)
        for key,value in [('request_sha256','f'*64),('input_upper_tokens',28673),('message_count',999),('model_id',oa.MODELS[1])]:
            bad=copy.deepcopy(receipt); bad[key]=value
            with self.assertRaises(ValueError): oa.verify_input_receipt(self.scope,payload,bad)
        with self.assertRaises(ValueError): self.adapter.serialize(self.scope,oa.MODELS[0],[{'role':'user','content':'雪'*24576}])

    def test_ob26_actual_breach_not_clamped(self):
        v=response(stats=usage(i=28673,o=32769)); store,h,chat,slot,result,shown,_=self.send(v)
        binding=json.loads(store.db.execute('SELECT contract_json FROM provider_call_contracts').fetchone()[0])
        self.assertEqual(binding['accounting']['input_tokens'],28673); self.assertEqual(binding['accounting']['output_total_tokens'],32769)
        self.assertEqual(binding['accounting']['rejection'],'ACCOUNTING_BOUND_VIOLATION'); self.assertEqual(shown,[])

    def test_ob27_scope_isolation(self):
        self.assertEqual(pc.SCOPE_VERSION,'apcore-provider-scope-6')
        for version in ('apcore-provider-scope-5','apcore-provider-scope-6'):
            bad=copy.deepcopy(self.scope); bad['schema_version']=version
            with self.assertRaises(ValueError): p.scope_check(bad)
        with self.assertRaises(ValueError): runner.load_suite('heldout',*oa.MODELS)

    def test_ob28_authorization_supersession_and_reserve(self):
        p.scope_check(self.scope); self.assertEqual(self.scope['reserved_upper_micro_cny'],752074752)
        self.assertEqual(self.scope['total_guard_cny'],'752.074752')
        for amount in ('19','753'):
            bad=copy.deepcopy(self.scope); bad['total_guard_cny']=amount
            with self.assertRaises(ValueError): p.scope_check(bad)
        bad=copy.deepcopy(self.scope); bad['spend_policy']['authorization_identity']['sha256']='0'*64
        with self.assertRaises(ValueError): p.scope_check(bad)

    def test_ob29_real_worker_ipc_fake_http(self):
        # Real provider_http_worker main and pipe framing; child sockets disabled.
        self.enable_mock_proof()
        payload=self.payload(); w=wire(); harness=self.base/('child_'+uuid.uuid4().hex+'.py')
        count=oa.authoritative_input_count_guard(self.scope,payload,KEY,self.scope['slots'][0]['id'],persist=lambda *a:None)
        harness.write_text('import sys,socket,io\n'+f'sys.path.insert(0,{str(runner.CODE)!r})\n'+
            'def deny(*a,**k): raise AssertionError("OFFLINE_NETWORK_FORBIDDEN")\n'+
            'socket.socket.connect=deny\nsocket.socket.connect_ex=deny\n'+
            'import provider_openai as o,provider_http_worker as worker\no.credential=deny\n'+
            'class Reply(io.BytesIO):\n status=200\n def read1(self,n): return self.read(n)\n'+
            'class Opener:\n def open(self,request,timeout):\n'+f'  assert request.data=={payload!r}\n  return Reply({w!r})\n'+
            'original=o.http_exchange\ndef fake(*a,**k): return original(*a,**k,opener_factory=lambda lifecycle:Opener())\n'+
            'o.http_exchange=fake\nraise SystemExit(worker.main())\n',encoding='utf-8')
        result=pt.worker_exchange(payload,KEY,600,self.scope['transport_policy'],[sys.executable,'-B',str(harness)],ROOT,
            lambda e:None,adapter_contract=self.adapter.worker_contract(self.scope,count))
        adapters.verified_result(self.adapter,self.scope,result); self.assertEqual(result.wire,w)

    def test_ob30_zero_call_construction_and_not_ready(self):
        from formal_binding_preflight import successor_preflight
        before=set(runner.EVIDENCE.glob('G6_V2_*'))
        result=successor_preflight(self.config,self.transport,self.route,authorization_file=self.auth,pricing_file=self.price,diagnostics_only=True)
        self.assertEqual(result['status'],'NOT_READY'); self.assertEqual(len(result['slot_checks']),44)
        self.assertEqual(len(result['initial_context_checks']),7); self.assertEqual(result['provider_call_rows'],0)
        gate=successor_preflight(self.config,self.transport,self.route,authorization_file=self.auth,pricing_file=self.price)
        self.assertTrue(gate['formal_preflight_executed']); self.assertEqual(gate['status'],'READY')
        self.assertEqual(gate['token_count_request_invocations'],0);self.assertEqual(gate['generation_request_invocations'],0)
        self.assertEqual(set(runner.EVIDENCE.glob('G6_V2_*')),before)

    def test_ob06_invalid_terminal_and_eof(self):
        good=wire()
        for value in (good[:-4],good.split(b'event: response.completed')[0],good.replace(b'resp_neutral',b'other',1),
                      good.replace(b'"status":"completed"',b'"status":"incomplete"')):
            with self.assertRaises(ValueError): oa.decode_http(value,200)
        body=oa.decode_http(good,200)
        with self.assertRaises(pt.TransportFault): adapters.verified_result(self.adapter,self.scope,pt.TransportResult(200,body+b' ',good))

    def test_ob07_empty_reasoning_tool_multiple(self):
        two=response()['output']+[dict(response()['output'][0],id='second')]
        for output in ([{'id':'r','type':'reasoning'}],[{'id':'tool','type':'function_call'}],two):
            v=response(); v['output']=output
            b=json.loads(oa.decode_http(wire(v,delta=False),200)); self.assertIsNotNone(b['provider_terminal']['reason'])

    def test_ob10_invalid_cache_and_reasoning(self):
        for c,w,r in ((80,80,0),(True,0,0),(0,-1,0),(0,0,11)):
            self.assertIsNotNone(pc.formal_accounting(usage(c=c,w=w,r=r),self.scope,oa.MODELS[0],28672)['rejection'])
        v=usage(); del v['output_tokens_details']['reasoning_tokens']
        a=pc.formal_accounting(v,self.scope,oa.MODELS[0],28672)
        self.assertIsNone(a['nonreasoning_output_tokens']); self.assertIsNotNone(a['rejection'])

    def test_ob21_crash_after_journal_and_before_commit(self):
        from contextlib import contextmanager
        self.enable_mock_proof()
        for stage in ('during_exchange','terminal_before_commit'):
            store,h,chat,slot=self.chat(); turn=store.begin_turn(h,slot['user_text'],'crash')
            context=chat.build_request_context(turn['turn_id']); original=store.transaction; counts=[0];sent_before=len(self.sent)
            @contextmanager
            def transaction():
                counts[0]+=1
                if len(self.sent)>sent_before and stage=='terminal_before_commit': raise SystemExit('AUTHORED_CRASH')
                with original(): yield
            def transport(payload,key):
                self.sent.append(payload)
                if stage=='during_exchange': raise SystemExit('AUTHORED_CRASH')
                w=wire(); return pt.TransportResult(200,oa.decode_http(w,200),w)
            with patch.object(store,'transaction',transaction),self.assertRaises(SystemExit):
                p.ProviderJournal(store).call(h,turn['turn_id'],self.scope['batch_id'],slot['id'],context,transport=transport,credential_reader=lambda:KEY)
            count=len(self.sent); root=store.root; sid=h.session_id; store.close()
            restored=TranscriptStore(root); self.addCleanup(restored.close); rh=restored.resume(self.scope['principal_id'],sid)
            result=p.ProviderJournal(restored).call(rh,turn['turn_id'],self.scope['batch_id'],slot['id'],context,transport=transport,credential_reader=lambda:KEY)
            self.assertEqual(result['status'],'SUBMITTED_STATUS_UNKNOWN'); self.assertEqual(len(self.sent),count)

    def test_ob22_concurrent_journal_contenders(self):
        import threading
        self.enable_mock_proof(); store,h,chat,slot=self.chat()
        turn=store.begin_turn(h,slot['user_text'],'race'); context=chat.build_request_context(turn['turn_id'])
        root=store.root; sid=h.session_id; start=threading.Barrier(2); calls=[]; outcomes=[]
        def contend():
            s=TranscriptStore(root)
            try:
                hh=s.resume(self.scope['principal_id'],sid); journal=p.ProviderJournal(s); start.wait(timeout=10)
                def transport(payload,key):
                    calls.append(payload); w=wire(); return pt.TransportResult(200,oa.decode_http(w,200),w)
                try: outcomes.append(journal.call(hh,turn['turn_id'],self.scope['batch_id'],slot['id'],context,transport=transport,credential_reader=lambda:KEY)['status'])
                except ValueError: outcomes.append('LOCAL_RACE_REFUSED')
            finally: s.close()
        ts=[threading.Thread(target=contend) for _ in range(2)]
        for t in ts: t.start()
        for t in ts: t.join(timeout=30)
        self.assertFalse(any(t.is_alive() for t in ts)); self.assertEqual(len(outcomes),2)
        self.assertEqual(len(calls),1); self.assertEqual(store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0],1)

    def test_ob25_untrusted_proof_and_many_messages(self):
        self.scope['input_bound_proof']={'proof_reference_sha256':PROOF,'input_upper_tokens':1}
        with self.assertRaisesRegex(ValueError,'INPUT_BOUND_PROOF_NOT_READY'): oa.local_input_bound(self.scope,self.payload())
        with self.assertRaises(ValueError): self.adapter.serialize(self.scope,oa.MODELS[0],[{'role':'user','content':''}]*1000)

    def test_ob30_sandbox_containment(self):
        from transcript_store import safe_root
        self.assertEqual(safe_root(self.base/'sandbox'),(self.base/'sandbox').resolve())
        for path in (ROOT/'work',ROOT/'work/unrelated',ROOT/'persona_core/runtime',ROOT/'work/openai_formal_binding'):
            with self.assertRaises(ValueError): safe_root(path)

    def test_ob02_inputs_cannot_be_substituted(self):
        self.scope['slots'][0]['user_text']='a substituted question'
        with self.assertRaisesRegex(ValueError,'OPENAI_FROZEN_SLOT_INPUT_CHANGED'): p.scope_check(self.scope)

    def test_ob05_additional_echo_metadata_is_preserved(self):
        value=response(); value['reasoning']['summary']=None
        self.assertTrue(self.adapter.verify_effective_identity(self.scope,{'native_response':value},oa.MODELS[0]))
        self.assertIn('summary',json.loads(oa.decode_http(wire(value),200))['native_response']['reasoning'])

    def test_ob15_http_failures_submit_only_once(self):
        import io
        self.enable_mock_proof()
        receipt=oa.authoritative_input_count_guard(self.scope,self.payload(),KEY,self.scope['slots'][0]['id'],persist=lambda *a:None)
        for status in (429,500):
            attempts=[]
            class Reply(io.BytesIO):
                def read1(self,n): return self.read(n)
            class Opener:
                def open(self,request,timeout):
                    attempts.append(request.full_url); result=Reply(b'{"error":{"code":"authored"}}'); result.status=status; return result
            with self.assertRaises(pt.TransportFault): oa.http_exchange(self.payload(),KEY,self.scope['transport_policy'],
                self.adapter.worker_contract(self.scope,receipt),opener_factory=lambda lifecycle:Opener())
            self.assertEqual(attempts,[oa.ENDPOINT])


if __name__=='__main__': unittest.main(verbosity=2)
