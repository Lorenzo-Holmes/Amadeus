"""Entity-filtered, provenance-preserving retrieval from verified runtime data.

No external embeddings, hidden model call, or summary-as-authority. Chinese
bigrams and ASCII terms rank already-authorized records deterministically.
Corrections and commitment state are resolved BEFORE anything enters a prompt.
"""
from __future__ import annotations
import json
import re
from context_router import _load_frozen, _source_language_glosses
from runtime_store import RuntimeStore
from transcript_store import TranscriptStore, SessionHandle, ensure

VERSION = 'RETRIEVAL_FULL_EVIDENCE_1'

def terms(text: str) -> set[str]:
    result = set(re.findall(r'[a-z0-9_]+', text.casefold()))
    for segment in re.findall(r'[\u3400-\u9fff]+', text):
        result.update(segment[i:i+2] for i in range(len(segment)-1))
    return result

class RetrievalService:
    def __init__(self, runtime: RuntimeStore, growth=None):
        self.runtime = runtime
        self.growth = growth

    def search(self, handle: SessionHandle, query: str, *, limit: int = 6, include_source: bool = True) -> list[dict]:
        store = self.runtime.store
        store._authenticate(handle)
        ensure(isinstance(query, str) and 0 < len(query) <= 12000, 'Invalid retrieval query')
        ensure(type(limit) is int and 1 <= limit <= 12, 'Invalid retrieval limit')
        # A corrupted index must not be allowed to launder invented facts into context.
        self.runtime.verify()
        query_terms = terms(query)
        docs = [dict(r) for r in store.db.execute('SELECT * FROM retrieval_documents WHERE entity_id=? ORDER BY sequence', (handle.entity_id,))]
        by_id = {d['event_id']: d for d in docs}
        snapshot = self.runtime.snapshot(handle)
        candidates = []
        seen_commitments = set()
        generic_commitment = re.search('约定|承诺|履约|提交|完成', query) is not None
        for doc in docs:
            if doc['superseded_by'] is not None:
                continue
            event = self.runtime.get_event(handle, doc['event_id'])
            if event['mode'] != handle.mode:
                continue
            payload = event['payload']
            content = doc['text_content']
            aliases = []
            previous = event
            chain = []
            chain_origins = []
            while previous['event_type'] == 'FACT_CORRECTED':
                old_id = previous['payload']['supersedes_event_id']
                ensure(old_id in by_id and old_id not in chain, 'Invalid correction chain')
                aliases.append(by_id[old_id]['text_content'])
                chain.append(old_id)
                previous = self.runtime.get_event(handle, old_id)
                chain_origins.append({'event_id': old_id, 'event_type': previous['event_type'],
                                      'source_turn_id': previous['payload'].get('turn_id')})
            rank_terms = terms(content + ' ' + ' '.join(aliases))
            overlap = sorted(query_terms.intersection(rank_terms))
            score = len(overlap)
            if event['event_type'] in {'COMMITMENT_OPEN', 'COMMITMENT_FULFILLED'}:
                cid = payload['commitment_id']
                if cid in seen_commitments:
                    continue
                commitment = snapshot['commitments'][cid]
                score = len(query_terms.intersection(terms(commitment['text']))) + (5 if generic_commitment else 0)
                if score == 0:
                    continue
                seen_commitments.add(cid)
                from state_projection import agreement_view
                agreement = agreement_view(self.runtime, handle, commitment)
                record = {'record_id': cid, 'record_kind': 'COMMITMENT', 'entity_id': handle.entity_id,
                    'content': commitment['text'], 'status': commitment['status'], 'provenance': 'PRODUCT_RUNTIME',
                    **agreement,
                    'admitted_scope': 'VERIFIED_TEXT_SUBMISSION_ONLY' if commitment['status'] == 'FULFILLED' else 'MUTUAL_TEXT_AGREEMENT_NOT_FULFILLMENT',
                    'event_ids': [i for i in [commitment['opened_event_id'], commitment['closed_event_id']] if i],
                    'first_person_scope': 'CURRENT_RUNTIME_AGREEMENT_ONLY', 'superseded': False}
            else:
                if score == 0:
                    continue
                record = {'record_id': event['event_id'], 'record_kind': event['event_type'], 'entity_id': handle.entity_id,
                    'content': content, 'content_truncated': False, 'provenance': doc['provenance'],
                    'admitted_scope': doc['admitted_scope'], 'event_ids': [event['event_id']],
                    'superseded_event_ids': chain, 'superseded': False, 'first_person_scope': 'RECORD_SCOPE_ONLY_NOT_DESCRIBED_WORLD_EVENTS'}
                if event['event_type'] == 'UTTERANCE_OBSERVED':
                    record['source_turn_id'] = payload.get('turn_id')
                    record['assistant_utterance'] = payload.get('assistant_text', '')
                    record['assistant_content_truncated'] = False
                    record['assistant_utterance_is_fact_authority'] = False
                if chain:
                    record['source_turn_id'] = payload.get('turn_id')
                    record['superseded_origins'] = chain_origins
                    score += 3
            record['ranking_reason'] = {'method': 'AUTHORIZED_RECORD_TERM_OVERLAP', 'matching_terms': overlap[:16],
                                         'resolved_corrections_before_ranking': True, 'version': VERSION}
            candidates.append((score, event['sequence'], record))
        candidates.sort(key=lambda item: (-item[0], -item[1], item[2]['record_id']))
        results = [item[2] for item in candidates[:limit]]
        if include_source and re.search('记忆|记得|来源|真帆|冈部|账号|童年|2010|三月', query):
            genesis, _ = _load_frozen(store)
            groups = [('encoded_autobiographical_memory', 'ENCODED_SOURCE_MEMORY'),
                      ('source_fact_only_not_first_person_memory', 'SOURCE_FACT_ONLY'),
                      ('claim_level_holds', 'HOLD')]
            source_records = []
            for key, provenance in groups:
                values = genesis[key]
                values = values if isinstance(values, list) else [values]
                for index, value in enumerate(values):
                    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
                    overlap = len(query_terms.intersection(terms(text)))
                    if overlap or ('来源' in query or '记忆' in query):
                        source_records.append((overlap, {'record_id': key + ':' + str(index), 'record_kind': 'FROZEN_SOURCE',
                            'entity_id': None, 'shared_source_not_another_user': True, 'content': value,
                            'provenance': provenance, 'admitted_scope': provenance, 'first_person_scope':
                            'ENCODED_SOURCE_MEMORY_ONLY' if provenance == 'ENCODED_SOURCE_MEMORY' else 'NOT_FIRST_PERSON_AUTOBIOGRAPHY',
                            'source_snapshot_id': genesis['source_snapshot_id'], 'superseded': False,
                            'hold_means_absence': False,
                            'source_language_glosses': _source_language_glosses([value]) if provenance == 'SOURCE_FACT_ONLY' else []}))
            source_records.sort(key=lambda item: (-item[0], item[1]['record_id']))
            results.extend(item[1] for item in source_records[:max(0, limit-len(results))])
        return results

    def __call__(self, store: TranscriptStore, handle: SessionHandle, query: str) -> list[dict]:
        ensure(store is self.runtime.store, 'Retrieval database and conversation mismatch')
        return self.search(handle, query)

    def memory_capability(self, store: TranscriptStore, handle: SessionHandle) -> dict:
        """Authenticated implementation facts, distinct from any query result.

        Context building has already verified the store while retrieving. This
        description grants no authority and does not need another full replay.
        """
        ensure(store is self.runtime.store, 'Retrieval database and conversation mismatch')
        store._authenticate(handle)
        return {
            'status': 'AVAILABLE', 'retrieval_provider_attached': True,
            'scope': {'entity_id': handle.entity_id, 'mode': handle.mode},
            'record_scope': 'RECORDED_UTTERANCES_AND_ADMITTED_RUNTIME_EVENTS',
            'same_entity_mode_across_sessions': True, 'after_store_reopen': True,
            'retrieval_coverage': 'BOUNDED_RELEVANCE_SEARCH_OF_THIS_PERSISTENT_STORE',
            'empty_result_proves_no_records': False, 'all_future_recall_guaranteed': False,
            'current_input_recording': 'NOT_IMPLIED_BY_CAPABILITY',
            'described_world_events_verified_by_utterance': False,
            'source_memory': 'SEPARATE_FROZEN_SOURCE_PROVENANCE',
            'external_tools_or_cross_entity_access': False, 'scheduled_reminders': False,
        }

    def context_state(self, handle: SessionHandle) -> dict:
        return {'state': self.runtime.snapshot(handle),
                'governed_growth': self.growth.active_view(handle) if self.growth is not None else [],
                'scope': 'CURRENT_ENTITY_DERIVED_STATE',
                'retrieval_absence_means_never_happened': False,
                'numbers_are_engineering_parameters_not_persona_facts': True}

    def context_observation(self, handle: SessionHandle, current: dict) -> dict:
        from state_projection import expression_observation
        return expression_observation(self.runtime, handle, current)
