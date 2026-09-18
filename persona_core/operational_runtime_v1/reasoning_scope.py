"""Finite reasoning descriptions, without semantic parsing or admission authority.

Surface marks authenticate only lexical positions. A negated/quoted marker is
still a marker, never a statement of its enclosing clause's truth or meaning.
Candidate reasoning is author/parser supplied, structurally checked, untrusted.
"""
from __future__ import annotations

from copy import deepcopy
import re

VERSION = 'REASONING_SCOPE_1'
UNKNOWN = 'UNRESOLVED'
RELATIONS = {
    'FIELD_COMPARISON': {'LESS_THAN','EQUAL','GREATER_THAN',UNKNOWN},
    'SAMPLING_ORDER': {'BEFORE','AFTER','SIMULTANEOUS',UNKNOWN},
    'RECORD_ORDER': {'BEFORE','AFTER','SIMULTANEOUS',UNKNOWN},
    'CAUSAL_ORDER': {'PRECEDES','FOLLOWS',UNKNOWN},
    'PAIRING_IDENTITY': {'SAME_PAIR','DIFFERENT_PAIR',UNKNOWN},
}
KINDS = {'SUPPLIED_PREMISE','REPORTED_OBSERVATION','INFERRED_CONSEQUENCE','UNRESOLVED_POSSIBILITY',UNKNOWN}
INVARIANTS = {
    'premise_acceptance_verifies_world': False,
    'candidate_set_completeness_default': UNKNOWN,
    'elimination_establishes_exhaustiveness': False,
    'independent_relations': list(RELATIONS),
    'cross_relation_inference': 'REQUIRES_EXPLICIT_BRIDGE_PREMISES',
}

# Broad discourse cues, not benchmark identifiers or topic-specific answers.
# These deliberately do not extract subjects, candidates, scope or entailment.
_CUES = (
    ('PREMISE_CUE',r'假设|如果|倘若|假如|前提|\b(?:assume|assuming|suppose|if|provided that)\b'),
    ('CONSEQUENCE_CUE',r'那么|则可|所以|因此|推出|\b(?:then|therefore|implies|consequently)\b'),
    ('OBSERVATION_REPORT_CUE',r'观测报告|实测|观察到|测得|\b(?:observed|measured|observation report)\b'),
    ('OPEN_CANDIDATE_CUE',r'目前想到|可能包括|候选之一|例如|\b(?:possible causes include|for example|among others)\b'),
    ('CLOSED_CANDIDATE_CLAIM_CUE',r'候选全集|所有可能|仅有|只能|\b(?:exhaustive|all possibilities|the only possibilities)\b'),
    ('SAMPLING_ORDER_CUE',r'(?:采样|取样|读取)(?:的)?(?:先后|顺序)|\b(?:sampling|sample|read) order\b'),
    ('RECORD_ORDER_CUE',r'(?:记录|写入|日志)(?:的)?(?:先后|顺序)|\b(?:logging|record|write) order\b'),
    ('CAUSAL_ORDER_CUE',r'因果(?:先后|顺序)|\bcausal order\b'),
    ('PAIRING_CUE',r'配对|关联正确|\b(?:pairing|paired|matching identity)\b'),
)
_PATTERNS = [(name,re.compile(pattern,re.I)) for name,pattern in _CUES]
_QUOTES = {'“':'”','‘':'’','「':'」','『':'』','"':'"'}

def _require(ok,message):
    if not ok: raise ValueError(message)

def _texts(value, label, *, limit=16):
    _require(type(value) is list and len(value)<=limit, 'Invalid '+label)
    _require(all(type(x) is str and 0<len(x)<=1000 for x in value), 'Invalid '+label+' text')
    return list(value)

def surface_view(text, speaker):
    """Only lexical offsets and delimiter scopes; no inferred facts or bindings.

    Bounded metadata records incomplete coverage explicitly. The full evidence
    text remains intact in claim_evidence, so omitted marks never imply absence.
    ASCII apostrophes are not treated as quotation delimiters (contractions).
    """
    _require(type(text) is str and speaker in {'user','assistant'},'Invalid surface source')
    marks=[]
    for kind,pattern in _PATTERNS:
        for m in pattern.finditer(text):
            marks.append({'kind':kind,'span':[m.start(),m.end()],'quote':m.group()})
    marks.sort(key=lambda m:(m['span'],m['kind']))
    stack=[];quotes=[];quote_count=0
    for i,char in enumerate(text):
        # Honor escaping only for ASCII quotation marks. Chinese punctuation
        # remains literal even if a preceding backslash is ordinary text.
        if char=='"':
            before=i
            while before and text[before-1]=='\\': before-=1
            if (i-before)%2: continue
        if stack and char==stack[-1]['close']:
            entry=stack.pop()
            if entry['row'] is not None:
                entry['row']['span'][1]=i;entry['row']['closed']=True
        elif char in _QUOTES:
            row={'span':[i+1,len(text)],'closed':False,'speaker':UNKNOWN,'addressee':UNKNOWN}
            parent=stack[-1]['start'] if stack else None
            if parent is not None: row['parent_quote_start']=parent
            quote_count+=1
            keep=row if len(quotes)<24 else None
            if keep is not None: quotes.append(keep)
            stack.append({'close':_QUOTES[char],'start':i,'row':keep})
    return {'version':VERSION,'origin':'USER_SUPPLIED' if speaker=='user' else 'ASSISTANT_GENERATED',
        'world_verification':'NOT_ESTABLISHED_BY_WORDS','claim_kind':UNKNOWN,
        'candidate_set_completeness':UNKNOWN,'relations':[],
        'marker_semantics':'LEXICAL_OCCURRENCE_ONLY_READ_ENCLOSING_TEXT',
        'markers':marks[:24],'quotes':quotes,
        'surface_coverage':'BOUNDED' if len(marks)>24 or quote_count>24 else 'MATCHED_CUES_ONLY_NOT_ALL_SEMANTICS'}

def validate_reasoning(value):
    """Retain one proposed reasoning scope without validating its correctness."""
    allowed={'claim_kind','premises','inference_strength','candidate_set','relations'}
    _require(type(value) is dict and set(value)<=allowed,'Unsupported reasoning fields')
    kind=value.get('claim_kind',UNKNOWN)
    strength=value.get('inference_strength',UNKNOWN)
    _require(type(kind) is str and kind in KINDS,'Invalid claim kind')
    _require(type(strength) is str and strength in {UNKNOWN,'PLAUSIBLE','CONDITIONAL_ON_PREMISES'},'Invalid inference strength')
    premises=_texts(value.get('premises',[]),'premises')
    _require(strength!='CONDITIONAL_ON_PREMISES' or bool(premises),'Conditional conclusion missing premises')
    candidates=value.get('candidate_set',{'members':[],'completeness':UNKNOWN,'closure_basis':[]})
    _require(type(candidates) is dict and set(candidates)=={'members','completeness','closure_basis'},'Invalid candidate set fields')
    members=_texts(candidates['members'],'candidate members')
    closure=_texts(candidates['closure_basis'],'closure basis')
    complete=candidates['completeness']
    _require(type(complete) is str and complete in {UNKNOWN,'OPEN','EXHAUSTIVE_WITHIN_PREMISES'},'Invalid candidate completeness')
    _require(complete!='EXHAUSTIVE_WITHIN_PREMISES' or
             (bool(members) and bool(closure) and all(p in premises for p in closure)),
             'Exhaustive candidate scope missing explicit universe premise')
    relations=value.get('relations',[])
    _require(type(relations) is list and len(relations)<=12,'Invalid relations')
    for r in relations:
        _require(type(r) is dict and set(r)=={'kind','left','right','relation','basis','confidence'},'Invalid relation fields')
        _require(type(r['kind']) is str and r['kind'] in RELATIONS,'Invalid relation domain')
        _require(type(r['relation']) is str and r['relation'] in RELATIONS[r['kind']],'Relation outside declared domain')
        _texts([r['left'],r['right']],'relation endpoints')
        basis=_texts(r['basis'],'relation basis')
        _require(type(r['confidence']) is str and r['confidence'] in {UNKNOWN,'EXPLICIT_REPORT','INFERRED'},'Invalid relation confidence')
        _require(r['relation']==UNKNOWN or bool(basis),'Stated relation missing basis')
    return {'claim_kind':kind,'premises':premises,'inference_strength':strength,
        'candidate_set':{'members':members,'completeness':complete,'closure_basis':closure},
        'relations':deepcopy(relations),'premises_verified':False,'semantic_entailment_verified':False}

def sparse_surface(scope):
    """Do not duplicate raw text; positions refer to the enclosing evidence unit."""
    result={}
    if scope['markers']: result['markers']=[[m['kind'],*m['span']] for m in scope['markers']]
    if scope['quotes']: result['quotes']=deepcopy(scope['quotes'])
    if scope['surface_coverage']=='BOUNDED': result['surface_coverage']='BOUNDED_NOT_EXHAUSTIVE'
    return result
