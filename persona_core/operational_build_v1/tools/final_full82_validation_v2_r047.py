"""Second clean full82 validation after final_full82_01 stopped on a definitive empty response.

The parent failure is preserved as a terminal RESPONSE_REJECTED, never retried
or rewritten. This revision uses a fresh runtime/batch/call identity while
keeping the same frozen 82 inputs, 328 semantic criteria, model roles,
thinking profile and quality thresholds. Creation/preparation are zero-call;
execution again requires an exact >=20 CNY user authorization.
"""
from __future__ import annotations

import argparse, copy, importlib, json, os, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

import r047_execution_common as common
import repair_revision_r047_v6 as capacity
import unknown_quarantine_r047 as unknowns

ROOT, PLAN = common.ROOT, common.PLAN
REV = PLAN / 'evidence/R047-03/final_full82_02'
LIVE = REV / 'live'
BATCH = 'APCORE-R047-FINAL-FULL82-02'
GUARD_CNY = 125
AGGREGATE_GUARD_CNY = 743.5
TARGETED = PLAN / 'evidence/R047-03/TARGETED_DIAGNOSTIC_CLOSEOUT.json'
PARENT = PLAN / 'evidence/R047-03/final_full82_01'
PARENT_FAILURE = PARENT / 'TERMINAL_FAILURE.json'
ensure = common.ensure


def dump(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def fixed_scope():
    parent, cases, fixture, frozen = common.load_frozen()
    scope = copy.deepcopy(capacity.revision_scope(parent))
    scope.update(
        batch_id=BATCH,
        purpose=(
            'Second clean final full82/328 known-development validation after '
            'final_full82_01 terminal EMPTY_RESPONSE; no parent call or slot is retried.'
        ),
        total_guard_cny=GUARD_CNY,
        all_operations_r045_plus_r047_guard_cny=AGGREGATE_GUARD_CNY,
    )
    rates = scope['peak_rates_cny_per_million_tokens']
    scope['reserved_upper_micro_cny'] = sum(
        (scope['max_input_bytes'] + scope['input_overhead_reserve_tokens']) * rates[s['model']]['input_miss']
        + scope['max_output_tokens'] * rates[s['model']]['output']
        for s in scope['slots'])
    common.scope_check(scope)
    ensure(len(scope['slots']) == 82, 'Final02 frozen denominator changed')
    ensure(sum(s['model'] == 'deepseek-v4-flash' for s in scope['slots']) == 76, 'Final02 Flash denominator changed')
    ensure(sum(s['model'] == 'deepseek-v4-pro' for s in scope['slots']) == 6, 'Final02 Pro denominator changed')
    ensure(scope['reserved_upper_micro_cny'] <= GUARD_CNY * 1_000_000, 'Final02 reserve exceeds guard')
    return scope, cases, fixture, frozen


def parent_failure() -> dict:
    proof = common.read_json(PARENT_FAILURE)
    ensure(proof['status'] == 'TERMINAL_STOPPED_ON_DEFINITIVE_EMPTY_RESPONSE', 'Parent terminal class changed')
    ensure(proof['batch_id'] == 'APCORE-R047-FINAL-FULL82-01', 'Wrong parent batch')
    journal = ROOT / proof['journal']
    audit = ROOT / proof['capture_audit']
    ensure(common.file_sha(journal) == proof['journal_sha256'], 'Parent final01 journal changed')
    ensure(common.file_sha(audit) == proof['capture_audit_sha256'], 'Parent final01 audit changed')
    db = sqlite3.connect(journal.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        ensure(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'Parent final01 journal integrity failure')
        counts = dict(db.execute('SELECT status,count(*) FROM provider_calls GROUP BY status').fetchall())
        ensure(counts == {'RESPONSE_CAPTURED': 5, 'RESPONSE_REJECTED': 1}, 'Parent final01 counts changed')
        batch = db.execute('SELECT stopped FROM call_batches WHERE batch_id=?', (proof['batch_id'],)).fetchone()
        ensure(batch is not None and batch[0] == 1, 'Parent final01 must stay stopped')
        driver = db.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone()
        ensure(driver is None or driver[0] == '', 'Parent final01 still has active driver')
        row = db.execute(
            "SELECT p.call_id,p.status,p.http_status,p.finish_reason,p.error_category,p.request_sha256,p.raw_sha256,"
            "p.usage_json,p.estimate_peak_micro_cny,p.reserve_micro_cny,t.status AS turn_status,t.assistant_text "
            "FROM provider_calls p JOIN turns t USING(turn_id) WHERE p.batch_id=? AND p.slot_id='N01_T6'",
            (proof['batch_id'],)).fetchone()
        ensure(row is not None and row['call_id'] == proof['failed_call_id'], 'Parent failed call identity changed')
        ensure(row['status'] == 'RESPONSE_REJECTED' and row['turn_status'] == 'RESPONSE_REJECTED', 'Parent failed slot status changed')
        ensure(row['http_status'] == 200 and row['finish_reason'] == 'stop' and row['error_category'] == 'EMPTY_RESPONSE',
               'Parent failure is no longer the recorded definitive empty response')
        ensure(row['assistant_text'] is None, 'Parent rejected turn unexpectedly has assistant text')
        ensure(row['request_sha256'] == proof['request_sha256'] and row['raw_sha256'] == proof['raw_response_sha256'],
               'Parent request/raw binding changed')
        usage = json.loads(row['usage_json'])
        ensure(usage['completion_tokens'] == proof['usage']['completion_tokens']
               and usage['completion_tokens_details']['reasoning_tokens'] == proof['usage']['reasoning_tokens'],
               'Parent failure usage changed')
        ensure(row['estimate_peak_micro_cny'] == proof['failed_call_peak_usage_estimate_micro_cny']
               and row['reserve_micro_cny'] == proof['failed_call_reserve_micro_cny'],
               'Parent failure accounting changed')
        ensure(db.execute("SELECT count(*) FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchone()[0] == 0,
               'Parent final01 unexpectedly contains UNKNOWN')
    finally:
        db.close()
    audit_value = common.read_json(audit)
    ensure(audit_value['status_counts'] == {'NOT_SUBMITTED': 76, 'RESPONSE_CAPTURED': 5, 'RESPONSE_REJECTED': 1},
           'Parent audit denominator changed')
    ensure(audit_value['binding_findings'] == [] and audit_value['complete_captures_and_delivery'] is False,
           'Parent failed audit was upgraded or corrupted')
    return {
        'path': PARENT_FAILURE.relative_to(ROOT).as_posix(),
        'sha256': common.file_sha(PARENT_FAILURE),
        'journal_sha256': proof['journal_sha256'],
        'audit_sha256': proof['capture_audit_sha256'],
        'failed_slot': 'N01_T6',
        'error_category': 'EMPTY_RESPONSE',
        'captured': 5,
        'rejected': 1,
        'not_submitted': 76,
        'unknown': 0,
    }


def targeted_closeout() -> dict:
    result = common.read_json(TARGETED)
    ensure(result['status'] == 'TARGETED_DIAGNOSTICS_PASS', 'Targeted diagnostics are not closed')
    ensure((result['reviewed_turns'], result['criterion_denominator'], result['criterion_pass']) == (38, 152, 152),
           'Targeted diagnostic denominator/pass count changed')
    ensure(not result['open_blocking_findings'] and result['full82_acceptance_claim'] is False,
           'Targeted diagnostics still have blockers or claim final acceptance')
    for row in result['cases']:
        ensure(common.file_sha(ROOT / row['journal']) == row['journal_sha256'], 'Targeted journal changed: ' + row['case_id'])
        ensure(common.file_sha(ROOT / row['review']) == row['review_sha256'], 'Targeted review changed: ' + row['case_id'])
    return {'path': TARGETED.relative_to(ROOT).as_posix(), 'sha256': common.file_sha(TARGETED),
            'reviewed_turns': 38, 'criteria': 152, 'pass': 152}


def current_regression() -> dict:
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
        if set(report.get('sources', {})) == set(current) and all(report['sources'][k] == v for k, v in current.items()):
            return {'path': path.relative_to(ROOT).as_posix(), 'sha256': common.file_sha(path), 'tests': report['tests']}
    raise common.StoreGuard('No current-source regression binds final02 full82')


def readiness(require_regression: bool = True) -> dict:
    unknown_status = unknowns.ensure_new_independent_batch_allowed()
    ensure(not unknown_status['active_unresolved_remote_unknowns'], 'Active remote UNKNOWN blocks final02')
    result = {
        'unknown_policy': unknown_status,
        'targeted_closeout': targeted_closeout(),
        'parent_final01_failure': parent_failure(),
    }
    if require_regression:
        result['current_regression'] = current_regression()
    return result


def execution_authorization(scope: dict) -> dict:
    path = REV / 'EXECUTION_AUTHORIZATION.json'
    ensure(path.is_file(), 'Explicit >=20 CNY final02 authorization required')
    auth = common.read_json(path)
    ensure(auth.get('approved') is True and auth.get('batch_id') == BATCH, 'Final02 authorization does not bind this batch')
    ensure(auth.get('guard_cny') == GUARD_CNY
           and auth.get('reserved_upper_micro_cny') == scope['reserved_upper_micro_cny']
           and auth.get('fixed_calls') == 82 and auth.get('automatic_paid_retries') == 0,
           'Final02 authorization parameters changed')
    return auth


def load(prepare: bool = False):
    scope, cases, fixture, frozen = fixed_scope()
    manifest = common.read_json(REV / 'MANIFEST.json')
    ensure(common.read_json(REV / 'EXECUTION_SCOPE.json') == scope
           and common.file_sha(REV / 'EXECUTION_SCOPE.json') == manifest['scope_sha256'], 'Final02 scope changed')
    ensure(manifest['fixed_calls'] == 82 and manifest['guard_cny'] == GUARD_CNY, 'Final02 manifest denominator/guard changed')
    ensure(manifest['parent_final01_failure'] == parent_failure(), 'Final02 parent failure binding changed')
    return scope, copy.deepcopy(cases), fixture, {**frozen, 'scope_sha256': manifest['scope_sha256'],
        'current_evaluation_classification': 'KNOWN_DEVELOPMENT_REGRESSION',
        'known_development_regression': True, 'new_heldout_claim': False}


def create() -> int:
    ready = readiness()
    scope, _, _, frozen = fixed_scope()
    ensure(not REV.exists(), 'Final02 revision already exists')
    REV.mkdir(parents=True)
    dump(REV / 'EXECUTION_SCOPE.json', scope)
    dump(REV / 'MANIFEST.json', {
        'batch_id': BATCH,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope_sha256': common.file_sha(REV / 'EXECUTION_SCOPE.json'),
        'parent_frozen_scope_sha256': frozen['scope_sha256'],
        'fixed_calls': 82,
        'main_flash_calls': 76,
        'switch_pro_calls': 6,
        'guard_cny': GUARD_CNY,
        'aggregate_guard_cny': AGGREGATE_GUARD_CNY,
        'reserved_upper_micro_cny': scope['reserved_upper_micro_cny'],
        'readiness': ready,
        'parent_final01_failure': ready['parent_final01_failure'],
        'known_development_regression': True,
        'new_heldout_claim': False,
        'automatic_paid_retries': 0,
        'automatic_next_revision': False,
        'full82_acceptance_claim': False,
        'execution_requires_explicit_user_confirmation': True,
        'parent_failed_slot_resend_allowed': False,
        'review_contract': 'After all82 captured/displayed, review all328 original frozen criteria and original quality targets; no missing/unknown/rejected slot may pass.',
    })
    parent_official = common.read_json(PARENT / 'OFFICIAL_PREFLIGHT.json')
    dump(REV / 'OFFICIAL_PREFLIGHT.json', {
        **parent_official,
        'at_utc': datetime.now(timezone.utc).isoformat(),
        'same_date_source_evidence_reused_from': (PARENT / 'OFFICIAL_PREFLIGHT.json').relative_to(ROOT).as_posix(),
        'same_date_source_evidence_sha256': common.file_sha(PARENT / 'OFFICIAL_PREFLIGHT.json'),
        'execution_recheck_complete': True,
        'billing_verified': False,
    })
    print(json.dumps({'output': REV.relative_to(ROOT).as_posix(), 'calls': 82,
                      'reserve_micro_cny': scope['reserved_upper_micro_cny'], 'guard_cny': GUARD_CNY,
                      'aggregate_guard_cny': AGGREGATE_GUARD_CNY, 'target_calls': 0}, ensure_ascii=False))
    return 0


def dispatch(action: str, rest: list[str]) -> int:
    scope, _, _, _ = load()
    pinned = common.read_json(REV / 'MANIFEST.json')['readiness']
    # Creation/execution of a paid batch must fail closed on any active remote
    # UNKNOWN. Read-only audit of an already stopped batch must remain possible
    # precisely so that such a terminal failure can be preserved and reviewed.
    if action in {'prepare', 'execute'}:
        now = readiness()
        ensure(now['targeted_closeout'] == pinned['targeted_closeout'], 'Targeted closeout changed after final02 freeze')
        ensure(now['parent_final01_failure'] == pinned['parent_final01_failure'], 'Parent final01 failure changed')
        ensure(not now['unknown_policy']['active_unresolved_remote_unknowns'], 'New active remote UNKNOWN appeared')
    if action == 'prepare':
        ensure(not rest and not LIVE.exists(), 'Existing final02 runtime cannot be prepared twice')
        dump(REV / 'PREPARE_INTENT.json', {'pid': os.getpid(), 'at_utc': datetime.now(timezone.utc).isoformat()})
    if action == 'execute':
        execution_authorization(scope)
        prepared = common.read_json(REV / 'PREPARE_COMPLETE.json')
        ensure(prepared['fixture_preparation_sha256'] == common.file_sha(LIVE / 'FIXTURE_PREPARATION.json'), 'Final02 preparation changed')
        official = common.read_json(REV / 'OFFICIAL_PREFLIGHT.json')
        ensure(official['checked_date'] == datetime.now(timezone.utc).date().isoformat()
               and official['execution_recheck_complete'] is True, 'Final02 provider recheck stale/incomplete')
    module = importlib.import_module({'prepare': 'prepare_execution_r047', 'execute': 'execute_r047', 'audit': 'audit_captures_r047'}[action])
    replacement = {'PLAN': REV, 'LIVE': LIVE, 'load_frozen': lambda: load(prepare=action == 'prepare')}
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
            ensure(preflight['passed'] and preflight['target_calls'] == 0, 'Final02 preparation failed')
            dump(REV / 'PREPARE_COMPLETE.json', {
                'fixture_preparation_sha256': common.file_sha(LIVE / 'FIXTURE_PREPARATION.json'),
                'new_target_calls': 0,
            })
        return result or 0
    finally:
        for path in set(REV.rglob('*.json')) - before:
            if path.name == 'CAPTURE_AUDIT.json' or path.name.endswith('_REVIEW_INPUT.json'):
                value = common.read_json(path)
                value.update(full82_acceptance_claim=True, new_heldout_claim=False,
                             known_development_regression=True, diagnostic_fixed_slots=82, batch_id=BATCH)
                path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        for key, value in previous.items():
            setattr(module, key, value)
        sys.argv = old_args


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['create', 'prepare', 'execute', 'audit'])
    args, rest = parser.parse_known_args()
    if args.action == 'create':
        ensure(not rest, 'Create accepts no extras')
        return create()
    return dispatch(args.action, rest)


if __name__ == '__main__':
    raise SystemExit(main())
