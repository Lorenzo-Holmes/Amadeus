"""Read only a frozen host typed catalog. User/model prose never fills it."""
import json
from dataclasses import fields
from semantic_types import *
from semantic_admission import TrustedAdmission
from semantic_binding import ADAPTER_VERSION, REQUEST_VERSION, reference, layer

def exact(cls, value):
    require(type(value) is dict and set(value)=={f.name for f in fields(cls)},'HOST_CATALOG_FIELDS')
    return dict(value)

def scope(value):
    value=exact(Scope,value)
    return Scope(tuple(value['path']))

def proposition(value):
    value=exact(Proposition,value); value['relation_domain']=Domain(value['relation_domain'])
    return Proposition(**value)

def strength(value):
    value=exact(Strength,value)
    require(all(type(v) is int for v in value.values()),'HOST_STRENGTH_TYPE')
    return Strength(Epistemic(value['epistemic']),Disposition(value['disposition']),Coverage(value['coverage']))

class TrustedAdmissionAdapter:
    version=ADAPTER_VERSION
    def __init__(self,binding):
        self.binding=binding

    def __call__(self,handle,turn,context):
        with layer('ADMISSION'):
            data=json.loads(reference(self.binding['semantic_source']).read_text(encoding='utf-8-sig'))
            require(set(data)=={'version','entities','sources','evidence','rules','candidates','universes','scopes','user_report'},
                    'HOST_CATALOG_SCHEMA')
            require(data['version']==self.version,'HOST_CATALOG_VERSION')
            a=TrustedAdmission(session_id=handle.session_id,entity_id=handle.entity_id,
                               turn_id=turn['turn_id'],raw_user_text=turn['user_text'])
            for value in data['entities']: a.entity(Entity(**exact(Entity,value)))
            for value in data['sources']:
                value=exact(Source,value); value['origin']=Origin(value['origin']); a.source(Source(**value))
            for value in data['scopes']:
                require(set(value)=={'scope','label_id'},'HOST_SCOPE_SCHEMA')
                a.scope(scope(value['scope']),value['label_id'])
            for value in data['evidence']:
                v=exact(Evidence,value); v.update(proposition=proposition(v['proposition']),scope=scope(v['scope']),
                    strength=strength(v['strength']),modality=Modality(v['modality']),
                    temporal_state=TemporalState(v['temporal_state']),role=Role(v['role']),conditions=tuple(v['conditions']))
                a.fact(Evidence(**v))
            for value in data['rules']:
                v=exact(Rule,value); v.update(premises=tuple(proposition(p) for p in v['premises']),
                    conclusion=proposition(v['conclusion']),scope=scope(v['scope']),
                    strength=strength(v['strength']),conditions=tuple(v['conditions']))
                a.rule(Rule(**v))
            for value in data['candidates']:
                v=exact(Candidate,value); v.update(proposition=proposition(v['proposition']),scope=scope(v['scope']))
                a.candidate(Candidate(**v))
            for value in data['universes']:
                v=exact(Universe,value); v.update(scope=scope(v['scope']),members=tuple(v['members']),
                    unresolved_remainder=None if v['unresolved_remainder'] is None else tuple(v['unresolved_remainder']))
                a.universe(Universe(**v))
            report=data['user_report']
            if report is None:
                a.unparsed.append(digest(turn['user_text']))
            else:
                require(set(report)=={'actor_id','scope'},'HOST_REPORT_SCHEMA')
                a.user_statement(turn['user_text'],actor_id=report['actor_id'],scope=scope(report['scope']))
            return a.freeze()

def request_contract(state,binding):
    """The host vocabulary is descriptive. Only validator certificates authorize."""
    from semantic_binding import strict_selected
    require(strict_selected(binding),'STRICT_BOUNDED_PATH_NOT_SELECTED')
    return {'version':REQUEST_VERSION,'authority':'PROPOSAL_ONLY',
        'response_kind':'PROPOSED_SEMANTIC_PLAN','host_only_authority':'AUTHORIZED_CLAIMS',
        'response_fields':['kind','plan','visible_text'],
        'plan_fields':[f.name for f in fields(SemanticPlan)],
        'claim_fields':[f.name for f in fields(Claim)],
        'nested_fields':{cls.__name__:[f.name for f in fields(cls)] for cls in (Proposition,Scope,Strength)},
        'enums':{cls.__name__:[e.value for e in cls] for cls in
                 (Domain,Epistemic,Disposition,Coverage,Modality,TemporalState)},
        'claim_types':['ASSERTION','EXCLUSION','CLOSURE','RESPONSIBILITY','LIMITATION'],
        'claim_optional_defaults':{f.name:f.default for f in fields(Claim) if f.name in
            ('bridge_refs','rule_ref','unresolved_dependencies','temporal_state','speaker',
             'attribution','candidate_id','universe_id','member_claims')},
        'plan_kind':'PROPOSED_PLAN','plan_version':VERSION,
        'context_digest':state.context_digest,'trusted_inventory':state.public_state(),
        'binding_sha256':digest(binding),
        'instructions':'Return exactly one JSON object with kind=PROPOSED_SEMANTIC_PLAN, plan and visible_text. '
        'plan is the strict proposed plan schema or null when input is unsupported. '
        'Certificates, completeness declarations and authority flags are forbidden. '
        'Use only the admitted inventory; unparsed text grants no authority. '
        'The host validates and renders the final product answer.'}

def parse_response(raw):
    def pairs(items):
        d={}
        for key,value in items:
            require(key not in d,'DUPLICATE_JSON_KEY'); d[key]=value
        return d
    require(type(raw) is str and len(raw.encode())<=131072,'FORMAL_RESPONSE_SIZE')
    try:
        value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(SemanticError('NONFINITE_JSON')))
        require(type(value) is dict and set(value)=={'kind','plan','visible_text'},'PROPOSAL_ENVELOPE_FIELDS')
        require(value['kind']=='PROPOSED_SEMANTIC_PLAN' and type(value['visible_text']) is str,'PROPOSAL_ENVELOPE_KIND')
        plan=parse_plan(canonical(value['plan'])) if value['plan'] is not None else None
        return plan,value['visible_text']
    except (TypeError,ValueError,RecursionError) as exc:
        if isinstance(exc,SemanticError): raise
        raise SemanticError('INVALID_PROPOSAL_ENVELOPE') from None
