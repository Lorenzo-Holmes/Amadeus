"""Host-owned admission. Never deserialize provider data into this inventory.

Program/system/mapped premises are explicit host trust roots, not proofs that a
real-world report is true. User text has only the small grammar below; all other
text is retained as UNPARSED. No model-provided semantic annotations are used.
"""
from dataclasses import dataclass, asdict
import re
from semantic_types import *

_HOST_SEAL = object()

@dataclass(frozen=True)
class TrustedState:
    entities: tuple[Entity, ...]
    sources: tuple[Source, ...]
    evidence: tuple[Evidence, ...]
    rules: tuple[Rule, ...]
    candidates: tuple[Candidate, ...]
    universes: tuple[Universe, ...]
    scope_names: tuple[tuple[tuple[str,...],str], ...]
    unparsed_sha256: tuple[str, ...]
    identity: tuple[str, str, str, str]
    _seal: object

    def public_state(self):
        return {k: v for k,v in asdict(self).items() if k != '_seal'}

    @property
    def context_digest(self):
        return digest(self.public_state())

    def table(self, name, key):
        return {getattr(v,key):v for v in getattr(self,name)}

    def check(self):
        require(self._seal is _HOST_SEAL,'HOST_ADMISSION_REQUIRED')

class TrustedAdmission:
    """Trusted host configuration API, never exposed to a provider tool call."""
    def __init__(self, *, session_id, entity_id, turn_id, raw_user_text):
        self.identity=(session_id,entity_id,turn_id,digest(raw_user_text))
        self.entities={}; self.sources={}; self.evidence={}; self.rules={}
        self.candidates={}; self.universes={}; self.unparsed=[]; self.scopes={}

    def _add(self, table, key, value, cls):
        require(type(value) is cls,'HOST_TYPED_OBJECT_REQUIRED')
        identifier(key)
        require(key not in table and len(table)<256,'DUPLICATE_OR_TOO_MANY_HOST_NODES')
        table[key]=value
        return value

    def entity(self, entity):
        return self._add(self.entities,entity.entity_id,entity,Entity)

    def source(self, source):
        return self._add(self.sources,source.source_id,source,Source)

    def scope(self,scope,label_id):
        require(type(scope) is Scope and label_id in self.entities and self.entities[label_id].kind=='SCOPE','HOST_SCOPE_LABEL_REQUIRED')
        require(scope.path not in self.scopes,'DUPLICATE_SCOPE')
        self.scopes[scope.path]=label_id

    def _proposition(self,p):
        require(type(p) is Proposition and p.subject in self.entities and p.object in self.entities,'UNBOUND_PROPOSITION')

    def _conditions(self,conditions):
        require(type(conditions) is tuple and len(conditions)<=32 and len(set(conditions))==len(conditions),'CONDITION_SCHEMA')
        require(all(c in self.entities and self.entities[c].kind=='CONDITION' for c in conditions),'UNKNOWN_CONDITION')

    def fact(self, fact):
        require(type(fact) is Evidence and type(fact.scope) is Scope and type(fact.strength) is Strength
                and type(fact.modality) is Modality and type(fact.temporal_state) is TemporalState
                and type(fact.role) is Role,'FACT_SCHEMA')
        self._proposition(fact.proposition)
        require(fact.scope.path in self.scopes,'UNBOUND_SCOPE')
        self._conditions(fact.conditions)
        require(fact.source_id in self.sources,'SOURCE_NOT_ADMITTED')
        source=self.sources[fact.source_id]
        require(source.basis!='SOURCE_REPORT' or fact.modality==Modality.REPORTED,'REPORT_QUALIFICATION_REQUIRED')
        require(not fact.conditions or fact.modality in {Modality.CONDITIONAL,Modality.REPORTED},'CONDITIONS_MUST_REMAIN_VISIBLE')
        require(fact.role!=Role.MEASUREMENT_ASSUMPTION or fact.modality in {Modality.CONDITIONAL,Modality.HYPOTHETICAL},
                'ASSUMPTION_CANNOT_BE_ASSERTED_OBSERVATION')
        require(fact.strength.coverage==Coverage.OPEN,'FACT_CANNOT_GRANT_COMPLETENESS')
        require(fact.proposition.predicate=='excluded' or fact.strength.disposition!=Disposition.EXCLUDED,'SUPPORTED_NOT_EXCLUDED')
        require(fact.proposition.predicate!='excluded' or fact.role==Role.EXCLUSION_EVIDENCE,'EXCLUSION_ROLE')
        phases={'assigned':('EXPLICITLY_ASSIGNED',TemporalState.ASSIGNED),
                'completed':('EXPLICITLY_COMPLETED',TemporalState.COMPLETED),
                'planned':('PLANNED',TemporalState.PLANNED),'proposed':('PROPOSED',TemporalState.UNSPECIFIED)}
        if fact.proposition.predicate in phases:
            if fact.attribution in {'INFERRED','UNKNOWN'}:
                require(fact.temporal_state==TemporalState.UNSPECIFIED and fact.modality==Modality.HYPOTHETICAL
                        and fact.strength.epistemic<=(Epistemic.POSSIBLE if fact.attribution=='INFERRED' else Epistemic.UNKNOWN),
                        'UNVERIFIED_RESPONSIBILITY_MUST_REMAIN_LOW_AUTHORITY')
            else:
                require((fact.attribution,fact.temporal_state)==phases[fact.proposition.predicate],'RESPONSIBILITY_PHASE')
            require(self.entities[fact.proposition.subject].kind=='ACTOR' and self.entities[fact.proposition.object].kind=='TASK','ACTOR_TASK_TYPES')
            require(source.speaker!='unknown','UNRESOLVED_SPEAKER')
        return self._add(self.evidence,fact.evidence_id,fact,Evidence)

    def rule(self,rule):
        require(type(rule) is Rule and rule.source_id in self.sources and type(rule.scope) is Scope
                and type(rule.premises) is tuple and 0<len(rule.premises)<=16,'RULE_SCHEMA')
        require(self.sources[rule.source_id].origin!=Origin.USER and self.sources[rule.source_id].basis!='SOURCE_REPORT','UNVERIFIED_RULE_SOURCE')
        require(rule.kind in {'IMPLICATION','EXCLUSION'} and type(rule.bridge) is bool,'RULE_KIND')
        require(rule.scope.path in self.scopes,'UNBOUND_SCOPE')
        for p in (*rule.premises,rule.conclusion): self._proposition(p)
        self._conditions(rule.conditions)
        require(rule.conclusion.predicate not in {'assigned','completed','planned','proposed'},'RESPONSIBILITY_REQUIRES_DIRECT_SOURCE')
        require(rule.strength.coverage==Coverage.OPEN,'RULE_CANNOT_GRANT_COMPLETENESS')
        require(rule.kind=='EXCLUSION' if rule.conclusion.predicate=='excluded' else rule.kind=='IMPLICATION','RULE_CONCLUSION_KIND')
        cross=any(p.relation_domain!=rule.conclusion.relation_domain for p in rule.premises)
        require(not cross or rule.bridge,'DIRECTED_BRIDGE_REQUIRED')
        return self._add(self.rules,rule.rule_id,rule,Rule)

    def candidate(self,candidate):
        require(type(candidate) is Candidate and type(candidate.scope) is Scope,'CANDIDATE_SCHEMA')
        self._proposition(candidate.proposition)
        require(candidate.scope.path in self.scopes,'UNBOUND_SCOPE')
        require(candidate.candidate_id in self.entities and self.entities[candidate.candidate_id].kind=='CANDIDATE','CANDIDATE_ENTITY')
        return self._add(self.candidates,candidate.candidate_id,candidate,Candidate)

    def universe(self,universe):
        require(type(universe) is Universe and type(universe.scope) is Scope and universe.source_id in self.sources,'UNIVERSE_SCHEMA')
        require(type(universe.members) is tuple and 0<len(universe.members)<=128
                and len(set(universe.members))==len(universe.members),'UNIVERSE_MEMBERS')
        require(universe.label_id in self.entities and self.entities[universe.label_id].kind=='SCOPE','UNIVERSE_LABEL')
        require(all(c in self.candidates and self.candidates[c].scope==universe.scope for c in universe.members),'UNIVERSE_BOUNDARY')
        require(universe.completeness_basis in {'HOST_FINITE_SET','VERIFIED_ENUMERATION','OPEN'},'COMPLETENESS_BASIS')
        require(type(universe.generation_boundary) is str and bool(universe.generation_boundary),'GENERATION_BOUNDARY')
        require(universe.unresolved_remainder is None or type(universe.unresolved_remainder) is tuple,'REMAINDER_SCHEMA')
        if universe.completeness_basis!='OPEN':
            require(self.sources[universe.source_id].origin!=Origin.USER and self.sources[universe.source_id].basis!='SOURCE_REPORT','UNTRUSTED_COMPLETENESS')
        return self._add(self.universes,universe.universe_id,universe,Universe)

    def user_statement(self,text,*,actor_id,scope):
        """Only exact `我计划执行「task」。` / `我已完成「task」。` reports.

        Task labels must already resolve uniquely in host vocabulary. No pronoun,
        quote nesting, inferred assignment or truth of external work is admitted.
        """
        require(type(text) is str and len(text)<=12000,'USER_TEXT')
        match=re.fullmatch(r'我(计划执行|已完成)「([^「」\r\n]{1,80})」。',text)
        tasks=[e.entity_id for e in self.entities.values() if e.kind=='TASK' and match and e.label==match[2]]
        if not match or len(tasks)!=1:
            self.unparsed.append(digest(text)); return {'status':'UNPARSED','authority':'NONE'}
        require(actor_id in self.entities and self.entities[actor_id].kind=='ACTOR','USER_ACTOR')
        sid='statement_'+digest(text)[:24]
        self.source(Source(sid,Origin.USER,actor_id,'finite-user-grammar-1',digest(text),'SOURCE_REPORT'))
        completed=match[1]=='已完成'
        p=Proposition('completed' if completed else 'planned',actor_id,tasks[0],Domain.EXECUTION)
        self.fact(Evidence(sid,p,sid,scope,Strength(),Modality.REPORTED,
                  TemporalState.COMPLETED if completed else TemporalState.PLANNED,Role.OBSERVED_EVIDENCE,(),
                  'EXPLICITLY_COMPLETED' if completed else 'PLANNED'))
        return {'status':'PARSED_USER_REPORT','evidence_id':sid,'world_verified':False}

    def freeze(self):
        return TrustedState(*(tuple(getattr(self,k).values()) for k in
             ('entities','sources','evidence','rules','candidates','universes')),
             tuple(self.scopes.items()),tuple(self.unparsed),self.identity,_HOST_SEAL)
