"""Deterministic local streaming provider, with no network or credential access.

This is synthetic transport evidence only. Native events deliberately differ
from Responses and Chat Completions so their terminal assumptions cannot leak.
"""
from __future__ import annotations
import hashlib
import json
from transcript_store import ensure, WORKSPACE
import provider_contract as contract
import provider_transport as pt

PROTOCOL = 'fixture_events_v1'
ROUTE = {'version': 'apcore-local-route-1', 'mode': 'LOCAL_ONLY', 'host': None}
ENDPOINT = 'local://deterministic-fixture'
CAPABILITIES = contract.Capabilities((PROTOCOL,), ('LOCAL_ONLY',), 'fixture.seal',
                                    supports_reasoning=True, network_access=False)


def _strict_json(data):
    def pairs(items):
        obj = {}
        for k, v in items:
            ensure(k not in obj, 'FIXTURE_DUPLICATE_KEY'); obj[k] = v
        return obj
    def constant(_):
        raise ValueError('FIXTURE_NONFINITE_VALUE')
    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)


class FixtureAssembly:
    def __init__(self, lifecycle):
        self.lifecycle = lifecycle; self.buffer = b''; self.seq = 0; self.identity = None
        self.text = []; self.seal = None

    def feed(self, block):
        self.buffer += block
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            obj = _strict_json(line)
            ensure(self.seal is None and isinstance(obj, dict), 'FIXTURE_TRAILING_OR_INVALID_EVENT')
            ensure(set(obj) == {'seq', 'id', 'model', 'type', 'data'}, 'FIXTURE_EVENT_SHAPE')
            ensure(type(obj['seq']) is int and obj['seq'] == self.seq, 'FIXTURE_SEQUENCE')
            identity = (obj['id'], obj['model'])
            ensure(all(isinstance(v, str) and v for v in identity), 'FIXTURE_IDENTITY')
            ensure(self.identity in (None, identity), 'FIXTURE_IDENTITY_CHANGED')
            if self.seq == 0: ensure(obj['type'] == 'fixture.open', 'FIXTURE_OPEN_REQUIRED')
            else: ensure(obj['type'] != 'fixture.open', 'FIXTURE_DUPLICATE_OPEN')
            self.identity = identity; self.seq += 1
            kind, data = obj['type'], obj['data']
            if kind in ('fixture.text', 'fixture.thought'):
                ensure(isinstance(data, str), 'FIXTURE_TEXT_SHAPE')
                if kind == 'fixture.text':
                    self.text.append(data)
                    if data: self.lifecycle.emit('first_token')
                elif data: self.lifecycle.emit('first_reasoning_token')
            elif kind == 'fixture.seal':
                ensure(isinstance(data, dict) and data.get('outcome') in ('complete', 'failed', 'incomplete'), 'FIXTURE_TERMINAL_STATUS')
                self.seal = data
                self.lifecycle.emit('provider_finish', finish_reason='stop' if data['outcome'] == 'complete' else 'aborted')
            else: ensure(kind == 'fixture.open' and data == {}, 'FIXTURE_EVENT_TYPE')

    def body(self):
        ensure(self.seal is not None and not self.buffer, 'FIXTURE_TERMINAL_MISSING')
        status = {'complete': 'completed', 'failed': 'failed', 'incomplete': 'incomplete'}[self.seal['outcome']]
        text = ''.join(self.text); reason = None; usage = None
        try:
            native = self.seal.get('meter')
            ensure(isinstance(native, dict), 'INVALID_USAGE')
            usage = {'prompt_tokens': native.get('read'), 'completion_tokens': native.get('write'),
                     'total_tokens': native.get('total'), 'prompt_cache_hit_tokens': native.get('cached', 0),
                     'completion_tokens_details': {'reasoning_tokens': native.get('thought', 0)}}
            contract.validate_usage(usage)
        except (ValueError, TypeError): reason = 'FIXTURE_INVALID_USAGE'; usage = None
        if status != 'completed': reason = 'FIXTURE_' + status.upper()
        elif not isinstance(self.seal.get('visible'), str) or self.seal['visible'] != text: reason = 'FIXTURE_VISIBLE_MISMATCH'
        if reason: text = ''
        return contract.canonical({'id': self.identity[0], 'model': self.identity[1], 'usage': usage,
            'choices': [{'index': 0, 'finish_reason': 'stop' if status == 'completed' else 'aborted',
                         'message': {'role': 'assistant', 'content': text}}],
            'provider_terminal': {'status': status, 'event': 'fixture.seal', 'reason': reason}})


def synthetic_wire(payload):
    request = _strict_json(payload)
    ensure(isinstance(request, dict) and set(request) == {'model', 'dialogue', 'output_limit', 'stream', 'reasoning'}, 'FIXTURE_REQUEST_SHAPE')
    ensure(request['stream'] is True and type(request['output_limit']) is int and 1 <= request['output_limit'] <= 131072, 'FIXTURE_OUTPUT_BOUND')
    ensure(request['model'] in ('fixture-text-1', 'fixture-text-2'), 'FIXTURE_MODEL')
    messages = request['dialogue']
    ensure(isinstance(messages, list) and messages and all(isinstance(m, dict) and set(m) == {'role', 'content'}
        and m['role'] in ('system', 'user', 'assistant') and isinstance(m['content'], str) for m in messages), 'FIXTURE_MESSAGES')
    ensure(messages[-1]['role'] == 'user', 'FIXTURE_CURRENT_USER')
    case = messages[-1]['content']
    allowed = {'fixture:' + name for name in ('short', 'long', 'failed', 'incomplete', 'disconnect', 'malformed_usage', 'missing_usage', 'reasoning_only')}
    ensure(case in allowed, 'SYNTHETIC_FIXTURE_INPUT_REQUIRED')
    rid = 'fixture_' + hashlib.sha256(payload).hexdigest()[:24]
    events = []
    def add(kind, data):
        events.append({'seq': len(events), 'id': rid, 'model': request['model'], 'type': kind, 'data': data})
    add('fixture.open', {}); add('fixture.thought', 'Private synthetic reasoning, never an answer.')
    chunks = (['Synthetic visible answer.'] if case != 'fixture:long' else ['Synthetic long output.\n'] * 128)
    if case in ('fixture:reasoning_only', 'fixture:failed', 'fixture:incomplete'): chunks = []
    for chunk in chunks: add('fixture.text', chunk)
    if case != 'fixture:disconnect':
        output = 132 if case == 'fixture:long' else 8
        meter = {'read': 10, 'write': output, 'total': 10 + output, 'cached': 2, 'thought': 4}
        if case == 'fixture:malformed_usage': meter['write'] = True
        if case == 'fixture:missing_usage': meter = None
        outcome = 'failed' if case == 'fixture:failed' else 'incomplete' if case == 'fixture:incomplete' or output > request['output_limit'] else 'complete'
        add('fixture.seal', {'outcome': outcome, 'visible': ''.join(chunks), 'meter': meter})
    return b''.join(contract.canonical(event) + b'\n' for event in events)


def local_exchange(payload, policy, sink):
    lifecycle = pt.Lifecycle(sink, policy); lifecycle.emit('worker_started')
    wire = b''
    try:
        wire = synthetic_wire(payload)
        ensure(len(wire) <= pt.MAX_WIRE, 'FIXTURE_WIRE_BOUND')
        parser = FixtureAssembly(lifecycle)
        for offset in range(0, len(wire), 17): parser.feed(wire[offset:offset + 17])
        body = parser.body()
        lifecycle.emit('worker_terminal')
        return pt.TransportResult(200, body, wire)
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise pt.TransportFault('TRANSPORT_PROTOCOL_OR_CONNECTION_ERROR', wire, 200) from None


class LocalFixtureAdapter:
    provider_id = 'local_fixture'
    capabilities = CAPABILITIES
    wire_format = 'FIXTURE_NDJSON'

    def validate_route(self, scope):
        ensure(scope.get('endpoint') == ENDPOINT and scope.get('network_route_policy') == ROUTE, 'FIXTURE_LOCAL_ROUTE_REQUIRED')

    def validate_model(self, requested, returned):
        ensure(requested in ('fixture-text-1', 'fixture-text-2') and requested == returned, 'FIXTURE_MODEL_MISMATCH')

    def validate_spend(self, scope):
        ensure(scope.get('spend_policy') == {'mode': 'UNESTIMATED', 'currency': None, 'rates': None}
               and scope.get('total_guard_cny') is None and scope.get('reserved_upper_micro_cny') is None, 'FIXTURE_UNESTIMATED_POLICY')

    def rates(self, scope, model): return None
    def reserve(self, scope, model, nbytes): return None
    def credential(self): return 'LOCAL_FIXTURE_NO_SECRET'

    def serialize(self, scope, model, messages):
        return {'model': model, 'dialogue': messages, 'output_limit': scope['max_output_tokens'],
                'stream': True, 'reasoning': scope['generation_config']['reasoning']}

    def exchange(self, scope, payload, credential, sink, command):
        return pt.worker_exchange(payload, credential, scope['request_timeout_seconds'], scope['transport_policy'],
            command, WORKSPACE, sink, adapter_contract={'provider_id': self.provider_id,
                'api_protocol': scope['api_protocol'], 'endpoint': scope['endpoint'],
                'network_route_policy': scope['network_route_policy'], 'transport_contract_version': scope['transport_contract_version']})

    def decode(self, scope, wire):
        parser = FixtureAssembly(pt.Lifecycle()); parser.feed(wire)
        return parser.body()

    def terminal(self, scope, body):
        value = body['provider_terminal']
        ensure(value.get('status') in ('completed', 'failed', 'incomplete') and value.get('event') == 'fixture.seal', 'FIXTURE_UNTRUSTED_TERMINAL')
        return value['status'], value['event'], value.get('reason')


def validate_worker_contract(value):
    ensure(isinstance(value, dict) and set(value) == {'provider_id', 'api_protocol', 'endpoint', 'network_route_policy', 'transport_contract_version'}, 'ADAPTER_WORKER_CONTRACT')
    ensure(value['provider_id'] == LocalFixtureAdapter.provider_id and value['api_protocol'] == PROTOCOL
           and value['transport_contract_version'] == contract.TRANSPORT_VERSION, 'ADAPTER_WORKER_NOT_LOCAL_FIXTURE')
    LocalFixtureAdapter().validate_route(value)


def make_scope(batch_id, principal_id='SYNTHETIC_PROVIDER2', case='short', model='fixture-text-1'):
    return {'schema_version': contract.SCOPE_VERSION, 'batch_id': batch_id, 'principal_id': principal_id,
        'provider_id': 'local_fixture', 'api_protocol': PROTOCOL, 'endpoint': ENDPOINT,
        'validation_purpose': 'SYNTHETIC_INDEPENDENT_VALIDATION', 'capabilities': CAPABILITIES.declaration(),
        'transport_contract_version': contract.TRANSPORT_VERSION, 'source_binding': contract.runtime_source_binding(),
        'network_route_policy': dict(ROUTE), 'automatic_paid_retries': 0,
        'max_input_bytes': 4096, 'max_output_tokens': 512, 'input_overhead_reserve_tokens': 4096,
        'stream': True, 'tools_allowed': False, 'thinking': {'type': 'disabled'}, 'reasoning_effort': None,
        'generation_config': {'stream': True, 'max_output_tokens': 512, 'reasoning': {'enabled': False, 'effort': None}},
        'request_timeout_seconds': 5, 'transport_policy': {'version': pt.VERSION,
            'connect_timeout_seconds': 1, 'read_timeout_seconds': 1, 'worker_deadline_seconds': 4},
        'spend_policy': {'mode': 'UNESTIMATED', 'currency': None, 'rates': None},
        'total_guard_cny': None, 'reserved_upper_micro_cny': None,
        'slots': [{'id': 'SYNTHETIC_1', 'model': model, 'entity_label': 'SYNTHETIC_TRANSPORT_ONLY', 'user_text': 'fixture:' + case}]}
