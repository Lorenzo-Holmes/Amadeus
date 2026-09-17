"""Second independent targeted diagnostic after quarantining one remote UNKNOWN.

This is not a retry of epistemic_probe_01. It creates a new logical batch,
runtime and provider call IDs, while permanently preserving the old stopped
batch and its raw UNKNOWN N06_T3 row.

Fixed scope: N06/N07/N08/N11 six-turn cases plus R02 two-turn regression = 26
known-development turns. N01/N02 are omitted only because probe_01 already has
complete quote-bound 24/24 PASS reviews for each; those reviews remain
diagnostic evidence and do not replace the eventual final full82/328 gate.
"""
from __future__ import annotations

import argparse
import copy
import importlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import r047_execution_common as common
import repair_revision_r047_v6 as parent
import unknown_quarantine_r047 as unknowns

ROOT, PLAN = common.ROOT, common.PLAN
REV = PLAN / 'evidence/R047-03/epistemic_probe_02'
LIVE = REV / 'live'
BATCH = 'APCORE-R047-EPISTEMIC-DIAGNOSTIC-02'
CASE_IDS = ('N06', 'N07', 'N08', 'N11', 'R02')
GUARD_CNY = 35
AGGREGATE_GUARD_CNY = 466.5
OLD = PLAN / 'evidence/R047-03/epistemic_probe_01'
OLD_UNKNOWN_CALL = 'call_b0a10f775d26445cb6402b8a012917bc'
PARTIAL_REVIEW = OLD / 'PARTIAL_SEMANTIC_REVIEW.json'
ensure = common.ensure


def dump(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def fixed_scope():
    original, cases, fixture, frozen = parent.load_revision()
    scope = copy.deepcopy(original)
    scope.update(
        batch_id=BATCH,
        purpose=(
            'Independent known-case epistemic diagnostic after preserving and '
            'quarantining probe_01 remote UNKNOWN; this is not a retry or resume '
            'of any consumed/unknown old slot.'
        ),
        total_guard_cny=GUARD_CNY,
        all_operations_r045_plus_r047_guard_cny=AGGREGATE_GUARD_CNY,
    )
    scope['slots'] = [s for s in scope['slots'] if s['case_id'] in CASE_IDS]
    ensure(len(scope['slots']) == 26, 'probe_02 fixed slot count changed')
    ensure({s['case_id'] for s in scope['slots']} == set(CASE_IDS), 'probe_02 case set changed')
    ensure(all(s['model'] == 'deepseek-v4-flash' for s in scope['slots']), 'probe_02 model set changed')
    rates = scope['peak_rates_cny_per_million_tokens']
    scope['reserved_upper_micro_cny'] = sum(
        (scope['max_input_bytes'] + scope['input_overhead_reserve_tokens']) * rates[s['model']]['input_miss']
        + scope['max_output_tokens'] * rates[s['model']]['output']
        for s in scope['slots'])
    common.scope_check(scope)
    return scope, cases, fixture, frozen


def current_regression() -> dict:
    """Require a complete current-source zero-target-call regression snapshot."""
    current = {p.relative_to(ROOT).as_posix(): common.file_sha(p)
               for p in sorted((ROOT / 'persona_core/operational_runtime_v1').glob('*.py'))
               + sorted((PLAN / 'tools').glob('*.py'))}
    for directory in sorted((PLAN / 'evidence/R047-03').glob('regression_*'), reverse=True):
        path = directory / 'REGRESSION.json'
        if not path.is_file():
            continue
        report = common.read_json(path)
        if not (report.get('passed') and report.get('protected_history_and_production_unchanged')
                and report.get('target_calls') == 0):
            continue
        sources = report.get('sources', {})
        if set(sources) == set(current) and all(sources[name] == digest for name, digest in current.items()):
            return {'path': path.relative_to(ROOT).as_posix(), 'sha256': common.file_sha(path),
                    'tests': report['tests']}
    raise common.StoreGuard('No complete current-source regression binds probe_02')


def readiness(*, require_current_regression: bool = True) -> dict:
    status = unknowns.ensure_new_independent_batch_allowed()
    quarantined = [r for r in status['allowed_historical_unknowns']
                   if r.get('call_id') == OLD_UNKNOWN_CALL and r.get('classification') == 'QUARANTINED_REMOTE_UNKNOWN']
    ensure(len(quarantined) == 1, 'probe_01 remote UNKNOWN is not uniquely quarantined')
    ensure(not status['active_unresolved_remote_unknowns'], 'An active remote UNKNOWN still exists')

    # No live driver may be active in any direct R047 journal.
    active = []
    for root in unknowns.direct_live_roots():
        db = sqlite3.connect((root / 'live/runtime.sqlite3').as_uri() + '?mode=ro', uri=True)
        try:
            rows = db.execute(
                "SELECT key,value FROM metadata WHERE key IN ('r047_active_driver','r047_capacity_driver') "
                "AND value<>''").fetchall()
            active.extend({'root': root.relative_to(ROOT).as_posix(), 'key': key, 'value': value}
                          for key, value in rows)
        finally:
            db.close()
    ensure(not active, 'A prior live driver is active or unreconciled')

    db = sqlite3.connect((OLD / 'live/runtime.sqlite3').as_uri() + '?mode=ro', uri=True)
    try:
        counts = dict(db.execute('SELECT status,count(*) FROM provider_calls GROUP BY status').fetchall())
        stopped = db.execute('SELECT stopped FROM call_batches WHERE batch_id=?',
                             ('APCORE-R047-EPISTEMIC-DIAGNOSTIC-01',)).fetchone()
        ensure(counts == {'RESPONSE_CAPTURED': 14, 'SUBMITTED_STATUS_UNKNOWN': 1},
               'probe_01 terminal denominator changed')
        ensure(stopped is not None and stopped[0] == 1, 'probe_01 must remain terminal-stopped')
    finally:
        db.close()

    partial = common.read_json(PARTIAL_REVIEW)
    ensure(partial['full_38_review_complete'] is False and partial['full_82_acceptance_claim'] is False,
           'Partial review cannot be upgraded')
    ensure({c['case_id'] for c in partial['complete_case_reviews']} == {'N01', 'N02'},
           'Only N01/N02 may justify omission from probe_02')
    ensure(all(c['criteria'] == 24 and c['pass'] == 24 for c in partial['complete_case_reviews']),
           'N01/N02 complete diagnostic reviews changed')
    result = {
        'unknown_policy': status,
        'quarantined_predecessor_call': quarantined[0],
        'old_probe_counts': counts,
        'old_probe_stopped': True,
        'partial_review': PARTIAL_REVIEW.relative_to(ROOT).as_posix(),
        'partial_review_sha256': common.file_sha(PARTIAL_REVIEW),
    }
    if require_current_regression:
        result['current_regression'] = current_regression()
    return result


def load(prepare: bool = False):
    scope, cases, fixture, frozen = fixed_scope()
    manifest = common.read_json(REV / 'MANIFEST.json')
    ensure(common.read_json(REV / 'EXECUTION_SCOPE.json') == scope, 'probe_02 scope changed')
    ensure(common.file_sha(REV / 'EXECUTION_SCOPE.json') == manifest['scope_sha256'], 'probe_02 scope hash changed')
    ensure(manifest['fixed_calls'] == 26 and manifest['case_ids'] == list(CASE_IDS), 'probe_02 manifest denominator changed')
    ensure(manifest['old_unknown_call_id'] == OLD_UNKNOWN_CALL and manifest['old_unknown_resend_allowed'] is False,
           'probe_02 predecessor retry boundary changed')
    ensure(manifest['full82_acceptance_claim'] is False and manifest['automatic_next_revision'] is False,
           'probe_02 cannot become full/open-ended acceptance')
    selected = copy.deepcopy(cases)
    if not prepare:
        selected['cases'] = [c for c in selected['cases'] if c['id'] in CASE_IDS]
    return scope, selected, fixture, {**frozen, 'scope_sha256': manifest['scope_sha256']}


def create() -> int:
    ready = readiness()
    scope, _, _, _ = fixed_scope()
    ensure(not REV.exists(), 'probe_02 already exists; reconcile instead of recreating')
    REV.mkdir(parents=True)
    dump(REV / 'EXECUTION_SCOPE.json', scope)
    dump(REV / 'MANIFEST.json', {
        'batch_id': BATCH,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope_sha256': common.file_sha(REV / 'EXECUTION_SCOPE.json'),
        'fixed_calls': 26,
        'case_ids': list(CASE_IDS),
        'guard_cny': GUARD_CNY,
        'aggregate_guard_cny': AGGREGATE_GUARD_CNY,
        'reserved_upper_micro_cny': scope['reserved_upper_micro_cny'],
        'old_unknown_call_id': OLD_UNKNOWN_CALL,
        'old_unknown_resend_allowed': False,
        'old_batch_resume_allowed': False,
        'fresh_batch_and_runtime_required': True,
        'readiness': ready,
        'known_development_regression': True,
        'new_heldout_claim': False,
        'full82_acceptance_claim': False,
        'automatic_paid_retries': 0,
        'automatic_next_revision': False,
        'execution_requires_explicit_over_20_cny_confirmation': True,
        'review_contract': (
            'Review every captured probe_02 turn under the original four criteria. '
            'Missing/unknown/unrun turns never pass. This diagnostic cannot replace final full82/328.'
        ),
    })
    old_official = common.read_json(OLD / 'OFFICIAL_PREFLIGHT.json')
    dump(REV / 'OFFICIAL_PREFLIGHT.json', {
        **old_official,
        'at_utc': datetime.now(timezone.utc).isoformat(),
        'same_date_source_evidence_reused_from': (OLD / 'OFFICIAL_PREFLIGHT.json').relative_to(ROOT).as_posix(),
        'same_date_source_evidence_sha256': common.file_sha(OLD / 'OFFICIAL_PREFLIGHT.json'),
        'execution_recheck_complete': False,
        'billing_verified': False,
    })
    print(json.dumps({'output': REV.relative_to(ROOT).as_posix(), 'calls': 26,
                      'reserve_micro_cny': scope['reserved_upper_micro_cny'],
                      'guard_cny': GUARD_CNY, 'aggregate_guard_cny': AGGREGATE_GUARD_CNY,
                      'target_calls': 0}, ensure_ascii=False))
    return 0


def dispatch(action: str, rest: list[str]) -> int:
    scope, _, _, _ = load()
    if action in {'prepare', 'execute'}:
        now = readiness()
        pinned = common.read_json(REV / 'MANIFEST.json')['readiness']
        # Current regression may legitimately advance after preparation; all
        # immutable predecessor/quarantine facts must remain identical.
        for key in ('quarantined_predecessor_call', 'old_probe_counts', 'old_probe_stopped',
                    'partial_review', 'partial_review_sha256'):
            ensure(now[key] == pinned[key], 'probe_02 predecessor/quarantine readiness changed')
        ensure(not now['unknown_policy']['active_unresolved_remote_unknowns'], 'New unresolved remote UNKNOWN appeared')
    if action == 'prepare':
        ensure(not rest and not LIVE.exists(), 'Existing probe_02 runtime cannot be prepared twice')
        dump(REV / 'PREPARE_INTENT.json', {'pid': os.getpid(), 'at_utc': datetime.now(timezone.utc).isoformat()})
    if action == 'execute':
        authorization = REV / 'EXECUTION_AUTHORIZATION.json'
        ensure(authorization.is_file(), 'Explicit >=20 CNY execution confirmation is required')
        approved = common.read_json(authorization)
        ensure(approved.get('approved') is True and approved.get('guard_cny') == GUARD_CNY
               and approved.get('batch_id') == BATCH, 'Execution authorization does not match probe_02')
        prepared = common.read_json(REV / 'PREPARE_COMPLETE.json')
        ensure(prepared['fixture_preparation_sha256'] == common.file_sha(LIVE / 'FIXTURE_PREPARATION.json'),
               'probe_02 preparation binding changed')
        official = common.read_json(REV / 'OFFICIAL_PREFLIGHT.json')
        ensure(official.get('execution_recheck_complete') is True, 'Current official provider recheck required before paid execution')
        ensure(official['checked_date'] == datetime.now(timezone.utc).date().isoformat(), 'Provider recheck date is stale')

    module = importlib.import_module({'prepare': 'prepare_execution_r047',
                                      'execute': 'execute_r047',
                                      'audit': 'audit_captures_r047'}[action])
    replacement = {'PLAN': REV, 'LIVE': LIVE,
                   'load_frozen': lambda: load(prepare=action == 'prepare')}
    if action == 'execute':
        replacement['OFFICIAL_PREFLIGHT_PATH'] = REV / 'OFFICIAL_PREFLIGHT.json'
    previous = {key: getattr(module, key) for key in replacement}
    old_args, before = sys.argv, set(REV.rglob('*.json'))
    try:
        for key, value in replacement.items():
            setattr(module, key, value)
        sys.argv = [module.__name__] + rest
        result = module.main()
        if action == 'prepare':
            saved = common.read_json(LIVE / 'FIXTURE_PREPARATION.json')
            preflight = common.read_json(ROOT / saved['preflight_path'] / 'PREFLIGHT.json')
            ensure(preflight['passed'] and preflight['target_calls'] == 0, 'probe_02 preparation failed')
            dump(REV / 'PREPARE_COMPLETE.json', {
                'fixture_preparation_sha256': common.file_sha(LIVE / 'FIXTURE_PREPARATION.json'),
                'new_target_calls': 0,
            })
        return result or 0
    finally:
        for path in set(REV.rglob('*.json')) - before:
            if path.name == 'CAPTURE_AUDIT.json' or path.name.endswith('_REVIEW_INPUT.json'):
                value = common.read_json(path)
                value.update(batch_id=BATCH, known_development_regression=True,
                             new_heldout_claim=False, full82_acceptance_claim=False,
                             diagnostic_fixed_slots=26)
                path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        for key, value in previous.items():
            setattr(module, key, value)
        sys.argv = old_args


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['create', 'prepare', 'execute', 'audit'])
    args, rest = parser.parse_known_args()
    if args.action == 'create':
        ensure(not rest, 'Create accepts no extra arguments')
        return create()
    return dispatch(args.action, rest)


if __name__ == '__main__':
    raise SystemExit(main())

