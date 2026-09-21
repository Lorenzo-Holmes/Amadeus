"""Six-turn N06-only follow-up after the attribution-scope repair."""
from __future__ import annotations

import argparse, copy, importlib, json, os, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

import r047_execution_common as common
import repair_revision_r047_v6 as parent
import unknown_quarantine_r047 as unknowns

ROOT, PLAN = common.ROOT, common.PLAN
REV = PLAN/'evidence/R047-03/epistemic_probe_04'
LIVE = REV/'live'
BATCH = 'APCORE-R047-EPISTEMIC-DIAGNOSTIC-04'
CASE_IDS = ('N06',)
GUARD_CNY = 8
AGGREGATE_GUARD_CNY = 493.5
PROBE02 = PLAN/'evidence/R047-03/epistemic_probe_02'
PROBE03 = PLAN/'evidence/R047-03/epistemic_probe_03'
ensure = common.ensure

def dump(path:Path,value:dict):
    with path.open('x',encoding='utf-8') as f: json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)

def fixed_scope():
    original,cases,fixture,frozen=parent.load_revision(); scope=copy.deepcopy(original)
    scope.update(batch_id=BATCH,purpose='N06-only attribution-scope regression after diagnostic review; no prior slot is retried.',
                 total_guard_cny=GUARD_CNY,all_operations_r045_plus_r047_guard_cny=AGGREGATE_GUARD_CNY)
    scope['slots']=[s for s in scope['slots'] if s['case_id']=='N06']
    ensure(len(scope['slots'])==6,'probe_04 fixed scope changed')
    rates=scope['peak_rates_cny_per_million_tokens']
    scope['reserved_upper_micro_cny']=sum((scope['max_input_bytes']+scope['input_overhead_reserve_tokens'])*rates[s['model']]['input_miss']+
        scope['max_output_tokens']*rates[s['model']]['output'] for s in scope['slots'])
    common.scope_check(scope); ensure(scope['reserved_upper_micro_cny']<=8_000_000,'probe_04 reserve exceeds guard')
    return scope,cases,fixture,frozen

def current_regression():
    current={p.relative_to(ROOT).as_posix():common.file_sha(p) for p in sorted((ROOT/'persona_core/operational_runtime_v1').glob('*.py'))+sorted((PLAN/'tools').glob('*.py'))}
    for directory in sorted((PLAN/'evidence/R047-03').glob('regression_*'),reverse=True):
        path=directory/'REGRESSION.json'
        if not path.is_file(): continue
        r=common.read_json(path)
        if r.get('passed') and r.get('protected_history_and_production_unchanged') and r.get('target_calls')==0 and set(r.get('sources',{}))==set(current) and all(r['sources'][k]==v for k,v in current.items()):
            return {'path':path.relative_to(ROOT).as_posix(),'sha256':common.file_sha(path),'tests':r['tests']}
    raise common.StoreGuard('No current-source regression binds probe_04')

def readiness(require_regression=True):
    status=unknowns.ensure_new_independent_batch_allowed(); ensure(not status['active_unresolved_remote_unknowns'],'Active UNKNOWN remains')
    p2=common.read_json(PROBE02/'SEMANTIC_REVIEW_VALIDATION.json')
    ensure(p2['passed'] and p2['open_blocking_findings']==['F-R047-P02-ATTRIBUTION-SCOPE'],'Expected sole N06 blocking finding changed')
    p3=common.read_json(PROBE03/'SEMANTIC_REVIEW_VALIDATION.json')
    ensure(p3['passed'] and p3['verdict_counts']=={'PASS':56} and not p3['open_blocking_findings'],'probe_03 semantic gate changed')
    db=sqlite3.connect((PROBE03/'live/runtime.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:
        ensure(dict(db.execute('SELECT status,count(*) FROM provider_calls GROUP BY status').fetchall())=={'RESPONSE_CAPTURED':14},'probe_03 terminal calls changed')
        d=db.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone(); ensure(d is None or d[0]=='','probe_03 driver active')
    finally: db.close()
    result={'unknown_policy':status,'probe02_review_sha256':common.file_sha(PROBE02/'SEMANTIC_REVIEW_VALIDATION.json'),
            'probe03_review_sha256':common.file_sha(PROBE03/'SEMANTIC_REVIEW_VALIDATION.json')}
    if require_regression: result['current_regression']=current_regression()
    return result

def load(prepare=False):
    scope,cases,fixture,frozen=fixed_scope(); m=common.read_json(REV/'MANIFEST.json')
    ensure(common.read_json(REV/'EXECUTION_SCOPE.json')==scope and common.file_sha(REV/'EXECUTION_SCOPE.json')==m['scope_sha256'],'probe_04 scope changed')
    selected=copy.deepcopy(cases)
    if not prepare: selected['cases']=[c for c in selected['cases'] if c['id']=='N06']
    return scope,selected,fixture,{**frozen,'scope_sha256':m['scope_sha256']}

def create():
    ready=readiness(); scope,_,_,_=fixed_scope(); ensure(not REV.exists(),'probe_04 exists')
    REV.mkdir(parents=True); dump(REV/'EXECUTION_SCOPE.json',scope)
    dump(REV/'MANIFEST.json',{'batch_id':BATCH,'created_at_utc':datetime.now(timezone.utc).isoformat(),'scope_sha256':common.file_sha(REV/'EXECUTION_SCOPE.json'),
        'fixed_calls':6,'case_ids':['N06'],'guard_cny':GUARD_CNY,'aggregate_guard_cny':AGGREGATE_GUARD_CNY,'reserved_upper_micro_cny':scope['reserved_upper_micro_cny'],
        'readiness':ready,'known_development_regression':True,'new_heldout_claim':False,'full82_acceptance_claim':False,'automatic_paid_retries':0,'automatic_next_revision':False})
    old=common.read_json(PROBE03/'OFFICIAL_PREFLIGHT.json'); dump(REV/'OFFICIAL_PREFLIGHT.json',{**old,'at_utc':datetime.now(timezone.utc).isoformat(),
        'same_date_source_evidence_reused_from':(PROBE03/'OFFICIAL_PREFLIGHT.json').relative_to(ROOT).as_posix(),'same_date_source_evidence_sha256':common.file_sha(PROBE03/'OFFICIAL_PREFLIGHT.json'),
        'execution_recheck_complete':True,'billing_verified':False})
    print(json.dumps({'output':REV.relative_to(ROOT).as_posix(),'calls':6,'reserve_micro_cny':scope['reserved_upper_micro_cny'],'guard_cny':GUARD_CNY,'target_calls':0})); return 0

def dispatch(action,rest):
    scope,_,_,_=load()
    if action in {'prepare','execute'}:
        now=readiness(); pinned=common.read_json(REV/'MANIFEST.json')['readiness']
        ensure(now['probe02_review_sha256']==pinned['probe02_review_sha256'] and now['probe03_review_sha256']==pinned['probe03_review_sha256'],'probe_04 predecessor review changed')
    if action=='prepare': ensure(not rest and not LIVE.exists(),'Existing probe_04 runtime'); dump(REV/'PREPARE_INTENT.json',{'pid':os.getpid(),'at_utc':datetime.now(timezone.utc).isoformat()})
    if action=='execute':
        p=common.read_json(REV/'PREPARE_COMPLETE.json'); ensure(p['fixture_preparation_sha256']==common.file_sha(LIVE/'FIXTURE_PREPARATION.json'),'probe_04 preparation changed')
    module=importlib.import_module({'prepare':'prepare_execution_r047','execute':'execute_r047','audit':'audit_captures_r047'}[action])
    repl={'PLAN':REV,'LIVE':LIVE,'load_frozen':lambda:load(prepare=action=='prepare')}
    if action=='execute': repl['OFFICIAL_PREFLIGHT_PATH']=REV/'OFFICIAL_PREFLIGHT.json'
    prev={k:getattr(module,k) for k in repl}; old_args,before=sys.argv,set(REV.rglob('*.json'))
    try:
        for k,v in repl.items(): setattr(module,k,v)
        sys.argv=[module.__name__]+rest; result=module.main()
        if action=='prepare':
            saved=common.read_json(LIVE/'FIXTURE_PREPARATION.json'); pre=common.read_json(ROOT/saved['preflight_path']/'PREFLIGHT.json')
            ensure(pre['passed'] and pre['target_calls']==0,'probe_04 prepare failed'); dump(REV/'PREPARE_COMPLETE.json',{'fixture_preparation_sha256':common.file_sha(LIVE/'FIXTURE_PREPARATION.json'),'new_target_calls':0})
        return result or 0
    finally:
        for path in set(REV.rglob('*.json'))-before:
            if path.name=='CAPTURE_AUDIT.json' or path.name.endswith('_REVIEW_INPUT.json'):
                v=common.read_json(path); v.update(full82_acceptance_claim=False,new_heldout_claim=False,known_development_regression=True,diagnostic_fixed_slots=6,batch_id=BATCH)
                path.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
        for k,v in prev.items(): setattr(module,k,v)
        sys.argv=old_args

def main():
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['create','prepare','execute','audit']); args,rest=p.parse_known_args()
    if args.action=='create': ensure(not rest,'Create accepts no extras'); return create()
    return dispatch(args.action,rest)

if __name__=='__main__': raise SystemExit(main())
