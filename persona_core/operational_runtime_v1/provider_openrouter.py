"""Bounded OpenRouter native adapter; no retries, arbitrary endpoints or tools."""
from __future__ import annotations
import json
import os
import time
import urllib.error
import urllib.request
from transcript_store import WORKSPACE, ensure
import provider_contract as contract
import provider_transport as pt

ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'
MODEL = 'openai/gpt-4.1-mini'
MODEL_ALIASES = frozenset({MODEL, 'openai/gpt-4.1-mini-2025-04-14', 'gpt-4.1-mini-2025-04-14'})
CAPABILITIES = contract.Capabilities(('chat_completions',), ('DIRECT_NO_PROXY', 'SYSTEM_PROXY'),
    'chat_finish_and_done_or_explicit_error', supports_reasoning=False)
WORKER_KEYS = {'provider_id','api_protocol','endpoint','network_route_policy','transport_contract_version'}
NATIVE_FINISHES = {'stop','length','content_filter','tool_calls','function_call','error'}


def generation_options():
    return {'temperature': 0, 'provider': {'order': ['openai'], 'only': ['openai'],
        'allow_fallbacks': False, 'require_parameters': True}}


def route(mode='SYSTEM_PROXY'):
    return {'version': 'apcore-openrouter-route-1', 'mode': mode, 'host': 'openrouter.ai'}


def credential():
    value = os.environ.get('OPENROUTER_API_KEY', '')
    if not value.strip():
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
                value = winreg.QueryValueEx(key, 'OPENROUTER_API_KEY')[0]
        except (ImportError, FileNotFoundError): value = ''
    ensure(isinstance(value, str) and value.strip(), 'OPENROUTER_CREDENTIAL_ABSENT')
    ensure(not any(ch in value for ch in '\r\n'), 'OPENROUTER_CREDENTIAL_FORMAT')
    return value.strip()


def normalize_usage(value):
    if not isinstance(value, dict): return value
    result = {k: value[k] for k in ('prompt_tokens','completion_tokens','total_tokens','completion_tokens_details') if k in value}
    details = value.get('prompt_tokens_details')
    if details is not None and not isinstance(details, dict):
        result['prompt_cache_hit_tokens'] = None
    if isinstance(details, dict) and 'cached_tokens' in details:
        hits = details['cached_tokens']; result['prompt_cache_hit_tokens'] = hits
        total = value.get('prompt_tokens')
        result['prompt_cache_miss_tokens'] = total - hits if type(total) is int and type(hits) is int else None
    return result


class OpenRouterAssembly:
    """SSE framing and terminal certainty, independently of answer usability."""
    def __init__(self, lifecycle):
        self.lifecycle = lifecycle; self.buffer = b''; self.data = []; self.done = False
        self.meta = {}; self.content = []; self.reasoning = []; self.finish = None
        self.usage = None; self.error = False; self.tools = False
        self.records = 0; self.content_events = 0

    def feed(self, block):
        self.buffer += block
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1); line = line.rstrip(b'\r')
            if line.startswith(b'data:'): self.data.append(line[5:].lstrip(b' '))
            elif not line and self.data:
                self.record(b'\n'.join(self.data)); self.data = []
            elif line and not line.startswith((b':', b'event:', b'id:', b'retry:')):
                ensure(False, 'OPENROUTER_INVALID_SSE_LINE')

    def record(self, data):
        if self.done:
            ensure(self.error and data == b'[DONE]', 'OPENROUTER_DATA_AFTER_TERMINAL')
            return
        if data == b'[DONE]':
            ensure(self.finish is not None, 'OPENROUTER_DONE_WITHOUT_FINISH')
            self.done = True; self.lifecycle.emit('stream_done'); return
        obj = json.loads(data)
        ensure(isinstance(obj, dict), 'OPENROUTER_STREAM_OBJECT')
        self.records += 1
        for key in ('id','model','created','provider'):
            if key in obj and obj[key] is not None:
                ensure(key not in self.meta or self.meta[key] == obj[key], 'OPENROUTER_IDENTITY_CHANGED')
                self.meta[key] = obj[key]
        if obj.get('usage') is not None:
            ensure(self.usage is None or self.usage == obj['usage'], 'OPENROUTER_USAGE_CHANGED')
            self.usage = obj['usage']
        choices = obj.get('choices')
        ensure(isinstance(choices, list) and len(choices) <= 1, 'OPENROUTER_CHOICES')
        if not choices:
            ensure('error' not in obj, 'OPENROUTER_UNBOUND_ERROR')
            return
        choice = choices[0]
        ensure(isinstance(choice, dict) and type(choice.get('index')) is int and choice['index'] == 0, 'OPENROUTER_CHOICE_INDEX')
        delta = choice.get('delta', {})
        ensure(isinstance(delta, dict), 'OPENROUTER_DELTA')
        ensure(delta.get('role') in (None, 'assistant'), 'OPENROUTER_ROLE')
        self.tools = self.tools or bool(delta.get('tool_calls') or delta.get('function_call'))
        for key, target in [('content', self.content), ('reasoning', self.reasoning), ('reasoning_content', self.reasoning)]:
            text = delta.get(key)
            if text is not None:
                ensure(isinstance(text, str), 'OPENROUTER_TEXT_TYPE')
                ensure(self.finish is None or not text, 'OPENROUTER_TEXT_AFTER_FINISH')
                target.append(text)
                if text:
                    self.lifecycle.emit('first_token' if key == 'content' else 'first_reasoning_token')
                    if key == 'content': self.content_events += 1
        finish = choice.get('finish_reason')
        if 'error' in obj:
            ensure(isinstance(obj['error'], dict) and isinstance(obj['error'].get('code'), (int,str))
                   and type(obj['error']['code']) is not bool and finish == 'error', 'OPENROUTER_UNTRUSTED_ERROR')
            self.error = True
        if finish is not None:
            ensure(finish in NATIVE_FINISHES and (self.finish is None or self.finish == finish), 'OPENROUTER_FINISH')
            ensure(finish != 'error' or self.error, 'OPENROUTER_ERROR_SHAPE')
            self.finish = finish
            self.lifecycle.emit('provider_finish', finish_reason='aborted' if finish == 'error' else 'tool_calls' if finish == 'function_call' else finish)
            if self.error: self.done = True

    def body(self):
        ensure(self.done and self.finish is not None and not self.buffer.strip() and not self.data, 'OPENROUTER_TERMINAL_MISSING')
        ensure(all(isinstance(self.meta.get(k), str) and self.meta[k] for k in ('id','model')), 'OPENROUTER_TERMINAL_IDENTITY')
        status = 'failed' if self.error else 'completed' if self.finish == 'stop' else 'incomplete'
        reason = 'OPENROUTER_STREAM_ERROR' if self.error else None
        if self.meta.get('provider') not in (None, 'OpenAI', 'openai'): reason = 'OPENROUTER_UPSTREAM_MISMATCH'
        message = {'role':'assistant', 'content':''.join(self.content), 'reasoning_content':''.join(self.reasoning)}
        if self.tools: message['tool_calls'] = ['UNEXPECTED_NATIVE_TOOL_OUTPUT']
        finish = 'aborted' if self.error else 'tool_calls' if self.finish == 'function_call' else self.finish
        return pt.encode({**self.meta, 'object':'chat.completion', 'choices':[{'index':0,'message':message,'finish_reason':finish}],
            'usage':normalize_usage(self.usage), 'provider_terminal':{'status':status,
                'event':'openrouter.stream.error' if self.error else 'openrouter.finish_and_done','reason':reason},
            'stream_observation':{'records':self.records,'content_events':self.content_events}})


def decode_http(wire, status):
    ensure(type(status) is int, 'OPENROUTER_HTTP_STATUS')
    if status == 200:
        parser = OpenRouterAssembly(pt.Lifecycle()); parser.feed(wire); return parser.body()
    ensure(400 <= status <= 599, 'OPENROUTER_UNTRUSTED_HTTP_STATUS')
    value = json.loads(wire)
    ensure(isinstance(value, dict) and isinstance(value.get('error'), dict), 'OPENROUTER_HTTP_ERROR_SHAPE')
    code = value['error'].get('code')
    ensure(type(code) is int and code == status, 'OPENROUTER_HTTP_ERROR_CODE')
    return pt.encode({'model':MODEL,'choices':[], 'usage':normalize_usage(value.get('usage')),
        'provider_terminal':{'status':'failed','event':'openrouter.http.error','reason':'OPENROUTER_HTTP_ERROR_'+str(status)}})


def validate_payload(payload):
    data = json.loads(payload)
    ensure(isinstance(data, dict) and set(data) == {'model','messages','max_tokens','stream','stream_options','temperature','provider'}, 'OPENROUTER_REQUEST_SCHEMA')
    ensure(data['model'] == MODEL and data['stream'] is True and data['stream_options'] == {'include_usage':True}, 'OPENROUTER_REQUEST_CONTRACT')
    ensure(type(data['max_tokens']) is int and 1 <= data['max_tokens'] <= 8192, 'OPENROUTER_OUTPUT_BOUND')
    ensure(all(data[k] == v for k, v in generation_options().items()), 'OPENROUTER_NATIVE_OPTIONS')
    messages = data['messages']
    ensure(isinstance(messages, list) and messages and all(isinstance(m, dict) and set(m)=={'role','content'}
        and m['role'] in ('user','assistant','system') and isinstance(m['content'],str) for m in messages), 'OPENROUTER_MESSAGES')
    ensure(len(contract.canonical(messages)) <= 4096, 'OPENROUTER_INPUT_BOUND')
    return data


def http_exchange(payload, key, policy, worker_contract, sink=lambda event: None, opener_factory=None):
    OpenRouterAdapter().validate_worker_contract(worker_contract)
    validate_payload(payload)
    lifecycle = pt.Lifecycle(sink, policy); lifecycle.emit('worker_started')
    wire = bytearray(); status = None
    try:
        proxy = urllib.request.ProxyHandler({}) if worker_contract['network_route_policy']['mode']=='DIRECT_NO_PROXY' else urllib.request.ProxyHandler()
        opener = opener_factory(lifecycle) if opener_factory else urllib.request.build_opener(proxy, *pt._handlers(lifecycle))
        request = urllib.request.Request(ENDPOINT, data=payload, method='POST', headers={
            'Authorization':'Bearer '+key,'Content-Type':'application/json','Accept':'text/event-stream','User-Agent':'Amadeus-Provider2-Synthetic'})
        lifecycle.operation = 'HTTP_OPEN'
        try: response = opener.open(request, timeout=lifecycle.remaining(policy['connect_timeout_seconds']))
        except urllib.error.HTTPError as exc: response = exc
        with response:
            status = response.status; lifecycle.emit('headers_complete', http_status=status)
            chunked = getattr(response, 'chunked', None)
            lifecycle.http_chunked = chunked if type(chunked) is bool else None
            lifecycle.phase = 'stream' if status==200 else 'read'
            parser = OpenRouterAssembly(lifecycle) if status==200 else None
            while True:
                lifecycle.operation = 'READ_BUDGET'; wait = lifecycle.remaining(policy['read_timeout_seconds'])
                lifecycle.operation = 'SOCKET_TIMEOUT'
                try: response.fp.raw._sock.settimeout(wait)
                except AttributeError: pass
                lifecycle.operation = 'HTTP_READ1'; block = response.read1(min(8192, pt.MAX_WIRE+1-len(wire)))
                if not block: break
                wire.extend(block); lifecycle.emit('first_response_byte')
                lifecycle.operation = 'WIRE_BOUND'; ensure(len(wire)<=pt.MAX_WIRE, 'OPENROUTER_WIRE_BOUND')
                if parser:
                    lifecycle.operation = 'SSE_FEED'; parser.feed(block)
                    if parser.done: break
            lifecycle.emit('last_response_byte', bytes=len(wire)); lifecycle.operation='RESPONSE_CLOSE'
        lifecycle.operation='NORMALIZE'
        body = parser.body() if parser else decode_http(bytes(wire), status)
        if not parser: lifecycle.emit('http_terminal', http_status=status)
        lifecycle.operation='BODY_BOUND'; ensure(len(body)<=pt.MAX_BODY, 'OPENROUTER_BODY_BOUND')
        lifecycle.emit('worker_terminal'); return pt.TransportResult(status, body, bytes(wire))
    except Exception as exc:
        cause = exc.reason if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, Exception) else exc
        if isinstance(exc, pt.TransportFault): reason=exc.reason
        elif time.monotonic()-lifecycle.started >= policy['worker_deadline_seconds']: reason='WORKER_DEADLINE'
        elif isinstance(cause, TimeoutError):
            reason='CONNECT_TIMEOUT' if lifecycle.phase in ('connect','proxy_tunnel') else 'INACTIVITY_TIMEOUT' if lifecycle.phase=='stream' else 'READ_TIMEOUT'
        else: reason='TRANSPORT_PROTOCOL_OR_CONNECTION_ERROR'
        diagnostics=pt.error_diagnostics(exc,lifecycle)
        lifecycle.emit('worker_error',diagnostics=diagnostics,**({'timeout_source':reason} if reason in pt.TIMEOUTS else {}))
        raise pt.TransportFault(reason,bytes(wire),status,diagnostics) from None


class OpenRouterAdapter:
    provider_id = 'openrouter'; capabilities = CAPABILITIES; wire_format = 'OPENROUTER_SSE_OR_HTTP_ERROR'
    generation_options = staticmethod(generation_options)
    credential = staticmethod(credential)

    def validate_route(self, scope):
        value=scope.get('network_route_policy')
        ensure(isinstance(value,dict) and value==route(value.get('mode')) and value['mode'] in CAPABILITIES.network_route_modes
            and scope.get('endpoint')==ENDPOINT, 'OPENROUTER_ROUTE')

    def validate_model(self, requested, returned):
        ensure(requested==MODEL and returned in MODEL_ALIASES, 'OPENROUTER_MODEL_MISMATCH')

    def validate_spend(self, scope):
        ensure(scope.get('spend_policy')=={'mode':'UNESTIMATED_SYNTHETIC','currency':None,'rates':None,
            'max_requests':2,'authorization':'G6-07T-PROVIDER2-REMOTE'}, 'OPENROUTER_UNESTIMATED_SCOPE')
        ensure(scope.get('total_guard_cny') is None and scope.get('reserved_upper_micro_cny') is None
            and scope['max_input_bytes']<=4096 and scope['max_output_tokens']<=8192, 'OPENROUTER_TOKEN_BOUND')
        ensure([s['id'] for s in scope['slots']]==['SHORT_SYNTHETIC','LONG_SYNTHETIC'], 'OPENROUTER_TWO_FIXED_SLOTS')

    def rates(self, scope, model): return None
    def reserve(self, scope, model, nbytes): return None

    def serialize(self, scope, model, messages):
        options = scope['generation_config']
        result={'model':model,'messages':messages,'max_tokens':scope['max_output_tokens'],'stream':True,
            'stream_options':{'include_usage':True},'temperature':options['temperature'],'provider':options['provider']}
        validate_payload(contract.canonical(result)); return result

    def worker_contract(self, scope): return {k:scope[k] for k in WORKER_KEYS}

    def validate_worker_contract(self, value):
        ensure(isinstance(value,dict) and set(value)==WORKER_KEYS and value.get('provider_id')==self.provider_id
            and value.get('api_protocol')=='chat_completions' and value.get('transport_contract_version')==contract.TRANSPORT_VERSION,
            'OPENROUTER_WORKER_CONTRACT')
        self.validate_route(value)

    def exchange(self, scope, payload, key, sink, command):
        return pt.worker_exchange(payload,key,scope['request_timeout_seconds'],scope['transport_policy'],command,WORKSPACE,sink,
            adapter_contract=self.worker_contract(scope))

    def worker_exchange(self, frame, sink):
        return http_exchange(frame['payload'].encode('utf-8'),frame['credential'],frame['transport_policy'],frame['adapter_contract'],sink)

    def decode(self, scope, wire): return decode_http(wire,200)
    def decode_http_result(self, scope, wire, status): return decode_http(wire,status)

    def terminal(self, scope, body):
        value=body.get('provider_terminal')
        ensure(isinstance(value,dict) and value.get('status') in ('completed','incomplete','failed')
            and value.get('event') in ('openrouter.finish_and_done','openrouter.stream.error','openrouter.http.error'), 'OPENROUTER_UNTRUSTED_TERMINAL')
        return value['status'],value['event'],value.get('reason')


def make_scope(batch_id, mode='SYSTEM_PROXY'):
    short='Write exactly one neutral sentence describing a blue cube on a white table.'
    long=('Produce 180 numbered lines, numbered 001 through 180. Each line must be a complete neutral sentence of 14 to 18 English words '
          'describing imaginary rivers, clouds, stones, trees, or boats. Use only invented observations, no people or real places. '
          'Write all 180 lines, without an introduction, summary, ellipsis, code fence, or request to continue.')
    return {'schema_version':contract.SCOPE_VERSION,'batch_id':batch_id,'principal_id':'SYNTHETIC_PROVIDER2_REMOTE',
        'provider_id':'openrouter','api_protocol':'chat_completions','endpoint':ENDPOINT,
        'validation_purpose':'SYNTHETIC_INDEPENDENT_VALIDATION','capabilities':CAPABILITIES.declaration(),
        'transport_contract_version':contract.TRANSPORT_VERSION,'source_binding':contract.runtime_source_binding(),
        'network_route_policy':route(mode),'automatic_paid_retries':0,'max_input_bytes':4096,'max_output_tokens':8192,
        'input_overhead_reserve_tokens':4096,'stream':True,'tools_allowed':False,'thinking':{'type':'disabled'},'reasoning_effort':None,
        'generation_config':{'stream':True,'max_output_tokens':8192,'reasoning':{'enabled':False,'effort':None},**generation_options()},
        'request_timeout_seconds':600,'transport_policy':{'version':pt.VERSION,'connect_timeout_seconds':20,
            'read_timeout_seconds':120,'worker_deadline_seconds':595},
        'spend_policy':{'mode':'UNESTIMATED_SYNTHETIC','currency':None,'rates':None,'max_requests':2,'authorization':'G6-07T-PROVIDER2-REMOTE'},
        'total_guard_cny':None,'reserved_upper_micro_cny':None,
        'slots':[{'id':name,'model':MODEL,'entity_label':'NEUTRAL_SYNTHETIC_TRANSPORT','user_text':text}
                 for name,text in [('SHORT_SYNTHETIC',short),('LONG_SYNTHETIC',long)]]}
