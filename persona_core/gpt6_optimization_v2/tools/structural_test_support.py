"""Authored mock-wire fixtures; no target-model quality judgments."""
from pathlib import Path
import sys, json, uuid, copy
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'persona_core/operational_runtime_v1'),str(Path(__file__).parent)]
import evaluation_runner as er
import provider_structural as ps
import provider_deepseek_formal as ds
import provider_contract as pc
import claim_calibration as cc
import test_deepseek_successor_binding as wire_fixture


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(pc.canonical(value))
    return ds.reference(path)


def scope_fixture(base, user_text='清单有3份文件，另有4份且不重复。合计多少？',probes=None):
    base.mkdir(parents=True,exist_ok=False)
    slots=[{'id':f'X{i:02d}_T1','case_id':f'X{i:02d}','entity_label':f'SYNTHETIC_{i:02d}',
            'user_text':user_text if i==1 else f'独立离线合同样本{i}：给定集合里有三个元素。请只复述这个数量。',
            'model':ds.MODEL,'model_role':'PRIMARY','host_action_before':None} for i in range(1,45)]
    cases=base/'CASES.json';write(cases,{'kind':'INDEPENDENT_AUTHORED_DEVELOPMENT','slots':slots})
    rubric=base/'PRIVATE_RUBRIC.json';write(rubric,{'kind':'AUTHORED_PATH_CONTRACT_ONLY','marker':'SYNTHETIC_REVIEW_EXPECTATION_NEVER_SENT'})
    routing={'original_denominator':176,'turn_count':44,
             'source_hashes':{'CASES.json':er.sha(cases),'PRIVATE_RUBRIC.json':er.sha(rubric)},
             'criteria':[{'turn_id':s['id'],'criterion_id':f'synthetic_{j}','original_criterion_wording':f'synthetic_{j}',
                          'route':'CONVERSATION_UTILITY' if j==0 else 'BOTH'} for s in slots for j in range(4)]}
    route_ref=write(base/'routing.json',routing)
    p1=er.GOAL/'architecture_scope_reconciliation_20260920_01/CONTRACT_FREEZE_MANIFEST.json'
    contract=er.read(p1);contract['files'][route_ref['path']]=route_ref['sha256']
    contract_ref=write(base/'contract.json',contract)
    config=er.read(er.GOAL/'bounded_boundary_p2_p3_20260920_01/FORMAL_ACCEPTANCE_CONFIG.json')
    config.update(acceptance_source_freeze=base.name,contract_manifest=contract_ref,criterion_routing=route_ref,
                  calibration_pipeline_identity=ps.pipeline_identity())
    source=er.source_bindings();source.update(er.read(p1)['files'])
    source.update(contract['files'])
    for p in [cases,rubric,base/'routing.json',base/'contract.json']:
        source[er.relative(p)]=er.sha(p)
    config['acceptance_source_manifest']=write(base/'SOURCE.json',{'freeze_id':base.name,'status':'OFFLINE_TEST_ONLY','files':source})
    cfg=base/'acceptance.json';write(cfg,config)
    probes=probes or []
    limits={'draft':44,'calibration':44+len(probes),'total':88+len(probes)}
    design=write(base/'input_design.json',{'slots':slots,'authored_probes':probes,'request_limits':limits})
    scope={'schema_version':ps.SCOPE_VERSION,'provider_id':'deepseek','candidate_id':ps.CANDIDATE,
        'batch_id':'SYNTHETIC_'+base.name,'principal_id':'SYNTHETIC_'+base.name,'formal_validation':True,
        'validation_purpose':'OFFLINE_SYNTHETIC','slots':slots,'authored_probes':probes,
        'request_limits':limits,'pipeline':ps.pipeline_contract(),'pipeline_identity':ps.pipeline_identity(),
        'primary_model':ds.MODEL,'switch_model':ds.MODEL,'endpoint':ds.ENDPOINT,'api_protocol':'responses',
        'stream':True,'thinking':{'type':'enabled'},'reasoning_effort':'max','tools_allowed':False,
        'automatic_paid_retries':0,'count_api_requests':0,'generation_config':ds.generation_options(),
        'max_input_bytes':24576,'max_request_bytes':32768,'max_output_tokens':32768,
        'input_overhead_reserve_tokens':4096,'input_budget_envelope_tokens':ds.INPUT_ENVELOPE,
        'request_timeout_seconds':600,'transport_policy':ds.configuration()['transport_policy'],
        'network_route_policy':ds.route(),'transport_contract_version':pc.TRANSPORT_VERSION,
        'capabilities':ds.CAPABILITIES.declaration(),'source_binding':pc.runtime_source_binding(),
        'criteria_count':176,'gate_denominators':{'A':176,'B':132},'automatic_capacity_escalation':False,
        'stop_rules':dict(ds.STOP_RULES,required_criterion='REQUIRED_CONVERSATION_FAIL_STOP'),
        'identity_references':{'input_design':design,'criterion_routing':route_ref,
            'configuration':write(base/'CONFIG.json',{'kind':'OFFLINE_ONLY','pipeline':ps.pipeline_contract()}),
            'source_manifest':config['acceptance_source_manifest'],'dataset':ds.reference(cases),
            'rubric':ds.reference(rubric),'acceptance_config':ds.reference(cfg)},
        'spend_policy':{'mode':'REVIEWED_RATES_PROJECT_AUTHORIZATION','currency':'CNY',
            'rates':{ds.MODEL:{'input_miss':'2','output':'8','input_hit':'0.04'}},
            'price_identity':ds.reference(ROOT/ds.DIRECTORY/'OFFICIAL_PRICING_EVIDENCE.json'),
            'authorization_identity':ds.reference(ROOT/ps.DIRECTORY/'TASK_AUTHORIZATION.json')}}
    from decimal import Decimal
    amount=limits['total']*ps.reserve(scope,ds.MODEL,0)
    scope.update(reserved_upper_micro_cny=amount,total_guard_cny=str(Decimal(amount)/1000000))
    scope['semantic_acceptance_binding']=er.build_acceptance_binding(scope,{'cases_path':cases},cfg,rubric_path=rubric,offline=True)
    ps.check_scope(scope,ps.StructuralAdapter())
    return scope


def authored_audit(supplied,case):
    before=case.get('before',case['draft'])
    decision=case.get('decision','KEEP')
    over=decision=='REVISE'
    claim={'id':'c1','quote':before,'occurrence':0,'stance':case.get('stance','ASSERTED'),
           'certainty':'explicit','conditions':'as stated','scope':'local input','quantifier':'as stated',
           'frequency':'as stated','causal_strength':'as stated','basis':'INPUT',
           'references':[{'message_index':len(supplied['ELIGIBLE_CONTEXT'])-1,
                          'quote':supplied['ELIGIBLE_CONTEXT'][-1]['content'],'occurrence':0}],
           'missing_premises':['discriminating evidence'] if over else [],
           'open_alternatives':['unexcluded alternatives'] if over else [],
           'assessment':'OVERSTATED' if over else 'NONASSERTION' if case.get('stance') else 'SUPPORTED',
           'rationale':'Authored offline path fixture; no model-quality judgment.'}
    return {'version':cc.VERSION,'input_identity':supplied['input_identity'],'decision':decision,'claims':[claim],
            'no_assertions_reason':'','edits':[{'claim_id':'c1','before':before,'after':case['after'],
             'resolution':'Authored localized removal of unsupported strength.'}] if over else [],
            'unresolved_claim_ids':[],'final_text':case.get('final',case['draft']) if decision!='HOLD' else None,
            'decision_reason':'Authored offline fixture exercising the fixed stage.'}


def transport_for(scope,case,sent,mutate=None,stage_fault=None):
    adapter=ps.StructuralAdapter()
    def transport(payload,key):
        value=json.loads(payload);sent.append(value)
        second=len(value['input'])==2 and value['input'][0]['content']==cc.POLICY
        if stage_fault:
            maybe=stage_fault('CALIBRATION' if second else 'DRAFT',value)
            if maybe is not None:return maybe
        if second:
            supplied=json.loads(value['input'][-1]['content']);out=authored_audit(supplied,case)
            if mutate:out=mutate(out)
            text=out if isinstance(out,str) else pc.canonical(out).decode()
        else:text=case['draft']
        wire=wire_fixture.wire(wire_fixture.response(text=text))
        import provider_transport as pt
        return pt.TransportResult(200,adapter.decode_http_result(scope,wire,200),wire)
    return transport
