"""Build a clean repaired local candidate from the composite 82/328 gate.

This is a zero-target-call release operation.  It binds the repaired composite
capture/review, current-source regression, new blank independent-review package,
and the complete historical UNKNOWN quarantine policy.  It creates a pristine
schema46 runtime, proves two real CLI process starts recover the same session,
and publishes a hashed pointer consumed by the repaired natural-day validator.
"""
from __future__ import annotations

import argparse, hashlib, json, sqlite3, subprocess, sys, zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
PLAN=ROOT/'persona_core/operational_build_v1'
CODE=ROOT/'persona_core/operational_runtime_v1'
sys.path.insert(0,str(CODE))
from transcript_store import TranscriptStore,create_sandbox,ensure,file_sha,utc_now
from admission import AdmissionController
from runtime_store import RuntimeStore
from provider import ProviderJournal,scope_check,RATES
from recovery import create_backup,restore_backup
import unknown_quarantine_r047 as unknowns

AUDIT=PLAN/'evidence/R047-03/composite_full82_repaired_01/COMPOSITE_CAPTURE_AUDIT.json'
REVIEW=PLAN/'evidence/R047-03/composite_full82_repaired_01/COMPOSITE_SEMANTIC_REVIEW.json'
BLIND=PLAN/'evidence/R047-04/repaired_independent_review_01/PACKAGE_REPORT.json'
BASE_SCOPE=PLAN/'evidence/R047-04/NATURAL_DAY_OBSERVATION_SCOPE.json'
POINTER=PLAN/'evidence/R047-04/repaired_natural_day/CURRENT_CANDIDATE.json'
TOKYO=timezone(timedelta(hours=9),name='Asia/Tokyo')

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f: json.dump(v,f,ensure_ascii=False,indent=2); f.write('\n')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def validate_repaired_evidence():
    audit,review,blind=load(AUDIT),load(REVIEW),load(BLIND)
    ensure(audit['frozen_denominator']==82 and len(audit['records'])==82
           and audit['complete_captures_and_delivery'] and audit['binding_checks_passed'],'Composite capture gate failed')
    ensure(review['reviewed_turns']==82 and review['explicit_criteria_decisions']==328
           and review['verdict_counts']=={'PASS':328} and review['quality_pass']
           and review['unresolved_critical_findings']==0 and review['unresolved_major_findings']==0,
           'Composite semantic/quality gate failed')
    ensure(review['composite_capture_audit_sha256']==file_sha(AUDIT),'Composite review binds another audit')
    ensure(review['independent_acceptance_claim'] is False and review['product_acceptance_complete'] is False,
           'Developer gate cannot claim independent/product acceptance')
    ensure(blind['passed'] and blind['actual_turns']==82 and blind['blank_criteria']==328
           and blind['developer_scores_in_public_package'] is False and blind['model_identity_in_public_package'] is False,
           'Repaired blind package gate failed')
    package=ROOT/blind['reviewer_package']; ensure(package.is_file() and file_sha(package)==blind['reviewer_package_sha256'],
           'Repaired reviewer package binding changed')
    return {'audit_sha256':file_sha(AUDIT),'review_sha256':file_sha(REVIEW),
            'blind_report_sha256':file_sha(BLIND),'reviewer_package':blind['reviewer_package'],
            'reviewer_package_sha256':blind['reviewer_package_sha256']}

def candidate_scope(stamp:str):
    scope=load(BASE_SCOPE)
    scope.update(batch_id='APCORE-R047-REPAIRED-NATURAL-DAY-'+stamp,principal_id='LOCAL_USER',
        purpose='Repaired controlled candidate: 16 genuine user-started longitudinal text turns across real natural dates; no automatic execution.',
        pricing_verified_date=datetime.now(timezone.utc).date().isoformat(),automatic_paid_retries=0)
    ensure(len(scope['slots'])==16 and sum(s['model']=='deepseek-v4-flash' for s in scope['slots'])==15
           and sum(s['model']=='deepseek-v4-pro' for s in scope['slots'])==1,'Candidate natural-day slot contract changed')
    ensure(scope['slots'][8]['id']=='USER_09' and scope['slots'][8]['model']=='deepseek-v4-pro','Candidate switch slot changed')
    rates=scope['peak_rates_cny_per_million_tokens']
    scope['reserved_upper_micro_cny']=sum((scope['max_input_bytes']+scope['input_overhead_reserve_tokens'])*rates[s['model']]['input_miss']
        +scope['max_output_tokens']*rates[s['model']]['output'] for s in scope['slots'])
    scope_check(scope)
    ensure(scope['total_guard_cny']==3.0 and scope['reserved_upper_micro_cny']==2_875_392,'Candidate guard changed')
    return scope

def main():
    p=argparse.ArgumentParser(); p.add_argument('--regression',type=Path,required=True); args=p.parse_args()
    regression=args.regression.resolve(); ensure(regression.is_relative_to(ROOT),'Regression outside workspace')
    tests=load(regression); ensure(tests['passed'] and tests['protected_history_and_production_unchanged'] and tests['target_calls']==0,
                                  'Current-source regression failed')
    for path,expected in tests['sources'].items(): ensure(file_sha(ROOT/path)==expected,'Tested source changed: '+path)
    repaired=validate_repaired_evidence()
    status=unknowns.project_unknown_status(); ensure(not status['active_unresolved_remote_unknowns'],'Active remote UNKNOWN blocks repaired release')
    state=load(PLAN/'TASK_STATE.json'); matrix=load(PLAN/'ACCEPTANCE_MATRIX.json')
    for task in state['tasks']:
        if task['required_for_build_scope'] and task['id']!='R047-05':
            gate=next(g for g in matrix['gates'] if g['task_id']==task['id'])
            ensure(task['status']=='DONE' and gate['status']=='PASS','Build prerequisite not accepted: '+task['id'])
    protected=load(PLAN/'evidence/R047-02/resume_20260908T005132917742Z/RESUME_AUDIT.json')
    for item in protected['protected_files']: ensure(file_sha(ROOT/item['path'])==item['sha256'],'Protected source modified')

    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=PLAN/'evidence/R047-05'/('repaired_candidate_'+stamp); out.mkdir(parents=True,exist_ok=False)
    clean=create_sandbox(out/'runtime'); store=TranscriptStore(clean)
    try:
        controller=AdmissionController(store); runtime=RuntimeStore(store,controller); ProviderJournal(store)
        ensure(store.db.execute('SELECT count(*) FROM turns').fetchone()[0]==0,'Candidate contains test turns')
        ensure(store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0]==0,'Candidate contains test calls')
        verification=runtime.verify(); current=store.db.execute('SELECT state_json,state_sha256,last_event_sha256,next_sequence FROM runtime_current WHERE singleton=1').fetchone()
        initialization={'observed_at_utc':utc_now(),'timezone':'Asia/Tokyo','observed_local_date':datetime.now(timezone.utc).astimezone(TOKYO).date().isoformat(),
            'checkpoint_kind':'REPAIRED_CANDIDATE_INITIALIZATION','qualified_observation_dates':[],'qualified_observation_day_count':0,
            'initialization_without_real_user_interaction_counts_as_observation':False,'schema_version':46,
            'state_sha256':current[1],'event_tail_sha256':current[2],'next_sequence':current[3],
            'provider_calls':0,'turns':0,'runtime_events':store.db.execute('SELECT count(*) FROM runtime_events').fetchone()[0],
            'genesis_sha256':json.loads(current[0])['genesis_sha256'],'product_acceptance_complete':False}
        backup=create_backup(store,runtime,out/'CLEAN_BACKUP')
    finally: store.close()
    write(out/'INITIALIZATION_CHECKPOINT.json',initialization)
    scope=candidate_scope(stamp); write(out/'USER_CHAT_SCOPE.json',scope)

    drill=out/'CLI_STARTUP_RECOVERY_DRILL'; restore_backup(out/'CLEAN_BACKUP',drill,backup['manifest_sha256'])
    command=[sys.executable,'-B',str(CODE/'chat_cli.py'),'--operations','--root',str(drill),'--scope',str(out/'USER_CHAT_SCOPE.json'),
             '--principal','LOCAL_USER','--entity','USER_PRIMARY']
    runs=[]
    for n in (1,2):
        proc=subprocess.run(command,input='/status\n/exit\n'.encode('utf-8'),capture_output=True,cwd=ROOT)
        log=out/('CLI_RUN_'+str(n)+'.log'); log.write_bytes(proc.stdout+b'\n'+proc.stderr)
        ensure(proc.returncode==0,'Repaired candidate CLI startup/reopen failed')
        runs.append({'run':n,'exit_code':proc.returncode,'log_sha256':file_sha(log)})
    db=sqlite3.connect((drill/'runtime.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:
        cli=db.execute('SELECT process_id,session_id,ended_at_utc,exit_code FROM cli_process_runs').fetchall()
        ensure(len(cli)==2 and cli[0][0]!=cli[1][0] and cli[0][1]==cli[1][1] and all(r[2] and r[3]==0 for r in cli),
               'Real repaired CLI process recovery not demonstrated')
        ensure(db.execute('SELECT count(*) FROM provider_calls').fetchone()[0]==0 and db.execute('SELECT count(*) FROM turns').fetchone()[0]==0,
               'Startup drill created provider/turn history')
    finally: db.close()
    sources=[{'path':p.relative_to(ROOT).as_posix(),'sha256':file_sha(p)} for p in sorted(CODE.glob('*.py'))]
    with zipfile.ZipFile(out/'CANDIDATE_SOURCE.zip','x',zipfile.ZIP_DEFLATED) as z:
        for item in sources: z.writestr(item['path'],(ROOT/item['path']).read_bytes())
    for item in protected['protected_files']: ensure(file_sha(ROOT/item['path'])==item['sha256'],'Protected source modified during repaired release')
    manifest={'release_id':'APCORE-OPERATIONS-V1-REPAIRED-CANDIDATE-'+stamp,'created_at_utc':utc_now(),
      'status':'CONTROLLED_LOCAL_REPAIRED_CANDIDATE','schema':46,'production_activated':False,
      'candidate_root':clean.relative_to(ROOT).as_posix(),'startup_scope':(out/'USER_CHAT_SCOPE.json').relative_to(ROOT).as_posix(),
      'startup_scope_sha256':file_sha(out/'USER_CHAT_SCOPE.json'),'initialization_checkpoint':(out/'INITIALIZATION_CHECKPOINT.json').relative_to(ROOT).as_posix(),
      'initialization_checkpoint_sha256':file_sha(out/'INITIALIZATION_CHECKPOINT.json'),'sources':sources,'source_archive_sha256':file_sha(out/'CANDIDATE_SOURCE.zip'),
      'clean_backup':backup,'runtime_verification':verification,'genesis_sha256':file_sha(clean/'legacy_runtime/genesis/GENESIS_SNAPSHOT_R035.json'),
      'composite_capture_audit':AUDIT.relative_to(ROOT).as_posix(),'composite_capture_audit_sha256':file_sha(AUDIT),
      'composite_semantic_review':REVIEW.relative_to(ROOT).as_posix(),'composite_semantic_review_sha256':file_sha(REVIEW),
      'regression_evidence':regression.relative_to(ROOT).as_posix(),'regression_evidence_sha256':file_sha(regression),
      'blind_reviewer_package':repaired['reviewer_package'],'blind_reviewer_package_sha256':repaired['reviewer_package_sha256'],
      'real_cli_processes':cli,'startup_runs':runs,'test_history_in_candidate':False,
      'independent_review':'WAITING_EXTERNAL_REPAIRED_PACKAGE','natural_day_validation':'WAITING_REAL_TIME_RESTART_FROM_ZERO',
      'qualified_natural_dates':[],'old_candidate_day1_counts_for_this_candidate':False,'product_acceptance_complete':False,
      'new_target_calls_for_release':0,'automatic_paid_retries':0,
      'historical_unknown_policy':{'raw_unknown_rows_preserved':True,'active_unresolved_remote_unknowns':status['active_unresolved_remote_unknowns'],
          'allowed_historical_unknowns':status['allowed_historical_unknowns'],'quarantine_does_not_resolve_remote_execution_or_billing':True}}
    write(out/'RELEASE_MANIFEST.json',manifest)
    write(out/'RELEASE_ACCEPTANCE_RECORD.json',{'at_utc':utc_now(),'engineering_release_gate':'PASS',
      'manifest_sha256':file_sha(out/'RELEASE_MANIFEST.json'),'reviewer':'CURRENT_SESSION_DEVELOPER_NONBLIND',
      'composite_82_328_gate_passed':True,'clean_runtime_verified':True,'real_cli_restart_passed':True,
      'protected_history_unchanged':True,'production_activated':False,'independent_review_complete':False,
      'natural_day_validation_complete':False,'product_acceptance_complete':False})
    guide='''# Repaired Candidate Launch / R047-04\n\nThis candidate starts with zero dialogue/provider history. Use the exact USER_CHAT_SCOPE.json and the existing chat_cli.py entrypoint. Natural-day acceptance restarts at 0/3 for this repaired candidate; the old candidate's 2026-09-11 checkpoint is historical only. Genuine user text is required. USER_09 is pinned to Pro so the three-day run can demonstrate same-instance model switching. Any submitted-status UNKNOWN stops this candidate batch and is never resent automatically.\n'''
    (out/'LAUNCH_AND_RECOVERY_GUIDE.md').write_text(guide,encoding='utf-8')
    pointer={'schema_version':'r047-repaired-candidate-pointer-1','updated_at_utc':utc_now(),'candidate_release_id':manifest['release_id'],
      'candidate_dir':out.relative_to(ROOT).as_posix(),'runtime':clean.relative_to(ROOT).as_posix(),
      'release_manifest':(out/'RELEASE_MANIFEST.json').relative_to(ROOT).as_posix(),'release_manifest_sha256':file_sha(out/'RELEASE_MANIFEST.json'),
      'initialization_checkpoint':(out/'INITIALIZATION_CHECKPOINT.json').relative_to(ROOT).as_posix(),
      'initialization_checkpoint_sha256':file_sha(out/'INITIALIZATION_CHECKPOINT.json'),
      'scope':(out/'USER_CHAT_SCOPE.json').relative_to(ROOT).as_posix(),'scope_sha256':file_sha(out/'USER_CHAT_SCOPE.json'),
      'batch_id':scope['batch_id'],'checkpoint_root':'persona_core/operational_build_v1/evidence/R047-04/repaired_natural_day/checkpoints',
      'qualified_dates':[],'minimum_distinct_real_dates':3,'product_acceptance_complete':False}
    if POINTER.exists():
        history=POINTER.parent/('POINTER_HISTORY_'+stamp+'.json'); history.write_bytes(POINTER.read_bytes()); POINTER.unlink()
    write(POINTER,pointer)
    print(json.dumps({'output':out.relative_to(ROOT).as_posix(),'status':'CONTROLLED_LOCAL_REPAIRED_CANDIDATE',
                      'release_manifest':(out/'RELEASE_MANIFEST.json').relative_to(ROOT).as_posix(),
                      'pointer':POINTER.relative_to(ROOT).as_posix(),'target_calls':0},ensure_ascii=False))

if __name__=='__main__': main()
