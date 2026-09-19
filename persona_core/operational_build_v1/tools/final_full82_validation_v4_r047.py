"""Fresh full82 validation after the returned independent review failed.

Final04 keeps the exact frozen 82 user inputs, 328 criteria and 76 Flash +
6 Pro provider roles. It runs repaired current source in a fresh runtime and
fresh logical batch. The response budget is reduced to 16K, which remains well
above observed answer lengths while reducing the logical guard to 25 CNY.
Automatic paid retries remain zero.
"""
from __future__ import annotations

import argparse, copy, importlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

import r047_execution_common as common
import unknown_quarantine_r047 as unknowns
import final_full82_validation_v3_r047 as final03

ROOT, PLAN = common.ROOT, common.PLAN
REV = PLAN / 'evidence/R047-03/final_full82_04'
LIVE = REV / 'live'
BATCH = 'APCORE-R047-FINAL-FULL82-04'
GUARD_CNY = 25
RESERVE_MICRO_CNY = 24_256_512
RETURN_AUDIT = PLAN / 'evidence/R047-04/independent_review_return_20260911/RETURN_AUDIT.json'
REPAIR = PLAN / 'evidence/R047-04/external_review_repair_probe_03'
REPAIR_REVIEW = REPAIR / 'SEMANTIC_REPAIR_REVIEW.json'
REPAIR_AUDIT = REPAIR / 'evidence/R047-02/audit_20260911T163840503861Z/CAPTURE_AUDIT.json'
ensure = common.ensure


def dump(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def fixed_scope():
    scope, cases, fixture, frozen = final03.fixed_scope()
    scope = copy.deepcopy(scope)
    scope.update(
        schema_version='apcore-provider-scope-2',
        batch_id=BATCH,
        purpose=('Fresh full82/328 validation of repaired source after the first '
                 'independent blind review returned FAIL. No prior call or slot is retried.'),
        max_input_bytes=32768,
        max_output_tokens=16384,
        request_timeout_seconds=240,
        total_guard_cny=GUARD_CNY,
        automatic_paid_retries=0,
    )
    for key in ('capacity_policy_id', 'output_budget_includes_reasoning', 'automatic_capacity_escalation'):
        scope.pop(key, None)
    rates = scope['peak_rates_cny_per_million_tokens']
    scope['reserved_upper_micro_cny'] = sum(
        (scope['max_input_bytes'] + scope['input_overhead_reserve_tokens']) * rates[s['model']]['input_miss']
        + scope['max_output_tokens'] * rates[s['model']]['output'] for s in scope['slots'])
    common.scope_check(scope)
    ensure(len(scope['slots']) == 82, 'Final04 frozen denominator changed')
    ensure(sum(s['model'] == 'deepseek-v4-flash' for s in scope['slots']) == 76, 'Final04 Flash count changed')
    ensure(sum(s['model'] == 'deepseek-v4-pro' for s in scope['slots']) == 6, 'Final04 Pro count changed')
    ensure(scope['reserved_upper_micro_cny'] == RESERVE_MICRO_CNY, 'Final04 reserve changed')
    ensure(scope['reserved_upper_micro_cny'] <= GUARD_CNY * 1_000_000, 'Final04 reserve exceeds guard')
    return scope, cases, fixture, frozen


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
                and all(report['sources'][key] == value for key, value in current.items())):
            return {'path': path.relative_to(ROOT).as_posix(), 'sha256': common.file_sha(path), 'tests': report['tests']}
    raise common.StoreGuard('No current-source regression binds final04')


def repair_evidence() -> dict:
    returned = common.read_json(RETURN_AUDIT)
    ensure(returned['overall_conclusion'] == 'FAIL', 'Parent independent review is no longer the failed input')
    ensure(returned['semantic_results']['verdict_counts'] == {'PASS': 319, 'FAIL': 9}, 'Parent independent verdicts changed')
    review = common.read_json(REPAIR_REVIEW)
    ensure(review['reviewed_turns'] == 44 and review['explicit_criteria_decisions'] == 176,
           'Repair semantic denominator changed')
    ensure(review['verdict_counts'] == {'PASS': 176} and review['all_repair_case_quality_targets_met'] is True,
           'Repair semantic closeout is not clean')
    ensure(review['independent_acceptance_claim'] is False and review['full82_acceptance_claim'] is False,
           'Repair probe was incorrectly promoted to acceptance')
    audit = common.read_json(REPAIR_AUDIT)
    ensure(audit['complete_captures_and_delivery'] and audit['binding_checks_passed']
           and audit['status_counts'] == {'RESPONSE_CAPTURED': 44}, 'Repair capture audit changed')
    return {
        'returned_review': RETURN_AUDIT.relative_to(ROOT).as_posix(),
        'returned_review_sha256': common.file_sha(RETURN_AUDIT),
        'repair_review': REPAIR_REVIEW.relative_to(ROOT).as_posix(),
        'repair_review_sha256': common.file_sha(REPAIR_REVIEW),
        'repair_audit': REPAIR_AUDIT.relative_to(ROOT).as_posix(),
        'repair_audit_sha256': common.file_sha(REPAIR_AUDIT),
    }


def readiness(require_regression: bool = True) -> dict:
    status = unknowns.ensure_new_independent_batch_allowed()
    ensure(not status['active_unresolved_remote_unknowns'], 'Active remote UNKNOWN blocks final04')
    result = {'unknown_policy': status, 'repair_evidence': repair_evidence()}
    if require_regression:
        result['current_regression'] = current_regression()
    return result


def execution_authorization(scope: dict) -> dict:
    path = REV / 'EXECUTION_AUTHORIZATION.json'
    ensure(path.is_file(), 'Final04 user execution authorization record required')
    auth = common.read_json(path)
    ensure(auth.get('approved') is True and auth.get('batch_id') == BATCH, 'Final04 authorization batch mismatch')
    ensure(auth.get('guard_cny') == GUARD_CNY and auth.get('reserved_upper_micro_cny') == scope['reserved_upper_micro_cny']
           and auth.get('fixed_calls') == 82 and auth.get('automatic_paid_retries') == 0,
           'Final04 authorization parameters changed')
    ensure(auth.get('authorization_basis') == 'USER_STANDING_EXECUTION_OVERRIDE_2026-09-12',
           'Final04 authorization basis changed')
    return auth


def load(prepare: bool = False):
    scope, cases, fixture, frozen = fixed_scope()
    manifest = common.read_json(REV / 'MANIFEST.json')
    ensure(common.read_json(REV / 'EXECUTION_SCOPE.json') == scope, 'Final04 scope changed')
    ensure(common.file_sha(REV / 'EXECUTION_SCOPE.json') == manifest['scope_sha256'], 'Final04 scope hash changed')
    ensure(manifest['fixed_calls'] == 82 and manifest['guard_cny'] == GUARD_CNY, 'Final04 manifest changed')
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
    ensure(not REV.exists(), 'Final04 already exists')
    REV.mkdir(parents=True)
    dump(REV / 'EXECUTION_SCOPE.json', scope)
    dump(REV / 'MANIFEST.json', {
        'batch_id': BATCH,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope_sha256': common.file_sha(REV / 'EXECUTION_SCOPE.json'),
        'parent_frozen_scope_sha256': frozen['scope_sha256'],
        'fixed_calls': 82,
        'flash_calls': 76,
        'pro_calls': 6,
        'guard_cny': GUARD_CNY,
        'reserved_upper_micro_cny': scope['reserved_upper_micro_cny'],
        'readiness': ready,
        'repair_evidence': ready['repair_evidence'],
        'known_development_regression': True,
        'new_heldout_claim': False,
        'full82_acceptance_claim': True,
        'automatic_paid_retries': 0,
        'automatic_next_revision': False,
        'review_contract': ('All 82 slots must be captured/displayed with zero UNKNOWN/rejected; '
                            'all 328 frozen criteria and original quality targets are reviewed again.'),
    })
    now = datetime.now(timezone.utc)
    dump(REV / 'OFFICIAL_PREFLIGHT.json', {
        'checked_date': now.date().isoformat(),
        'at_utc': now.isoformat(),
        'sources': ['https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',
                    'https://api-docs.deepseek.com/zh-cn/news/news260813/'],
        'verification_method': 'Current official DeepSeek documentation rechecked by host immediately before final04 freeze.',
        'models_confirmed': ['deepseek-v4-flash', 'deepseek-v4-pro'],
        'documented_versions': {'deepseek-v4-flash': 'DeepSeek-V4-Flash-0731',
                                'deepseek-v4-pro': 'DeepSeek-V4-Pro-0813'},
        'thinking_effort_supported': ['low', 'high', 'max'],
        'chosen_thinking': {'type': 'enabled'},
        'chosen_reasoning_effort': 'max',
        'documented_max_output_tokens': 393216,
        'chosen_max_output_tokens': 16384,
        'peak_rates_cny_per_million_tokens': scope['peak_rates_cny_per_million_tokens'],
        'pinned_rates_match_current_peak': True,
        'execution_recheck_complete': True,
        'billing_verified': False,
    })
    print(json.dumps({'output': REV.relative_to(ROOT).as_posix(), 'calls': 82,
                      'reserve_micro_cny': scope['reserved_upper_micro_cny'], 'guard_cny': GUARD_CNY,
                      'target_calls': 0}, ensure_ascii=False))
    return 0


def dispatch(action: str, rest: list[str]) -> int:
    scope, _, _, _ = load()
    pinned = common.read_json(REV / 'MANIFEST.json')['readiness']
    if action in {'prepare', 'execute'}:
        now = readiness()
        ensure(now['repair_evidence'] == pinned['repair_evidence'], 'Repair evidence changed after final04 freeze')
        ensure(not now['unknown_policy']['active_unresolved_remote_unknowns'], 'New active remote UNKNOWN appeared')
    if action == 'prepare':
        ensure(not rest and not LIVE.exists(), 'Existing final04 runtime cannot be prepared twice')
        dump(REV / 'PREPARE_INTENT.json', {'pid': os.getpid(), 'at_utc': datetime.now(timezone.utc).isoformat()})
    if action == 'execute':
        execution_authorization(scope)
        prepared = common.read_json(REV / 'PREPARE_COMPLETE.json')
        ensure(prepared['fixture_preparation_sha256'] == common.file_sha(LIVE / 'FIXTURE_PREPARATION.json'),
               'Final04 preparation changed')
        official = common.read_json(REV / 'OFFICIAL_PREFLIGHT.json')
        ensure(official['checked_date'] == datetime.now(timezone.utc).date().isoformat()
               and official['execution_recheck_complete'] is True, 'Final04 provider recheck stale/incomplete')
    module = importlib.import_module({
        'prepare': 'prepare_execution_r047',
        'execute': 'execute_r047',
        'audit': 'audit_captures_r047',
        'review': 'compile_reviews_r047',
    }[action])
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
            ensure(preflight['passed'] and preflight['target_calls'] == 0, 'Final04 preparation failed')
            dump(REV / 'PREPARE_COMPLETE.json', {
                'fixture_preparation_sha256': common.file_sha(LIVE / 'FIXTURE_PREPARATION.json'),
                'new_target_calls': 0,
            })
        return result or 0
    finally:
        for path in set(REV.rglob('*.json')) - before:
            if (path.name in {'CAPTURE_AUDIT.json', 'QUALITY_AND_COVERAGE.json', 'REVIEW_BINDING_REPORT.json'}
                    or path.name.endswith('_REVIEW_INPUT.json')):
                value = common.read_json(path)
                value.update(full82_acceptance_claim=True, new_heldout_claim=False,
                             known_development_regression=True, diagnostic_fixed_slots=82, batch_id=BATCH)
                path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        for key, value in previous.items():
            setattr(module, key, value)
        sys.argv = old_args


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['create', 'prepare', 'execute', 'audit', 'review'])
    args, rest = parser.parse_known_args()
    if args.action == 'create':
        ensure(not rest, 'Create accepts no extras')
        return create()
    return dispatch(args.action, rest)


if __name__ == '__main__':
    raise SystemExit(main())
