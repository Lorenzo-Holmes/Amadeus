"""One preregistered DeepSeek successor; existing transport and state semantics.

Host byte limits are pre-request evidence. Native token usage is exclusively
post-request accounting. This module does not implement or claim a count API.
"""
from __future__ import annotations
import hashlib
import json
from decimal import Decimal, ROUND_CEILING
from datetime import datetime, timezone, timedelta
from transcript_store import WORKSPACE, ensure
import provider_contract as pc
import provider_transport as pt
from provider_adapters import DeepSeekAdapter

SCOPE_VERSION = 'apcore-provider-scope-9'
VERSION = 'APCORE_DEEPSEEK_FORMAL_ADAPTER_1'
CANDIDATE = 'APCORE_SUCCESSOR_DEEPSEEK_FLASH_MAX_1'
MODEL = 'deepseek-flash'
ENDPOINT = 'https://api.deepseek.com/responses'
DIRECTORY = 'persona_core/gpt6_optimization_v2/deepseek_successor_20260921_01/'
CONFIG_PATH = DIRECTORY + 'CONFIGURATION_PREREGISTRATION.json'
CONFIG_SHA = '80e7f80bd6b3c8ec78187bf7a0db719633fad2606fcef5eb0757f68ac8ecde30'
CALIBRATED_CANDIDATE = 'APCORE_DEEPSEEK_FLASH_GENERALIZED_EPISTEMIC_CALIBRATION_V1'
CALIBRATED_DIRECTORY = 'persona_core/gpt6_optimization_v2/epistemic_calibration_20260921_01/'
CALIBRATED_CONFIG_SHA = '0752ef9b3014d04082b10e52c01cc44a3fd65178b7732c1b91af97e4512b1df6'
INPUT_ENVELOPE = 1_100_000
CAPABILITIES = pc.Capabilities(('responses',), ('DIRECT_NO_PROXY',),
    'responses_terminal_or_explicit_http_rejection', supports_reasoning=True)
STOP_RULES = {'quality_major':'QUALITY_FAILURE_STOP','state_major':'INTEGRITY_HARD_STOP',
              'critical':'SAFETY_HARD_STOP','unknown':'STOP_AND_QUARANTINE'}

def strict_json(data):
    def pairs(items):
        obj={}
        for k,v in items:
            ensure(k not in obj,'DEEPSEEK_DUPLICATE_JSON_KEY'); obj[k]=v
        return obj
    def constant(_): raise ValueError('DEEPSEEK_NONFINITE_JSON')
    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)

def reference(path):
    path=path.resolve()
    ensure(path.is_relative_to(WORKSPACE),'DEEPSEEK_REFERENCE_OUTSIDE_WORKSPACE')
    return {'path':path.relative_to(WORKSPACE).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def verify_reference(value):
    ensure(isinstance(value,dict) and set(value)=={'path','sha256'},'DEEPSEEK_REFERENCE_SHAPE')
    p=(WORKSPACE/value['path']).resolve()
    ensure(p.is_relative_to(WORKSPACE) and p.is_file(),'DEEPSEEK_REFERENCE_PATH')
    ensure(reference(p)==value,'DEEPSEEK_REFERENCE_CHANGED')
    return p

def candidate_profile(candidate_id=CANDIDATE):
    """Pinned registrations, never a caller-selected arbitrary configuration."""
    if candidate_id == CANDIDATE:
        return DIRECTORY, CONFIG_SHA, 'APCORE_DEEPSEEK_SUCCESSOR_CONFIGURATION_1'
    ensure(candidate_id == CALIBRATED_CANDIDATE, 'DEEPSEEK_UNREGISTERED_CANDIDATE')
    return CALIBRATED_DIRECTORY, CALIBRATED_CONFIG_SHA, 'APCORE_EPISTEMIC_CALIBRATION_CONFIGURATION_1'

def configuration(candidate_id=CANDIDATE):
    directory, digest, _ = candidate_profile(candidate_id)
    cfg = strict_json(verify_reference({'path':directory+'CONFIGURATION_PREREGISTRATION.json','sha256':digest}).read_bytes())
    ensure(cfg['candidate_id'] == candidate_id, 'DEEPSEEK_CANDIDATE_CONFIGURATION_MISMATCH')
    if candidate_id == CALIBRATED_CANDIDATE:
        verify_reference(cfg['generation_calibration']['implementation'])
        ensure(cfg['attempt_kind']=='POST_FAIL_PRODUCT_REPAIR_NEW_CANDIDATE', 'DEEPSEEK_ATTEMPT_KIND')
    return cfg

def generation_options():
    return {'stream':True,'max_output_tokens':32768,'reasoning':{'enabled':True,'effort':'max'},
            'top_p':1,'tools_parameter':'NOT_SENT','automatic_truncation':False}

def route():
    return {'version':'apcore-network-route-1','mode':'DIRECT_NO_PROXY','host':'api.deepseek.com'}

def input_guard_receipt(scope,payload,slot_id):
    if scope.get('schema_version') == pc.STRUCTURAL_SCOPE_VERSION:
        from provider_structural import input_guard_receipt as stage_input_guard
        return stage_input_guard(scope,payload,slot_id)
    value=strict_json(payload)
    ensure(payload==pc.canonical(value),'DEEPSEEK_NONCANONICAL_REQUEST')
    ensure(set(value)=={'model','input','stream','max_output_tokens','reasoning','top_p'},'DEEPSEEK_REQUEST_FIELDS')
    ensure(value['model']==MODEL and value['stream'] is True and type(value['max_output_tokens']) is int and value['max_output_tokens']==32768
        and value['reasoning']=={'effort':'max'} and type(value['top_p']) is int and value['top_p']==1,
        'DEEPSEEK_REQUEST_CONTROLS')
    messages=value['input']
    ensure(isinstance(messages,list) and messages and all(isinstance(m,dict) and set(m)=={'role','content'}
        and m['role'] in ('system','user','assistant') and isinstance(m['content'],str) for m in messages),
        'DEEPSEEK_MESSAGE_SHAPE')
    message_bytes=len(pc.canonical(messages))
    ensure(message_bytes<=24576 and len(payload)<=32768,'DEEPSEEK_INPUT_BYTES_EXCEEDED')
    ensure(any(s['id']==slot_id and s['model']==MODEL for s in scope['slots']),'DEEPSEEK_INPUT_SLOT')
    return {'version':'APCORE_DEEPSEEK_HOST_BYTES_RECEIPT_1','candidate_id':scope['candidate_id'],'model':MODEL,
        'slot_id':slot_id,'request_sha256':hashlib.sha256(payload).hexdigest(),'messages_sha256':pc.digest(messages),
        'canonical_message_bytes':message_bytes,'canonical_request_bytes':len(payload),
        'input_tokens_pre_request':None,'exact_token_proof':False,'automatic_truncation':False,
        'scope_sha256':pc.digest(scope),'source_binding':scope['source_binding'],
        'input_policy_identity':scope['identity_references']['input_safety_policy']}

def reserve(scope,model,nbytes):
    if scope.get('schema_version') == pc.STRUCTURAL_SCOPE_VERSION:
        from provider_structural import reserve as stage_reserve
        return stage_reserve(scope,model,nbytes)
    ensure(model==MODEL and type(nbytes) is int and 0<=nbytes<=24576,'DEEPSEEK_RESERVE_INPUT')
    rates=scope['spend_policy']['rates'][model]
    return int((Decimal(INPUT_ENVELOPE)*Decimal(rates['input_miss']) +
        Decimal(32768)*Decimal(rates['output'])).to_integral_value(rounding=ROUND_CEILING))

def check_spend(scope):
    if scope.get('schema_version') == pc.STRUCTURAL_SCOPE_VERSION:
        from provider_structural import check_spend as stage_check_spend
        return stage_check_spend(scope)
    policy=scope.get('spend_policy')
    ensure(isinstance(policy,dict) and set(policy)=={'mode','currency','rates','price_identity','authorization_identity'},'DEEPSEEK_SPEND_FIELDS')
    ensure(policy['mode']=='REVIEWED_RATES_PROJECT_AUTHORIZATION' and policy['currency']=='CNY','DEEPSEEK_SPEND_MODE')
    price=strict_json(verify_reference(policy['price_identity']).read_bytes())
    ensure(price.get('currency')=='CNY' and price.get('official_pricing_refreshed') is True
        and price.get('rates')==policy['rates']=={MODEL:{'input_miss':'2','output':'8','input_hit':'0.04'}},'DEEPSEEK_PRICE_CHANGED')
    ensure(price.get('sources') and all(s['url'].startswith('https://api-docs.deepseek.com/') for s in price['sources']), 'DEEPSEEK_PRICE_SOURCE')
    auth=strict_json(verify_reference(policy['authorization_identity']).read_bytes())
    candidate_profile(scope.get('candidate_id'))
    ensure(auth.get('status')=='PROJECT_COMPLETION_SPEND_AUTHORIZED_AS_NEEDED' and auth.get('candidate_id')==scope['candidate_id']
        and auth.get('max_fresh_revisions')==1 and auth.get('max_generation_requests')==44
        and auth.get('automatic_paid_retries')==auth.get('count_api_requests')==auth.get('readiness_requests')==0
        and auth.get('fallback_allowed') is False,'DEEPSEEK_AUTHORIZATION_CHANGED')
    total=44*reserve(scope,MODEL,24576)
    ensure(scope.get('reserved_upper_micro_cny')==total and isinstance(scope.get('total_guard_cny'),str)
        and Decimal(scope['total_guard_cny'])*1_000_000==total==price['batch_reserved_micro_cny'],'DEEPSEEK_RESERVATION_CHANGED')

def build_scope(revision,suite_data,pricing,transport_policy,network_route_policy,*,
                authorization_file,pricing_file,acceptance_config_file,input_proof_file=None):
    auth_preview=strict_json(authorization_file.read_bytes())
    if auth_preview.get('schema_version')=='APCORE_STRUCTURAL_TASK_AUTHORIZATION_1':
        from provider_structural import build_scope as structural_scope
        return structural_scope(revision,suite_data,pricing,transport_policy,network_route_policy,
            authorization_file=authorization_file,pricing_file=pricing_file,
            acceptance_config_file=acceptance_config_file,input_proof_file=input_proof_file)
    ensure(input_proof_file is None,'DEEPSEEK_FOREIGN_INPUT_PROOF_FORBIDDEN')
    auth=strict_json(authorization_file.read_bytes());candidate=auth.get('candidate_id')
    directory,digest,_=candidate_profile(candidate)
    cfg=configuration(candidate);acceptance=strict_json(acceptance_config_file.read_bytes())
    refs={'configuration':{'path':directory+'CONFIGURATION_PREREGISTRATION.json','sha256':digest},
        'contract':reference(WORKSPACE/directory/'CONFIGURATION_FREEZE.json'),
        'quality_policy':cfg['model_quality_policy_identity'],'dataset':cfg['dataset_identity'],
        'rubric':cfg['rubric_identity'],'criterion_routing':cfg['criterion_routing_identity'],
        'source_manifest':acceptance['acceptance_source_manifest'],'acceptance_config':reference(acceptance_config_file),
        'policy_amendment':cfg['policy_amendment_identity'],'input_safety_policy':cfg['input_safety_policy_identity'],
        'schedule':cfg['schedule_identity']}
    schedule=strict_json(verify_reference(refs['schedule']).read_bytes())['slots']
    safety=strict_json(verify_reference(refs['input_safety_policy']).read_bytes())
    scope={'schema_version':SCOPE_VERSION,'provider_id':'deepseek','candidate_id':candidate,
        'batch_design_id':'APCORE_DEEPSEEK_FLASH_EXTERNAL44_SINGLE_BATCH_1',
        'validation_purpose':'FORMAL_EXTERNAL44_CONFIGURATION_QUALIFICATION','formal_validation':True,
        'batch_id':'APCORE-G6-V2-'+revision,'principal_id':'APCORE_G6_V2_'+revision,
        'endpoint':ENDPOINT,'api_protocol':'responses','primary_model':MODEL,'switch_model':MODEL,
        'slots':suite_data['slots'],'stream':True,'thinking':{'type':'enabled'},'reasoning_effort':'max',
        'tools_allowed':False,'automatic_paid_retries':0,'generation_config':generation_options(),
        'max_input_bytes':24576,'max_request_bytes':32768,'input_overhead_reserve_tokens':4096,
        'input_overhead_reserve_role':'LEGACY_COMPATIBILITY_ONLY_NOT_TOKEN_PROOF_OR_RESERVATION',
        'input_budget_envelope_tokens':INPUT_ENVELOPE,'input_safety_policy':safety,'max_output_tokens':32768,
        'request_timeout_seconds':600,'transport_policy':transport_policy,'network_route_policy':network_route_policy,
        'transport_contract_version':pc.TRANSPORT_VERSION,'capabilities':CAPABILITIES.declaration(),
        'source_binding':pc.runtime_source_binding(),'schedule_identity':pc.digest(schedule),'identity_references':refs,
        'evaluation_schema':'apcore-gpt6-evaluation-2','criteria_count':176,'gate_denominators':{'A':176,'B':132},
        'stop_rules':STOP_RULES,'input_bound_mode':safety['method'],'count_api_requests':0,
        'spend_policy':{'mode':'REVIEWED_RATES_PROJECT_AUTHORIZATION','currency':'CNY','rates':pricing['rates'],
            'price_identity':reference(pricing_file),'authorization_identity':reference(authorization_file)},
        'output_budget_includes_reasoning':True,'automatic_capacity_escalation':False,'billing_verified':False}
    total=44*reserve(scope,MODEL,24576)
    scope.update(reserved_upper_micro_cny=total,total_guard_cny=str(Decimal(total)/1_000_000))
    return scope

def check_scope(scope,adapter):
    from semantic_binding import validate_binding
    candidate=scope.get('candidate_id');directory,digest,freeze_id=candidate_profile(candidate)
    cfg=configuration(candidate)
    ensure(scope.get('schema_version')==SCOPE_VERSION and scope.get('provider_id')=='deepseek'
        and adapter.provider_id=='deepseek' and cfg['candidate_id']==candidate,'DEEPSEEK_FORMAL_IDENTITY')
    ensure(scope.get('formal_validation') is True and scope.get('validation_purpose')=='FORMAL_EXTERNAL44_CONFIGURATION_QUALIFICATION','DEEPSEEK_FORMAL_PURPOSE')
    ensure(scope.get('source_binding')==pc.runtime_source_binding(),'PROVIDER_SOURCE_BINDING_CHANGED')
    ensure(scope.get('capabilities')==CAPABILITIES.declaration() and scope.get('transport_contract_version')==pc.TRANSPORT_VERSION,'DEEPSEEK_CAPABILITIES')
    ensure(scope.get('primary_model')==scope.get('switch_model')==MODEL,'DEEPSEEK_ROLE_MODEL_CHANGED')
    ensure(scope.get('generation_config')==generation_options() and scope.get('max_input_bytes')==24576
        and scope.get('max_output_tokens')==32768 and scope.get('input_budget_envelope_tokens')==INPUT_ENVELOPE
        and scope.get('request_timeout_seconds')==600 and scope.get('reasoning_effort')=='max'
        and scope.get('thinking')=={'type':'enabled'} and scope.get('stream') is True and scope.get('tools_allowed') is False,
        'DEEPSEEK_FROZEN_CONTROLS')
    ensure(type(scope.get('automatic_paid_retries')) is int and scope['automatic_paid_retries']==0
        and scope.get('automatic_capacity_escalation') is False,'DEEPSEEK_RETRY_OR_ESCALATION')
    ensure(scope.get('transport_policy')==cfg['transport_policy'],'DEEPSEEK_TRANSPORT_CHANGED')
    pt.check_policy(scope['transport_policy'],600);adapter.validate_route(scope)
    refs=scope.get('identity_references',{})
    ensure(set(refs)=={'configuration','contract','quality_policy','dataset','rubric','criterion_routing',
        'source_manifest','acceptance_config','policy_amendment','input_safety_policy','schedule'},'DEEPSEEK_IDENTITY_FIELDS')
    for v in refs.values():verify_reference(v)
    ensure(refs['configuration']=={'path':directory+'CONFIGURATION_PREREGISTRATION.json','sha256':digest},'DEEPSEEK_CONFIGURATION_CHANGED')
    for name,field in [('quality_policy','model_quality_policy_identity'),('dataset','dataset_identity'),('rubric','rubric_identity'),
        ('criterion_routing','criterion_routing_identity'),('policy_amendment','policy_amendment_identity'),
        ('input_safety_policy','input_safety_policy_identity'),('schedule','schedule_identity')]:
        ensure(refs[name]==cfg[field],'DEEPSEEK_PREREGISTERED_IDENTITY_CHANGED')
    frozen=strict_json(verify_reference(refs['contract']).read_bytes())
    ensure(frozen.get('freeze_id')==freeze_id,'DEEPSEEK_CONFIGURATION_FREEZE')
    for p,h in frozen['files'].items():verify_reference({'path':p,'sha256':h})
    safety=strict_json(verify_reference(refs['input_safety_policy']).read_bytes())
    ensure(scope.get('input_safety_policy')==safety and safety['pre_request_exact_proof_required'] is False,'DEEPSEEK_INPUT_POLICY_CHANGED')
    design=strict_json(verify_reference(refs['schedule']).read_bytes())['slots']
    slots=scope.get('slots');ensure(isinstance(slots,list) and len(slots)==44,'DEEPSEEK_SLOT_COUNT')
    actual=[dict(position=i+1,slot_id=s.get('id'),case_id=s.get('case_id'),model_role=s.get('model_role'),
        model=s.get('model'),host_action_before=s.get('host_action_before')) for i,s in enumerate(slots)]
    ensure(actual==design and scope.get('schedule_identity')==pc.digest(design),'DEEPSEEK_SCHEDULE_CHANGED')
    original=strict_json((WORKSPACE/'persona_core/operational_build_v1/evidence/R047-01/freeze_20260907T164424498856Z/EXECUTION_SCOPE.json').read_bytes())['slots']
    ids={s['slot_id'] for s in design}; fields=('id','case_id','entity_label','user_text')
    ensure([{k:s.get(k) for k in fields} for s in slots]==[{k:s.get(k) for k in fields} for s in original if s['id'] in ids], 'DEEPSEEK_BENCHMARK_CHANGED')
    binding=scope.get('semantic_acceptance_binding')
    ensure(isinstance(binding,dict) and binding.get('semantic_acceptance_mode')=='BOUNDED','DEEPSEEK_BOUNDED_REQUIRED')
    for a,b in [('dataset','dataset_identity'),('rubric','rubric_identity'),('criterion_routing','criterion_routing'),('source_manifest','acceptance_source_manifest')]:
        ensure(refs[a]==binding.get(b),'DEEPSEEK_ACCEPTANCE_CHANGED')
    validate_binding(binding,scope)
    ensure(scope.get('evaluation_schema')=='apcore-gpt6-evaluation-2' and scope.get('criteria_count')==176
        and scope.get('gate_denominators')=={'A':176,'B':132} and scope.get('stop_rules')==STOP_RULES,'DEEPSEEK_GATES_CHANGED')
    check_spend(scope)

def accounting(native,scope,model):
    result={'version':'APCORE_DEEPSEEK_NATIVE_ACCOUNTING_1','native_usage':native,'native_usage_sha256':pc.digest(native),
        'basis':'POST_REQUEST_PROVIDER_ACCOUNTING','pre_request_exact_proof':False,'billing_certified':False,
        'accounting_status':'INVALID_OR_MISSING_USAGE','rejection':'DEEPSEEK_USAGE_MISSING_OR_INVALID','estimate_micro_cny':None}
    if not isinstance(native,dict):return result
    i,o,t=(native.get(k) for k in ('input_tokens','output_tokens','total_tokens'))
    if any(type(v) is not int or v<0 for v in (i,o,t)) or i+o!=t:return result
    ids=native.get('input_tokens_details');ods=native.get('output_tokens_details')
    if not isinstance(ids,dict) or not isinstance(ods,dict):return result
    c=ids.get('cached_tokens');r=ods.get('reasoning_tokens')
    if type(c) is not int or not 0<=c<=i or type(r) is not int or not 0<=r<=o:return result
    rates=scope['spend_policy']['rates'][model]
    amount=Decimal(i-c)*Decimal(rates['input_miss'])+Decimal(c)*Decimal(rates['input_hit'])+Decimal(o)*Decimal(rates['output'])
    result.update(input_tokens=i,output_tokens=o,total_tokens=t,cached_input_tokens=c,reasoning_tokens=r,
        estimate_micro_cny=int(amount.to_integral_value(rounding=ROUND_CEILING)),accounting_status='ESTIMATED_FROM_NATIVE_USAGE',rejection=None)
    if i>INPUT_ENVELOPE or o>32768:result.update(accounting_status='ACCOUNTING_BOUND_VIOLATION',rejection='DEEPSEEK_USAGE_ENVELOPE_EXCEEDED')
    return result

class DeepSeekFormalAdapter(DeepSeekAdapter):
    capabilities=CAPABILITIES
    wire_format='DEEPSEEK_FORMAL_RESPONSES_SSE_OR_HTTP_ERROR'

    def validate_route(self,scope):
        ensure(scope.get('endpoint')==ENDPOINT and scope.get('api_protocol')=='responses'
            and scope.get('network_route_policy')==route(),'DEEPSEEK_DIRECT_OFFICIAL_ONLY')

    def validate_model(self,requested,returned):
        ensure(requested==returned==MODEL,'DEEPSEEK_EXACT_MODEL_MISMATCH')

    def validate_spend(self,scope):check_spend(scope)
    def rates(self,scope,model):
        rates=scope['spend_policy']['rates'][model]
        return [rates['input_miss'],rates['output'],rates['input_hit']]
    def reserve(self,scope,model,nbytes):return reserve(scope,model,nbytes)

    def serialize(self,scope,model,messages):
        self.validate_route(scope);self.validate_model(model,model)
        payload=super().serialize(scope,model,messages);payload['top_p']=1
        input_guard_receipt(scope,pc.canonical(payload),scope['slots'][0]['id'])
        return payload

    def decode_http_result(self,scope,wire,status):
        if status==200:
            parser=pt.ResponsesAssembly(pt.Lifecycle());parser.feed(wire)
            body=strict_json(parser.body())
            body.update(native_usage=parser.response.get('usage'),native_response=parser.response)
            return pc.canonical(body)
        ensure(type(status) is int and 400<=status<500 and status!=408,'DEEPSEEK_HTTP_OUTCOME_UNKNOWN')
        native=strict_json(wire);error=native.get('error') if isinstance(native,dict) else None
        ensure(isinstance(error,dict) and isinstance(error.get('message'),str),'DEEPSEEK_HTTP_ERROR_UNTRUSTED')
        code=str(error.get('code') or error.get('type') or '').lower();message=error['message'].lower()
        length=status==413 or code in ('context_length_exceeded','request_too_large','input_too_long') or (
            status==400 and ('context' in message or 'request' in message or 'input' in message) and
            any(s in message for s in ('too long','too large','maximum context','exceed')))
        return pc.canonical({'model':MODEL,'choices':[],'usage':None,'native_usage':None,'native_response':native,
            'http_terminal_status':status,'responses_api_status':'failed',
            'terminal_rejection':'TERMINAL_KNOWN_INPUT_LIMIT_REJECTION' if length else 'TERMINAL_KNOWN_PROVIDER_REJECTION'})

    def decode(self,scope,wire):return self.decode_http_result(scope,wire,200)

    def terminal(self,scope,body):
        if 'http_terminal_status' in body:
            return 'failed','http.rejected',body['terminal_rejection']
        status,event,reason=super().terminal(scope,body)
        if status=='failed':
            error=(body.get('native_response') or {}).get('error') or {}
            if error.get('code') in ('context_length_exceeded','request_too_large','input_too_long'):
                reason='TERMINAL_KNOWN_INPUT_LIMIT_REJECTION'
        return status,event,reason

    def exchange(self,scope,payload,credential,sink,command):
        # The existing bounded DeepSeek worker owns all actual HTTP I/O.
        result=super().exchange(scope,payload,credential,sink,command)
        try:body=self.decode_http_result(scope,result.wire,result.status)
        except (ValueError,TypeError,KeyError):
            raise pt.TransportFault('TRANSPORT_PROTOCOL_OR_CONNECTION_ERROR',result.wire,result.status) from None
        return pt.TransportResult(result.status,body,result.wire)
