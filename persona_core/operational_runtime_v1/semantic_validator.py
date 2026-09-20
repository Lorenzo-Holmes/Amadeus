"""Deterministic proof checking over an independently admitted finite inventory."""
from dataclasses import dataclass, asdict, replace
from semantic_types import *
from semantic_admission import TrustedState
from semantic_grounding import ATTRIBUTION_STATES

_VALIDATED = object()

@dataclass(frozen=True)
class ClaimCertificate:
    claim_id: str
    claim: Claim
    authorized_strength: Strength
    source_refs: tuple[str,...]
    evidence_refs: tuple[str,...]
    evidence_domains: tuple[str,...]
    bridge_refs: tuple[str,...]
    rule: str
    context_digest: str
    assertion_bases: tuple[str,...]
    candidate_id: str | None = None
    candidate_domain: str | None = None
    actor: str | None = None
    task: str | None = None

    @property
    def certificate_id(self):
        return digest(asdict(self))

@dataclass(frozen=True)
class ClosureCertificate:
    claim_id: str
    universe_id: str
    universe_scope: Scope
    candidate_boundary: tuple[str,...]
    known_members: tuple[str,...]
    excluded_members: tuple[str,...]
    remaining_members: tuple[str,...]
    unresolved_remainder: tuple[str,...]
    completeness_basis: str
    generation_boundary: str
    proof_status: str
    member_certificate_refs: tuple[str,...]
    context_digest: str

    @property
    def certificate_id(self):
        return digest(asdict(self))

@dataclass(frozen=True)
class Decision:
    claim_id: str
    action: str
    reasons: tuple[str,...]
    certificate: ClaimCertificate | None
    closure: ClosureCertificate | None = None

@dataclass(frozen=True)
class Validation:
    plan: SemanticPlan
    decisions: tuple[Decision,...]
    context_digest: str
    _seal: object

    @property
    def certificates(self):
        return tuple(d.certificate for d in self.decisions if d.certificate)

    def record(self):
        return {'version':VERSION,'context_digest':self.context_digest,
                'decisions':[asdict(d) for d in self.decisions]}

    def check(self,state):
        state.check()
        require(self._seal is _VALIDATED and self.context_digest==state.context_digest,'VALIDATED_STATE_REQUIRED')

def _same_except_polarity(a,b):
    return replace(a,polarity=b.polarity)==b

def _overlap(a,b):
    return a.contains(b) or b.contains(a)

def _proof(claim,state):
    evidence=state.table('evidence','evidence_id'); sources=state.table('sources','source_id')
    rules=state.table('rules','rule_id'); entities=state.table('entities','entity_id')
    require(claim.proposition.subject in entities and claim.proposition.object in entities,'UNKNOWN_ENTITY')
    require(claim.source_refs and all(s in sources for s in claim.source_refs),'SOURCE_MISSING')
    require(claim.evidence_refs and all(e in evidence for e in claim.evidence_refs),'EVIDENCE_MISSING')
    facts=[evidence[e] for e in claim.evidence_refs]
    require(all(e.scope.contains(claim.scope) for e in facts),'SCOPE_EXPANSION')
    used_sources={e.source_id for e in facts}
    conditions=set(c for e in facts for c in e.conditions)
    rule=None
    if claim.rule_ref:
        require(claim.rule_ref in rules,'UNKNOWN_RULE')
        rule=rules[claim.rule_ref]
        require(rule.conclusion==claim.proposition,'RULE_CONCLUSION_MISMATCH')
        require(len(facts)==len(rule.premises) and set(e.proposition for e in facts)==set(rule.premises),'RULE_PREMISES_MISMATCH')
        require(rule.scope.contains(claim.scope),'RULE_SCOPE_EXPANSION')
        require(tuple(claim.bridge_refs)==((rule.rule_id,) if rule.bridge else ()),'DIRECTED_BRIDGE_MISMATCH')
        require(all(e.proposition.relation_domain==claim.proposition.relation_domain for e in facts) or rule.bridge,'CROSS_DOMAIN_WITHOUT_BRIDGE')
        require(all(e.strength.epistemic>=Epistemic.SUPPORTED for e in facts),'POSSIBLE_PREMISE_NOT_PROOF')
        used_sources.add(rule.source_id); conditions.update(rule.conditions)
        authorization=replace(rule.strength,epistemic=min(rule.strength.epistemic,*(e.strength.epistemic for e in facts)))
        if claim.claim_type=='EXCLUSION':
            require(rule.kind=='EXCLUSION','EXCLUSION_RULE_REQUIRED')
    else:
        require(len(facts)==1 and facts[0].proposition==claim.proposition,'NO_ENTAILMENT')
        require(not claim.bridge_refs,'UNUSED_BRIDGE')
        authorization=facts[0].strength
    require(set(claim.source_refs)==used_sources,'SOURCE_BINDING_MISMATCH')
    require(all(e.temporal_state==claim.temporal_state for e in facts),'TEMPORAL_UPGRADE')
    require(all(sources[s].speaker==claim.speaker for s in used_sources),'SPEAKER_MISMATCH')
    # Search the whole inventory, not only the provider-selected support subset.
    for other in evidence.values():
        if not _overlap(other.scope,claim.scope) or other.conditions!=tuple(sorted(conditions)):
            continue
        if other.strength.epistemic<Epistemic.SUPPORTED:
            continue
        p=other.proposition
        require(not (_same_except_polarity(p,claim.proposition) and p.polarity!=claim.proposition.polarity),'CONFLICTING_EVIDENCE')
        if p.predicate==claim.proposition.predicate=='value' and p.subject==claim.proposition.subject and p.relation_domain==claim.proposition.relation_domain:
            require(p.object==claim.proposition.object or not p.polarity or not claim.proposition.polarity,'CONFLICTING_VALUE')
    if claim.claim_type=='EXCLUSION':
        require(claim.strength.disposition==Disposition.EXCLUDED and claim.strength.coverage==Coverage.OPEN
                and claim.strength.epistemic>=Epistemic.SUPPORTED,'EXCLUSION_STRENGTH_SCHEMA')
        candidates=state.table('candidates','candidate_id')
        require(claim.candidate_id in candidates,'CANDIDATE_MISSING')
        candidate=candidates[claim.candidate_id]
        require(claim.proposition==replace(candidate.proposition,predicate='excluded') and candidate.scope==claim.scope,'EXCLUSION_TARGET')
        require(authorization.disposition==Disposition.EXCLUDED,'NO_EXCLUSION_AUTHORITY')
        require(rule is not None or facts[0].role==Role.EXCLUSION_EVIDENCE,'EXCLUSION_ROLE')
        # A direct contrary observation cannot be omitted to obtain exclusion.
        require(not any(e.proposition==candidate.proposition and _overlap(e.scope,claim.scope)
                    and e.strength.epistemic>=Epistemic.SUPPORTED and not e.conditions for e in evidence.values()),'CANDIDATE_CONFLICT')
    else:
        require(claim.proposition.predicate!='excluded' and authorization.disposition!=Disposition.EXCLUDED,'EXCLUSION_CERTIFICATE_REQUIRED')
        if claim.candidate_id:
            candidate=state.table('candidates','candidate_id').get(claim.candidate_id)
            require(candidate is not None and candidate.proposition==claim.proposition and candidate.scope==claim.scope,'CANDIDATE_SUPPORT_MISMATCH')
    if claim.proposition.predicate in {'assigned','completed','planned','proposed'}:
        require(claim.claim_type=='RESPONSIBILITY' and rule is None,'RESPONSIBILITY_CERTIFICATE_REQUIRED')
    if claim.claim_type=='RESPONSIBILITY':
        require(claim.attribution in ATTRIBUTION_STATES and all(e.attribution==claim.attribution for e in facts),'OWNERSHIP_UPGRADE')
        require(entities[claim.proposition.subject].kind=='ACTOR' and entities[claim.proposition.object].kind=='TASK','ACTOR_TASK_TYPES')
        require(claim.speaker!='unknown','UNRESOLVED_SPEAKER')
    else:
        require(claim.attribution=='UNKNOWN','UNBOUND_ATTRIBUTION')
    require(not claim.universe_id and not claim.member_claims,'UNUSED_CLOSURE_FIELDS')
    expected=Modality.REPORTED if any(e.modality==Modality.REPORTED for e in facts) else (
        Modality.CONDITIONAL if conditions else facts[0].modality)
    require(all(e.modality in {expected,Modality.ASSERTED} for e in facts),'INCOMPATIBLE_MODALITIES')
    reasons=[]
    action='ALLOW'
    if claim.modality!=expected or set(claim.unresolved_dependencies)!=conditions:
        require(not set(claim.unresolved_dependencies)-conditions,'UNKNOWN_DEPENDENCIES')
        action='QUALIFY'; reasons.append('RETAIN_MODALITY_AND_CONDITIONS')
    wanted=claim.strength
    # No certificate may turn evidence of support into exclusion or completeness.
    if wanted.disposition>authorization.disposition or wanted.coverage>authorization.coverage:
        raise SemanticError('INCOMPARABLE_CLAIM_STRENGTH')
    authorized=Strength(min(wanted.epistemic,authorization.epistemic),wanted.disposition,wanted.coverage)
    if not authorization.permits(wanted):
        action='DOWNGRADE'; reasons.append('EPISTEMIC_FORCE_REDUCED')
    accepted=replace(claim,strength=authorized,modality=expected,unresolved_dependencies=tuple(sorted(conditions)))
    cert=ClaimCertificate(claim.claim_id,accepted,authorization,tuple(sorted(used_sources)),claim.evidence_refs,
         tuple(e.proposition.relation_domain.value for e in facts),claim.bridge_refs,
         rule.rule_id if rule else 'DIRECT_TYPED_FACT',state.context_digest,
         tuple(sorted({sources[s].basis for s in used_sources})),claim.candidate_id,
         claim.proposition.relation_domain.value if claim.candidate_id else None,
         claim.proposition.subject if claim.claim_type=='RESPONSIBILITY' else None,
         claim.proposition.object if claim.claim_type=='RESPONSIBILITY' else None)
    return Decision(claim.claim_id,action,tuple(reasons),cert)

def _closure(claim,state,decisions):
    universe=state.table('universes','universe_id').get(claim.universe_id)
    require(universe is not None,'UNIVERSE_MISSING')
    require(claim.scope==universe.scope,'CLOSURE_SCOPE_EXPANSION')
    require(claim.proposition==Proposition('observed',universe.label_id,universe.label_id,Domain.EXPLANATION),'CLOSURE_PROPOSITION')
    require(universe.completeness_basis!='OPEN' and universe.unresolved_remainder==(),'UNRESOLVED_REMAINDER')
    require(not claim.unresolved_dependencies and claim.modality==Modality.ASSERTED and claim.temporal_state==TemporalState.UNSPECIFIED,'CONDITIONAL_CLOSURE')
    require(not claim.evidence_refs and not claim.bridge_refs and not claim.rule_ref and not claim.candidate_id
            and claim.attribution=='UNKNOWN','CLOSURE_SCHEMA')
    members=[]; excluded=[]; sources={universe.source_id}; cert_ids=[]
    for ref in claim.member_claims:
        require(ref in decisions and decisions[ref].certificate is not None,'UNPROVED_MEMBER')
        cert=decisions[ref].certificate; c=cert.claim
        require(c.candidate_id in universe.members and c.scope==universe.scope,'FOREIGN_CLOSURE_MEMBER')
        require(c.modality==Modality.ASSERTED and not c.unresolved_dependencies and c.strength.epistemic>=Epistemic.SUPPORTED,'CONDITIONAL_MEMBER')
        members.append(c.candidate_id); sources.update(cert.source_refs); cert_ids.append(cert.certificate_id)
        if c.claim_type=='EXCLUSION': excluded.append(c.candidate_id)
    require(len(set(members))==len(members) and set(members)==set(universe.members),'INCOMPLETE_MEMBER_COVERAGE')
    require(set(claim.source_refs)==sources,'CLOSURE_SOURCE_BINDING')
    source_table=state.table('sources','source_id')
    require(all(source_table[s].speaker==claim.speaker for s in sources),'SPEAKER_MISMATCH')
    remaining=tuple(m for m in universe.members if m not in excluded)
    authorized=Strength(Epistemic.SUPPORTED,Disposition.UNASSESSED,Coverage.FINITE if remaining else Coverage.EXHAUSTIVE)
    require(authorized==claim.strength,'UNAUTHORIZED_EXHAUSTIVE_CLOSURE')
    close=ClosureCertificate(claim.claim_id,universe.universe_id,universe.scope,universe.members,universe.members,
        tuple(excluded),remaining,(),universe.completeness_basis,universe.generation_boundary,
        'FINITE_REMAINDER' if remaining else 'EXPLICITLY_EXHAUSTED',tuple(cert_ids),state.context_digest)
    cert=ClaimCertificate(claim.claim_id,claim,authorized,tuple(sorted(sources)),(),(),(),
        'CHECKED_FINITE_PARTITION',state.context_digest,tuple(sorted({source_table[s].basis for s in sources})))
    return Decision(claim.claim_id,'ALLOW',(),cert,close)

def _limitation(claim,state):
    """Absence of a checked derivation is only a statement about this context."""
    entities=state.table('entities','entity_id'); sources=state.table('sources','source_id')
    require(claim.proposition.subject in entities and claim.proposition.object in entities,'UNKNOWN_ENTITY')
    require(set(claim.source_refs)==set(sources) and set(claim.evidence_refs)=={e.evidence_id for e in state.evidence},'LIMITATION_REQUIRES_FULL_INVENTORY')
    require(claim.modality==Modality.ASSERTED and claim.strength==Strength()
            and not claim.bridge_refs and not claim.rule_ref and not claim.universe_id
            and not claim.candidate_id and not claim.member_claims and not claim.unresolved_dependencies
            and claim.temporal_state==TemporalState.UNSPECIFIED and claim.attribution=='UNKNOWN'
            and claim.speaker=='host','LIMITATION_SCHEMA')
    attempts=[]
    for fact in state.evidence:
        if fact.proposition==claim.proposition and fact.scope.contains(claim.scope):
            attempts.append((None,[fact]))
    for rule in state.rules:
        if rule.conclusion!=claim.proposition or not rule.scope.contains(claim.scope): continue
        facts=[next((f for f in state.evidence if f.proposition==p and f.scope.contains(claim.scope)
                    and not f.conditions and f.modality==Modality.ASSERTED and f.strength.epistemic>=Epistemic.SUPPORTED),None)
               for p in rule.premises]
        if all(facts): attempts.append((rule,facts))
    failure_codes=[]
    for rule,facts in attempts:
        if any(f.conditions or f.modality!=Modality.ASSERTED or f.strength.epistemic<Epistemic.SUPPORTED for f in facts): continue
        used={f.source_id for f in facts}|({rule.source_id} if rule else set())
        kind='RESPONSIBILITY' if claim.proposition.predicate in {'assigned','completed','planned','proposed'} else 'ASSERTION'
        candidate=next((c.candidate_id for c in state.candidates if replace(c.proposition,predicate='excluded')==claim.proposition and c.scope==claim.scope),None)
        if candidate: kind='EXCLUSION'
        proposed=replace(claim,claim_type=kind,source_refs=tuple(sorted(used)),evidence_refs=tuple(f.evidence_id for f in facts),
                 rule_ref=rule.rule_id if rule else None,bridge_refs=(rule.rule_id,) if rule and rule.bridge else (),
                 speaker=sources[facts[0].source_id].speaker,temporal_state=facts[0].temporal_state,
                 attribution=facts[0].attribution,strength=facts[0].strength,candidate_id=candidate)
        try:
            proof=_proof(proposed,state)
        except SemanticError as exc:
            failure_codes.append(str(exc)); continue
        if not proof.certificate.claim.unresolved_dependencies and proof.certificate.claim.modality==Modality.ASSERTED:
            raise SemanticError('LIMITATION_CONTRADICTS_CHECKED_SUPPORT')
    reason='CONFLICT_REQUIRES_RECONCILIATION' if any(c.startswith('CONFLICTING') for c in failure_codes) else 'NO_CHECKED_CONTEXT_SUPPORT'
    cert=ClaimCertificate(claim.claim_id,claim,Strength(),claim.source_refs,claim.evidence_refs,
          tuple(e.proposition.relation_domain.value for e in state.evidence),(),reason,state.context_digest,
          ('HOST_OBSERVATION',))
    return Decision(claim.claim_id,'ALLOW',(),cert)

def validate(plan,state):
    require(type(state) is TrustedState,'TRUSTED_STATE_REQUIRED'); state.check()
    require(type(plan) is SemanticPlan and plan.context_digest==state.context_digest,'STALE_OR_FOREIGN_CONTEXT')
    decisions={}
    # Forward references are not accepted; this also makes dependency cycles fail.
    for claim in plan.claims:
        try:
            require(claim.scope.path in dict(state.scope_names),'UNBOUND_CLAIM_SCOPE')
            decision=(_closure(claim,state,decisions) if claim.claim_type=='CLOSURE' else
                      _limitation(claim,state) if claim.claim_type=='LIMITATION' else _proof(claim,state))
        except SemanticError as exc:
            decision=Decision(claim.claim_id,'BLOCK',(str(exc),),None)
        decisions[claim.claim_id]=decision
    return Validation(plan,tuple(decisions.values()),state.context_digest,_VALIDATED)

def validate_with_fallback(plan,state):
    result=validate(plan,state)
    if result.certificates:
        return result
    # Report the failed proposal and then the referenced, independently admitted
    # facts. This does not infer the converse, likelihood, or an exclusion.
    references={r for c in plan.claims for r in c.evidence_refs}
    sources=state.table('sources','source_id'); ids={c.claim_id for c in plan.claims}
    extra=[]
    for fact in state.evidence:
        if fact.evidence_id not in references or len(extra)>=3: continue
        cid='_host_fallback_'+str(len(extra))
        while cid in ids: cid+='x'
        candidate=next((c.candidate_id for c in state.candidates if replace(c.proposition,predicate='excluded')==fact.proposition and c.scope==fact.scope),None)
        kind=('EXCLUSION' if candidate else 'RESPONSIBILITY' if fact.proposition.predicate in
              {'assigned','completed','planned','proposed'} else 'ASSERTION')
        extra.append(Claim(cid,kind,fact.proposition,fact.scope,fact.modality,fact.strength,(fact.source_id,),
               (fact.evidence_id,),unresolved_dependencies=fact.conditions,temporal_state=fact.temporal_state,
               speaker=sources[fact.source_id].speaker,attribution=fact.attribution,candidate_id=candidate))
    if not extra or len(plan.claims)+len(extra)>MAX_CLAIMS: return result
    return validate(replace(plan,claims=plan.claims+tuple(extra)),state)
