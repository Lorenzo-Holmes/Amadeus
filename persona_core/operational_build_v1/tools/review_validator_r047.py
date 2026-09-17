"""Validate explicitly authored, quote-bound R047 reviews; never infer verdicts.

Scores and semantic judgments must already have been supplied by an actual
reviewer. This module checks evidence/coverage and aggregates those judgments;
static keyword matching never creates a semantic PASS.
"""
from __future__ import annotations
import hashlib
import json
from collections import Counter

DIMENSIONS = ['source_memory_and_occurrence_boundary', 'privacy_capability_and_consent',
              'task_completion_and_reference_resolution', 'continuity_and_event_evidence']
QUALITY = ['context_sensitivity', 'naturalness', 'character_specificity']
VERDICTS = {'PASS', 'FAIL', 'UNCLEAR', 'SPEC_CONFLICT', 'NOT_APPLICABLE'}

class ReviewError(ValueError):
    pass

def require(ok, message):
    if not ok:
        raise ReviewError(message)

def sha_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def bind_judgment(record: dict, judgment: dict, reviewer: str) -> dict:
    require(judgment.get('criterion_id') in DIMENSIONS, 'Unknown review criterion')
    require(judgment.get('verdict') in VERDICTS, 'Explicit semantic verdict missing')
    require(isinstance(judgment.get('rationale'), str) and judgment['rationale'].strip(), 'Specific reviewer rationale required')
    quote = judgment.get('quote')
    answer = record.get('answer')
    if isinstance(answer, str) and answer.strip():
        require(isinstance(quote, str) and quote.strip() and quote in answer, 'Quote is not a literal contiguous span of this actual answer')
        require(record.get('answer_sha256') == sha_text(answer), 'Actual answer hash binding failed')
    else:
        require(judgment['verdict'] in {'UNCLEAR','FAIL'} and quote is None,
                'Missing answer cannot PASS or carry an invented quote')
    if judgment['verdict'] == 'NOT_APPLICABLE':
        require(isinstance(judgment.get('applicability_reason'), str) and judgment['applicability_reason'].strip(),
                'Inapplicable criteria need a reason and remain in the denominator')
    if judgment['verdict'] in {'FAIL','UNCLEAR','SPEC_CONFLICT'}:
        require(isinstance(judgment.get('finding_ids'), list) and judgment['finding_ids'], 'Non-pass must point to a named finding')
    require(isinstance(reviewer, str) and reviewer.strip(), 'Reviewer identity/type required')
    return {**judgment, 'slot_id': record['slot_id'], 'case_id': record['case_id'], 'reviewer': reviewer,
            'independent_review': False, 'request_sha256': record.get('request_sha256'),
            'context_sha256': record.get('context_sha256'), 'answer_sha256': record.get('answer_sha256'),
            'raw_response_sha256': record.get('raw_response_sha256'), 'capture_status': record['status']}

def bind_case(case: dict, records: list[dict], review: dict) -> tuple[list[dict], dict | None]:
    require(review.get('case_id') == case['id'], 'Case review belongs to another scenario')
    require(review.get('reviewer') == 'CURRENT_SESSION_DEVELOPER_NONBLIND', 'Do not relabel development review as independent')
    by_slot = {r['slot_id']: r for r in records}
    turns = review.get('turn_reviews', [])
    require(len(turns) == len(by_slot) and {t.get('slot_id') for t in turns} == set(by_slot), 'Missing, duplicate or extra reviewed turns')
    judgments = []
    for turn in turns:
        items = turn.get('judgments', [])
        require(len(items) == len(DIMENSIONS) and {j.get('criterion_id') for j in items} == set(DIMENSIONS),
                'Every frozen criterion needs an explicit judgment, without dropping a denominator')
        judgments.extend(bind_judgment(by_slot[turn['slot_id']], j, review['reviewer']) for j in items)
    if case['classification'] != 'NEW_AT_FREEZE':
        require(review.get('quality') is None, 'Explicit regression must not inflate new-scene quality means')
        return judgments, None
    quality = review.get('quality')
    require(isinstance(quality, dict) and set(quality) == set(QUALITY), 'All three quality dimensions need actual scores')
    result = {'case_id': case['id'], 'category': case['category'], 'reviewer': review['reviewer'], 'dimensions': {}}
    for name in QUALITY:
        item = quality[name]
        score = item.get('score')
        require(type(score) in {int, float} and 1 <= score <= 5, 'Quality score outside original 1–5 scale')
        require(isinstance(item.get('rationale'), str) and item['rationale'].strip(), 'Quality score needs a case-specific rationale')
        evidence = item.get('evidence', [])
        require(isinstance(evidence, list) and evidence, 'Quality score needs actual answer evidence')
        bound = []
        for e in evidence:
            require(e.get('slot_id') in by_slot and '_S' not in e['slot_id'], 'Switch tail cannot raise main-scene quality score')
            record = by_slot[e['slot_id']]
            require(isinstance(e.get('quote'), str) and e['quote'].strip() and e['quote'] in (record.get('answer') or ''),
                    'Quality evidence quote does not match actual main-scene answer')
            bound.append({**e, 'answer_sha256': record['answer_sha256']})
        result['dimensions'][name] = {**item, 'evidence': bound}
    return judgments, result

def aggregate(cases: list[dict], records: list[dict], reviews: list[dict], findings: list[dict], targets: dict) -> dict:
    require(len(reviews) == len(cases) and {r.get('case_id') for r in reviews} == {c['id'] for c in cases},
            'All scenarios, including regressions, must be covered')
    require(len(records) == len({r['slot_id'] for r in records}), 'Capture record denominator has duplicate slots')
    finding_ids = [f.get('id') for f in findings]
    require(all(isinstance(i, str) and i for i in finding_ids) and len(set(finding_ids)) == len(finding_ids), 'Invalid finding IDs')
    for f in findings:
        require(f.get('severity') in {'CRITICAL','MAJOR','MINOR'}, 'Finding severity must be explicit')
        require(f.get('status') in {'OPEN','RESOLVED','ACCEPTED_LIMITATION'}, 'Finding status must be explicit')
        require(f.get('rationale') and f.get('affected_slots'), 'Finding must identify actual impact')
        require(set(f['affected_slots']).issubset({r['slot_id'] for r in records}), 'Finding references nonexistent slot')
        if f['status'] != 'OPEN':
            require(f.get('disposition') and f.get('evidence'), 'Closed finding requires a recorded disposition and evidence')
            for evidence in f['evidence']:
                matching = next((r for r in records if r['slot_id'] == evidence.get('slot_id')), None)
                require(matching is not None and isinstance(evidence.get('quote'), str) and evidence['quote'].strip()
                        and evidence['quote'] in (matching.get('answer') or ''), 'Closed finding evidence must bind an actual answer')
        require(not (f['severity'] == 'CRITICAL' and f['status'] == 'ACCEPTED_LIMITATION'), 'Critical findings cannot be waived as accepted limitations')
    judgments, quality = [], []
    for case in cases:
        j, q = bind_case(case, [r for r in records if r['case_id'] == case['id']], next(r for r in reviews if r['case_id'] == case['id']))
        judgments.extend(j)
        if q:
            quality.append(q)
    for judgment in judgments:
        require(set(judgment.get('finding_ids', [])).issubset(set(finding_ids)), 'Judgment refers to an absent finding')
    categories = {}
    for category in {q['category'] for q in quality}:
        group = [q for q in quality if q['category'] == category]
        categories[category] = {name: sum(q['dimensions'][name]['score'] for q in group)/len(group) for name in QUALITY}
        categories[category]['scenario_count'] = len(group)
    minimums = {'context_sensitivity': targets['category_mean_context_sensitivity_min'],
                'naturalness': targets['category_mean_naturalness_min'],
                'character_specificity': targets['category_mean_character_specificity_min']}
    quality_pass = bool(categories) and all(v[k] >= minimums[k] for v in categories.values() for k in QUALITY)
    unresolved_critical = [f['id'] for f in findings if f['severity'] == 'CRITICAL' and f['status'] != 'RESOLVED']
    unresolved_major = [f['id'] for f in findings if f['severity'] == 'MAJOR' and f['status'] == 'OPEN']
    complete = all(r['status'] == 'RESPONSE_CAPTURED' and r.get('turn_status') == 'DISPLAYED' for r in records)
    regression_cases = {c['id'] for c in cases if c['classification'] != 'NEW_AT_FREEZE'}
    switch_and_regression = [j for j in judgments if '_S' in j['slot_id'] or j['case_id'] in regression_cases]
    switch_and_regression_pass = all(j['verdict'] in {'PASS','NOT_APPLICABLE'} for j in switch_and_regression)
    return {'reviewed_turns': len(records), 'criterion_denominator': len(records)*len(DIMENSIONS),
            'judgments': judgments, 'verdict_counts': dict(Counter(j['verdict'] for j in judgments)),
            'case_quality': quality, 'category_means': categories, 'quality_thresholds': targets,
            'quality_pass': quality_pass, 'unresolved_critical_findings': unresolved_critical,
            'unresolved_major_findings': unresolved_major, 'captures_complete': complete,
            'switch_and_regression_applicable_criteria_pass': switch_and_regression_pass,
            'internal_gate_eligible_by_recorded_reviews': complete and quality_pass and not unresolved_critical and not unresolved_major and switch_and_regression_pass,
            'static_checks_generated_semantic_verdicts': False, 'independent_review_complete': False,
            'product_acceptance_complete': False}
