"""Read-only, entity-scoped evidence views for expression, never admission.

The prompt is built before this turn is displayed/observed. Current input can
therefore match pinned text without constituting a committed receipt. No method
here issues evidence, decides a candidate, mutates runtime state, or calls a model.
"""
from __future__ import annotations
import hashlib
import json
import re
from dialogue_admission import PROPOSAL, CONFIRM, CORRECTION
from transcript_store import ensure

VERSION = 'HOST_STATE_EXPRESSION_47_1'

def agreement_view(runtime, handle, commitment):
    """Derive verifier semantics, including unresolved legacy acceptance text."""
    ensure(commitment['entity_id'] == handle.entity_id, 'Agreement outside current entity')
    proposal = runtime.controller._turn(handle, commitment['proposal_turn_id'])
    match = re.search(r'验收内容[：:]([^；;\r\n]+)', proposal['user_text'])
    requirement = match.group(1).strip() if match else None
    if requirement is not None and hashlib.sha256(requirement.encode('utf-8')).hexdigest() != commitment['expected_text_sha256']:
        requirement = None
    exact_user_policy = commitment['verification_policy'] == 'EXACT_USER_TEXT_V1'
    view = {'commitment_id': commitment['commitment_id'], 'content': commitment['text'],
        'status': commitment['status'], 'submission_actor': 'CURRENT_USER' if exact_user_policy else 'UNKNOWN',
        'assistant_role': 'AGREEMENT_COUNTERPART_NOT_SUBMITTER' if exact_user_policy else 'UNKNOWN',
        'agreed_submission_requirement': requirement,
        'requirement_evidence_turn_id': commitment['proposal_turn_id'],
        'requirement_evidence_status': 'HASH_BOUND_ORIGINAL_USER_TERMS' if requirement is not None else 'NOT_RESOLVED_DO_NOT_GUESS',
        'verification_scope': 'EXACT_USER_TEXT_ONLY_NOT_EXTERNAL_WORK' if exact_user_policy else 'UNKNOWN',
        'assistant_added_conditions_are_binding': False,
        'opened_event_id': commitment['opened_event_id'], 'closed_event_id': commitment['closed_event_id']}
    if commitment['status'] == 'FULFILLED':
        closing = runtime.get_event(handle, commitment['closed_event_id'])
        view['verified_submission_turn_id'] = closing['payload']['submission_turn_id']
        view['fulfilled_means'] = 'USER_TEXT_SUBMISSION_VERIFIED_NOT_ASSISTANT_WORK_OR_EXTERNAL_COMPLETION'
    return view

def expression_observation(runtime, handle, current, *, limit=6):
    """Read only; stale/missing evidence fails through the existing verifier."""
    runtime.store._authenticate(handle)
    ensure(type(limit) is int and 1 <= limit <= 12, 'Invalid expression view limit')
    runtime.verify()
    bound = runtime.store.get_turn(handle, current['turn_id'])
    ensure(bound['user_text'] == current['user_text'] and bound['seq'] == current['seq'], 'Current input binding mismatch')
    base = {'version': VERSION, 'scope': 'CURRENT_ENTITY_AND_MODE_ONLY',
        'projection_grants_authority': False, 'current_input_is_committed_evidence': False,
        'current_turn_id': current['turn_id'], 'current_input_kind': 'ORDINARY_UNADMITTED_INPUT',
        'ordinary_requests_replace_admitted_state': False, 'commitments': [], 'current_corrections': []}
    if handle.mode != 'PRODUCT_RUNTIME':
        base['scope'] = 'NON_RUNTIME_MODE_NO_PRODUCT_STATE_PROJECTION'
        return base
    snapshot = runtime.snapshot(handle)
    text = current['user_text']
    proposal = PROPOSAL.fullmatch(text.strip())
    confirmation = CONFIRM.fullmatch(text.strip())
    correction = CORRECTION.fullmatch(text.strip())
    if proposal:
        base.update(current_input_kind='PROPOSAL_ONLY_NOT_CONFIRMED', proposed_user_submission={
            'content': proposal.group(1).strip(), 'acceptance_text': proposal.group(2).strip(),
            'submission_actor': 'CURRENT_USER', 'state_effect': 'NONE_PENDING_MUTUAL_AGREEMENT'})
    elif confirmation:
        base['current_input_kind'] = 'CONFIRMATION_TEXT_PENDING_OBSERVATION'
    elif correction:
        base['current_input_kind'] = 'CORRECTION_TEXT_PENDING_ADMISSION'
    # Mirror only the verifier's observable predicates, not its side effects.
    actual = hashlib.sha256(text.encode('utf-8')).hexdigest()
    matches = [c for c in snapshot['commitments'].values()
               if c['status'] == 'OPEN' and c['expected_text_sha256'] == actual]
    eligible = [c for c in matches if current['seq'] > runtime.controller._turn(handle, c['confirmation_turn_id'])['seq']]
    base['current_text_submission_check'] = {
        'matching_open_commitment_ids': [c['commitment_id'] for c in matches],
        'unique_exact_match_after_confirmation': len(matches) == 1 and len(eligible) == 1,
        'workflow_branch_allows_submission': not (proposal or confirmation or correction),
        'receipt_committed': False, 'external_work_proven': False,
        'meaning': 'CURRENT_INPUT_COMPARISON_ONLY_PENDING_DISPLAY_AND_HOST_OBSERVATION'}
    # Prioritize current exact matches, then relevant agreement titles, then latest.
    from retrieval import terms
    query_terms = terms(text)
    agreements = list(snapshot['commitments'].values())
    agreements.sort(key=lambda c: (c in matches, len(query_terms & terms(c['text'])),
        runtime.get_event(handle, c['closed_event_id'] or c['opened_event_id'])['sequence']), reverse=True)
    base['commitments'] = [agreement_view(runtime, handle, c) for c in agreements[:limit]]
    base['omitted_commitment_count'] = max(0, len(agreements)-limit)
    documents = {r['event_id']: dict(r) for r in runtime.store.db.execute(
        'SELECT * FROM retrieval_documents WHERE entity_id=?', (handle.entity_id,))}
    corrections = []
    for doc in documents.values():
        if doc['event_type'] != 'FACT_CORRECTED' or doc['superseded_by'] is not None:
            continue
        event = runtime.get_event(handle, doc['event_id'])
        if event['mode'] != handle.mode:
            continue
        previous, old_ids, old_texts, old_origins = event, [], [], []
        while previous['event_type'] == 'FACT_CORRECTED':
            old_id = previous['payload']['supersedes_event_id']
            ensure(old_id in documents and old_id not in old_ids, 'Invalid correction chain')
            old_ids.append(old_id)
            old_texts.append(documents[old_id]['text_content'])
            previous = runtime.get_event(handle, old_id)
            old_origins.append({'event_id': old_id, 'event_type': previous['event_type'],
                                'source_turn_id': previous['payload'].get('turn_id')})
        view = {'event_id': event['event_id'], 'current_user_statement': doc['text_content'],
            'admitted_scope': 'CORRECTED_USER_STATEMENT_NOT_EXTERNAL_TRUTH',
            'superseded_event_ids': old_ids, 'superseded_origins': old_origins,
            'source_turn_id': event['payload']['turn_id'],
            'original_statement_for_topic_only': old_texts[-1],
            'old_statement_is_current': False, 'later_ordinary_requests_override': False}
        score = len(query_terms & terms(doc['text_content'] + ' '.join(old_texts)))
        corrections.append((score, event['sequence'], view))
    corrections.sort(key=lambda row: (row[0], row[1]), reverse=True)
    base['current_corrections'] = [row[2] for row in corrections[:limit]]
    base['omitted_correction_count'] = max(0, len(corrections)-limit)
    return base
