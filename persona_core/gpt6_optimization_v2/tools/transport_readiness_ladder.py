"""One new synthetic generation per frozen level, never a retry of an old slot."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from decimal import Decimal
import hashlib,json,math,os,sqlite3,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
G=ROOT/'persona_core/gpt6_optimization_v2'
CODE=ROOT/'persona_core/operational_runtime_v1'
sys.path[:0]=[str(CODE),str(G/'tools')]
import provider,provider_transport as pt,evaluation_runner as runner
from transcript_store import TranscriptStore,create_sandbox

def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def rel(p):return Path(p).resolve().relative_to(ROOT).as_posix()
def new(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def atomic(p,v):
    p=Path(p);tmp=p.with_suffix(p.suffix+'.g607t.tmp')
    tmp.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(tmp,p)
def require(x,message):
    if not x:raise ValueError(message)
def protected(audit):
    baseline=read(audit/'BASELINE.json')
    require(all(sha(ROOT/p)==h for p,h in baseline['historical_journals'].items()),'HISTORICAL_UNKNOWN_JOURNAL_CHANGED')
    require(all(sha(ROOT/p)==h for p,h in baseline['source'].items()
        if Path(p).name not in {'provider.py','provider_http_worker.py'}),'NONTRANSPORT_CORE_CHANGED')
    original=read(G/'resume_20260918_claim_evidence/BASELINE.json')['protected_sha256']
    require(all(sha(ROOT/p)==h for p,h in original.items()),'PROTECTED_SOURCE_OR_HISTORY_CHANGED')
    return len(original)

def append_log(audit,message):
    text='\n\n'+now()+' — '+message+' Evidence: '+rel(audit)+'.\n'
    for p in [G/'IMPLEMENTATION_LOG.md',G/'DECISION_LOG.md',ROOT/'PERSONA_CORE_DECISION_LOG.md']:
        with p.open('a',encoding='utf-8') as f:f.write(text)

def publish(audit,state,results,journal=None,terminal=False,passed=False):
    baseline=read(audit/'BASELINE.json');plan=read(audit/'LADDER_PLAN.json')
    guard=1.50+(read(audit/'SUPPLEMENTAL_L4_PLAN.json')['finite_guard_cny'] if (audit/'SUPPLEMENTAL_L4_PLAN.json').exists() else 0)
    rows=[]
    if journal:
        rows=[dict(r) for r in journal.store.db.execute('SELECT call_id,slot_id,status,request_sha256,raw_sha256,reserve_micro_cny,estimate_peak_micro_cny FROM provider_calls')]
    elif (ROOT/plan['journal']).exists():
        with sqlite3.connect((ROOT/plan['journal']).as_uri()+'?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            rows=[dict(r) for r in db.execute('SELECT call_id,slot_id,status,request_sha256,raw_sha256,reserve_micro_cny,estimate_peak_micro_cny FROM provider_calls')]
    unknown=[{**{k:r[k] for k in ('call_id','slot_id','status','request_sha256','raw_sha256','reserve_micro_cny')},
              'revision':audit.name,'journal':plan['journal']} for r in rows if r['status']=='SUBMITTED_STATUS_UNKNOWN']
    known=sum(r['estimate_peak_micro_cny'] or 0 for r in rows)
    reserve=sum(r['reserve_micro_cny'] for r in unknown)
    message=('Fresh external44 required, then frozen heldout, original82, Candidate V2 and blind package.' if passed else
        'Preserve all UNKNOWNs, stop this ladder permanently; require new external transport evidence before a separately authorized recovery.' if terminal else
        'Execute at most one new request per frozen synthetic level; stop immediately at any UNKNOWN.')
    blocker=None if not terminal or passed else 'PROVIDER_EXTERNAL_BLOCKER: no complete terminal generation at the stopped ladder level.'
    readiness={'status':'PASS' if passed else 'PROVIDER_EXTERNAL_BLOCKER' if terminal else state,
        'evidence':rel(audit/'READINESS_REPORT.json'),'paid_validation_ready':passed,'semantic_acceptance':False,
        'generation_requests':len(rows),'new_unknown_count':len(unknown),'automatic_paid_retries':0,'finite_guard_cny':guard}
    for name in ['GOAL_STATE.json','TASK_GRAPH.json','RECOVERY_CURSOR.json','VALIDATION_MATRIX.json']:
        p=G/name;value=read(p)
        value.update(CURRENT_STATE=state,NEXT_ACTION=message,RECOVERY_POINT=rel(audit/'READINESS_REPORT.json'),BLOCKER=blocker,
            updated_at_utc=now(),active_subtask='G6-07T',transport_readiness=readiness,core_validation_status='FROZEN_FOR_VALIDATION',
            IN_FLIGHT={'local_execution_active':not terminal,'external_effect':None,
                       'unresolved_requests':baseline['historical_unknowns']+unknown})
        if 'current_state' in value:value['current_state']=state
        if 'state' in value:value['state']='BLOCKED' if terminal and not passed else 'IN_PROGRESS'
        if 'paid_validation_ready' in value:value['paid_validation_ready']=passed
        if name=='TASK_GRAPH.json':
            task=next((t for t in value['tasks'] if t['id']=='G6-07T'),None)
            if task is None:
                task={'id':'G6-07T','name':'Provider Transport Root-Cause & Readiness Recovery','depends_on':['G6-06']}
                value['tasks'].insert(next(i for i,t in enumerate(value['tasks']) if t['id']=='G6-07'),task)
            task.update(status='DONE' if passed else 'BLOCKED' if terminal else 'IN_PROGRESS',evidence=[rel(audit/'ROOT_CAUSE_AUDIT.md'),rel(audit/'READINESS_REPORT.json')])
            main=next(t for t in value['tasks'] if t['id']=='G6-07')
            if 'G6-07T' not in main['depends_on']:main['depends_on'].append('G6-07T')
            main.update(status='READY' if passed else 'BLOCKED',blocker=None if passed else blocker or 'Transport readiness not yet established',transport_readiness=readiness)
        atomic(p,value)
    ledger=read(audit/'before/SPEND_LEDGER.json')
    batch={'id':audit.name,'purpose':'TRANSPORT_ONLY_NOT_SEMANTIC_ACCEPTANCE','calls':len(rows),'known_usage_estimate_cny':known/1e6,
        'unknown_count':len(unknown),'unknown_cost_reserve_cny':reserve/1e6,'guard_cny':guard,'automatic_paid_retries':0,
        'billing_certified':False,'evidence':rel(audit/'READINESS_REPORT.json'),'journal':plan['journal']}
    ledger.setdefault('readiness_batches',[]).append(batch)
    ledger['current_submitted_calls']+=len(rows)
    ledger['known_usage_estimate']=float(Decimal(str(ledger['known_usage_estimate']))+Decimal(known)/1000000)
    ledger['unknown_cost_reserve']=float(Decimal(str(ledger['unknown_cost_reserve']))+Decimal(reserve)/1000000)
    ledger.update(current_readiness=readiness,updated_at_utc=now())
    atomic(G/'SPEND_LEDGER.json',ledger)
    text=f'''# APCORE-GPT6-OPTIMIZATION-V2 — G6-07T

LAST_COMPLETED: G6-06
CURRENT_STATE: {state}
ACTIVE_TASK: G6-07 / G6-07T
RECOVERY_POINT: {rel(audit/'READINESS_REPORT.json')}
NEXT_ACTION: {message}
BLOCKER: {blocker}

Core remains FROZEN_FOR_VALIDATION. Claim/Evidence offline findings are unchanged; R8-N02-01 and R8-N06-01 remain OPEN. Current transport ladder requests={len(rows)}, new UNKNOWN={len(unknown)}, historical UNKNOWN=3, automatic_paid_retries=0. Local execution active={str(not terminal).lower()}.

Generation readiness={passed}; semantic acceptance=false. Production remains false. No new Candidate V2 or blind package; new natural days=0/3. Total submissions={ledger['current_submitted_calls']}; known usage estimate={ledger['known_usage_estimate']} CNY; UNKNOWN reserve={ledger['unknown_cost_reserve']} CNY. Reserve is not billed consumption; actual total remains unknown.
'''
    for p,start,end in [(ROOT/'PERSONA_CORE_PROGRESS.md','<!-- G6_ACTIVE_START -->','<!-- G6_ACTIVE_END -->'),
        (G/'CURRENT_EXECUTION_RUNBOOK.md','<!-- TRANSPORT_READINESS_ACTIVE_START -->','<!-- TRANSPORT_READINESS_ACTIVE_END -->')]:
        prior=p.read_text(encoding='utf-8');a=prior.index(start);b=prior.index(end)+len(end)
        p.write_text(prior[:a]+start+'\n'+text+end+prior[b:],encoding='utf-8')
    return rows,unknown,readiness

def prepare(audit):
    require(read(audit/'L0_REPORT.json')['preflight_passed'],'L0_NOT_PASS')
    checks=read(read(audit/'LATEST_TESTS.json')['path'])
    require(checks['passed'] and checks['source_stable'],'LOCAL_TRANSPORT_TESTS_NOT_PASS')
    require(all(sha(ROOT/p)==h for p,h in checks['source_bindings'].items()),'LOCAL_TEST_SOURCE_CHANGED')
    protected(audit)
    regression=ROOT/'persona_core/operational_build_v1/evidence/R047-03/regression_20260918T080600715925Z/REGRESSION.json'
    r=read(regression);fail=[x for x in r['results'] if x['exit_code']]
    require(len(r['results'])==43 and r['tests']==450 and len(fail)==1 and fail[0]['module']=='test_composite_full82_repaired_r047.py','REGRESSION_UNEXPECTED')
    log=(regression.parent/fail[0]['log']).read_text(encoding='utf-8')
    require('FAILED (errors=1)' in log and 'test_repair_runtime_matches_current' in log and r['source_bytes_unchanged_during_tests'] and r['protected_history_and_production_unchanged'],'REGRESSION_BINDING')
    require(all(sha(ROOT/p)==h for p,h in r['sources'].items()),'REGRESSION_SOURCE_CHANGED')
    new(audit/'REGRESSION_ADJUDICATION.json',{'report':rel(regression),'sha256':sha(regression),'tests':450,'compatible_pass':449,
        'expected_historical_identity_error':1,'unexpected_failures':0,'raw_passed':False})
    levels=[('L1',32,512,False,90,30,'Print Q.'),
        ('L2',256,1024,False,120,45,'Print exactly the tokens S001 through S032 in order, separated by spaces. No other text.'),
        ('L3',4096,1024,True,240,90,'Synthetic counter test. Start x=7. Repeat x=(13*x+11) mod 97 exactly 20 times. Output only the final integer.'),
        ('L4',32768,24576,True,600,120,'Synthetic transport payload. Write exactly 128 lines. Each line is FRAME followed by a four-digit sequential index from 0001 through 0128 and then the fixed tokens AZ BY CX. After line 0128 write TRANSPORT_END on its own line. No introduction or extra text.')]
    plan=[];stamp=audit.name.removeprefix('transport_readiness_ladder_')
    evidence=ROOT/'persona_core/operational_build_v1/evidence'/('G6_TRANSPORT_LADDER_'+stamp)
    for level,cap,inbytes,thinking,total,read_limit,prompt in levels:
        reserve=(inbytes+4096)*9+cap*27
        scope={'schema_version':'apcore-provider-scope-3','capacity_policy_id':'EXTENDED_MAX_REASONING_20260911',
            'output_budget_includes_reasoning':True,'automatic_capacity_escalation':False,
            'batch_id':'APCORE-G6-07T-'+stamp+'-'+level,'principal_id':'TRANSPORT_OPERATOR','purpose':'Independent synthetic transport ladder; no Persona or evaluation content.',
            'endpoint':provider.ENDPOINT,'automatic_paid_retries':0,'pricing_verified_date':datetime.now(timezone.utc).astimezone().date().isoformat(),
            'pricing_sources':['https://api-docs.deepseek.com/zh-cn/quick_start/pricing/'],'max_input_bytes':inbytes,'max_output_tokens':cap,
            'input_overhead_reserve_tokens':4096,'reserved_upper_micro_cny':reserve,'total_guard_cny':math.ceil(reserve/10000)/100,
            'thinking':{'type':'enabled' if thinking else 'disabled'},'reasoning_effort':'max' if thinking else None,'stream':True,'tools_allowed':False,
            'request_timeout_seconds':total,'transport_policy':{'version':pt.VERSION,'connect_timeout_seconds':15,'read_timeout_seconds':read_limit,'worker_deadline_seconds':total-5},
            'peak_rates_cny_per_million_tokens':{'deepseek-v4-pro':{'input_miss':9,'output':27,'input_hit':.3}},
            'slots':[{'id':level,'model':'deepseek-v4-pro','entity_label':'SYNTHETIC_TRANSPORT','user_text':prompt}]}
        provider.scope_check(scope);plan.append({'level':level,'scope':scope})
    require(sum(x['scope']['reserved_upper_micro_cny'] for x in plan)<=1500000,'LADDER_FINITE_GUARD')
    bindings=runner.source_bindings()
    new(audit/'SOURCE_MANIFEST.json',{'files':bindings,'transport_files':{rel(CODE/p):sha(CODE/p) for p in ['provider.py','provider_http_worker.py','provider_transport.py']}})
    new(audit/'LADDER_PLAN.json',{'at_utc':now(),'levels':plan,'journal':rel(evidence/'runtime/runtime.sqlite3'),'finite_guard_cny':1.5,
        'request_limit_per_level':1,'automatic_paid_retries':0,'stop_on_unknown':True,'semantic_acceptance':False,'tool_sha256':sha(__file__),
        'L4_is_formal_transport_configuration':True,'L4_reasoning':'enabled/max','future_G6_07_must_pin_same_transport_policy':True})
    publish(audit,'G6_07T_LADDER_PREPARED',[])
    append_log(audit,'Offline transport29/29 and legacy449 compatible + 1 retained identity error verified. L0 authenticated actual worker HTTP200. Freeze four levels, one request each,1.50CNY total guard. No generation submitted yet.')
    return plan

def terminal_transport(result):
    names={e['event'] for e in result['lifecycle']}
    return (result['http_status']==200 and result['finish_reason'] in {'stop','length'} and result.get('usage') is not None
        and result['status'] in {'RESPONSE_CAPTURED','RESPONSE_REJECTED'}
        and result['error_category'] in {None,'TRUNCATED_OR_OTHER_FINISH'}
        and {'request_write_complete','headers_complete','provider_finish','stream_done','worker_terminal','child_exit','parent_receipt'}.issubset(names))

def run(audit,remaining_after_terminal=False):
    plan=read(audit/'LADDER_PLAN.json');protected(audit)
    require(runner.source_bindings()==read(audit/'SOURCE_MANIFEST.json')['files'],'SOURCE_CHANGED')
    results=[];dbpath=ROOT/plan['journal']
    if remaining_after_terminal:
        # This narrow continuation cannot touch a consumed slot or any UNKNOWN.
        # The first result remains REJECTED; only its transport terminal evidence
        # is adjudicated against the user's explicit L1 criterion.
        first=read(audit/'L1_RESULT.json');prior=read(audit/'READINESS_REPORT.json')
        require(prior['generation_requests']==1 and prior['new_unknown_count']==0
            and sha(dbpath)==prior['journal_sha256'] and first['slot_id']=='L1'
            and first['status']=='RESPONSE_REJECTED' and first['finish_reason']=='length'
            and terminal_transport(first),'TERMINAL_ONLY_CONTINUATION_NOT_ALLOWED')
        with sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True) as db:
            require(db.execute('SELECT count(*) FROM provider_calls').fetchone()[0]==1,'UNEXPECTED_CONSUMED_SLOTS')
            require(db.execute("SELECT count(*) FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchone()[0]==0,'UNKNOWN_FORBIDS_CONTINUATION')
        new(audit/'CONTINUATION_AFTER_TERMINAL_CLAIM.json',{'at_utc':now(),'pid':os.getpid(),'tool_sha256':sha(__file__),
            'original_plan_sha256':sha(audit/'LADDER_PLAN.json'),'original_result_sha256':sha(audit/'L1_RESULT.json'),
            'original_report_sha256':sha(audit/'READINESS_REPORT.json'),'allowed_new_slots':['L2','L3','L4'],
            'no_consumed_slot_resubmission':True,'L1_journal_status_preserved':True,'automatic_paid_retries':0})
        new(audit/'L1_TRANSPORT_ADJUDICATION.json',{'at_utc':now(),'user_L1_criterion':'SUBMITTED -> HTTP RESPONSE -> TERMINAL',
            'terminal_transport_observed':True,'usable_reply':False,'journal_status':'RESPONSE_REJECTED','finish_reason':'length',
            'original_pass_false_preserved':True,'source_result_sha256':sha(audit/'L1_RESULT.json'),
            'reason':'Initial harness incorrectly required an untruncated reply for a minimal transport-only terminal check. No provider request is repeated; L4 still requires RESPONSE_CAPTURED and stop.'})
        new(audit/'INITIAL_STOP_REPORT.json',prior)
        results=[{**first,'passed':True,'transport_only_terminal_adjudication':'L1_TRANSPORT_ADJUDICATION.json','usable_reply':False}]
        levels=plan['levels'][1:]
    else:
        require(sha(__file__)==plan['tool_sha256'],'LADDER_TOOL_CHANGED')
        new(audit/'GENERATION_ATTEMPT_CLAIM.json',{'at_utc':now(),'pid':os.getpid(),'resumable':False,'automatic_paid_retries':0})
        create_sandbox(dbpath.parent);levels=plan['levels']
    store=TranscriptStore(dbpath.parent);journal=provider.ProviderJournal(store)
    handle=store.open_session('TRANSPORT_OPERATOR','SYNTHETIC_TRANSPORT','CHARACTER_SIMULATION')
    passed=False;exception=None
    try:
        for item in levels:
            scope=item['scope'];slot=scope['slots'][0]
            require(runner.source_bindings()==read(audit/'SOURCE_MANIFEST.json')['files'],'SOURCE_CHANGED')
            journal.register_batch(scope)
            turn=store.begin_turn(handle,slot['user_text'],scope['batch_id']+':'+slot['id'])
            context={'turn_id':turn['turn_id'],'mode':handle.mode,'messages':[{'role':'user','content':slot['user_text']}]}
            new(audit/(slot['id']+'_INTENT.json'),{'at_utc':now(),'slot_id':slot['id'],'scope_sha256':provider.digest(scope),'context_sha256':provider.digest(context),'automatic_paid_retries':0})
            publish(audit,'G6_07T_'+slot['id']+'_IN_PROGRESS',results,journal)
            print(json.dumps({'level':slot['id'],'phase':'ONE_NEW_REQUEST','model':slot['model'],'max_tokens':scope['max_output_tokens'],'thinking':scope['thinking'],'total_deadline':scope['request_timeout_seconds']}),flush=True)
            started=time.monotonic()
            call=journal.call(handle,turn['turn_id'],scope['batch_id'],slot['id'],context)
            lifecycle=[{'at_utc':r['at_utc'],**json.loads(r['detail_json'])} for r in store.db.execute("SELECT at_utc,detail_json FROM turn_lifecycle WHERE turn_id=? AND state='TRANSPORT_LIFECYCLE' ORDER BY seq",(turn['turn_id'],))]
            eventnames={r['event'] for r in lifecycle}
            result={k:call.get(k) for k in ['call_id','slot_id','status','http_status','finish_reason','provider_model','error_category','request_sha256','raw_sha256','reserve_micro_cny','estimate_peak_micro_cny']}
            result.update(elapsed_seconds=round(time.monotonic()-started,3),lifecycle=lifecycle,usage=json.loads(call['usage_json']) if call['usage_json'] else None)
            result['passed']=(call['status']=='RESPONSE_CAPTURED' and call['finish_reason']=='stop' and
                {'request_write_complete','headers_complete','first_response_byte','provider_finish','stream_done','worker_terminal','child_exit','parent_receipt'}.issubset(eventnames))
            if slot['id']!='L4':
                result['passed']=terminal_transport(result)
                result['usable_reply']=call['status']=='RESPONSE_CAPTURED'
            new(audit/(slot['id']+'_RESULT.json'),result);results.append(result)
            print(json.dumps({k:v for k,v in result.items() if k not in {'lifecycle','usage'}}),flush=True)
            append_log(audit,slot['id']+' result '+call['status']+'; no retry. '+str(call['error_category']))
            if not result['passed']:break
        passed=len(results)==4 and all(r['passed'] for r in results)
    except BaseException as exc:
        exception=type(exc).__name__
        new(audit/'EXECUTION_ERROR.json',{'at_utc':now(),'error_class':exception,'sensitive_text_omitted':True})
    finally:
        with store.transaction():store.db.execute('UPDATE call_batches SET stopped=1')
        rows,unknown,readiness=publish(audit,'PROVIDER_READINESS_PASS_FRESH_G6_07_REQUIRED' if passed else 'WAITING_PROVIDER_READINESS',results,journal,terminal=True,passed=passed)
        if not passed:
            quarantine={'at_utc':now(),'resend_allowed':False,'old_batch_resume_allowed':False,'unknown_requests':unknown,'automatic_paid_retries':0,'replay_allowed':False}
            if remaining_after_terminal:
                new(audit/'INITIAL_QUARANTINE.json',read(dbpath.parent.parent/'QUARANTINE.json'))
                atomic(dbpath.parent.parent/'QUARANTINE.json',quarantine)
            else:new(dbpath.parent.parent/'QUARANTINE.json',quarantine)
        report={'schema':'g6-transport-ladder-1','at_utc':now(),'status':readiness['status'],'readiness_passed':passed,
            'generation_requests':len(rows),'new_unknown_count':len(unknown),'historical_unknown_count':3,'results':results,
            'error_class':exception,'journal':plan['journal'],'automatic_paid_retries':0,'finite_guard_cny':1.5,
            'semantic_acceptance':False,'production_activated':False,'protected_files_unchanged':protected(audit),
            'source_stable':runner.source_bindings()==read(audit/'SOURCE_MANIFEST.json')['files'],
            'local_execution_active':False,'probe_resumable':False}
        store.close();report['journal_sha256']=sha(dbpath)
        if remaining_after_terminal:atomic(audit/'READINESS_REPORT.json',report)
        else:new(audit/'READINESS_REPORT.json',report)
        append_log(audit,'Ladder ended '+report['status']+'; new requests='+str(len(rows))+', new UNKNOWN='+str(len(unknown))+'. Historical3 UNKNOWNs preserved. No acceptance gates advanced.')
        print(json.dumps({k:v for k,v in report.items() if k!='results'}),flush=True)
    return 0 if passed else 2

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','execute','remaining-after-terminal']);parser.add_argument('audit',type=Path)
    args=parser.parse_args();audit=args.audit.resolve()
    require(audit.parent==G and audit.name.startswith('transport_readiness_ladder_'),'INVALID_AUDIT_ROOT')
    if args.mode=='prepare':prepare(audit)
    else:raise SystemExit(run(audit,args.mode=='remaining-after-terminal'))
