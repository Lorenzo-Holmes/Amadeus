"""Fresh final05 full82 batch after final04 stopped on remote UNKNOWN.

Final05 preserves final04's repaired source, exact 82 inputs, 328 criteria,
76 Flash + 6 Pro roles, 16K output budget and 25 CNY guard.  The only runtime
capacity change is a 600-second owned-worker deadline under scope-v3, intended
to reduce transport ambiguity for long max-reasoning responses.  It is not a
retry of the final04 slot: final04 remains stopped and quarantined forever.
"""
from __future__ import annotations

import argparse, copy, importlib, json, os, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

import r047_execution_common as common
import unknown_quarantine_r047 as unknowns
import final_full82_validation_v4_r047 as final04

ROOT, PLAN = common.ROOT, common.PLAN
REV = PLAN / 'evidence/R047-03/final_full82_05'
LIVE = REV / 'live'
BATCH = 'APCORE-R047-FINAL-FULL82-05'
GUARD_CNY = 25
RESERVE_MICRO_CNY = 24_256_512
PARENT = PLAN / 'evidence/R047-03/final_full82_04'
PARENT_FAILURE = PARENT / 'TERMINAL_FAILURE.json'
PARENT_QUARANTINE = PLAN / 'evidence/R047-03/unknown_quarantine_final04_20260912/QUARANTINE.json'
ensure = common.ensure


def dump(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def fixed_scope():
    scope, cases, fixture, frozen = final04.fixed_scope()
    scope = copy.deepcopy(scope)
    scope.update(
        schema_version='apcore-provider-scope-3',
        batch_id=BATCH,
        purpose=('Fresh full82/328 repaired-source validation after final04 terminal remote UNKNOWN. '
                 'No final04 call or slot is retried; owned-worker deadline increased only.'),
        request_timeout_seconds=600,
        total_guard_cny=GUARD_CNY,
        automatic_paid_retries=0,
        capacity_policy_id='EXTENDED_MAX_REASONING_20260911',
        output_budget_includes_reasoning=True,
        automatic_capacity_escalation=False,
    )
    rates = scope['peak_rates_cny_per_million_tokens']
    scope['reserved_upper_micro_cny'] = sum(
        (scope['max_input_bytes'] + scope['input_overhead_reserve_tokens']) * rates[s['model']]['input_miss']
        + scope['max_output_tokens'] * rates[s['model']]['output'] for s in scope['slots'])
    common.scope_check(scope)
    ensure(len(scope['slots']) == 82, 'Final05 denominator changed')
    ensure(sum(s['model'] == 'deepseek-v4-flash' for s in scope['slots']) == 76, 'Final05 Flash count changed')
    ensure(sum(s['model'] == 'deepseek-v4-pro' for s in scope['slots']) == 6, 'Final05 Pro count changed')
    ensure(scope['reserved_upper_micro_cny'] == RESERVE_MICRO_CNY, 'Final05 reserve changed')
    ensure(scope['reserved_upper_micro_cny'] <= GUARD_CNY * 1_000_000, 'Final05 reserve exceeds guard')
    return scope, cases, fixture, frozen


def parent_failure() -> dict:
    proof = common.read_json(PARENT_FAILURE)
    ensure(proof['status'] == 'TERMINAL_STOPPED_23_CAPTURED_1_REMOTE_UNKNOWN_58_NOT_SUBMITTED',
           'Final04 terminal class changed')
    ensure(proof['batch_id'] == 'APCORE-R047-FINAL-FULL82-04' and proof['failed_slot'] == 'N04_T6',
           'Final04 failed identity changed')
    journal = ROOT / proof['journal']
    audit = ROOT / proof['capture_audit']
    ensure(common.file_sha(journal) == proof['journal_sha256'], 'Final04 journal changed')
    ensure(common.file_sha(audit) == proof['capture_audit_sha256'], 'Final04 audit changed')
    q = common.read_json(PARENT_QUARANTINE)
    ensure(q['call_id'] == proof['failed_call_id'] and q['classification'] == 'QUARANTINED_REMOTE_UNKNOWN',
           'Final04 quarantine identity changed')
    ensure(q['resend_allowed'] is False and q['old_batch_resume_allowed'] is False,
           'Final04 quarantine retry boundary changed')
    db = sqlite3.connect(journal.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        ensure(dict(db.execute('SELECT status,count(*) FROM provider_calls GROUP BY status').fetchall())
               == {'RESPONSE_CAPTURED': 23, 'SUBMITTED_STATUS_UNKNOWN': 1}, 'Final04 journal counts changed')
        batch = db.execute('SELECT stopped FROM call_batches WHERE batch_id=?', (proof['batch_id'],)).fetchone()
        ensure(batch is not None and batch[0] == 1, 'Final04 batch must stay stopped')
        driver = db.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone()
        ensure(driver is None or driver[0] == '', 'Final04 driver still active')
        row = db.execute("SELECT p.*,t.status AS turn_status,t.assistant_text FROM provider_calls p JOIN turns t USING(turn_id) WHERE p.call_id=?",
                         (proof['failed_call_id'],)).fetchone()
        ensure(row is not None and row['status'] == 'SUBMITTED_STATUS_UNKNOWN'
               and row['turn_status'] == 'SUBMITTED_STATUS_UNKNOWN' and row['assistant_text'] is None,
               'Final04 UNKNOWN row changed')
        ensure(row['http_status'] is None and row['raw_sha256'] is None and row['usage_json'] is None,
               'Final04 UNKNOWN unexpectedly acquired provider result')
    finally:
        db.close()
    return {
        'path': PARENT_FAILURE.relative_to(ROOT).as_posix(),
        'sha256': common.file_sha(PARENT_FAILURE),
        'quarantine': PARENT_QUARANTINE.relative_to(ROOT).as_posix(),
        'quarantine_sha256': common.file_sha(PARENT_QUARANTINE),
        'failed_call_id': proof['failed_call_id'],
        'failed_slot': 'N04_T6',
        'captured': 23,
        'unknown': 1,
        'not_submitted': 58,
    }


def current_regression() -> dict:
    current = {p.relative_to(ROOT).as_posix(): common.file_sha(p)
               for p in sorted((ROOT / 'persona_core/operational_runtime_v1').glob('*.py'))
               + sorted((PLAN / 'tools').glob('*.py'))}
    for directory in sorted((PLAN / 'evidence/R047-03').glob('regression_*'), reverse=True):
        path = directory / 'REGRESSION.json'
        if not path.is_file():
            continue
        report = common.read_json(path)
        if (report.get('passed') and report.get('protected_history_and_production_unchanged')
                and report.get('target_calls') == 0 and set(report.get('sources', {})) == set(current)
                and all(report['sources'][k] == v for k, v in current.items())):
            return {'path': path.relative_to(ROOT).as_posix(), 'sha256': common.file_sha(path), 'tests': report['tests']}
    raise common.StoreGuard('No current-source regression binds final05')


def readiness(require_regression: bool = True) -> dict:
    status = unknowns.ensure_new_independent_batch_allowed()
    ensure(not status['active_unresolved_remote_unknowns'], 'Active remote UNKNOWN blocks final05')
    result = {'unknown_policy': status, 'repair_evidence': final04.repair_evidence(),
              'parent_final04_failure': parent_failure()}
    if require_regression:
        result['current_regression'] = current_regression()
    return result


def execution_authorization(scope: dict) -> dict:
    path = REV / 'EXECUTION_AUTHORIZATION.json'
    ensure(path.is_file(), 'Final05 user execution authorization record required')
    auth = common.read_json(path)
    ensure(auth.get('approved') is True and auth.get('batch_id') == BATCH, 'Final05 authorization batch mismatch')
    ensure(auth.get('guard_cny') == GUARD_CNY and auth.get('reserved_upper_micro_cny') == scope['reserved_upper_micro_cny']
           and auth.get('fixed_calls') == 82 and auth.get('automatic_paid_retries') == 0,
           'Final05 authorization parameters changed')
    ensure(auth.get('authorization_basis') == 'USER_STANDING_EXECUTION_OVERRIDE_2026-09-12',
           'Final05 authorization basis changed')
    return auth


def load(prepare: bool = False):
    scope, cases, fixture, frozen = fixed_scope()
    manifest = common.read_json(REV / 'MANIFEST.json')
    ensure(common.read_json(REV / 'EXECUTION_SCOPE.json') == scope, 'Final05 scope changed')
    ensure(common.file_sha(REV / 'EXECUTION_SCOPE.json') == manifest['scope_sha256'], 'Final05 scope hash changed')
    ensure(manifest['parent_final04_failure'] == parent_failure(), 'Final05 parent binding changed')
    return scope, copy.deepcopy(cases), fixture, {
        **frozen,
        'scope_sha256': manifest['scope_sha256'],
        'current_evaluation_classification': 'KNOWN_DEVELOPMENT_REPAIRED_FULL82',
        'known_development_regression': True,
        'new_heldout_claim': False,
    }


def create() -> int:
    ready = readiness()
    scope, _, _, frozen = fixed_scope()
    ensure(not REV.exists(), 'Final05 already exists')
    REV.mkdir(parents=True)
    dump(REV / 'EXECUTION_SCOPE.json', scope)
    dump(REV / 'MANIFEST.json', {
        'batch_id': BATCH,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope_sha256': common.file_sha(REV / 'EXECUTION_SCOPE.json'),
        'parent_frozen_scope_sha256': frozen['scope_sha256'],
        'fixed_calls': 82, 'flash_calls': 76, 'pro_calls': 6,
        'guard_cny': GUARD_CNY, 'reserved_upper_micro_cny': scope['reserved_upper_micro_cny'],
        'request_timeout_seconds': 600,
        'readiness': ready,
        'repair_evidence': ready['repair_evidence'],
        'parent_final04_failure': ready['parent_final04_failure'],
        'known_development_regression': True, 'new_heldout_claim': False,
        'full82_acceptance_claim': True, 'automatic_paid_retries': 0,
        'automatic_next_revision': False,
    })
    previous = common.read_json(final04.REV / 'OFFICIAL_PREFLIGHT.json')
    now = datetime.now(timezone.utc)
    dump(REV / 'OFFICIAL_PREFLIGHT.json', {
        **previous,
        'checked_date': now.date().isoformat(),
        'at_utc': now.isoformat(),
        'chosen_max_output_tokens': 16384,
        'execution_recheck_complete': True,
        'frozen_scope_parameters_changed': False,
        'billing_verified': False,
    })
    print(json.dumps({'output': REV.relative_to(ROOT).as_posix(), 'calls': 82,
                      'reserve_micro_cny': scope['reserved_upper_micro_cny'], 'guard_cny': GUARD_CNY,
                      'timeout_seconds': 600, 'target_calls': 0}, ensure_ascii=False))
    return 0


def dispatch(action: str, rest: list[str]) -> int:
    scope, _, _, _ = load()
    pinned = common.read_json(REV / 'MANIFEST.json')['readiness']
    if action in {'prepare', 'execute'}:
        now = readiness()
        ensure(now['repair_evidence'] == pinned['repair_evidence'], 'Repair evidence changed after final05 freeze')
        ensure(now['parent_final04_failure'] == pinned['parent_final04_failure'], 'Final04 failure changed after final05 freeze')
        ensure(not now['unknown_policy']['active_unresolved_remote_unknowns'], 'New active remote UNKNOWN appeared')
    if action == 'prepare':
        ensure(not rest and not LIVE.exists(), 'Existing final05 runtime cannot be prepared twice')
        dump(REV / 'PREPARE_INTENT.json', {'pid': os.getpid(), 'at_utc': datetime.now(timezone.utc).isoformat()})
    if action == 'execute':
        execution_authorization(scope)
        prepared = common.read_json(REV / 'PREPARE_COMPLETE.json')
        ensure(prepared['fixture_preparation_sha256'] == common.file_sha(LIVE / 'FIXTURE_PREPARATION.json'),
               'Final05 preparation changed')
        official = common.read_json(REV / 'OFFICIAL_PREFLIGHT.json')
        ensure(official['checked_date'] == datetime.now(timezone.utc).date().isoformat()
               and official['execution_recheck_complete'] is True, 'Final05 provider recheck stale/incomplete')
    module = importlib.import_module({'prepare': 'prepare_execution_r047', 'execute': 'execute_r047',
                                      'audit': 'audit_captures_r047', 'review': 'compile_reviews_r047'}[action])
    replacement = {'PLAN': REV, 'LIVE': LIVE, 'load_frozen': lambda: load(prepare=action == 'prepare')}
    if action == 'execute':
        replacement['OFFICIAL_PREFLIGHT_PATH'] = REV / 'OFFICIAL_PREFLIGHT.json'
    previous = {key: getattr(module, key) for key in replacement}
    old_args, before = sys.argv, set(REV.rglob('*.json'))
    try:
        for key, value in replacement.items(): setattr(module, key, value)
        sys.argv = [module.__name__] + rest
        result = module.main()
        if action == 'prepare':
            saved = common.read_json(LIVE / 'FIXTURE_PREPARATION.json')
            preflight = common.read_json(ROOT / saved['preflight_path'] / 'PREFLIGHT.json')
            ensure(preflight['passed'] and preflight['target_calls'] == 0, 'Final05 preparation failed')
            dump(REV / 'PREPARE_COMPLETE.json', {'fixture_preparation_sha256': common.file_sha(LIVE / 'FIXTURE_PREPARATION.json'),
                                                  'new_target_calls': 0})
        return result or 0
    finally:
        for path in set(REV.rglob('*.json')) - before:
            if (path.name in {'CAPTURE_AUDIT.json', 'QUALITY_AND_COVERAGE.json', 'REVIEW_BINDING_REPORT.json'}
                    or path.name.endswith('_REVIEW_INPUT.json')):
                value = common.read_json(path)
                value.update(full82_acceptance_claim=True, new_heldout_claim=False,
                             known_development_regression=True, diagnostic_fixed_slots=82, batch_id=BATCH)
                path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        for key, value in previous.items(): setattr(module, key, value)
        sys.argv = old_args


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['create','prepare','execute','audit','review'])
    args, rest = parser.parse_known_args()
    if args.action == 'create':
        ensure(not rest, 'Create accepts no extras')
        return create()
    return dispatch(args.action, rest)


if __name__ == '__main__':
    raise SystemExit(main())
