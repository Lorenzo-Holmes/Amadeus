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
HISTORICAL_LOCAL_FORMAL_SCOPE_VERSION = 'apcore-provider-scope-7'
FORMAL_SCOPE_VERSION = 'apcore-provider-scope-8'
DEEPSEEK_FORMAL_SCOPE_VERSION = 'apcore-provider-scope-9'
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
    if scope.get('schema_version') in (FORMAL_SCOPE_VERSION, DEEPSEEK_FORMAL_SCOPE_VERSION):
        return digest({'version':'apcore-generation-identity-2','scope_sha256':digest(scope),
                       'model_id':model,'messages':messages})
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


def formal_reserve(scope, model, input_bound):
    policy=scope['spend_policy']; rates=policy['rates_usd_per_million'][model]
    usd_micro=Decimal(input_bound)*max(Decimal(rates['input']),Decimal(rates['cache_write'])) + Decimal(32768)*Decimal(rates['output'])
    return int((usd_micro*Decimal(policy['fx_cny_per_usd'])*(1+Decimal(policy['fee_fraction']))).to_integral_value(rounding=ROUND_CEILING))


def check_formal_spend(scope):
    import provider_openai as oa
    policy=scope.get('spend_policy')
    ensure(isinstance(policy,dict) and set(policy)=={'mode','currency','rates_usd_per_million','price_identity',
        'fx_cny_per_usd','fee_fraction','authorization_identity'}, 'OPENAI_SPEND_FIELDS')
    ensure(policy['mode']=='REVIEWED_RATES_PROJECT_AUTHORIZATION' and policy['currency']=='USD', 'OPENAI_SPEND_MODE')
    price=oa.strict_json(oa.verify_reference(policy['price_identity']).read_bytes())
    ensure(price.get('rates')==policy['rates_usd_per_million'] and set(price['rates'])==set(oa.MODELS)
        and price.get('currency')=='USD' and price.get('official_pricing_refreshed') is True
        and price.get('sources') and all(s['url'].startswith('https://developers.openai.com/') for s in price['sources']), 'OPENAI_PRICE_IDENTITY')
    for rates in price['rates'].values():
        ensure(set(rates)=={'input','cached_input','cache_write','output'} and all(type(v) is str and Decimal(v).is_finite() and Decimal(v)>0 for v in rates.values()), 'OPENAI_INVALID_PRICE')
    # These are estimate conversion assumptions, not claims about the real bill.
    ensure(policy['fx_cny_per_usd']=='8' and policy['fee_fraction']=='0.10','OPENAI_CONVERSION_IDENTITY')
    auth=oa.strict_json(oa.verify_reference(policy['authorization_identity']).read_bytes())
    ensure(auth.get('status')=='PROJECT_COMPLETION_SPEND_AUTHORIZED_AS_NEEDED'
        and auth.get('candidate_id')==oa.CANDIDATE and auth.get('batch_design_id')==scope['batch_design_id']
        and auth.get('max_fresh_revisions')==1 and auth.get('max_generation_requests')==44
        and auth.get('automatic_paid_retries')==0 and auth.get('count_api_requests')==44
        and auth.get('count_retry_policy')==0,
        'OPENAI_EXECUTION_AUTHORIZATION_MISMATCH')
    reserve=sum(formal_reserve(scope,s['model'],28672) for s in scope['slots'])
    ensure(type(scope.get('reserved_upper_micro_cny')) is int and scope['reserved_upper_micro_cny']==reserve
        and isinstance(scope.get('total_guard_cny'),str) and Decimal(scope['total_guard_cny'])*1_000_000==reserve,
        'OPENAI_WHOLE_BATCH_RESERVE_MISMATCH')


def check_formal_scope(scope, adapter):
    import provider_openai as oa
    import provider_transport as pt
    from semantic_binding import validate_binding
    ensure(scope.get('schema_version')==FORMAL_SCOPE_VERSION and adapter.provider_id=='openai', 'FORMAL_PROVIDER_SCOPE_MISMATCH')
    ensure(scope.get('candidate_id')==oa.CANDIDATE and scope.get('provider_id')=='openai'
        and scope.get('validation_purpose')=='FORMAL_EXTERNAL44_CONFIGURATION_QUALIFICATION'
        and scope.get('formal_validation') is True, 'OPENAI_FORMAL_PURPOSE')
    ensure(scope.get('capabilities')==oa.CAPABILITIES.declaration() and scope.get('api_protocol')=='responses'
        and scope.get('transport_contract_version')==TRANSPORT_VERSION, 'OPENAI_CAPABILITY_MISMATCH')
    ensure(scope.get('source_binding')==runtime_source_binding(), 'PROVIDER_SOURCE_BINDING_CHANGED')
    ensure(scope.get('primary_model')==oa.MODELS[0] and scope.get('switch_model')==oa.MODELS[1], 'OPENAI_ROLE_MODELS')
    ensure(scope.get('stream') is True and scope.get('tools_allowed') is False
        and type(scope.get('automatic_paid_retries')) is int and scope['automatic_paid_retries']==0, 'OPENAI_EXECUTION_CONTROLS')
    ensure(scope.get('generation_config')==oa.generation_options() and scope.get('max_output_tokens')==32768
        and scope.get('max_input_bytes')==24576 and scope.get('input_overhead_reserve_tokens')==4096
        and scope.get('reasoning_effort')=='max' and scope.get('thinking')=={'type':'enabled'}, 'OPENAI_FROZEN_CONTROLS')
    ensure(scope.get('request_timeout_seconds')==600, 'OPENAI_TIMEOUT_CHANGED')
    pt.check_policy(scope.get('transport_policy'),600)
    policy=scope['transport_policy']
    ensure(all(policy.get(k)==v for k,v in {'connect_timeout_seconds':15,'read_timeout_seconds':120,
        'worker_deadline_seconds':595}.items()), 'OPENAI_TRANSPORT_CHANGED')
    adapter.validate_route(scope)
    ensure(all(isinstance(scope.get(k),str) and scope[k] for k in ('batch_id','principal_id')), 'OPENAI_ACTOR_SCOPE')
    design=oa.frozen_contract()['PROVIDER_SCOPE_CONTRACT.json']['schedule']
    slots=scope.get('slots'); ensure(isinstance(slots,list) and len(slots)==44,'OPENAI_SLOT_COUNT')
    actual=[dict(position=i+1,slot_id=s.get('id'),case_id=s.get('case_id'),model_role=s.get('model_role'),
        model=s.get('model'),host_action_before=s.get('host_action_before')) for i,s in enumerate(slots)]
    ensure(actual==design and scope.get('schedule_identity')==digest(design), 'OPENAI_SCHEDULE_CHANGED')
    ensure(all(isinstance(s.get('user_text'),str) and s.get('entity_label') for s in slots), 'OPENAI_SLOT_CONTENT')
    original_path=oa.WORKSPACE/'persona_core/operational_build_v1/evidence/R047-01/freeze_20260907T164424498856Z/EXECUTION_SCOPE.json'
    original=oa.strict_json(original_path.read_bytes())['slots']; selected={s['slot_id'] for s in design}
    fields=('id','case_id','entity_label','user_text')
    ensure([{k:s.get(k) for k in fields} for s in slots]==[{k:s.get(k) for k in fields} for s in original if s['id'] in selected],
        'OPENAI_FROZEN_SLOT_INPUT_CHANGED')
    refs=scope.get('identity_references',{})
    ensure(set(refs)=={'configuration','contract','quality_policy','dataset','rubric','criterion_routing','source_manifest','acceptance_config'}, 'OPENAI_IDENTITY_FIELDS')
    for value in refs.values(): oa.verify_reference(value)
    for name,path,d in [('configuration',oa.CONFIG_PATH,oa.CONFIG_SHA),('contract',oa.CONTRACT_DIR+'CONTRACT_FREEZE_MANIFEST.json',oa.CONTRACT_SHA),('quality_policy',oa.POLICY_PATH,oa.POLICY_SHA)]:
        ensure(refs[name]=={'path':path,'sha256':d}, 'OPENAI_FROZEN_IDENTITY_CHANGED')
    binding=scope.get('semantic_acceptance_binding')
    ensure(isinstance(binding,dict) and binding.get('semantic_acceptance_mode')=='BOUNDED', 'OPENAI_BOUNDED_BINDING_REQUIRED')
    for a,b in [('dataset','dataset_identity'),('rubric','rubric_identity'),('criterion_routing','criterion_routing'),('source_manifest','acceptance_source_manifest')]:
        ensure(refs[a]==binding.get(b),'OPENAI_ACCEPTANCE_IDENTITY_CHANGED')
    validate_binding(binding,scope)
    ensure(scope.get('evaluation_schema')=='apcore-gpt6-evaluation-2' and scope.get('criteria_count')==176
        and scope.get('gate_denominators')=={'A':176,'B':132}, 'OPENAI_DENOMINATOR_CHANGED')
    ensure(scope.get('stop_rules')=={'quality_major':'QUALITY_FAILURE_STOP','state_major':'INTEGRITY_HARD_STOP',
        'critical':'SAFETY_HARD_STOP','unknown':'STOP_AND_QUARANTINE'}, 'OPENAI_STOP_RULES_CHANGED')
    oa.validate_count_policy(scope)
    adapter.validate_spend(scope)


def formal_accounting(native, scope, model, input_bound, visible_text=''):
    """Preserve native usage and report evidence without certifying a bill."""
    result={'version':'APCORE_OPENAI_USAGE_ACCOUNTING_1','native_usage':native,'native_usage_sha256':digest(native),
        'billing_certified':False,'accounting_status':'INVALID_OR_MISSING_USAGE','rejection':'OPENAI_INVALID_USAGE',
        'usd_estimate':None,'estimate_micro_cny':None,'reserve_retained':True,
        'visible_text_utf8_bytes':len(visible_text.encode('utf-8')),'official_visible_tokens':None,'visible_text_tokens_local':None}
    if not isinstance(native,dict): return result
    values=[native.get(k) for k in ('input_tokens','output_tokens','total_tokens')]
    if any(type(v) is not int or v<0 for v in values): return result
    i,o,t=values
    if t!=i+o: return result
    details=native.get('input_tokens_details'); out=native.get('output_tokens_details')
    if details is not None and not isinstance(details,dict) or out is not None and not isinstance(out,dict): return result
    c=(details or {}).get('cached_tokens'); w=(details or {}).get('cache_write_tokens'); r=(out or {}).get('reasoning_tokens')
    if any(v is not None and (type(v) is not int or v<0) for v in (c,w,r)): return result
    if (c or 0)+(w or 0)>i or r is not None and r>o: return result
    rates={k:Decimal(v) for k,v in scope['spend_policy']['rates_usd_per_million'][model].items()}
    complete=all(v is not None for v in (c,w,r)); known_cache=c is not None and w is not None
    u=i-c-w if known_cache else None
    charge=(Decimal(u)*rates['input']+Decimal(c)*rates['cached_input']+Decimal(w)*rates['cache_write'] if known_cache else
        Decimal(c or 0)*rates['cached_input']+Decimal(i-(c or 0))*max(rates['input'],rates['cache_write']))+Decimal(o)*rates['output']
    policy=scope['spend_policy']
    result.update(input_tokens=i,cache_read_tokens=c,cache_write_tokens=w,uncached_input_tokens=u,
        output_total_tokens=o,reasoning_tokens=r,nonreasoning_output_tokens=o-r if r is not None else None,total_tokens=t,
        usd_estimate=str(charge/1_000_000),estimate_micro_cny=int((charge*Decimal(policy['fx_cny_per_usd'])*(1+Decimal(policy['fee_fraction']))).to_integral_value(rounding=ROUND_CEILING)),
        accounting_status='ESTIMATED_FROM_COMPLETE_USAGE' if complete else 'BOUNDED_ESTIMATE_INCOMPLETE_USAGE',
        rejection=None if complete else 'OPENAI_INCOMPLETE_USAGE')
    if i>input_bound or o>32768:
        result.update(rejection='ACCOUNTING_BOUND_VIOLATION',accounting_status='ACCOUNTING_BOUND_VIOLATION',bound_guarantee_withdrawn=True)
    return result
