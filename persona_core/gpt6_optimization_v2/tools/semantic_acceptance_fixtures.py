"""Synthetic typed host inputs for bounded offline acceptance tests."""
from dataclasses import replace
from semantic_types import *
from semantic_admission import TrustedAdmission

LOCAL=Scope(('model','local'))
GLOBAL=Scope(('model',))

def admission(identity=('session','entity','turn','typed premise')):
    a=TrustedAdmission(session_id=identity[0],entity_id=identity[1],turn_id=identity[2],raw_user_text=identity[3])
    for key,label,kind in [('host','来源','ACTOR'),('person','林','ACTOR'),('other_person','郁','ACTOR'),
            ('item','筹码甲','OBJECT'),('blue','蓝色','PROPERTY'),('round','圆形','PROPERTY'),
            ('green','绿标','PROPERTY'),('checked','复核','PROPERTY'),('other','筹码乙','OBJECT'),
            ('task','海报排版','TASK'),('adjacent','票务','TASK'),('condition','密封圈完好','CONDITION'),
            ('candidate_a','模块甲','CANDIDATE'),('candidate_b','模块乙','CANDIDATE'),
            ('anomaly','故障','OBJECT'),('boundary','本次形式模型','SCOPE')]:
        a.entity(Entity(key,label,kind))
    a.source(Source('source',Origin.PROGRAM,'host','1',digest('typed host observation')))
    a.source(Source('rule_source',Origin.VERIFIED,'host','1',digest('reviewed formal rule'),'FORMAL_PREMISE'))
    a.scope(LOCAL,'boundary')
    a.entity(Entity('global_boundary','整个模型','SCOPE')); a.scope(GLOBAL,'global_boundary')
    return a

def fact_claim(f, *, claim_id='claim',kind=None,source_refs=None,**kw):
    kind=kind or ('EXCLUSION' if f.proposition.predicate=='excluded' else
                  'RESPONSIBILITY' if f.proposition.predicate in {'assigned','completed','planned','proposed'} else 'ASSERTION')
    return Claim(claim_id,kind,f.proposition,f.scope,f.modality,f.strength,
        source_refs or (f.source_id,),(f.evidence_id,),temporal_state=f.temporal_state,
        unresolved_dependencies=f.conditions,attribution=f.attribution,**kw)

def scenario(name,identity=('session','entity','turn','typed premise')):
    a=admission(identity)
    p=Proposition('is','item','blue',Domain.TRANSFORM)
    if name in {'same_domain_exclusion','bridge_exclusion'}:
        domain=Domain.EXPLANATION if name=='same_domain_exclusion' else Domain.TRANSFORM
        p=replace(p,relation_domain=domain)
        target=Proposition('explains','candidate_a','anomaly',Domain.EXPLANATION)
        a.candidate(Candidate('candidate_a',target,LOCAL))
        f=Evidence('e',p,'source',LOCAL); a.fact(f)
        force=Strength(Epistemic.SUPPORTED,Disposition.EXCLUDED)
        a.rule(Rule('exclude',(p,),replace(target,predicate='excluded'),'rule_source',LOCAL,'EXCLUSION',force,name=='bridge_exclusion'))
        c=replace(fact_claim(f),claim_type='EXCLUSION',proposition=replace(target,predicate='excluded'),
              strength=force,source_refs=('source','rule_source'),rule_ref='exclude',candidate_id='candidate_a',
              bridge_refs=('exclude',) if name=='bridge_exclusion' else ())
        s=a.freeze(); return s,SemanticPlan((c,),s.context_digest)
    if name in {'same_domain','bridge','no_bridge','measurement','row_order','causal'}:
        conclusion=Proposition('is','item','round',Domain.TRANSFORM)
        if name=='bridge':
            p=Proposition('is','item','green',Domain.TRANSFORM)
            conclusion=Proposition('valid','item','checked',Domain.MEASUREMENT)
        elif name in {'no_bridge','row_order'}:
            p=Proposition('before','item','other',Domain.RECORD)
            conclusion=Proposition('before','item','other',Domain.TIMESTAMP)
        elif name=='causal':
            conclusion=Proposition('causes','item','other',Domain.CAUSAL)
        elif name=='measurement':
            p=Proposition('valid','item','checked',Domain.MEASUREMENT)
            conclusion=Proposition('excluded','candidate_a','anomaly',Domain.EXPLANATION)
            a.candidate(Candidate('candidate_a',replace(conclusion,predicate='explains'),LOCAL))
        f=Evidence('e',p,'source',LOCAL,role=Role.VALIDATION_PRECONDITION if name=='measurement' else Role.OBSERVED_EVIDENCE)
        a.fact(f)
        if name in {'same_domain','bridge','causal'}:
            a.rule(Rule('implication',(p,),conclusion,'rule_source',LOCAL,bridge=name in {'bridge','causal'}))
            claim=replace(fact_claim(f),proposition=conclusion,rule_ref='implication',
                          source_refs=('source','rule_source'),bridge_refs=('implication',) if name!='same_domain' else ())
        else:
            claim=replace(fact_claim(f),proposition=conclusion)
            if name=='measurement': claim=replace(claim,claim_type='EXCLUSION',candidate_id='candidate_a',
                                                  strength=Strength(Epistemic.SUPPORTED,Disposition.EXCLUDED))
        state=a.freeze(); return state,SemanticPlan((claim,),state.context_digest)
    if name in {'finite','exhaustive','partial','unknown_remainder','open','local_global'}:
        claims=[]
        for i,cid in enumerate(('candidate_a','candidate_b')):
            p=Proposition('explains',cid,'anomaly',Domain.EXPLANATION)
            a.candidate(Candidate(cid,p,LOCAL))
            excluded=(i==0 or name=='exhaustive')
            f=Evidence('e'+str(i),replace(p,predicate='excluded') if excluded else p,'source',LOCAL,
                Strength(Epistemic.SUPPORTED,Disposition.EXCLUDED if excluded else Disposition.UNASSESSED),
                role=Role.EXCLUSION_EVIDENCE if excluded else Role.OBSERVED_EVIDENCE)
            a.fact(f); claims.append(fact_claim(f,claim_id='c'+str(i),candidate_id=cid))
        remainder=('unknown_branch',) if name=='unknown_remainder' else None if name=='open' else ()
        a.universe(Universe('universe',LOCAL,'boundary',('candidate_a','candidate_b'),'source',
            'OPEN' if name in {'partial','open'} else 'HOST_FINITE_SET','finite-inventory-v1',remainder))
        close=Claim('closure','CLOSURE',Proposition('observed','boundary','boundary',Domain.EXPLANATION),
                    GLOBAL if name=='local_global' else LOCAL,Modality.ASSERTED,
                    Strength(Epistemic.SUPPORTED,Disposition.UNASSESSED,Coverage.EXHAUSTIVE if name=='exhaustive' else Coverage.FINITE),
                    ('source',),(),universe_id='universe',member_claims=tuple(c.claim_id for c in claims))
        if name=='partial': close=replace(close,member_claims=('c0',))
        state=a.freeze(); return state,SemanticPlan(tuple(claims)+(close,),state.context_digest)
    if name in {'assignment','completion','planned','suggested'}:
        pred,domain,phase,attr={'assignment':('assigned',Domain.RESPONSIBILITY,TemporalState.ASSIGNED,'EXPLICITLY_ASSIGNED'),
            'completion':('completed',Domain.EXECUTION,TemporalState.COMPLETED,'EXPLICITLY_COMPLETED'),
            'planned':('planned',Domain.EXECUTION,TemporalState.PLANNED,'PLANNED'),
            'suggested':('proposed',Domain.RESPONSIBILITY,TemporalState.UNSPECIFIED,'PROPOSED')}[name]
        f=Evidence('e',Proposition(pred,'person','task',domain),'source',LOCAL,temporal_state=phase,attribution=attr)
    elif name=='conditional':
        f=Evidence('e',p,'source',LOCAL,modality=Modality.CONDITIONAL,conditions=('condition',))
    elif name=='possible':
        f=Evidence('e',Proposition('explains','candidate_a','anomaly',Domain.EXPLANATION),'source',LOCAL,
                   Strength(Epistemic.POSSIBLE))
    elif name=='measurement_valid':
        f=Evidence('e',Proposition('valid','item','checked',Domain.MEASUREMENT),'source',LOCAL,role=Role.VALIDATION_PRECONDITION)
    elif name=='observed_order':
        f=Evidence('e',Proposition('before','item','other',Domain.RECORD),'source',LOCAL)
    elif name=='unassessed':
        f=Evidence('e',Proposition('unassessed','item','checked',Domain.MEASUREMENT),'source',LOCAL)
    else:
        f=Evidence('e',p,'source',LOCAL)
    a.fact(f)
    if name=='conflict':
        a.fact(replace(f,evidence_id='opposite',proposition=replace(p,polarity=False)))
    state=a.freeze(); return state,SemanticPlan((fact_claim(f),),state.context_digest)

POSITIVE_SCENARIOS=('same_domain','bridge','finite','exhaustive','assignment','completion','planned','suggested',
                    'conditional','possible','measurement_valid','observed_order','unassessed','causal',
                    'same_domain_exclusion','bridge_exclusion')
NEGATIVE_SCENARIOS=('no_bridge','measurement','row_order','partial','unknown_remainder','open','local_global','conflict')
