"""Second named R047 semantic-repair regression revision.

repair_01 is terminal and immutable after a real provider response returned
HTTP 200 / finish_reason=stop but no displayable final content for N02_T1.
This module creates a wholly separate full-82 known-development regression
batch. It never clears repair_01's stopped flag, never resends a slot inside
repair_01, and never writes the original R047 live runtime.
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

import r047_execution_common as original

ROOT, PLAN = original.ROOT, original.PLAN
REV = PLAN / 'evidence/R047-03/repair_02'
LIVE = REV / 'live'
PREVIOUS = PLAN / 'evidence/R047-03/repair_01'
BATCH = 'APCORE-R047-SEMANTIC-REPAIR-02'
PREVIOUS_BATCH = 'APCORE-R047-SEMANTIC-REPAIR-01'
KNOWN = 'KNOWN_DEVELOPMENT_REGRESSION'
TOTAL_GUARD_CNY = 45
ALL_OPERATIONS_GUARD_CNY = 136.5
ensure = original.ensure


def dump(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def revision_scope(parent: dict) -> dict:
    scope = copy.deepcopy(parent)
    scope.update(
        batch_id=BATCH,
        purpose=(
            'Fresh full82 known-case semantic repair regression after repair_01 '
            'terminated on a preserved provider EMPTY_RESPONSE. This is a new '
            'logical batch, not a retry or unlock of any repair_01 slot.'
        ),
        pricing_verified_date='2026-09-11',
        all_operations_r045_plus_r047_guard_cny=ALL_OPERATIONS_GUARD_CNY,
    )
    # Keep the already conservative 2026-09-08 pinned rates. The 2026-09-11
    # official pricing page showed no higher peak rate; Flash was lower.
    for slot in scope['slots']:
        slot['parent_evaluation_phase'] = slot['evaluation_phase']
        slot['evaluation_phase'] = KNOWN
    return scope


def taxonomy() -> dict:
    return {
        'batch_id': BATCH,
        'current_evaluation_classification': KNOWN,
        'known_development_regression': True,
        'new_heldout_claim': False,
        'parent_taxonomy_note': (
            'All repair_02 outputs are known development regression. Original '
            'NEW_AT_FREEZE taxonomy belongs only to the immutable parent protocol.'
        ),
    }


def verify_previous_terminal() -> dict:
    db_path = PREVIOUS / 'live/runtime.sqlite3'
    ensure(db_path.is_file(), 'repair_01 journal missing')
    db = sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        ensure(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'repair_01 SQLite integrity failure')
        counts = {row['status']: row['n'] for row in db.execute(
            'SELECT status,count(*) AS n FROM provider_calls GROUP BY status')}
        ensure(counts == {'RESPONSE_CAPTURED': 6, 'RESPONSE_REJECTED': 1},
               'repair_01 terminal call counts differ from preserved failure')
        batch = db.execute('SELECT stopped FROM call_batches WHERE batch_id=?', (PREVIOUS_BATCH,)).fetchone()
        ensure(batch is not None and batch['stopped'] == 1, 'repair_01 logical batch is not terminal-stopped')
        active = db.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone()
        ensure(active is not None and active['value'] == '', 'repair_01 driver lease is not reconciled')
        ensure(db.execute("SELECT count(*) FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchone()[0] == 0,
               'repair_01 has unknown provider submissions')
        failed = db.execute(
            "SELECT slot_id,http_status,finish_reason,error_category,raw_response,usage_json "
            "FROM provider_calls WHERE status='RESPONSE_REJECTED'").fetchone()
        ensure(failed is not None and failed['slot_id'] == 'N02_T1', 'repair_01 rejected slot changed')
        ensure(failed['http_status'] == 200 and failed['finish_reason'] == 'stop' and failed['error_category'] == 'EMPTY_RESPONSE',
               'repair_01 rejection signature changed')
        raw = json.loads(failed['raw_response'])
        usage = json.loads(failed['usage_json'])
        message = raw['choices'][0]['message']
        ensure(message.get('content') == '', 'repair_01 preserved response is no longer empty')
        reasoning = (usage.get('completion_tokens_details') or {}).get('reasoning_tokens')
        ensure(reasoning == usage['completion_tokens'] == 300,
               'repair_01 preserved empty-response token signature changed')
        return {
            'journal': str(db_path.relative_to(ROOT)).replace('\\', '/'),
            'status_counts': counts,
            'batch_stopped': True,
            'unknown_submissions': 0,
            'terminal_failure': {
                'slot_id': failed['slot_id'],
                'http_status': failed['http_status'],
                'finish_reason': failed['finish_reason'],
                'error_category': failed['error_category'],
                'completion_tokens': usage['completion_tokens'],
                'reasoning_tokens': reasoning,
                'final_content_empty': True,
            },
        }
    finally:
        db.close()


def load_revision():
    parent, cases, fixture, frozen = original.load_frozen()
    manifest = original.read_json(REV / 'REVISION.json')
    scope = original.read_json(REV / 'EXECUTION_SCOPE.json')
    ensure(original.file_sha(REV / 'EXECUTION_SCOPE.json') == manifest['scope_file_sha256'],
           'repair_02 scope bytes differ from manifest')
    ensure(manifest['parent_scope_file_sha256'] == frozen['scope_sha256'], 'repair_02 parent protocol changed')
    ensure(scope == revision_scope(parent), 'repair_02 scope differs beyond declared batch/date/accounting/taxonomy changes')
    ensure(manifest['previous_repair_batch_id'] == PREVIOUS_BATCH, 'repair_02 lineage changed')
    ensure(manifest['known_development_regression'] is True and manifest['new_heldout_claim'] is False,
           'repair_02 cannot claim heldout evaluation')
    ensure(manifest['total_guard_cny'] == TOTAL_GUARD_CNY and manifest['all_operations_guards_cny'] == ALL_OPERATIONS_GUARD_CNY,
           'repair_02 guard accounting changed')
    original.scope_check(scope)
    cases = copy.deepcopy(cases)
    for case in cases['cases']:
        case['parent_classification'] = case['classification']
        case['current_evaluation_classification'] = KNOWN
    return scope, cases, fixture, {
        **frozen,
        'scope_sha256': manifest['scope_file_sha256'],
        'original_scope_sha256': frozen['scope_sha256'],
        **taxonomy(),
    }


def create_revision() -> int:
    parent, _, _, frozen = original.load_frozen()
    # Original 82 remains immutable and complete.
    db = sqlite3.connect((original.LIVE / 'runtime.sqlite3').as_uri() + '?mode=ro', uri=True)
    try:
        counts = db.execute('SELECT status,count(*) FROM provider_calls GROUP BY status').fetchall()
        ensure(counts == [('RESPONSE_CAPTURED', 82)], 'Original82 journal is not wholly terminal')
        active = db.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone()
        ensure(active is not None and active[0] == '', 'Original R047 driver is active or unreconciled')
    finally:
        db.close()
    previous = verify_previous_terminal()
    REV.mkdir(parents=True, exist_ok=False)
    scope = revision_scope(parent)
    original.scope_check(scope)
    dump(REV / 'EXECUTION_SCOPE.json', scope)
    dump(REV / 'REVISION.json', {
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'batch_id': BATCH,
        'parent_batch_id': parent['batch_id'],
        'previous_repair_batch_id': PREVIOUS_BATCH,
        'parent_scope_file_sha256': frozen['scope_sha256'],
        'scope_file_sha256': original.file_sha(REV / 'EXECUTION_SCOPE.json'),
        'known_development_regression': True,
        'new_heldout_claim': False,
        'original_rubric_unchanged': True,
        'fixed_calls': len(scope['slots']),
        'total_guard_cny': TOTAL_GUARD_CNY,
        'all_operations_guards_cny': ALL_OPERATIONS_GUARD_CNY,
        'automatic_paid_retries': 0,
        'previous_terminal_evidence': previous,
        'continuation_policy': (
            'repair_01 is immutable and permanently stopped. repair_02 starts a fresh '
            'full82 denominator so no successful subset is cherry-picked and no '
            'consumed repair_01 slot is resent within its logical batch.'
        ),
        'comparison_policy': (
            'Original82, repair_01 partial terminal evidence and repair_02 are reported '
            'separately. Only a complete clean repair_02 may be bound to a new semantic review.'
        ),
    })
    dump(REV / 'OFFICIAL_PREFLIGHT.json', {
        'at_utc': datetime.now(timezone.utc).isoformat(),
        'evidence_kind': 'LIVE_OFFICIAL_DOCUMENTATION_CHECK_NOT_BILLING',
        'checked_date': '2026-09-11',
        'sources': [
            'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',
            'https://api-docs.deepseek.com/api/create-chat-completion/',
            'https://api-docs.deepseek.com/guides/thinking_mode/',
        ],
        'http_checks': {'pricing': 200, 'chat_completions': 200, 'thinking_mode': 200},
        'models_confirmed': [scope['primary_model'], scope['switch_model']],
        'model_note': (
            'Official pricing page lists deepseek-v4-pro and documents deepseek-flash '
            'with deepseek-v4-flash version/alias wording; the frozen switch model is retained '
            'for protocol comparability and remains fail-closed if the provider rejects it.'
        ),
        'thinking': scope['thinking'],
        'reasoning_effort': scope['reasoning_effort'],
        'thinking_contract_observed': 'thinking enabled/disabled and reasoning effort none/low/high/max documented',
        'current_peak_table_observation_cny_per_million_tokens': {
            'deepseek-flash': {'input_miss': 2.0, 'input_hit': 0.04, 'output': 8.0},
            'deepseek-v4-pro': {'input_miss': 9.0, 'input_hit': 0.30, 'output': 27.0},
        },
        'pinned_conservative_rates_used_for_guard': scope['peak_rates_cny_per_million_tokens'],
        'pinned_rates_not_lower_than_current_peak': True,
        'frozen_scope_parameters_changed': False,
        'billing_verified': False,
    })
    print(json.dumps({'revision': str(REV.relative_to(ROOT)), 'calls': 82,
                      'guard': TOTAL_GUARD_CNY, 'target_calls': 0}, ensure_ascii=False))
    return 0


def annotate_generated_outputs(before: set[Path]) -> None:
    for path in set(REV.rglob('*.json')) - before:
        if path.name in {'CAPTURE_AUDIT.json', 'QUALITY_AND_COVERAGE.json', 'REVIEW_BINDING_REPORT.json'} or path.name.endswith('_REVIEW_INPUT.json'):
            report = original.read_json(path)
            report.update(taxonomy())
            with path.open('w', encoding='utf-8') as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)


def dispatch(action: str, rest: list[str]) -> int:
    load_revision()
    ensure(action in {'prepare', 'execute', 'audit', 'review'}, 'Unsupported repair_02 action')
    if action == 'prepare':
        ensure(not rest, 'Preparation does not accept extra arguments')
        ensure(not LIVE.exists(), 'Existing repair_02 runtime must be reconciled; preparation is never repeated')
        dump(REV / 'PREPARE_INTENT.json', {
            'pid': os.getpid(),
            'started_at_utc': datetime.now(timezone.utc).isoformat(),
            'scope_sha256': original.file_sha(REV / 'EXECUTION_SCOPE.json'),
        })
    if action == 'execute':
        completed = original.read_json(REV / 'PREPARE_COMPLETE.json')
        ensure(completed['fixture_preparation_sha256'] == original.file_sha(LIVE / 'FIXTURE_PREPARATION.json'),
               'repair_02 preparation binding changed')
        official = original.read_json(REV / 'OFFICIAL_PREFLIGHT.json')
        scope = load_revision()[0]
        ensure(official['frozen_scope_parameters_changed'] is False, 'repair_02 official preflight changed frozen parameters')
        ensure(official['pinned_conservative_rates_used_for_guard'] == scope['peak_rates_cny_per_million_tokens'],
               'repair_02 budget rates differ from scope')
        ensure(official['models_confirmed'] == [scope['primary_model'], scope['switch_model']],
               'repair_02 official model verification differs')
        ensure(official['thinking'] == scope['thinking'] and official['reasoning_effort'] == scope['reasoning_effort'],
               'repair_02 thinking contract differs')
    module_name = {
        'prepare': 'prepare_execution_r047',
        'execute': 'execute_r047',
        'audit': 'audit_captures_r047',
        'review': 'compile_reviews_r047',
    }[action]
    module = importlib.import_module(module_name)
    changes = {'LIVE': LIVE, 'PLAN': REV, 'load_frozen': load_revision}
    if action == 'execute':
        changes['OFFICIAL_PREFLIGHT_PATH'] = REV / 'OFFICIAL_PREFLIGHT.json'
    previous = {name: getattr(module, name) for name in changes}
    previous_argv = sys.argv
    before = set(REV.rglob('*.json'))
    try:
        for name, value in changes.items():
            setattr(module, name, value)
        sys.argv = [module_name + '.py'] + rest
        result = module.main()
        if action == 'prepare':
            saved = original.read_json(LIVE / 'FIXTURE_PREPARATION.json')
            preflight = original.read_json(ROOT / saved['preflight_path'] / 'PREFLIGHT.json')
            ensure(preflight['passed'] and preflight['target_calls'] == 0, 'repair_02 preparation did not complete')
            dump(REV / 'PREPARE_COMPLETE.json', {
                'completed_at_utc': datetime.now(timezone.utc).isoformat(),
                'fixture_preparation_sha256': original.file_sha(LIVE / 'FIXTURE_PREPARATION.json'),
                **taxonomy(),
            })
        return result or 0
    finally:
        annotate_generated_outputs(before)
        for name, value in previous.items():
            setattr(module, name, value)
        sys.argv = previous_argv


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['create', 'prepare', 'execute', 'audit', 'review'])
    args, rest = parser.parse_known_args()
    if args.action == 'create':
        ensure(not rest, 'Create does not accept extra arguments')
        return create_revision()
    return dispatch(args.action, rest)


if __name__ == '__main__':
    raise SystemExit(main())
