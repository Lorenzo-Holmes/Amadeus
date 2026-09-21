"""Offline count/identity/failure tests. No provider evidence or real credentials."""
import copy,io,json,hashlib,socket,unittest,urllib.error
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
import test_openai_formal_binding as base
oa=base.oa;pc=base.pc;p=base.p;pt=base.pt

class Reply(io.BytesIO):
    status=200
    def read1(self,n): return self.read(n)

class CountGuardTests(unittest.TestCase):
    setUpClass=classmethod(base.OpenAIFormalTests.setUpClass.__func__)
    setUp=base.OpenAIFormalTests.setUp
    payload=base.OpenAIFormalTests.payload
    chat=base.OpenAIFormalTests.chat
    enable_mock_proof=base.OpenAIFormalTests.enable_mock_proof
    send=base.OpenAIFormalTests.send

    def count(self,n=100,*,wire=None,status=200,error=None,payload=None):
        payload=payload or self.payload(); requests=[]
        class Opener:
            def open(this,request,timeout):
                requests.append(request)
                if error: raise error
                result=Reply(wire if wire is not None else pc.canonical({'object':'response.input_tokens','input_tokens':n}))
                result.status=status;return result
        result=oa.count_input_tokens(self.scope,oa.build_count_payload(payload),base.KEY,opener_factory=lambda lifecycle:Opener())
        self.assertEqual(len(requests),1)
        self.assertEqual(requests[0].full_url,oa.COUNT_ENDPOINT)
        self.assertEqual(requests[0].get_method(),'POST')
        return result

    def receipt(self,n=100,payload=None):
        payload=payload or self.payload();slot=self.scope['slots'][0]['id'];saved=[]
        with patch.object(oa,'count_input_tokens',return_value={'response':{'object':'response.input_tokens','input_tokens':n},'http_status':200,'response_sha256':'0'*64}):
            receipt=oa.authoritative_input_count_guard(self.scope,payload,base.KEY,slot,persist=lambda *args:saved.append(args))
        self.assertEqual(len(saved),1)
        self.addCleanup(oa._issued_counts.pop,receipt['receipt_id'],None)
        return receipt

    def verify(self,receipt,payload=None,scope=None,slot=None):
        return oa.verify_count_receipt(scope or self.scope,payload or self.payload(),receipt,slot or self.scope['slots'][0]['id'])

    def reject_mutation(self,field,value):
        receipt=self.receipt();receipt[field]=value
        with self.assertRaises(ValueError):self.verify(receipt)

    def test_01_endpoint_frozen(self):
        self.assertEqual(oa.COUNT_ENDPOINT,'https://api.openai.com/v1/responses/input_tokens')
        for endpoint in ('https://api.openai.com/v1/responses','https://example.invalid/count'):
            with self.assertRaises(ValueError):oa.validate_count_policy(dict(self.scope,count_endpoint=endpoint))
        self.count()

    def test_02_same_model(self):
        for model in oa.MODELS:
            payload=self.payload(model);self.assertEqual(json.loads(oa.build_count_payload(payload))['model'],model)

    def test_03_same_input_and_supported_controls(self):
        payload=self.payload();count=json.loads(oa.build_count_payload(payload));value=json.loads(payload)
        self.assertEqual(count,{k:v for k,v in value.items() if k in oa.COUNT_FIELDS})
        for key in ('instructions','conversation','previous_response_id','stream','max_output_tokens','store','background','service_tier','prompt_cache_options','include'):
            self.assertNotIn(key,count)
        for key in ('input','model','reasoning','text','tools','tool_choice','parallel_tool_calls','truncation'):
            self.assertEqual(count[key],value[key])

    def test_04_generation_hash(self):self.reject_mutation('generation_payload_sha256','f'*64)
    def test_05_messages_hash(self):self.reject_mutation('messages_sha256','f'*64)

    def test_06_under_limit_allows_generation_once(self):
        receipt=self.receipt(100)
        with patch.object(pt,'worker_exchange',return_value='MOCK') as worker:
            self.assertEqual(self.adapter.exchange(self.scope,self.payload(),base.KEY,lambda e:None,[],count_receipt=receipt,slot_id=self.scope['slots'][0]['id']),'MOCK')
            with self.assertRaises(ValueError):self.adapter.exchange(self.scope,self.payload(),base.KEY,lambda e:None,[],count_receipt=receipt,slot_id=self.scope['slots'][0]['id'])
            self.assertEqual(worker.call_count,1)

    def test_07_equal_limit_allows(self):self.verify(self.receipt(28672))
    def test_08_over_limit_rejects(self):
        with self.assertRaisesRegex(ValueError,'INPUT_TOKEN_LIMIT_EXCEEDED'):self.receipt(28673)
    def test_09_negative(self):
        with self.assertRaisesRegex(ValueError,'INPUT_COUNT_UNKNOWN_OR_FAILED'):self.count(-1)
    def test_10_missing_count(self):
        with self.assertRaisesRegex(ValueError,'INPUT_COUNT_UNKNOWN_OR_FAILED'):self.count(wire=b'{"object":"response.input_tokens"}')
    def test_11_wrong_object(self):
        with self.assertRaisesRegex(ValueError,'INPUT_COUNT_UNKNOWN_OR_FAILED'):self.count(wire=b'{"object":"response","input_tokens":1}')
    def test_12_invalid_json(self):
        for wire in (b'{',b'null',b'[]',b'{"object":"response.input_tokens","input_tokens":NaN}',b'{"object":"response.input_tokens","input_tokens":1,"input_tokens":2}'):
            with self.subTest(wire=wire),self.assertRaisesRegex(ValueError,'INPUT_COUNT_UNKNOWN_OR_FAILED'):self.count(wire=wire)
    def test_13_http_error(self):
        for status in (301,400,401,429,500):
            with self.subTest(status=status),self.assertRaisesRegex(ValueError,'INPUT_COUNT_UNKNOWN_OR_FAILED'):self.count(status=status)
    def test_14_timeout(self):
        with self.assertRaisesRegex(ValueError,'INPUT_COUNT_UNKNOWN_OR_FAILED'):self.count(error=TimeoutError())

    def journal_failure(self,error='INPUT_COUNT_UNKNOWN_OR_FAILED',count=None):
        store,h,chat,slot=self.chat();sent=[]
        def transport(*args):sent.append(args);raise AssertionError('GENERATION_AFTER_FAILED_COUNT')
        kwargs={'side_effect':ValueError(error)} if count is None else {'return_value':{'response':{'object':'response.input_tokens','input_tokens':count},'http_status':200,'response_sha256':'0'*64}}
        with patch.object(oa,'count_input_tokens',**kwargs) as counter:
            with self.assertRaisesRegex(ValueError,error):
                chat.send_text(slot['user_text'],'failed-count',slot_id=slot['id'],transport=transport,credential_reader=lambda:base.KEY)
            with self.assertRaises(Exception):
                chat.send_text(slot['user_text'],'failed-count',slot_id=slot['id'],transport=transport,credential_reader=lambda:base.KEY)
            self.assertEqual(counter.call_count,1)
        self.assertFalse(sent)
        self.assertEqual(store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0],0)
        self.assertEqual(store.db.execute('SELECT stopped FROM call_batches').fetchone()[0],1)
        self.assertEqual(store.db.execute('SELECT count(*) FROM provider_input_counts').fetchone()[0],1)
        return store,h,chat,slot

    def test_15_no_count_retry(self):self.journal_failure()
    def test_16_no_generation_without_receipt(self):
        with patch.object(pt,'worker_exchange') as worker,self.assertRaisesRegex(ValueError,'INPUT_COUNT_RECEIPT_REQUIRED'):
            self.adapter.exchange(self.scope,self.payload(),base.KEY,lambda e:None,[])
        worker.assert_not_called()
    def test_17_stale_receipt(self):self.reject_mutation('timestamp',(datetime.now(timezone.utc)-timedelta(seconds=601)).isoformat())
    def test_18_altered_input(self):
        receipt=self.receipt();value=json.loads(self.payload());value['input'][0]['content']='altered'
        with self.assertRaisesRegex(ValueError,'INPUT_COUNT_PAYLOAD_IDENTITY_MISMATCH'):self.verify(receipt,pc.canonical(value))
    def test_19_altered_model(self):
        with self.assertRaisesRegex(ValueError,'INPUT_COUNT_PAYLOAD_IDENTITY_MISMATCH'):self.verify(self.receipt(),self.payload(oa.MODELS[1]))
    def test_20_altered_scope_source(self):
        for key,value in [('source_binding',{}),('batch_id','another')]:
            with self.assertRaisesRegex(ValueError,'INPUT_COUNT_PAYLOAD_IDENTITY_MISMATCH'):self.verify(self.receipt(),scope=dict(self.scope,**{key:value}))
    def test_21_other_slot(self):
        with self.assertRaisesRegex(ValueError,'INPUT_COUNT_PAYLOAD_IDENTITY_MISMATCH'):self.verify(self.receipt(),slot=self.scope['slots'][1]['id'])
    def test_22_preflight_no_network(self):
        from formal_binding_preflight import successor_preflight
        with patch.object(oa,'count_input_tokens',side_effect=AssertionError('COUNT_FORBIDDEN')) as c,patch.object(oa,'http_exchange',side_effect=AssertionError('GENERATION_FORBIDDEN')) as g:
            result=successor_preflight(self.config,self.transport,self.route,authorization_file=self.auth,pricing_file=self.price)
        self.assertEqual(result['status'],'READY');c.assert_not_called();g.assert_not_called()
        for name in ('provider_call_invocations','token_count_request_invocations','generation_request_invocations'):self.assertEqual(result[name],0)
    def test_23_count_failure_no_generation_reserve(self):
        store,h,chat,slot=self.journal_failure();ledger=p.ProviderJournal(store).summary(self.scope['batch_id'])
        self.assertEqual(ledger['token_count_requests'],1);self.assertEqual(ledger['generation_requests'],0);self.assertEqual(ledger['reserved_cny'],0)
    def test_24_no_fallback(self):
        for key,value in [('endpoint','https://example.invalid/responses'),('network_route_policy',{'mode':'PROXY'})]:
            with self.assertRaises(ValueError):oa.validate_count_policy(dict(self.scope,**{key:value}))
    def test_25_generation_retry_zero(self):
        self.assertEqual(self.scope['automatic_paid_retries'],0)
        with self.assertRaises(ValueError):p.scope_check(dict(self.scope,automatic_paid_retries=1))
    def test_26_boolean_float_null_rejected(self):
        for n in (True,False,1.0,None,'1'):
            with self.assertRaisesRegex(ValueError,'INPUT_COUNT_UNKNOWN_OR_FAILED'):self.count(n)
    def test_27_count_request_mutation(self):
        payload=self.payload();value=json.loads(oa.build_count_payload(payload));value['input'][0]['content']='changed'
        with self.assertRaises(ValueError):oa.validate_count_payload(pc.canonical(value),payload)
    def test_28_count_hash(self):self.reject_mutation('count_request_sha256','f'*64)
    def test_29_count_disconnect(self):
        with self.assertRaisesRegex(ValueError,'INPUT_COUNT_UNKNOWN_OR_FAILED'):self.count(error=ConnectionResetError())
    def test_30_success_records_two_calls(self):
        store,h,chat,slot,result,shown,transport=self.send();ledger=p.ProviderJournal(store).summary(self.scope['batch_id'])
        self.assertEqual(ledger['token_count_requests'],1);self.assertEqual(ledger['generation_requests'],1)
        self.assertEqual(ledger['count_billed_amount'],'UNKNOWN');self.assertFalse(ledger['count_billing_certified'])
    def test_31_over_limit_persists_receipt(self):
        store,*_=self.journal_failure('INPUT_TOKEN_LIMIT_EXCEEDED',28673)
        row=store.db.execute('SELECT receipt_json FROM provider_input_counts').fetchone();self.assertEqual(json.loads(row[0])['input_tokens'],28673)
    def test_32_count_persist_crash_no_resend(self):
        store,h,chat,slot=self.chat();turn=store.begin_turn(h,slot['user_text'],'count-crash');context=chat.build_request_context(turn['turn_id'])
        with patch.object(oa,'count_input_tokens',side_effect=SystemExit('OFFLINE_CRASH')) as counter:
            with self.assertRaises(SystemExit):p.ProviderJournal(store).call(h,turn['turn_id'],self.scope['batch_id'],slot['id'],context,credential_reader=lambda:base.KEY)
        self.assertEqual(counter.call_count,1)
        root=store.root;sid=h.session_id;store.close();restored=base.TranscriptStore(root);self.addCleanup(restored.close)
        rh=restored.resume(self.scope['principal_id'],sid)
        with patch.object(oa,'count_input_tokens') as counter,self.assertRaisesRegex(ValueError,'INPUT_COUNT_SLOT_ALREADY_CONSUMED'):
            p.ProviderJournal(restored).call(rh,turn['turn_id'],self.scope['batch_id'],slot['id'],context,credential_reader=lambda:base.KEY)
        counter.assert_not_called();self.assertEqual(restored.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0],0)
    def test_33_mock_not_runtime_receipt(self):self.reject_mutation('origin','PREFLIGHT_MOCK')
    def test_34_unissued_receipt_rejects(self):self.reject_mutation('receipt_id','forged')
    def test_35_worker_guard(self):
        receipt=self.receipt();oa.verify_worker_count(self.payload(),receipt)
        value=json.loads(self.payload());value['input'][0]['content']='changed'
        with self.assertRaises(ValueError):oa.verify_worker_count(pc.canonical(value),receipt)
        with self.assertRaises(ValueError):oa.validate_receipt_shape(None)
    def test_36_count_zero_valid(self):self.assertEqual(self.count(0)['response']['input_tokens'],0)
    def test_37_old_scope_immutable(self):
        self.assertEqual(pc.HISTORICAL_LOCAL_FORMAL_SCOPE_VERSION,'apcore-provider-scope-7')
        self.assertEqual(pc.FORMAL_SCOPE_VERSION,'apcore-provider-scope-8')
        with self.assertRaises(ValueError):oa.validate_count_policy(dict(self.scope,schema_version='apcore-provider-scope-7'))

    def test_38_count_persist_reserve_generation_order(self):
        store,h,chat,slot=self.chat();order=[]
        def count(scope,payload,key):
            self.assertEqual(store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0],0)
            self.assertEqual(store.db.execute('SELECT status FROM provider_input_counts').fetchone()[0],'SUBMITTED_STATUS_UNKNOWN')
            order.append('COUNT');return {'response':{'object':'response.input_tokens','input_tokens':100},'http_status':200,'response_sha256':'0'*64}
        def transport(payload,key):
            row=store.db.execute('SELECT * FROM provider_input_counts').fetchone()
            self.assertEqual(row['status'],'COUNTED');self.assertTrue(row['receipt_json'])
            self.assertEqual(store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0],1)
            order.append('GENERATION');w=base.wire();return pt.TransportResult(200,oa.decode_http(w,200),w)
        with patch.object(oa,'count_input_tokens',side_effect=count):
            chat.send_text(slot['user_text'],'ordering',slot_id=slot['id'],transport=transport,credential_reader=lambda:base.KEY,display=lambda text:None)
        self.assertEqual(order,['COUNT','GENERATION'])

if __name__=='__main__':unittest.main(verbosity=2)
