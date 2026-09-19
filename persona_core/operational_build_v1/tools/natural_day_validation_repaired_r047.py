"""Fail-closed real-natural-day checkpointing for the current repaired candidate."""
from __future__ import annotations
import argparse,hashlib,json,shutil,sqlite3,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]; PLAN=ROOT/'persona_core/operational_build_v1'
POINTER=PLAN/'evidence/R047-04/repaired_natural_day/CURRENT_CANDIDATE.json'
TOKYO=timezone(timedelta(hours=9),name='Asia/Tokyo')
sys.path.insert(0,str(ROOT/'persona_core/operational_runtime_v1'))
from provider import digest,scope_check

class ObservationGuard(ValueError): pass
def ensure(v,m):
    if not v: raise ObservationGuard(m)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def dump(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f: json.dump(v,f,ensure_ascii=False,indent=2); f.write('\n')
def file_entries(base): return [{'path':p.relative_to(base).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(base.rglob('*')) if p.is_file()]
def _exists(db,name): return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone() is not None
def _date(value): return datetime.fromisoformat(value).astimezone(TOKYO).date().isoformat()

def resolved(pointer_path=POINTER):
    pointer=load(pointer_path); ensure(pointer['schema_version']=='r047-repaired-candidate-pointer-1','Unsupported pointer')
    runtime=ROOT/pointer['runtime']; release=ROOT/pointer['release_manifest']; init=ROOT/pointer['initialization_checkpoint']; scope_path=ROOT/pointer['scope']
    for path,key in ((release,'release_manifest_sha256'),(init,'initialization_checkpoint_sha256'),(scope_path,'scope_sha256')):
        ensure(path.is_file() and sha(path)==pointer[key],'Pointer binding changed: '+key)
    scope=load(scope_path); scope_check(scope); ensure(scope['batch_id']==pointer['batch_id'],'Pointer/scope batch mismatch')
    ensure(len(scope['slots'])==16 and sum(s['model']=='deepseek-v4-flash' for s in scope['slots'])==15
           and sum(s['model']=='deepseek-v4-pro' for s in scope['slots'])==1,'Natural-day slot denominator changed')
    ensure(scope['slots'][8]['id']=='USER_09' and scope['slots'][8]['model']=='deepseek-v4-pro','Model switch slot changed')
    ensure(scope['total_guard_cny']==3.0 and scope['reserved_upper_micro_cny']==2_875_392 and scope['automatic_paid_retries']==0,'Natural-day guard changed')
    checkpoints=ROOT/pointer['checkpoint_root']
    return pointer,runtime,release,init,scope_path,scope,checkpoints

def prior_dates(root):
    values=[]
    if root.exists():
        for path in sorted(root.glob('*/CHECKPOINT.json')):
            v=load(path)
            if v.get('qualified_observation_day') is True: values.append(v['observed_local_date'])
    return sorted(set(values))

def logical(db):
    ensure(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','SQLite integrity failure')
    row=db.execute('SELECT state_json,state_sha256,last_event_sha256,next_sequence FROM runtime_current WHERE singleton=1').fetchone(); ensure(row,'Missing runtime_current')
    return {'state':json.loads(row[0]),'state_sha256':row[1],'event_tail_sha256':row[2],'next_sequence':row[3],
      'provider_calls':db.execute('SELECT count(*) FROM provider_calls').fetchone()[0] if _exists(db,'provider_calls') else 0,
      'turns':db.execute('SELECT count(*) FROM turns').fetchone()[0] if _exists(db,'turns') else 0,
      'runtime_events':db.execute('SELECT count(*) FROM runtime_events').fetchone()[0] if _exists(db,'runtime_events') else 0}

def evaluate(pointer_path=POINTER,now=None):
    pointer,runtime,release,init,scope_path,scope,checkpoints=resolved(pointer_path); now=now or datetime.now(timezone.utc); today=now.astimezone(TOKYO).date().isoformat()
    db=sqlite3.connect((runtime/'runtime.sqlite3').resolve().as_uri()+'?mode=ro',uri=True); db.row_factory=sqlite3.Row
    try:
        summary=logical(db); batch=db.execute('SELECT scope_sha256,stopped FROM call_batches WHERE batch_id=?',(scope['batch_id'],)).fetchone() if _exists(db,'call_batches') else None
        if batch: ensure(batch['scope_sha256']==digest(scope),'Registered scope differs from pointer scope')
        rows=[dict(r) for r in db.execute('''SELECT p.call_id,p.slot_id,p.model,p.status,p.error_category,p.session_id,p.context_json,
            t.turn_id,t.user_text,t.status AS turn_status,t.display_at_utc,t.input_provenance,t.response_provenance FROM provider_calls p
            JOIN turns t USING(turn_id) WHERE p.batch_id=? ORDER BY p.submitted_at_utc''',(scope['batch_id'],))] if _exists(db,'provider_calls') else []
        displayed=[r for r in rows if r['status']=='RESPONSE_CAPTURED' and r['turn_status']=='DISPLAYED' and r['display_at_utc']]
        today_rows=[r for r in displayed if _date(r['display_at_utc'])==today]; bad=[r for r in rows if r['status']!='RESPONSE_CAPTURED' or r['turn_status']!='DISPLAYED']
        sessions=sorted({r['session_id'] for r in rows}); proc=[]
        if len(sessions)==1 and _exists(db,'cli_process_runs'):
            proc=[dict(r) for r in db.execute('SELECT process_id,session_id,started_at_utc,ended_at_utc,exit_code FROM cli_process_runs WHERE session_id=? ORDER BY started_at_utc',(sessions[0],))]
        models=[r['model'] for r in rows]; retrieval=[]
        for r in rows:
            try: values=json.loads(r['context_json']).get('retrieval',[])
            except (TypeError,json.JSONDecodeError): values=[]
            if any(isinstance(x,dict) and x.get('record_kind')=='COMMITMENT' for x in values): retrieval.append(r['call_id'])
        commitments=summary['state'].get('commitments',{})
    finally: db.close()
    prior=prior_dates(checkpoints); already=today in prior
    qualifies=bool(today_rows) and not bad and len(sessions)==1 and not already and batch is not None and batch['stopped']==0
    pids={r['process_id'] for r in proc}
    return {'observed_at_utc':now.astimezone(timezone.utc).isoformat(),'observed_local_date':today,'candidate_release_id':pointer['candidate_release_id'],
      'batch_registered':batch is not None,'batch_stopped':None if batch is None else batch['stopped'],'submitted_calls':len(rows),'displayed_calls':len(displayed),
      'today_displayed_calls':len(today_rows),'bad_or_unresolved_calls':[{'call_id':r['call_id'],'slot_id':r['slot_id'],'status':r['status'],'turn_status':r['turn_status'],'error_category':r['error_category']} for r in bad],
      'session_ids':sessions,'single_session_continuity':len(sessions)==1 if rows else False,'model_sequence':models,
      'same_session_model_switch_observed':len(sessions)==1 and 'deepseek-v4-flash' in models and 'deepseek-v4-pro' in models,
      'cli_processes_for_session':proc,'real_restart_observed':len(pids)>=2 and all(r['ended_at_utc'] and r['exit_code']==0 for r in proc[:-1]),
      'commitments':commitments,'commitment_retrieval_call_ids':retrieval,'commitment_retrieval_observed':bool(retrieval),
      'prior_qualified_dates':prior,'today_already_counted':already,'today_can_qualify':qualifies,
      'qualified_date_count_if_checkpointed':len(prior)+(1 if qualifies else 0),'initialization_counts_as_observation':False,
      'logical_summary':summary,'scope_sha256':digest(scope),'scope_path':scope_path.relative_to(ROOT).as_posix()}

def checkpoint():
    pointer,runtime,release,init,scope_path,scope,checkpoints=resolved(); status=evaluate(); ensure(status['today_can_qualify'],'Today is not a new qualified repaired observation day')
    day=status['observed_local_date']; dest=checkpoints/day; ensure(not dest.exists(),'Checkpoint already exists for date'); dest.mkdir(parents=True)
    backup=dest/'content_backup'; backup.mkdir(); db_path=runtime/'runtime.sqlite3'; before_sha=sha(db_path)
    src=sqlite3.connect(db_path.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        before=logical(src); dst=sqlite3.connect(backup/'runtime.sqlite3')
        try: src.backup(dst)
        finally: dst.close()
    finally: src.close()
    ensure(sha(db_path)==before_sha,'Candidate database changed during checkpoint')
    if (runtime/'SANDBOX.json').is_file(): shutil.copy2(runtime/'SANDBOX.json',backup/'SANDBOX.json')
    shutil.copytree(runtime/'legacy_runtime',backup/'legacy_runtime',ignore=shutil.ignore_patterns('__pycache__')); shutil.copy2(scope_path,backup/'USER_CHAT_SCOPE.json')
    verify=sqlite3.connect((backup/'runtime.sqlite3').resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    try: after=logical(verify)
    finally: verify.close()
    ensure(before==after,'Checkpoint logical state differs')
    dates=status['prior_qualified_dates']+[day]
    record={'qualified_observation_day':True,'observed_at_utc':status['observed_at_utc'],'observed_local_date':day,'timezone':'Asia/Tokyo',
      'candidate_release_id':pointer['candidate_release_id'],'qualified_observation_dates':dates,'qualified_observation_day_count':len(dates),'minimum_distinct_real_local_dates':3,
      'candidate_release_manifest':release.relative_to(ROOT).as_posix(),'candidate_release_manifest_sha256':sha(release),
      'candidate_initialization_checkpoint':init.relative_to(ROOT).as_posix(),'candidate_initialization_checkpoint_sha256':sha(init),
      'observation_scope':scope_path.relative_to(ROOT).as_posix(),'observation_scope_sha256':sha(scope_path),'session_ids':status['session_ids'],
      'single_session_continuity':status['single_session_continuity'],'submitted_calls':status['submitted_calls'],'displayed_calls':status['displayed_calls'],
      'today_displayed_calls':status['today_displayed_calls'],'model_sequence':status['model_sequence'],'same_session_model_switch_observed':status['same_session_model_switch_observed'],
      'real_restart_observed':status['real_restart_observed'],'cli_processes_for_session':status['cli_processes_for_session'],'commitments':status['commitments'],
      'commitment_retrieval_call_ids':status['commitment_retrieval_call_ids'],'commitment_retrieval_observed':status['commitment_retrieval_observed'],
      'bad_or_unresolved_calls':status['bad_or_unresolved_calls'],'runtime_logical_summary':after,'runtime_main_db_sha256_at_checkpoint':before_sha,
      'content_backup_manifest':file_entries(backup),'initialization_without_real_user_interaction_counts':False,'same_local_date_duplicate_counts':False,
      'product_acceptance_complete':False}
    dump(dest/'CHECKPOINT.json',record); return record

def main():
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['status','checkpoint']); args=p.parse_args()
    try:
        result=evaluate() if args.action=='status' else checkpoint(); print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
    except (OSError,sqlite3.Error,ObservationGuard,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'BLOCKED','error':str(exc),'provider_calls_submitted_by_tool':0},ensure_ascii=False)); return 2
if __name__=='__main__': raise SystemExit(main())
