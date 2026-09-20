"""Closed, compositional Chinese realization; provider prose is never a template."""
from dataclasses import dataclass, asdict, replace
import re
from semantic_types import *
from semantic_validator import Validation, validate

RENDERER_VERSION='CONTROLLED_ZH_1'

@dataclass(frozen=True)
class RenderedOutput:
    text: str
    clauses: tuple[dict,...]
    validation_digest: str
    renderer_version: str = RENDERER_VERSION

def _label(state,key):
    label=state.table('entities','entity_id')[key].label
    # Data stays within a quoted noun phrase, including punctuation or instructions.
    return '「'+label.replace('「','\\u300c').replace('」','\\u300d')+'」'

def _body(claim,state,*,introduce=True):
    p=claim.proposition; a=_label(state,p.subject); b=_label(state,p.object)
    if claim.claim_type=='EXCLUSION': a=_label(state,claim.candidate_id)
    forms={
        'is':f'{a}是{b}', 'value':f'{a}的值为{b}', 'observed':f'已观察到{a}的{b}',
        'has_state':f'{a}处于{b}状态', 'has_trait':f'{a}有{b}这一倾向',
        'processed':f'{a}的{b}已完成', 'checked':f'已检查{a}的{b}',
        'candidate':f'{a}是{b}范围内的候选', 'listed':f'{a}列在{b}中',
        'valid':f'{a}的{b}已通过检验', 'paired':f'{a}与{b}配对',
        'causes':f'{a}会导致{b}', 'explains':f'{a}可以解释{b}',
        'assigned':f'{b}由{a}负责', 'completed':f'{a}已完成{b}',
        'planned':f'{a}的计划是{b}', 'proposed':f'有人提议由{a}负责{b}',
        'not_started':f'{a}尚未开始{b}', 'coincident':f'同一时间出现了{a}和{b}',
        'excluded':f'{a}已在本次检查范围内排除',
        'unassessed':f'{a}的{b}仍待核查', 'said':f'{a}提到了{b}',
    }
    before={Domain.RECORD:f'{a}的排列位置在{b}之前',
            Domain.TIMESTAMP:f'{a}的时间值小于{b}的时间值',
            Domain.SAMPLING:f'{a}的采样先于{b}',
            Domain.CAUSAL:f'模型中的{a}先于{b}'}
    if p.predicate=='before':
        require(p.relation_domain in before,'UNSUPPORTED_RELATION_REALIZATION')
        text=before[p.relation_domain]
    else:
        text=forms[p.predicate]
    if not p.polarity:
        text=f'“{text}”这一判断不成立'
    if claim.strength.epistemic==Epistemic.UNKNOWN:
        text=f'目前还不能判断是否{text}'
    elif claim.strength.epistemic==Epistemic.POSSIBLE:
        text=f'{text}，目前只是一种待验证的可能'
    elif claim.strength.epistemic==Epistemic.SUPPORTED and introduce:
        text=f'现有信息支持：{text}'
    if claim.modality==Modality.REPORTED:
        text=f'按{_label(state,claim.speaker) if claim.speaker in state.table("entities","entity_id") else "来源"}的陈述，{text}'
    elif claim.modality==Modality.HYPOTHETICAL:
        text=f'作为一个假设，{text}'
    if claim.unresolved_dependencies:
        conditions='且'.join(_label(state,c) for c in claim.unresolved_dependencies)
        text=f'如果{conditions}，{text}；这些条件仍待确认'
    return text+'。'

def render(validation,state):
    require(type(validation) is Validation,'VALIDATED_STATE_REQUIRED')
    validation.check(state)
    clauses=[]; previous_profile=None; previous_scope=None
    for d in validation.decisions:
        if d.certificate is None:
            # A blocked important proposal is explicitly accounted for, not deleted.
            if not any(c['kind']=='UNSUPPORTED' for c in clauses):
                clauses.append({'kind':'UNSUPPORTED','claim_id':d.claim_id,
                    'text':'现有信息还不足以支持这个判断。','certificate_ref':None})
            continue
        cert=d.certificate; claim=cert.claim
        require(cert.authorized_strength.permits(claim.strength),'RENDERED_STRENGTH_EXCEEDS_AUTHORIZATION')
        profile=(claim.modality,claim.strength,cert.assertion_bases)
        if claim.claim_type=='LIMITATION':
            if cert.rule=='CONFLICT_REQUIRES_RECONCILIATION':
                text='相关记录存在冲突，还需要核对后才能确定。'
            else:
                body=_body(replace(claim,strength=Strength(Epistemic.CERTAIN)),state,introduce=False).rstrip('。')
                text=f'仅凭当前信息，还不能确认{body}。'
        elif d.closure:
            u=state.table('universes','universe_id')[d.closure.universe_id]
            boundary=_label(state,u.label_id)
            if d.closure.remaining_members:
                names='、'.join(_label(state,c) for c in d.closure.remaining_members)
                text=f'在{boundary}限定的完整候选范围内，剩下的是{names}。'
            else:
                require(claim.strength.coverage==Coverage.EXHAUSTIVE,'EXHAUSTIVE_RENDER_REQUIRES_EXHAUSTIVE_PLAN')
                text=f'在{boundary}限定的完整候选范围内，全部候选都已排除。'
        else:
            text=_body(claim,state,introduce=profile!=previous_profile)
            if 'FORMAL_PREMISE' in cert.assertion_bases and profile!=previous_profile:
                text='按给定前提，'+text
        if not d.closure and previous_scope!=claim.scope:
            text=f'在{_label(state,dict(state.scope_names)[claim.scope.path])}范围内，'+text
        clauses.append({'kind':'AUTHORIZED_CLAIM','claim_id':claim.claim_id,'text':text,
             'certificate_ref':cert.certificate_id,'rendered_strength':asdict(claim.strength)})
        previous_profile=profile
        previous_scope=claim.scope
    require(clauses,'EMPTY_RENDER')
    return RenderedOutput(''.join(c['text'] for c in clauses),tuple(clauses),digest(validation.record()))

def check_visible(validation,state,text):
    """Exact authorized realization, not a keyword classifier or equivalence guess."""
    expected=render(validation,state)
    return {'matches':type(text) is str and text==expected.text,
            'action':'ALLOW' if text==expected.text else 'REBUILD_FROM_VALIDATED_STATE',
            'rendered':expected}
