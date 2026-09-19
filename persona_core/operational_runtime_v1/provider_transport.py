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
from provider_network_route import check_route_policy, proxy_handler

VERSION = 'apcore-transport-lifecycle-1'
RESULT_HEADER = b'AMADEUS_WORKER_RESULT_V2\n'
MAX_BODY = 1_000_000
# SSE repeats metadata per token. Preserve the legacy normalized-body bound,
# while allowing the transport framing overhead of a 32768-token completion.
MAX_WIRE = 16_000_000
MAX_PIPE = 24_000_000
FINISHES = {'stop', 'length', 'content_filter', 'tool_calls', 'insufficient_system_resource', 'aborted'}
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


def route_opener(lifecycle, network_route_policy=None):
    handlers = _handlers(lifecycle)
    if network_route_policy is not None:
        handlers = (proxy_handler(network_route_policy), *handlers)
    return urllib.request.build_opener(*handlers)

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

class ResponsesAssembly:
    """DeepSeek Responses API SSE assembly normalized to the existing provider contract."""
    TERMINALS={'response.completed','response.incomplete','response.failed'}
    def __init__(self,lifecycle):
        self.lifecycle=lifecycle; self.buffer=b''; self.event_name=None; self.data=[]
        self.last_sequence=-1; self.response_id=None; self.model=None
        self.content=[]; self.terminal=None; self.response=None
    def feed(self,block):
        self.buffer+=block
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1); line=line.rstrip(b'\r')
            if line.startswith(b'event:'):
                ensure(self.terminal is None and self.event_name is None,'RESPONSES_EVENT_AFTER_TERMINAL_OR_DUPLICATE')
                self.event_name=line[6:].strip().decode('utf-8')
            elif line.startswith(b'data:'):
                ensure(self.terminal is None,'RESPONSES_EVENT_AFTER_TERMINAL')
                self.data.append(line[5:].lstrip(b' '))
            elif not line:
                if self.data:self.record(self.event_name,b'\n'.join(self.data))
                else:ensure(self.event_name is None,'RESPONSES_EVENT_WITHOUT_DATA')
                self.event_name=None;self.data=[]
    def _bind_response(self,response):
        ensure(isinstance(response,dict),'RESPONSES_RESPONSE_OBJECT')
        rid=response.get('id');model=response.get('model')
        ensure(isinstance(rid,str) and bool(rid) and isinstance(model,str) and bool(model),'RESPONSES_RESPONSE_IDENTITY')
        ensure(self.response_id in (None,rid) and self.model in (None,model),'RESPONSES_IDENTITY_CHANGED')
        self.response_id=rid;self.model=model
    def record(self,event_name,data):
        ensure(self.terminal is None,'RESPONSES_EVENT_AFTER_TERMINAL')
        def pairs(items):
            result={}
            for key,value in items:
                ensure(key not in result,'RESPONSES_DUPLICATE_JSON_KEY');result[key]=value
            return result
        def constant(_):raise StoreGuard('RESPONSES_NONFINITE_JSON')
        obj=json.loads(data,object_pairs_hook=pairs,parse_constant=constant)
        ensure(isinstance(obj,dict),'RESPONSES_EVENT_OBJECT')
        event_type=obj.get('type')
        ensure(isinstance(event_type,str) and event_type.startswith('response.')
               and (event_name is None or event_type==event_name),'RESPONSES_EVENT_TYPE')
        sequence=obj.get('sequence_number')
        ensure(type(sequence) is int and sequence>self.last_sequence,'RESPONSES_SEQUENCE')
        self.last_sequence=sequence
        if event_type in {'response.created','response.in_progress'}|self.TERMINALS:
            self._bind_response(obj.get('response'))
        if 'response_id' in obj:
            ensure(self.response_id is not None and obj['response_id']==self.response_id,'RESPONSES_IDENTITY_CHANGED')
        if 'model' in obj:
            ensure(self.model is not None and obj['model']==self.model,'RESPONSES_IDENTITY_CHANGED')
        if event_type=='response.output_text.delta':
            delta=obj.get('delta');ensure(isinstance(delta,str),'RESPONSES_TEXT_DELTA')
            self.content.append(delta)
            if delta:self.lifecycle.emit('first_token')
        if event_type in self.TERMINALS:
            ensure(obj['response'].get('status')==event_type.split('.',1)[1],'RESPONSES_TERMINAL_STATUS_MISMATCH')
            self.terminal=event_type;self.response=obj['response']
            finish='stop'
            if event_type=='response.incomplete':
                details=self.response.get('incomplete_details')
                reason=details.get('reason') if isinstance(details,dict) else None
                finish='content_filter' if reason=='content_filter' else 'length'
            elif event_type=='response.failed':finish='aborted'
            self.lifecycle.emit('provider_finish',finish_reason=finish)
    @property
    def done(self):return self.terminal is not None
    def _visible_text(self):
        response=self.response;status=response['status'];final=[];output=response.get('output')
        ensure(response.get('error') is None,'RESPONSES_COMPLETED_ERROR')
        ensure(response.get('incomplete_details') is None,'RESPONSES_COMPLETED_INCOMPLETE_DETAILS')
        if status=='completed':ensure(isinstance(output,list),'RESPONSES_OUTPUT_REQUIRED')
        ensure(output is None or isinstance(output,list),'RESPONSES_OUTPUT_SHAPE')
        for item in output or []:
            ensure(isinstance(item,dict),'RESPONSES_OUTPUT_ITEM')
            if item.get('type')=='reasoning':continue
            ensure(item.get('type')=='message' and item.get('role')=='assistant','RESPONSES_UNEXPECTED_OUTPUT')
            ensure(isinstance(item.get('content'),list),'RESPONSES_CONTENT_SHAPE')
            if status=='completed':ensure(item.get('status') in (None,'completed'),'RESPONSES_MESSAGE_NOT_COMPLETED')
            for part in item['content']:
                ensure(isinstance(part,dict) and part.get('type')=='output_text'
                       and isinstance(part.get('text'),str),'RESPONSES_OUTPUT_TEXT_REQUIRED')
                final.append(part['text'])
        streamed=''.join(self.content);final_text=''.join(final)
        if status=='completed' or output is not None:
            ensure(streamed==final_text,'RESPONSES_STREAM_FINAL_MISMATCH')
        ensure(bool(streamed.strip()),'RESPONSES_COMPLETED_NO_VISIBLE_OUTPUT')
        return streamed
    def _usage(self):
        usage=self.response.get('usage')
        if self.response['status']=='completed':ensure(isinstance(usage,dict),'RESPONSES_USAGE_REQUIRED')
        ensure(usage is None or isinstance(usage,dict),'RESPONSES_USAGE_SHAPE')
        if isinstance(usage,dict):
            inp=usage.get('input_tokens');out=usage.get('output_tokens');total=usage.get('total_tokens')
            ensure(all(type(v) is int and v>=0 for v in (inp,out,total)) and inp+out==total,'RESPONSES_USAGE')
            input_details=usage.get('input_tokens_details');output_details=usage.get('output_tokens_details')
            ensure(input_details is None or isinstance(input_details,dict),'RESPONSES_USAGE_DETAILS')
            ensure(output_details is None or isinstance(output_details,dict),'RESPONSES_USAGE_DETAILS')
            cached=(input_details or {}).get('cached_tokens',0)
            reasoning=(output_details or {}).get('reasoning_tokens',0)
            ensure(type(cached) is int and 0<=cached<=inp and type(reasoning) is int and 0<=reasoning<=out,'RESPONSES_USAGE_DETAILS')
            return {'prompt_tokens':inp,'completion_tokens':out,'total_tokens':total,
                'prompt_cache_hit_tokens':cached,'prompt_cache_miss_tokens':inp-cached,
                'completion_tokens_details':{'reasoning_tokens':reasoning}}
        return None
    def body(self):
        # Protocol certainty is decided before usability. A trusted terminal
        # with unusable text/usage is not a transport failure or permission to retry.
        ensure(self.done and isinstance(self.response,dict),'RESPONSES_TERMINAL_MISSING')
        ensure(not self.buffer.strip() and not self.data and self.event_name is None,'RESPONSES_UNFINISHED_SSE_RECORD')
        response=self.response;status=response.get('status')
        ensure(status==self.terminal.split('.',1)[1],'RESPONSES_TERMINAL_STATUS_MISMATCH')
        details=response.get('incomplete_details')
        incomplete_reason=details.get('reason') if isinstance(details,dict) else None
        finish='stop' if status=='completed' else 'aborted' if status=='failed' else (
            'content_filter' if incomplete_reason=='content_filter' else 'length')
        normalized_usage=None;usage_error=None;text='';output_error=None
        try:normalized_usage=self._usage()
        except StoreGuard as exc:usage_error=str(exc)
        if status=='completed':
            try:text=self._visible_text()
            except StoreGuard as exc:output_error=str(exc)
        rejection=('RESPONSES_INCOMPLETE' if status=='incomplete' else
                   'RESPONSES_FAILED' if status=='failed' else output_error or usage_error)
        extra={}
        if rejection:
            # No partial answer, reasoning, summary or provider error message is
            # copied into an assistant message. Original evidence stays in wire.
            text=''
            extra['responses_terminal_rejection']={
                'version':'apcore-responses-terminal-1','reason':rejection,
                'terminal_event':self.terminal,'response_id':self.response_id,
                'usage_error':usage_error,'incomplete_reason':incomplete_reason if incomplete_reason in ('max_output_tokens','content_filter') else None}
        # Successful normalization is byte-compatible with historical captures.
        return encode({'id':response.get('id'),'model':response.get('model'),
            'choices':[{'index':0,'message':{'role':'assistant','content':text},'finish_reason':finish}],
            'usage':normalized_usage,'responses_api_status':status,**extra})

def verify_responses_result(result):
    """Bind a parent receipt to its wire before journal acceptance or rejection."""
    if result.status!=200:return
    try:
        assembly=ResponsesAssembly(Lifecycle());assembly.feed(result.wire)
        ensure(assembly.body()==result.body,'RESPONSES_RECEIPT_WIRE_MISMATCH')
    except (ValueError,KeyError,TypeError,UnicodeError):
        raise TransportFault('TRANSPORT_PROTOCOL_OR_CONNECTION_ERROR',result.wire,result.status) from None

def verify_responses_wire(db,row,scope):
    """Rebuild the normalized receipt from its separately hash-bound wire."""
    ensure(scope.get('schema_version') in {'apcore-provider-scope-4','apcore-provider-scope-5'}
           and scope.get('api_protocol')=='responses','RESPONSES_SCOPE_BINDING')
    if scope.get('schema_version') == 'apcore-provider-scope-5':
        check_route_policy(scope.get('network_route_policy'))
    wire=db.execute('SELECT * FROM transport_wire_captures WHERE call_id=?',(row['call_id'],)).fetchone()
    ensure(wire is not None and wire['wire_format']=='SSE' and wire['complete']==1
           and wire['credential_redacted']==0,'RESPONSES_WIRE_CAPTURE_REQUIRED')
    data=bytes(wire['wire_bytes'])
    ensure(hashlib.sha256(data).hexdigest()==wire['wire_sha256'],'RESPONSES_WIRE_HASH_CHANGED')
    assembly=ResponsesAssembly(Lifecycle());assembly.feed(data)
    raw=row['raw_response'];raw=raw.encode('utf-8') if isinstance(raw,str) else raw
    ensure(assembly.body()==raw and assembly.terminal=='response.completed','RESPONSES_NORMALIZATION_CHANGED')
    ensure(hashlib.sha256(raw).hexdigest()==row['raw_sha256'],'RESPONSES_NORMALIZED_HASH_CHANGED')

def responses_http_exchange(payload,credential,policy,sink=lambda e:None,opener_factory=None,*,network_route_policy=None):
    lifecycle=Lifecycle(sink,policy);lifecycle.emit('worker_started')
    wire=bytearray();status=None
    try:
        data=json.loads(payload);ensure(data.get('stream') is True,'RESPONSES_STREAM_REQUIRED')
        opener=(opener_factory(lifecycle) if opener_factory else route_opener(lifecycle,network_route_policy))
        request=urllib.request.Request('https://api.deepseek.com/responses',data=payload,method='POST',headers={
            'Authorization':'Bearer '+credential,'Content-Type':'application/json','Accept':'text/event-stream',
            'User-Agent':'Amadeus-APCORE-RESPONSES-V1'})
        try:response=opener.open(request,timeout=lifecycle.remaining(policy['connect_timeout_seconds']))
        except urllib.error.HTTPError as exc:response=exc
        with response:
            status=response.status;lifecycle.emit('headers_complete',http_status=status)
            lifecycle.phase='stream' if status==200 else 'read'
            assembly=ResponsesAssembly(lifecycle) if status==200 else None
            while True:
                wait=lifecycle.remaining(policy['read_timeout_seconds'])
                try:response.fp.raw._sock.settimeout(wait)
                except AttributeError:pass
                block=response.read1(min(8192,MAX_WIRE+1-len(wire)))
                if not block:break
                wire.extend(block);lifecycle.emit('first_response_byte')
                ensure(len(wire)<=MAX_WIRE,'WIRE_RESPONSE_TOO_LARGE')
                if assembly:
                    assembly.feed(block)
                    # Read to bounded EOF so a later event cannot hide behind
                    # a completed event at the end of an earlier socket read.
            lifecycle.emit('last_response_byte',bytes=len(wire))
        if status!=200:
            lifecycle.emit('http_terminal',http_status=status);body=bytes(wire)
        else:
            body=assembly.body()
        ensure(len(body)<=MAX_BODY,'ASSEMBLED_RESPONSE_TOO_LARGE')
        lifecycle.emit('worker_terminal');return TransportResult(status,body,bytes(wire))
    except Exception as exc:
        cause=exc.reason if isinstance(exc,urllib.error.URLError) and isinstance(exc.reason,Exception) else exc
        if isinstance(exc,TransportFault):reason=exc.reason
        elif time.monotonic()-lifecycle.started>=policy['worker_deadline_seconds']:reason='WORKER_DEADLINE'
        elif isinstance(cause,TimeoutError):
            reason='CONNECT_TIMEOUT' if lifecycle.phase in ('connect','proxy_tunnel') else 'INACTIVITY_TIMEOUT' if lifecycle.phase=='stream' else 'READ_TIMEOUT'
        else:reason='TRANSPORT_PROTOCOL_OR_CONNECTION_ERROR'
        lifecycle.emit('worker_error',**({'timeout_source':reason} if reason in TIMEOUTS else {}))
        raise TransportFault(reason,bytes(wire),status) from None

def http_exchange(payload,credential,policy,sink=lambda e:None,*,catalogue=False,opener_factory=None,network_route_policy=None):
    lifecycle=Lifecycle(sink,policy); lifecycle.emit('worker_started')
    wire=bytearray(); status=None
    try:
        data=json.loads(payload); streaming=data.get('stream') is True and not catalogue
        opener=(opener_factory(lifecycle) if opener_factory else route_opener(lifecycle,network_route_policy))
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
    route_args={'network_route_policy':frame['network_route_policy']} if 'network_route_policy' in frame else {}
    def sink(event):
        import sys
        sys.stderr.buffer.write(encode({'frame_sha256':frame_hash,'lifecycle':event})+b'\n');sys.stderr.buffer.flush()
    try:
        if frame.get('operation')=='RESPONSES':
            result=responses_http_exchange(frame['payload'].encode('utf-8'),frame['credential'],policy,sink,**route_args)
        else:
            result=http_exchange(frame['payload'].encode('utf-8'),frame['credential'],policy,sink,catalogue=frame.get('operation')=='CATALOGUE',**route_args)
        value={'kind':'terminal','status':result.status,'body':base64.b64encode(result.body).decode('ascii'),
               'wire':base64.b64encode(result.wire).decode('ascii')}
    except TransportFault as exc:
        value={'kind':'unknown','status':exc.status,'reason':exc.reason,'wire':base64.b64encode(exc.wire).decode('ascii')}
    return RESULT_HEADER+encode({'frame_sha256':frame_hash,**value})

def worker_exchange(payload,credential,total,policy,command,cwd,sink=lambda e:None,*,catalogue=False,responses=False,network_route_policy=None):
    """Drain both pipes concurrently; main thread commits live telemetry to SQLite."""
    check_policy(policy,total)
    if network_route_policy is not None:check_route_policy(network_route_policy)
    ensure(not (catalogue and responses),'WORKER_OPERATION_CONFLICT')
    operation='CATALOGUE' if catalogue else 'RESPONSES' if responses else None
    frame=encode({'payload':payload.decode('utf-8'),'credential':credential,'timeout_seconds':total,
                  'transport_policy':policy,**({'operation':operation} if operation else {}),
                  **({'network_route_policy':network_route_policy} if network_route_policy is not None else {})})
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
