"""Governed post-Genesis Persona/Self adaptation.

This is deliberately separate from ordinary dialogue admission. Model text,
user role claims and raw utterances cannot directly mutate Persona or Self.
Stable runtime evidence may be proposed by trusted host code, then an explicit
host governance review can activate a versioned runtime adaptation. Frozen
Genesis/source files are never edited.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from provider import canonical, digest
from runtime_store import RuntimeStore
from transcript_store import SessionHandle, ensure, utc_now

VERSION = 'GOVERNED_GROWTH_1'
SCOPES = {'GLOBAL_SELF', 'ENTITY_RELATIONSHIP'}
DIMENSIONS = {'communication_preference', 'decision_tendency', 'self_preference', 'relationship_interpretation'}
EVIDENCE_EVENT_TYPES = {'INTEREST_OBSERVED', 'COMMITMENT_FULFILLED', 'BOUNDARY_VIOLATION', 'FACT_CORRECTED'}


@dataclass(frozen=True)
class GrowthProposal:
    proposal_id: str
    status: str
    scope_kind: str
    scope_entity_id: str | None
    dimension: str
    candidate: dict[str, Any]
    evidence_event_ids: tuple[str, ...]


class PersonaGrowthController:
    """Trusted-host governance API; never callable through natural-language fields."""

    def __init__(self, runtime: RuntimeStore):
        self.runtime = runtime
        self.store = runtime.store
        self.store.db.executescript('''
        CREATE TABLE IF NOT EXISTS persona_growth_proposals(
          proposal_id TEXT PRIMARY KEY,
          proposal_key TEXT UNIQUE NOT NULL,
          scope_kind TEXT NOT NULL,
          scope_entity_id TEXT,
          dimension TEXT NOT NULL,
          candidate_json TEXT NOT NULL,
          evidence_event_ids_json TEXT NOT NULL,
          evidence_sha256 TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS persona_growth_reviews(
          review_id TEXT PRIMARY KEY,
          proposal_id TEXT UNIQUE NOT NULL REFERENCES persona_growth_proposals(proposal_id),
          verdict TEXT NOT NULL,
          rationale TEXT NOT NULL,
          reviewer_class TEXT NOT NULL,
          reviewed_at_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS persona_growth_versions(
          version_id INTEGER PRIMARY KEY AUTOINCREMENT,
          proposal_id TEXT UNIQUE NOT NULL REFERENCES persona_growth_proposals(proposal_id),
          scope_kind TEXT NOT NULL,
          scope_entity_id TEXT,
          dimension TEXT NOT NULL,
          candidate_json TEXT NOT NULL,
          evidence_event_ids_json TEXT NOT NULL,
          activated_at_utc TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS persona_growth_active_scope
          ON persona_growth_versions(scope_kind,scope_entity_id,dimension,version_id);
        ''')

    @staticmethod
    def _validate_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
        ensure(isinstance(candidate, dict), 'Growth candidate must be an object')
        allowed = {'statement', 'conditions', 'limits', 'confidence'}
        ensure(set(candidate).issubset(allowed), 'Unsupported growth candidate field')
        statement = candidate.get('statement')
        conditions = candidate.get('conditions', [])
        limits = candidate.get('limits', [])
        confidence = candidate.get('confidence')
        ensure(isinstance(statement, str) and 0 < len(statement.strip()) <= 600, 'Growth statement required')
        ensure(isinstance(conditions, list) and len(conditions) <= 8 and all(isinstance(x, str) and 0 < len(x) <= 300 for x in conditions),
               'Invalid growth conditions')
        ensure(isinstance(limits, list) and len(limits) <= 8 and all(isinstance(x, str) and 0 < len(x) <= 300 for x in limits),
               'Invalid growth limits')
        ensure(isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and 0.0 <= float(confidence) <= 1.0,
               'Growth confidence must be 0..1')
        return {'statement': statement.strip(), 'conditions': list(conditions), 'limits': list(limits),
                'confidence': round(float(confidence), 4)}

    def _evidence(self, handle: SessionHandle, event_ids: list[str]) -> tuple[list[dict], str]:
        self.store._authenticate(handle)
        ensure(isinstance(event_ids, list) and 2 <= len(event_ids) <= 12 and len(set(event_ids)) == len(event_ids),
               'Stable growth proposal requires 2..12 distinct admitted events')
        events = [self.runtime.get_event(handle, eid) for eid in event_ids]
        ensure(all(e['mode'] == 'PRODUCT_RUNTIME' for e in events), 'Only product runtime evidence can support growth')
        ensure(all(e['event_type'] in EVIDENCE_EVENT_TYPES for e in events),
               'Raw utterances and unsupported events cannot support Persona/Self growth')
        sessions = {e['session_id'] for e in events}
        ensure(len(sessions) >= 2, 'Stable growth proposal requires evidence across at least two sessions')
        bindings = [{'event_id': e['event_id'], 'event_type': e['event_type'], 'entity_id': e['entity_id'],
                     'session_id': e['session_id'], 'event_sha256': digest(e)} for e in events]
        return events, digest(bindings)

    def propose(self, handle: SessionHandle, *, key: str, scope_kind: str, dimension: str,
                candidate: dict[str, Any], evidence_event_ids: list[str]) -> GrowthProposal:
        self.store._authenticate(handle)
        ensure(isinstance(key, str) and 0 < len(key) <= 200, 'Stable growth proposal key required')
        ensure(scope_kind in SCOPES, 'Unsupported growth scope')
        ensure(dimension in DIMENSIONS, 'Unsupported growth dimension')
        candidate = self._validate_candidate(candidate)
        events, evidence_sha = self._evidence(handle, evidence_event_ids)
        scope_entity = handle.entity_id if scope_kind == 'ENTITY_RELATIONSHIP' else None
        proposal_id = 'growth_' + digest([VERSION, handle.principal_id, key])
        values = [scope_kind, scope_entity, dimension, candidate, evidence_event_ids, evidence_sha]
        with self.store.transaction():
            old = self.store.db.execute('SELECT * FROM persona_growth_proposals WHERE proposal_id=?', (proposal_id,)).fetchone()
            if old:
                ensure(old['proposal_key'] == key and old['scope_kind'] == scope_kind and old['scope_entity_id'] == scope_entity
                       and old['dimension'] == dimension and old['candidate_json'] == canonical(candidate).decode('utf-8')
                       and old['evidence_event_ids_json'] == canonical(evidence_event_ids).decode('utf-8')
                       and old['evidence_sha256'] == evidence_sha, 'Growth proposal key reused with different content')
            else:
                self.store.db.execute('INSERT INTO persona_growth_proposals VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (proposal_id, key, scope_kind, scope_entity, dimension, canonical(candidate).decode('utf-8'),
                     canonical(evidence_event_ids).decode('utf-8'), evidence_sha, 'PENDING', utc_now()))
        return self.load(proposal_id)

    def load(self, proposal_id: str) -> GrowthProposal:
        row = self.store.db.execute('SELECT * FROM persona_growth_proposals WHERE proposal_id=?', (proposal_id,)).fetchone()
        ensure(row is not None, 'Growth proposal not found')
        return GrowthProposal(row['proposal_id'], row['status'], row['scope_kind'], row['scope_entity_id'], row['dimension'],
                              json.loads(row['candidate_json']), tuple(json.loads(row['evidence_event_ids_json'])))

    def review(self, proposal_id: str, *, verdict: str, rationale: str,
               reviewer_class: str = 'TRUSTED_HOST_GOVERNANCE') -> GrowthProposal:
        """Explicit host governance decision; no natural-language role claim is accepted here."""
        ensure(verdict in {'APPROVE', 'REJECT'}, 'Growth review verdict must be APPROVE or REJECT')
        ensure(isinstance(rationale, str) and 0 < len(rationale.strip()) <= 2000, 'Growth review rationale required')
        ensure(reviewer_class == 'TRUSTED_HOST_GOVERNANCE', 'Unsupported growth reviewer class')
        proposal = self.load(proposal_id)
        ensure(proposal.status == 'PENDING', 'Growth proposal already reviewed')
        review_id = 'growth_review_' + digest([proposal_id, verdict, rationale.strip(), reviewer_class])
        with self.store.transaction():
            self.store.db.execute('INSERT INTO persona_growth_reviews VALUES(?,?,?,?,?,?)',
                (review_id, proposal_id, verdict, rationale.strip(), reviewer_class, utc_now()))
            status = 'APPROVED' if verdict == 'APPROVE' else 'REJECTED'
            self.store.db.execute('UPDATE persona_growth_proposals SET status=? WHERE proposal_id=?', (status, proposal_id))
            if verdict == 'APPROVE':
                row = self.store.db.execute('SELECT * FROM persona_growth_proposals WHERE proposal_id=?', (proposal_id,)).fetchone()
                self.store.db.execute('''INSERT INTO persona_growth_versions(
                    proposal_id,scope_kind,scope_entity_id,dimension,candidate_json,evidence_event_ids_json,activated_at_utc)
                    VALUES(?,?,?,?,?,?,?)''', (proposal_id, row['scope_kind'], row['scope_entity_id'], row['dimension'],
                    row['candidate_json'], row['evidence_event_ids_json'], utc_now()))
        return self.load(proposal_id)

    def active_view(self, handle: SessionHandle) -> list[dict[str, Any]]:
        self.store._authenticate(handle)
        rows = self.store.db.execute('''SELECT * FROM persona_growth_versions
            WHERE scope_kind='GLOBAL_SELF' OR (scope_kind='ENTITY_RELATIONSHIP' AND scope_entity_id=?)
            ORDER BY version_id''', (handle.entity_id,)).fetchall()
        latest: dict[tuple[str, str | None, str], Any] = {}
        for row in rows:
            latest[(row['scope_kind'], row['scope_entity_id'], row['dimension'])] = row
        result = []
        for row in latest.values():
            candidate = json.loads(row['candidate_json'])
            result.append({'version_id': row['version_id'], 'scope_kind': row['scope_kind'],
                'scope_entity_id': row['scope_entity_id'], 'dimension': row['dimension'],
                'statement': candidate['statement'], 'conditions': candidate['conditions'], 'limits': candidate['limits'],
                'confidence': candidate['confidence'], 'evidence_event_ids': json.loads(row['evidence_event_ids_json']),
                'provenance': 'GOVERNED_RUNTIME_GROWTH_NOT_SOURCE_PERSONA',
                'genesis_mutated': False, 'model_output_is_authority': False})
        return sorted(result, key=lambda x: (x['scope_kind'], x['dimension'], x['version_id']))

    def audit(self) -> dict[str, Any]:
        proposals = self.store.db.execute('SELECT * FROM persona_growth_proposals ORDER BY created_at_utc').fetchall()
        active = self.store.db.execute('SELECT * FROM persona_growth_versions ORDER BY version_id').fetchall()
        for row in active:
            proposal = self.store.db.execute('SELECT status,candidate_json,evidence_event_ids_json FROM persona_growth_proposals WHERE proposal_id=?',
                                             (row['proposal_id'],)).fetchone()
            ensure(proposal is not None and proposal['status'] == 'APPROVED', 'Active growth version lacks approved proposal')
            ensure(proposal['candidate_json'] == row['candidate_json'] and proposal['evidence_event_ids_json'] == row['evidence_event_ids_json'],
                   'Growth version/proposal mismatch')
        return {'version': VERSION, 'proposal_count': len(proposals), 'active_version_count': len(active),
                'genesis_write_path': False, 'model_direct_write_path': False, 'integrity': 'ok'}
