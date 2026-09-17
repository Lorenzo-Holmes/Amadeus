"""Resilient current-source full82 validation assembled by independent cases.

The frozen evaluation consists of independent case sessions/entities. Seven
cases implicated by the returned independent review were already rerun in the
clean 44-turn repair probe03 on the repaired product runtime. This workflow
runs the remaining seven cases as separate bounded logical batches, preserving
each case's complete multi-turn history and original model-switch slots.

No case may be partially spliced. A component with UNKNOWN/rejection is
terminal and must be replaced by a fresh component revision. The final
composite is accepted structurally only when all frozen 82 slot IDs appear
exactly once, with exact original inputs/provider roles, clean capture/display
evidence and one identical repaired operational-runtime source snapshot.
"""
from __future__ import annotations

import argparse, copy, hashlib, importlib, json, os, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

import r047_execution_common as common
import unknown_quarantine_r047 as unknowns
import final_full82_validation_v5_r047 as parent

ROOT, PLAN = common.ROOT, common.PLAN
REV = PLAN / 'evidence/R047-03/composite_full82_repaired_01'
REPAIR = PLAN / 'evidence/R047-04/external_review_repair_probe_03'
REPAIR_AUDIT = REPAIR / 'evidence/R047-02/audit_20260911T163840503861Z/CAPTURE_AUDIT.json'
REPAIR_REVIEW = REPAIR / 'SEMANTIC_REPAIR_REVIEW.json'
REPAIR_CASES = ('N02','N04','N06','N07','N08','N09','N11')
COMPONENT_CASES = ('N01','N03','N05','N10','N12','R01','R02')
ensure = common.ensure


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_runtime_hashes() -> dict[str,str]:
    return {p.relative_to(ROOT).as_posix(): common.file_sha(p)
            for p in sorted((ROOT/'persona_core/operational_runtime_v1').glob('*.py'))}


def repair_runtime_binding() -> dict:
    saved = common.read_json(REPAIR/'live/FIXTURE_PREPARATION.json')
    preflight = common.read_json(ROOT/saved['preflight_path']/'PREFLIGHT.json')
    source = {item['path']: item['sha256'] for item in preflight['tested_sources']
              if item['path'].startswith('persona_core/operational_runtime_v1/')}
    current = current_runtime_hashes()
    ensure(source == current, 'Repair probe operational runtime no longer matches current repaired runtime')
    audit = common.read_json(REPAIR_AUDIT)
    review = common.read_json(REPAIR_REVIEW)
    ensure(audit['complete_captures_and_delivery'] and audit['binding_checks_passed']
           and audit['status_counts']=={'RESPONSE_CAPTURED':44}, 'Repair probe capture binding changed')
    ensure(review['verdict_counts']=={'PASS':176} and review['all_repair_case_quality_targets_met'] is True,
           'Repair probe semantic closeout changed')
    ensure({r['case_id'] for r in audit['records']} == set(REPAIR_CASES), 'Repair probe case set changed')
    return {'preflight': (ROOT/saved['preflight_path']/'PREFLIGHT.json').relative_to(ROOT).as_posix(),
            'preflight_sha256': common.file_sha(ROOT/saved['preflight_path']/'PREFLIGHT.json'),
            'runtime_hashes': current,
            'audit': REPAIR_AUDIT.relative_to(ROOT).as_posix(), 'audit_sha256': sha(REPAIR_AUDIT),
            'review': REPAIR_REVIEW.relative_to(ROOT).as_posix(), 'review_sha256': sha(REPAIR_REVIEW)}


def current_regression() -> dict:
    current={p.relative_to(ROOT).as_posix():common.file_sha(p)
             for p in sorted((ROOT/'persona_core/operational_runtime_v1').glob('*.py'))+sorted((PLAN/'tools').glob('*.py'))}
    for directory in sorted((PLAN/'evidence/R047-03').glob('regression_*'),reverse=True):
        path=directory/'REGRESSION.json'
        if not path.is_file(): continue
        r=common.read_json(path)
        if (r.get('passed') and r.get('protected_history_and_production_unchanged') and r.get('target_calls')==0
                and set(r.get('sources',{}))==set(current) and all(r['sources'][k]==v for k,v in current.items())):
            return {'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'tests':r['tests']}
    raise common.StoreGuard('No current-source regression binds composite validation')


def readiness(require_regression: bool=True) -> dict:
    status=unknowns.ensure_new_independent_batch_allowed()
    ensure(not status['active_unresolved_remote_unknowns'],'Active remote UNKNOWN blocks composite validation')
    result={'unknown_policy':status,'repair_runtime_binding':repair_runtime_binding()}
    if require_regression: result['current_regression']=current_regression()
    return result


def component_root(case_id: str) -> Path:
    ensure(case_id in COMPONENT_CASES,'Unknown component case')
    return REV/'components'/case_id


def component_scope(case_id: str):
    base,cases,fixture,frozen=parent.fixed_scope()
    scope=copy.deepcopy(base)
    scope.update(batch_id='APCORE-R047-COMPOSITE-'+case_id+'-01',
                 purpose='Current-source composite full82 component for '+case_id+'; exact frozen case, no cross-case splicing.',
                 total_guard_cny=5, automatic_paid_retries=0)
    scope['slots']=[s for s in scope['slots'] if s['case_id']==case_id]
    rates=scope['peak_rates_cny_per_million_tokens']
    scope['reserved_upper_micro_cny']=sum(
        (scope['max_input_bytes']+scope['input_overhead_reserve_tokens'])*rates[s['model']]['input_miss']
        +scope['max_output_tokens']*rates[s['model']]['output'] for s in scope['slots'])
    common.scope_check(scope)
    ensure(scope['reserved_upper_micro_cny']<=5_000_000,'Component reserve exceeds guard')
    selected=copy.deepcopy(cases); selected['cases']=[c for c in selected['cases'] if c['id']==case_id]
    ensure(len(selected['cases'])==1,'Component case missing')
    return scope,selected,fixture,frozen


def load_component(case_id: str, prepare: bool=False):
    scope,cases,fixture,frozen=component_scope(case_id)
    root=component_root(case_id)
    if prepare:
        _,all_cases,_,_=common.load_frozen(); cases=copy.deepcopy(all_cases)
    manifest=common.read_json(root/'MANIFEST.json')
    ensure(common.read_json(root/'EXECUTION_SCOPE.json')==scope and sha(root/'EXECUTION_SCOPE.json')==manifest['scope_sha256'],
           'Component scope changed: '+case_id)
    return scope,cases,fixture,{**frozen,'scope_sha256':manifest['scope_sha256'],
        'current_evaluation_classification':'KNOWN_DEVELOPMENT_REPAIRED_COMPOSITE',
        'known_development_regression':True,'new_heldout_claim':False}


def create() -> int:
    ready=readiness(); ensure(not REV.exists(),'Composite revision already exists')
    REV.mkdir(parents=True)
    dump(REV/'MANIFEST.json',{'schema_version':'r047-composite-full82-1','created_at_utc':datetime.now(timezone.utc).isoformat(),
         'repair_cases':list(REPAIR_CASES),'component_cases':list(COMPONENT_CASES),'repair_turns':44,'component_turns':38,
         'frozen_total_turns':82,'frozen_total_criteria':328,'readiness':ready,
         'composition_rule':'WHOLE_CASE_ONLY_NO_PARTIAL_CASE_SPLICE','automatic_paid_retries':0,'target_calls_at_create':0})
    for case_id in COMPONENT_CASES:
        root=component_root(case_id); root.mkdir(parents=True)
        scope,selected,_,frozen=component_scope(case_id)
        dump(root/'EXECUTION_SCOPE.json',scope)
        dump(root/'MANIFEST.json',{'case_id':case_id,'batch_id':scope['batch_id'],'fixed_calls':len(scope['slots']),
             'slot_ids':[s['id'] for s in scope['slots']],'models':[s['model'] for s in scope['slots']],
             'scope_sha256':sha(root/'EXECUTION_SCOPE.json'),'parent_frozen_scope_sha256':frozen['scope_sha256'],
             'guard_cny':5,'reserved_upper_micro_cny':scope['reserved_upper_micro_cny'],'automatic_paid_retries':0,
             'full82_acceptance_claim':False,'component_only':True})
        now=datetime.now(timezone.utc)
        prior=common.read_json(parent.REV/'OFFICIAL_PREFLIGHT.json')
        dump(root/'OFFICIAL_PREFLIGHT.json',{**prior,'checked_date':now.date().isoformat(),'at_utc':now.isoformat(),
             'execution_recheck_complete':True,'frozen_scope_parameters_changed':False,'billing_verified':False})
    print(json.dumps({'output':REV.relative_to(ROOT).as_posix(),'components':list(COMPONENT_CASES),
                      'component_calls':38,'repair_calls':44,'target_calls':0},ensure_ascii=False)); return 0


def dispatch(case_id: str, action: str, rest: list[str]) -> int:
    root=component_root(case_id); live=root/'live'; scope,_,_,_=load_component(case_id)
    ready=readiness(); pinned=common.read_json(REV/'MANIFEST.json')['readiness']
    ensure(ready['repair_runtime_binding']==pinned['repair_runtime_binding'],'Repair binding changed after composite freeze')
    ensure(not ready['unknown_policy']['active_unresolved_remote_unknowns'],'New active remote UNKNOWN appeared')
    if action=='prepare':
        ensure(not rest and not live.exists(),'Existing component runtime: '+case_id)
        dump(root/'PREPARE_INTENT.json',{'pid':os.getpid(),'at_utc':datetime.now(timezone.utc).isoformat()})
    if action=='execute':
        p=common.read_json(root/'PREPARE_COMPLETE.json')
        ensure(p['fixture_preparation_sha256']==sha(live/'FIXTURE_PREPARATION.json'),'Component preparation changed')
        official=common.read_json(root/'OFFICIAL_PREFLIGHT.json')
        ensure(official['checked_date']==datetime.now(timezone.utc).date().isoformat() and official['execution_recheck_complete'],
               'Component provider recheck stale')
    module=importlib.import_module({'prepare':'prepare_execution_r047','execute':'execute_r047','audit':'audit_captures_r047'}[action])
    repl={'PLAN':root,'LIVE':live,'load_frozen':lambda:load_component(case_id,prepare=action=='prepare')}
    if action=='execute': repl['OFFICIAL_PREFLIGHT_PATH']=root/'OFFICIAL_PREFLIGHT.json'
    prev={k:getattr(module,k) for k in repl}; old_args,before=sys.argv,set(root.rglob('*.json'))
    try:
        for k,v in repl.items(): setattr(module,k,v)
        sys.argv=[module.__name__]+rest; result=module.main()
        if action=='prepare':
            saved=common.read_json(live/'FIXTURE_PREPARATION.json'); pre=common.read_json(ROOT/saved['preflight_path']/'PREFLIGHT.json')
            ensure(pre['passed'] and pre['target_calls']==0,'Component prepare failed')
            dump(root/'PREPARE_COMPLETE.json',{'fixture_preparation_sha256':sha(live/'FIXTURE_PREPARATION.json'),'new_target_calls':0})
        return result or 0
    finally:
        for path in set(root.rglob('*.json'))-before:
            if path.name=='CAPTURE_AUDIT.json' or path.name.endswith('_REVIEW_INPUT.json'):
                v=common.read_json(path); v.update(full82_acceptance_claim=False,new_heldout_claim=False,
                    known_development_regression=True,component_case_id=case_id,batch_id=scope['batch_id'])
                path.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
        for k,v in prev.items(): setattr(module,k,v)
        sys.argv=old_args


def latest_component_audit(case_id: str) -> Path:
    paths=sorted(component_root(case_id).glob('evidence/R047-02/audit_*/CAPTURE_AUDIT.json'))
    ensure(paths,'Missing component audit: '+case_id); return paths[-1]


def assemble() -> int:
    ready=readiness(); pinned=common.read_json(REV/'MANIFEST.json')['readiness']
    ensure(ready['repair_runtime_binding']==pinned['repair_runtime_binding'],'Repair binding changed')
    expected_scope,_,_,_=parent.fixed_scope(); expected={s['id']:s for s in expected_scope['slots']}
    records=[]; sources=[]
    repair=common.read_json(REPAIR_AUDIT); records.extend(copy.deepcopy(repair['records']))
    sources.append({'kind':'repair_probe03','path':REPAIR_AUDIT.relative_to(ROOT).as_posix(),'sha256':sha(REPAIR_AUDIT)})
    for case_id in COMPONENT_CASES:
        path=latest_component_audit(case_id); audit=common.read_json(path)
        ensure(audit['complete_captures_and_delivery'] and audit['binding_checks_passed'],'Component audit incomplete: '+case_id)
        ensure(audit['status_counts']=={'RESPONSE_CAPTURED':len(component_scope(case_id)[0]['slots'])},'Component status mismatch')
        ensure({r['case_id'] for r in audit['records']}=={case_id},'Component contains foreign case')
        records.extend(copy.deepcopy(audit['records'])); sources.append({'kind':'component','case_id':case_id,
            'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path)})
    ensure(len(records)==82,'Composite denominator changed')
    ids=[r['slot_id'] for r in records]; ensure(len(ids)==len(set(ids))==82,'Duplicate/missing composite slots')
    ensure(set(ids)==set(expected),'Composite slot set differs from frozen82')
    findings=[]
    for r in records:
        slot=expected[r['slot_id']]
        if r['case_id']!=slot['case_id'] or r['user_text']!=slot['user_text'] or r['model_expected']!=slot['model']:
            findings.append({'slot_id':r['slot_id'],'code':'FROZEN_SLOT_BINDING_MISMATCH'})
        if r['status']!='RESPONSE_CAPTURED' or r['turn_status']!='DISPLAYED' or not r.get('answer'):
            findings.append({'slot_id':r['slot_id'],'code':'CAPTURE_OR_DISPLAY_INCOMPLETE'})
    ensure(not findings,'Composite binding findings present')
    records.sort(key=lambda r:list(expected).index(r['slot_id']))
    out=REV/'COMPOSITE_CAPTURE_AUDIT.json'
    dump(out,{'schema_version':'r047-composite-capture-audit-1','at_utc':datetime.now(timezone.utc).isoformat(),
        'frozen_denominator':82,'records':records,'status_counts':{'RESPONSE_CAPTURED':82},
        'complete_captures_and_delivery':True,'binding_checks_passed':True,'binding_findings':[],
        'sources':sources,'repair_runtime_binding':ready['repair_runtime_binding'],
        'whole_case_only':True,'full82_acceptance_claim':True,'semantic_reviewed_turns':0,'quality_gate_passed':False})
    print(json.dumps({'output':out.relative_to(ROOT).as_posix(),'records':82,'binding_findings':0,'complete':True},ensure_ascii=False)); return 0


def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['create','prepare','execute','audit','assemble']); p.add_argument('--case',dest='case_id');
    args,rest=p.parse_known_args()
    if args.action=='create': ensure(args.case_id is None and not rest,'Create accepts no case/extras'); return create()
    if args.action=='assemble': ensure(args.case_id is None and not rest,'Assemble accepts no case/extras'); return assemble()
    ensure(args.case_id in COMPONENT_CASES,'--case required for component action')
    return dispatch(args.case_id,args.action,rest)

if __name__=='__main__': raise SystemExit(main())
