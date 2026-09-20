"""Conservative Chinese dialogue workflows backed by original text evidence.

Recognizes explicit proposal/confirmation/correction forms, not arbitrary JSON,
role claims, model-suggested state fields, or inferred external completion.
Ambiguous language remains an observed utterance; no silent fact upgrade.
"""
from __future__ import annotations
import hashlib
import json
import re
from admission import AdmissionController
from transcript_store import SessionHandle, StoreGuard

PROPOSAL = re.compile(r'提议约定[：:]([^；;\r\n]{1,1000})[；;]\s*验收内容[：:]([^；;\r\n]{1,4000})(?:[；;].*)?')
CONFIRM = re.compile(r'确认约定：([^\r\n]{1,1000})')
CORRECTION = re.compile(r'更正[：:]([^；;\r\n]{1,4000})[；;]\s*改为[：:]([^；;\r\n]{1,4000})')
VERSION = 'EXPLICIT_DIALOGUE_EVIDENCE_46_1'

class DialogueAdmissionController(AdmissionController):
    def _existing_effects(self, handle: SessionHandle, turn_id: str) -> list[dict]:
        result = []
        for row in self.store.db.execute('SELECT event_json FROM runtime_events WHERE entity_id=? AND event_type<>? ORDER BY sequence',
                                         (handle.entity_id, 'UTTERANCE_OBSERVED')):
            event = json.loads(row[0])
            payload = event['payload']
            if turn_id in {payload.get('confirmation_turn_id'), payload.get('submission_turn_id'), payload.get('turn_id')}:
                result.append({'event_id': event['event_id'], 'event_type': event['event_type'],
                               'decision_id': event['decision_id'], 'sequence': event['sequence']})
        return result

    def observe_turn(self, handle: SessionHandle, turn_id: str) -> dict:
        result = super().observe_turn(handle, turn_id)
        result['workflow_version'] = VERSION
        if self.runtime is None or handle.mode != 'PRODUCT_RUNTIME':
            result['workflow_status'] = 'RAW_UTTERANCE_ONLY'
            return result
        existing = self._existing_effects(handle, turn_id)
        if existing:
            result.update(workflow_status='EXISTING_EFFECTS_NOT_REAPPLIED', verified_effects=existing)
            return result
        turn = self._turn(handle, turn_id)
        text = turn['user_text'].strip()
        notes = []
        confirmation = CONFIRM.fullmatch(text)
        correction = CORRECTION.fullmatch(text)
        try:
            if confirmation:
                name = confirmation.group(1).strip()
                proposals = []
                for row in self.store.db.execute('''SELECT t.* FROM turns t JOIN sessions s USING(session_id)
                    WHERE s.entity_id=? AND s.principal_id=? AND s.mode='PRODUCT_RUNTIME'
                    AND t.seq<? AND t.status='DISPLAYED' ORDER BY t.seq''',
                    (handle.entity_id, handle.principal_id, turn['seq'])):
                    from accepted_output import project_turn
                    row = project_turn(self.store.db, row, 'memory')
                    match = PROPOSAL.fullmatch(row['user_text'].strip())
                    if match and match.group(1).strip() == name and row['assistant_text'].strip() == '同意约定：' + name:
                        proposals.append((row['turn_id'], match.group(2).strip()))
                if len(proposals) == 1:
                    decision = self.confirm_agreement(handle, proposals[0][0], turn_id, name, proposals[0][1])
                    self.runtime.commit(handle, decision)
                    notes.append('EXPLICIT_MUTUAL_TEXT_AGREEMENT_VERIFIED')
                else:
                    notes.append('HOLD_PROPOSAL_MISSING_OR_AMBIGUOUS')
            elif correction:
                old, replacement = correction.group(1).strip(), correction.group(2).strip()
                matches = self.store.db.execute('''SELECT event_id FROM retrieval_documents
                    WHERE entity_id=? AND superseded_by IS NULL AND text_content=?
                    AND event_type IN ('UTTERANCE_OBSERVED','FACT_CORRECTED') AND provenance='PRODUCT_RUNTIME' ''',
                    (handle.entity_id, old)).fetchall()
                if len(matches) == 1:
                    decision = self.correct_user_statement(handle, matches[0][0], turn_id, replacement)
                    self.runtime.commit(handle, decision)
                    notes.append('EXPLICIT_SAME_ENTITY_USER_CORRECTION')
                else:
                    notes.append('HOLD_CORRECTION_TARGET_MISSING_OR_AMBIGUOUS')
            else:
                actual_sha = hashlib.sha256(turn['user_text'].encode('utf-8')).hexdigest()
                matches = [c for c in self.runtime.snapshot(handle)['commitments'].values()
                           if c['status'] == 'OPEN' and c['expected_text_sha256'] == actual_sha]
                if len(matches) == 1:
                    decision = self.verify_text_submission(handle, matches[0]['commitment_id'], turn_id)
                    self.runtime.commit(handle, decision)
                    notes.append('EXACT_TEXT_SUBMISSION_VERIFIED_NOT_EXTERNAL_WORK')
                elif len(matches) > 1:
                    notes.append('HOLD_MULTIPLE_AGREEMENTS_MATCH_ONE_SUBMISSION')
                else:
                    notes.append('NO_VERIFIABLE_STATE_TRANSITION')
        except StoreGuard as exc:
            # Never downgrade an integrity or authority failure into benign HOLD.
            # A concurrent already-committed effect is the only safe reconciliation.
            if not self._existing_effects(handle, turn_id):
                raise
            notes.append('EXISTING_EFFECT_RECONCILED_AFTER_CONCURRENT_COMMIT')
        result.update(workflow_status='CHECKED', reason_codes=notes,
                      verified_effects=self._existing_effects(handle, turn_id),
                      external_action_proven=False, natural_language_role_claims_authorize_nothing=True)
        return result
