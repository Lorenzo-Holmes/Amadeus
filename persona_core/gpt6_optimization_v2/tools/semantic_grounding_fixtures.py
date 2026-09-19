"""Authored, synthetic, non-heldout source readings and independent expectations.

No semantic annotations here are inferred by production code. The fixture
author supplies them, and the implementation must preserve their limits.
"""
from copy import deepcopy


def source(eid, words, domain, claim_type, *, actor='UNKNOWN', task='UNKNOWN', phase='UNRESOLVED',
           modality='ASSERTED', speaker='user', scope='PALETTE_MODEL', **facets):
    return {'id':eid,'text':words,'speaker':speaker,'annotation':{
        'domain':domain,'scope':scope,'claim_type':claim_type,'modality':modality,
        'temporal_state':phase,'actor':actor,'task':task,'polarity':'AFFIRMED',
        'quotation':'NOT_QUOTED','confidence':'EXPLICIT',**facets}}


def palette():
    return {'scope':'PALETTE_MODEL','candidates':[{'id':'red','domain':'PIGMENT'},{'id':'green','domain':'PIGMENT'}],
        'sources':[
            source('sample','检验报告称本次样片不含红色素。','PIGMENT','OBSERVATION'),
            source('rule','本模型中，不含红色素与红色素样片假说不相容。','PIGMENT','RELATION'),
            source('retain','在这次模型演练中，绿色素样片假说仍然保留。','PIGMENT','RELATION'),
            source('universe','这次玩具模型的候选全集恰为红色素和绿色素样片。','PIGMENT','UNIVERSE')],
        'exclusions':[{'candidate_id':'red','evidence_id':'sample','exclusion_rule':'INCOMPATIBLE_WITH_HYPOTHESIS','rule_evidence_id':'rule'}],
        'bridges':[],'assessments':[],
        'universe':{'kind':'UNKNOWN','candidate_ids':[],'evidence_ids':[],'unresolved_remainder':None}}


def cross_palette():
    d=palette()
    d['sources'][0]=source('sample','本次光谱记录没有红色分量。','SPECTRAL_CHANNEL','OBSERVATION')
    d['sources'][1]=source('rule','本模型内必产生红色分量的样片假说，与缺少该分量不相容。','PIGMENT','RELATION')
    return d


def finite(d):
    d['universe']={'kind':'EXPLICIT_FINITE_SOURCE','candidate_ids':['red','green'],
                   'evidence_ids':['universe'],'unresolved_remainder':[]}
    d['assessments']=[{'candidate_id':'green','status':'RETAINED','evidence_ids':['retain']}]
    return d


def bridge(d):
    d['sources'].append(source('bridge_basis',
        '在这个已校准白光模型内，红色素样片一定产生红色分量，因此缺少分量可以反向约束该样片假说。',
        'PIGMENT','BRIDGE'))
    d['bridges']=[{'id':'spectral_pigment','from_domain':'SPECTRAL_CHANNEL','to_domain':'PIGMENT',
        'scope':'PALETTE_MODEL','candidate_ids':['red'],'evidence_id':'bridge_basis','rule':'MODEL_NECESSARY_SIGNAL'}]
    d['exclusions'][0]['bridge_id']='spectral_pigment'
    return d


CANDIDATE_FIXTURES=[]
def case(name, data, state, excluded, unhandled, remainder=None):
    CANDIDATE_FIXTURES.append({'id':name,'kind':'CANDIDATE_CLOSURE','data':data,
        'expected':{'closure_state':state,'excluded_candidates':excluded,'unhandled_candidates':unhandled,
                    'conditional_finite_remainder':remainder}})

case('same_domain_valid_exclusion',palette(),'PARTIALLY_CONSTRAINED',['red'],['green'])
case('cross_domain_without_bridge',cross_palette(),'OPEN',[],['red','green'])
case('cross_domain_explicit_bridge',bridge(cross_palette()),'PARTIALLY_CONSTRAINED',['red'],['green'])
d=palette();d['candidates'].append({'id':'blue','domain':'PIGMENT'})
case('partial_elimination',d,'PARTIALLY_CONSTRAINED',['red'],['green','blue'])
case('finite_universe_complete_closure',finite(palette()),'LOCALLY_CLOSED',['red'],[],['green'])
d=finite(palette());d['universe']['unresolved_remainder']=['另有尚未验证的材料边界']
case('unknown_remainder',d,'PARTIALLY_CONSTRAINED',['red'],[])
d=finite(palette());d['scope']='UNKNOWN'
case('ambiguous_candidate_scope',d,'OPEN',[],['red','green'])
d=finite(palette());d['scope']='LOCAL_TRAINING_ONLY'
for s in d['sources']:s['annotation']['scope']='LOCAL_TRAINING_ONLY'
case('local_closure_not_global',d,'LOCALLY_CLOSED',['red'],[],['green'])
d=palette();d['sources'][0]['text']='假设本次样片确实不含红色素。';d['sources'][0]['annotation']['modality']='CONDITIONAL'
case('conditional_exclusion',d,'PARTIALLY_CONSTRAINED',['red'],['green'])
d=finite(palette());d['sources'].append(source('opposing','另一份检验报告称仍有红色素。','PIGMENT','OBSERVATION'))
d['exclusions'][0]['contradicting_evidence_ids']=['opposing']
case('contradictory_evidence',d,'PARTIALLY_CONSTRAINED',[],['red'])
d=finite(palette());d['assessments']=[]
d['sources'] += [source('second','报告还称不含绿色素。','PIGMENT','OBSERVATION'),
                source('second_rule','在此模型内不含绿色素与绿色素样片假说不相容。','PIGMENT','RELATION')]
d['exclusions'].append({'candidate_id':'green','evidence_id':'second','exclusion_rule':'INCOMPATIBLE_WITH_HYPOTHESIS','rule_evidence_id':'second_rule'})
case('explicitly_exhausted_local_set',d,'EXPLICITLY_EXHAUSTED',['green','red'],[],[])
d=finite(palette());d['inquiry_status']='REOPENED'
case('reopened_scope',d,'OPEN',[],['red','green'])


ATTRIBUTION_FIXTURES=[]
def attribution(name, words, source_kind, phase, expected, *, claim='OWNERSHIP', requested='EXPLICITLY_ASSIGNED',
                source_actor='林', source_task='编制花卉目录', actor='林', task='编制花卉目录', speaker='user',
                extra_sources=(), **facets):
    ATTRIBUTION_FIXTURES.append({'id':name,'kind':'RESPONSIBILITY','data':{
        'actor':actor,'task':task,'scope':'GARDEN_WORK','claim_type':claim,'requested_state':requested,
        'sources':[source('task_source',words,'TASK',''+source_kind,actor=source_actor,task=source_task,
                    phase=phase,speaker=speaker,scope='GARDEN_WORK',**facets),*deepcopy(extra_sources)]},
        'expected':{'state':expected,'requested_state_supported':expected==requested and expected in {'EXPLICITLY_ASSIGNED','EXPLICITLY_COMPLETED'}}})

attribution('explicit_assignment','目录的编制工作明确交给林负责。','ASSIGNMENT','ASSIGNED','EXPLICITLY_ASSIGNED')
attribution('explicit_completion','林已经完成花卉目录的编制，这是现场负责人的报告。','COMPLETION','COMPLETED','EXPLICITLY_COMPLETED',claim='EXECUTION',requested='EXPLICITLY_COMPLETED')
attribution('future_plan','林计划下周编制花卉目录。','PLAN','PLANNED','PLANNED',claim='EXECUTION',requested='EXPLICITLY_COMPLETED')
attribution('suggestion','我建议可以让林编制花卉目录。','SUGGESTION','UNRESOLVED','PROPOSED')
attribution('adjacent_task_inference','目录编制交给林负责。','ASSIGNMENT','ASSIGNED','INFERRED',task='校对花卉目录')
attribution('responsibility_unknown','暂时不知道谁来编制目录。','UNKNOWN','UNRESOLVED','UNKNOWN',source_actor='UNKNOWN',confidence='UNKNOWN')
attribution('multiple_actors','目录编制交给林负责；郁另行负责制作展牌。','ASSIGNMENT','ASSIGNED','EXPLICITLY_ASSIGNED',extra_sources=[
    source('other_actor','展牌制作交给郁负责。','TASK','ASSIGNMENT',actor='郁',task='制作展牌',phase='ASSIGNED',scope='GARDEN_WORK')])
attribution('quoted_assignment','管理员说：“目录编制交给林负责。”','ASSIGNMENT','ASSIGNED','EXPLICITLY_ASSIGNED',quotation='QUOTED',reported_speaker='管理员',reported_addressee='林')
attribution('speaker_ambiguity','纸条写着：“你负责目录。”但不知道是谁对谁说的。','ASSIGNMENT','ASSIGNED','UNKNOWN',quotation='QUOTED',reported_speaker='UNKNOWN',reported_addressee='UNKNOWN')
attribution('task_relation_without_ownership','林正在讨论花卉目录与展牌的关联。','RELATION','UNRESOLVED','UNKNOWN')
attribution('execution_without_ownership','林报告目录已经编制完成。','COMPLETION','COMPLETED','UNKNOWN')
attribution('ownership_without_completion','林被指派编制目录，尚无执行报告。','ASSIGNMENT','ASSIGNED','UNKNOWN',claim='EXECUTION',requested='EXPLICITLY_COMPLETED')
attribution('assistant_repetition_not_user_evidence','林已经完成目录编制。','COMPLETION','COMPLETED','INFERRED',claim='EXECUTION',requested='EXPLICITLY_COMPLETED',speaker='assistant')
attribution('negated_completion','林并没有完成花卉目录。','COMPLETION','COMPLETED','UNKNOWN',claim='EXECUTION',requested='EXPLICITLY_COMPLETED',polarity='NEGATED')

FIXTURES=CANDIDATE_FIXTURES+ATTRIBUTION_FIXTURES


def fixture(name):
    return deepcopy(next(f for f in FIXTURES if f['id']==name))


def bind_fixture(f):
    """Create occurrence-bound original sources without a semantic parser."""
    from dataclasses import asdict
    from claim_evidence import utterance
    d=deepcopy(f['data']);units=[];evidence=[]
    for s in d.pop('sources'):
        u=utterance(entity_id='AUTHOR_ONLY',mode='PRODUCT_RUNTIME',turn_id=f['id']+'/'+s['id'],speaker=s['speaker'],text=s['text'])
        units.append(asdict(u))
        evidence.append(dict(s['annotation'],id=s['id'],source_id=u.proposition_id,span=[0,len(s['text'])],quote=s['text']))
    d['evidence']=evidence
    return d,units
