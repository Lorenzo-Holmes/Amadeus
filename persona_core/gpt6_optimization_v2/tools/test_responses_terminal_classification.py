"""Terminal certainty, usability and non-replay invariants on authored fixtures."""
from __future__ import annotations
import copy
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
CODE=ROOT/'persona_core/operational_runtime_v1'
sys.path[:0]=[str(CODE),str(ROOT/'persona_core/operational_build_v1/tools')]
import provider
import provider_transport as pt
from chat import ChatService
import test_provider_v2_r047 as old
from test_responses_provider_integration import POLICY,Response,normalized
from responses_terminal_fixtures import KINDS,REASONING,VISIBLE,events,wire,encode_events

REJECTED='RESPONSE_REJECTED_TERMINAL_KNOWN'
HTTP_EXCHANGE=pt.responses_http_exchange

def exchange(data, sink=lambda e:None):
    class Opener:
        def __init__(self,lifecycle):pass
        def open(self,*a,**k):return Response(data)
    return HTTP_EXCHANGE(pt.encode({'stream':True}),'DUMMY',POLICY,sink,opener_factory=Opener)

class TerminalTransportTests(unittest.TestCase):
    def test_completed_reasoning_and_visible_text_accepted(self):
        result=exchange(wire('completed_text'));body=json.loads(result.body)
        self.assertEqual(body['choices'][0]['message']['content'],VISIBLE)
        self.assertNotIn(REASONING,result.body.decode())
        self.assertNotIn('responses_terminal_rejection',body)

    def test_completed_reasoning_only_is_known_rejected(self):
        observed=[];result=exchange(wire('reasoning_only'),observed.append);body=json.loads(result.body)
        self.assertEqual(body['responses_terminal_rejection']['reason'],'RESPONSES_COMPLETED_NO_VISIBLE_OUTPUT')
        self.assertEqual(body['usage']['completion_tokens'],20)
        self.assertIn('worker_terminal',[e['event'] for e in observed])
        self.assertNotIn('worker_error',[e['event'] for e in observed])
        self.assertEqual(body['choices'][0]['message']['content'],'')

    def test_completed_empty_message_rejected(self):
        body=json.loads(exchange(wire('empty_message')).body)
        self.assertEqual(body['responses_terminal_rejection']['reason'],'RESPONSES_COMPLETED_NO_VISIBLE_OUTPUT')

    def test_incomplete_max_output_tokens_is_known_rejected(self):
        body=json.loads(exchange(wire('incomplete')).body)
        self.assertEqual(body['responses_terminal_rejection']['incomplete_reason'],'max_output_tokens')
        self.assertEqual(body['responses_terminal_rejection']['reason'],'RESPONSES_INCOMPLETE')
        self.assertEqual(body['choices'][0]['message']['content'],'')
        self.assertEqual(body['choices'][0]['finish_reason'],'length')

    def test_failed_without_usage_output_or_details_is_known_rejected(self):
        value=events('failed');value[-1]['response'].pop('usage');value[-1]['response'].pop('output')
        body=json.loads(exchange(encode_events(value)).body)
        self.assertEqual(body['responses_terminal_rejection']['reason'],'RESPONSES_FAILED')
        self.assertIsNone(body['usage'])

    def test_stream_disconnect_before_terminal_is_unknown(self):
        with self.assertRaises(pt.TransportFault) as error:exchange(wire('disconnect'))
        self.assertEqual(error.exception.wire,wire('disconnect'))

    def test_terminal_after_malformed_sequence_is_unknown(self):
        with self.assertRaises(pt.TransportFault):exchange(wire('malformed_sequence'))

    def test_reasoning_token_accounting_does_not_invent_or_require_reasoning_text(self):
        body=json.loads(exchange(wire('tokens_without_reasoning_text')).body)
        self.assertEqual(body['usage']['completion_tokens_details']['reasoning_tokens'],12)
        self.assertEqual(body['choices'][0]['message']['content'],VISIBLE)
        self.assertNotIn('responses_terminal_rejection',body)

    def test_visible_output_with_bad_usage_is_known_rejected(self):
        body=json.loads(exchange(wire('bad_usage')).body)
        self.assertEqual(body['responses_terminal_rejection']['reason'],'RESPONSES_USAGE')
        self.assertIsNone(body['usage']);self.assertEqual(body['choices'][0]['message']['content'],'')

    def test_content_filter_incomplete_is_known_not_a_reply(self):
        value=events('incomplete');value[-1]['response']['incomplete_details']['reason']='content_filter'
        body=json.loads(exchange(encode_events(value)).body)
        self.assertEqual(body['choices'][0]['finish_reason'],'content_filter')
        self.assertEqual(body['responses_terminal_rejection']['reason'],'RESPONSES_INCOMPLETE')

    def test_completed_with_provider_error_or_incomplete_details_is_rejected(self):
        for field in ('error','incomplete_details'):
            value=events('completed_text');value[-1]['response'][field]={'reason':'authored'}
            with self.subTest(field=field):
                body=json.loads(exchange(encode_events(value)).body)
                self.assertIn('responses_terminal_rejection',body)

    def test_unrecognized_or_refusal_output_is_never_promoted(self):
        value=events('reasoning_only');value[-1]['response']['output'].append({'type':'message','role':'assistant','content':[{'type':'refusal','refusal':'authored refusal'}]})
        body=json.loads(exchange(encode_events(value)).body)
        self.assertIn('responses_terminal_rejection',body)
        self.assertEqual(body['choices'][0]['message']['content'],'')

    def test_worker_ipc_preserves_known_rejection(self):
        child=("import sys;sys.path[:0]="+repr([str(CODE),str(Path(__file__).parent)])+";"
               "import provider_transport as p,provider_http_worker as w;"
               "from test_responses_terminal_classification import exchange;"
               "from responses_terminal_fixtures import wire;"
               "p.responses_http_exchange=lambda payload,key,policy,sink:exchange(wire('reasoning_only'),sink);"
               "raise SystemExit(w.main())")
        result=pt.worker_exchange(pt.encode({'stream':True}),'DUMMY',5,POLICY,
            [sys.executable,'-X','utf8','-B','-c',child],ROOT,responses=True)
        pt.verify_responses_result(result)
        self.assertEqual(json.loads(result.body)['responses_terminal_rejection']['reason'],'RESPONSES_COMPLETED_NO_VISIBLE_OUTPUT')

    def test_parent_rejects_mismatched_receipt_as_unknown(self):
        result=exchange(wire('completed_text'));result.body=exchange(wire('reasoning_only')).body
        with self.assertRaises(pt.TransportFault):pt.verify_responses_result(result)

    def test_success_normalization_remains_byte_identical(self):
        expected={'id':'resp_authored_terminal','model':'deepseek-v4-pro','choices':[{'index':0,
            'message':{'role':'assistant','content':VISIBLE},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,
                     'prompt_cache_hit_tokens':10,'prompt_cache_miss_tokens':90,
                     'completion_tokens_details':{'reasoning_tokens':12}},'responses_api_status':'completed'}
        self.assertEqual(exchange(wire('completed_text')).body,pt.encode(expected))

class TerminalJournalTests(unittest.TestCase):
    def setUp(self):
        self.root=old.create_sandbox(old.OUT/('terminal_'+self._testMethodName))
        self.store=old.TranscriptStore(self.root);self.handle=self.store.open_session('OFFLINE_OPERATOR','A')
        self.journal=provider.ProviderJournal(self.store);self.scope=old.scope()
        self.scope.update(schema_version='apcore-provider-scope-4',endpoint=provider.RESPONSES_ENDPOINT,
            api_protocol='responses',stream=True,request_timeout_seconds=5,transport_policy=POLICY,
            capacity_policy_id='EXTENDED_MAX_REASONING_20260911',output_budget_includes_reasoning=True,
            automatic_capacity_escalation=False)
        self.journal.register_batch(self.scope)
        self.service=ChatService(self.store,self.handle,self.scope)
        self.turn=self.store.begin_turn(self.handle,'第一轮问题','one')
        self.context=old.build_context(self.store,self.handle,self.turn['turn_id'])
    def tearDown(self):self.store.close()
    def submit(self,kind):
        def worker(*args,**kwargs):
            with sqlite3.connect(self.root/'runtime.sqlite3') as db:
                self.assertEqual(db.execute('SELECT status FROM provider_calls').fetchone()[0],'SUBMITTED_STATUS_UNKNOWN')
            return exchange(wire(kind))
        with patch.object(provider.lifecycle_transport,'worker_exchange',worker):
            return self.journal.call(self.handle,self.turn['turn_id'],self.scope['batch_id'],'one',self.context,credential_reader=lambda:'DUMMY')
    def assert_rejected(self,row):
        self.assertEqual(row['status'],REJECTED)
        turn=self.store.get_turn(self.handle,self.turn['turn_id'])
        self.assertEqual(turn['status'],'RESPONSE_REJECTED');self.assertIsNone(turn['assistant_text'])
        self.assertIsNone(turn['display_at_utc'])
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM display_journal').fetchone()[0],0)
        self.assertEqual(self.store.db.execute('SELECT stopped FROM call_batches').fetchone()[0],1)
        capture=self.store.db.execute('SELECT * FROM transport_wire_captures').fetchone()
        self.assertEqual(capture['complete'],1)
        self.assertEqual(capture['wire_sha256'],hashlib.sha256(capture['wire_bytes']).hexdigest())
        detail=json.loads(self.store.db.execute('SELECT detail_json FROM turn_lifecycle WHERE state=?',(REJECTED,)).fetchone()[0])
        for k,v in {'remote_outcome_known':True,'response_usable':False,'semantic_verdict':None,
                    'batch_stopped':True,'automatic_paid_retries':0,'slot_consumed':True}.items():self.assertEqual(detail[k],v)
        summary=self.journal.summary(self.scope['batch_id'])
        self.assertEqual(summary['remote_outcome_unknown_count'],0);self.assertEqual(summary['terminal_known_rejected_count'],1)
    def test_reasoning_only_accounted_known_rejected(self):
        row=self.submit('reasoning_only');self.assert_rejected(row)
        self.assertEqual(row['error_category'],'RESPONSES_COMPLETED_NO_VISIBLE_OUTPUT')
        self.assertIsNotNone(row['estimate_peak_micro_cny']);self.assertGreater(row['estimate_peak_micro_cny'],0)
        self.assertNotIn(REASONING,json.dumps(old.build_context(self.store,self.handle,self.turn['turn_id'])))
        result=self.service.send_text('第一轮问题','one',slot_id='one',display=lambda _:self.fail('DISPLAY_FORBIDDEN'),
            credential_reader=lambda:self.fail('CREDENTIAL_REREAD_FORBIDDEN'))
        self.assertFalse(result['displayed_now']);self.assertIsNone(result['text'])
    def test_empty_message_known_rejected(self):self.assert_rejected(self.submit('empty_message'))
    def test_incomplete_known_rejected(self):
        row=self.submit('incomplete');self.assert_rejected(row);self.assertEqual(row['error_category'],'RESPONSES_INCOMPLETE')
    def test_failed_known_rejected(self):
        row=self.submit('failed');self.assert_rejected(row);self.assertEqual(row['error_category'],'RESPONSES_FAILED')
    def test_usage_malformed_known_but_not_zero_cost(self):
        row=self.submit('bad_usage');self.assert_rejected(row)
        self.assertIsNone(row['estimate_peak_micro_cny']);self.assertIsNone(row['usage_json'])
        summary=self.journal.summary(self.scope['batch_id'])
        self.assertFalse(summary['estimate_complete']);self.assertIsNone(summary['peak_usage_estimate_cny'])
        self.assertGreater(summary['reserved_cny'],0)
    def test_disconnect_stays_unknown(self):
        row=self.submit('disconnect');self.assertEqual(row['status'],'SUBMITTED_STATUS_UNKNOWN')
        self.assertEqual(self.journal.summary(self.scope['batch_id'])['remote_outcome_unknown_count'],1)
    def test_malformed_sequence_terminal_stays_unknown(self):
        row=self.submit('malformed_sequence');self.assertEqual(row['status'],'SUBMITTED_STATUS_UNKNOWN')
    def test_known_rejection_no_retry_same_turn_other_slot_or_restart(self):
        row=self.submit('reasoning_only')
        with patch.object(provider.lifecycle_transport,'worker_exchange',side_effect=AssertionError('RETRY_FORBIDDEN')):
            repeat=self.journal.call(self.handle,self.turn['turn_id'],self.scope['batch_id'],'one',self.context,
                credential_reader=lambda:self.fail('CREDENTIAL_REREAD_FORBIDDEN'))
            self.assertEqual(row,repeat)
            next_turn=self.store.begin_turn(self.handle,'第二轮问题','two')
            context=old.build_context(self.store,self.handle,next_turn['turn_id'])
            with self.assertRaisesRegex(ValueError,'stopped'):
                self.journal.call(self.handle,next_turn['turn_id'],self.scope['batch_id'],'two',context,credential_reader=lambda:'DUMMY')
        self.store.close();self.store=old.TranscriptStore(self.root);self.journal=provider.ProviderJournal(self.store)
        self.handle=self.store.resume('OFFLINE_OPERATOR',self.handle.session_id)
        self.assertEqual(self.journal.get_call(self.handle,row['call_id'])['status'],REJECTED)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0],1)
        self.assertEqual(self.store.db.execute('SELECT stopped FROM call_batches').fetchone()[0],1)

if __name__=='__main__':unittest.main(verbosity=2)
