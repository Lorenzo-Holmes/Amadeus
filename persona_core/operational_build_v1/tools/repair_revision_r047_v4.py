"""Fourth named R047 semantic-repair regression revision.

repair_03 proved the non-empty-final prompt repair across 30 Pro slots, then
stopped on the first Flash switch because the provider canonicalized the
requested `deepseek-v4-flash` model name to `deepseek-flash`. The response had
valid non-empty content; the adapter rejected only the model-name mismatch.

The current candidate recognizes that explicit official alias while preserving
strict family/version checks. repair_01..03 remain immutable terminal evidence.
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
REV = PLAN / 'evidence/R047-03/repair_04'
LIVE = REV / 'live'
PREVIOUS = PLAN / 'evidence/R047-03/repair_03'
BATCH = 'APCORE-R047-SEMANTIC-REPAIR-04'
PREVIOUS_BATCH = 'APCORE-R047-SEMANTIC-REPAIR-03'
KNOWN = 'KNOWN_DEVELOPMENT_REGRESSION'
TOTAL_GUARD_CNY = 45
ALL_OPERATIONS_GUARD_CNY = 226.5
ensure = original.ensure


def dump(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def revision_scope(parent: dict) -> dict:
    scope = copy.deepcopy(parent)
    scope.update(
        batch_id=BATCH,
        purpose=(
            'Fresh full82 known-case semantic repair regression after preserving '
            'repair_03 Flash canonical-name rejection and implementing an explicit '
            'deepseek-v4-flash -> deepseek-flash response alias. No prior slot retry.'
        ),
        pricing_verified_date='2026-09-11',
        all_operations_r045_plus_r047_guard_cny=ALL_OPERATIONS_GUARD_CNY,
    )
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
        'provider_reliability_repairs': [
            'NONEMPTY_DISPLAYABLE_FINAL_ANSWER_AFTER_REASONING',
            'OFFICIAL_FLASH_CANONICAL_RESPONSE_ALIAS',
        ],
    }


def verify_previous_terminal() -> dict:
    db_path = PREVIOUS / 'live/runtime.sqlite3'
    ensure(db_path.is_file(), 'repair_03 journal missing')
    db = sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        ensure(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'repair_03 SQLite integrity failure')
        counts = {row['status']: row['n'] for row in db.execute(
            'SELECT status,count(*) AS n FROM provider_calls GROUP BY status')}
        ensure(counts == {'RESPONSE_CAPTURED': 30, 'RESPONSE_REJECTED': 1},
               'repair_03 terminal counts differ from preserved failure')
        batch = db.execute('SELECT stopped FROM call_batches WHERE batch_id=?', (PREVIOUS_BATCH,)).fetchone()
        ensure(batch is not None and batch['stopped'] == 1, 'repair_03 is not terminal-stopped')
        active = db.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone()
        ensure(active is not None and active['value'] == '', 'repair_03 driver lease is not reconciled')
        ensure(db.execute("SELECT count(*) FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchone()[0] == 0,
               'repair_03 has unknown provider submissions')
        failed = db.execute(
            "SELECT slot_id,http_status,finish_reason,error_category,provider_model,raw_response,usage_json "
            "FROM provider_calls WHERE status='RESPONSE_REJECTED'").fetchone()
        ensure(failed is not None and failed['slot_id'] == 'N05_S1', 'repair_03 rejected slot changed')
        ensure(failed['http_status'] == 200 and failed['finish_reason'] == 'stop' and
               failed['error_category'] == 'PROVIDER_MODEL_MISMATCH' and failed['provider_model'] == 'deepseek-flash',
               'repair_03 Flash alias failure signature changed')
        raw = json.loads(failed['raw_response'])
        content = raw['choices'][0]['message'].get('content')
        ensure(isinstance(content, str) and content.strip(), 'repair_03 rejected Flash response no longer has displayable content')
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
                'requested_model': 'deepseek-v4-flash',
                'provider_model': failed['provider_model'],
                'final_content_nonempty': True,
            },
        }
    finally:
        db.close()


def load_revision():
    parent, cases, fixture, frozen = original.load_frozen()
    manifest = original.read_json(REV / 'REVISION.json')
    scope = original.read_json(REV / 'EXECUTION_SCOPE.json')
    ensure(original.file_sha(REV / 'EXECUTION_SCOPE.json') == manifest['scope_file_sha256'],
           'repair_04 scope bytes differ from manifest')
    ensure(manifest['parent_scope_file_sha256'] == frozen['scope_sha256'], 'repair_04 parent protocol changed')
    ensure(scope == revision_scope(parent), 'repair_04 scope differs beyond declared repair revision')
    ensure(manifest['previous_repair_batch_id'] == PREVIOUS_BATCH, 'repair_04 lineage changed')
    ensure(manifest['known_development_regression'] is True and manifest['new_heldout_claim'] is False,
           'repair_04 cannot claim heldout evaluation')
    ensure(manifest['total_guard_cny'] == TOTAL_GUARD_CNY and manifest['all_operations_guards_cny'] == ALL_OPERATIONS_GUARD_CNY,
           'repair_04 guard accounting changed')
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
    db = sqlite3.connect((original.LIVE / 'runtime.sqlite3').as_uri() + '?mode=ro', uri=True)
    try:
        ensure(db.execute('SELECT status,count(*) FROM provider_calls GROUP BY status').fetchall() == [('RESPONSE_CAPTURED', 82)],
               'Original82 journal is not wholly terminal')
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
        'older_terminal_evidence': [
            'evidence/R047-03/repair_01/live/runtime.sqlite3',
            'evidence/R047-03/repair_02/live/runtime.sqlite3',
        ],
        'repair_evidence': [
            'evidence/R047-03/provider_output_fix_20260911/README.md',
            'evidence/R047-03/provider_alias_fix_20260911/README.md',
        ],
        'continuation_policy': (
            'All prior repair batches stay stopped and immutable. repair_04 starts a '
            'fresh full82 denominator after provider compatibility code changed.'
        ),
    })
    dump(REV / 'OFFICIAL_PREFLIGHT.json', {
        'at_utc': datetime.now(timezone.utc).isoformat(),
        'evidence_kind': 'LIVE_OFFICIAL_DOCUMENTATION_AND_REAL_ALIAS_OBSERVATION_NOT_BILLING',
        'checked_date': '2026-09-11',
        'sources': [
            'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',
            'https://api-docs.deepseek.com/api/create-chat-completion/',
            'https://api-docs.deepseek.com/guides/thinking_mode/',
        ],
        'http_checks': {'pricing': 200, 'chat_completions': 200, 'thinking_mode': 200},
        'models_confirmed': [scope['primary_model'], scope['switch_model']],
        'flash_response_alias_confirmed': {
            'requested': 'deepseek-v4-flash',
            'returned': 'deepseek-flash',
            'evidence_batch': PREVIOUS_BATCH,
            'evidence_slot': 'N05_S1',
        },
        'thinking': scope['thinking'],
        'reasoning_effort': scope['reasoning_effort'],
        'peak_rates_cny_per_million_tokens': scope['peak_rates_cny_per_million_tokens'],
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
    ensure(action in {'prepare', 'execute', 'audit', 'review'}, 'Unsupported repair_04 action')
    if action == 'prepare':
        ensure(not rest, 'Preparation does not accept extra arguments')
        ensure(not LIVE.exists(), 'Existing repair_04 runtime must be reconciled; preparation is never repeated')
        dump(REV / 'PREPARE_INTENT.json', {
            'pid': os.getpid(), 'started_at_utc': datetime.now(timezone.utc).isoformat(),
            'scope_sha256': original.file_sha(REV / 'EXECUTION_SCOPE.json')})
    if action == 'execute':
        completed = original.read_json(REV / 'PREPARE_COMPLETE.json')
        ensure(completed['fixture_preparation_sha256'] == original.file_sha(LIVE / 'FIXTURE_PREPARATION.json'),
               'repair_04 preparation binding changed')
        official = original.read_json(REV / 'OFFICIAL_PREFLIGHT.json')
        scope = load_revision()[0]
        ensure(official['frozen_scope_parameters_changed'] is False and
               official['peak_rates_cny_per_million_tokens'] == scope['peak_rates_cny_per_million_tokens'],
               'repair_04 official pricing evidence differs')
        ensure(official['models_confirmed'] == [scope['primary_model'], scope['switch_model']],
               'repair_04 official model verification differs')
        ensure(official['thinking'] == scope['thinking'] and official['reasoning_effort'] == scope['reasoning_effort'],
               'repair_04 thinking contract differs')
    module_name = {'prepare': 'prepare_execution_r047', 'execute': 'execute_r047',
                   'audit': 'audit_captures_r047', 'review': 'compile_reviews_r047'}[action]
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
            ensure(preflight['passed'] and preflight['target_calls'] == 0, 'repair_04 preparation did not complete')
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
