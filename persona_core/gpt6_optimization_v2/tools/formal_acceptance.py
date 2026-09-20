"""Formal revision binding and accepted-product evaluation, without generation."""
import json
from semantic_types import VERSION
from semantic_binding import (BINDING_VERSION,RUNTIME_VERSION,ADAPTER_VERSION,REQUEST_VERSION,
    PERSISTENCE_VERSION,EVALUATOR_VERSION,validate_binding,provider_identity,reference,require,
    require_session,consumer_text)

def build_binding(scope,suite_data,config_path,*,rubric_path,offline=False):
    import evaluation_runner as runner
    from accepted_output import runtime_identity,CONSUMERS
    require(config_path is not None,'ADMISSION','FORMAL_ACCEPTANCE_CONFIG_REQUIRED')
    config=runner.read(config_path)
    keys={'semantic_acceptance_mode','acceptance_policy_version','acceptance_source_freeze',
          'acceptance_source_manifest','trusted_semantic_runtime_version','semantic_source'}
    require(type(config) is dict and set(config)==keys,'ADMISSION','FORMAL_ACCEPTANCE_CONFIG_FIELDS')
    def ref(path): return {'path':runner.relative(path),'sha256':runner.sha(path)}
    binding=dict(config,schema_version=BINDING_VERSION,runtime_source_hashes=runtime_identity(),
        admission_adapter_version=ADAPTER_VERSION,provider_config_identity=provider_identity(scope),
        dataset_identity=ref(suite_data['cases_path']),rubric_identity=ref(rubric_path),
        consumers=sorted(CONSUMERS),request_contract_version=REQUEST_VERSION,
        persistence_version=PERSISTENCE_VERSION,evaluator_contract_version=EVALUATOR_VERSION)
    validate_binding(binding,scope)
    freeze=runner.read(reference(binding['acceptance_source_manifest']))
    require(freeze.get('status')=='FROZEN_FOR_FRESH_VALIDATION' or
            (offline and freeze.get('status')=='OFFLINE_TEST_ONLY'),'ADMISSION','FORMAL_FROZEN_SOURCE_REQUIRED')
    frozen=freeze['files']
    current=runner.source_bindings()
    require(all(frozen.get(p)==h for p,h in current.items()),'ADMISSION','FORMAL_SOURCE_MEMBERSHIP_CHANGED')
    # A missing adapter/catalog fails before allocating the revision.
    from trusted_admission_adapter import TrustedAdmissionAdapter
    from types import SimpleNamespace
    TrustedAdmissionAdapter(binding)(SimpleNamespace(session_id='preflight',entity_id='preflight'),
                                    {'turn_id':'preflight','user_text':''},{})
    return binding

def verify_metadata(manifest,scope,preparation):
    binding=validate_binding(scope.get('semantic_acceptance_binding'),scope)
    require(manifest.get('formal_validation') is True and manifest.get('semantic_acceptance_binding')==binding,
            'EVALUATION','FORMAL_MANIFEST_BINDING_MISSING')
    require(preparation.get('semantic_acceptance_binding')==binding,'PERSISTENCE','PREPARATION_BINDING_MISSING')
    for key in ('semantic_acceptance_mode','acceptance_policy_version','acceptance_source_freeze',
                'trusted_semantic_runtime_version','provider_config_identity','dataset_identity','rubric_identity'):
        require(manifest.get(key)==binding[key],'EVALUATION','REVISION_ACCEPTANCE_IDENTITY_CHANGED')
    return binding

def evaluator_provenance(row,binding):
    record=row.get('accepted_output')
    require(row.get('output_provenance')=='HOST_ACCEPTED_OUTPUT' and record is not None,
            'EVALUATION','ACCEPTED_EVALUATOR_BINDING_REQUIRED')
    require(record.get('acceptance_identity')==binding,'EVALUATION','EVALUATOR_ACCEPTANCE_IDENTITY_CHANGED')
    consumer_text(record,row['assistant_text'])
    audit=record['acceptance_audit']
    return {'contract_version':EVALUATOR_VERSION,'product_semantic_target':'accepted_assistant_text',
        'raw_text':row['raw_assistant_text'],'raw_visible_text':record['raw_visible_text'],
        'accepted_text':row['accepted_assistant_text'],'transformation':record['transformation'],
        'raw_provider_violation':audit['raw_provider_violation'],'guard_action':record['acceptance_disposition'],
        'guard_containment':audit['guard_containment'],'guard_escape':False,
        'consumer_binding_status':'ACCEPTED_ONLY_VERIFIED','acceptance_audit':audit}
