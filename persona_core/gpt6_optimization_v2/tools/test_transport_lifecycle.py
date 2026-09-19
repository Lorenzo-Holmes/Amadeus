"""Synthetic transport faults, real child IPC and loopback HTTP. No provider use."""
import base64
import copy
import io
import json
import socket
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
CODE=ROOT/'persona_core/operational_runtime_v1'
sys.path[:0]=[str(CODE),str(ROOT/'persona_core/operational_build_v1/tools')]
import provider
import provider_transport as pt
import test_provider_v2_r047 as old
from transcript_store import StoreGuard

POLICY={'version':pt.VERSION,'connect_timeout_seconds':1,'read_timeout_seconds':1,'worker_deadline_seconds':4}
BODY=old.response(completion=6,reasoning=3)
BODY['choices'][0]['message']={'role':'assistant','content':'甲乙','reasoning_content':'abc'}
def sse(done=True,finish=True,usage=True):
    rows=[{'model':'deepseek-v4-pro','id':'synthetic','choices':[{'index':0,'delta':{'reasoning_content':'abc'},'finish_reason':None}]},
          {'model':'deepseek-v4-pro','id':'synthetic','choices':[{'index':0,'delta':{'content':'甲'},'finish_reason':None}]},
          {'model':'deepseek-v4-pro','id':'synthetic','choices':[{'index':0,'delta':{'content':'乙'},'finish_reason':None}]}]
    if finish:rows.append({'model':'deepseek-v4-pro','id':'synthetic','choices':[{'index':0,'delta':{},'finish_reason':'stop'}],**({'usage':BODY['usage']} if usage else {})})
    return b': keep-alive\n\n'+b''.join(b'data: '+pt.encode(r)+b'\n\n' for r in rows)+(b'data: [DONE]\n\n' if done else b'')

class Response:
    status=200
    def __init__(self,wire,status=200,error=None):self.reader=io.BytesIO(wire);self.status=status;self.error=error
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read1(self,n):
        data=self.reader.read(min(n,13))
        if not data and self.error:raise self.error
        return data

def exchange(wire,stream=True,status=200,error=None,open_error=None,policy=POLICY):
    events=[]
    class Opener:
        def __init__(self,lifecycle):self.lifecycle=lifecycle
        def open(self,*args,**kwargs):
            self.lifecycle.phase='connect'
            if open_error:raise open_error
            return Response(wire,status,error)
    try:result=pt.http_exchange(pt.encode({'stream':stream}),'DUMMY_PRIVATE',policy,events.append,opener_factory=Opener)
    except pt.TransportFault as exc:return exc,events
    return result,events

CHILD=r'''
import sys,json,io,time,os
sys.path.insert(0,sys.argv[1]);import provider_transport as pt,provider_http_worker as worker
mode=sys.argv[2]
if mode=='exit':sys.stdin.buffer.read();sys.exit(7)
if mode=='killed':sys.stdin.buffer.read();os._exit(9)
if mode=='hang':sys.stdin.buffer.read();time.sleep(10);sys.exit(0)
wire=__import__('base64').b64decode(sys.argv[3])
class Response:
 status=200
 def __init__(self):self.r=io.BytesIO(wire)
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def read1(self,n):return self.r.read(min(n,17))
class Opener:
 def __init__(self,t):self.t=t
 def open(self,*a,**k):
  for event in ('dns_started','dns_complete','tcp_started','tcp_connected','tls_started','tls_connected','request_write_started','request_write_complete','response_wait_started'):self.t.emit(event)
  self.t.emit('first_response_header',http_status=200)
  return Response()
original=pt.http_exchange
pt.http_exchange=lambda *a,**k:original(*a,**k,opener_factory=Opener)
sys.exit(worker.main())
'''
def command(mode='ok',wire=None):
    return [sys.executable,'-B','-c',CHILD,str(CODE),mode,base64.b64encode(wire if wire is not None else sse()).decode('ascii')]

class ProtocolTests(unittest.TestCase):
    def test_evaluation_scope_pins_transport_without_changing_generation(self):
        sys.path.insert(0,str(ROOT/'persona_core/gpt6_optimization_v2/tools'))
        import evaluation_runner as runner
        prices={'observation_date_local':'2026-09-18','sources':['AUTHORED'],
                'peak_rates_cny_per_million_tokens':{'deepseek-v4-pro':{'input_miss':9,'output':27,'input_hit':.3}}}
        suite={'slots':[{'id':'fixture','model':'deepseek-v4-pro','entity_label':'fixture','user_text':'synthetic'}]}
        before=runner.build_scope('test',suite,prices,'deepseek-v4-pro','deepseek-v4-pro',max_output_tokens=32768)
        after=runner.build_scope('test',suite,prices,'deepseek-v4-pro','deepseek-v4-pro',max_output_tokens=32768,transport_policy=POLICY)
        self.assertFalse(before['stream']);self.assertTrue(after['stream'])
        self.assertEqual(after['transport_policy'],POLICY)
        self.assertEqual({k:v for k,v in after.items() if k not in {'stream','transport_policy'}},
                         {k:v for k,v in before.items() if k!='stream'})
    def test_stream_framing_can_exceed_normalized_body_bound(self):
        chunk=pt.encode({'id':'synthetic','model':'deepseek-v4-pro','choices':[{'index':0,'delta':{'content':'x'},'finish_reason':None}]})
        wire=(b'data: '+chunk+b'\n\n')*12000+sse()
        self.assertGreater(len(wire),pt.MAX_BODY)
        result,_=exchange(wire)
        self.assertIsInstance(result,pt.TransportResult)
        self.assertEqual(len(json.loads(result.body)['choices'][0]['message']['content']),12002)
        self.assertEqual(result.wire,wire)
    def test_stream_wire_bound_remains_finite_and_unknown_on_overflow(self):
        with patch.object(pt,'MAX_WIRE',64):
            result,_=exchange(sse())
        self.assertIsInstance(result,pt.TransportFault)
    def test_normal_nonstream_http_completion(self):
        result,events=exchange(pt.encode(BODY),stream=False)
        self.assertEqual(json.loads(result.body),BODY)
        self.assertNotIn('first_token',[e['event'] for e in events])
    def test_stream_reconstruction_all_bytes_usage_finish(self):
        wire=sse();result,events=exchange(wire)
        body=json.loads(result.body)
        self.assertEqual(body['choices'][0]['message'],BODY['choices'][0]['message'])
        self.assertEqual(body['usage'],BODY['usage']);self.assertEqual(result.wire,wire)
        self.assertEqual(body['choices'][0]['finish_reason'],'stop')
        self.assertIn('first_token',[e['event'] for e in events])
    def test_partial_stream_disconnect_is_unknown(self):
        result,_=exchange(sse(done=False),error=ConnectionResetError('PRIVATE_MESSAGE'))
        self.assertIsInstance(result,pt.TransportFault);self.assertEqual(result.wire,sse(done=False))
    def test_connect_timeout_is_identified(self):
        result,_=exchange(b'',open_error=urllib.error.URLError(TimeoutError('SECRET')))
        self.assertEqual(result.reason,'CONNECT_TIMEOUT')
    def test_read_timeout_is_identified(self):
        result,_=exchange(b' ',stream=False,error=TimeoutError('SECRET'))
        self.assertEqual(result.reason,'READ_TIMEOUT')
    def test_streaming_inactivity_is_identified(self):
        result,_=exchange(sse(done=False),error=TimeoutError('SECRET'))
        self.assertEqual(result.reason,'INACTIVITY_TIMEOUT')
    def test_worker_deadline_is_identified(self):
        policy={**POLICY,'worker_deadline_seconds':.001}
        class Slow:
            def open(self,*a,**k):time.sleep(.05);raise TimeoutError()
        with self.assertRaises(pt.TransportFault) as caught:
            pt.http_exchange(b'{}','DUMMY',policy,opener_factory=lambda t:Slow())
        self.assertEqual(caught.exception.reason,'WORKER_DEADLINE')
    def test_http_4xx_terminal(self):
        result,events=exchange(b'{"error":"authored"}',status=401)
        self.assertEqual(result.status,401);self.assertIn('http_terminal',[e['event'] for e in events])
    def test_http_5xx_terminal(self):
        result,_=exchange(b'authored',status=503);self.assertEqual(result.status,503)
    def test_malformed_response_is_unknown(self):
        result,_=exchange(b'data: broken\n\n');self.assertIsInstance(result,pt.TransportFault)
    def test_missing_finish_marker_is_unknown(self):
        for wire in (sse(done=False),sse(finish=False),b''):
            self.assertIsInstance(exchange(wire)[0],pt.TransportFault)
        body=copy.deepcopy(BODY);body['choices'][0]['finish_reason']=None
        self.assertIsInstance(exchange(pt.encode(body),stream=False)[0],pt.TransportFault)
    def test_done_stops_read_without_waiting_for_socket_eof(self):
        result,_=exchange(sse(),error=TimeoutError('would hang after DONE'))
        self.assertIsInstance(result,pt.TransportResult)
    def test_usage_absence_remains_explicit(self):
        result,_=exchange(sse(usage=False));self.assertIsNone(json.loads(result.body)['usage'])
    def test_telemetry_rejects_arbitrary_fields_and_sensitive_strings(self):
        for e in ({'event':'dns_complete','elapsed_ms':0,'url':'SECRET'},
                  {'event':'SECRET','elapsed_ms':0},{'event':'provider_finish','elapsed_ms':0,'finish_reason':'SECRET'}):
            with self.assertRaises(StoreGuard):pt.check_event(e)
        _,events=exchange(b'',open_error=TimeoutError('KEY PRIVATE URL'))
        self.assertNotIn('PRIVATE',json.dumps(events));self.assertNotIn('KEY',json.dumps(events))
    def test_actual_dns_tcp_local_socket_observation(self):
        server=socket.socket();server.bind(('127.0.0.1',0));server.listen()
        events=[];life=pt.Lifecycle(events.append,POLICY)
        try:
            client=pt._connection(server.getsockname(),1,None,life)
            accepted,_=server.accept();client.close();accepted.close()
        finally:server.close()
        self.assertEqual([e['event'] for e in events],['dns_started','dns_complete','tcp_started','tcp_connected'])
    def test_loopback_http_real_chunked_stream(self):
        payload=sse();counts=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                counts.append(self.rfile.read(int(self.headers['Content-Length'])))
                self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Transfer-Encoding','chunked');self.end_headers()
                for block in (payload[:21],payload[21:]):
                    self.wfile.write(('%x\r\n'%len(block)).encode()+block+b'\r\n');self.wfile.flush()
                self.wfile.write(b'0\r\n\r\n');self.wfile.flush()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        class Opener:
            def open(self,req,timeout):
                local=urllib.request.Request('http://127.0.0.1:'+str(server.server_port),data=req.data,method='POST')
                return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(local,timeout=timeout)
        try:result=pt.http_exchange(b'{"stream":true}','DUMMY',POLICY,opener_factory=lambda t:Opener())
        finally:server.shutdown();server.server_close();thread.join()
        self.assertEqual(result.wire,payload);self.assertEqual(len(counts),1)

class ChildTests(unittest.TestCase):
    def test_real_child_pipe_preserves_large_wire_and_bounded_body(self):
        script="""import sys,json,hashlib,base64
sys.path.insert(0,sys.argv[1]);import provider_transport as pt
frame=sys.stdin.buffer.read();wire=b'x'*2000000
receipt={'frame_sha256':hashlib.sha256(frame).hexdigest(),'kind':'terminal','status':200,'body':base64.b64encode(b'{}').decode(),'wire':base64.b64encode(wire).decode()}
sys.stdout.buffer.write(pt.RESULT_HEADER+pt.encode(receipt))
"""
        result=pt.worker_exchange(b'{}','DUMMY',5,POLICY,[sys.executable,'-B','-c',script,str(CODE)],ROOT)
        self.assertEqual(result.wire,b'x'*2000000)
    def test_streaming_child_terminal_and_parent_receipt(self):
        events=[]
        result=pt.worker_exchange(b'{"stream":true}','DUMMY',5,POLICY,command(),ROOT,events.append)
        self.assertEqual(result.wire,sse())
        self.assertEqual([e['event'] for e in events][-2:],['child_exit','parent_receipt'])
        self.assertIn('worker_terminal',[e['event'] for e in events])
    def test_worker_killed(self):
        with self.assertRaises(pt.TransportFault) as c:pt.worker_exchange(b'{}','DUMMY',5,POLICY,command('killed'),ROOT)
        self.assertEqual(c.exception.reason,'PROCESS_EXIT_UNKNOWN')
    def test_child_exits_without_receipt(self):
        with self.assertRaises(pt.TransportFault) as c:pt.worker_exchange(b'{}','DUMMY',5,POLICY,command('exit'),ROOT)
        self.assertEqual(c.exception.reason,'PROCESS_EXIT_UNKNOWN')
    def test_parent_deadline_terminates_owned_child(self):
        policy={**POLICY,'connect_timeout_seconds':.1,'read_timeout_seconds':.1,'worker_deadline_seconds':.2}
        events=[];start=time.monotonic()
        with self.assertRaises(pt.TransportFault) as c:pt.worker_exchange(b'{}','DUMMY',.4,policy,command('hang'),ROOT,events.append)
        self.assertEqual(c.exception.reason,'PARENT_DEADLINE');self.assertLess(time.monotonic()-start,3)
        self.assertIn('child_exit',[e['event'] for e in events])

class JournalTests(unittest.TestCase):
    tearDown=old.V2Tests.tearDown
    def setUp(self):
        self.root=old.create_sandbox(old.OUT/self._testMethodName)
        self.s=old.TranscriptStore(self.root);self.h=self.s.open_session('OFFLINE_OPERATOR','A')
        self.j=provider.ProviderJournal(self.s);self.scope=old.scope()
        self.scope.update(stream=True,request_timeout_seconds=5,transport_policy=POLICY)
        for slot in self.scope['slots']:slot['case_id']='AUTHORED_TRANSPORT'
        self.j.register_batch(self.scope);self.t=self.s.begin_turn(self.h,'第一轮问题','one')
        self.context=old.build_context(self.s,self.h,self.t['turn_id'])
    def call(self,wire=None):
        with patch.object(provider,'_worker_command',lambda:command(wire=wire)):
            return self.j.call(self.h,self.t['turn_id'],self.scope['batch_id'],'one',self.context,credential_reader=lambda:'DUMMY')
    def test_success_journal_exact_raw_stream_and_configuration(self):
        row=self.call();self.assertEqual(row['status'],'RESPONSE_CAPTURED')
        req=json.loads(row['request_json']);self.assertTrue(req['stream']);self.assertEqual(req['thinking'],{'type':'enabled'})
        self.assertEqual(req['reasoning_effort'],'max');self.assertEqual(req['max_tokens'],8192)
        wire=self.s.db.execute('SELECT * FROM transport_wire_captures').fetchone()
        self.assertEqual(wire['wire_bytes'],sse());self.assertEqual(wire['complete'],1)
        events=[json.loads(r[0]) for r in self.s.db.execute("SELECT detail_json FROM turn_lifecycle WHERE state='TRANSPORT_LIFECYCLE'")]
        self.assertIn('parent_receipt',[e['event'] for e in events])
    def test_evaluation_binding_accepts_exact_stream_and_rejects_changed_options(self):
        sys.path.insert(0,str(ROOT/'persona_core/gpt6_optimization_v2/tools'))
        import evaluation_runner as runner
        self.call()
        prep={'sessions':{'AUTHORED_TRANSPORT':{'session_id':self.h.session_id,'entity_id':self.h.entity_id,'mode':self.h.mode}}}
        rows,_=runner.validate_rows(self.s.db,self.root,{'capture_mode':runner.TARGET},self.scope,prep)
        self.assertEqual(len(rows),1)
        payload=json.loads(self.s.db.execute('SELECT request_json FROM provider_calls').fetchone()[0])
        payload['stream_options']['include_usage']=False
        with self.s.transaction():
            self.s.db.execute('UPDATE provider_calls SET request_json=?,request_sha256=?',
                (provider.canonical(payload).decode('utf-8'),provider.digest(payload)))
        with self.assertRaisesRegex(runner.RunnerError,'REQUEST_SCOPE_MISMATCH'):
            runner.validate_rows(self.s.db,self.root,{'capture_mode':runner.TARGET},self.scope,prep)
    def test_unknown_quarantine_no_retry_no_duplicate_no_next_slot(self):
        row=self.call(sse(done=False));self.assertEqual(row['status'],'SUBMITTED_STATUS_UNKNOWN')
        self.assertIsNone(self.s.get_turn(self.h,self.t['turn_id'])['assistant_text'])
        self.assertGreater(row['reserve_micro_cny'],0);self.assertIsNone(row['estimate_peak_micro_cny'])
        with patch.object(provider,'_worker_command',side_effect=AssertionError('NO RESEND')):
            self.assertEqual(self.call()['call_id'],row['call_id'])
            t=self.s.begin_turn(self.h,'第二轮追问','two')
            with self.assertRaises(StoreGuard):
                self.j.call(self.h,t['turn_id'],self.scope['batch_id'],'two',old.build_context(self.s,self.h,t['turn_id']),credential_reader=lambda:'DUMMY')
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0],1)
        self.assertEqual(self.s.db.execute('SELECT stopped FROM call_batches').fetchone()[0],1)
        self.assertEqual(self.s.db.execute('SELECT complete FROM transport_wire_captures').fetchone()[0],0)
    def test_terminal_without_usage_rejected_not_accepted_or_retried(self):
        row=self.call(sse(usage=False));self.assertEqual(row['status'],'RESPONSE_REJECTED')
        self.assertEqual(row['error_category'],'INVALID_USAGE');self.assertIsNone(row['estimate_peak_micro_cny'])
        self.assertEqual(self.call()['call_id'],row['call_id'])

if __name__=='__main__':
    unittest.main(verbosity=2)
