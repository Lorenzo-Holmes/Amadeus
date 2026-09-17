"""Final known-development full82/328 validation candidate for R047-03.

This is the required final clean full-suite gate after all targeted diagnostics
closed. Create/prepare are zero-target-call operations. Execute is forbidden
unless an exact batch authorization file exists because the fixed logical guard
is >=20 CNY. Historical quarantined UNKNOWN rows remain immutable and are not
retried or treated as resolved.
"""
from __future__ import annotations

import argparse, copy, importlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

import r047_execution_common as common
import repair_revision_r047_v6 as capacity
import unknown_quarantine_r047 as unknowns

ROOT, PLAN = common.ROOT, common.PLAN
REV = PLAN/'evidence/R047-03/final_full82_01'
LIVE = REV/'live'
BATCH = 'APCORE-R047-FINAL-FULL82-01'
GUARD_CNY = 125
AGGREGATE_GUARD_CNY = 618.5
TARGETED = PLAN/'evidence/R047-03/TARGETED_DIAGNOSTIC_CLOSEOUT.json'
ensure = common.ensure


def dump(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def fixed_scope():
    parent, cases, fixture, frozen = common.load_frozen()
    scope = copy.deepcopy(capacity.revision_scope(parent))
    scope.update(batch_id=BATCH,
                 purpose='Final full82/328 known-development validation after targeted diagnostics passed; no historical failed/unknown slot is retried.',
                 total_guard_cny=GUARD_CNY,
                 all_operations_r045_plus_r047_guard_cny=AGGREGATE_GUARD_CNY)
    rates=scope['peak_rates_cny_per_million_tokens']
    scope['reserved_upper_micro_cny']=sum(
        (scope['max_input_bytes']+scope['input_overhead_reserve_tokens'])*rates[s['model']]['input_miss']+
        scope['max_output_tokens']*rates[s['model']]['output'] for s in scope['slots'])
    common.scope_check(scope)
    ensure(len(scope['slots'])==82, 'Final frozen denominator changed')
    models={m:sum(s['model']==m for s in scope['slots']) for m in ('deepseek-v4-flash','deepseek-v4-pro')}
    ensure(models=={'deepseek-v4-flash':76,'deepseek-v4-pro':6}, 'Final model-role denominator changed')
    ensure(scope['reserved_upper_micro_cny'] <= GUARD_CNY*1_000_000, 'Final reserve exceeds guard')
    return scope,cases,fixture,frozen


def current_regression() -> dict:
    current={p.relative_to(ROOT).as_posix():common.file_sha(p)
             for p in sorted((ROOT/'persona_core/operational_runtime_v1').glob('*.py'))+sorted((PLAN/'tools').glob('*.py'))}
    for directory in sorted((PLAN/'evidence/R047-03').glob('regression_*'), reverse=True):
        path=directory/'REGRESSION.json'
        if not path.is_file(): continue
        report=common.read_json(path)
        if not (report.get('passed') and report.get('protected_history_and_production_unchanged')
                and report.get('target_calls')==0): continue
        if set(report.get('sources',{}))==set(current) and all(report['sources'][k]==v for k,v in current.items()):
            return {'path':path.relative_to(ROOT).as_posix(),'sha256':common.file_sha(path),'tests':report['tests']}
    raise common.StoreGuard('No current-source regression binds final full82')


def targeted_closeout() -> dict:
    result=common.read_json(TARGETED)
    ensure(result['status']=='TARGETED_DIAGNOSTICS_PASS', 'Targeted diagnostics are not closed')
    ensure(result['reviewed_turns']==38 and result['criterion_denominator']==152 and result['criterion_pass']==152,
           'Targeted diagnostic denominator/pass count changed')
    ensure(not result['open_blocking_findings'] and result['full82_acceptance_claim'] is False,
           'Targeted closeout cannot contain blockers or claim final acceptance')
    expected={'N01','N02','N06','N07','N08','N11','R02'}
    ensure({r['case_id'] for r in result['cases']}==expected, 'Targeted closeout case set changed')
    for row in result['cases']:
        journal=ROOT/row['journal']; review=ROOT/row['review']
        ensure(common.file_sha(journal)==row['journal_sha256'], 'Targeted journal changed: '+row['case_id'])
        ensure(common.file_sha(review)==row['review_sha256'], 'Targeted review changed: '+row['case_id'])
    return {'path':TARGETED.relative_to(ROOT).as_posix(),'sha256':common.file_sha(TARGETED),
            'reviewed_turns':38,'criteria':152,'pass':152}


def readiness(require_regression=True) -> dict:
    status=unknowns.ensure_new_independent_batch_allowed()
    ensure(not status['active_unresolved_remote_unknowns'], 'Active remote UNKNOWN blocks final validation')
    result={'unknown_policy':status,'targeted_closeout':targeted_closeout()}
    if require_regression: result['current_regression']=current_regression()
    return result


def execution_authorization(scope: dict) -> dict:
    path=REV/'EXECUTION_AUTHORIZATION.json'
    ensure(path.is_file(), 'Explicit >=20 CNY final full82 authorization required')
    auth=common.read_json(path)
    ensure(auth.get('approved') is True and auth.get('batch_id')==BATCH,
           'Final full82 authorization does not bind this batch')
    ensure(auth.get('guard_cny')==GUARD_CNY and auth.get('reserved_upper_micro_cny')==scope['reserved_upper_micro_cny']
           and auth.get('fixed_calls')==82 and auth.get('automatic_paid_retries')==0,
           'Final full82 authorization parameters changed')
    return auth


def load(prepare=False):
    scope,cases,fixture,frozen=fixed_scope(); manifest=common.read_json(REV/'MANIFEST.json')
    ensure(common.read_json(REV/'EXECUTION_SCOPE.json')==scope and common.file_sha(REV/'EXECUTION_SCOPE.json')==manifest['scope_sha256'],
           'Final full82 scope changed')
    ensure(manifest['fixed_calls']==82 and manifest['guard_cny']==GUARD_CNY,
           'Final full82 manifest denominator/guard changed')
    selected=copy.deepcopy(cases)
    return scope,selected,fixture,{**frozen,'scope_sha256':manifest['scope_sha256'],
                                   'current_evaluation_classification':'KNOWN_DEVELOPMENT_REGRESSION',
                                   'known_development_regression':True,'new_heldout_claim':False}


def create() -> int:
    ready=readiness(); scope,_,_,frozen=fixed_scope(); ensure(not REV.exists(),'Final full82 revision exists')
    REV.mkdir(parents=True); dump(REV/'EXECUTION_SCOPE.json',scope)
    dump(REV/'MANIFEST.json',{
        'batch_id':BATCH,'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'scope_sha256':common.file_sha(REV/'EXECUTION_SCOPE.json'),'parent_frozen_scope_sha256':frozen['scope_sha256'],
        'fixed_calls':82,'main_flash_calls':76,'switch_pro_calls':6,'guard_cny':GUARD_CNY,
        'aggregate_guard_cny':AGGREGATE_GUARD_CNY,'reserved_upper_micro_cny':scope['reserved_upper_micro_cny'],
        'readiness':ready,'known_development_regression':True,'new_heldout_claim':False,
        'automatic_paid_retries':0,'automatic_next_revision':False,'full82_acceptance_claim':False,
        'execution_requires_explicit_user_confirmation':True,
        'review_contract':'After all82 captured/displayed, review all328 original frozen criteria and original quality targets; no missing/unknown/rejected slot may pass.'})
    dump(REV/'OFFICIAL_PREFLIGHT.json',{
        'checked_date':'2026-09-11','at_utc':datetime.now(timezone.utc).isoformat(),
        'sources':['https://api-docs.deepseek.com/quick_start/pricing/','https://api-docs.deepseek.com/news/news260813/'],
        'verification_method':'Current official DeepSeek pages read on 2026-09-11 before final batch freeze',
        'models_confirmed':['deepseek-v4-flash','deepseek-v4-pro'],
        'documented_versions':{'deepseek-v4-flash':'DeepSeek-V4-Flash-0731','deepseek-v4-pro':'DeepSeek-V4-Pro-0813'},
        'thinking_effort_supported':['low','high','max'],'chosen_thinking':scope['thinking'],'chosen_reasoning_effort':scope['reasoning_effort'],
        'documented_max_output_tokens':393216,'chosen_max_output_tokens':scope['max_output_tokens'],
        'current_peak_rates_cny_per_million_tokens':{
            'deepseek-v4-flash':{'input_hit':0.1,'input_miss':3.0,'output':9.0},
            'deepseek-v4-pro':{'input_hit':0.3,'input_miss':9.0,'output':27.0}},
        'peak_rates_cny_per_million_tokens':scope['peak_rates_cny_per_million_tokens'],
        'pinned_rates_match_current_peak':True,'billing_verified':False,'execution_recheck_complete':True,
        'frozen_scope_parameters_changed':False})
    print(json.dumps({'output':REV.relative_to(ROOT).as_posix(),'calls':82,'reserve_micro_cny':scope['reserved_upper_micro_cny'],
                      'guard_cny':GUARD_CNY,'aggregate_guard_cny':AGGREGATE_GUARD_CNY,'target_calls':0}))
    return 0


def dispatch(action,rest):
    scope,_,_,_=load()
    now=readiness(); pinned=common.read_json(REV/'MANIFEST.json')['readiness']
    ensure(now['targeted_closeout']==pinned['targeted_closeout'], 'Targeted closeout changed after final freeze')
    ensure(not now['unknown_policy']['active_unresolved_remote_unknowns'], 'New active remote UNKNOWN appeared')
    if action=='prepare':
        ensure(not rest and not LIVE.exists(),'Existing final runtime cannot be prepared twice')
        dump(REV/'PREPARE_INTENT.json',{'pid':os.getpid(),'at_utc':datetime.now(timezone.utc).isoformat()})
    if action=='execute':
        execution_authorization(scope)
        prepared=common.read_json(REV/'PREPARE_COMPLETE.json')
        ensure(prepared['fixture_preparation_sha256']==common.file_sha(LIVE/'FIXTURE_PREPARATION.json'),'Final preparation changed')
        official=common.read_json(REV/'OFFICIAL_PREFLIGHT.json')
        ensure(official['checked_date']==datetime.now(timezone.utc).date().isoformat() and official['execution_recheck_complete'] is True,
               'Final provider recheck is stale/incomplete')
    module=importlib.import_module({'prepare':'prepare_execution_r047','execute':'execute_r047','audit':'audit_captures_r047'}[action])
    replacement={'PLAN':REV,'LIVE':LIVE,'load_frozen':lambda:load(prepare=action=='prepare')}
    if action=='execute': replacement['OFFICIAL_PREFLIGHT_PATH']=REV/'OFFICIAL_PREFLIGHT.json'
    previous={k:getattr(module,k) for k in replacement}; old_args,before=sys.argv,set(REV.rglob('*.json'))
    try:
        for k,v in replacement.items(): setattr(module,k,v)
        sys.argv=[module.__name__]+rest; result=module.main()
        if action=='prepare':
            saved=common.read_json(LIVE/'FIXTURE_PREPARATION.json'); pre=common.read_json(ROOT/saved['preflight_path']/'PREFLIGHT.json')
            ensure(pre['passed'] and pre['target_calls']==0,'Final preparation failed')
            dump(REV/'PREPARE_COMPLETE.json',{'fixture_preparation_sha256':common.file_sha(LIVE/'FIXTURE_PREPARATION.json'),'new_target_calls':0})
        return result or 0
    finally:
        for path in set(REV.rglob('*.json'))-before:
            if path.name=='CAPTURE_AUDIT.json' or path.name.endswith('_REVIEW_INPUT.json'):
                value=common.read_json(path); value.update(full82_acceptance_claim=True,new_heldout_claim=False,
                    known_development_regression=True,diagnostic_fixed_slots=82,batch_id=BATCH)
                path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        for k,v in previous.items(): setattr(module,k,v)
        sys.argv=old_args


def main():
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['create','prepare','execute','audit']); args,rest=p.parse_known_args()
    if args.action=='create': ensure(not rest,'Create accepts no extras'); return create()
    return dispatch(args.action,rest)

if __name__=='__main__': raise SystemExit(main())
