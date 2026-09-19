"""Single-use, two-slot neutral remote validation. No retry or resume entry point."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'persona_core/operational_runtime_v1'))
from transcript_store import TranscriptStore, create_sandbox, ensure, utc_now
from provider import ProviderJournal, canonical, scope_check
from provider_openrouter import make_scope, MODEL, OpenRouterAdapter
import provider_contract as contract

MANIFEST = ROOT/'persona_core/gpt6_optimization_v2/provider2_remote_runtime_20260919_01/SOURCE_MANIFEST.json'
DESTINATION = ROOT/'persona_core/operational_build_v1/evidence/PROVIDER2_REMOTE_20260919_01'
FREEZE_ID = 'PROVIDER2_REMOTE_RUNTIME_20260919_01'
REQUIRED_EVENTS = {'dns_started','dns_complete','tcp_connected','tls_connected','request_write_started',
    'request_write_complete','headers_complete','first_response_byte','first_token','provider_finish',
    'stream_done','worker_terminal','parent_receipt','child_exit'}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    import os
    with Path(path).open('xb') as stream:
        stream.write(canonical(value)+b'\n'); stream.flush(); os.fsync(stream.fileno())


def verify_source():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8-sig'))
    ensure(manifest.get('freeze_id')==FREEZE_ID and manifest.get('offline_integration_passed') is True
        and manifest.get('independent_validation_only') is True and manifest.get('semantic_acceptance') is False,
        'REMOTE_OFFLINE_FREEZE_REQUIRED')
    for name, expected in manifest['files'].items():
        path=(ROOT/name).resolve()
        ensure(path.is_relative_to(ROOT) and path.is_file() and sha(path)==expected, 'REMOTE_SOURCE_CHANGED')
    prefix='persona_core/operational_runtime_v1/'
    ensure({name for name in manifest['files'] if name.startswith(prefix) and name.endswith('.py')} ==
        {prefix+p.name for p in (ROOT/prefix).glob('*.py')}, 'REMOTE_SOURCE_MEMBERSHIP_CHANGED')
    return manifest


def assess(store, handle, turn_id, call, slot):
    events=[json.loads(row[0]) for row in store.db.execute(
        "SELECT detail_json FROM turn_lifecycle WHERE turn_id=? AND state='TRANSPORT_LIFECYCLE' ORDER BY seq", (turn_id,))]
    names={event['event'] for event in events}
    raw=store.db.execute('SELECT raw_response FROM provider_calls WHERE call_id=?',(call['call_id'],)).fetchone()[0]
    body=json.loads(raw) if raw is not None else {}
    text=store.get_turn(handle,turn_id)['assistant_text'] or ''
    usage=json.loads(call['usage_json']) if call['usage_json'] else None
    terminal=body.get('provider_terminal',{})
    observation=body.get('stream_observation',{})
    sustained=(len(text)>=8000 and observation.get('content_events',0)>=150
        and isinstance(usage,dict) and type(usage.get('completion_tokens')) is int and usage['completion_tokens']>=1000)
    captured=call['status']=='RESPONSE_CAPTURED'
    passed=captured and REQUIRED_EVENTS<=names and (slot=='SHORT_SYNTHETIC' or sustained)
    return {'slot':slot,'passed':passed,'status':call['status'],'call_id':call['call_id'],
        'http_status':call['http_status'],'terminal_status':terminal.get('status'),
        'terminal_event':terminal.get('event'),'terminal_known':bool(terminal),
        'visible_output_usable':captured,'visible_characters':len(text),'usage':usage,
        'usage_status':call['usage_status'],'estimate_status':call['estimate_status'],
        'generation_identity':call['provider_binding']['generation_identity'],
        'scope_sha256':call['provider_binding']['scope_sha256'],'source_binding':call['provider_binding']['source_binding'],
        'provider_id':call['provider_binding']['provider_id'],'model_requested':MODEL,'model_returned':call['provider_model'],
        'stream_observation':observation,'sustained_output_verified':sustained if slot=='LONG_SYNTHETIC' else None,
        'required_lifecycle_complete':REQUIRED_EVENTS<=names,'lifecycle_events':events,
        'error_category':call['error_category'],'billing_certified':False,'semantic_acceptance':False}


def run():
    manifest=verify_source()
    scope=make_scope('G6_07T_PROVIDER2_REMOTE_20260919_01')
    scope_check(scope)
    # Credentials are checked locally before consuming the intent. No network.
    key=OpenRouterAdapter().credential(); del key
    DESTINATION.mkdir(parents=True,exist_ok=False)
    write_new(DESTINATION/'VALIDATION_INTENT.json',{'at_utc':utc_now(),'source_manifest_sha256':sha(MANIFEST),
        'freeze_id':manifest['freeze_id'],'source_binding':scope['source_binding'],'scope_sha256':contract.digest(scope),
        'max_remote_requests':2,'max_submissions_per_slot':1,'automatic_paid_retries':0,
        'slots':['SHORT_SYNTHETIC','LONG_SYNTHETIC'],'intent_permanently_consumed':True,
        'retry_resume_resend_replacement_forbidden':True,'deepseek_readiness_authorized':False})
    write_new(DESTINATION/'SCOPE.json',scope)
    runtime=create_sandbox(DESTINATION/'runtime'); store=TranscriptStore(runtime)
    results=[]
    try:
        journal=ProviderJournal(store); journal.register_batch(scope)
        for slot in scope['slots']:
            verify_source()
            handle=store.open_session(scope['principal_id'],slot['entity_label'],'CHARACTER_SIMULATION')
            turn=store.begin_turn(handle,slot['user_text'],slot['id'])
            context={'turn_id':turn['turn_id'],'mode':handle.mode,'messages':[{'role':'user','content':slot['user_text']}]}
            call=journal.call(handle,turn['turn_id'],scope['batch_id'],slot['id'],context)
            result=assess(store,handle,turn['turn_id'],call,slot['id']); results.append(result)
            write_new(DESTINATION/(slot['id']+'_RESULT.json'),result)
            print(json.dumps({k:result[k] for k in ('slot','passed','status','terminal_known','visible_characters','usage_status')}),flush=True)
            if not result['passed']: break
        summary=journal.summary(scope['batch_id'])
        with store.transaction(): store.db.execute('UPDATE call_batches SET stopped=1 WHERE batch_id=?',(scope['batch_id'],))
    finally:
        store.close()
    passed=len(results)==2 and all(r['passed'] for r in results)
    unknown=summary['remote_outcome_unknown_count']
    status='REMOTE_PROVIDER2_VALIDATION_PASS' if passed else 'STOPPED_UNKNOWN' if unknown else 'STOPPED_TERMINAL_KNOWN_OR_VALIDATION_FAILURE'
    report={'at_utc':utc_now(),'status':status,'passed':passed,'results':results,'summary':summary,
        'remote_generation_requests':summary['calls_submitted'],'new_remote_unknown_count':unknown,
        'source_manifest_sha256':sha(MANIFEST),'source_freeze_id':FREEZE_ID,'automatic_paid_retries':0,
        'billing_certified':False,'estimate_complete':False,'deepseek_blocker_remains_open':True,
        'g6_07_satisfied':False,'semantic_acceptance':False,'production_ready':False}
    write_new(DESTINATION/'VALIDATION_REPORT.json',report)
    return report


if __name__=='__main__':
    value=run()
    print(json.dumps({'status':value['status'],'requests':value['remote_generation_requests'],'automatic_paid_retries':0}),flush=True)
    raise SystemExit(0 if value['passed'] else 1)
