"""Versioned two-stage scope. Original scope-9 registrations remain immutable."""
from __future__ import annotations
from decimal import Decimal, ROUND_CEILING
import copy
import hashlib
import json
from pathlib import Path
from transcript_store import WORKSPACE, ensure
import provider_contract as pc
import provider_deepseek_formal as ds
import claim_calibration as cc

SCOPE_VERSION = 'apcore-provider-scope-10'
CANDIDATE = 'APCORE_DEEPSEEK_FLASH_STRUCTURAL_PRE_DISPLAY_CALIBRATION_V1'
DIRECTORY = 'persona_core/gpt6_optimization_v2/structural_calibration_20260921_01/'
CONFIG_SHA = '39e1cad6252564f263ee77a133563b8a22c3acda9e0294df563858e949a81868'


def pipeline_contract():
    return {'version': 'APCORE_FIXED_TWO_STAGE_PIPELINE_1', 'stage_order': ['DRAFT', 'CALIBRATION'],
            'draft_limit': 1, 'calibration_limit': 1, 'automatic_retries': 0, 'extra_candidates': 0,
            'trigger': 'EVERY_KNOWN_USABLE_DRAFT_WITHOUT_PRIOR_HARD_STOP',
            'calibration_policy': cc.VERSION, 'policy_sha256': cc.text_sha(cc.POLICY),
            'draft_max_input_bytes': 24576, 'draft_max_request_bytes': 32768,
            'calibration_max_input_bytes': cc.MAX_INPUT_BYTES,
            'calibration_max_request_bytes': cc.MAX_INPUT_BYTES + 8192,
            'calibration_max_draft_bytes': cc.MAX_DRAFT_BYTES, 'max_output_tokens_per_stage': 32768,
            'input_overflow': 'HOLD_NO_TRUNCATION_NO_REQUEST',
            'disposal': ['KEEP', 'REVISE', 'HOLD'], 'state_authority': False,
            'journal_version': 'APCORE_STAGE_JOURNAL_2', 'prompt_includes_private_evaluation': False}


def pipeline_identity():
    return pc.digest({'contract': pipeline_contract(), 'source_binding': pc.runtime_source_binding()})


def scope_contract_identity(scope):
    return pc.digest({k:v for k,v in scope.items() if k not in ('batch_id','principal_id','request_stage')})


def build_scope(revision,suite_data,pricing,transport_policy,network_route_policy,*,
                authorization_file,pricing_file,acceptance_config_file,input_proof_file=None,phase='FORMAL'):
    ensure(input_proof_file is None and phase in {'SMOKE','FORMAL'},'STRUCTURAL_SCOPE_BUILD_ARGUMENTS')
    cfg_ref={'path':DIRECTORY+'CONFIGURATION_PREREGISTRATION.json','sha256':CONFIG_SHA}
    cfg=ds.strict_json(ds.verify_reference(cfg_ref).read_bytes())
    acceptance=ds.strict_json(acceptance_config_file.read_bytes())
    design_ref=cfg['smoke_input_design'] if phase=='SMOKE' else cfg['formal_input_design']
    design=ds.strict_json(ds.verify_reference(design_ref).read_bytes())
    ensure(suite_data['slots']==design['slots'],'STRUCTURAL_SCOPE_BUILD_INPUT_CHANGED')
    refs={'configuration':cfg_ref,'contract':ds.reference(WORKSPACE/DIRECTORY/'CONFIGURATION_FREEZE.json'),
          'input_design':design_ref,'quality_policy':cfg['model_quality_policy_identity'],
          'dataset':cfg['dataset_identity'],'rubric':cfg['rubric_identity'],
          'criterion_routing':cfg['criterion_routing_identity'],
          'source_manifest':acceptance['acceptance_source_manifest'],
          'acceptance_config':ds.reference(acceptance_config_file)}
    scope={'schema_version':SCOPE_VERSION,'provider_id':'deepseek','candidate_id':CANDIDATE,
        'batch_id':'APCORE-G6-V2-'+revision,'principal_id':'APCORE_G6_V2_'+revision,
        'batch_design_id':'APCORE_STRUCTURAL_'+phase+'_1',
        'validation_purpose':'NON_BENCHMARK_SMOKE' if phase=='SMOKE' else 'FORMAL_EXTERNAL44_CONFIGURATION_QUALIFICATION',
        'formal_validation':True,'slots':design['slots'],'authored_probes':design.get('authored_probes',[]),
        'request_limits':design['request_limits'],'pipeline':pipeline_contract(),'pipeline_identity':pipeline_identity(),
        'endpoint':ds.ENDPOINT,'api_protocol':'responses','primary_model':ds.MODEL,'switch_model':ds.MODEL,
        'stream':True,'thinking':{'type':'enabled'},'reasoning_effort':'max','tools_allowed':False,
        'automatic_paid_retries':0,'generation_config':ds.generation_options(),
        'max_input_bytes':24576,'max_request_bytes':32768,'input_overhead_reserve_tokens':4096,
        'input_budget_envelope_tokens':ds.INPUT_ENVELOPE,'max_output_tokens':32768,
        'request_timeout_seconds':600,'transport_policy':transport_policy,'network_route_policy':network_route_policy,
        'transport_contract_version':pc.TRANSPORT_VERSION,'capabilities':ds.CAPABILITIES.declaration(),
        'source_binding':pc.runtime_source_binding(),'identity_references':refs,'count_api_requests':0,
        'evaluation_schema':'apcore-gpt6-evaluation-2','criteria_count':176,'gate_denominators':{'A':176,'B':132},
        'stop_rules':dict(ds.STOP_RULES,required_criterion='REQUIRED_CONVERSATION_FAIL_STOP'),
        'spend_policy':{'mode':'REVIEWED_RATES_PROJECT_AUTHORIZATION','currency':'CNY','rates':pricing['rates'],
            'price_identity':ds.reference(pricing_file),'authorization_identity':ds.reference(authorization_file)},
        'output_budget_includes_reasoning':True,'automatic_capacity_escalation':False,'billing_verified':False}
    total=design['request_limits']['total']*reserve(scope,ds.MODEL,24576)
    scope.update(reserved_upper_micro_cny=total,total_guard_cny=str(Decimal(total)/1000000))
    return scope


def reserve(scope, model, nbytes):
    limit = cc.MAX_INPUT_BYTES if scope.get('request_stage') == 'CALIBRATION' else 24576
    ensure(model == ds.MODEL and type(nbytes) is int and 0 <= nbytes <= limit, 'STRUCTURAL_RESERVE_INPUT')
    rates = scope['spend_policy']['rates'][model]
    return int((Decimal(ds.INPUT_ENVELOPE) * Decimal(rates['input_miss']) +
                Decimal(32768) * Decimal(rates['output'])).to_integral_value(rounding=ROUND_CEILING))


def input_guard_receipt(scope, payload, slot_id):
    value = ds.strict_json(payload)
    ensure(payload == pc.canonical(value) and set(value) == {'model','input','stream','max_output_tokens','reasoning','top_p'},
           'STRUCTURAL_REQUEST_FIELDS')
    ensure(value['model'] == ds.MODEL and value['stream'] is True and type(value['max_output_tokens']) is int
           and value['max_output_tokens'] == 32768 and value['reasoning'] == {'effort':'max'}
           and type(value['top_p']) is int and value['top_p'] == 1, 'STRUCTURAL_REQUEST_CONTROLS')
    messages = value['input']
    ensure(type(messages) is list and messages and all(type(m) is dict and set(m) == {'role','content'}
           and m['role'] in {'system','user','assistant'} and type(m['content']) is str for m in messages),
           'STRUCTURAL_MESSAGE_SHAPE')
    stage = scope.get('request_stage', 'DRAFT')
    ensure(stage in {'DRAFT','CALIBRATION'}, 'STRUCTURAL_THIRD_STAGE_FORBIDDEN')
    limits = pipeline_contract()
    prefix = stage.lower()
    ensure(len(pc.canonical(messages)) <= limits[prefix+'_max_input_bytes'] and
           len(payload) <= limits[prefix+'_max_request_bytes'], 'STRUCTURAL_INPUT_BUDGET')
    ids = [s['id'] for s in scope['slots']]
    if stage == 'CALIBRATION':
        ids += [s['id'] for s in scope.get('authored_probes', [])]
    ensure(slot_id in ids, 'STRUCTURAL_INPUT_SLOT')
    return {'version':'APCORE_STAGE_INPUT_RECEIPT_1','stage':stage,'slot_id':slot_id,
            'request_sha256':hashlib.sha256(payload).hexdigest(),'messages_sha256':pc.digest(messages),
            'canonical_message_bytes':len(pc.canonical(messages)),'canonical_request_bytes':len(payload),
            'scope_sha256':pc.digest(scope),'pipeline_identity':scope['pipeline_identity'],
            'input_tokens_pre_request':None,'exact_token_proof':False,'automatic_truncation':False}


def check_spend(scope):
    policy = scope['spend_policy']
    ensure(set(policy) == {'mode','currency','rates','price_identity','authorization_identity'}
           and policy['mode'] == 'REVIEWED_RATES_PROJECT_AUTHORIZATION' and policy['currency'] == 'CNY',
           'STRUCTURAL_SPEND_POLICY')
    price = ds.strict_json(ds.verify_reference(policy['price_identity']).read_bytes())
    ensure(price.get('official_pricing_refreshed') is True and price.get('currency') == 'CNY'
           and price.get('rates') == policy['rates'] == {ds.MODEL:{'input_miss':'2','output':'8','input_hit':'0.04'}},
           'STRUCTURAL_PRICE_IDENTITY')
    ensure(price.get('sources') and all(s['url'].startswith('https://api-docs.deepseek.com/') for s in price['sources']),
           'STRUCTURAL_PRICE_SOURCE')
    auth = ds.strict_json(ds.verify_reference(policy['authorization_identity']).read_bytes())
    ensure(auth.get('schema_version') == 'APCORE_STRUCTURAL_TASK_AUTHORIZATION_1'
           and auth.get('candidate_id') == CANDIDATE and auth.get('max_smoke_requests') == 50
           and auth.get('max_formal_requests') == 88 and auth.get('max_total_provider_requests') == 138
           and auth.get('max_candidates') == auth.get('max_fresh_revisions') == 1
           and auth.get('automatic_paid_retries') == auth.get('readiness_requests') == auth.get('count_api_requests') == 0
           and auth.get('fallback_allowed') is False, 'STRUCTURAL_TASK_AUTHORIZATION')
    cap = scope['request_limits']['total'] * reserve(scope, ds.MODEL, 0)
    ensure(scope.get('reserved_upper_micro_cny') == cap and Decimal(scope['total_guard_cny']) * 1000000 == cap,
           'STRUCTURAL_FEE_CAP')


def check_scope(scope, adapter):
    from semantic_binding import validate_binding
    ensure(scope.get('schema_version') == SCOPE_VERSION and scope.get('candidate_id') == CANDIDATE
           and scope.get('provider_id') == adapter.provider_id == 'deepseek', 'STRUCTURAL_IDENTITY')
    ensure(scope.get('request_stage', 'DRAFT') == 'DRAFT', 'STRUCTURAL_TOP_LEVEL_DRAFT_SCOPE_REQUIRED')
    ensure(scope.get('pipeline') == pipeline_contract() and scope.get('pipeline_identity') == pipeline_identity()
           and scope.get('source_binding') == pc.runtime_source_binding(), 'STRUCTURAL_PIPELINE_CHANGED')
    ensure(scope.get('formal_validation') is True and scope.get('stream') is True and scope.get('tools_allowed') is False
           and scope.get('automatic_paid_retries') == 0 and scope.get('automatic_capacity_escalation') is False,
           'STRUCTURAL_EXECUTION_CONTROLS')
    ensure(scope.get('generation_config') == ds.generation_options() and scope.get('max_input_bytes') == 24576
           and scope.get('max_request_bytes') == 32768 and scope.get('max_output_tokens') == 32768
           and scope.get('request_timeout_seconds') == 600 and scope.get('reasoning_effort') == 'max'
           and scope.get('thinking') == {'type':'enabled'} and scope.get('count_api_requests') == 0,
           'STRUCTURAL_MODEL_OPTIONS')
    ensure(scope.get('transport_policy') == ds.configuration()['transport_policy']
           and scope.get('capabilities') == ds.CAPABILITIES.declaration()
           and scope.get('input_budget_envelope_tokens') == ds.INPUT_ENVELOPE,
           'STRUCTURAL_TRANSPORT_OR_RESERVE')
    adapter.validate_route(scope)
    for value in scope['identity_references'].values():
        ds.verify_reference(value)
    design = ds.strict_json(ds.verify_reference(scope['identity_references']['input_design']).read_bytes())
    ensure(design['slots'] == scope['slots'] and design.get('authored_probes', []) == scope.get('authored_probes', [])
           and design['request_limits'] == scope['request_limits'], 'STRUCTURAL_INPUT_DESIGN_CHANGED')
    ensure(len({s['id'] for s in scope['slots'] + scope.get('authored_probes', [])}) ==
           len(scope['slots']) + len(scope.get('authored_probes', [])), 'STRUCTURAL_DUPLICATE_SLOT')
    ensure(all(s['model'] == ds.MODEL and type(s['user_text']) is str and s['entity_label'] for s in scope['slots']),
           'STRUCTURAL_ROLE_OR_INPUT_CHANGED')
    phase = scope['validation_purpose']
    if phase!='OFFLINE_SYNTHETIC':
        cfg=ds.strict_json(ds.verify_reference(scope['identity_references']['configuration']).read_bytes())
        ensure(scope['identity_references']['configuration']=={'path':DIRECTORY+'CONFIGURATION_PREREGISTRATION.json','sha256':CONFIG_SHA}
               and cfg['candidate_id']==CANDIDATE and cfg['pipeline']==pipeline_contract(), 'STRUCTURAL_REGISTERED_CONFIGURATION')
        field='formal_input_design' if phase=='FORMAL_EXTERNAL44_CONFIGURATION_QUALIFICATION' else 'smoke_input_design'
        ensure(scope['identity_references']['input_design']==cfg[field], 'STRUCTURAL_REGISTERED_DESIGN')
        for key,field in [('dataset','dataset_identity'),('rubric','rubric_identity'),('criterion_routing','criterion_routing_identity'),
                          ('quality_policy','model_quality_policy_identity')]:
            ensure(scope['identity_references'][key]==cfg[field], 'STRUCTURAL_FROZEN_SCIENTIFIC_IDENTITY')
        frozen=ds.strict_json(ds.verify_reference(scope['identity_references']['contract']).read_bytes())
        for path,digest in frozen['files'].items():ds.verify_reference({'path':path,'sha256':digest})
        ensure(scope.get('stop_rules')==dict(ds.STOP_RULES,required_criterion='REQUIRED_CONVERSATION_FAIL_STOP'),
               'STRUCTURAL_STOP_RULES_CHANGED')
    if phase == 'FORMAL_EXTERNAL44_CONFIGURATION_QUALIFICATION':
        ensure(scope['request_limits'] == {'draft':44,'calibration':44,'total':88}
               and scope.get('authored_probes', []) == [] and len(scope['slots']) == 44,
               'STRUCTURAL_FORMAL_REQUEST_LIMITS')
        original = ds.strict_json((WORKSPACE/'persona_core/operational_build_v1/evidence/R047-01/freeze_20260907T164424498856Z/EXECUTION_SCOPE.json').read_bytes())['slots']
        schedule = ds.strict_json(ds.verify_reference(ds.configuration()['schedule_identity']).read_bytes())['slots']
        ensure([dict(position=i+1,slot_id=s['id'],case_id=s['case_id'],model_role=s['model_role'],model=s['model'],
                     host_action_before=s.get('host_action_before')) for i,s in enumerate(scope['slots'])] == schedule,
               'STRUCTURAL_ORIGINAL_SCHEDULE_CHANGED')
        fields = ('id','case_id','entity_label','user_text')
        ids = {s['id'] for s in scope['slots']}
        ensure([{k:s.get(k) for k in fields} for s in scope['slots']] ==
               [{k:s.get(k) for k in fields} for s in original if s['id'] in ids], 'STRUCTURAL_BENCHMARK_CHANGED')
        ensure(scope.get('criteria_count') == 176 and scope.get('gate_denominators') == {'A':176,'B':132},
               'STRUCTURAL_DENOMINATORS_CHANGED')
    else:
        ensure(phase in {'NON_BENCHMARK_SMOKE','OFFLINE_SYNTHETIC'}, 'STRUCTURAL_SCOPE_PURPOSE')
        limits = scope['request_limits']
        ensure(limits == {'draft':len(scope['slots']),
                         'calibration':len(scope['slots'])+len(scope.get('authored_probes', [])),
                         'total':2*len(scope['slots'])+len(scope.get('authored_probes', []))}, 'STRUCTURAL_REQUEST_LIMITS')
        if phase == 'NON_BENCHMARK_SMOKE':
            ensure(len(scope['slots']) == 20 and len(scope.get('authored_probes', [])) == 10
                   and limits['total'] == 50, 'STRUCTURAL_SMOKE_DESIGN')
    binding = validate_binding(scope['semantic_acceptance_binding'], scope)
    ensure(binding.get('calibration_pipeline_identity') == scope['pipeline_identity']
           and binding.get('consumer_purpose') == 'DISPLAY', 'STRUCTURAL_DISPLAY_BINDING')
    if phase!='OFFLINE_SYNTHETIC':
        ensure(all(scope['identity_references'][key]==binding[field] for key,field in
                   [('dataset','dataset_identity'),('rubric','rubric_identity'),('criterion_routing','criterion_routing'),
                    ('source_manifest','acceptance_source_manifest')]), 'STRUCTURAL_CONSUMER_SCIENTIFIC_IDENTITY')
    check_spend(scope)


def require_paid_activation(scope):
    ensure(scope['validation_purpose'] != 'OFFLINE_SYNTHETIC', 'STRUCTURAL_OFFLINE_NETWORK_FORBIDDEN')
    ensure(scope['identity_references']['configuration'] == {
           'path':DIRECTORY+'CONFIGURATION_PREREGISTRATION.json','sha256':CONFIG_SHA}, 'STRUCTURAL_UNREGISTERED_CONFIG')
    # The canonical writer owns gate activation. No source file alone grants it.
    import sys
    sys.path.insert(0, str(WORKSPACE/'persona_core/gpt6_optimization_v2/tools'))
    import governance_v2 as g
    pointer = g.load(WORKSPACE/g.CANONICAL)
    state = g.pinned_json(WORKSPACE, pointer['checkpoint'])
    g.validate_paid_state(WORKSPACE, state)
    ensure(state.get('paid_requests_allowed') is True and state.get('active_paid_scope_sha256') == pc.digest(
           {k:v for k,v in scope.items() if k != 'request_stage'}), 'STRUCTURAL_PAID_GATE_CLOSED_OR_FOREIGN')


class StructuralAdapter(ds.DeepSeekFormalAdapter):
    def validate_spend(self, scope):
        check_spend(scope)

    def reserve(self, scope, model, nbytes):
        return reserve(scope, model, nbytes)

    def serialize(self, scope, model, messages):
        self.validate_route(scope)
        self.validate_model(model, model)
        payload = {'model':model,'input':messages,'stream':True,'max_output_tokens':32768,
                   'reasoning':{'effort':'max'},'top_p':1}
        input_guard_receipt(scope, pc.canonical(payload), scope['slots'][0]['id'])
        return payload

    def exchange(self, scope, payload, credential, sink, command):
        require_paid_activation(scope)
        return super().exchange(scope, payload, credential, sink, command)
