"""Frozen OpenAI Responses binding. No fallback, retry, polling or count API.

Native wire, terminal certainty, usable text and accounting are separate. The
local input proof registry is deliberately empty until an audited model-specific
framing proof exists; a scope flag or an operator-supplied count cannot enable it.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType
import time
import urllib.error
import urllib.request
from transcript_store import WORKSPACE, ensure
import provider_contract as contract
import provider_transport as pt

VERSION = 'APCORE_OPENAI_FORMAL_ADAPTER_1'
ENDPOINT = 'https://api.openai.com/v1/responses'
MODELS = ('gpt-6-astra', 'gpt-5.6-sol')
CANDIDATE = 'APCORE_SUCCESSOR_OPENAI_ASTRA_MAX_SOL_MAX_1'
BASE = 'persona_core/gpt6_optimization_v2/'
CONTRACT_DIR = BASE + 'successor_binding_contract_20260921_01/'
CONTRACT_SHA = '8b6d2ee98492b6ee6b3e157606b59de173cd315ecea2b85c9602c610fc6484ce'
CONFIG_PATH = BASE + 'model_configuration_qualification_20260920_01/CONFIGURATION_PREREGISTRATION.json'
CONFIG_SHA = 'b110549e5d76372cbbff79f4f919d92af89a482636498c7604a4b6c45fe9e0ff'
POLICY_PATH = BASE + 'model_quality_acceptance_20260920_01/POLICY_FREEZE_MANIFEST.json'
POLICY_SHA = 'a54396c3c07088b07ad2f3682b8ea91c0a73ac10e9edd1195599e11ff784ddf5'
CAPABILITIES = contract.Capabilities(('responses',), ('DIRECT_NO_PROXY',),
    'openai_responses_native_terminal', supports_reasoning=True)
WORKER_KEYS = {'provider_id','api_protocol','endpoint','network_route_policy','transport_contract_version'}
# An entry must contain a reviewed exact tokenizer implementation AND a proof
# covering roles, message count, Unicode and all implicit Responses formatting.
# Samples and the 4096-token allowance are not such a proof.
LOCAL_INPUT_PROOFS = MappingProxyType({})


def strict_json(data):
    def pairs(values):
        result = {}
        for k, v in values:
            ensure(k not in result, 'OPENAI_DUPLICATE_JSON_KEY')
            result[k] = v
        return result
    def invalid(value):
        raise ValueError('OPENAI_NONFINITE_JSON')
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)


def reference(path):
    p = Path(path).resolve()
    ensure(p.is_relative_to(WORKSPACE.resolve()) and p.is_file(), 'OPENAI_REFERENCE_PATH')
    return {'path':p.relative_to(WORKSPACE).as_posix(), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}


def verify_reference(value):
    ensure(isinstance(value,dict) and set(value)=={'path','sha256'}, 'OPENAI_REFERENCE_SHAPE')
    p = (WORKSPACE/value['path']).resolve()
    ensure(reference(p)==value, 'OPENAI_IDENTITY_MISMATCH')
    return p


def frozen_contract():
    p = WORKSPACE/CONTRACT_DIR/'CONTRACT_FREEZE_MANIFEST.json'
    ensure(reference(p)['sha256']==CONTRACT_SHA, 'OPENAI_CONTRACT_FREEZE_CHANGED')
    manifest = strict_json(p.read_bytes())
    for name, digest in manifest['files'].items():
        verify_reference({'path':name,'sha256':digest})
    return {name:strict_json((WORKSPACE/CONTRACT_DIR/name).read_bytes()) for name in
        ('REQUEST_SERIALIZATION_CONTRACT.json','PROVIDER_SCOPE_CONTRACT.json')}


def route():
    return {'version':'apcore-openai-route-1','mode':'DIRECT_NO_PROXY','host':'api.openai.com'}


def template():
    return frozen_contract()['REQUEST_SERIALIZATION_CONTRACT.json']['payload_template']


def generation_options():
    return {k:v for k,v in template().items() if k not in ('model','input')}


def validate_payload(payload):
    value = strict_json(payload)
    expected = template()
    ensure(isinstance(value,dict) and set(value)==set(expected), 'OPENAI_REQUEST_FIELDS')
    ensure(value['model'] in MODELS, 'OPENAI_MODEL_NOT_ALLOWED')
    for k in expected.keys()-{'model','input'}:
        # Canonical equality preserves false vs zero, integers vs booleans, and
        # recursively rejects unknown fields rather than silently removing them.
        ensure(contract.canonical(value[k])==contract.canonical(expected[k]), 'OPENAI_REQUEST_CONTROL_'+k)
    messages = value['input']
    ensure(isinstance(messages,list) and messages and all(isinstance(m,dict) and set(m)=={'role','content'}
        and m['role'] in ('system','user','assistant') and isinstance(m['content'],str) for m in messages), 'OPENAI_INPUT_SHAPE')
    ensure(messages[-1]['role']=='user', 'OPENAI_LAST_MESSAGE')
    ensure(len(contract.canonical(messages))<=24576, 'OPENAI_INPUT_BYTES_EXCEEDED')
    ensure(contract.canonical(value)==payload, 'OPENAI_NONCANONICAL_PAYLOAD')
    return value


def input_proof_ready(scope):
    proof = scope.get('input_bound_proof')
    return isinstance(proof,dict) and proof.get('proof_reference_sha256') in LOCAL_INPUT_PROOFS


def local_input_bound(scope, payload):
    value = validate_payload(payload)
    ensure(input_proof_ready(scope), 'INPUT_BOUND_PROOF_NOT_READY')
    proof = scope['input_bound_proof']
    calculator = LOCAL_INPUT_PROOFS[proof['proof_reference_sha256']]
    receipt = calculator(scope, value)
    verify_input_receipt(scope, payload, receipt)
    return receipt


def verify_input_receipt(scope, payload, receipt):
    value = validate_payload(payload); messages = value['input']
    ensure(isinstance(receipt,dict) and receipt.get('version')=='APCORE_INPUT_BOUND_RECEIPT_1', 'INPUT_BOUND_NOT_PROVEN')
    ensure(input_proof_ready(scope) and receipt.get('proof_reference_sha256')==scope['input_bound_proof']['proof_reference_sha256'], 'INPUT_BOUND_UNTRUSTED_PROOF')
    ensure(receipt.get('request_sha256')==hashlib.sha256(payload).hexdigest()
        and receipt.get('messages_sha256')==contract.digest(messages) and receipt.get('model_id')==value['model']
        and receipt.get('source_binding')==scope['source_binding'] and receipt.get('scope_sha256')==contract.digest(scope), 'INPUT_BOUND_IDENTITY_MISMATCH')
    ensure(receipt.get('host_bytes')==len(contract.canonical(messages)) and receipt.get('message_count')==len(messages), 'INPUT_BOUND_CONTENT_MISMATCH')
    for k in ('content_token_count','framing_upper_tokens','input_upper_tokens'):
        ensure(type(receipt.get(k)) is int and receipt[k]>=0, 'INPUT_BOUND_INVALID_COUNT')
    ensure(receipt['input_upper_tokens']==receipt['content_token_count']+receipt['framing_upper_tokens']
        and receipt['input_upper_tokens']<=28672, 'INPUT_BOUND_EXCEEDED')
    ensure(all(isinstance(receipt.get(k),str) and receipt[k] for k in
        ('tokenizer','tokenizer_version','tokenizer_artifact_sha256','count_method')), 'INPUT_BOUND_ARTIFACT_MISSING')
    ensure(receipt==LOCAL_INPUT_PROOFS[receipt['proof_reference_sha256']](scope,value), 'INPUT_BOUND_RECOMPUTATION_MISMATCH')
    return receipt


def credential():
    value = os.environ.get('OPENAI_API_KEY','')
    if not value.strip():
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as key:
                value = winreg.QueryValueEx(key,'OPENAI_API_KEY')[0]
        except (ImportError,FileNotFoundError): value = ''
    ensure(isinstance(value,str) and value.strip() and not any(c in value for c in '\r\n'), 'OPENAI_CREDENTIAL_ABSENT_OR_INVALID')
    return value.strip()


class OpenAIAssembly:
    """Incremental UTF-8/SSE framing; only a consistent native terminal counts."""
    def __init__(self, lifecycle):
        self.lifecycle=lifecycle; self.buffer=b''; self.data=[]; self.event=None
        self.done=False; self.response=None; self.identity={}; self.sequence=-1
        self.deltas={}; self.text_done={}; self.item_ids={}; self.items_done={}; self.parts_done={}; self.records=0

    def feed(self, block):
        self.buffer += block
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1); line=line.rstrip(b'\r')
            if line.startswith(b'data:'): self.data.append(line[5:].lstrip(b' '))
            elif line.startswith(b'event:'):
                ensure(self.event is None, 'OPENAI_DUPLICATE_EVENT_FIELD'); self.event=line[6:].strip().decode('utf-8')
            elif not line:
                if self.data: self.record(b'\n'.join(self.data))
                self.data=[]; self.event=None
            elif not line.startswith(b':'): ensure(False, 'OPENAI_INVALID_SSE_LINE')

    def bind_response(self, response):
        ensure(isinstance(response,dict), 'OPENAI_RESPONSE_SHAPE')
        for key in ('id','model'):
            value=response.get(key)
            ensure(isinstance(value,str) and value and (key not in self.identity or self.identity[key]==value), 'OPENAI_RESPONSE_IDENTITY_CHANGED')
            self.identity[key]=value

    def index(self, obj, content=False):
        i=obj.get('output_index'); item_id=obj.get('item_id')
        ensure(type(i) is int and i>=0 and isinstance(item_id,str) and item_id, 'OPENAI_OUTPUT_INDEX')
        ensure(i not in self.item_ids or self.item_ids[i]==item_id, 'OPENAI_ITEM_ID_CHANGED')
        ensure(all(index==i or identity!=item_id for index,identity in self.item_ids.items()), 'OPENAI_DUPLICATE_ITEM_ID')
        self.item_ids[i]=item_id
        if not content: return i
        c=obj.get('content_index'); ensure(type(c) is int and c>=0,'OPENAI_CONTENT_INDEX')
        return i,c

    def record(self, data):
        ensure(not self.done, 'OPENAI_DATA_AFTER_TERMINAL')
        obj=strict_json(data)
        ensure(isinstance(obj,dict) and isinstance(obj.get('type'),str), 'OPENAI_EVENT_SHAPE')
        kind=obj['type']; seq=obj.get('sequence_number')
        ensure(type(seq) is int and seq>self.sequence, 'OPENAI_SEQUENCE_CONFLICT')
        ensure(self.event in (None,kind), 'OPENAI_EVENT_TYPE_MISMATCH')
        self.sequence=seq; self.records+=1
        if 'response_id' in obj:
            ensure(obj['response_id']==self.identity.get('id'), 'OPENAI_EVENT_RESPONSE_CHANGED')
        if kind in ('response.created','response.in_progress','response.completed','response.incomplete','response.failed'):
            response=obj.get('response'); self.bind_response(response)
            status=kind.split('.')[-1]
            if status in ('completed','incomplete','failed'):
                ensure(response.get('status')==status, 'OPENAI_TERMINAL_STATUS_MISMATCH')
                ensure(status!='failed' or isinstance(response.get('error'),dict), 'OPENAI_FAILED_ERROR_MISSING')
                self.response=response; self.done=True; self.lifecycle.emit('stream_done')
        elif kind in ('response.output_item.added','response.output_item.done'):
            item=obj.get('item'); ensure(isinstance(item,dict), 'OPENAI_ITEM_SHAPE')
            i=self.index(dict(obj,item_id=item.get('id')))
            if kind.endswith('.done'):
                ensure(i not in self.items_done, 'OPENAI_DUPLICATE_ITEM_DONE'); self.items_done[i]=item
        elif kind in ('response.content_part.added','response.content_part.done'):
            key=self.index(obj,True); part=obj.get('part'); ensure(isinstance(part,dict), 'OPENAI_PART_SHAPE')
            if kind.endswith('.done'):
                ensure(key not in self.parts_done, 'OPENAI_DUPLICATE_PART_DONE'); self.parts_done[key]=part
        elif kind in ('response.output_text.delta','response.output_text.done'):
            key=self.index(obj,True)
            if kind.endswith('.delta'):
                ensure(key not in self.text_done and isinstance(obj.get('delta'),str), 'OPENAI_TEXT_DELTA')
                self.deltas.setdefault(key,[]).append(obj['delta']); self.lifecycle.emit('first_token')
            else:
                ensure(key not in self.text_done and isinstance(obj.get('text'),str), 'OPENAI_TEXT_DONE')
                self.text_done[key]=obj['text']
        elif kind in ('response.reasoning_summary_part.added','response.reasoning_summary_part.done',
                      'response.reasoning_summary_text.delta','response.reasoning_summary_text.done',
                      'response.reasoning_text.delta','response.reasoning_text.done',
                      'response.refusal.delta','response.refusal.done','response.output_text.annotation.added'):
            self.index(obj, 'content_index' in obj)  # Private wire only; never display reasoning/refusals.
        else: ensure(False,'OPENAI_UNRECOGNIZED_EVENT')

    def body(self):
        ensure(self.done and self.response is not None and not self.buffer.strip() and not self.data, 'OPENAI_TERMINAL_MISSING')
        response=self.response; output=response.get('output')
        ensure(isinstance(output,list), 'OPENAI_FINAL_OUTPUT_SHAPE')
        texts={}; visible=[]; messages=0; unusable=False
        for i,item in enumerate(output):
            ensure(isinstance(item,dict) and isinstance(item.get('id'),str), 'OPENAI_FINAL_ITEM_SHAPE')
            ensure(i not in self.item_ids or self.item_ids[i]==item['id'], 'OPENAI_FINAL_ITEM_ID_CHANGED')
            ensure(i not in self.items_done or self.items_done[i]==item, 'OPENAI_FINAL_ITEM_CHANGED')
            ensure(all(previous.get('id')!=item['id'] for previous in output[:i]), 'OPENAI_DUPLICATE_FINAL_ITEM')
            if item.get('type')=='reasoning': continue
            if item.get('type')!='message' or item.get('role')!='assistant': unusable=True; continue
            messages+=1
            ensure(isinstance(item.get('content'),list), 'OPENAI_FINAL_CONTENT_SHAPE')
            for c,part in enumerate(item['content']):
                ensure(isinstance(part,dict), 'OPENAI_FINAL_PART_SHAPE')
                key=(i,c)
                ensure(key not in self.parts_done or self.parts_done[key]==part, 'OPENAI_FINAL_PART_CHANGED')
                if part.get('type')!='output_text': unusable=True; continue
                ensure(isinstance(part.get('text'),str), 'OPENAI_FINAL_TEXT_TYPE')
                texts[key]=part['text']; visible.append(part['text'])
        ensure(all(i<len(output) for i in self.item_ids), 'OPENAI_UNBOUND_ITEM')
        for key,value in self.deltas.items(): ensure(key in texts and ''.join(value)==texts[key], 'OPENAI_DELTA_FINAL_MISMATCH')
        for key,value in self.text_done.items(): ensure(key in texts and value==texts[key], 'OPENAI_TEXT_FINAL_MISMATCH')
        for i,c in self.parts_done: ensure(i<len(output) and c<len(output[i].get('content',[])), 'OPENAI_UNBOUND_PART')
        status=response['status']; text=''.join(visible)
        rejection=None
        if status!='completed': rejection='OPENAI_'+status.upper()
        elif unusable or messages!=1 or not text.strip(): rejection='OPENAI_UNUSABLE_VISIBLE_OUTPUT'
        usage=response.get('usage')
        normalized=None
        if isinstance(usage,dict):
            normalized={'prompt_tokens':usage.get('input_tokens'),'completion_tokens':usage.get('output_tokens'),
                'total_tokens':usage.get('total_tokens'),'completion_tokens_details':usage.get('output_tokens_details')}
        return contract.canonical({'id':response['id'],'model':response['model'],'native_response':response,
            'native_usage':usage,'native_receipt_version':'APCORE_OPENAI_NATIVE_RECEIPT_1',
            'usage':normalized,'responses_api_status':status,
            'choices':[{'index':0,'message':{'role':'assistant','content':text},'finish_reason':'stop' if status=='completed' else 'length'}],
            'provider_terminal':{'status':status,'event':'response.'+status,'reason':rejection},
            'stream_observation':{'records':self.records}})


def decode_http(wire,status):
    # An HTTP error alone does not establish the generation's native terminal.
    ensure(status==200, 'OPENAI_HTTP_OUTCOME_UNKNOWN')
    parser=OpenAIAssembly(pt.Lifecycle()); parser.feed(wire); return parser.body()


def http_exchange(payload,key,policy,worker_contract,sink=lambda event:None,opener_factory=None):
    OpenAIAdapter().validate_worker_contract(worker_contract); validate_payload(payload)
    lifecycle=pt.Lifecycle(sink,policy); lifecycle.emit('worker_started'); wire=bytearray(); status=None
    try:
        opener=(opener_factory(lifecycle) if opener_factory else
            urllib.request.build_opener(urllib.request.ProxyHandler({}),*pt._handlers(lifecycle)))
        request=urllib.request.Request(ENDPOINT,data=payload,method='POST',headers={
            'Authorization':'Bearer '+key,'Content-Type':'application/json','Accept':'text/event-stream',
            'User-Agent':'Amadeus-APCORE-OpenAI-Formal/1'})
        lifecycle.operation='HTTP_OPEN'
        try: response=opener.open(request,timeout=lifecycle.remaining(policy['connect_timeout_seconds']))
        except urllib.error.HTTPError as exc: response=exc
        with response:
            status=response.status; lifecycle.emit('headers_complete',http_status=status); lifecycle.phase='stream'
            parser=OpenAIAssembly(lifecycle) if status==200 else None
            while True:
                lifecycle.operation='HTTP_READ1'; wait=lifecycle.remaining(policy['read_timeout_seconds'])
                try: response.fp.raw._sock.settimeout(wait)
                except AttributeError: pass
                block=response.read1(min(8192,pt.MAX_WIRE+1-len(wire)))
                if not block: break
                wire.extend(block); lifecycle.emit('first_response_byte')
                ensure(len(wire)<=pt.MAX_WIRE,'OPENAI_WIRE_BOUND')
                if parser: parser.feed(block)
                if parser and parser.done: break
            lifecycle.emit('last_response_byte',bytes=len(wire))
        body=parser.body() if parser else decode_http(bytes(wire),status)
        ensure(len(body)<=pt.MAX_BODY,'OPENAI_BODY_BOUND'); lifecycle.emit('worker_terminal')
        return pt.TransportResult(status,body,bytes(wire))
    except Exception as exc:
        cause=exc.reason if isinstance(exc,urllib.error.URLError) and isinstance(exc.reason,Exception) else exc
        reason=('WORKER_DEADLINE' if time.monotonic()-lifecycle.started>=policy['worker_deadline_seconds'] else
            ('CONNECT_TIMEOUT' if lifecycle.phase in ('connect','proxy_tunnel') else 'INACTIVITY_TIMEOUT')
            if isinstance(cause,TimeoutError) else 'TRANSPORT_PROTOCOL_OR_CONNECTION_ERROR')
        raise pt.TransportFault(reason,bytes(wire),status,pt.error_diagnostics(exc,lifecycle)) from None


class OpenAIAdapter:
    provider_id='openai'; capabilities=CAPABILITIES; wire_format='OPENAI_RESPONSES_NATIVE_SSE'
    credential=staticmethod(credential)

    def validate_route(self,scope):
        ensure(scope.get('endpoint')==ENDPOINT and scope.get('network_route_policy')==route(), 'OPENAI_ROUTE_MISMATCH')

    def validate_model(self,requested,returned):
        ensure(requested in MODELS and returned==requested, 'OPENAI_MODEL_MISMATCH')

    def validate_spend(self,scope): contract.check_formal_spend(scope)
    def rates(self,scope,model): return scope['spend_policy']['rates_usd_per_million'][model]
    def reserve(self,scope,model,nbytes): return contract.formal_reserve(scope,model,28672)

    def serialize(self,scope,model,messages):
        self.validate_model(model,model)
        ensure(scope.get('generation_config')==generation_options(), 'OPENAI_GENERATION_CHANGED')
        result=dict(scope['generation_config'],model=model,input=messages)
        validate_payload(contract.canonical(result)); return result

    def worker_contract(self,scope): return {k:scope[k] for k in WORKER_KEYS}

    def validate_worker_contract(self,value):
        ensure(isinstance(value,dict) and set(value)==WORKER_KEYS and value.get('provider_id')=='openai'
            and value.get('api_protocol')=='responses' and value.get('transport_contract_version')==contract.TRANSPORT_VERSION,'OPENAI_WORKER_CONTRACT')
        self.validate_route(value)

    def exchange(self,scope,payload,key,sink,command):
        local_input_bound(scope,payload)  # No alternate direct adapter path around the gate.
        return pt.worker_exchange(payload,key,scope['request_timeout_seconds'],scope['transport_policy'],command,WORKSPACE,sink,
            adapter_contract=self.worker_contract(scope))

    def worker_exchange(self,frame,sink):
        return http_exchange(frame['payload'].encode('utf-8'),frame['credential'],frame['transport_policy'],frame['adapter_contract'],sink)

    def decode(self,scope,wire): return decode_http(wire,200)
    def decode_http_result(self,scope,wire,status): return decode_http(wire,status)

    def terminal(self,scope,body):
        terminal=body.get('provider_terminal',{})
        ensure(terminal.get('status') in ('completed','incomplete','failed') and
            terminal.get('event')=='response.'+terminal['status'], 'OPENAI_UNTRUSTED_TERMINAL')
        return terminal['status'],terminal['event'],terminal.get('reason')

    def verify_effective_identity(self,scope,body,model):
        response=body['native_response']; self.validate_model(model,response.get('model'))
        def contains(actual,expected):
            if isinstance(expected,dict):
                return isinstance(actual,dict) and all(k in actual and contains(actual[k],v) for k,v in expected.items())
            return contract.canonical(actual)==contract.canonical(expected)
        for k in ('reasoning','service_tier','max_output_tokens','store','background','truncation','tools','tool_choice','parallel_tool_calls','text'):
            ensure(k in response and contains(response[k],scope['generation_config'][k]), 'OPENAI_EFFECTIVE_CONTROL_'+k)
        return True
