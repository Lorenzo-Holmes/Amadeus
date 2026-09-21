"""Bounded semantic language. Provider values describe proposals, never authority."""
from __future__ import annotations
from dataclasses import dataclass, asdict, fields
from enum import Enum, IntEnum
import hashlib
import json
import re

VERSION = 'TRUSTED_SEMANTIC_ACCEPTANCE_1'
MAX_CLAIMS = 64

class SemanticError(ValueError):
    pass

def require(ok, code):
    if not ok:
        raise SemanticError(code)

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()

class Domain(str, Enum):
    RECORD = 'record_order'
    TIMESTAMP = 'timestamp_value_relation'
    SAMPLING = 'sampling_order'
    CAUSAL = 'causal_order'
    PAIRING = 'request_response_pairing'
    TRANSFORM = 'field_transform'
    MEASUREMENT = 'measurement_validity'
    EXPLANATION = 'explanatory_premise'
    RESPONSIBILITY = 'responsibility'
    EXECUTION = 'execution'
    SPEAKER = 'speaker_relation'

class Epistemic(IntEnum):
    UNKNOWN = 0
    POSSIBLE = 1
    SUPPORTED = 2
    CERTAIN = 3

class Disposition(IntEnum):
    UNASSESSED = 0
    LOCALLY_CONSTRAINED = 1
    EXCLUDED = 2

class Coverage(IntEnum):
    OPEN = 0
    FINITE = 1
    EXHAUSTIVE = 2

@dataclass(frozen=True)
class Strength:
    epistemic: Epistemic = Epistemic.SUPPORTED
    disposition: Disposition = Disposition.UNASSESSED
    coverage: Coverage = Coverage.OPEN

    def __post_init__(self):
        require(type(self.epistemic) is Epistemic and type(self.disposition) is Disposition
                and type(self.coverage) is Coverage, 'STRENGTH_TYPE')

    def permits(self, requested):
        return all(a >= b for a, b in zip((self.epistemic, self.disposition, self.coverage),
                                         (requested.epistemic, requested.disposition, requested.coverage)))

class Modality(str, Enum):
    ASSERTED = 'ASSERTED'
    CONDITIONAL = 'CONDITIONAL'
    REPORTED = 'REPORTED'
    HYPOTHETICAL = 'HYPOTHETICAL'

class TemporalState(str, Enum):
    UNSPECIFIED = 'UNSPECIFIED'
    PLANNED = 'PLANNED'
    ASSIGNED = 'ASSIGNED'
    COMPLETED = 'COMPLETED'

class Role(str, Enum):
    VALIDATION_PRECONDITION = 'VALIDATION_PRECONDITION'
    MEASUREMENT_ASSUMPTION = 'MEASUREMENT_ASSUMPTION'
    EXPLANATORY_PREMISE = 'EXPLANATORY_PREMISE'
    OBSERVED_EVIDENCE = 'OBSERVED_EVIDENCE'
    EXCLUSION_EVIDENCE = 'EXCLUSION_EVIDENCE'

class Origin(str, Enum):
    PROGRAM = 'PROGRAM_TYPED_FACT'
    SYSTEM = 'SCHEMA_SYSTEM_STATE'
    USER = 'PARSED_USER_STATEMENT'
    VERIFIED = 'VERIFIED_SOURCE_MAPPING'
    DERIVED = 'HOST_DERIVATION'

def identifier(value):
    require(type(value) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value) is not None, 'INVALID_ID')

@dataclass(frozen=True)
class Scope:
    path: tuple[str, ...]

    def __post_init__(self):
        require(type(self.path) is tuple and 0 < len(self.path) <= 8, 'SCOPE_TYPE')
        for p in self.path:
            identifier(p)

    def contains(self, other):
        return other.path[:len(self.path)] == self.path

@dataclass(frozen=True)
class Entity:
    entity_id: str
    label: str
    kind: str = 'OBJECT'

    def __post_init__(self):
        identifier(self.entity_id)
        require(type(self.label) is str and 0 < len(self.label) <= 80 and self.label.isprintable(), 'ENTITY_LABEL')
        require(self.kind in {'OBJECT','ACTOR','TASK','PROPERTY','CONDITION','CANDIDATE','SCOPE'}, 'ENTITY_KIND')

Actor = Entity
Task = Entity

@dataclass(frozen=True)
class Proposition:
    predicate: str
    subject: str
    object: str
    relation_domain: Domain
    polarity: bool = True

    def __post_init__(self):
        allowed = {'is','has_state','has_trait','processed','checked','candidate','listed','value','coincident','not_started','before','paired','causes','valid','explains','assigned','completed',
                   'planned','proposed','excluded','observed','unassessed','said'}
        require(self.predicate in allowed and type(self.relation_domain) is Domain and type(self.polarity) is bool, 'PREDICATE_TYPE')
        identifier(self.subject)
        identifier(self.object)
        fixed = {'assigned':Domain.RESPONSIBILITY, 'planned':Domain.EXECUTION,
                 'completed':Domain.EXECUTION, 'proposed':Domain.RESPONSIBILITY,
                 'said':Domain.SPEAKER, 'valid':Domain.MEASUREMENT,
                 'coincident':Domain.TIMESTAMP, 'not_started':Domain.EXECUTION,
                 'causes':Domain.CAUSAL, 'explains':Domain.EXPLANATION, 'paired':Domain.PAIRING}
        require(self.predicate not in fixed or self.relation_domain == fixed[self.predicate], 'PREDICATE_DOMAIN')

Relation = Proposition

@dataclass(frozen=True)
class Source:
    source_id: str
    origin: Origin
    speaker: str
    version: str
    content_sha256: str
    basis: str = 'HOST_OBSERVATION'

    def __post_init__(self):
        identifier(self.source_id)
        identifier(self.speaker)
        require(type(self.origin) is Origin and type(self.version) is str and bool(self.version), 'SOURCE_TYPE')
        require(self.basis in {'HOST_OBSERVATION','FORMAL_PREMISE','SOURCE_REPORT'}, 'SOURCE_BASIS')
        require(re.fullmatch('[0-9a-f]{64}', self.content_sha256) is not None, 'SOURCE_DIGEST')
        require(self.origin != Origin.USER or self.basis == 'SOURCE_REPORT', 'USER_REPORT_NOT_WORLD_FACT')

@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    proposition: Proposition
    source_id: str
    scope: Scope
    strength: Strength = Strength()
    modality: Modality = Modality.ASSERTED
    temporal_state: TemporalState = TemporalState.UNSPECIFIED
    role: Role = Role.OBSERVED_EVIDENCE
    conditions: tuple[str, ...] = ()
    attribution: str = 'UNKNOWN'

@dataclass(frozen=True)
class Rule:
    rule_id: str
    premises: tuple[Proposition, ...]
    conclusion: Proposition
    source_id: str
    scope: Scope
    kind: str = 'IMPLICATION'
    strength: Strength = Strength()
    bridge: bool = False
    conditions: tuple[str, ...] = ()

@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    proposition: Proposition
    scope: Scope

@dataclass(frozen=True)
class Universe:
    universe_id: str
    scope: Scope
    label_id: str
    members: tuple[str, ...]
    source_id: str
    completeness_basis: str
    generation_boundary: str
    unresolved_remainder: tuple[str, ...] | None

@dataclass(frozen=True)
class Claim:
    claim_id: str
    claim_type: str
    proposition: Proposition
    scope: Scope
    modality: Modality
    strength: Strength
    source_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    bridge_refs: tuple[str, ...] = ()
    rule_ref: str | None = None
    unresolved_dependencies: tuple[str, ...] = ()
    temporal_state: TemporalState = TemporalState.UNSPECIFIED
    speaker: str = 'host'
    attribution: str = 'UNKNOWN'
    candidate_id: str | None = None
    universe_id: str | None = None
    member_claims: tuple[str, ...] = ()

    def __post_init__(self):
        identifier(self.claim_id)
        identifier(self.speaker)
        for value in (self.rule_ref,self.candidate_id,self.universe_id):
            if value is not None: identifier(value)
        require(self.claim_type in {'ASSERTION','EXCLUSION','CLOSURE','RESPONSIBILITY','LIMITATION'}, 'CLAIM_TYPE')
        require(type(self.proposition) is Proposition and type(self.scope) is Scope
                and type(self.modality) is Modality and type(self.strength) is Strength
                and type(self.temporal_state) is TemporalState, 'CLAIM_SCHEMA')
        for name in ('source_refs','evidence_refs','bridge_refs','unresolved_dependencies','member_claims'):
            values = getattr(self, name)
            require(type(values) is tuple and len(values) <= MAX_CLAIMS and len(set(values)) == len(values), 'REFERENCE_SCHEMA')
            for v in values:
                identifier(v)
        require(self.attribution in {'EXPLICITLY_ASSIGNED','EXPLICITLY_COMPLETED','PLANNED','PROPOSED','INFERRED','UNKNOWN'}, 'ATTRIBUTION_TYPE')

@dataclass(frozen=True)
class SemanticPlan:
    claims: tuple[Claim, ...]
    context_digest: str
    kind: str = 'PROPOSED_PLAN'
    version: str = VERSION

    def __post_init__(self):
        require(self.kind == 'PROPOSED_PLAN' and self.version == VERSION, 'PROPOSAL_ONLY')
        require(type(self.claims) is tuple and 0 < len(self.claims) <= MAX_CLAIMS
                and all(type(c) is Claim for c in self.claims), 'PLAN_SIZE_OR_TYPE')
        require(len({c.claim_id for c in self.claims}) == len(self.claims), 'DUPLICATE_CLAIM')
        require(type(self.context_digest) is str and re.fullmatch('[0-9a-f]{64}', self.context_digest), 'CONTEXT_DIGEST')

def _exact(cls, value):
    require(type(value) is dict and set(value) == {f.name for f in fields(cls)}, 'SCHEMA_FIELDS')
    return dict(value)

def parse_plan(raw: str) -> SemanticPlan:
    """Strict offline/provider capability boundary, including duplicate JSON keys."""
    require(type(raw) is str and len(raw.encode('utf-8')) <= 65536, 'ENVELOPE_SIZE')
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'DUPLICATE_JSON_KEY')
            result[k] = v
        return result
    try:
        obj = _exact(SemanticPlan, json.loads(raw, object_pairs_hook=pairs,
                    parse_constant=lambda _: (_ for _ in ()).throw(SemanticError('NONFINITE_JSON'))))
        require(type(obj['claims']) is list and 0 < len(obj['claims']) <= MAX_CLAIMS, 'PLAN_SIZE_OR_TYPE')
        claims=[]
        for value in obj['claims']:
            c=_exact(Claim, value)
            p=_exact(Proposition,c['proposition']); p['relation_domain']=Domain(p['relation_domain'])
            c['proposition']=Proposition(**p)
            s=_exact(Scope,c['scope']); require(type(s['path']) is list,'SCOPE_TYPE')
            c['scope']=Scope(tuple(s['path']))
            s=_exact(Strength,c['strength'])
            require(all(type(v) is int for v in s.values()),'STRENGTH_TYPE')
            c['strength']=Strength(Epistemic(s['epistemic']),Disposition(s['disposition']),Coverage(s['coverage']))
            c['modality']=Modality(c['modality']); c['temporal_state']=TemporalState(c['temporal_state'])
            for key in ('source_refs','evidence_refs','bridge_refs','unresolved_dependencies','member_claims'):
                require(type(c[key]) is list,'REFERENCE_SCHEMA'); c[key]=tuple(c[key])
            claims.append(Claim(**c))
        obj['claims']=tuple(claims)
        return SemanticPlan(**obj)
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        if isinstance(exc,SemanticError): raise
        raise SemanticError('INVALID_PROPOSED_PLAN') from None

def serialize_plan(plan):
    return canonical(asdict(plan))

def provider_capability():
    return {'version':VERSION,'transport_hook_installed':False,'plan_kind':'PROPOSED_PLAN',
            'parser':'STRICT_JSON','authority':'NONE','remote_required':False,
            'top_level_fields':[f.name for f in fields(SemanticPlan)]}
