"""Named known-case repair revision; never opens original live runtime for writing.

Reuses the original execution/audit/binding functions with an explicit separate
scope and live directory. Original scope/cases/rubric are verified unchanged.
"""
from __future__ import annotations
import argparse,copy,hashlib,importlib,json,sqlite3,sys,os
from datetime import datetime,timezone
from pathlib import Path
import r047_execution_common as original

ROOT,PLAN=original.ROOT,original.PLAN
REV=PLAN/'evidence/R047-03/repair_01'
LIVE=REV/'live'
BATCH='APCORE-R047-SEMANTIC-REPAIR-01'
KNOWN='KNOWN_DEVELOPMENT_REGRESSION'
ensure=original.ensure

def revision_scope(parent):
    scope=copy.deepcopy(parent)
    scope.update(batch_id=BATCH,purpose='Known-case full82 semantic repair regression; original batch terminal and immutable; no original slot retry.',
                 pricing_verified_date='2026-09-08',all_operations_r045_plus_r047_guard_cny=91.5)
    for slot in scope['slots']:
        slot['parent_evaluation_phase']=slot['evaluation_phase']
        slot['evaluation_phase']=KNOWN
    return scope

def taxonomy():
    return {'batch_id':BATCH,'current_evaluation_classification':KNOWN,
        'known_development_regression':True,'new_heldout_claim':False,
        'parent_taxonomy_note':'NEW_AT_FREEZE and regression classification describe parent scenarios only. All current outputs are known development regression; unchanged original category quality thresholds apply separately.'}

def dump(path,obj):
    with path.open('x',encoding='utf-8') as f: json.dump(obj,f,ensure_ascii=False,indent=2)
def load_revision():
    parent,cases,fixture,frozen=original.load_frozen()
    manifest=original.read_json(REV/'REVISION.json')
    scope=original.read_json(REV/'EXECUTION_SCOPE.json')
    ensure(original.file_sha(REV/'EXECUTION_SCOPE.json')==manifest['scope_file_sha256'],'Repair scope bytes differ from revision manifest')
    ensure(manifest['parent_scope_file_sha256']==frozen['scope_sha256'],'Repair parent scope changed')
    ensure(scope==revision_scope(parent),'Repair scope differs beyond explicitly allowed batch/date/accounting/taxonomy changes')
    ensure(manifest['known_development_regression'] is True and manifest['new_heldout_claim'] is False,'Repair cannot claim new heldout evaluation')
    ensure(manifest['total_guard_cny']==scope['total_guard_cny'] and manifest['all_operations_guards_cny']==91.5,'Repair total budget accounting differs')
    original.scope_check(scope)
    cases=copy.deepcopy(cases)
    for case in cases['cases']:
        case['parent_classification']=case['classification']
        case['current_evaluation_classification']=KNOWN
    return scope,cases,fixture,{**frozen,'scope_sha256':manifest['scope_file_sha256'],
        'original_scope_sha256':frozen['scope_sha256'],**taxonomy()}
def create_revision():
    parent,cases,fixture,frozen=original.load_frozen()
    db=sqlite3.connect((original.LIVE/'runtime.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:
        calls=db.execute('SELECT status,count(*) FROM provider_calls GROUP BY status').fetchall()
        ensure(calls==[('RESPONSE_CAPTURED',82)],'Original82 journal is not wholly terminal')
        row=db.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone()
        ensure(row is not None and row[0]=='','Original driver is still active or unreconciled')
    finally: db.close()
    REV.mkdir(parents=True,exist_ok=False)
    scope=revision_scope(parent)
    original.scope_check(scope)
    dump(REV/'EXECUTION_SCOPE.json',scope)
    dump(REV/'REVISION.json',{'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'batch_id':BATCH,'parent_batch_id':parent['batch_id'],'parent_scope_file_sha256':frozen['scope_sha256'],
        'scope_file_sha256':original.file_sha(REV/'EXECUTION_SCOPE.json'),
        'known_development_regression':True,'new_heldout_claim':False,'original_rubric_unchanged':True,
        'fixed_calls':len(scope['slots']),'total_guard_cny':scope['total_guard_cny'],
        'all_operations_guards_cny':91.5,'automatic_paid_retries':0,
        'slot_identity':'(batch_id, slot_id); names retained to bind original scenario criteria; new repair batch only',
        'comparison_policy':'Keep original82 and repair82 results separate. Original NEW_AT_FREEZE taxonomy is only the parent scenario taxonomy. Repair outputs are all known development regression.',
        'targeted_and_global':'N05/N09 agreement, N10 correction, N01/N02/R01/R02 occurrence/science, N06/N08 plans/writing, N11 memory plus all remaining privacy/consent/social controls.',
        'original_journal':'persona_core/operational_build_v1/evidence/R047-02/live_01/runtime.sqlite3'})
    dump(REV/'OFFICIAL_PREFLIGHT.json',{'at_utc':datetime.now(timezone.utc).isoformat(),
        'evidence_kind':'PARSED_OFFICIAL_DOCUMENTATION_AND_SEARCH_NOT_BILLING',
        'sources':['https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',
                   'https://api-docs.deepseek.com/api/create-chat-completion/',
                   'https://api-docs.deepseek.com/guides/thinking_mode/'],
        'models_confirmed':['deepseek-v4-pro','deepseek-v4-flash'],
        'thinking':scope['thinking'],'reasoning_effort':scope['reasoning_effort'],
        'peak_rates_cny_per_million_tokens':scope['peak_rates_cny_per_million_tokens'],
        'english_cached_pricing_not_used':'English results showed an older dollar table; current Chinese peak CNY table matches pinned rates.',
        'frozen_scope_parameters_changed':False,'billing_verified':False})
    print(json.dumps({'revision':str(REV.relative_to(ROOT)),'calls':82,'guard':scope['total_guard_cny'],'target_calls':0}))
def annotate_generated_outputs(before):
    for path in set(REV.rglob('*.json'))-before:
        if path.name in {'CAPTURE_AUDIT.json','QUALITY_AND_COVERAGE.json','REVIEW_BINDING_REPORT.json'} or path.name.endswith('_REVIEW_INPUT.json'):
            report=original.read_json(path)
            report.update(taxonomy())
            # Only generated reporting metadata changes; captured text/hashes and judgments do not.
            with path.open('w',encoding='utf-8') as stream:
                json.dump(report,stream,ensure_ascii=False,indent=2)

def dispatch(action,rest):
    load_revision()
    ensure(action in {'prepare','execute','audit','review'},'Unsupported repair action')
    if action=='prepare':
        ensure(not rest,'Preparation does not accept extra arguments')
        ensure(not LIVE.exists(),'Existing repair runtime must be reconciled; preparation is never repeated')
        # Exclusive create serializes two preparing processes; retain any stale intent for reconciliation.
        dump(REV/'PREPARE_INTENT.json',{'pid':os.getpid(),'started_at_utc':datetime.now(timezone.utc).isoformat(),
                                      'scope_sha256':original.file_sha(REV/'EXECUTION_SCOPE.json')})
    if action=='execute':
        completed=original.read_json(REV/'PREPARE_COMPLETE.json')
        ensure(completed['fixture_preparation_sha256']==original.file_sha(LIVE/'FIXTURE_PREPARATION.json'),'Completed preparation binding changed')
        official=original.read_json(REV/'OFFICIAL_PREFLIGHT.json')
        scope=load_revision()[0]
        ensure(official['frozen_scope_parameters_changed'] is False and official['peak_rates_cny_per_million_tokens']==scope['peak_rates_cny_per_million_tokens'],'Repair official pricing evidence differs')
        ensure(official['models_confirmed']==[scope['primary_model'],scope['switch_model']],'Repair official model verification differs')
        ensure(official['thinking']==scope['thinking'] and official['reasoning_effort']==scope['reasoning_effort'],'Repair official API verification differs')
    module_name={'prepare':'prepare_execution_r047','execute':'execute_r047','audit':'audit_captures_r047','review':'compile_reviews_r047'}[action]
    module=importlib.import_module(module_name)
    changes={'LIVE':LIVE,'PLAN':REV,'load_frozen':load_revision}
    if action=='execute':
        changes['OFFICIAL_PREFLIGHT_PATH']=REV/'OFFICIAL_PREFLIGHT.json'
    previous={name:getattr(module,name) for name in changes}
    previous_argv=sys.argv
    before=set(REV.rglob('*.json'))
    try:
        for name,value in changes.items():
            setattr(module,name,value)
        sys.argv=[module_name+'.py']+rest
        result=module.main()
        if action=='prepare':
            saved=original.read_json(LIVE/'FIXTURE_PREPARATION.json')
            preflight=original.read_json(ROOT/saved['preflight_path']/'PREFLIGHT.json')
            ensure(preflight['passed'] and preflight['target_calls']==0,'Repair preparation did not complete')
            dump(REV/'PREPARE_COMPLETE.json',{'completed_at_utc':datetime.now(timezone.utc).isoformat(),
                 'fixture_preparation_sha256':original.file_sha(LIVE/'FIXTURE_PREPARATION.json'),**taxonomy()})
        return result or 0
    finally:
        annotate_generated_outputs(before)
        for name,value in previous.items():
            setattr(module,name,value)
        sys.argv=previous_argv
def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['create','prepare','execute','audit','review'])
    args,rest=p.parse_known_args()
    if args.action=='create':
        ensure(not rest,'Create does not accept extra arguments')
        create_revision()
        return 0
    return dispatch(args.action,rest)
if __name__=='__main__':raise SystemExit(main())
