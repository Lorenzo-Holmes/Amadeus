"""A substantive expression/provider revision, not a retry of stopped batches.

All original user inputs, rubrics, and 82 denominator entries are preserved.
This candidate explicitly changes primary/switch roles and prompt bounds;
results are known development regression, not an unseen or paired benchmark.
"""
from __future__ import annotations
import argparse
import copy
import importlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import r047_execution_common as common

ROOT, PLAN = common.ROOT, common.PLAN
REV = PLAN / 'evidence/R047-03/repair_05'
LIVE = REV / 'live'
PREVIOUS = PLAN / 'evidence/R047-03/repair_04'
BATCH = 'APCORE-R047-EXPRESSION-PROVIDER-REPAIR-05'
KNOWN = 'KNOWN_DEVELOPMENT_REGRESSION'
GUARD = 18
TOTAL_GUARD = 244.5
PRO_ROUTE_CHANGE_UTC = datetime(2026, 9, 14, 4, tzinfo=timezone.utc)
ensure = common.ensure


def dump(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def revision_scope(parent):
    scope = copy.deepcopy(parent)
    scope.update(batch_id=BATCH,
        purpose='Scoped contract-expression and usage-accounting repair; explicit V4.1-Flash main / V4-Pro switch provider revision, known full82 regression. No automatic retries.',
        primary_model='deepseek-v4-flash', switch_model='deepseek-v4-pro',
        max_input_bytes=32768, total_guard_cny=GUARD,
        all_operations_r045_plus_r047_guard_cny=TOTAL_GUARD,
        pricing_verified_date='2026-09-11')
    for slot in scope['slots']:
        slot['parent_evaluation_phase'] = slot['evaluation_phase']
        slot['evaluation_phase'] = KNOWN
        slot['model'] = scope['switch_model'] if '_S' in slot['id'] else scope['primary_model']
    rates = scope['peak_rates_cny_per_million_tokens']
    scope['reserved_upper_micro_cny'] = sum(
        (scope['max_input_bytes'] + scope['input_overhead_reserve_tokens']) * rates[s['model']]['input_miss'] +
        scope['max_output_tokens'] * rates[s['model']]['output'] for s in scope['slots'])
    return scope


def taxonomy():
    return {'batch_id': BATCH, 'current_evaluation_classification': KNOWN,
            'known_development_regression': True, 'new_heldout_claim': False,
            'paired_provider_performance_claim': False,
            'explicit_provider_revision': True,
            'primary_provider_version_documented': 'DeepSeek-V4.1-Flash',
            'switch_provider_version_documented': 'DeepSeek-V4-Pro-0813',
            'provider_version_independently_verified': False,
            'multi_change_candidate_not_causal_ablation': True}


def verify_previous_terminal():
    path = PREVIOUS / 'live/runtime.sqlite3'
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        ensure(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'Previous journal integrity failed')
        counts = dict(db.execute('SELECT status,count(*) FROM provider_calls GROUP BY status'))
        ensure(counts == {'RESPONSE_CAPTURED': 64, 'RESPONSE_REJECTED': 1}, 'Previous terminal counts changed')
        ensure(db.execute('SELECT stopped FROM call_batches').fetchall() == [(1,)], 'Previous batch not stopped')
        ensure(db.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone() == ('',), 'Previous driver active/unreconciled')
        failure = db.execute("SELECT slot_id,error_category,http_status,finish_reason FROM provider_calls WHERE status='RESPONSE_REJECTED'").fetchone()
        ensure(failure == ('N11_T1', 'EMPTY_RESPONSE', 200, 'stop'), 'Previous terminal signature changed')
        return {'journal': path.relative_to(ROOT).as_posix(), 'counts': counts,
                'failed_slot': failure[0], 'not_submitted': 17, 'unknown_submissions': 0,
                'journal_sha256': common.file_sha(path), 'stopped_flag_cleared': False}
    finally:
        db.close()


def load_revision():
    parent, cases, fixture, frozen = common.load_frozen()
    manifest = common.read_json(REV / 'REVISION.json')
    scope = common.read_json(REV / 'EXECUTION_SCOPE.json')
    ensure(common.file_sha(REV / 'EXECUTION_SCOPE.json') == manifest['scope_file_sha256'], 'Revision scope hash changed')
    ensure(frozen['scope_sha256'] == manifest['parent_scope_sha256'], 'Parent protocol changed')
    ensure(scope == revision_scope(parent), 'Scope differs from explicit provider/expression revision')
    ensure(manifest['total_guard_cny'] == GUARD and manifest['aggregate_guard_cny'] == TOTAL_GUARD, 'Guard ledger changed')
    ensure(manifest['known_development_regression'] and not manifest['new_heldout_claim'], 'Cannot relabel known cases as unseen')
    common.scope_check(scope)
    cases = copy.deepcopy(cases)
    for case in cases['cases']:
        case['parent_classification'] = case['classification']
        case['current_evaluation_classification'] = KNOWN
    return scope, cases, fixture, {**frozen, 'scope_sha256': manifest['scope_file_sha256'],
                                  'original_scope_sha256': frozen['scope_sha256'], **taxonomy()}


def create():
    parent, _, _, frozen = common.load_frozen()
    previous = verify_previous_terminal()
    ensure(not REV.exists(), 'Revision already exists; inspect instead of recreating')
    scope = revision_scope(parent)
    common.scope_check(scope)
    REV.mkdir(parents=True)
    dump(REV / 'EXECUTION_SCOPE.json', scope)
    dump(REV / 'REVISION.json', {
        'created_at_utc': datetime.now(timezone.utc).isoformat(), **taxonomy(),
        'parent_scope_sha256': frozen['scope_sha256'],
        'scope_file_sha256': common.file_sha(REV / 'EXECUTION_SCOPE.json'),
        'previous_terminal': previous, 'fixed_calls': 82,
        'total_guard_cny': GUARD, 'aggregate_guard_cny': TOTAL_GUARD,
        'reserved_upper_micro_cny': scope['reserved_upper_micro_cny'],
        'unchanged': ['fixed user inputs', 'private rubric', 'quality thresholds', '82-slot denominator', 'thinking enabled/max', '8192 output tokens', 'zero automatic retries', 'no API tools'],
        'changes': ['readable contract title/acceptance separation', 'no invented completion or deadlines in drafts', 'respect stipulated premises; distinguish descriptive arithmetic from population inference', 'reduce repetitive engineering exposition', 'reject bad responses while retaining validated usage costs', 'explicit primary Flash / switch Pro reversal', '32768-byte input cap'],
        'no_deterministic_prompt_guarantee_claim': True,
        'all_prior_batches_immutable': True,
        'next_revision_not_automatically_created_on_failure': True,
        'original_failure_not_removed_from_reports': True})
    dump(REV / 'OFFICIAL_PREFLIGHT.json', {
        'at_utc': datetime.now(timezone.utc).isoformat(),
        'checked_date': '2026-09-11', 'evidence_kind': 'WEB_PARSED_OFFICIAL_DOCUMENTATION_NOT_BILLING',
        'sources': ['https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',
                    'https://api-docs.deepseek.com/quick_start/pricing/',
                    'https://api-docs.deepseek.com/api/create-chat-completion/'],
        'models_confirmed': [scope['primary_model'], scope['switch_model']],
        'route_observation': 'Old deepseek-v4-flash name remains accepted but is served by V4.1-Flash. Pro requests route to V4.1-Flash after 2026-09-14 12:00 Beijing; this run must end before that.',
        'model_identity_is_provider_documentation_not_independent_attestation': True,
        'current_peak_rates_cny_per_million_tokens': {
            'deepseek-flash': {'input_miss': 2, 'input_hit': .04, 'output': 8},
            'deepseek-v4-pro': {'input_miss': 9, 'input_hit': .3, 'output': 27}},
        'peak_rates_cny_per_million_tokens': scope['peak_rates_cny_per_million_tokens'],
        'pinned_rates_are_conservative_not_current_bill': True,
        'thinking': scope['thinking'], 'reasoning_effort': scope['reasoning_effort'],
        'frozen_scope_parameters_changed': False,
        'parent_scope_parameters_changed_explicitly': True,
        'billing_verified': False})
    print(json.dumps({'revision': REV.relative_to(ROOT).as_posix(), 'fixed_calls': 82,
                      'guard_cny': GUARD, 'aggregate_guard_cny': TOTAL_GUARD,
                      'reserve_micro_cny': scope['reserved_upper_micro_cny'], 'target_calls': 0}))


def dispatch(action, rest):
    scope = load_revision()[0]
    if action == 'prepare':
        ensure(not LIVE.exists() and not rest, 'Cannot prepare an existing runtime')
        dump(REV / 'PREPARE_INTENT.json', {'pid': os.getpid(), 'at_utc': datetime.now(timezone.utc).isoformat()})
    if action == 'execute':
        verify_previous_terminal()
        completed = common.read_json(REV / 'PREPARE_COMPLETE.json')
        ensure(completed['fixture_preparation_sha256'] == common.file_sha(LIVE / 'FIXTURE_PREPARATION.json'), 'Preparation binding changed')
        official = common.read_json(REV / 'OFFICIAL_PREFLIGHT.json')
        ensure(official['checked_date'] == datetime.now(timezone.utc).date().isoformat(), 'Current official documentation must be rechecked before paid execution')
        ensure(official['models_confirmed'] == [scope['primary_model'], scope['switch_model']], 'Provider role check failed')
        ensure(official['thinking'] == scope['thinking'] and official['reasoning_effort'] == 'max', 'Thinking check failed')
        ensure(datetime.now(timezone.utc) + timedelta(seconds=82 * scope['request_timeout_seconds'] + 300) < PRO_ROUTE_CHANGE_UTC,
               'Run could cross documented Pro route change; do not claim a different-model switch')
    name = {'prepare': 'prepare_execution_r047', 'execute': 'execute_r047',
            'audit': 'audit_captures_r047', 'review': 'compile_reviews_r047'}[action]
    module = importlib.import_module(name)
    values = {'LIVE': LIVE, 'PLAN': REV, 'load_frozen': load_revision}
    if action == 'execute':
        values['OFFICIAL_PREFLIGHT_PATH'] = REV / 'OFFICIAL_PREFLIGHT.json'
    old = {key: getattr(module, key) for key in values}
    argv, before = sys.argv, set(REV.rglob('*.json'))
    try:
        for key, value in values.items():
            setattr(module, key, value)
        sys.argv = [name + '.py'] + rest
        result = module.main()
        if action == 'prepare':
            prepared = common.read_json(LIVE / 'FIXTURE_PREPARATION.json')
            check = common.read_json(ROOT / prepared['preflight_path'] / 'PREFLIGHT.json')
            ensure(check['passed'] and check['target_calls'] == 0, 'Preflight did not pass')
            dump(REV / 'PREPARE_COMPLETE.json', {'fixture_preparation_sha256': common.file_sha(LIVE / 'FIXTURE_PREPARATION.json'), **taxonomy()})
        return result or 0
    finally:
        for path in set(REV.rglob('*.json')) - before:
            if path.name in {'CAPTURE_AUDIT.json', 'QUALITY_AND_COVERAGE.json', 'REVIEW_BINDING_REPORT.json'} or path.name.endswith('_REVIEW_INPUT.json'):
                report = common.read_json(path)
                report.update(taxonomy())
                path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        for key, value in old.items():
            setattr(module, key, value)
        sys.argv = argv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['create', 'prepare', 'execute', 'audit', 'review'])
    args, rest = parser.parse_known_args()
    if args.action == 'create':
        ensure(not rest, 'Create accepts no additional arguments')
        create()
        return 0
    return dispatch(args.action, rest)


if __name__ == '__main__':
    raise SystemExit(main())
