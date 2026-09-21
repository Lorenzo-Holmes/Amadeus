"""Build a recoverable local candidate only after recorded internal quality gates."""
from __future__ import annotations
import argparse,json,sqlite3,subprocess,sys,zipfile
from datetime import datetime,timezone
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
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2)

def validated_local_pre_http_unknowns():
    """Compatibility wrapper around the shared verified UNKNOWN policy."""
    return set(unknowns.validated_local_pre_http_unknowns())

def unresolved_remote_requests(base=None,reconciled_call_ids=None,quarantined_call_ids=None):
    """Only *active* unclassified UNKNOWNs block release.

    A validated historical quarantine remains UNKNOWN and is recorded in the
    release manifest; it is not silently converted to success/failure.
    """
    if base is None and reconciled_call_ids is None and quarantined_call_ids is None:
        return unknowns.project_unknown_status()['active_unresolved_remote_unknowns']
    base=Path(base) if base is not None else PLAN/'evidence/R047-03'
    allowed=set(reconciled_call_ids or ()) | set(quarantined_call_ids or ())
    return unknowns.scan_unknowns(base,allowed)['active_unresolved_remote_unknowns']

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--regression',type=Path,required=True)
    p.add_argument('--review',type=Path,required=True)
    p.add_argument('--audit',type=Path,required=True)
    args=p.parse_args()
    for path in [args.regression,args.review,args.audit]:ensure(path.resolve().is_relative_to(ROOT),'Evidence must be in workspace')
    tests,review,audit=load(args.regression),load(args.review),load(args.audit)
    ensure(tests['passed'] and tests['protected_history_and_production_unchanged'],'Current-source regression did not pass')
    for path,expected in tests['sources'].items():ensure(file_sha(ROOT/path)==expected,'Tested source changed: '+path)
    ensure(review['internal_gate_eligible_by_recorded_reviews'] and review['structural_review_binding_passed'],'Actual semantic gate failed')
    ensure(audit['complete_captures_and_delivery'] and audit['binding_checks_passed'],'Actual capture gate failed')
    ensure(review['audit_sha256']==file_sha(args.audit),'Quality result binds another audit')
    unknown_status=unknowns.project_unknown_status()
    ensure(not unknown_status['active_unresolved_remote_unknowns'],'Unresolved remote provider request blocks controlled release')
    state=load(PLAN/'TASK_STATE.json');matrix=load(PLAN/'ACCEPTANCE_MATRIX.json')
    for task in state['tasks']:
        if task['required_for_build_scope'] and task['id']!='R047-05':
            gate=next(g for g in matrix['gates'] if g['task_id']==task['id'])
            ensure(task['status']=='DONE' and gate['status']=='PASS','Prerequisite not accepted: '+task['id'])
            for ev in gate['evidence']:ensure((PLAN/ev).resolve().is_file(),'Missing gate evidence: '+ev)
    before=load(PLAN/'evidence/R047-02/resume_20260908T005132917742Z/RESUME_AUDIT.json')
    for item in before['protected_files']:ensure(file_sha(ROOT/item['path'])==item['sha256'],'Protected source modified')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=PLAN/'evidence/R047-05'/('candidate_'+stamp)
    out.mkdir(parents=True,exist_ok=False)
    clean=create_sandbox(out/'runtime')
    store=TranscriptStore(clean)
    try:
        controller=AdmissionController(store);runtime=RuntimeStore(store,controller);ProviderJournal(store)
        ensure(store.db.execute('SELECT count(*) FROM turns').fetchone()[0]==0,'Candidate contains test turns')
        ensure(store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0]==0,'Candidate contains test calls')
        verification=runtime.verify()
        backup=create_backup(store,runtime,out/'CLEAN_BACKUP')
    finally:store.close()
    original=load(PLAN/'evidence/R047-01/freeze_20260907T164424498856Z/EXECUTION_SCOPE.json')
    scope={**original,'batch_id':'APCORE-CANDIDATE-TEXT-'+stamp,'principal_id':'LOCAL_USER',
        'purpose':'User-started local text candidate: 16 bounded free-text turns; no automatic execution.',
        'max_output_tokens':8192,'total_guard_cny':3.0,'pricing_verified_date':'2026-09-08',
        'slots':[{'id':'USER_'+str(i).zfill(2),'model':'deepseek-v4-flash','entity_label':'USER_PRIMARY','user_text':None} for i in range(1,17)]}
    scope['reserved_upper_micro_cny']=sum((scope['max_input_bytes']+scope['input_overhead_reserve_tokens'])*RATES[s['model']][0]+scope['max_output_tokens']*RATES[s['model']][1] for s in scope['slots'])
    scope.pop('all_operations_r045_plus_r047_guard_cny',None)
    scope_check(scope);write(out/'USER_CHAT_SCOPE.json',scope)
    drill=out/'CLI_STARTUP_RECOVERY_DRILL'
    restore_backup(out/'CLEAN_BACKUP',drill,backup['manifest_sha256'])
    command=[sys.executable,'-B',str(CODE/'chat_cli.py'),'--operations','--root',str(drill),'--scope',str(out/'USER_CHAT_SCOPE.json'),'--principal','LOCAL_USER','--entity','USER_PRIMARY']
    runs=[]
    for n in [1,2]:
        proc=subprocess.run(command,input='/status\n/exit\n'.encode('utf-8'),capture_output=True,cwd=ROOT)
        (out/('CLI_RUN_'+str(n)+'.log')).write_bytes(proc.stdout+b'\n'+proc.stderr)
        ensure(proc.returncode==0,'CLI startup/reopen failed; preserved output')
        runs.append({'run':n,'exit_code':proc.returncode,'log_sha256':file_sha(out/('CLI_RUN_'+str(n)+'.log'))})
    db=sqlite3.connect((drill/'runtime.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:
        cli=db.execute('SELECT process_id,session_id,ended_at_utc,exit_code FROM cli_process_runs').fetchall()
        ensure(len(cli)==2 and cli[0][0]!=cli[1][0] and cli[0][1]==cli[1][1] and all(r[2] and r[3]==0 for r in cli),'Real CLI process recovery not demonstrated')
        ensure(db.execute('SELECT count(*) FROM provider_calls').fetchone()[0]==0,'Startup drill unexpectedly called provider')
        ensure(db.execute('SELECT count(*) FROM turns').fetchone()[0]==0,'Startup controls became dialogue history')
    finally:db.close()
    frozen_sources=[{'path':p.relative_to(ROOT).as_posix(),'sha256':file_sha(p)} for p in sorted(CODE.glob('*.py'))]
    with zipfile.ZipFile(out/'CANDIDATE_SOURCE.zip','x',zipfile.ZIP_DEFLATED) as z:
        for item in frozen_sources:z.writestr(item['path'],(ROOT/item['path']).read_bytes())
    for item in before['protected_files']:ensure(file_sha(ROOT/item['path'])==item['sha256'],'Protected source modified during release')
    manifest={'release_id':'APCORE-OPERATIONS-V1-CANDIDATE-'+stamp,'created_at_utc':utc_now(),
        'status':'CONTROLLED_LOCAL_CANDIDATE','schema':46,'production_activated':False,
        'candidate_root':str(clean.relative_to(ROOT)),'startup_scope':str((out/'USER_CHAT_SCOPE.json').relative_to(ROOT)),
        'sources':frozen_sources,'source_archive_sha256':file_sha(out/'CANDIDATE_SOURCE.zip'),
        'clean_backup':backup,'runtime_verification':verification,'genesis_sha256':file_sha(clean/'legacy_runtime/genesis/GENESIS_SNAPSHOT_R035.json'),
        'quality_evidence':str(args.review.resolve().relative_to(ROOT)),'quality_evidence_sha256':file_sha(args.review),
        'regression_evidence':str(args.regression.resolve().relative_to(ROOT)),'regression_evidence_sha256':file_sha(args.regression),
        'capture_audit':str(args.audit.resolve().relative_to(ROOT)),'capture_audit_sha256':file_sha(args.audit),
        'real_cli_processes':cli,'startup_runs':runs,'test_history_in_candidate':False,
        'independent_review':'WAITING_EXTERNAL','natural_day_validation':'WAITING_REAL_TIME',
        'qualified_natural_dates':[],'product_acceptance_complete':False,
        'new_target_calls_for_release':0,'automatic_paid_retries':0,
        'historical_unknown_policy':{
            'raw_unknown_rows_preserved':True,
            'active_unresolved_remote_unknowns':unknown_status['active_unresolved_remote_unknowns'],
            'allowed_historical_unknowns':unknown_status['allowed_historical_unknowns'],
            'quarantine_does_not_resolve_remote_execution_or_billing':True,
        }}
    write(out/'RELEASE_MANIFEST.json',manifest)
    write(out/'RELEASE_ACCEPTANCE_RECORD.json',{'at_utc':utc_now(),'engineering_release_gate':'PASS',
        'manifest_sha256':file_sha(out/'RELEASE_MANIFEST.json'),'reviewer':'CURRENT_SESSION_DEVELOPER_NONBLIND',
        'prerequisite_gates_passed':True,'clean_runtime_verified':True,'real_cli_restart_passed':True,
        'protected_history_unchanged':True,'production_activated':False,'product_acceptance_complete':False})
    print(json.dumps({'output':str(out.relative_to(ROOT)),'status':'CONTROLLED_LOCAL_CANDIDATE','target_calls':0}))
if __name__=='__main__':main()
