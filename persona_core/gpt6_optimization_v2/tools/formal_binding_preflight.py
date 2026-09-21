"""Zero-provider-call preflight of the real formal external44 construction path."""
from pathlib import Path
import argparse
import json
import socket
import sys
import uuid
import copy
from datetime import datetime,timezone
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import evaluation_runner as runner


def active_paid_driver_count(evidence=None):
    """Exclude only sealed authored runs; unknown or live paid runs stay blocking.

    Historical offline fixtures retain ACTIVE_RUN markers whose PIDs can later
    belong to unrelated processes. PID liveness is not evidence of a paid run.
    Never remove those markers or weaken the check for target-provider runs.
    """
    default_evidence=evidence is None or evidence==runner.EVIDENCE
    evidence = runner.EVIDENCE if evidence is None else evidence
    active = 0
    for marker in evidence.glob('G6_V2_*/ACTIVE_RUN.json'):
        try:
            if not runner.process_alive(runner.read(marker).get('pid')):
                continue
            manifest = marker.parent / 'MANIFEST.json'
            seal = marker.parent / 'MANIFEST_SEAL.json'
            if (runner.sha(manifest) == runner.read(seal)['sha256']
                    and runner.read(manifest).get('capture_mode') == runner.OFFLINE):
                continue
        except (OSError, ValueError, KeyError, TypeError):
            pass  # Missing or unverified identity cannot justify exclusion.
        active += 1
    if default_evidence:
        marker=runner.ROOT/'work/structural_calibration_20260921_01/ACTIVE_PAID_DRIVER.json'
        if marker.exists():
            try:
                if runner.process_alive(runner.read(marker).get('pid')):active+=1
            except (OSError,ValueError,KeyError,TypeError):active+=1
    return active


def deepseek_successor_preflight(acceptance_config_file,transport_policy_file,network_route_policy_file,*,
                                authorization_file,pricing_file,output=None):
    """Construct all frozen roles and actual initial contexts with I/O denied."""
    provider,transcript,operations,*_=runner.runtime_modules()
    import provider_deepseek_formal as ds
    import provider_transport as pt
    from semantic_binding import require_session, strict_selected
    name='deepseek_preflight_'+uuid.uuid4().hex
    base=runner.ROOT/'work/deepseek_successor/preflight';base.mkdir(parents=True,exist_ok=True)
    root=base/name
    with patch.object(socket.socket,'connect',side_effect=AssertionError('PREFLIGHT_NETWORK_FORBIDDEN')), \
         patch.object(socket.socket,'connect_ex',side_effect=AssertionError('PREFLIGHT_NETWORK_FORBIDDEN')), \
         patch.object(ds.DeepSeekFormalAdapter,'credential',side_effect=AssertionError('PREFLIGHT_CREDENTIAL_FORBIDDEN')) as keys, \
         patch.object(pt,'worker_exchange',side_effect=AssertionError('PREFLIGHT_GENERATION_FORBIDDEN')) as transport, \
         patch.object(provider.ProviderJournal,'call',side_effect=AssertionError('PREFLIGHT_CALL_FORBIDDEN')) as calls:
        runner.prepare(name,suite='external44',offline=True,formal_validation=True,offline_root=root,
            acceptance_config_file=acceptance_config_file,primary=ds.MODEL,secondary=ds.MODEL,
            max_output_tokens=32768,api_protocol='responses',transport_policy_file=transport_policy_file,
            network_route_policy_file=network_route_policy_file,successor_authorization_file=authorization_file,pricing_record=pricing_file)
        manifest,scope,preparation=runner.verify_sources(root)
        binding=scope['semantic_acceptance_binding'];checks=[];contexts=[];seen=set()
        store=transcript.TranscriptStore(root/'runtime')
        try:
            for slot in scope['slots']:
                h=store.resume(scope['principal_id'],preparation['sessions'][slot['case_id']]['session_id'])
                chat=operations.open_chat(store,h,scope);require_session(store.db,h.session_id,binding)
                assert chat.acceptance_mode=='BOUNDED' and not strict_selected(binding)
                neutral=[{'role':'system','content':'Neutral offline serializer contract.'},{'role':'user','content':slot['user_text']}]
                payload=runner.canonical(ds.DeepSeekFormalAdapter().serialize(scope,slot['model'],neutral))
                guard=ds.input_guard_receipt(scope,payload,slot['id'])
                checks.append({'slot_id':slot['id'],'model':slot['model'],'model_role':slot['model_role'],
                    'host_action_before':slot['host_action_before'],'binding':'MATCH','serializer_and_input_guard':'PASS',
                    'guard_receipt_sha256':runner.value_sha(guard),'neutral_serializer_fixture_not_future_context':True})
                if slot['case_id'] in seen:continue
                seen.add(slot['case_id']);turn=store.begin_turn(h,slot['user_text'],'OFFLINE_BINDING_PREVIEW')
                context=chat.build_request_context(turn['turn_id'])
                assert context['messages'][-1]=={'role':'user','content':slot['user_text']}
                assert 'semantic_plan_request' not in context and context['display_policy_binding']['consumer_purpose']=='DISPLAY'
                payload=runner.canonical(ds.DeepSeekFormalAdapter().serialize(scope,slot['model'],context['messages']))
                guard=ds.input_guard_receipt(scope,payload,slot['id'])
                contexts.append({'case_id':slot['case_id'],'request_sha256':guard['request_sha256'],
                    'prompt_bytes':guard['canonical_message_bytes'],'display_state_strict_binding':'MATCH'})
            rows,_=runner.validate_rows(store.db,root,manifest,scope,preparation)
            assert not rows and store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0]==0
            calls.assert_not_called();transport.assert_not_called();keys.assert_not_called()
            active=active_paid_driver_count()
            assert active==0
            result={'status':'READY','kind':'ZERO_PROVIDER_FORMAL_BINDING_PREFLIGHT','formal_preflight_executed':True,
                'candidate_id':scope['candidate_id'],'scope_version':ds.SCOPE_VERSION,'provider_identity':binding['provider_config_identity'],
                'source_freeze':binding['acceptance_source_freeze'],'offline_work_path':runner.relative(root),
                'provider_call_invocations':0,'provider_call_rows':0,'token_count_request_invocations':0,
                'generation_request_invocations':0,'readiness_requests':0,'credential_reads':0,
                'input_guard_structural_binding':'PASS','paid_revision_created':False,'slot_checks':checks,
                'initial_context_checks':contexts,'future_contexts':'BUILT_EXACTLY_AND_GUARDED_AT_EACH_LIVE_SLOT',
                'denominators':{'turns':44,'criteria':176,'gate_a':176,'gate_b':132},
                'consumer_display_state_strict_schema':'MATCH','stop_rules':scope['stop_rules'],
                'automatic_paid_retries':0,'active_paid_driver_count':active,'at_utc':runner.now()}
        finally:store.close()
    if output is not None:runner.write_new(output,result)
    return result


def count_structure_checks(scope,payload,slot_id):
    """Memory-only test double. Never persist it as a runtime count receipt."""
    import provider_openai as oa
    import provider_transport as pt
    receipt={**oa.count_binding(scope,payload,slot_id),'version':oa.COUNT_RECEIPT_VERSION,
        'input_tokens':28672,'timestamp':datetime.now(timezone.utc).isoformat(),
        'origin':'OPENAI_OFFICIAL_COUNT_RESPONSE','receipt_id':'PREFLIGHT_MEMORY_ONLY_'+uuid.uuid4().hex}
    tests=[]
    with patch.dict(oa._issued_counts,{receipt['receipt_id']:runner.canonical(receipt)},clear=True), \
         patch.object(pt,'worker_exchange',return_value='OFFLINE_GENERATION_PATH') as worker:
        oa.verify_count_receipt(scope,payload,receipt,slot_id)
        tests.append('same_payload_model_input_source_scope_slot_limit')
        for key,value in [('input_tokens',28673),('input_tokens',-1),('model',oa.MODELS[1] if receipt['model']==oa.MODELS[0] else oa.MODELS[0]),
                          ('slot_id','different'),('generation_payload_sha256','0'*64),('messages_sha256','0'*64),
                          ('source_binding',{}),('scope_sha256','0'*64),('timestamp','2000-01-01T00:00:00+00:00')]:
            bad=copy.deepcopy(receipt);bad[key]=value
            try: oa.verify_count_receipt(scope,payload,bad,slot_id)
            except ValueError: tests.append('reject_'+key)
            else: raise AssertionError('PREFLIGHT_COUNT_MUTATION_ACCEPTED')
        try: oa.OpenAIAdapter().exchange(scope,payload,'OFFLINE',lambda e:None,[])
        except ValueError: tests.append('missing_count_blocks_generation')
        else: raise AssertionError('PREFLIGHT_GENERATION_WITHOUT_COUNT')
        worker.assert_not_called()
        assert oa.OpenAIAdapter().exchange(scope,payload,'OFFLINE',lambda e:None,[],count_receipt=receipt,slot_id=slot_id)=='OFFLINE_GENERATION_PATH'
        try: oa.OpenAIAdapter().exchange(scope,payload,'OFFLINE',lambda e:None,[],count_receipt=receipt,slot_id=slot_id)
        except ValueError: tests.append('count_receipt_single_use')
        else: raise AssertionError('PREFLIGHT_COUNT_REUSE')
        assert worker.call_count==1
    return {'status':'PASS','checks':tests,'evidence_kind':'AUTHORED_MEMORY_ONLY_NO_RUNTIME_RECEIPT',
        'mock_generation_path_invocations':1,'token_count_request_invocations':0,'generation_request_invocations':0}


def successor_preflight(acceptance_config_file,transport_policy_file,network_route_policy_file,*,
                        authorization_file,pricing_file,input_proof_file=None,output=None,diagnostics_only=False):
    """Construct the formal path under work, with no call/key/network access.

    Mock receipts prove wiring only. No count, generation or credential calls.
    """
    provider,transcript,operations,*_=runner.runtime_modules()
    import provider_openai as oa
    from semantic_binding import require_session
    name='openai_preflight_'+uuid.uuid4().hex
    base=runner.ROOT/'work/openai_formal_binding/preflight'; base.mkdir(parents=True,exist_ok=True)
    root=base/name
    with patch.object(socket.socket,'connect',side_effect=AssertionError('PREFLIGHT_NETWORK_FORBIDDEN')), \
         patch.object(socket.socket,'connect_ex',side_effect=AssertionError('PREFLIGHT_NETWORK_FORBIDDEN')), \
         patch.object(oa.OpenAIAdapter,'credential',side_effect=AssertionError('PREFLIGHT_CREDENTIAL_FORBIDDEN')), \
         patch.object(oa,'count_input_tokens',side_effect=AssertionError('PREFLIGHT_COUNT_FORBIDDEN')) as count_calls, \
         patch.object(oa,'http_exchange',side_effect=AssertionError('PREFLIGHT_GENERATION_FORBIDDEN')) as generation_calls, \
         patch.object(provider.ProviderJournal,'call',side_effect=AssertionError('PREFLIGHT_CALL_FORBIDDEN')) as calls:
        runner.prepare(name,suite='external44',offline=True,formal_validation=True,offline_root=root,
            acceptance_config_file=acceptance_config_file,primary=oa.MODELS[0],secondary=oa.MODELS[1],
            max_output_tokens=32768,api_protocol='responses',transport_policy_file=transport_policy_file,
            network_route_policy_file=network_route_policy_file,successor_authorization_file=authorization_file,
            pricing_record=pricing_file,input_proof_file=input_proof_file)
        manifest,scope,preparation=runner.verify_sources(root)
        binding=scope['semantic_acceptance_binding']; requests=[]; metadata=[]; seen=set()
        store=transcript.TranscriptStore(root/'runtime')
        try:
            for slot in scope['slots']:
                entry=preparation['sessions'][slot['case_id']]
                h=store.resume(scope['principal_id'],entry['session_id']); chat=operations.open_chat(store,h,scope)
                require_session(store.db,h.session_id,binding)
                metadata.append({'slot_id':slot['id'],'model':slot['model'],'model_role':slot['model_role'],
                    'host_action_before':slot['host_action_before'],'binding':'MATCH'})
                if slot['case_id'] in seen: continue
                seen.add(slot['case_id'])
                turn=store.begin_turn(h,slot['user_text'],'OFFLINE_BINDING_PREVIEW')
                context=chat.build_request_context(turn['turn_id'])
                assert context['messages'][-1]=={'role':'user','content':slot['user_text']}
                assert 'semantic_plan_request' not in context and context['display_policy_binding']['consumer_purpose']=='DISPLAY'
                payload=runner.canonical(oa.OpenAIAdapter().serialize(scope,slot['model'],context['messages']))
                structural=count_structure_checks(scope,payload,slot['id'])
                requests.append({'case_id':slot['case_id'],'request_sha256':runner.hashlib.sha256(payload).hexdigest(),
                    'messages_sha256':runner.value_sha(context['messages']),'prompt_bytes':context['prompt_bytes'],
                    'count_guard_structure':structural,'display_and_state_binding':'MATCH'})
            rows,_=runner.validate_rows(store.db,root,manifest,scope,preparation)
            assert not rows and store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0]==0
            calls.assert_not_called()
            count_calls.assert_not_called();generation_calls.assert_not_called()
            result={'status':'NOT_READY' if diagnostics_only else 'READY',
                'blocker':'DIAGNOSTICS_ONLY' if diagnostics_only else None,
                'kind':'OFFLINE_BINDING_DIAGNOSTICS' if diagnostics_only else 'ZERO_PROVIDER_FORMAL_BINDING_PREFLIGHT',
                'formal_preflight_executed':not diagnostics_only,'at_utc':runner.now(),
                'provider_identity':binding['provider_config_identity'],'source_freeze':binding['acceptance_source_freeze'],
                'offline_work_path':runner.relative(root),'provider_call_invocations':0,'provider_call_rows':0,
                'token_count_request_invocations':0,'generation_request_invocations':0,
                'count_guard_structural_binding':'PASS','scope_version':scope['schema_version'],
                'input_policy':oa.INPUT_POLICY,'count_endpoint':oa.COUNT_ENDPOINT,
                'paid_revision_created':False,'slot_checks':metadata,'initial_context_checks':requests,
                'denominators':{'turns':44,'criteria':176,'gate_a':176,'gate_b':132},
                'consumer_display_state_strict_schema':'MATCH','automatic_paid_retries':0}
        finally: store.close()
    if output is not None: runner.write_new(output,result)
    return result

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
