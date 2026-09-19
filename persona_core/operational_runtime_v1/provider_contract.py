"""Provider-independent generation identity, accounting and reply usability.

Capability declarations constrain requests; only validated wire proves terminal
certainty. No contract grants semantic acceptance or permission to retry.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from pathlib import Path
from transcript_store import ensure

SCOPE_VERSION = 'apcore-provider-scope-6'
TRANSPORT_VERSION = 'apcore-provider-transport-1'
IDENTITY_FIELDS = frozenset({'provider_id', 'generation_config', 'transport_contract_version',
                             'source_binding', 'spend_policy', 'capabilities'})


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class Capabilities:
    protocols: tuple[str, ...]
    network_route_modes: tuple[str, ...]
    terminal_model: str
    supports_streaming: bool = True
    supports_reasoning: bool = False
    supports_usage: bool = True
    network_access: bool = True

    def declaration(self):
        return {'supports_streaming': self.supports_streaming,
                'supports_reasoning': self.supports_reasoning, 'supports_usage': self.supports_usage,
                'supports_responses_protocol': 'responses' in self.protocols,
                'supports_chat_completions': 'chat_completions' in self.protocols,
                'api_protocols': list(self.protocols), 'network_route_modes': list(self.network_route_modes),
                'terminal_model': self.terminal_model, 'network_access': self.network_access}


def runtime_source_binding():
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob('*.py'))}
    return {'version': 'apcore-runtime-source-1', 'sha256': digest(files)}


def guard_legacy_identity(scope):
    """Old schemas have exactly one implicit provider; reject foreign metadata."""
    ensure(scope.get('schema_version') != SCOPE_VERSION and not (IDENTITY_FIELDS & set(scope)),
           'FORMAL_PROVIDER_SCOPE_MISMATCH')


def generation_identity(scope, model, messages):
    return digest({'version': 'apcore-generation-identity-1', 'provider_id': scope['provider_id'],
        'model_id': model, 'api_protocol': scope['api_protocol'], 'endpoint': scope['endpoint'],
        'generation_config': scope['generation_config'], 'network_route_policy': scope['network_route_policy'],
        'transport_contract_version': scope['transport_contract_version'],
        'transport_policy': scope['transport_policy'], 'source_binding': scope['source_binding'],
        'messages': messages})


def validate_usage(usage):
    ensure(isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0
        for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')), 'INVALID_USAGE')
    ensure(usage['total_tokens'] == usage['prompt_tokens'] + usage['completion_tokens'], 'USAGE_TOTAL_MISMATCH')
    details = usage.get('completion_tokens_details')
    if details is not None:
        ensure(isinstance(details, dict), 'INVALID_COMPLETION_DETAILS')
        reasoning = details.get('reasoning_tokens')
        if reasoning is not None:
            ensure(type(reasoning) is int and 0 <= reasoning <= usage['completion_tokens'], 'INVALID_REASONING_TOKEN_ACCOUNTING')
    hits = usage.get('prompt_cache_hit_tokens', 0)
    misses = usage.get('prompt_cache_miss_tokens', usage['prompt_tokens'] - hits)
    ensure(type(hits) is int and type(misses) is int and hits >= 0 and misses >= 0
           and hits + misses == usage['prompt_tokens'], 'CACHE_USAGE_MISMATCH')
    return hits, misses


def estimate_usage(usage, rates):
    hits, misses = validate_usage(usage)
    if rates is None:
        return None
    amount = (Decimal(misses) * Decimal(str(rates[0])) + Decimal(hits) * Decimal(str(rates[2]))
              + Decimal(usage['completion_tokens']) * Decimal(str(rates[1])))
    return int(amount.to_integral_value(rounding=ROUND_CEILING))


def usage_known(usage_json):
    try:
        validate_usage(json.loads(usage_json) if usage_json is not None else None)
        return True
    except (ValueError, TypeError):
        return False


def usable_reply(body, *, responses_api=False):
    choices = body.get('choices')
    ensure(isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict), 'INVALID_RESPONSE_CHOICES')
    choice = choices[0]
    message = choice.get('message')
    ensure(isinstance(message, dict), 'INVALID_RESPONSE_MESSAGE')
    ensure(choice.get('finish_reason') == 'stop', 'TRUNCATED_OR_OTHER_FINISH')
    if responses_api:
        ensure(body.get('responses_api_status') == 'completed', 'RESPONSES_NOT_COMPLETED')
    ensure(not message.get('tool_calls'), 'UNEXPECTED_TOOL_CALL')
    text = message.get('content')
    ensure(isinstance(text, str) and text.strip(), 'EMPTY_RESPONSE')
    return text, choice['finish_reason']


def check_scope(scope, adapter):
    import provider_transport as pt
    ensure(scope.get('schema_version') == SCOPE_VERSION, 'PROVIDER_SCOPE_VERSION')
    ensure(type(scope.get('automatic_paid_retries')) is int and scope['automatic_paid_retries'] == 0, 'AUTOMATIC_RETRY_FORBIDDEN')
    ensure(scope.get('validation_purpose') == 'SYNTHETIC_INDEPENDENT_VALIDATION', 'SYNTHETIC_SCOPE_REQUIRED')
    ensure(scope.get('transport_contract_version') == TRANSPORT_VERSION, 'TRANSPORT_CONTRACT_VERSION')
    ensure(scope.get('provider_id') == adapter.provider_id and scope.get('capabilities') == adapter.capabilities.declaration(), 'CAPABILITY_CONTRACT_MISMATCH')
    ensure(scope.get('api_protocol') in adapter.capabilities.protocols, 'UNSUPPORTED_API_PROTOCOL')
    ensure(scope.get('source_binding') == runtime_source_binding(), 'PROVIDER_SOURCE_BINDING_CHANGED')
    ensure(isinstance(scope.get('batch_id'), str) and scope['batch_id'] and isinstance(scope.get('principal_id'), str)
           and scope['principal_id'], 'PROVIDER_ACTOR_SCOPE_REQUIRED')
    ensure(scope.get('stream') is True and adapter.capabilities.supports_streaming, 'STREAMING_REQUIRED')
    ensure(scope.get('tools_allowed') is False, 'TOOLS_FORBIDDEN')
    ensure(type(scope.get('max_input_bytes')) is int and 1 <= scope['max_input_bytes'] <= 32768, 'INPUT_BOUND')
    ensure(type(scope.get('max_output_tokens')) is int and 1 <= scope['max_output_tokens'] <= 131072, 'OUTPUT_BOUND')
    ensure(type(scope.get('input_overhead_reserve_tokens')) is int and scope['input_overhead_reserve_tokens'] >= 4096, 'INPUT_RESERVE_REQUIRED')
    ensure(scope.get('thinking') in ({'type': 'enabled'}, {'type': 'disabled'}), 'REASONING_CONFIGURATION')
    reasoning = scope['thinking']['type'] == 'enabled'
    ensure(not reasoning or adapter.capabilities.supports_reasoning, 'REASONING_UNSUPPORTED')
    ensure(scope.get('reasoning_effort') in ('low', 'high', 'max') if reasoning else scope.get('reasoning_effort') is None, 'REASONING_EFFORT')
    generation = {'stream': True, 'max_output_tokens': scope['max_output_tokens'],
        'reasoning': {'enabled': reasoning, 'effort': scope['reasoning_effort']}}
    native_options = getattr(adapter, 'generation_options', lambda: {})()
    ensure(isinstance(native_options, dict) and not (set(native_options) & set(generation)), 'GENERATION_OPTIONS_CONFLICT')
    generation.update(native_options)
    ensure(scope.get('generation_config') == generation, 'GENERATION_CONFIG_MISMATCH')
    ensure(type(scope.get('request_timeout_seconds')) is int and 1 <= scope['request_timeout_seconds'] <= 1200, 'REQUEST_DEADLINE')
    pt.check_policy(scope.get('transport_policy'), scope['request_timeout_seconds'])
    adapter.validate_route(scope)
    slots = scope.get('slots')
    ensure(isinstance(slots, list) and 1 <= len(slots) <= 2, 'SYNTHETIC_SLOT_BOUND')
    ensure(all(isinstance(s, dict) and isinstance(s.get('id'), str) and s['id'] and s.get('entity_label')
               and isinstance(s.get('user_text'), str) for s in slots), 'SYNTHETIC_SLOT_SHAPE')
    ensure(len({s['id'] for s in slots}) == len(slots), 'DUPLICATE_SLOT')
    for slot in slots:
        adapter.validate_model(slot.get('model'), slot.get('model'))
    adapter.validate_spend(scope)
