"""Explicit adapter registry. Providers own serialization and native contracts."""
from __future__ import annotations
import json
from types import MappingProxyType
from transcript_store import ensure, WORKSPACE
import provider_contract as contract
import provider_transport as pt


class DeepSeekAdapter:
    provider_id = 'deepseek'
    capabilities = contract.Capabilities(('responses', 'chat_completions'), ('DIRECT_NO_PROXY', 'SYSTEM_PROXY'),
        'responses_terminal_or_chat_finish_and_done', supports_reasoning=True)

    def validate_route(self, scope):
        from provider_network_route import check_route_policy
        from provider import RESPONSES_ENDPOINT, CHAT_COMPLETIONS_ENDPOINT
        check_route_policy(scope.get('network_route_policy'))
        ensure(scope.get('endpoint') == {'responses': RESPONSES_ENDPOINT, 'chat_completions': CHAT_COMPLETIONS_ENDPOINT}[scope['api_protocol']], 'ADAPTER_ENDPOINT_MISMATCH')
        if scope['api_protocol'] == 'responses':
            ensure(scope.get('thinking') == {'type': 'enabled'} and scope.get('reasoning_effort') == 'max', 'DEEPSEEK_RESPONSES_REASONING_POLICY')

    def validate_model(self, requested, returned):
        from provider import validate_provider_model, RATES
        ensure(requested in RATES, 'ADAPTER_MODEL_NOT_ALLOWED')
        validate_provider_model(requested, returned, strict_version=True)

    def validate_spend(self, scope):
        from provider import RATES
        from decimal import Decimal
        policy = scope.get('spend_policy')
        ensure(isinstance(policy, dict) and policy.get('mode') == 'REVIEWED_RATES' and policy.get('currency') == 'CNY', 'PAID_PROVIDER_REQUIRES_REVIEWED_PRICE')
        rates = {s['model']: list(RATES[s['model']]) for s in scope['slots']}
        ensure(policy.get('rates') == rates, 'ADAPTER_PRICE_POLICY_MISMATCH')
        guard = scope.get('total_guard_cny')
        ensure(type(guard) in (int, float) and 0 < guard <= 150, 'FINITE_SPEND_GUARD_REQUIRED')
        bound = sum(self.reserve(scope, s['model'], scope['max_input_bytes']) for s in scope['slots'])
        ensure(scope.get('reserved_upper_micro_cny') == bound and bound <= int(Decimal(str(guard))*1_000_000), 'SCOPE_RESERVE_MISMATCH')
        ensure(isinstance(policy.get('price_evidence'), dict) and policy['price_evidence'].get('sources')
               and policy['price_evidence'].get('verified_date'), 'PRICE_EVIDENCE_REQUIRED')

    def rates(self, scope, model):
        return scope['spend_policy']['rates'][model]

    def reserve(self, scope, model, nbytes):
        rates = self.rates(scope, model)
        return (nbytes + scope['input_overhead_reserve_tokens']) * rates[0] + scope['max_output_tokens'] * rates[1]

    def credential(self):
        from provider import existing_credential
        return existing_credential()

    def serialize(self, scope, model, messages):
        if scope.get('api_protocol') == 'responses':
            return {'model': model, 'input': messages, 'max_output_tokens': scope['max_output_tokens'],
                    'stream': True, 'reasoning': {'effort': scope['reasoning_effort']}}
        result = {'model': model, 'messages': messages, 'max_tokens': scope['max_output_tokens'],
                  'stream': scope['stream'], 'thinking': scope['thinking']}
        if scope['thinking']['type'] == 'enabled': result['reasoning_effort'] = scope['reasoning_effort']
        if scope['stream']: result['stream_options'] = {'include_usage': True}
        return result

    def exchange(self, scope, payload, credential, sink, command):
        return pt.worker_exchange(payload, credential, scope['request_timeout_seconds'], scope['transport_policy'],
            command, WORKSPACE, sink, responses=scope['api_protocol'] == 'responses',
            network_route_policy=scope['network_route_policy'])

    def decode(self, scope, wire):
        parser = (pt.ResponsesAssembly if scope['api_protocol'] == 'responses' else pt.StreamAssembly)(pt.Lifecycle())
        parser.feed(wire)
        body = parser.body()
        if scope['api_protocol'] == 'chat_completions':
            ensure(not parser.buffer.strip() and not parser.data, 'CHAT_UNFINISHED_RECORD')
        return body

    def terminal(self, scope, body):
        if scope['api_protocol'] == 'responses':
            status = body.get('responses_api_status')
            ensure(status in ('completed', 'incomplete', 'failed'), 'UNTRUSTED_TERMINAL')
            rejection = body.get('responses_terminal_rejection') or {}
            return status, 'response.' + status, rejection.get('reason')
        finish = body['choices'][0]['finish_reason']
        return ('completed' if finish == 'stop' else 'incomplete'), 'chat.finish_and_done', None


class ProviderRegistry:
    def __init__(self, adapters):
        values = {}
        for adapter in adapters:
            ensure(isinstance(adapter.provider_id, str) and adapter.provider_id not in values, 'DUPLICATE_PROVIDER')
            ensure(isinstance(adapter.capabilities, contract.Capabilities), 'CAPABILITY_DECLARATION_REQUIRED')
            ensure(all(callable(getattr(adapter, name, None)) for name in ('validate_route', 'validate_model',
                'validate_spend', 'rates', 'reserve', 'credential', 'serialize', 'exchange', 'decode', 'terminal')), 'ADAPTER_CONTRACT_INCOMPLETE')
            values[adapter.provider_id] = adapter
        self.adapters = MappingProxyType(values)

    def select(self, provider_id):
        ensure(isinstance(provider_id, str) and provider_id in self.adapters, 'PROVIDER_NOT_REGISTERED')
        return self.adapters[provider_id]


def registry():
    from provider_fixture import LocalFixtureAdapter
    return ProviderRegistry((DeepSeekAdapter(), LocalFixtureAdapter()))


def select(scope):
    return registry().select(scope.get('provider_id'))


def verified_result(adapter, scope, result):
    """Do not trust capabilities, worker success or a normalized body alone."""
    try:
        ensure(isinstance(result, pt.TransportResult) and result.status == 200, 'ADAPTER_UNTRUSTED_HTTP_RESULT')
        ensure(isinstance(result.wire, bytes) and isinstance(result.body, bytes), 'ADAPTER_CAPTURE_TYPE')
        ensure(len(result.wire) <= pt.MAX_WIRE and len(result.body) <= pt.MAX_BODY, 'ADAPTER_CAPTURE_BOUND')
        ensure(adapter.decode(scope, result.wire) == result.body, 'ADAPTER_RECEIPT_WIRE_MISMATCH')
        adapter.terminal(scope, json.loads(result.body))
    except (ValueError, TypeError, KeyError, IndexError, UnicodeError):
        wire = getattr(result, 'wire', b''); status = getattr(result, 'status', None)
        wire = wire[:pt.MAX_WIRE] if isinstance(wire, bytes) else b''
        status = status if type(status) is int and 100 <= status <= 599 else None
        raise pt.TransportFault('TRANSPORT_PROTOCOL_OR_CONNECTION_ERROR', wire, status) from None
    return result
