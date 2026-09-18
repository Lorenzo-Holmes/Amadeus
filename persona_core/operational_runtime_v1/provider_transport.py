"""Opt-in, bounded HTTP lifecycle transport. No generation retries or resumption.

Only allowlisted states/times enter telemetry. Wire bodies use a separate private
capture; an incomplete stream is never a reply. Legacy worker IPC stays readable.
"""
from __future__ import annotations
import base64
import hashlib
import http.client
import json
import math
import queue
import socket
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from transcript_store import StoreGuard, ensure

VERSION = 'apcore-transport-lifecycle-1'
RESULT_HEADER = b'AMADEUS_WORKER_RESULT_V2\n'
MAX_BODY = 1_000_000
# SSE repeats metadata per token. Preserve the legacy normalized-body bound,
# while allowing the transport framing overhead of a 32768-token completion.
MAX_WIRE = 16_000_000
MAX_PIPE = 24_000_000
FINISHES = {'stop', 'length', 'content_filter', 'tool_calls', 'insufficient_system_resource'}
TIMEOUTS = {'CONNECT_TIMEOUT','READ_TIMEOUT','INACTIVITY_TIMEOUT','WORKER_DEADLINE','PARENT_DEADLINE','PROCESS_EXIT_UNKNOWN'}
EVENTS = {'worker_started','dns_started','dns_complete','tcp_started','tcp_connected',
          'proxy_tunnel_started','proxy_tunnel_complete','tls_started','tls_connected',
          'request_write_started','request_write_complete','response_wait_started',
          'first_response_header','headers_complete','first_response_byte','first_token',
          'last_response_byte','provider_finish','stream_done','http_terminal',
          'worker_terminal','worker_error','child_started','child_exit','parent_receipt',
          'parent_deadline','transport_unknown'}

def encode(v):
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

def check_policy(policy, total):
    ensure(isinstance(policy,dict) and set(policy)=={'version','connect_timeout_seconds','read_timeout_seconds','worker_deadline_seconds'},'TRANSPORT_POLICY_SHAPE')
    ensure(policy['version']==VERSION,'TRANSPORT_POLICY_VERSION')
    for k in ('connect_timeout_seconds','read_timeout_seconds','worker_deadline_seconds'):
        ensure(type(policy[k]) in (int,float) and math.isfinite(policy[k]) and 0<policy[k]<=1200,'TRANSPORT_POLICY_BOUND')
    ensure(policy['connect_timeout_seconds']<=policy['worker_deadline_seconds'] and
           policy['read_timeout_seconds']<=policy['worker_deadline_seconds']<total<=1200,'TRANSPORT_DEADLINE_ORDER')

def check_event(e):
    ensure(isinstance(e,dict) and set(e).issubset({'event','elapsed_ms','http_status','bytes','finish_reason','timeout_source','exit_code'}),'TELEMETRY_FIELDS')
    ensure(e.get('event') in EVENTS and type(e.get('elapsed_ms')) is int and 0<=e['elapsed_ms']<=1_300_000,'TELEMETRY_EVENT')
    if 'http_status' in e: ensure(type(e['http_status']) is int and 100<=e['http_status']<=599,'TELEMETRY_HTTP_STATUS')
    if 'bytes' in e: ensure(type(e['bytes']) is int and 0<=e['bytes']<=MAX_PIPE,'TELEMETRY_BYTES')
    if 'finish_reason' in e: ensure(e['finish_reason'] in FINISHES,'TELEMETRY_FINISH')
    if 'timeout_source' in e: ensure(e['timeout_source'] in TIMEOUTS,'TELEMETRY_TIMEOUT')
    if 'exit_code' in e: ensure(type(e['exit_code']) is int and -(2**32)<=e['exit_code']<2**32,'TELEMETRY_EXIT')

class Lifecycle:
    def __init__(self,sink=lambda e:None,policy=None):
        self.sink=sink; self.started=time.monotonic(); self.phase='worker'; self.policy=policy
        self.seen=set(); self.count=0
    def emit(self,event,**values):
        if event in self.seen:return
        e={'event':event,'elapsed_ms':round((time.monotonic()-self.started)*1000),**values}
        check_event(e); self.seen.add(event); self.count+=1
        ensure(self.count<=64,'TELEMETRY_COUNT'); self.sink(e)
    def remaining(self,limit):
        remaining=self.policy['worker_deadline_seconds']-(time.monotonic()-self.started)
        if remaining<=0:raise TransportFault('WORKER_DEADLINE')
        return min(limit,remaining)

class TransportFault(StoreGuard):
    def __init__(self,reason,wire=b'',status=None):
        super().__init__(reason)
        self.reason=reason; self.wire=wire; self.status=status

class TransportResult:
    def __init__(self,status,body,wire):self.status=status; self.body=body; self.wire=wire
    def __iter__(self):return iter((self.status,self.body))

def _connection(address,timeout,source_address,lifecycle):
    lifecycle.phase='connect'; lifecycle.emit('dns_started')
    addresses=socket.getaddrinfo(*address,type=socket.SOCK_STREAM)
    lifecycle.emit('dns_complete')
    # Multiple resolved addresses may be connected before writing any request;
    # this never resubmits HTTP. Bound the address list and total worker budget.
    last=None
    for family,kind,proto,_,sockaddr in addresses[:16]:
        sock=socket.socket(family,kind,proto)
        try:
            sock.settimeout(lifecycle.remaining(timeout))
            if source_address:sock.bind(source_address)
            lifecycle.emit('tcp_started'); sock.connect(sockaddr)
            lifecycle.emit('tcp_connected'); return sock
        except OSError as exc:
            last=exc; sock.close()
    if last:raise last
    raise OSError('NO_ADDRESS')

def _handlers(lifecycle):
    class Response(http.client.HTTPResponse):
        def _read_status(self):
            value=super()._read_status()
            if lifecycle.phase!='proxy_tunnel':
                lifecycle.emit('first_response_header',http_status=value[1])
            return value
    class Connection(http.client.HTTPSConnection):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self._create_connection=lambda address,timeout,source_address: _connection(address,timeout,source_address,lifecycle)
            self.response_class=Response
        def _tunnel(self):
            lifecycle.phase='proxy_tunnel'; lifecycle.emit('proxy_tunnel_started')
            super()._tunnel(); lifecycle.emit('proxy_tunnel_complete')
        def connect(self):
            http.client.HTTPConnection.connect(self)
            lifecycle.phase='connect'; lifecycle.emit('tls_started')
            self.sock.settimeout(lifecycle.remaining(lifecycle.policy['connect_timeout_seconds']))
            self.sock=self._context.wrap_socket(self.sock,server_hostname=self._tunnel_host or self.host)
            lifecycle.emit('tls_connected')
        def _send_request(self,*args,**kwargs):
            # Establish the connection before marking the request write phase.
            if self.sock is None:self.connect()
            lifecycle.phase='write'; lifecycle.emit('request_write_started')
            self.sock.settimeout(lifecycle.remaining(lifecycle.policy['read_timeout_seconds']))
            super()._send_request(*args,**kwargs)
            lifecycle.emit('request_write_complete'); lifecycle.phase='header'
            lifecycle.emit('response_wait_started')
    class HTTPS(urllib.request.HTTPSHandler):
        def https_open(self,req):return self.do_open(Connection,req,context=self._context)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            raise urllib.error.HTTPError(req.full_url,code,'REFUSED',headers,fp)
    return HTTPS(),NoRedirect()

class StreamAssembly:
    """SSE records are preserved exactly; text is rebuilt without another call."""
    def __init__(self,lifecycle):
        self.lifecycle=lifecycle; self.buffer=b''; self.data=[]; self.done=False
        self.content=[]; self.reasoning=[]; self.meta={}; self.finish=None; self.usage=None
    def feed(self,block):
        self.buffer+=block
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1); line=line.rstrip(b'\r')
            if line.startswith(b'data:'):self.data.append(line[5:].lstrip(b' '))
            elif not line and self.data:
                self.record(b'\n'.join(self.data)); self.data=[]
    def record(self,data):
        if self.done:
            ensure(not data.strip(),'STREAM_DATA_AFTER_DONE'); return
        if data==b'[DONE]':
            ensure(self.finish is not None,'STREAM_DONE_WITHOUT_FINISH')
            self.done=True; self.lifecycle.emit('stream_done'); return
        obj=json.loads(data)
        ensure(isinstance(obj,dict) and 'error' not in obj,'INVALID_STREAM_OBJECT')
        for key in ('id','model','created','system_fingerprint'):
            if key in obj:
                ensure(key not in self.meta or self.meta[key]==obj[key],'STREAM_IDENTITY_CHANGED')
                self.meta[key]=obj[key]
        if obj.get('usage') is not None:
            ensure(self.usage is None or self.usage==obj['usage'],'STREAM_USAGE_CHANGED')
            self.usage=obj['usage']
        choices=obj.get('choices')
        ensure(isinstance(choices,list) and len(choices)<=1,'INVALID_STREAM_CHOICES')
        if not choices:return
        choice=choices[0]; ensure(choice.get('index')==0,'INVALID_STREAM_INDEX')
        delta=choice.get('delta',{}); ensure(isinstance(delta,dict),'INVALID_STREAM_DELTA')
        ensure(not delta.get('tool_calls') and not delta.get('function_call'),'UNEXPECTED_STREAM_TOOLS')
        for key,target in [('content',self.content),('reasoning_content',self.reasoning)]:
            text=delta.get(key)
            if text is not None:
                ensure(isinstance(text,str),'INVALID_STREAM_TEXT')
                ensure(self.finish is None or not text,'STREAM_CONTENT_AFTER_FINISH')
                target.append(text)
                if text:self.lifecycle.emit('first_token')
        finish=choice.get('finish_reason')
        if finish is not None:
            ensure(finish in FINISHES and (self.finish is None or self.finish==finish),'INVALID_STREAM_FINISH')
            self.finish=finish; self.lifecycle.emit('provider_finish',finish_reason=finish)
    def body(self):
        ensure(self.done and self.finish is not None,'STREAM_TERMINAL_MISSING')
        return encode({**self.meta,'object':'chat.completion','choices':[{'index':0,
            'message':{'role':'assistant','content':''.join(self.content),'reasoning_content':''.join(self.reasoning)},
            'finish_reason':self.finish}], 'usage':self.usage})

def http_exchange(payload,credential,policy,sink=lambda e:None,*,catalogue=False,opener_factory=None):
    lifecycle=Lifecycle(sink,policy); lifecycle.emit('worker_started')
    wire=bytearray(); status=None
    try:
        data=json.loads(payload); streaming=data.get('stream') is True and not catalogue
        opener=(opener_factory(lifecycle) if opener_factory else urllib.request.build_opener(*_handlers(lifecycle)))
        request=urllib.request.Request('https://api.deepseek.com/models' if catalogue else 'https://api.deepseek.com/chat/completions',
            data=None if catalogue else payload,method='GET' if catalogue else 'POST',headers={
            'Authorization':'Bearer '+credential,'Content-Type':'application/json','User-Agent':'Amadeus-APCORE-OPERATIONS-V1'})
        try:response=opener.open(request,timeout=lifecycle.remaining(policy['connect_timeout_seconds']))
        except urllib.error.HTTPError as exc:response=exc
        with response:
            status=response.status; lifecycle.emit('headers_complete',http_status=status)
            lifecycle.phase='stream' if streaming and status==200 else 'read'
            assembly=StreamAssembly(lifecycle) if streaming and status==200 else None
            while True:
                wait=lifecycle.remaining(policy['read_timeout_seconds'])
                try:response.fp.raw._sock.settimeout(wait)
                except AttributeError:pass  # Authored in-memory test responses only.
                block=response.read1(min(8192,MAX_WIRE+1-len(wire)))
                if not block:break
                wire.extend(block); lifecycle.emit('first_response_byte')
                ensure(len(wire)<=MAX_WIRE,'WIRE_RESPONSE_TOO_LARGE')
                if assembly:
                    assembly.feed(block)
                    if assembly.done:break
            lifecycle.emit('last_response_byte',bytes=len(wire))
        if status!=200:
            lifecycle.emit('http_terminal',http_status=status); body=bytes(wire)
        elif catalogue:
            ensure(isinstance(json.loads(wire),dict),'CATALOGUE_INVALID'); body=bytes(wire)
            lifecycle.emit('http_terminal',http_status=status)
        elif assembly:
            body=assembly.body()
        else:
            obj=json.loads(wire); choices=obj.get('choices')
            ensure(isinstance(choices,list) and len(choices)==1,'NONSTREAM_CHOICES_INVALID')
            finish=choices[0].get('finish_reason')
            ensure(finish in FINISHES,'NONSTREAM_TERMINAL_MISSING')
            lifecycle.emit('provider_finish',finish_reason=finish)
            # Nonstream token timing is unobservable until the completed JSON.
            body=bytes(wire)
        ensure(len(body)<=MAX_BODY,'ASSEMBLED_RESPONSE_TOO_LARGE')
        lifecycle.emit('worker_terminal'); return TransportResult(status,body,bytes(wire))
    except Exception as exc:
        cause=exc.reason if isinstance(exc,urllib.error.URLError) and isinstance(exc.reason,Exception) else exc
        if isinstance(exc,TransportFault):reason=exc.reason
        elif time.monotonic()-lifecycle.started>=policy['worker_deadline_seconds']:reason='WORKER_DEADLINE'
        elif isinstance(cause,TimeoutError):
            reason='CONNECT_TIMEOUT' if lifecycle.phase in ('connect','proxy_tunnel') else 'INACTIVITY_TIMEOUT' if lifecycle.phase=='stream' else 'READ_TIMEOUT'
        else:reason='TRANSPORT_PROTOCOL_OR_CONNECTION_ERROR'
        lifecycle.emit('worker_error',**({'timeout_source':reason} if reason in TIMEOUTS else {}))
        raise TransportFault(reason,bytes(wire),status) from None

def child_result(frame,frame_hash):
    policy=frame['transport_policy']
    def sink(event):
        import sys
        sys.stderr.buffer.write(encode({'frame_sha256':frame_hash,'lifecycle':event})+b'\n');sys.stderr.buffer.flush()
    try:
        result=http_exchange(frame['payload'].encode('utf-8'),frame['credential'],policy,sink,catalogue=frame.get('operation')=='CATALOGUE')
        value={'kind':'terminal','status':result.status,'body':base64.b64encode(result.body).decode('ascii'),
               'wire':base64.b64encode(result.wire).decode('ascii')}
    except TransportFault as exc:
        value={'kind':'unknown','status':exc.status,'reason':exc.reason,'wire':base64.b64encode(exc.wire).decode('ascii')}
    return RESULT_HEADER+encode({'frame_sha256':frame_hash,**value})

def worker_exchange(payload,credential,total,policy,command,cwd,sink=lambda e:None,*,catalogue=False):
    """Drain both pipes concurrently; main thread commits live telemetry to SQLite."""
    check_policy(policy,total)
    frame=encode({'payload':payload.decode('utf-8'),'credential':credential,'timeout_seconds':total,
                  'transport_policy':policy,**({'operation':'CATALOGUE'} if catalogue else {})})
    frame_hash=hashlib.sha256(frame).hexdigest(); events=queue.Queue(maxsize=128)
    output=bytearray(); problems=[]; lifecycle=Lifecycle(sink)
    child=subprocess.Popen(command,cwd=cwd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    lifecycle.emit('child_started')
    def read_out():
        try:
            while True:
                data=child.stdout.read(8192)
                if not data:break
                if len(output)+len(data)>MAX_PIPE:problems.append('PIPE_BOUND');break
                output.extend(data)
        except Exception:problems.append('PIPE_READ')
    def read_events():
        count=0
        try:
            while True:
                line=child.stderr.readline(2049)
                if not line:break
                count+=1
                ensure(len(line)<=2048 and line.endswith(b'\n') and count<=64,'TELEMETRY_BOUND')
                record=json.loads(line)
                ensure(set(record)=={'frame_sha256','lifecycle'} and record['frame_sha256']==frame_hash,'TELEMETRY_BINDING')
                check_event(record['lifecycle']); events.put_nowait(record['lifecycle'])
        except Exception:problems.append('TELEMETRY_INVALID')
    def send_frame():
        try:child.stdin.write(frame);child.stdin.close()
        except Exception:problems.append('PIPE_WRITE')
    threads=[threading.Thread(target=f,daemon=True) for f in (read_out,read_events,send_frame)]
    for thread in threads:thread.start()
    deadline=lifecycle.started+total; timeout=False
    def drain():
        while True:
            try:e=events.get_nowait()
            except queue.Empty:break
            sink(e)
    try:
        while child.poll() is None:
            drain()
            if problems:break
            if time.monotonic()>=deadline:timeout=True;break
            time.sleep(min(.02,max(0,deadline-time.monotonic())))
        if child.poll() is None:child.kill()
        child.wait(timeout=5)
        for thread in threads:thread.join(timeout=2)
        drain(); lifecycle.emit('child_exit',exit_code=child.returncode)
        if timeout:
            lifecycle.emit('parent_deadline',timeout_source='PARENT_DEADLINE')
            raise TransportFault('PARENT_DEADLINE')
        if problems or any(thread.is_alive() for thread in threads):raise TransportFault('PROCESS_EXIT_UNKNOWN')
        ensure(output.startswith(RESULT_HEADER),'WORKER_TERMINAL_RECEIPT_MISSING')
        receipt=json.loads(output[len(RESULT_HEADER):])
        ensure(receipt.get('frame_sha256')==frame_hash,'WORKER_RECEIPT_BINDING')
        ensure(receipt.get('kind') in ('terminal','unknown'),'WORKER_RECEIPT_KIND')
        expected={'frame_sha256','kind','status','wire','body' if receipt['kind']=='terminal' else 'reason'}
        ensure(set(receipt)==expected,'WORKER_RECEIPT_FIELDS')
        status=receipt['status']; ensure(status is None or type(status) is int and 100<=status<=599,'WORKER_HTTP_STATUS')
        wire=base64.b64decode(receipt['wire'],validate=True);ensure(len(wire)<=MAX_WIRE,'WORKER_WIRE_BOUND')
        lifecycle.emit('parent_receipt')
        if receipt['kind']=='unknown':
            reason=receipt['reason'];ensure(reason in TIMEOUTS|{'TRANSPORT_PROTOCOL_OR_CONNECTION_ERROR'},'WORKER_REASON')
            raise TransportFault(reason,wire,status)
        ensure(child.returncode==0 and status is not None,'WORKER_EXIT_WITHOUT_SUCCESS')
        body=base64.b64decode(receipt['body'],validate=True);ensure(len(body)<=MAX_BODY,'WORKER_BODY_BOUND')
        return TransportResult(status,body,wire)
    except TransportFault:raise
    except Exception:raise TransportFault('PROCESS_EXIT_UNKNOWN') from None
    finally:
        if child.poll() is None:child.kill();child.wait(timeout=5)
        for pipe in (child.stdin,child.stdout,child.stderr):
            try:pipe.close()
            except Exception:pass
