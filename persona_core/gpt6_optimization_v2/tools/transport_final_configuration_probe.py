"""One explicitly justified L4 verification after correcting SSE framing capacity."""
import argparse,copy,json,sqlite3,sys,time
from pathlib import Path
from contextlib import closing
from transport_readiness_ladder import *

def prepare(audit,regression):
    old=read(audit/'READINESS_REPORT.json');require(old['readiness_passed'] and old['new_unknown_count']==0,'PRIOR_LADDER_NOT_TERMINAL')
    tests=read(read(audit/'LATEST_TESTS.json')['path']);require(tests['passed'] and tests['source_stable'],'TESTS_NOT_PASSED')
    require(all(sha(ROOT/p)==h for p,h in tests['source_bindings'].items()),'TEST_SOURCE_CHANGED')
    r=read(regression);failed=[x for x in r['results'] if x['exit_code']]
    require(r['tests']==450 and len(failed)==1 and failed[0]['module']=='test_composite_full82_repaired_r047.py'
        and r['source_bytes_unchanged_during_tests'] and r['protected_history_and_production_unchanged'],'REGRESSION_UNEXPECTED')
    require(all(sha(ROOT/p)==h for p,h in r['sources'].items()),'REGRESSION_SOURCE_CHANGED')
    require('FAILED (errors=1)' in (regression.parent/failed[0]['log']).read_text(encoding='utf-8'),'REGRESSION_ERROR_COUNT')
    protected(audit)
    plan=read(audit/'LADDER_PLAN.json');scope=copy.deepcopy(plan['levels'][-1]['scope'])
    scope['batch_id']+='-FINAL-WIRE-CAPACITY'
    scope['slots'][0].update(id='L4_FINAL',user_text='Synthetic framing-capacity verification. Write exactly 256 lines. Each line is FRAME followed by a four-digit sequential index from 0001 through 0256 and then the fixed tokens AZ BY CX. After line 0256 write TRANSPORT_FINAL_END. No introduction or extra text.')
    scope['purpose']='One justified final L4 verification after correcting SSE framing capacity; not a retry of any consumed or UNKNOWN request.'
    provider.scope_check(scope)
    new(audit/'SUPPLEMENTAL_L4_PLAN.json',{'at_utc':now(),'scope':scope,'finite_guard_cny':scope['total_guard_cny'],
        'maximum_new_requests':1,'automatic_paid_retries':0,'new_slot':'L4_FINAL','journal':plan['journal'],
        'reason':'Real L3/L4 raw SSE measured 689955/656806 bytes for roughly 2000 tokens, exposing that the 1MB wire limit could truncate valid 32768-token output. Final transport now separates 16MB wire / 1MB normalized body / 24MB IPC bounds. A completed L4 predates this hash, so one new synthetic request binds the final implementation.',
        'source_files':runner.source_bindings(),'tool_sha256':sha(__file__),'state_publisher_sha256':sha(Path(__file__).with_name('transport_readiness_ladder.py')),
        'regression':rel(regression),'regression_sha256':sha(regression),'tests':read(audit/'LATEST_TESTS.json'),
        'previous_generation_count':4,'previous_unknown_count':0,'cumulative_guard_cny':round(1.5+scope['total_guard_cny'],2)})
    new(audit/'FINAL_TRANSPORT_POLICY.json',scope['transport_policy'])
    publish(audit,'G6_07T_FINAL_TRANSPORT_VERIFICATION_PREPARED',old['results'])
    append_log(audit,'Written exception to one-request L4 default: measured SSE framing overhead exposed a finite capture bound mismatch.33/33 offline transport tests pass including >1MB SSE and real IPC; final legacy regression retains449 compatible + historical1. One new L4_FINAL, separate1.15CNY guard, no retries or reused slots.')

def execute(audit):
    plan=read(audit/'SUPPLEMENTAL_L4_PLAN.json');scope=plan['scope'];dbpath=ROOT/plan['journal']
    protected(audit);require(runner.source_bindings()==plan['source_files'],'SOURCE_CHANGED')
    require(sha(__file__)==plan['tool_sha256'],'PROBE_CHANGED')
    old=read(audit/'READINESS_REPORT.json');require(old['readiness_passed'] and old['generation_requests']==4,'OLD_LADDER_NOT_PASS')
    new(audit/'FINAL_L4_ATTEMPT_CLAIM.json',{'at_utc':now(),'pid':os.getpid(),'maximum_requests':1,'automatic_paid_retries':0,'resumable':False})
    with closing(sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True)) as db:
        require(db.execute('SELECT count(*) FROM provider_calls').fetchone()[0]==4,'UNEXPECTED_EXISTING_REQUEST')
        require(db.execute("SELECT count(*) FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchone()[0]==0,'UNKNOWN_FORBIDS_SUBMISSION')
    store=TranscriptStore(dbpath.parent);journal=provider.ProviderJournal(store);results=old['results'];passed=False;result=None
    try:
        journal.register_batch(scope);handle=store.open_session(scope['principal_id'],'SYNTHETIC_TRANSPORT','CHARACTER_SIMULATION')
        slot=scope['slots'][0];turn=store.begin_turn(handle,slot['user_text'],scope['batch_id']+':L4_FINAL')
        context={'turn_id':turn['turn_id'],'mode':handle.mode,'messages':[{'role':'user','content':slot['user_text']}]}
        new(audit/'L4_FINAL_INTENT.json',{'at_utc':now(),'scope_sha256':provider.digest(scope),'request_context_sha256':provider.digest(context)})
        publish(audit,'G6_07T_FINAL_TRANSPORT_VERIFICATION_IN_PROGRESS',results,journal)
        print(json.dumps({'slot':'L4_FINAL','one_new_request':True,'automatic_retries':0}),flush=True)
        started=time.monotonic();call=journal.call(handle,turn['turn_id'],scope['batch_id'],'L4_FINAL',context)
        life=[{'at_utc':r['at_utc'],**json.loads(r['detail_json'])} for r in store.db.execute("SELECT at_utc,detail_json FROM turn_lifecycle WHERE turn_id=? AND state='TRANSPORT_LIFECYCLE' ORDER BY seq",(turn['turn_id'],))]
        result={k:call.get(k) for k in ['call_id','slot_id','status','http_status','finish_reason','provider_model','error_category','request_sha256','raw_sha256','reserve_micro_cny','estimate_peak_micro_cny']}
        wire=store.db.execute('SELECT length(wire_bytes),wire_sha256,complete FROM transport_wire_captures WHERE call_id=?',(call['call_id'],)).fetchone()
        result.update(elapsed_seconds=round(time.monotonic()-started,3),lifecycle=life,
            usage=json.loads(call['usage_json']) if call['usage_json'] else None,raw_wire_bytes=wire[0],wire_sha256=wire[1],wire_complete=bool(wire[2]))
        passed=call['status']=='RESPONSE_CAPTURED' and call['finish_reason']=='stop' and terminal_transport(result)
        result['passed']=passed;new(audit/'L4_FINAL_RESULT.json',result);results.append(result)
    finally:
        with store.transaction():store.db.execute('UPDATE call_batches SET stopped=1')
        rows,unknown,readiness=publish(audit,'PROVIDER_READINESS_PASS_FRESH_G6_07_REQUIRED' if passed else 'WAITING_PROVIDER_READINESS',results,journal,terminal=True,passed=passed)
        if unknown:
            quarantine={'at_utc':now(),'resend_allowed':False,'old_batch_resume_allowed':False,'unknown_requests':unknown,'automatic_paid_retries':0}
            new(audit/'FINAL_L4_QUARANTINE.json',quarantine)
            atomic(dbpath.parent.parent/'QUARANTINE.json',quarantine)
        snapshot=audit/'FINAL_TRANSPORT_JOURNAL_SNAPSHOT.sqlite3'
        with closing(sqlite3.connect(snapshot)) as backup:store.db.backup(backup)
        store.close()
        new(audit/'BEFORE_FINAL_CONFIGURATION_REPORT.json',old)
        report={**old,'at_utc':now(),'status':readiness['status'],'readiness_passed':passed,'generation_requests':len(rows),'new_unknown_count':len(unknown),
            'results':results,'source_stable':runner.source_bindings()==plan['source_files'],'final_source_manifest':'SUPPLEMENTAL_L4_PLAN.json',
            'finite_guard_cny':plan['cumulative_guard_cny'],'coherent_journal_snapshot':rel(snapshot),'snapshot_sha256':sha(snapshot),
            'journal_sha256':sha(dbpath),'journal_hash_note':'Main file hash alone is insufficient when WAL exists; coherent SQLite backup is authoritative for this audit.',
            'journal_file_bindings':{p.name:sha(p) for p in dbpath.parent.glob('runtime.sqlite3*') if p.is_file() and not p.name.endswith('-shm')},
            'protected_files_unchanged':protected(audit)}
        atomic(audit/'READINESS_REPORT.json',report)
        append_log(audit,'Final configuration verification '+report['status']+'; generation_requests='+str(len(rows))+'; new_unknown='+str(len(unknown))+'. Main/WAL distinction corrected using coherent backup. No old UNKNOWN touched.')
        print(json.dumps({k:v for k,v in report.items() if k!='results'}),flush=True)
    return 0 if passed else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','execute']);p.add_argument('audit',type=Path);p.add_argument('--regression',type=Path)
    args=p.parse_args();audit=args.audit.resolve();require(audit.parent==G,'AUDIT_ROOT')
    if args.mode=='prepare':prepare(audit,args.regression.resolve())
    else:raise SystemExit(execute(audit))
