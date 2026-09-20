"""Host-bound evidence admission. User/model JSON never becomes authority.

Threat model: the OS user and application code are trusted; untrusted chat,
retrieval and model text are not. Python object seals are capability boundaries
inside this host, not protection against an attacker controlling Python/SQLite.
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any
from provider import canonical, digest
from transcript_store import TranscriptStore, SessionHandle, StoreGuard, ensure, utc_now

POLICY = 'admission-46.2'
LEGACY_POLICIES = {'admission-46.1', POLICY}
FORBIDDEN = {'SOURCE_MEMORY_WRITE','PERSONA_WRITE','CAPABILITY_GRANT','RELATIONSHIP_WRITE','STATE_REPLACE','GENESIS_INSTALL'}
EVIDENCE_KINDS = {
    'UTTERANCE_OBSERVED':'HOST_TRANSCRIPT_OBSERVATION',
    'COMMITMENT_OPEN':'MUTUAL_DIALOGUE_AGREEMENT',
    'COMMITMENT_FULFILLED':'TRUSTED_LOCAL_TEXT_CHECK_RECEIPT',
    'INTEREST_OBSERVED':'HOST_BOUND_USER_STATEMENT',
    'APOLOGY_OBSERVED':'HOST_BOUND_USER_STATEMENT',
    'BOUNDARY_VIOLATION':'HOST_REVIEWED_BOUNDARY_OBSERVATION',
    'FACT_CORRECTED':'HOST_BOUND_USER_CORRECTION',
}

@dataclass(frozen=True)
class EvidenceToken:
    receipt_id: str
    entity_id: str
    fingerprint: str
    _seal: object = field(repr=False,compare=False)

@dataclass(frozen=True)
class AdmissionDecision:
    decision_id: str
    entity_id: str
    verdict: str
    effect_kind: str | None
    payload_json: str
    evidence_fingerprint: str | None
    _seal: object = field(repr=False,compare=False)

class AdmissionController:
    def __init__(self, store: TranscriptStore):
        self.store = store
        self._seal = object()
        self.runtime = None
        store.db.executescript('''
        CREATE TABLE IF NOT EXISTS evidence_receipts(
          receipt_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entities(entity_id),
          effect_kind TEXT NOT NULL, evidence_class TEXT NOT NULL,
          payload_json TEXT NOT NULL, source_turns_json TEXT NOT NULL,
          fingerprint TEXT UNIQUE NOT NULL, created_at_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS event_candidates(
          candidate_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id),
          entity_id TEXT NOT NULL REFERENCES entities(entity_id), claimed_entity_id TEXT NOT NULL,
          kind TEXT NOT NULL, payload_json TEXT NOT NULL, proposer_kind TEXT NOT NULL,
          requested_effects_json TEXT NOT NULL, source_turns_json TEXT NOT NULL,
          candidate_sha256 TEXT NOT NULL, created_at_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS admission_decisions(
          decision_id TEXT PRIMARY KEY, candidate_id TEXT UNIQUE NOT NULL REFERENCES event_candidates(candidate_id),
          entity_id TEXT NOT NULL REFERENCES entities(entity_id), verdict TEXT NOT NULL,
          effect_kind TEXT, payload_json TEXT NOT NULL, evidence_fingerprint TEXT,
          evidence_class TEXT, policy_version TEXT NOT NULL, reasons_json TEXT NOT NULL,
          decision_sha256 TEXT NOT NULL, created_at_utc TEXT NOT NULL);
        ''')

    def _turn(self, handle: SessionHandle, turn_id: str) -> dict:
        self.store._authenticate(handle)
        row = self.store.db.execute('''SELECT t.*, s.mode AS session_mode FROM turns t JOIN sessions s USING(session_id)
          WHERE t.turn_id=? AND s.entity_id=? AND s.principal_id=? AND s.mode=?''',
          (turn_id,handle.entity_id,handle.principal_id,handle.mode)).fetchone()
        ensure(row is not None,'Evidence unavailable for this entity')
        from accepted_output import project_turn
        return project_turn(self.store.db, row, 'memory')

    def _issue(self, handle: SessionHandle, kind: str, payload: dict, turns: list[str],
               *, physical_fingerprint: str | None = None) -> EvidenceToken:
        self.store._authenticate(handle)
        ensure(kind in EVIDENCE_KINDS,'Unknown host observation kind')
        ensure(turns and len(turns)<=8,'Evidence must bind original turns')
        bound = []
        for tid in turns:
            row = self._turn(handle,tid)
            ensure(row['status']=='DISPLAYED','Evidence turn not displayed')
            bound.append({'turn_id':tid,'user_sha256':digest(row['user_text']),
                          'assistant_sha256':digest(row['assistant_text']), 'origin':row['response_provenance'],
                          'mode':row['session_mode']})
        fingerprint = physical_fingerprint or digest({'entity_id':handle.entity_id,'kind':kind,'payload':payload,'turns':bound})
        rid = 'receipt_' + fingerprint
        ptext, ttext = canonical(payload).decode('utf-8'),canonical(bound).decode('utf-8')
        with self.store.transaction():
            old = self.store.db.execute('SELECT * FROM evidence_receipts WHERE fingerprint=?',(fingerprint,)).fetchone()
            if old:
                ensure(old['entity_id']==handle.entity_id and old['effect_kind']==kind and old['payload_json']==ptext
                       and old['source_turns_json']==ttext,'Receipt already bound to a different observation or commitment')
            else:
                self.store.db.execute('INSERT INTO evidence_receipts VALUES(?,?,?,?,?,?,?,?)',
                    (rid,handle.entity_id,kind,EVIDENCE_KINDS[kind],ptext,ttext,fingerprint,utc_now()))
        return EvidenceToken(rid,handle.entity_id,fingerprint,self._seal)

    def propose(self, handle: SessionHandle, kind: str, payload: dict, *, key: str,
                source_turn_ids: list[str], claimed_entity_id: str | None = None,
                proposer_kind: str = 'UNTRUSTED_TEXT', requested_effects: list | None = None) -> str:
        self.store._authenticate(handle)
        ensure(isinstance(kind,str) and 0<len(kind)<=80,'Invalid candidate kind')
        ensure(isinstance(payload,dict) and len(canonical(payload))<=32768,'Invalid candidate payload')
        ensure(isinstance(key,str) and 0<len(key)<=300,'Candidate idempotency key required')
        ensure(isinstance(source_turn_ids,list) and len(source_turn_ids)<=8,'Invalid source references')
        values = {'session_id':handle.session_id,'entity_id':handle.entity_id,
                  'claimed_entity_id':claimed_entity_id or handle.entity_id,'kind':kind,
                  'payload':payload,'proposer_kind':proposer_kind,
                  'requested_effects':requested_effects or [],'source_turn_ids':source_turn_ids}
        fingerprint = digest(values)
        cid = 'candidate_' + digest({'session_id':handle.session_id,'key':key})
        with self.store.transaction():
            old = self.store.db.execute('SELECT candidate_sha256 FROM event_candidates WHERE candidate_id=?',(cid,)).fetchone()
            if old:
                ensure(old[0]==fingerprint,'Candidate key reused with different content')
            else:
                self.store.db.execute('INSERT INTO event_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (cid,handle.session_id,handle.entity_id,values['claimed_entity_id'],kind,canonical(payload).decode('utf-8'),
                     proposer_kind,canonical(values['requested_effects']).decode('utf-8'),canonical(source_turn_ids).decode('utf-8'),fingerprint,utc_now()))
        return cid

    def decide(self, handle: SessionHandle, candidate_id: str, evidence: EvidenceToken | None = None) -> AdmissionDecision:
        self.store._authenticate(handle)
        candidate = self.store.db.execute('SELECT * FROM event_candidates WHERE candidate_id=? AND entity_id=?',
                                           (candidate_id,handle.entity_id)).fetchone()
        ensure(candidate is not None,'Candidate unavailable for this entity')
        old = self.store.db.execute('SELECT decision_id FROM admission_decisions WHERE candidate_id=?',(candidate_id,)).fetchone()
        if old:
            return self.load_decision(handle,old[0])
        verdict, reasons, receipt = 'HOLD',['TRUSTED_EVIDENCE_REQUIRED'],None
        payload = json.loads(candidate['payload_json'])
        forbidden_fields = {'admission_authority','source_memory_write','persona_write','capability_grant','trust','permissions','state_override'}
        if candidate['kind'] in FORBIDDEN or candidate['kind'] not in EVIDENCE_KINDS:
            verdict,reasons = 'REJECT',['FORBIDDEN_OR_UNSUPPORTED_EVENT_KIND']
        elif candidate['claimed_entity_id'] != handle.entity_id:
            verdict,reasons = 'REJECT',['ENTITY_MISMATCH']
        elif json.loads(candidate['requested_effects_json']) or forbidden_fields.intersection(payload):
            verdict,reasons = 'REJECT',['CALLER_REQUESTED_STATE_AUTHORITY']
        elif evidence is not None:
            if type(evidence) is not EvidenceToken or evidence._seal is not self._seal or evidence.entity_id != handle.entity_id:
                verdict,reasons = 'REJECT',['HOST_ISSUED_EVIDENCE_TOKEN_REQUIRED']
            else:
                receipt = self.store.db.execute('SELECT * FROM evidence_receipts WHERE receipt_id=? AND entity_id=?',
                                                (evidence.receipt_id,handle.entity_id)).fetchone()
                if receipt is None or receipt['fingerprint']!=evidence.fingerprint or receipt['effect_kind']!=candidate['kind'] or receipt['payload_json']!=candidate['payload_json']:
                    verdict,reasons = 'REJECT',['EVIDENCE_PAYLOAD_OR_KIND_MISMATCH']
                else:
                    try:
                        bound = json.loads(receipt['source_turns_json'])
                        ensure([r['turn_id'] for r in bound]==json.loads(candidate['source_turns_json']),'Source set mismatch')
                        for r in bound:
                            turn = self._turn(handle,r['turn_id'])
                            ensure(turn['status']=='DISPLAYED' and digest(turn['user_text'])==r['user_sha256']
                                   and digest(turn['assistant_text'])==r['assistant_sha256'],'Original utterance binding changed')
                        verdict,reasons = 'ADMIT',['HOST_EVIDENCE_BOUND_TO_ORIGINAL_UTTERANCES']
                    except StoreGuard:
                        verdict,reasons = 'REJECT',['EVIDENCE_SCOPE_OR_CONTENT_MISMATCH']
        did = 'decision_' + digest({'candidate_id':candidate_id,'policy':POLICY})
        approved_payload = candidate['payload_json'] if verdict=='ADMIT' else '{}'
        fingerprint = receipt['fingerprint'] if receipt is not None and verdict=='ADMIT' else None
        evidence_class = receipt['evidence_class'] if fingerprint else None
        effect_kind = candidate['kind'] if verdict=='ADMIT' else None
        decision_binding = digest([did,candidate_id,handle.entity_id,verdict,effect_kind,approved_payload,fingerprint,evidence_class,POLICY,reasons])
        with self.store.transaction():
            self.store.db.execute('INSERT OR IGNORE INTO admission_decisions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (did,candidate_id,handle.entity_id,verdict,effect_kind,approved_payload,fingerprint,evidence_class,POLICY,
                 canonical(reasons).decode('utf-8'),decision_binding,utc_now()))
        return self.load_decision(handle,did)

    def load_decision(self, handle: SessionHandle, decision_id: str) -> AdmissionDecision:
        self.store._authenticate(handle)
        r = self.store.db.execute('SELECT * FROM admission_decisions WHERE decision_id=? AND entity_id=?',
                                  (decision_id,handle.entity_id)).fetchone()
        ensure(r is not None,'Decision unavailable for this entity')
        expected = digest([r['decision_id'],r['candidate_id'],r['entity_id'],r['verdict'],r['effect_kind'],r['payload_json'],
                           r['evidence_fingerprint'],r['evidence_class'],r['policy_version'],json.loads(r['reasons_json'])])
        ensure(expected==r['decision_sha256'] and r['policy_version'] in LEGACY_POLICIES,'Decision binding/version mismatch')
        return AdmissionDecision(r['decision_id'],r['entity_id'],r['verdict'],r['effect_kind'],r['payload_json'],r['evidence_fingerprint'],self._seal)

    def validate_decision(self, handle: SessionHandle, decision: AdmissionDecision) -> AdmissionDecision:
        ensure(type(decision) is AdmissionDecision and decision._seal is self._seal,'Host-issued decision required; strings do not authorize')
        current = self.load_decision(handle,decision.decision_id)
        ensure(current==decision and current.verdict=='ADMIT','Decision is not an authentic admitted effect')
        self.validate_persisted_evidence(handle,current)
        return current

    def validate_persisted_evidence(self, handle:SessionHandle, decision:AdmissionDecision) -> None:
        """Recheck original provenance on commit/reopen, not only on first admit."""
        self.store._authenticate(handle)
        ensure(decision.verdict=='ADMIT' and decision.entity_id==handle.entity_id,'Admitted same-entity decision required')
        receipt=self.store.db.execute('SELECT * FROM evidence_receipts WHERE fingerprint=? AND entity_id=?',
                                      (decision.evidence_fingerprint,handle.entity_id)).fetchone()
        ensure(receipt is not None and receipt['payload_json']==decision.payload_json
               and receipt['effect_kind']==decision.effect_kind,'Persistent receipt/decision binding mismatch')
        ensure(receipt['evidence_class']==EVIDENCE_KINDS[decision.effect_kind],'Receipt evidence class changed')
        for ref in json.loads(receipt['source_turns_json']):
            turn=self._turn(handle,ref['turn_id'])
            ensure(turn['status']=='DISPLAYED' and digest(turn['user_text'])==ref['user_sha256']
                   and digest(turn['assistant_text'])==ref['assistant_sha256']
                   and turn['response_provenance']==ref['origin'],'Original evidence transcript changed')
            if 'mode' in ref:
                ensure(turn['session_mode']==ref['mode']==handle.mode,'Original evidence mode changed')

    def _observed_decision(self, handle: SessionHandle, kind: str, payload: dict, turns: list[str],
                           *, physical_fingerprint: str | None = None) -> AdmissionDecision:
        evidence = self._issue(handle,kind,payload,turns,physical_fingerprint=physical_fingerprint)
        cid = self.propose(handle,kind,payload,key=evidence.receipt_id,source_turn_ids=turns,proposer_kind='HOST_OBSERVATION')
        return self.decide(handle,cid,evidence)

    def observe_turn(self, handle: SessionHandle, turn_id: str) -> dict:
        turn = self._turn(handle,turn_id)
        ensure(turn['status']=='DISPLAYED','Only actual displayed dialogue can be observed')
        payload = {'turn_id':turn_id,'user_text':turn['user_text'],'assistant_text':turn['assistant_text'],
                   'input_provenance':turn['input_provenance'],'response_provenance':turn['response_provenance'],
                   'described_events_proven':False}
        if turn.get('output_provenance') == 'HOST_ACCEPTED_OUTPUT':
            payload['output_provenance'] = turn['output_provenance']
            payload['accepted_output_sha256'] = digest(turn['accepted_output'])
        elif turn.get('output_provenance') == 'HOST_ACKNOWLEDGED_DISPLAY':
            payload.update(output_provenance=turn['output_provenance'],
                displayed_output_sha256=digest(turn['display_record']),
                accepted_output_sha256=turn['accepted_output_sha256'],
                display_policy_version=turn['display_record']['policy_version'],
                content_is_event_proof=False)
        decision = self._observed_decision(handle,'UTTERANCE_OBSERVED',payload,[turn_id])
        result = self.runtime.commit(handle,decision) if self.runtime is not None else None
        return {'decision_id':decision.decision_id,'verdict':decision.verdict,'evidence_class':'HOST_TRANSCRIPT_OBSERVATION',
                'runtime_events_committed':int(result is not None and not result.get('idempotent',False)),
                'commit':result,'content_is_event_proof':False}

    def confirm_agreement(self, handle: SessionHandle, proposal_turn_id: str, confirmation_turn_id: str,
                          text: str, expected_text: str) -> AdmissionDecision:
        proposal,confirmation = self._turn(handle,proposal_turn_id),self._turn(handle,confirmation_turn_id)
        ensure(0<len(text)<=1000 and 0<len(expected_text)<=4000,'Invalid text agreement')
        ensure(proposal['assistant_text'].strip()=='同意约定：'+text,'Explicit exact assistant agreement required')
        ensure(confirmation['user_text'].strip()=='确认约定：'+text,'Explicit user confirmation required')
        ensure(proposal['seq']<confirmation['seq'],'Agreement confirmation must follow proposal')
        ensure(text in proposal['user_text'] and expected_text in proposal['user_text'],'Terms or acceptance text missing from original user proposal')
        cid = 'commitment_' + digest([handle.entity_id,proposal_turn_id,confirmation_turn_id,text])
        payload = {'commitment_id':cid,'text':text,'status':'OPEN','expected_text_sha256':hashlib.sha256(expected_text.encode('utf-8')).hexdigest(),
                   'verification_policy':'EXACT_USER_TEXT_V1','proposal_turn_id':proposal_turn_id,'confirmation_turn_id':confirmation_turn_id}
        return self._observed_decision(handle,'COMMITMENT_OPEN',payload,[proposal_turn_id,confirmation_turn_id])

    def verify_text_submission(self, handle: SessionHandle, commitment_id: str, turn_id: str) -> AdmissionDecision:
        ensure(self.runtime is not None,'A committed open agreement is required')
        commitment = self.runtime.get_commitment(handle,commitment_id)
        turn = self._turn(handle,turn_id)
        ensure(commitment['status']=='OPEN','Agreement is not open')
        confirmation = self._turn(handle,commitment['confirmation_turn_id'])
        ensure(turn['seq']>confirmation['seq'],'Submission must follow the completed agreement; old text is not new fulfillment')
        actual_sha = hashlib.sha256(turn['user_text'].encode('utf-8')).hexdigest()
        ensure(actual_sha==commitment['expected_text_sha256'],'Submitted text does not satisfy the pinned agreement')
        payload = {'commitment_id':commitment_id,'submission_turn_id':turn_id,'observed_text_sha256':actual_sha,
                   'verification_policy':'EXACT_USER_TEXT_V1','tool':'HOST_LOCAL_TEXT_VERIFIER',
                   'claim_scope':'TEXT_SUBMISSION_ONLY_NOT_EXTERNAL_TASK_COMPLETION'}
        physical = digest(['HOST_LOCAL_TEXT_VERIFIER',handle.entity_id,turn_id,actual_sha])
        return self._observed_decision(handle,'COMMITMENT_FULFILLED',payload,[turn_id],physical_fingerprint=physical)

    def record_interest(self, handle: SessionHandle, turn_id: str, topic: str) -> AdmissionDecision:
        turn = self._turn(handle,turn_id)
        ensure(isinstance(topic,str) and 0<len(topic.strip())<=100,'Invalid interest topic')
        topic=topic.strip()
        declaration=turn['user_text'].strip().rstrip('。.!！')
        ensure(declaration in {'我喜欢'+topic,'我也喜欢'+topic,'我的兴趣是'+topic,'兴趣：'+topic},
               'Only an explicit complete affirmative self-declaration is admitted; negations, quotes and uncertain prose remain raw text')
        return self._observed_decision(handle,'INTEREST_OBSERVED',{'turn_id':turn_id,'topic':topic.strip().casefold(),
            'scope':'USER_SELF_REPORT_NOT_SHARED_PERSONA_FACT'},[turn_id])

    def record_apology(self, handle: SessionHandle, turn_id: str) -> AdmissionDecision:
        turn = self._turn(handle,turn_id)
        return self._observed_decision(handle,'APOLOGY_OBSERVED',{'turn_id':turn_id,'text':turn['user_text'],
            'scope':'UTTERANCE_ONLY_NOT_VERIFIED_REPAIR'},[turn_id])

    def record_reviewed_boundary(self, handle: SessionHandle, turn_id: str, exact_quote: str, reason: str) -> AdmissionDecision:
        """Host review annotation, not automatic sentiment inference from a word."""
        turn = self._turn(handle,turn_id)
        ensure(exact_quote and exact_quote in turn['user_text'] and reason.strip(),'Original quote and contextual host reason required')
        return self._observed_decision(handle,'BOUNDARY_VIOLATION',{'turn_id':turn_id,'quote':exact_quote,'reason':reason,
            'review_kind':'HOST_CONTEXTUAL_REVIEW_NOT_MODEL_SELF_AUTHORITY'},[turn_id])

    def correct_user_statement(self, handle: SessionHandle, old_event_id: str, new_turn_id: str, replacement: str) -> AdmissionDecision:
        ensure(self.runtime is not None,'Runtime event evidence required')
        old = self.runtime.get_event(handle,old_event_id)
        ensure(old['event_type'] in {'UTTERANCE_OBSERVED','FACT_CORRECTED'},'Cannot rewrite source, identity or trusted completion as a user correction')
        turn = self._turn(handle,new_turn_id)
        ensure(replacement and replacement in turn['user_text'],'Replacement must be an exact user quote')
        return self._observed_decision(handle,'FACT_CORRECTED',{'supersedes_event_id':old_event_id,'replacement':replacement,
            'turn_id':new_turn_id,'scope':'CORRECTED_USER_STATEMENT_NOT_EXTERNAL_TRUTH'},[new_turn_id])
