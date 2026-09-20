"""Zero-provider-call preflight of the real formal external44 construction path."""
from pathlib import Path
import argparse
import json
import socket
import sys
import uuid
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import evaluation_runner as runner

def preflight(acceptance_config_file,transport_policy_file,network_route_policy_file,*,output=None):
    provider,transcript,operations,*_=runner.runtime_modules()
    from accepted_output import session_mode
    from semantic_binding import require_session,strict_selected
    name='binding_preflight_'+uuid.uuid4().hex
    with patch.object(socket.socket,'connect',side_effect=AssertionError('PREFLIGHT_NETWORK_FORBIDDEN')), \
         patch.object(socket.socket,'connect_ex',side_effect=AssertionError('PREFLIGHT_NETWORK_FORBIDDEN')), \
         patch.object(provider.ProviderJournal,'call',side_effect=AssertionError('PREFLIGHT_PROVIDER_CALL_FORBIDDEN')) as calls:
        runner.prepare(name,suite='external44',offline=True,formal_validation=True,
            acceptance_config_file=acceptance_config_file,primary='deepseek-v4-pro',secondary='deepseek-flash',
            max_output_tokens=32768,api_protocol='responses',transport_policy_file=transport_policy_file,
            network_route_policy_file=network_route_policy_file)
        root=runner.revision_root(name)
        manifest,scope,preparation=runner.verify_sources(root)
        binding=scope['semantic_acceptance_binding']
        store=transcript.TranscriptStore(root/'runtime')
        try:
            session_checks=[]
            for entry in preparation['sessions'].values():
                h=store.resume(scope['principal_id'],entry['session_id'])
                chat=operations.open_chat(store,h,scope)
                require_session(store.db,h.session_id,binding)
                assert chat.acceptance_mode==session_mode(store.db,h.session_id)==binding['semantic_acceptance_mode']
                session_checks.append({'session_id':h.session_id,'mode':chat.acceptance_mode,
                    'adapter_version':chat.acceptance.admit.version if chat.acceptance.admit else None,
                    'consumer_purpose':binding.get('consumer_purpose','BOUNDED_CLAIM'),'policy_and_source_persisted':True})
            # Build the actual context in each selected target session, without
            # invoking a provider or consuming a journal slot.
            requests=[]; seen=set()
            for slot in scope['slots']:
                if slot['case_id'] in seen: continue
                seen.add(slot['case_id'])
                h=store.resume(scope['principal_id'],preparation['sessions'][slot['case_id']]['session_id'])
                chat=operations.open_chat(store,h,scope)
                turn=store.begin_turn(h,slot['user_text'],'OFFLINE_BINDING_PREVIEW')
                context=chat.build_request_context(turn['turn_id'])
                assert context['messages'][-1]=={'role':'user','content':slot['user_text']}
                if strict_selected(binding):
                    assert context['semantic_plan_request']['authority']=='PROPOSAL_ONLY'
                else:
                    assert 'semantic_plan_request' not in context
                    assert context['display_policy_binding']['consumer_purpose']=='DISPLAY'
                    assert not any(m['content'].startswith('Host semantic proposal contract:') for m in context['messages'])
                contract=context.get('semantic_plan_request',{})
                inventory=contract.get('trusted_inventory',{})
                requests.append({'session_id':h.session_id,'request_contract':contract.get('version'),
                    'prompt_bytes':context['prompt_bytes'],'messages_sha256':runner.value_sha(context['messages']),
                    'admitted_facts':len(inventory.get('evidence',[])),
                    'unparsed_inputs':len(inventory.get('unparsed_sha256',[]))})
            rows,_=runner.validate_rows(store.db,root,manifest,scope,preparation)
            assert not rows and store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0]==0
            calls.assert_not_called()
            result={'status':'BOUNDED_CONVERSATION_STATE_BINDING_READY' if binding['semantic_acceptance_mode']=='BOUNDED'
                    else 'TRUSTED_ACCEPTANCE_EXTERNAL44_BINDING_READY','at_utc':runner.now(),
                'kind':'ZERO_PROVIDER_CALL_FORMAL_PATH_PREFLIGHT','mock_revision':name,
                'mock_revision_path':runner.relative(root),'capture_mode':manifest['capture_mode'],
                'paid_revision_created':False,'source_freeze':binding['acceptance_source_freeze'],
                'acceptance_binding':binding,'session_checks':session_checks,'request_checks':requests,
                'revision_metadata':'PASS','source_identity':'MATCH','persistence_schema':'PASS',
                'consumer_binding':'ACKNOWLEDGED_DISPLAY_WITH_SEPARATE_STATE' if binding['semantic_acceptance_mode']=='BOUNDED'
                    else 'REQUIRED_ACCEPTED_ONLY','evaluator_contract':binding['evaluator_contract_version'],
                'provider_call_invocations':calls.call_count,'provider_call_rows':0,'remote_generation':0,
                'deepseek_requests':0,'openrouter_requests':0,'readiness':0,'automatic_paid_retries':0,
                'semantic_validation_performed':False,'captured':0,'reviewed':0}
        finally: store.close()
    if output is not None: runner.write_new(output,result)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--acceptance-config-file',type=Path,required=True)
    p.add_argument('--transport-policy-file',type=Path,required=True)
    p.add_argument('--network-route-policy-file',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=vars(p.parse_args())
    try:
        result=preflight(**args)
        print(json.dumps({k:result[k] for k in ('status','source_freeze','provider_call_invocations','paid_revision_created')}))
        return 0
    except Exception as exc:
        print(json.dumps({'status':'TRUSTED_ACCEPTANCE_EXTERNAL44_BINDING_NOT_READY',
            'failure_layer':getattr(exc,'failure_layer','ADMISSION'),'error_category':type(exc).__name__}))
        return 2

if __name__=='__main__': raise SystemExit(main())
