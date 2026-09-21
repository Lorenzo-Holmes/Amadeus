"""Occurrence-bound evidence and non-authoritative semantic interpretations.

This module cannot admit events, write state, classify natural language, or call
a model. A quotation hash authenticates bytes, NOT the truth/meaning of words.
Raw utterances deliberately retain unresolved semantic axes. A parser may
propose an interpretation, but even a perfectly bound interpretation is not a
host receipt. Only the existing runtime verifier supplies scoped host facts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from copy import deepcopy
from reasoning_scope import surface_view, validate_reasoning, sparse_surface, INVARIANTS, unparsed_candidate_closure
from semantic_grounding import candidate_closure, responsibility_attribution

VERSION = 'CLAIM_EVIDENCE_4'
UNRESOLVED = 'UNRESOLVED'
PHASES = {'PLANNED', 'ASSIGNED', 'STARTED', 'COMPLETED', 'UNRESOLVED'}
MODALITIES = {'ASSERTED', 'CONDITIONAL', 'HYPOTHETICAL', 'POSSIBLE', 'OBSERVED', 'UNRESOLVED'}
POLARITIES = {'AFFIRMED', 'NEGATED', 'UNRESOLVED'}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _id(prefix, value):
    return prefix + hashlib.sha256(_json(value).encode('utf-8')).hexdigest()[:24]


def _require(ok, message):
    if not ok:
        raise ValueError(message)


@dataclass(frozen=True)
class EvidenceUnit:
    proposition_id: str
    origin: str
    speaker: str
    raw_text: str
    raw_sha256: str
    authority: str
    authority_scope: str
    phase: str = UNRESOLVED
    modality: str = UNRESOLVED
    condition: str = UNRESOLVED
    negation: str = UNRESOLVED
    quoted_speech: str = UNRESOLVED
    world_event_status: str = UNRESOLVED
    currentness: str = 'UNRESOLVED_NOT_ASSERTED_CURRENT_TRUTH'
    superseded_by: str | None = None


def utterance(*, entity_id: str, mode: str, turn_id: str, speaker: str, text: str) -> EvidenceUnit:
    _require(speaker in {'user', 'assistant'}, 'Unknown utterance speaker')
    _require(all(isinstance(x, str) and x for x in (entity_id, mode, turn_id)), 'Missing origin scope')
    _require(isinstance(text, str), 'Utterance must preserve text')
    origin = turn_id + '/' + speaker
    return EvidenceUnit(_id('p_', [entity_id, mode, origin]), origin, speaker, text,
        hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'USER_UTTERANCE' if speaker == 'user' else 'ASSISTANT_PRIOR_STATEMENT',
        'WORDS_ONLY_NOT_DESCRIBED_WORLD_EVENT')


def interpret(unit: EvidenceUnit, candidate: dict) -> dict:
    """Validate a proposed reading; never validate semantic entailment or truth.

    The complete enclosing quotation is always retained, including conditions
    outside the selected span. Identity is span/occurrence-based, not a semantic
    equivalence claim. Changed readings have the same proposition ID but a new
    candidate ID. Even an interpretation of host text is not itself verified.
    """
    allowed = {'span', 'quote', 'actor', 'phase', 'modality', 'condition', 'negation',
               'quoted_speech', 'reported_speaker', 'reported_addressee', 'report_type', 'proposed_relations', 'reasoning', 'grounding'}
    _require(type(candidate) is dict and set(candidate) <= allowed, 'Unsupported interpretation fields')
    span = candidate.get('span')
    _require(isinstance(span, list) and len(span) == 2 and all(type(x) is int for x in span), 'Invalid quote span')
    start, end = span
    _require(0 <= start < end <= len(unit.raw_text), 'Quote span outside evidence')
    _require(candidate.get('quote') == unit.raw_text[start:end], 'Quote does not match original evidence')
    values = {k: candidate.get(k, UNRESOLVED) for k in
              ('actor', 'phase', 'modality', 'condition', 'negation', 'quoted_speech', 'reported_speaker', 'reported_addressee', 'report_type')}
    _require(values['phase'] in PHASES, 'Invalid phase')
    _require(values['modality'] in MODALITIES, 'Invalid modality')
    _require(values['negation'] in POLARITIES, 'Invalid negation')
    _require(values['quoted_speech'] in {'QUOTED', 'NOT_QUOTED', UNRESOLVED}, 'Invalid quotation state')
    _require(values['report_type'] in {'SELF_REPORT', 'THIRD_PARTY_REPORT', 'PROPOSAL', 'QUESTION', UNRESOLVED}, 'Invalid report type')
    _require(all(isinstance(v, str) and 0 < len(v) <= 4000 for v in values.values()), 'Invalid semantic facet')
    relations = candidate.get('proposed_relations', [])
    _require(isinstance(relations, list) and len(relations) <= 12, 'Invalid proposed relations')
    for relation in relations:
        _require(type(relation) is dict and set(relation) == {'kind', 'target_proposition_id'}, 'Invalid relation fields')
        _require(relation['kind'] in {'SAME_PROPOSITION', 'CONTRADICTS', 'SUPPORTS', 'EXCLUDES'}, 'Invalid relation kind')
        _require(isinstance(relation['target_proposition_id'], str) and
                 0 < len(relation['target_proposition_id']) <= 100, 'Invalid relation target')
    proposition_id = unit.proposition_id if span == [0, len(unit.raw_text)] else _id('p_', [unit.proposition_id, span])
    grounded = describe_grounding({'units': [asdict(unit)]}, candidate.get('grounding', []))
    return {'candidate_id': _id('i_', [unit.proposition_id, unit.raw_sha256, candidate]),
        'proposition_id': proposition_id, 'parent_proposition_id': unit.proposition_id,
        'speaker': unit.speaker, 'enclosing_evidence': asdict(unit), 'span': list(span),
        'proposition': candidate['quote'], 'interpretation': values,
        'reasoning': validate_reasoning(candidate.get('reasoning', {})),
        'grounded_descriptions': grounded['grounded_descriptions'],
        'proposed_relations': json.loads(_json(relations)),
        'relations_admitted': False, 'authority': 'NONE_INTERPRETATION_ONLY',
        'world_event_status': UNRESOLVED, 'admission_eligible': False,
        'validation': 'STRUCTURAL_QUOTE_BINDING_ONLY_NOT_SEMANTIC_ENTAILMENT'}


def describe_grounding(graph, proposals):
    """Read-only typed proposals; source binding never admits a semantic fact."""
    _require(type(proposals) is list and len(proposals) <= 16, 'Invalid grounding proposals')
    result = deepcopy(graph)
    descriptions = []
    for p in proposals:
        _require(type(p) is dict and set(p) == {'kind', 'description'}, 'Invalid grounding proposal')
        _require(p['kind'] in {'CANDIDATE_CLOSURE', 'RESPONSIBILITY'}, 'Invalid grounding kind')
        validator = candidate_closure if p['kind'] == 'CANDIDATE_CLOSURE' else responsibility_attribution
        descriptions.append({'kind': p['kind'], 'description': validator(p['description'], graph['units'])})
    result['grounded_descriptions'] = descriptions
    result['projection_grants_authority'] = False
    return result


def build_graph(*, entity_id, mode, current, history, retrieval,
                observation=None, source_memory=None, trusted_runtime=False):
    """Bind exactly the selected prompt data, not omitted transcript/trace data.

    ``trusted_runtime`` is supplied by context_router's exact built-in provider
    identity check after verification, never taken from a record's text/fields.
    The graph itself is a read-only description, not an admission capability.
    """
    units, locations = [], []

    def add(unit, path):
        row = asdict(unit)
        if unit.authority in {'USER_UTTERANCE', 'ASSISTANT_PRIOR_STATEMENT', 'CORRECTED_USER_REPORT'}:
            row['reasoning_scope'] = surface_view(unit.raw_text, unit.speaker)
        # A collision must not relabel a different quote with one identity.
        same = next((x for x in units if x['proposition_id'] == unit.proposition_id), None)
        _require(same is None or same == row, 'Evidence identity collision')
        if same is None:
            units.append(row)
        locations.append({'proposition_id': unit.proposition_id, 'path': path})

    def say(turn_id, speaker, text, path):
        add(utterance(entity_id=entity_id, mode=mode, turn_id=turn_id, speaker=speaker, text=text), path)

    say(current['turn_id'], 'user', current['user_text'], 'current/user')
    for i, row in enumerate(history):
        say(row['turn_id'], 'user', row['user_text'], f'history/{i}/user')
        if row['status'] == 'DISPLAYED' and row.get('assistant_text') is not None:
            say(row['turn_id'], 'assistant', row['assistant_text'], f'history/{i}/assistant')

    def record(origin, speaker, text, authority, scope, path, **facets):
        raw = text if isinstance(text, str) else _json(text)
        unit = EvidenceUnit(_id('p_', [entity_id, mode, origin]), origin, speaker, raw,
            hashlib.sha256(raw.encode('utf-8')).hexdigest(), authority, scope, **facets)
        add(unit, path)
        return unit.proposition_id

    for i, row in enumerate(retrieval):
        kind, rid = row.get('record_kind'), row['record_id']
        if kind == 'UTTERANCE_OBSERVED' and not row.get('content_truncated'):
            # A custom provider's asserted origin is not an authenticated join.
            origin = row.get('source_turn_id') if trusted_runtime else None
            origin = origin or 'unverified-retrieval:' + rid
            say(origin, 'user', row['content'], f'retrieval/{i}/content')
            if row.get('assistant_utterance') is not None and not row.get('assistant_content_truncated'):
                say(origin, 'assistant', row['assistant_utterance'], f'retrieval/{i}/assistant_utterance')
        else:
            authority = 'UNVERIFIED_RETRIEVAL'
            if trusted_runtime and kind == 'FACT_CORRECTED':
                record('correction:' + rid, 'user', row['content'], 'CORRECTED_USER_REPORT',
                       'USER_REPORT_NOT_EXTERNAL_TRUTH', f'retrieval/{i}/content',
                       currentness='CURRENT_ADMITTED_USER_REPORT')
                continue
            elif trusted_runtime and kind == 'FROZEN_SOURCE':
                authority = row['provenance']
            elif trusted_runtime and kind == 'COMMITMENT':
                authority = 'HOST_VERIFIED_AGREEMENT_TITLE'
            record('retrieval:' + rid, 'source' if kind == 'FROZEN_SOURCE' else 'host' if kind == 'COMMITMENT' and trusted_runtime else 'user',
                   row['content'], authority, row.get('admitted_scope', UNRESOLVED)
                   if trusted_runtime else 'UNVERIFIED_PROVIDER_DATA', f'retrieval/{i}/content')

    # These structured facts originate in already verified host state, not in a
    # classifier interpreting free text. Completion is ONLY a local text receipt.
    observation = observation if trusted_runtime and mode == 'PRODUCT_RUNTIME' else None
    host_values, replacements = [], []
    agreements = list((observation or {}).get('commitments', []))
    corrections = list((observation or {}).get('current_corrections', []))
    # A bounded host summary is not an exhaustive authority inventory. Verified
    # retrieved records retain their own receipt/lineage even outside that list.
    if trusted_runtime and mode == 'PRODUCT_RUNTIME':
        for row in retrieval:
            if row.get('record_kind') == 'COMMITMENT' and row['record_id'] not in {r['commitment_id'] for r in agreements}:
                agreements.append(dict(row, commitment_id=row['record_id']))
            elif row.get('record_kind') == 'FACT_CORRECTED' and row['record_id'] not in {r['event_id'] for r in corrections}:
                corrections.append(dict(row, event_id=row['record_id'], current_user_statement=row['content'],
                                        superseded_event_ids=row.get('supersedes', [])))
    for row in agreements:
        exact = row.get('verification_scope') == 'EXACT_USER_TEXT_ONLY_NOT_EXTERNAL_WORK'
        terminal = row['status'] == 'FULFILLED' and bool(row.get('closed_event_id')) and exact
        value = {'kind': 'TEXT_AGREEMENT', 'name': row['content'], 'status': row['status'],
                 'scope': row.get('verification_scope', UNRESOLVED),
                 'actor': row.get('submission_actor', UNRESOLVED),
                 'event_id': row.get('closed_event_id') or row.get('opened_event_id')}
        host_values.append(value)
        record('agreement:' + row['commitment_id'], 'host', value, 'HOST_VERIFIED_EVENT',
               'TEXT_SUBMISSION_ONLY_NOT_EXTERNAL_WORK' if exact else 'AGREEMENT_STATE_ONLY',
               f'host_facts/{len(host_values)-1}', phase='COMPLETED' if terminal else UNRESOLVED,
               modality='OBSERVED', condition='HOST_VERIFIER_SCOPE', negation='AFFIRMED', quoted_speech='NOT_QUOTED',
               currentness='CURRENT_HOST_STATE')
    for row in corrections:
        value = {'kind': 'CORRECTED_USER_REPORT', 'text': row['current_user_statement'],
                 'event_id': row['event_id'], 'supersedes_event_ids': row['superseded_event_ids']}
        host_values.append(value)
        latest = record('correction:' + row['event_id'], 'user', row['current_user_statement'],
               'CORRECTED_USER_REPORT', 'USER_REPORT_NOT_EXTERNAL_TRUTH',
               f'host_facts/{len(host_values)-1}/text', currentness='CURRENT_ADMITTED_USER_REPORT')
        for old in row.get('superseded_origins', []):
            origin = old['source_turn_id'] + '/user' if old['event_type'] == 'UTTERANCE_OBSERVED' else 'correction:' + old['event_id']
            old_id = _id('p_', [entity_id, mode, origin])
            replacements.append({'old': old_id, 'current': latest, 'basis': 'HOST_VERIFIED_CORRECTION_LINEAGE'})
            for unit in units:
                if unit['proposition_id'] == old_id:
                    unit.update(currentness='SUPERSEDED_REPORT_HISTORY_ONLY', superseded_by=latest)
        # The correction command itself remains an utterance, not atomic truth.
    for group in ('ENCODED_SOURCE_MEMORY', 'SOURCE_FACT_ONLY', 'HOLD'):
        for i, value in enumerate((source_memory or {}).get(group, [])):
            record('source:' + str((source_memory or {}).get('source_snapshot_id')) + ':' + group + ':' + str(i),
                   'source', value, group, 'EXISTING_FROZEN_NARRATION_SCOPE_ONLY', f'source_memory/{group}/{i}')
    return {'version': VERSION, 'units': units, 'locations': locations, 'host_facts': host_values,
            'replacements': replacements, 'interpretations': [],
            'semantic_parser_applied': False, 'projection_grants_authority': False,
            'identity_semantics': 'OCCURRENCE_AND_SPAN_NOT_AUTOMATIC_SEMANTIC_EQUIVALENCE',
            'coverage': 'SELECTED_EVIDENCE_ONLY_NOT_EXHAUSTIVE'}


def prompt_projection(graph):
    """Sparse reference table: no duplicate dialogue text or guessed parsing."""
    by = {u['proposition_id']: u for u in graph['units']}
    groups = {}
    for location in graph['locations']:
        unit = by[location['proposition_id']]
        row = [unit['proposition_id'], location['path']]
        if unit['currentness'] != 'UNRESOLVED_NOT_ASSERTED_CURRENT_TRUTH' or unit['phase'] != UNRESOLVED:
            row.append({'phase': unit['phase'], 'currentness': unit['currentness']})
        groups.setdefault((unit['speaker'], unit['authority']), []).append(row)
    result = {'version': VERSION, 'columns': ['id', 'location', 'known_facets'],
        'group_columns': ['speaker', 'authority', 'rows'],
        'unresolved_facets': ['phase', 'modality', 'condition', 'negation', 'quoted_speech', 'world_event_status'],
        'evidence': [[speaker, authority, rows] for (speaker, authority), rows in groups.items()],
        'coverage': 'SELECTED_EVIDENCE_ONLY_NOT_EXHAUSTIVE'}
    if graph['host_facts']:
        result['host_facts'] = graph['host_facts']
    if graph['replacements']:
        result['replacements'] = graph['replacements']
    result['reasoning_invariants'] = deepcopy(INVARIANTS)
    # Present even without lexical cues. These are explicit unresolved data,
    # not a parser's invented candidate inventory or a host closure receipt.
    result['candidate_closure'] = unparsed_candidate_closure()
    result['reasoning_scopes'] = [[u['proposition_id'], view] for u in graph['units']
        if 'reasoning_scope' in u and (view := sparse_surface(u['reasoning_scope']))]
    return result


def evidence_message(graph):
    return {'role': 'user', 'content':
        '只读陈述索引：text≠truth; lexical markers; scoped host_facts; no admission.\n' + _json(prompt_projection(graph))}
