"""Finite known-case diagnostic using unchanged real prepare/execute/audit paths.

38 calls: a six-turn numeric control, five six-turn failing domains and the
two-turn normalization regression. No automatic follow-on revision or retry.
Diagnostic completion is not full82 acceptance or independent review.
"""
from __future__ import annotations
import argparse
import copy
import importlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import r047_execution_common as common
import repair_revision_r047_v6 as parent

ROOT, PLAN = common.ROOT, common.PLAN
REV = PLAN/'evidence/R047-03/epistemic_probe_01'
LIVE = REV/'live'
BATCH = 'APCORE-R047-EPISTEMIC-DIAGNOSTIC-01'
CASE_IDS = ('N01','N02','N06','N07','N08','N11','R02')
GUARD, AGGREGATE_GUARD = 50, 431.5
ensure = common.ensure


def dump(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def fixed_scope():
    original, cases, fixture, frozen = parent.load_revision()
    scope = copy.deepcopy(original)
    scope.update(batch_id=BATCH, purpose='Bounded38 known-case epistemic expression diagnostic; all original failed full82 results preserved; no full acceptance claim.',
                 total_guard_cny=GUARD, all_operations_r045_plus_r047_guard_cny=AGGREGATE_GUARD)
    scope['slots'] = [s for s in scope['slots'] if s['case_id'] in CASE_IDS]
    ensure(len(scope['slots']) == 38 and all(s['model'] == 'deepseek-v4-flash' for s in scope['slots']), 'Fixed diagnostic slot set changed')
    rates = scope['peak_rates_cny_per_million_tokens']
    scope['reserved_upper_micro_cny'] = sum((scope['max_input_bytes']+scope['input_overhead_reserve_tokens'])*rates[s['model']]['input_miss']+
        scope['max_output_tokens']*rates[s['model']]['output'] for s in scope['slots'])
    common.scope_check(scope)
    return scope, cases, fixture, frozen


def load(prepare=False):
    scope, cases, fixture, frozen = fixed_scope()
    manifest = common.read_json(REV/'MANIFEST.json')
    ensure(common.read_json(REV/'EXECUTION_SCOPE.json') == scope, 'Diagnostic scope changed')
    ensure(common.file_sha(REV/'EXECUTION_SCOPE.json') == manifest['scope_sha256'], 'Diagnostic scope hash changed')
    ensure(manifest['full82_acceptance_claim'] is False and manifest['automatic_next_revision'] is False, 'Diagnostic cannot become a full or open-ended run')
    ensure(manifest['parent_review_sha256'] == common.file_sha(ROOT/manifest['parent_review']), 'Original failed review changed')
    selected = copy.deepcopy(cases)
    if not prepare:
        selected['cases'] = [c for c in selected['cases'] if c['id'] in CASE_IDS]
    return scope, selected, fixture, {**frozen,'scope_sha256':manifest['scope_sha256']}


def create():
    readiness = parent.verify_ready()
    scope, _, _, _ = fixed_scope()
    failed = parent.REV/'evidence/R047-03/review_20260911T034723027160Z/REVIEW_BINDING_REPORT.json'
    result = common.read_json(failed)
    ensure(result['structural_review_binding_passed'] and not result['internal_gate_eligible_by_recorded_reviews'], 'Expected complete failed parent review missing')
    REV.mkdir(parents=True, exist_ok=False)
    dump(REV/'EXECUTION_SCOPE.json',scope)
    dump(REV/'MANIFEST.json', {'batch_id':BATCH,'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'scope_sha256':common.file_sha(REV/'EXECUTION_SCOPE.json'),'parent_review':failed.relative_to(ROOT).as_posix(),
        'parent_review_sha256':common.file_sha(failed),'readiness':readiness,
        'fixed_calls':38,'case_ids':CASE_IDS,'guard_cny':GUARD,'aggregate_guard_cny':AGGREGATE_GUARD,
        'known_development_regression':True,'full82_acceptance_claim':False,'automatic_paid_retries':0,
        'automatic_next_revision':False,'new_heldout_claim':False,
        'review_contract':'Review every captured turn under original four criteria, keep failed/unrun slots. Quality scores retain original scale; diagnostic category means cannot replace full82 category means.',
        'purpose':'N01 numeric-control plus N02,N06,N07,N08,N11 failing domains and R02 explicit regression; all six-turn histories are real outputs from fresh sessions.'})
    # Current observations were independently read from official pages before
    # this named run, not inferred from the historical candidate metadata.
    dump(REV/'OFFICIAL_PREFLIGHT.json',{'checked_date':'2026-09-11',
        'at_utc':datetime.now(timezone.utc).isoformat(),
        'sources':['https://api-docs.deepseek.com/zh-cn/quick_start/pricing/','https://api-docs.deepseek.com/api/create-chat-completion/'],
        'verification_method':'Current official pages read by web tool on 2026-09-11',
        'requested_model':'deepseek-v4-flash','canonical_response_model':'deepseek-flash',
        'documented_version':'DeepSeek-V4.1-Flash','legacy_request_alias_explicitly_supported':True,
        'current_peak_rates_cny_per_million_tokens':{'input_miss':2,'input_hit':0.04,'output':8},
        'peak_rates_cny_per_million_tokens':scope['peak_rates_cny_per_million_tokens'],
        'pinned_conservative_rates_not_lower_than_current':True,
        'documented_max_output_tokens':393216,'chosen_max_output_tokens':131072,
        'thinking':scope['thinking'],'reasoning_effort':scope['reasoning_effort'],
        'frozen_scope_parameters_changed':False,'billing_verified':False})
    print(json.dumps({'output':REV.relative_to(ROOT).as_posix(),'calls':38,'reserve_micro_cny':scope['reserved_upper_micro_cny'],
                      'guard_cny':GUARD,'aggregate_guard_cny':AGGREGATE_GUARD,'new_target_calls':0}))


def dispatch(action, rest):
    scope, _, _, _ = load()
    if action in ('prepare','execute'):
        ensure(parent.verify_ready() == common.read_json(REV/'MANIFEST.json')['readiness'], 'Prior unknown disposition or diagnostic readiness changed')
    if action == 'prepare':
        ensure(not rest and not LIVE.exists(), 'Existing diagnostic cannot be prepared twice')
        dump(REV/'PREPARE_INTENT.json',{'pid':os.getpid(),'at_utc':datetime.now(timezone.utc).isoformat()})
    if action == 'execute':
        preparation = common.read_json(REV/'PREPARE_COMPLETE.json')
        ensure(preparation['fixture_preparation_sha256'] == common.file_sha(LIVE/'FIXTURE_PREPARATION.json'), 'Prepared identity changed')
        official = common.read_json(REV/'OFFICIAL_PREFLIGHT.json')
        ensure(official['checked_date'] == datetime.now(timezone.utc).date().isoformat(), 'Current-date official recheck required')
        ensure(official['thinking'] == scope['thinking'] and official['reasoning_effort'] == scope['reasoning_effort'], 'Reasoning profile differs')
    module = importlib.import_module({'prepare':'prepare_execution_r047','execute':'execute_r047','audit':'audit_captures_r047'}[action])
    replacement = {'PLAN':REV,'LIVE':LIVE,'load_frozen':lambda:load(prepare=action=='prepare')}
    if action == 'execute':
        replacement['OFFICIAL_PREFLIGHT_PATH'] = REV/'OFFICIAL_PREFLIGHT.json'
    previous = {key:getattr(module,key) for key in replacement}
    old_args, before = sys.argv, set(REV.rglob('*.json'))
    try:
        for key, value in replacement.items():setattr(module,key,value)
        sys.argv = [module.__name__]+rest
        result = module.main()
        if action == 'prepare':
            prepared = common.read_json(LIVE/'FIXTURE_PREPARATION.json')
            preflight = common.read_json(ROOT/prepared['preflight_path']/'PREFLIGHT.json')
            ensure(preflight['passed'] and preflight['target_calls']==0,'Preparation failed')
            dump(REV/'PREPARE_COMPLETE.json',{'fixture_preparation_sha256':common.file_sha(LIVE/'FIXTURE_PREPARATION.json'),'new_target_calls':0})
        return result or 0
    finally:
        for path in set(REV.rglob('*.json'))-before:
            if path.name == 'CAPTURE_AUDIT.json' or path.name.endswith('_REVIEW_INPUT.json'):
                content = common.read_json(path)
                content.update(full82_acceptance_claim=False,new_heldout_claim=False,known_development_regression=True,
                               diagnostic_fixed_slots=38,batch_id=BATCH)
                path.write_text(json.dumps(content,ensure_ascii=False,indent=2),encoding='utf-8')
        for key, value in previous.items():setattr(module,key,value)
        sys.argv = old_args


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['create','prepare','execute','audit'])
    args, rest=p.parse_known_args()
    if args.action=='create':
        ensure(not rest,'Create accepts no extra arguments');create();return 0
    return dispatch(args.action,rest)


if __name__=='__main__':raise SystemExit(main())
