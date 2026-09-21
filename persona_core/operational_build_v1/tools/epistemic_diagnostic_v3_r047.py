"""Third independent targeted diagnostic after quarantining probe_02 N08_T1.

Fresh batch/runtime/call IDs; never resumes or rewrites probe_01/probe_02.
Scope: N08 + N11 + R02 = 14 known-development turns. Guard is 19 CNY,
below the user's >=20 CNY reconfirmation threshold. Zero automatic retries.
"""
from __future__ import annotations

import argparse, copy, importlib, json, os, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

import r047_execution_common as common
import repair_revision_r047_v6 as parent
import unknown_quarantine_r047 as unknowns

ROOT, PLAN = common.ROOT, common.PLAN
REV = PLAN/'evidence/R047-03/epistemic_probe_03'
LIVE = REV/'live'
BATCH = 'APCORE-R047-EPISTEMIC-DIAGNOSTIC-03'
CASE_IDS = ('N08','N11','R02')
GUARD_CNY = 19
AGGREGATE_GUARD_CNY = 485.5
PROBE02 = PLAN/'evidence/R047-03/epistemic_probe_02'
OLD_UNKNOWN = 'call_9ee0cd0ce3d14527bf00b62866181aee'
ensure = common.ensure


def dump(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def fixed_scope():
    original, cases, fixture, frozen = parent.load_revision()
    scope = copy.deepcopy(original)
    scope.update(batch_id=BATCH,
                 purpose='Fresh14 known-case diagnostic after quarantining probe_02 remote UNKNOWN; not a retry/resume of the old call.',
                 total_guard_cny=GUARD_CNY,
                 all_operations_r045_plus_r047_guard_cny=AGGREGATE_GUARD_CNY)
    scope['slots'] = [s for s in scope['slots'] if s['case_id'] in CASE_IDS]
    ensure(len(scope['slots']) == 14 and {s['case_id'] for s in scope['slots']} == set(CASE_IDS),
           'probe_03 fixed scope changed')
    rates = scope['peak_rates_cny_per_million_tokens']
    scope['reserved_upper_micro_cny'] = sum(
        (scope['max_input_bytes']+scope['input_overhead_reserve_tokens'])*rates[s['model']]['input_miss']+
        scope['max_output_tokens']*rates[s['model']]['output'] for s in scope['slots'])
    common.scope_check(scope)
    ensure(scope['reserved_upper_micro_cny'] <= 19_000_000, 'probe_03 reserve exceeds 19 CNY guard')
    return scope, cases, fixture, frozen


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
    raise common.StoreGuard('No current-source regression binds probe_03')


def readiness(require_regression=True):
    status=unknowns.ensure_new_independent_batch_allowed()
    quarantined=[r for r in status['allowed_historical_unknowns']
                 if r.get('call_id')==OLD_UNKNOWN and r.get('classification')=='QUARANTINED_REMOTE_UNKNOWN']
    ensure(len(quarantined)==1,'probe_02 N08_T1 is not uniquely quarantined')
    ensure(not status['active_unresolved_remote_unknowns'],'Active remote UNKNOWN remains')
    db=sqlite3.connect((PROBE02/'live/runtime.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:
        counts=dict(db.execute('SELECT status,count(*) FROM provider_calls GROUP BY status').fetchall())
        stopped=db.execute('SELECT stopped FROM call_batches WHERE batch_id=?',('APCORE-R047-EPISTEMIC-DIAGNOSTIC-02',)).fetchone()
        driver=db.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone()
        ensure(counts=={'RESPONSE_CAPTURED':12,'SUBMITTED_STATUS_UNKNOWN':1},'probe_02 terminal denominator changed')
        ensure(stopped and stopped[0]==1 and (driver is None or driver[0]==''),'probe_02 is not terminal/idle')
    finally: db.close()
    result={'unknown_policy':status,'quarantined_probe02_call':quarantined[0],
            'probe02_counts':counts,'probe02_stopped':True}
    if require_regression: result['current_regression']=current_regression()
    return result


def load(prepare=False):
    scope,cases,fixture,frozen=fixed_scope()
    manifest=common.read_json(REV/'MANIFEST.json')
    ensure(common.read_json(REV/'EXECUTION_SCOPE.json')==scope,'probe_03 scope changed')
    ensure(common.file_sha(REV/'EXECUTION_SCOPE.json')==manifest['scope_sha256'],'probe_03 scope hash changed')
    ensure(manifest['fixed_calls']==14 and manifest['case_ids']==list(CASE_IDS),'probe_03 denominator changed')
    ensure(manifest['old_unknown_call_id']==OLD_UNKNOWN and manifest['old_unknown_resend_allowed'] is False,
           'probe_03 retry boundary changed')
    selected=copy.deepcopy(cases)
    if not prepare: selected['cases']=[c for c in selected['cases'] if c['id'] in CASE_IDS]
    return scope,selected,fixture,{**frozen,'scope_sha256':manifest['scope_sha256']}


def create():
    ready=readiness()
    scope,_,_,_=fixed_scope()
    ensure(not REV.exists(),'probe_03 exists; reconcile instead of recreating')
    REV.mkdir(parents=True)
    dump(REV/'EXECUTION_SCOPE.json',scope)
    dump(REV/'MANIFEST.json',{
        'batch_id':BATCH,'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'scope_sha256':common.file_sha(REV/'EXECUTION_SCOPE.json'),'fixed_calls':14,
        'case_ids':list(CASE_IDS),'guard_cny':GUARD_CNY,'aggregate_guard_cny':AGGREGATE_GUARD_CNY,
        'reserved_upper_micro_cny':scope['reserved_upper_micro_cny'],'old_unknown_call_id':OLD_UNKNOWN,
        'old_unknown_resend_allowed':False,'old_batch_resume_allowed':False,'fresh_batch_and_runtime_required':True,
        'readiness':ready,'known_development_regression':True,'new_heldout_claim':False,
        'full82_acceptance_claim':False,'automatic_paid_retries':0,'automatic_next_revision':False,
        'execution_requires_explicit_over_20_cny_confirmation':False,
        'review_contract':'Review all captured probe_03 turns under original criteria; missing/unknown/unrun never pass.'})
    old=common.read_json(PROBE02/'OFFICIAL_PREFLIGHT.json')
    dump(REV/'OFFICIAL_PREFLIGHT.json',{**old,'at_utc':datetime.now(timezone.utc).isoformat(),
        'same_date_source_evidence_reused_from':(PROBE02/'OFFICIAL_PREFLIGHT.json').relative_to(ROOT).as_posix(),
        'same_date_source_evidence_sha256':common.file_sha(PROBE02/'OFFICIAL_PREFLIGHT.json'),
        'execution_recheck_complete':True,'billing_verified':False})
    print(json.dumps({'output':REV.relative_to(ROOT).as_posix(),'calls':14,'reserve_micro_cny':scope['reserved_upper_micro_cny'],
                      'guard_cny':GUARD_CNY,'aggregate_guard_cny':AGGREGATE_GUARD_CNY,'target_calls':0}))
    return 0


def dispatch(action,rest):
    scope,_,_,_=load()
    if action in {'prepare','execute'}:
        now=readiness(); pinned=common.read_json(REV/'MANIFEST.json')['readiness']
        ensure(now['quarantined_probe02_call']==pinned['quarantined_probe02_call'],'probe_03 predecessor quarantine changed')
        ensure(now['probe02_counts']==pinned['probe02_counts'] and now['probe02_stopped'] is True,'probe_02 terminal state changed')
        ensure(not now['unknown_policy']['active_unresolved_remote_unknowns'],'New active UNKNOWN appeared')
    if action=='prepare':
        ensure(not rest and not LIVE.exists(),'Existing probe_03 runtime cannot be prepared twice')
        dump(REV/'PREPARE_INTENT.json',{'pid':os.getpid(),'at_utc':datetime.now(timezone.utc).isoformat()})
    if action=='execute':
        prepared=common.read_json(REV/'PREPARE_COMPLETE.json')
        ensure(prepared['fixture_preparation_sha256']==common.file_sha(LIVE/'FIXTURE_PREPARATION.json'),'probe_03 preparation binding changed')
        official=common.read_json(REV/'OFFICIAL_PREFLIGHT.json')
        ensure(official.get('execution_recheck_complete') is True and official['checked_date']==datetime.now(timezone.utc).date().isoformat(),
               'Current provider recheck required')
    module=importlib.import_module({'prepare':'prepare_execution_r047','execute':'execute_r047','audit':'audit_captures_r047'}[action])
    replacement={'PLAN':REV,'LIVE':LIVE,'load_frozen':lambda:load(prepare=action=='prepare')}
    if action=='execute': replacement['OFFICIAL_PREFLIGHT_PATH']=REV/'OFFICIAL_PREFLIGHT.json'
    previous={k:getattr(module,k) for k in replacement}; old_args,before=sys.argv,set(REV.rglob('*.json'))
    try:
        for k,v in replacement.items(): setattr(module,k,v)
        sys.argv=[module.__name__]+rest
        result=module.main()
        if action=='prepare':
            saved=common.read_json(LIVE/'FIXTURE_PREPARATION.json')
            preflight=common.read_json(ROOT/saved['preflight_path']/'PREFLIGHT.json')
            ensure(preflight['passed'] and preflight['target_calls']==0,'probe_03 preparation failed')
            dump(REV/'PREPARE_COMPLETE.json',{'fixture_preparation_sha256':common.file_sha(LIVE/'FIXTURE_PREPARATION.json'),'new_target_calls':0})
        return result or 0
    finally:
        for path in set(REV.rglob('*.json'))-before:
            if path.name=='CAPTURE_AUDIT.json' or path.name.endswith('_REVIEW_INPUT.json'):
                value=common.read_json(path); value.update(full82_acceptance_claim=False,new_heldout_claim=False,
                    known_development_regression=True,diagnostic_fixed_slots=14,batch_id=BATCH)
                path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        for k,v in previous.items(): setattr(module,k,v)
        sys.argv=old_args


def main():
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['create','prepare','execute','audit'])
    args,rest=p.parse_known_args()
    if args.action=='create': ensure(not rest,'Create accepts no extra args'); return create()
    return dispatch(args.action,rest)

if __name__=='__main__': raise SystemExit(main())
