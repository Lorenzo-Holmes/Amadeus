"""Construct both fixed stages without reading credentials or submitting calls."""
from contextlib import ExitStack
from pathlib import Path
import socket
import uuid
from unittest.mock import patch
import evaluation_runner as er


def smoke_scope(acceptance, pricing, authorization, *, revision='structural_smoke_20260921_01'):
    er.runtime_modules()
    import provider_structural as ps
    import provider_deepseek_formal as ds
    cfg=er.read(er.ROOT/ps.DIRECTORY/'CONFIGURATION_PREREGISTRATION.json')
    design=er.read(ds.verify_reference(cfg['smoke_input_design']))
    scope=ps.build_scope(revision,design,er.checked_pricing(pricing,False,(ds.MODEL,ds.MODEL)),
        ds.configuration()['transport_policy'],ds.route(),authorization_file=authorization,
        pricing_file=pricing,acceptance_config_file=acceptance,phase='SMOKE')
    scope['semantic_acceptance_binding']=er.build_acceptance_binding(scope,
        {'cases_path':ds.verify_reference(cfg['dataset_identity'])},acceptance,
        rubric_path=ds.verify_reference(cfg['rubric_identity']))
    ps.check_scope(scope,ps.StructuralAdapter())
    return scope


def prepare_smoke(root,scope,*,runtime=None):
    provider,transcript,operations,*_=er.runtime_modules()
    root=er.offline_destination(root)
    er.require(not root.exists(),'SMOKE_SCOPE_ALREADY_PREPARED_NO_REPLACEMENT')
    root.mkdir(parents=True)
    er.write_new(root/'SCOPE.json',scope)
    runtime=runtime or root/'runtime'
    transcript.safe_root(runtime)
    er.write_new(root/'RUNTIME_LOCATION.json',{'path':er.relative(runtime)})
    transcript.create_sandbox(runtime)
    store=transcript.TranscriptStore(runtime)
    try:
        provider.ProviderJournal(store).register_batch(scope)
        sessions={}
        for slot in scope['slots']:
            h=store.open_session(scope['principal_id'],slot['entity_label'],'PRODUCT_RUNTIME')
            operations.open_chat(store,h,scope)
            sessions[slot['id']]=h.session_id
        for probe in scope.get('authored_probes',[]):
            h=store.open_session(scope['principal_id'],'AUTHORED_PROBE_'+probe['id'],'PRODUCT_RUNTIME')
            operations.open_chat(store,h,scope)
            sessions[probe['id']]=h.session_id
        er.write_new(root/'SESSIONS.json',sessions)
        er.require(store.db.execute('SELECT count(*) FROM turns').fetchone()[0]==0,'SMOKE_PREPARE_CREATED_TURN')
        return sessions
    finally:store.close()


def probe_input(store,handle,scope,probe):
    from operations import open_chat
    import claim_calibration as cc
    import provider_contract as pc
    turn=store.begin_turn(handle,probe['input'],'AUTHORED_DRAFT_PROBE:'+probe['id'])
    context=open_chat(store,handle,scope).build_request_context(turn['turn_id'])
    # A probe has no first-stage Provider call, no display, and no state admission.
    return cc.input_record(context,probe['authored_draft'],turn_id=turn['turn_id'],
        parent_call_id='AUTHORED_PROBE:'+probe['id'],parent_request_sha256=pc.digest(probe),
        pipeline_identity=scope['pipeline_identity'])


def inspect_prepared(root,scope,sessions,*,formal=False):
    provider,transcript,operations,*_=er.runtime_modules()
    import provider_structural as ps
    import provider_contract as pc
    import claim_calibration as cc
    import calibration_journal as cj
    from semantic_binding import require_session,strict_selected
    from formal_binding_preflight import active_paid_driver_count
    ps.check_scope(scope,ps.StructuralAdapter())
    binding=scope['semantic_acceptance_binding'];checks=[];initial=[];probes=[];seen=set()
    runtime=er.ROOT/er.read(root/'RUNTIME_LOCATION.json')['path'] if (root/'RUNTIME_LOCATION.json').exists() else root/'runtime'
    store=transcript.TranscriptStore(runtime)
    try:
        cj.install(store.db)
        for slot in scope['slots']:
            sid=sessions[slot['case_id']]['session_id'] if formal else sessions[slot['id']]
            h=store.resume(scope['principal_id'],sid);chat=operations.open_chat(store,h,scope)
            require_session(store.db,h.session_id,binding)
            er.require(chat.acceptance_mode=='BOUNDED' and not strict_selected(binding),'PREFLIGHT_POLICY_CHANGED')
            neutral=[{'role':'system','content':'Offline serialization contract only.'},
                     {'role':'user','content':slot['user_text']}]
            payload=pc.canonical(ps.StructuralAdapter().serialize(scope,slot['model'],neutral))
            guard=ps.input_guard_receipt(scope,payload,slot['id'])
            checks.append({'slot_id':slot['id'],'model':slot['model'],'model_role':slot['model_role'],
                           'draft_guard_sha256':pc.digest(guard),'neutral_serializer_fixture':True})
            if sid in seen:continue
            seen.add(sid)
            turn=store.begin_turn(h,slot['user_text'],'ZERO_PROVIDER_PREVIEW')
            context=chat.build_request_context(turn['turn_id'])
            er.require(context['messages'][-1]=={'role':'user','content':slot['user_text']},'PREFLIGHT_CONTEXT')
            draft=pc.canonical(ps.StructuralAdapter().serialize(scope,slot['model'],context['messages']))
            dg=ps.input_guard_receipt(scope,draft,slot['id'])
            supplied,messages=cc.input_record(context,'Offline stage binding placeholder; no model output exists.',
                turn_id=turn['turn_id'],parent_call_id='ZERO_PROVIDER_PARENT',
                parent_request_sha256=dg['request_sha256'],pipeline_identity=scope['pipeline_identity'])
            stage=dict(scope,request_stage='CALIBRATION')
            payload=pc.canonical(ps.StructuralAdapter().serialize(stage,slot['model'],messages))
            cg=ps.input_guard_receipt(stage,payload,slot['id'])
            initial.append({'slot_id':slot['id'],'draft_guard':dg,'calibration_guard':cg,
                            'calibration_uses_authored_placeholder':True,'no_future_context_claim':True})
        for probe in scope.get('authored_probes',[]):
            h=store.resume(scope['principal_id'],sessions[probe['id']])
            supplied,messages=probe_input(store,h,scope,probe)
            stage=dict(scope,request_stage='CALIBRATION')
            payload=pc.canonical(ps.StructuralAdapter().serialize(stage,scope['primary_model'],messages))
            probes.append(ps.input_guard_receipt(stage,payload,probe['id']))
        drafts=store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0]
        calibrations=store.db.execute('SELECT count(*) FROM calibration_calls_v2').fetchone()[0]
        er.require(drafts==calibrations==0,'PREFLIGHT_JOURNAL_SUBMISSION')
        active=active_paid_driver_count();er.require(active==0,'ACTIVE_PAID_DRIVER_PRESENT')
        return {'status':'READY','kind':'ZERO_PROVIDER_FORMAL_BINDING_PREFLIGHT' if formal else 'ZERO_PROVIDER_SMOKE_PREFLIGHT',
            'formal_preflight_executed':formal,'candidate_id':scope['candidate_id'],
            'scope_version':scope['schema_version'],'scope_sha256':pc.digest(scope),
            'scope_contract_sha256':ps.scope_contract_identity(scope),'pipeline_identity':scope['pipeline_identity'],
            'source_manifest':scope['identity_references']['source_manifest'],
            'configuration':scope['identity_references']['configuration'],
            'provider_identity':binding['provider_config_identity'],'pipeline_max_stages':2,
            'stage_request_limits':{'draft':1,'calibration':1},'max_requests':scope['request_limits']['total'],
            'max_reserved_micro_cny':scope['reserved_upper_micro_cny'],'input_guard_structural_binding':'PASS',
            'consumer_display_state_strict_schema':'MATCH','raw_calibrated_display_chain':'VERSIONED_AND_SOURCE_BOUND',
            'provider_call_invocations':0,'calibration_call_invocations':0,'provider_call_rows':drafts,
            'calibration_call_rows':calibrations,'generation_request_invocations':0,'readiness_requests':0,
            'token_count_request_invocations':0,'credential_reads':0,'automatic_paid_retries':0,
            'active_paid_driver_count':active,'paid_revision_created':False,'slot_checks':checks,
            'initial_context_checks':initial,'authored_probe_checks':probes,
            'future_contexts':'BUILT_EXACTLY_AND_GUARDED_AT_EACH_LIVE_STAGE_NO_TRUNCATION',
            'denominators':{'turns':44,'criteria':176,'gate_a':176,'gate_b':132} if formal else None,
            'review_before_next_request':'REQUIRED','stop_rules':scope['stop_rules'],
            'offline_work_path':er.relative(root),'at_utc':er.now()}
    finally:store.close()


def preflight(acceptance,pricing,authorization,*,formal=False,output=None):
    provider,_,_,*_=er.runtime_modules()
    import provider_structural as ps
    import provider_deepseek_formal as ds
    import provider_transport as pt
    import calibration_journal as cj
    root=er.ROOT/'work/deepseek_successor/structural_preflight'/uuid.uuid4().hex
    root.parent.mkdir(parents=True,exist_ok=True)
    with ExitStack() as stack:
        spies=[]
        for target,name in [(socket.socket,'connect'),(socket.socket,'connect_ex'),
            (ds.DeepSeekFormalAdapter,'credential'),(provider,'existing_credential'),
            (pt,'worker_exchange'),(provider.ProviderJournal,'call'),(cj,'run_input')]:
            spies.append(stack.enter_context(patch.object(target,name,side_effect=AssertionError('ZERO_PROVIDER_PREFLIGHT_FORBIDDEN_IO'))))
        if formal:
            base=er.GOAL/'deepseek_successor_20260921_01'
            er.prepare('structural_preflight_'+root.name,suite='external44',offline=True,formal_validation=True,offline_root=root,
                acceptance_config_file=acceptance,pricing_record=pricing,successor_authorization_file=authorization,
                primary=ds.MODEL,secondary=ds.MODEL,max_output_tokens=32768,api_protocol='responses',
                transport_policy_file=base/'TRANSPORT_POLICY.json',network_route_policy_file=base/'NETWORK_ROUTE_POLICY.json')
            manifest,scope,preparation=er.verify_sources(root);sessions=preparation['sessions']
        else:
            scope=smoke_scope(acceptance,pricing,authorization)
            sessions=prepare_smoke(root,scope)
        result=inspect_prepared(root,scope,sessions,formal=formal)
        for spy in spies:spy.assert_not_called()
    if output is not None:er.write_new(output,result)
    return result,scope
