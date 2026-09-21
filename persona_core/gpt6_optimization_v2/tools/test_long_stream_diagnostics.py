"""Authored in-memory HTTP framing and owned-worker faults. No provider traffic."""
from __future__ import annotations
import base64
import copy
import http.client
import io
import json
import ssl
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
CODE=ROOT/'persona_core/operational_runtime_v1'
sys.path[:0]=[str(CODE),str(ROOT/'persona_core/operational_build_v1/tools')]
import provider
import provider_transport as pt
import test_responses_provider_integration as fixtures
import test_responses_terminal_classification as terminal
from transcript_store import StoreGuard

POLICY=fixtures.POLICY
HTTP_EXCHANGE=pt.responses_http_exchange
SECRET='AUTHORED_SECRET_URL_QUERY_AND_PROMPT'
PARTIAL=fixtures.responses_wire().split(b'event: response.completed')[0]

class FaultResponse(fixtures.Response):
    def __init__(self,wire,error=None):super().__init__(wire);self.error=error
    def read1(self,n):
        data=super().read1(n)
        if not data and self.error:raise self.error
        return data

def exchange(wire=PARTIAL,error=None,sink=lambda e:None,response=None):
    class Opener:
        def open(self,*a,**k):return response if response is not None else FaultResponse(wire,error)
    return HTTP_EXCHANGE(b'{"stream":true}','DUMMY',POLICY,sink,opener_factory=lambda life:Opener())

class FakeSocket:
    def __init__(self,wire):self.wire=wire
    def makefile(self,*a,**k):return io.BytesIO(self.wire)

def chunk_response(body,ending=b'0\r\n\r\n',cut_payload=False):
    chunk=format(len(body)+(1 if cut_payload else 0),'x').encode()+b'\r\n'+body
    if not cut_payload:chunk+=b'\r\n'+ending
    response=http.client.HTTPResponse(FakeSocket(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n'+chunk))
    response.begin();return response

class DiagnosticsTests(unittest.TestCase):
    def fault(self,*args,**kwargs):
        with self.assertRaises(pt.TransportFault) as caught:exchange(*args,**kwargs)
        return caught.exception
    def test_distinguishes_real_exception_classes_without_text(self):
        errors=[http.client.RemoteDisconnected(SECRET),http.client.IncompleteRead(SECRET.encode()),
                ConnectionResetError(10054,SECRET),ssl.SSLError(1,SECRET),ssl.SSLEOFError(8,SECRET),
                EOFError(SECRET),http.client.HTTPException(SECRET)]
        for error in errors:
            with self.subTest(kind=type(error).__name__):
                observed=[];fault=self.fault(error=error,sink=observed.append)
                self.assertEqual(fault.reason,'TRANSPORT_PROTOCOL_OR_CONNECTION_ERROR')
                self.assertEqual(fault.diagnostics['reason_class'],type(error).__name__)
                self.assertEqual(fault.diagnostics['operation'],'HTTP_READ1')
                self.assertEqual(fault.wire,PARTIAL)
                self.assertEqual(observed[-1]['diagnostics'],fault.diagnostics)
                self.assertNotIn(SECRET,json.dumps(observed)+str(fault))
    def test_wrapped_errno_and_winerror_are_bounded(self):
        error=ConnectionResetError(10054,SECRET);error.winerror=10054
        fault=self.fault(error=urllib.error.URLError(error))
        self.assertEqual(fault.diagnostics['exception_class'],'URLError')
        self.assertEqual(fault.diagnostics['reason_class'],'ConnectionResetError')
        self.assertEqual((fault.diagnostics['errno'],fault.diagnostics['winerror']),(10054,10054))
    def test_unknown_exception_class_does_not_leak_class_name(self):
        error=type(SECRET,(Exception,),{})(SECRET)
        fault=self.fault(error=error)
        self.assertEqual(fault.diagnostics['exception_class'],'OTHER')
        self.assertNotIn(SECRET,json.dumps(fault.diagnostics))
    def test_timeout_mapping_and_phase_are_unchanged(self):
        fault=self.fault(error=TimeoutError(SECRET))
        self.assertEqual(fault.reason,'INACTIVITY_TIMEOUT')
        self.assertEqual(fault.diagnostics['phase'],'stream')
    def test_clean_eof_without_terminal_is_normalize_error(self):
        events=[];fault=self.fault(sink=events.append)
        self.assertEqual(fault.diagnostics['exception_class'],'StoreGuard')
        self.assertEqual(fault.diagnostics['operation'],'NORMALIZE')
        self.assertIn('last_response_byte',[e['event'] for e in events])
    def test_malformed_sse_is_distinct_from_socket_read(self):
        fault=self.fault(b'data: invalid-json\n\n')
        self.assertEqual(fault.diagnostics['exception_class'],'JSONDecodeError')
        self.assertEqual(fault.diagnostics['operation'],'SSE_FEED')
    def test_missing_chunk_terminator_preserves_complete_sse_frame(self):
        events=[];fault=self.fault(response=chunk_response(PARTIAL,ending=b''),sink=events.append)
        self.assertEqual(fault.wire,PARTIAL)
        self.assertEqual(fault.diagnostics['reason_class'],'IncompleteRead')
        self.assertIs(fault.diagnostics['http_chunked'],True)
        self.assertNotIn('last_response_byte',[e['event'] for e in events])
    def test_malformed_chunk_size_is_not_promoted_to_normal_eof(self):
        fault=self.fault(response=chunk_response(PARTIAL,ending=b'XYZ\r\n'))
        self.assertEqual(fault.diagnostics['reason_class'],'IncompleteRead')
        self.assertEqual(fault.wire,PARTIAL)
    def test_truncated_chunk_payload_is_unknown(self):
        fault=self.fault(response=chunk_response(PARTIAL,cut_payload=True))
        self.assertEqual(fault.diagnostics['reason_class'],'IncompleteRead')
        self.assertEqual(fault.wire,PARTIAL)
    def test_valid_chunked_completion_unchanged(self):
        result=exchange(response=chunk_response(fixtures.responses_wire()))
        self.assertEqual(result.body,fixtures.normalized())
    def test_keepalive_crlf_multiline_data_utf8_single_byte_feed(self):
        body=fixtures.normalized();values=fixtures.records()
        wire=b': keep-alive\r\n\r\n'
        for value in values:
            # Split a JSON object at a legal whitespace boundary into two data lines.
            data=pt.encode(value);cut=data.index(b',')+1
            wire+=b'event: '+value['type'].encode()+b'\r\n: heartbeat\r\n'
            wire+=b'data: '+data[:cut]+b'\r\ndata: '+data[cut:]+b'\r\n\r\n'
        assembly=pt.ResponsesAssembly(pt.Lifecycle())
        for byte in wire:assembly.feed(bytes([byte]))
        self.assertEqual(assembly.body(),body)
    def test_partial_terminal_frame_never_accepted(self):
        for data in (fixtures.responses_wire()[:-1],fixtures.responses_wire()[:-20]):
            self.fault(data)
    def test_reasoning_milestone_does_not_become_visible_token(self):
        values=fixtures.records()[:1]+[{'type':'response.reasoning_text.delta','sequence_number':1,'delta':'authored'}]
        events=[];self.fault(fixtures.wire_records(values),sink=events.append)
        names=[e['event'] for e in events]
        self.assertEqual(names.count('first_reasoning_token'),1)
        self.assertNotIn('first_token',names)
    def test_diagnostics_schema_rejects_untrusted_values(self):
        good=self.fault(error=EOFError()).diagnostics
        bads=[{**good,'extra':SECRET},{**good,'exception_class':SECRET},{**good,'phase':SECRET},
              {**good,'operation':SECRET},{**good,'http_chunked':1},{**good,'errno':True},
              {**good,'winerror':2**31},{**good,'errno':SECRET},{**good,'version':'unrecognized'}]
        for bad in bads:
            with self.subTest(bad=sorted(bad)):
                with self.assertRaises(StoreGuard):pt.validate_diagnostics(bad)
    def test_telemetry_diagnostics_only_on_error_and_under_pipe_line_bound(self):
        good=self.fault(error=EOFError()).diagnostics
        event={'event':'worker_error','elapsed_ms':0,'diagnostics':good}
        pt.check_event(event)
        self.assertLess(len(pt.encode({'frame_sha256':'0'*64,'lifecycle':event}))+1,2048)
        with self.assertRaises(StoreGuard):pt.check_event({**event,'event':'worker_terminal'})
    def test_legacy_chat_lifecycle_preserves_same_error_details(self):
        class Opener:
            def open(self,*a,**k):return FaultResponse(b' ',ConnectionResetError(10054,SECRET))
        with self.assertRaises(pt.TransportFault) as caught:
            pt.http_exchange(b'{"stream":false}','DUMMY',POLICY,opener_factory=lambda life:Opener())
        self.assertEqual(caught.exception.diagnostics['reason_class'],'ConnectionResetError')

class ReceiptTests(unittest.TestCase):
    def child(self,script):
        return [sys.executable,'-X','utf8','-B','-c',script]
    def test_real_worker_error_details_reach_parent(self):
        script=("import sys;sys.path[:0]="+repr([str(CODE),str(Path(__file__).parent)])+";"
          "import provider_transport as p,provider_http_worker as w;from test_long_stream_diagnostics import exchange;"
          "p.responses_http_exchange=lambda payload,key,policy,sink:exchange(error=ConnectionResetError(10054,'SECRET'),sink=sink);"
          "raise SystemExit(w.main())")
        events=[]
        with self.assertRaises(pt.TransportFault) as caught:
            pt.worker_exchange(b'{"stream":true}','DUMMY',5,POLICY,self.child(script),ROOT,events.append,responses=True)
        self.assertEqual(caught.exception.wire,PARTIAL)
        self.assertEqual(caught.exception.diagnostics['reason_class'],'ConnectionResetError')
        self.assertEqual(events[-1]['event'],'parent_receipt')
        self.assertNotIn('SECRET',json.dumps(events))
    def receipt_script(self,diagnostics=None,include=False):
        data={'kind':'unknown','status':200,'reason':'TRANSPORT_PROTOCOL_OR_CONNECTION_ERROR',
              'wire':base64.b64encode(PARTIAL).decode()}
        if include:data['diagnostics']=diagnostics
        return ("import sys,json,hashlib;sys.path.insert(0,"+repr(str(CODE))+");import provider_transport as p;"
                "raw=sys.stdin.buffer.read();r="+repr(data)+";r['frame_sha256']=hashlib.sha256(raw).hexdigest();"
                "sys.stdout.buffer.write(p.RESULT_HEADER+p.encode(r))")
    def test_old_unknown_receipt_without_diagnostics_remains_readable(self):
        with self.assertRaises(pt.TransportFault) as caught:
            pt.worker_exchange(b'{}','DUMMY',5,POLICY,self.child(self.receipt_script()),ROOT)
        self.assertEqual(caught.exception.wire,PARTIAL)
        self.assertIsNone(caught.exception.diagnostics)
    def test_invalid_diagnostic_receipt_is_fail_closed(self):
        for bad in (None,{'exception_text':SECRET}):
            with self.assertRaises(pt.TransportFault) as caught:
                pt.worker_exchange(b'{}','DUMMY',5,POLICY,self.child(self.receipt_script(bad,True)),ROOT)
            self.assertEqual(caught.exception.reason,'PROCESS_EXIT_UNKNOWN')
            self.assertIsNone(caught.exception.diagnostics)

class JournalDiagnosticsTests(unittest.TestCase):
    setUp=terminal.TerminalJournalTests.setUp
    tearDown=terminal.TerminalJournalTests.tearDown
    def test_journal_preserves_diagnostics_unknown_reserve_and_no_replay(self):
        def worker(*args,**kwargs):
            self.assertEqual(self.store.db.execute('select status from provider_calls').fetchone()[0],
                             'SUBMITTED_STATUS_UNKNOWN')
            return exchange(error=ConnectionResetError(10054,SECRET))
        with patch.object(provider.lifecycle_transport,'worker_exchange',worker):
            row=self.journal.call(self.handle,self.turn['turn_id'],self.scope['batch_id'],'one',self.context,
                                  credential_reader=lambda:'DUMMY')
        self.assertEqual(row['status'],'SUBMITTED_STATUS_UNKNOWN')
        detail=json.loads(self.store.db.execute('select detail_json from turn_lifecycle order by seq desc').fetchone()[0])
        self.assertEqual(detail['transport_diagnostics']['reason_class'],'ConnectionResetError')
        self.assertFalse(detail['remote_outcome_known']);self.assertEqual(detail['automatic_paid_retries'],0)
        cap=self.store.db.execute('select * from transport_wire_captures').fetchone()
        self.assertEqual(bytes(cap['wire_bytes']),PARTIAL);self.assertEqual(cap['complete'],0)
        self.assertIsNone(row['usage_json']);self.assertGreater(row['reserve_micro_cny'],0)
        with patch.object(provider.lifecycle_transport,'worker_exchange',side_effect=AssertionError('REPLAY')):
            repeat=self.journal.call(self.handle,self.turn['turn_id'],self.scope['batch_id'],'one',self.context,
                                     credential_reader=lambda:self.fail('CREDENTIAL_REREAD'))
        self.assertEqual(row,repeat)
        self.assertEqual(self.store.db.execute('select count(*) from provider_calls').fetchone()[0],1)
        self.assertEqual(self.store.db.execute('select stopped from call_batches').fetchone()[0],1)
        self.assertNotIn(SECRET,json.dumps(detail))

if __name__=='__main__':unittest.main(verbosity=2)
