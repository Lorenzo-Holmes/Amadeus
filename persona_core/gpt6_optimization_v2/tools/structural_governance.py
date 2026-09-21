"""Narrow append-only authorization adapter for one structural candidate cycle."""
import json

AUTH_VERSION='APCORE_STRUCTURAL_TASK_AUTHORIZATION_1'
TASK='G6-07-STRUCTURAL-PRE-DISPLAY-CALIBRATION-AND-NEW-CANDIDATE-V1'


def authorization(root,payload,auth):
    import governance_v2 as g
    g.require(auth.get('schema_version')==AUTH_VERSION and auth.get('task')==payload.get('active_task')==TASK
        and auth.get('kind')=='POST_FAIL_PRODUCT_REPAIR_NEW_CANDIDATE'
        and auth.get('status')=='PROJECT_COMPLETION_SPEND_AUTHORIZED_AS_NEEDED'
        and auth.get('source')=='CURRENT_EXPLICIT_USER_REQUEST_20260921'
        and auth.get('candidate_id')==payload['draw_lineage']['candidate_id']
        and auth.get('max_candidates')==auth.get('max_fresh_revisions')==1
        and auth.get('max_smoke_requests')==50 and auth.get('max_formal_requests')==88
        and auth.get('max_total_provider_requests')==138
        and auth.get('max_draft_requests_per_product_turn')==auth.get('max_calibration_requests_per_product_turn')==1
        and auth.get('automatic_paid_retries')==auth.get('count_api_requests')==auth.get('readiness_requests')==auth.get('extra_probe_requests')==0
        and auth.get('fallback_allowed') is False and auth.get('replacement_draw') is False
        and auth.get('historical_draw_refunded') is False and auth.get('r18_r19_preserved') is True
        and auth.get('r18_r19_resume_replay_resend') is False and auth.get('g6_08_execution_authorized') is False,
        'STRUCTURAL_TASK_AUTHORIZATION_MISMATCH')
    return auth


def paid_state(root,payload):
    import governance_v2 as g
    auth=authorization(root,payload,g.pinned_json(root,payload['task_authorization']))
    g.require(payload.get('paid_cycle_closed') is False and payload.get('paid_validation_blockers')==[], 'STRUCTURAL_PAID_CYCLE_CLOSED')
    phase=payload.get('paid_phase')
    g.require(phase in ('SMOKE','FORMAL'),'STRUCTURAL_PAID_PHASE_REQUIRED')
    p=g.pinned_json(root,payload['preflight'])
    expected='ZERO_PROVIDER_SMOKE_PREFLIGHT' if phase=='SMOKE' else 'ZERO_PROVIDER_FORMAL_BINDING_PREFLIGHT'
    g.require(p.get('status')=='READY' and p.get('kind')==expected
        and p.get('candidate_id')==auth['candidate_id'] and p.get('source_manifest')==payload['source_freeze']
        and p.get('configuration')==payload['configuration']
        and (p.get('scope_sha256')==payload.get('active_paid_scope_sha256') if phase=='SMOKE' else
             p.get('scope_contract_sha256')==payload.get('active_paid_scope_contract_sha256'))
        and p.get('pipeline_max_stages')==2 and p.get('stage_request_limits')=={'draft':1,'calibration':1}
        and all(p.get(k)==0 for k in ('provider_call_invocations','provider_call_rows','calibration_call_invocations',
            'calibration_call_rows','generation_request_invocations','readiness_requests','token_count_request_invocations',
            'automatic_paid_retries','active_paid_driver_count')),'STRUCTURAL_PREFLIGHT_NOT_READY')
    tests=g.pinned_json(root,payload['test_receipt']);source=g.pinned_json(root,payload['source_freeze'])
    g.require(tests.get('status')=='PASS' and tests.get('source_files')==source['files']
        and tests.get('results') and all(r.get('exit_code')==0 and r.get('tests',0)>0 and r.get('skipped')==0 for r in tests['results'])
        and g.verify_manifest(root,payload['source_freeze'])['status']=='MATCH','STRUCTURAL_TESTED_SOURCE_MISMATCH')
    full_path=g.pinned_json(root,payload['full_path_receipt'])
    g.require(full_path.get('status')=='PASS' and full_path.get('source_files')==source['files'], 'STRUCTURAL_FULL_PATH_REQUIRED')
    smoke=payload.get('smoke_attempt',{})
    g.require(smoke.get('allocations')==1 and smoke.get('max_requests')==50
        and smoke.get('source_manifest')==payload['source_freeze'] and smoke.get('configuration')==payload['configuration'],
        'STRUCTURAL_SINGLE_SMOKE_REQUIRED')
    if phase=='SMOKE':
        g.require(payload.get('status') in {'READY_FOR_STRUCTURAL_SMOKE','STRUCTURAL_SMOKE_RUNNING'}
            and p.get('max_requests')==50 and smoke.get('scope_sha256')==p['scope_sha256']
            and payload.get('formal_attempt',{}).get('allocations')==0
            and payload.get('formal_attempt',{}).get('revision') is None,'STRUCTURAL_SMOKE_ALLOCATION')
        prereg=g.pinned_json(root,payload['smoke_preregistration'])
        g.verify_reference(root,prereg['inputs'])
    else:
        receipt=g.pinned_json(root,payload['smoke_receipt'])
        g.require(receipt.get('status')=='PASS' and receipt.get('end_to_end_reviewed')==20
            and receipt.get('authored_probes_reviewed')==10 and receipt.get('unclear')==receipt.get('failed')==0
            and receipt.get('source_manifest')==payload['source_freeze'] and receipt.get('configuration')==payload['configuration']
            and receipt.get('independent_from_product_calibration_step') is True,
            'STRUCTURAL_SMOKE_PASS_REQUIRED')
        attempt=payload.get('formal_attempt',{})
        g.require(payload.get('status') in {'READY_FOR_SINGLE_NEW_CANDIDATE_ATTEMPT','VALIDATING_NEW_CANDIDATE'}
            and p.get('denominators')=={'turns':44,'criteria':176,'gate_a':176,'gate_b':132}
            and p.get('max_requests')==88 and attempt.get('allocations')==1
            and isinstance(attempt.get('revision'),str) and bool(attempt['revision']), 'STRUCTURAL_FORMAL_ALLOCATION')


def implementation(root,config,freeze,parent):
    import governance_v2 as g
    structural=config.get('structural_calibration',{})
    g.require(structural.get('mechanism_version')=='APCORE_FIXED_TWO_STAGE_PIPELINE_1'
              and structural.get('max_stages')==2,'STRUCTURAL_MECHANISM_BINDING_REQUIRED')
    refs=structural.get('implementation',[])
    integration=structural.get('integration',[])
    g.require(bool(refs) and bool(integration),'STRUCTURAL_IMPLEMENTATION_REQUIRED')
    for r in refs+integration:
        g.verify_reference(root,r)
        g.require(freeze['files'].get(r['path'])==r['sha256'],'STRUCTURAL_SOURCE_MEMBERSHIP')
    g.require(any(parent['files'].get(r['path']) is None for r in refs)
        and any(parent['files'].get(r['path']) not in (None,r['sha256']) for r in integration),
        'STRUCTURAL_REAL_INTEGRATION_CHANGE_REQUIRED')


def preserve_cycle(root,old,payload):
    import governance_v2 as g
    if old.get('paid_cycle_closed') is True:
        g.require(payload.get('paid_cycle_closed') is True and payload.get('paid_requests_allowed') is False,
                  'STRUCTURAL_CLOSED_CYCLE_CANNOT_REOPEN')
    for k in ('smoke_attempt','smoke_preregistration'):
        if k in old:g.require(payload.get(k)==old[k],'STRUCTURAL_SMOKE_REPLACEMENT_FORBIDDEN')
    prior=old.get('formal_attempt',{})
    new=payload.get('formal_attempt',{})
    if prior.get('allocations')==0:
        g.require(new.get('allocations') in (0,1) and new.get('kind')==prior.get('kind'),'STRUCTURAL_ATTEMPT_LIMIT')
        if new.get('allocations')==1:
            g.require(payload.get('paid_phase')=='FORMAL' and payload.get('paid_requests_allowed') is True,
                      'STRUCTURAL_ALLOCATION_REQUIRES_FORMAL_ACTIVATION')
            paid_state(root,payload)
        else:g.require(new.get('revision') is None,'STRUCTURAL_PREMATURE_REVISION')
    else:
        g.require(new==prior,'STRUCTURAL_FORMAL_REPLACEMENT_FORBIDDEN')
