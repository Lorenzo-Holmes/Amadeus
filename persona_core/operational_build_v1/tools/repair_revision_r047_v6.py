"""Fixed full82 validation after the actual host/worker capacity diagnostic.

Original and failed batches remain immutable. This candidate uses the same
expression repair with a tested, explicitly larger maximum-reasoning envelope.
It is known development regression, never an unseen or independent acceptance.
"""
from __future__ import annotations
import argparse
import copy
import importlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import r047_execution_common as common
import repair_revision_r047_v5 as expression_revision
import capacity_probe_v2_r047 as diagnostic_revision

ROOT, PLAN = common.ROOT, common.PLAN
REV = PLAN / 'evidence/R047-03/repair_06'
LIVE = REV / 'live'
PREVIOUS = PLAN / 'evidence/R047-03/repair_05'
BATCH = 'APCORE-R047-CAPACITY-VALIDATED-REPAIR-06'
KNOWN = 'KNOWN_DEVELOPMENT_REGRESSION'
DIAGNOSTIC = PLAN / 'evidence/R047-03/capacity_probe_02'
DIAGNOSTIC_REVIEW = DIAGNOSTIC / 'BOUND_DIAGNOSTIC_REVIEW_20260911T030359610355Z.json'
GUARD = 125
AGGREGATE_GUARD = 381.5
PRO_ROUTE_CHANGE_UTC = datetime(2026, 9, 14, 4, tzinfo=timezone.utc)
ensure = common.ensure


def dump(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)

def direct_live_roots(directory):
    """Every direct live journal participates, regardless of revision name.

    Nested test fixtures and archived snapshots are not active model journals.
    A newly named diagnostic must not evade the cross-batch unknown guard.
    """
    return sorted(p for p in Path(directory).iterdir()
                  if p.is_dir() and (p/'live/runtime.sqlite3').is_file())


def verify_ready():
    disposition = diagnostic_revision.verify_local_disposition()
    review = common.read_json(DIAGNOSTIC_REVIEW)
    ensure(review['batch_id'] == 'APCORE-R047-CAPACITY-PROBE-02', 'Wrong diagnostic review')
    ensure(review['diagnostic_capture_and_binding_passed'] is True and review['local_diagnostic_semantic_criteria_pass'] is True,
           'Actual diagnostic and its explicit review must pass first')
    ensure(review['reviewed_turns'] == 4 and review['criteria_reviewed'] == 16 and len(review['bound_judgments']) == 16, 'Diagnostic coverage changed')
    ensure(all(j['verdict'] == 'PASS' for j in review['bound_judgments']), 'Diagnostic review contains a nonpass')
    ensure(review['full_82_acceptance_complete'] is False and review['capacity_increase_is_proven_cause'] is False,
           'Diagnostic must not be upgraded to a full or causal acceptance')
    ensure(common.file_sha(DIAGNOSTIC / 'live/runtime.sqlite3') == review['journal_sha256'], 'Reviewed diagnostic journal changed')
    ensure(common.file_sha(DIAGNOSTIC / 'SEMANTIC_REVIEW.json') == review['review_notes_sha256'], 'Diagnostic review notes changed')
    # All direct live revisions are checked, not historical copied test fixtures.
    roots = direct_live_roots(PLAN/'evidence/R047-03')
    reconciled = []
    for root in roots:
        path = root / 'live/runtime.sqlite3'
        if not path.is_file():
            continue
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        try:
            ensure(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'Prior live journal integrity failure')
            leases = db.execute("SELECT key,value FROM metadata WHERE key IN ('r047_active_driver','r047_capacity_driver') AND value<>''").fetchall()
            ensure(not leases, 'Another live or stale driver is present; reconcile it first')
            unknown = db.execute("SELECT call_id FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchall()
            if unknown:
                ensure(root.name == 'capacity_probe_01' and unknown == [('call_65df5a4dbb844432bdad8e63a8c68db5',)],
                       'An unreconciled real provider submission blocks further calls')
                # The named source-bound proof is checked above; the raw row is
                # still UNKNOWN and its batch/slot are never made runnable again.
                reconciled.append({'journal': path.relative_to(ROOT).as_posix(), 'raw_unknown_retained': True, **disposition})
        finally:
            db.close()
    return {'diagnostic_review': DIAGNOSTIC_REVIEW.relative_to(ROOT).as_posix(),
            'diagnostic_review_sha256': common.file_sha(DIAGNOSTIC_REVIEW),
            'named_local_disposition': disposition, 'raw_unknown_rows_with_specific_local_proof': reconciled}


def revision_scope(parent):
    scope = expression_revision.revision_scope(parent)
    scope.update(schema_version='apcore-provider-scope-3', batch_id=BATCH,
        purpose='Full82 known-case expression/continuity validation after tested host/HTTP-worker max-reasoning capacity repair. Prior failures and denominators retained.',
        capacity_policy_id='EXTENDED_MAX_REASONING_20260911',
        output_budget_includes_reasoning=True, automatic_capacity_escalation=False,
        max_output_tokens=131072, request_timeout_seconds=1200,
        total_guard_cny=GUARD, all_operations_r045_plus_r047_guard_cny=AGGREGATE_GUARD)
    rates = scope['peak_rates_cny_per_million_tokens']
    scope['reserved_upper_micro_cny'] = sum((scope['max_input_bytes'] + scope['input_overhead_reserve_tokens']) * rates[s['model']]['input_miss'] +
        scope['max_output_tokens'] * rates[s['model']]['output'] for s in scope['slots'])
    return scope


def taxonomy():
    return {'batch_id': BATCH, 'current_evaluation_classification': KNOWN,
        'known_development_regression': True, 'new_heldout_claim': False,
        'explicit_provider_and_capacity_revision': True,
        'primary_provider_version_documented': 'DeepSeek-V4.1-Flash',
        'switch_provider_version_documented': 'DeepSeek-V4-Pro-0813',
        'provider_identity_independently_verified': False,
        'paired_provider_performance_claim': False, 'capacity_change_is_proven_causal_benefit': False}


def load_revision():
    parent, cases, fixture, frozen = common.load_frozen()
    manifest = common.read_json(REV / 'REVISION.json')
    scope = common.read_json(REV / 'EXECUTION_SCOPE.json')
    ensure(scope == revision_scope(parent), 'Scope differs from this explicit fixed capacity revision')
    ensure(common.file_sha(REV / 'EXECUTION_SCOPE.json') == manifest['scope_file_sha256'], 'Revision scope file changed')
    ensure(frozen['scope_sha256'] == manifest['parent_scope_sha256'], 'Original frozen protocol changed')
    ensure(manifest['guard_cny'] == GUARD and manifest['aggregate_guard_cny'] == AGGREGATE_GUARD, 'Budget ledger changed')
    ensure(manifest['known_development_regression'] and not manifest['new_heldout_claim'], 'Do not relabel known data as unseen')
    common.scope_check(scope)
    cases = copy.deepcopy(cases)
    for case in cases['cases']:
        case['parent_classification'] = case['classification']
        case['current_evaluation_classification'] = KNOWN
    return scope, cases, fixture, {**frozen, 'scope_sha256': manifest['scope_file_sha256'],
                                  'original_scope_sha256': frozen['scope_sha256'], **taxonomy()}


def create():
    readiness = verify_ready()
    parent, _, _, frozen = common.load_frozen()
    scope = revision_scope(parent)
    common.scope_check(scope)
    ensure(not REV.exists(), 'Revision exists; reconcile instead of recreating it')
    REV.mkdir(parents=True)
    dump(REV / 'EXECUTION_SCOPE.json', scope)
    dump(REV / 'REVISION.json', {'created_at_utc': datetime.now(timezone.utc).isoformat(), **taxonomy(),
        'scope_file_sha256': common.file_sha(REV / 'EXECUTION_SCOPE.json'), 'parent_scope_sha256': frozen['scope_sha256'],
        'guard_cny': GUARD, 'aggregate_guard_cny': AGGREGATE_GUARD,
        'reserved_upper_micro_cny': scope['reserved_upper_micro_cny'], 'fixed_calls': 82,
        'readiness': readiness,
        'frozen_original_user_inputs_and_rubric_unchanged': True,
        'all_failed_batches_remain_immutable': True,
        'automatic_paid_retries': 0, 'automatic_next_revision_on_failure': False,
        'budget_authority': 'Existing project standing authorization / ONE_SHOT_EXECUTION_TO_BUILD_SCOPE_COMPLETE section6: explicit bounded higher-capacity revision, not an unbounded loop.',
        'diagnostic_four_turns_not_counted_toward_this_82': True,
        'profile': {'main_calls': 76, 'switch_calls': 6, 'thinking': 'enabled/max', 'input_bytes': 32768, 'output_tokens_including_reasoning': 131072, 'deadline_seconds_per_call': 1200}})
    official = common.read_json(PREVIOUS / 'OFFICIAL_PREFLIGHT.json')
    official.update(at_utc=datetime.now(timezone.utc).isoformat(), checked_date='2026-09-11',
        scope_parameters_verified_before_execution=True,
        frozen_scope_parameters_changed=False, parent_scope_parameters_changed_explicitly=True,
        max_output_tokens=131072, request_timeout_seconds=1200,
        output_budget_includes_reasoning=True, peak_rates_cny_per_million_tokens=scope['peak_rates_cny_per_million_tokens'],
        current_recheck_source='https://api-docs.deepseek.com/api/create-chat-completion/',
        documented_default_output_tokens_for_max_effort=131072,
        billing_verified=False)
    dump(REV / 'OFFICIAL_PREFLIGHT.json', official)
    print(json.dumps({'revision': REV.relative_to(ROOT).as_posix(), 'calls': 82,
                      'reserve_micro_cny': scope['reserved_upper_micro_cny'], 'guard_cny': GUARD,
                      'aggregate_guard_cny': AGGREGATE_GUARD, 'target_calls': 0}))


def dispatch(action, rest):
    scope = load_revision()[0]
    if action == 'prepare':
        verify_ready()
        ensure(not LIVE.exists() and not rest, 'Existing runtime cannot be prepared again')
        dump(REV / 'PREPARE_INTENT.json', {'pid': os.getpid(), 'at_utc': datetime.now(timezone.utc).isoformat()})
    if action == 'execute':
        ready = verify_ready()
        ensure(ready == common.read_json(REV / 'REVISION.json')['readiness'], 'Predecessor reconciliation or reviewed diagnostic changed')
        completion = common.read_json(REV / 'PREPARE_COMPLETE.json')
        ensure(completion['fixture_preparation_sha256'] == common.file_sha(LIVE / 'FIXTURE_PREPARATION.json'), 'Preparation binding changed')
        official = common.read_json(REV / 'OFFICIAL_PREFLIGHT.json')
        ensure(official['checked_date'] == datetime.now(timezone.utc).date().isoformat(), 'Official models/prices require a current-date recheck')
        ensure(official['models_confirmed'] == [scope['primary_model'], scope['switch_model']], 'Documented model roles differ')
        ensure(datetime.now(timezone.utc) + timedelta(seconds=82 * scope['request_timeout_seconds'] + 300) < PRO_ROUTE_CHANGE_UTC,
               'Run could cross the announced Pro service route change')
    name = {'prepare': 'prepare_execution_r047', 'execute': 'execute_r047',
            'audit': 'audit_captures_r047', 'review': 'compile_reviews_r047'}[action]
    module = importlib.import_module(name)
    changes = {'LIVE': LIVE, 'PLAN': REV, 'load_frozen': load_revision}
    if action == 'execute':
        changes['OFFICIAL_PREFLIGHT_PATH'] = REV / 'OFFICIAL_PREFLIGHT.json'
    old = {key: getattr(module, key) for key in changes}
    old_argv, before = sys.argv, set(REV.rglob('*.json'))
    try:
        for key, value in changes.items():
            setattr(module, key, value)
        sys.argv = [name + '.py'] + rest
        result = module.main()
        if action == 'prepare':
            prepared = common.read_json(LIVE / 'FIXTURE_PREPARATION.json')
            check = common.read_json(ROOT / prepared['preflight_path'] / 'PREFLIGHT.json')
            ensure(check['passed'] and check['target_calls'] == 0, 'No-network preflight failed')
            dump(REV / 'PREPARE_COMPLETE.json', {'fixture_preparation_sha256': common.file_sha(LIVE / 'FIXTURE_PREPARATION.json'), **taxonomy()})
        return result or 0
    finally:
        for path in set(REV.rglob('*.json')) - before:
            if path.name in {'CAPTURE_AUDIT.json', 'QUALITY_AND_COVERAGE.json', 'REVIEW_BINDING_REPORT.json'} or path.name.endswith('_REVIEW_INPUT.json'):
                value = common.read_json(path)
                value.update(taxonomy())
                path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        for key, value in old.items():
            setattr(module, key, value)
        sys.argv = old_argv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['create', 'prepare', 'execute', 'audit', 'review'])
    args, rest = parser.parse_known_args()
    if args.action == 'create':
        ensure(not rest, 'Create accepts no extra arguments')
        create(); return 0
    return dispatch(args.action, rest)


if __name__ == '__main__':
    raise SystemExit(main())
