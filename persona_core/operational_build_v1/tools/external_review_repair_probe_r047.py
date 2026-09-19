"""Bounded 44-turn repair probe for R047-04 independent-review failures.

Uses the exact final03 user inputs and provider roles for the seven affected
cases. It runs in a fresh sandbox/batch, never mutates the natural-day
candidate, never retries paid calls automatically, and never claims product
acceptance. The smaller response budget keeps the logical guard below the
user's 20 CNY confirmation threshold while remaining well above observed
answer lengths.
"""
from __future__ import annotations

import argparse, copy, importlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

import r047_execution_common as common
import unknown_quarantine_r047 as unknowns

ROOT, PLAN = common.ROOT, common.PLAN
REV = PLAN / 'evidence/R047-04/external_review_repair_probe_03'
LIVE = REV / 'live'
BATCH = 'APCORE-R047-EXTERNAL-REPAIR-PROBE-03'
CASE_IDS = ('N02', 'N04', 'N06', 'N07', 'N08', 'N09', 'N11')
FINAL03 = PLAN / 'evidence/R047-03/final_full82_03'
RETURN_AUDIT = PLAN / 'evidence/R047-04/independent_review_return_20260911/RETURN_AUDIT.json'
PARENT_UNKNOWN_CALL = 'call_1c8d685185f34c149a4e6588ebbbd9eb'
GUARD_CNY = 15
ensure = common.ensure


def dump(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def fixed_scope() -> tuple[dict, dict, dict, dict]:
    _, cases, fixture, frozen = common.load_frozen()
    scope = copy.deepcopy(common.read_json(FINAL03 / 'EXECUTION_SCOPE.json'))
    scope.update(
        schema_version='apcore-provider-scope-2',
        batch_id=BATCH,
        purpose=('Known-development repair probe for the seven cases implicated by the '
                 'returned independent review. Exact final03 inputs/provider roles; no acceptance claim.'),
        max_input_bytes=32768,
        max_output_tokens=16384,
        request_timeout_seconds=240,
        total_guard_cny=GUARD_CNY,
        automatic_paid_retries=0,
    )
    for key in ('capacity_policy_id', 'output_budget_includes_reasoning', 'automatic_capacity_escalation'):
        scope.pop(key, None)
    scope['slots'] = [s for s in scope['slots'] if s.get('case_id') in CASE_IDS]
    rates = scope['peak_rates_cny_per_million_tokens']
    scope['reserved_upper_micro_cny'] = sum(
        (scope['max_input_bytes'] + scope['input_overhead_reserve_tokens']) * rates[s['model']]['input_miss']
        + scope['max_output_tokens'] * rates[s['model']]['output'] for s in scope['slots'])
    common.scope_check(scope)
    ensure(len(scope['slots']) == 44, 'Repair probe denominator changed')
    ensure(sum(s['model'] == 'deepseek-v4-flash' for s in scope['slots']) == 42, 'Repair probe Flash count changed')
    ensure(sum(s['model'] == 'deepseek-v4-pro' for s in scope['slots']) == 2, 'Repair probe Pro count changed')
    ensure(scope['reserved_upper_micro_cny'] == 12_386_304, 'Repair probe reserve changed')
    ensure(scope['reserved_upper_micro_cny'] <= GUARD_CNY * 1_000_000 < 20_000_000,
           'Repair probe exceeds no-confirmation guard boundary')
    selected = copy.deepcopy(cases)
    selected['cases'] = [c for c in selected['cases'] if c['id'] in CASE_IDS]
    ensure([c['id'] for c in selected['cases']] == list(CASE_IDS), 'Repair probe case order changed')
    return scope, selected, fixture, frozen


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
                and report.get('target_calls') == 0
                and set(report.get('sources', {})) == set(current)
                and all(report['sources'][k] == v for k, v in current.items())):
            return {'path': path.relative_to(ROOT).as_posix(), 'sha256': common.file_sha(path), 'tests': report['tests']}
    raise common.StoreGuard('No current-source regression binds external repair probe')


def readiness(require_regression: bool = True) -> dict:
    review = common.read_json(RETURN_AUDIT)
    ensure(review['overall_conclusion'] == 'FAIL', 'Independent review is no longer a failed repair input')
    ensure(review['semantic_results']['verdict_counts'] == {'PASS': 319, 'FAIL': 9}, 'Independent review verdicts changed')
    ensure(review['quality_results']['all_quality_targets_met'] is False, 'Independent review quality result changed')
    status = unknowns.ensure_new_independent_batch_allowed()
    ensure(not status['active_unresolved_remote_unknowns'], 'Active remote UNKNOWN blocks repair probe')
    parent = [row for row in status['allowed_historical_unknowns']
              if row.get('call_id') == PARENT_UNKNOWN_CALL
              and row.get('classification') == 'QUARANTINED_REMOTE_UNKNOWN']
    ensure(len(parent) == 1 and parent[0]['resend_allowed'] is False,
           'Probe02 N07_T1 remote UNKNOWN is not uniquely quarantined')
    result = {
        'independent_review_return_audit_sha256': common.file_sha(RETURN_AUDIT),
        'unknown_policy': status,
        'parent_probe02_unknown_quarantine': {
            'call_id': PARENT_UNKNOWN_CALL,
            'manifest': parent[0]['manifest'],
            'manifest_sha256': parent[0]['manifest_sha256'],
        },
    }
    if require_regression:
        result['current_regression'] = current_regression()
    return result


def load(prepare: bool = False):
    scope, cases, fixture, frozen = fixed_scope()
    if prepare:
        _, all_cases, _, _ = common.load_frozen()
        cases = copy.deepcopy(all_cases)
    manifest = common.read_json(REV / 'MANIFEST.json')
    ensure(common.read_json(REV / 'EXECUTION_SCOPE.json') == scope, 'Repair probe scope changed')
    ensure(common.file_sha(REV / 'EXECUTION_SCOPE.json') == manifest['scope_sha256'], 'Repair probe scope hash changed')
    return scope, cases, fixture, {
        **frozen,
        'scope_sha256': manifest['scope_sha256'],
        'current_evaluation_classification': 'KNOWN_DEVELOPMENT_REPAIR_PROBE',
        'known_development_regression': True,
        'new_heldout_claim': False,
    }


def create() -> int:
    ready = readiness()
    scope, _, _, frozen = fixed_scope()
    ensure(not REV.exists(), 'Repair probe already exists')
    REV.mkdir(parents=True)
    dump(REV / 'EXECUTION_SCOPE.json', scope)
    dump(REV / 'MANIFEST.json', {
        'batch_id': BATCH,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope_sha256': common.file_sha(REV / 'EXECUTION_SCOPE.json'),
        'parent_frozen_scope_sha256': frozen['scope_sha256'],
        'fixed_calls': 44,
        'case_ids': list(CASE_IDS),
        'flash_calls': 42,
        'pro_calls': 2,
        'guard_cny': GUARD_CNY,
        'reserved_upper_micro_cny': scope['reserved_upper_micro_cny'],
        'readiness': ready,
        'known_development_regression': True,
        'new_heldout_claim': False,
        'full82_acceptance_claim': False,
        'automatic_paid_retries': 0,
        'automatic_next_revision': False,
        'execution_requires_new_user_confirmation': False,
        'confirmation_policy_reason': 'guard_cny < 20 under standing project authorization',
    })
    official = common.read_json(FINAL03 / 'OFFICIAL_PREFLIGHT.json')
    dump(REV / 'OFFICIAL_PREFLIGHT.json', {
        **official,
        'at_utc': datetime.now(timezone.utc).isoformat(),
        'same_date_source_evidence_reused_from': (FINAL03 / 'OFFICIAL_PREFLIGHT.json').relative_to(ROOT).as_posix(),
        'same_date_source_evidence_sha256': common.file_sha(FINAL03 / 'OFFICIAL_PREFLIGHT.json'),
        'execution_recheck_complete': True,
        'billing_verified': False,
    })
    print(json.dumps({'output': REV.relative_to(ROOT).as_posix(), 'calls': 44,
                      'reserve_micro_cny': scope['reserved_upper_micro_cny'], 'guard_cny': GUARD_CNY,
                      'target_calls': 0}, ensure_ascii=False))
    return 0


def dispatch(action: str, rest: list[str]) -> int:
    scope, _, _, _ = load()
    pinned = common.read_json(REV / 'MANIFEST.json')['readiness']
    if action in {'prepare', 'execute'}:
        now = readiness()
        ensure(now['independent_review_return_audit_sha256'] == pinned['independent_review_return_audit_sha256'],
               'Independent review return changed after repair probe freeze')
        ensure(not now['unknown_policy']['active_unresolved_remote_unknowns'], 'New active remote UNKNOWN appeared')
    if action == 'prepare':
        ensure(not rest and not LIVE.exists(), 'Existing repair probe runtime cannot be prepared twice')
        dump(REV / 'PREPARE_INTENT.json', {'pid': os.getpid(), 'at_utc': datetime.now(timezone.utc).isoformat()})
    if action == 'execute':
        prepared = common.read_json(REV / 'PREPARE_COMPLETE.json')
        ensure(prepared['fixture_preparation_sha256'] == common.file_sha(LIVE / 'FIXTURE_PREPARATION.json'),
               'Repair probe preparation changed')
        official = common.read_json(REV / 'OFFICIAL_PREFLIGHT.json')
        ensure(official['checked_date'] == datetime.now(timezone.utc).date().isoformat()
               and official['execution_recheck_complete'] is True, 'Repair probe provider recheck stale/incomplete')
        ensure(scope['total_guard_cny'] < 20 and scope['automatic_paid_retries'] == 0,
               'Repair probe paid-call policy changed')
    module = importlib.import_module({'prepare': 'prepare_execution_r047', 'execute': 'execute_r047',
                                      'audit': 'audit_captures_r047'}[action])
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
            ensure(preflight['passed'] and preflight['target_calls'] == 0, 'Repair probe prepare failed')
            dump(REV / 'PREPARE_COMPLETE.json', {
                'fixture_preparation_sha256': common.file_sha(LIVE / 'FIXTURE_PREPARATION.json'),
                'new_target_calls': 0,
            })
        return result or 0
    finally:
        for path in set(REV.rglob('*.json')) - before:
            if path.name == 'CAPTURE_AUDIT.json' or path.name.endswith('_REVIEW_INPUT.json'):
                value = common.read_json(path)
                value.update(full82_acceptance_claim=False, new_heldout_claim=False,
                             known_development_regression=True, diagnostic_fixed_slots=44, batch_id=BATCH)
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
