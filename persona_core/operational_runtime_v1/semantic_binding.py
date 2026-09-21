"""Explicit host-owned validation identity. No benchmark or provider inference."""
from contextlib import contextmanager
import json
import hashlib
from pathlib import Path
from semantic_types import VERSION, canonical, digest

BINDING_VERSION = 'FORMAL_SEMANTIC_BINDING_1'
RUNTIME_VERSION = 'TRUSTED_SEMANTIC_RUNTIME_1'
ADAPTER_VERSION = 'FROZEN_TYPED_ADMISSION_1'
REQUEST_VERSION = 'PROPOSED_SEMANTIC_PLAN_REQUEST_1'
PERSISTENCE_VERSION = 'RAW_ACCEPTED_IDENTITY_1'
EVALUATOR_VERSION = 'ACCEPTED_PRODUCT_WITH_RAW_PROVENANCE_1'
BOUNDED_BINDING_VERSION = 'FORMAL_BOUNDED_BINDING_1'
CALIBRATED_BINDING_VERSION = 'FORMAL_CALIBRATED_BINDING_1'
CALIBRATED_PERSISTENCE_VERSION = 'RAW_CALIBRATED_DISPLAY_IDENTITY_3'
DISPLAY_POLICY = 'BOUNDED_CONVERSATION_1'
BOUNDED_PERSISTENCE_VERSION = 'RAW_DISPLAY_ACCEPTED_IDENTITY_2'
DUAL_GATE_VERSION = 'DUAL_GATE_DISPLAY_STATE_1'
ARCHITECTURE_CONTRACT = 'APCORE_BOUNDED_ARCHITECTURE_CONTRACT_1'
STATE_POLICY = 'admission-46.2'
BOUNDED_FIELDS = {'architecture_contract','contract_manifest','criterion_routing',
    'consumer_authority_matrix','display_policy_version','state_admission_policy_version',
    'strict_semantic_policy_version','consumer_purpose','task_role'}
LAYERS = {'PROVIDER','TRANSPORT','ADMISSION','VALIDATOR','CERTIFICATE','RENDERER',
          'PERSISTENCE','CONSUMER','EVALUATION'}
ROOT = Path(__file__).resolve().parents[2]

class BindingError(ValueError):
    def __init__(self, layer, code):
        self.failure_layer = layer
        self.code = code
        super().__init__(code)

def require(ok, layer, code):
    if not ok:
        raise BindingError(layer, code)

@contextmanager
def layer(name):
    try:
        yield
    except BindingError:
        raise
    except Exception as exc:
        raise BindingError(name, 'FORMAL_'+name+'_FAILED') from exc

def reference(value):
    require(type(value) is dict and set(value)=={'path','sha256'}, 'ADMISSION', 'SOURCE_REFERENCE_REQUIRED')
    path=(ROOT/value['path']).resolve()
    require(path.is_relative_to(ROOT) and path.is_file(), 'ADMISSION', 'SOURCE_OUTSIDE_WORKSPACE_OR_MISSING')
    require(hashlib.sha256(path.read_bytes()).hexdigest()==value['sha256'], 'ADMISSION', 'SOURCE_IDENTITY_CHANGED')
    return path

def provider_identity(scope):
    # Everything affecting generation/transport/budget is covered; only per-run
    # allocation, dataset and the identity containing this digest are excluded.
    excluded={'batch_id','principal_id','slots','semantic_acceptance_binding','formal_validation'}
    return digest({k:v for k,v in scope.items() if k not in excluded})

def validate_binding(binding, scope=None, *, check_files=True):
    from accepted_output import CONSUMERS, runtime_identity
    required={'schema_version','semantic_acceptance_mode','acceptance_policy_version',
        'acceptance_source_freeze','acceptance_source_manifest','trusted_semantic_runtime_version',
        'runtime_source_hashes','admission_adapter_version','semantic_source',
        'provider_config_identity','dataset_identity','rubric_identity','consumers',
        'request_contract_version','persistence_version','evaluator_contract_version'}
    calibrated=type(binding) is dict and binding.get('schema_version')==CALIBRATED_BINDING_VERSION
    bounded=type(binding) is dict and binding.get('schema_version') in (BOUNDED_BINDING_VERSION,CALIBRATED_BINDING_VERSION)
    require(type(binding) is dict and set(binding)==required | (BOUNDED_FIELDS if bounded else set()) | ({'calibration_pipeline_identity'} if calibrated else set()),
            'ADMISSION','FORMAL_ACCEPTANCE_BINDING_REQUIRED')
    expected={'schema_version':BINDING_VERSION,'semantic_acceptance_mode':'TRUSTED',
        'acceptance_policy_version':VERSION,'trusted_semantic_runtime_version':RUNTIME_VERSION,
        'admission_adapter_version':ADAPTER_VERSION,'request_contract_version':REQUEST_VERSION,
        'persistence_version':PERSISTENCE_VERSION,'evaluator_contract_version':EVALUATOR_VERSION}
    if bounded:
        expected.update(schema_version=BOUNDED_BINDING_VERSION,semantic_acceptance_mode='BOUNDED',
            acceptance_policy_version=DISPLAY_POLICY,persistence_version=BOUNDED_PERSISTENCE_VERSION,
            evaluator_contract_version=DUAL_GATE_VERSION,architecture_contract=ARCHITECTURE_CONTRACT,
            display_policy_version=DISPLAY_POLICY,state_admission_policy_version=STATE_POLICY,
            strict_semantic_policy_version=VERSION)
        require((binding['task_role'],binding['consumer_purpose']) in
                {('CONVERSATION','DISPLAY'),('STRICT_BOUNDED_CLAIM','BOUNDED_CLAIM')},
                'CONSUMER','BOUNDED_PURPOSE_REQUIRED')
    if calibrated:
        from provider_structural import pipeline_identity,SCOPE_VERSION
        expected.update(schema_version=CALIBRATED_BINDING_VERSION,persistence_version=CALIBRATED_PERSISTENCE_VERSION)
        require(binding['calibration_pipeline_identity']==pipeline_identity() and binding['consumer_purpose']=='DISPLAY',
                'ADMISSION','CALIBRATION_PIPELINE_BINDING_CHANGED')
        if scope is not None:
            require(scope.get('schema_version')==SCOPE_VERSION and scope.get('pipeline_identity')==binding['calibration_pipeline_identity'],
                    'ADMISSION','CALIBRATION_SCOPE_BINDING_CHANGED')
    for k,v in expected.items():
        failure='EVALUATION' if k=='evaluator_contract_version' else 'PERSISTENCE' if k=='persistence_version' else 'ADMISSION'
        require(binding.get(k)==v,failure,'FORMAL_'+k.upper()+'_MISMATCH')
    require(binding['consumers']==sorted(CONSUMERS),'CONSUMER','ACCEPTED_CONSUMERS_REQUIRED')
    require(binding['runtime_source_hashes']==runtime_identity(),'ADMISSION','ACCEPTANCE_RUNTIME_CHANGED')
    require(isinstance(binding['acceptance_source_freeze'],str) and bool(binding['acceptance_source_freeze']),
            'ADMISSION','SOURCE_FREEZE_REQUIRED')
    if scope is not None:
        require(scope.get('formal_validation') is True,'ADMISSION','FORMAL_VALIDATION_DECLARATION_REQUIRED')
        require(binding['provider_config_identity']==provider_identity(scope),'PROVIDER','PROVIDER_CONFIG_IDENTITY_CHANGED')
    if check_files:
        manifest=json.loads(reference(binding['acceptance_source_manifest']).read_text(encoding='utf-8-sig'))
        require(manifest.get('freeze_id')==binding['acceptance_source_freeze'],'ADMISSION','SOURCE_FREEZE_IDENTITY_CHANGED')
        require(type(manifest.get('files')) is dict and bool(manifest['files']),'ADMISSION','SOURCE_MANIFEST_REQUIRED')
        for name,expected_hash in manifest['files'].items():
            reference({'path':name,'sha256':expected_hash})
        for key in ('semantic_source','dataset_identity','rubric_identity'):
            ref=binding[key]; reference(ref)
            require(manifest['files'].get(ref['path'])==ref['sha256'],'ADMISSION','SOURCE_NOT_FROZEN')
        catalog=json.loads(reference(binding['semantic_source']).read_text(encoding='utf-8-sig'))
        require(catalog.get('version')==ADAPTER_VERSION,'ADMISSION','SEMANTIC_SOURCE_SCHEMA')
        if bounded:
            contract=json.loads(reference(binding['contract_manifest']).read_text(encoding='utf-8-sig'))
            require(contract.get('contract')==ARCHITECTURE_CONTRACT,'ADMISSION','ARCHITECTURE_CONTRACT_CHANGED')
            require(type(contract.get('files')) is dict and bool(contract['files']),
                    'ADMISSION','CONTRACT_MANIFEST_REQUIRED')
            for name,h in contract['files'].items(): reference({'path':name,'sha256':h})
            for key in ('contract_manifest','criterion_routing','consumer_authority_matrix'):
                ref=binding[key]; reference(ref)
                require(manifest['files'].get(ref['path'])==ref['sha256'],'ADMISSION','BOUNDED_SOURCE_NOT_FROZEN')
            for key in ('criterion_routing','consumer_authority_matrix'):
                ref=binding[key]
                require(contract['files'].get(ref['path'])==ref['sha256'],'ADMISSION','BOUNDED_CONTRACT_REFERENCE_CHANGED')
            # Routing bytes are hashed as evaluator provenance, never read as
            # production semantic rules, prompt data or claim selection.
    return binding

def install_binding(store, handle, binding, scope):
    from accepted_output import bind_mode
    validate_binding(binding,scope)
    existing=session_binding(store.db,handle.session_id)
    if existing is not None:
        require_session(store.db,handle.session_id,binding)
    bind_mode(store,handle,binding['semantic_acceptance_mode'])
    with layer('PERSISTENCE'):
        store.db.executescript('''
        CREATE TABLE IF NOT EXISTS semantic_session_binding(
          session_id TEXT PRIMARY KEY REFERENCES sessions(session_id),
          binding_json TEXT NOT NULL, binding_sha256 TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS semantic_binding_no_update BEFORE UPDATE ON semantic_session_binding
          BEGIN SELECT RAISE(ABORT,'SESSION_BINDING_IMMUTABLE'); END;
        CREATE TRIGGER IF NOT EXISTS semantic_binding_no_delete BEFORE DELETE ON semantic_session_binding
          BEGIN SELECT RAISE(ABORT,'SESSION_BINDING_IMMUTABLE'); END;
        CREATE TRIGGER IF NOT EXISTS formal_policy_no_update BEFORE UPDATE ON semantic_session_policy
          WHEN EXISTS(SELECT 1 FROM semantic_session_binding WHERE session_id=OLD.session_id)
          BEGIN SELECT RAISE(ABORT,'FORMAL_POLICY_IMMUTABLE'); END;
        CREATE TRIGGER IF NOT EXISTS formal_policy_no_delete BEFORE DELETE ON semantic_session_policy
          WHEN EXISTS(SELECT 1 FROM semantic_session_binding WHERE session_id=OLD.session_id)
          BEGIN SELECT RAISE(ABORT,'FORMAL_POLICY_IMMUTABLE'); END;
        ''')
        with store.transaction():
            row=store.db.execute('SELECT binding_json,binding_sha256 FROM semantic_session_binding WHERE session_id=?',
                                 (handle.session_id,)).fetchone()
            if row:
                require(row[0]==canonical(binding) and row[1]==digest(binding),'PERSISTENCE','SESSION_BINDING_IMMUTABLE')
            else:
                require(not store.db.execute('SELECT 1 FROM turns WHERE session_id=?',(handle.session_id,)).fetchone(),
                        'PERSISTENCE','FORMAL_BINDING_MUST_PRECEDE_TURNS')
                store.db.execute('INSERT INTO semantic_session_binding VALUES(?,?,?)',
                                 (handle.session_id,canonical(binding),digest(binding)))
    return binding

def session_binding(db, session_id):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='semantic_session_binding'").fetchone():
        return None
    row=db.execute('SELECT binding_json,binding_sha256 FROM semantic_session_binding WHERE session_id=?',(session_id,)).fetchone()
    if row is None: return None
    binding=json.loads(row[0])
    require(digest(binding)==row[1],'PERSISTENCE','SESSION_BINDING_CORRUPT')
    from accepted_output import session_mode
    expected=binding.get('semantic_acceptance_mode')
    require(expected in {'TRUSTED','BOUNDED'} and session_mode(db,session_id)==expected,
            'CONSUMER','FORMAL_SESSION_MUST_BE_TRUSTED' if expected=='TRUSTED' else 'BOUNDED_SESSION_POLICY_CHANGED')
    return binding

def require_session(db, session_id, binding):
    require(session_binding(db,session_id)==binding,'PERSISTENCE','FORMAL_SESSION_BINDING_MISSING_OR_CHANGED')
    for name in ('semantic_raw_outputs','accepted_outputs'):
        require(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone(),
                'PERSISTENCE','ACCEPTED_PERSISTENCE_REQUIRED')
    if binding['semantic_acceptance_mode']=='BOUNDED':
        for name in ('displayed_outputs','bounded_claim_outputs'):
            require(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone(),
                    'PERSISTENCE','BOUNDED_PERSISTENCE_REQUIRED')

def consumer_text(record, text):
    require(record is not None and text==record.get('accepted_assistant_text'),
            'CONSUMER','GUARD_ESCAPE_DETECTED')
    return text

def strict_selected(binding):
    """Only a host-bound policy chooses a finite proof request."""
    return binding['semantic_acceptance_mode']=='TRUSTED' or binding.get('consumer_purpose')=='BOUNDED_CLAIM'
