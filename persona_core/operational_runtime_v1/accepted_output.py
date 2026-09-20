"""Separate immutable raw/accepted records, shared by every semantic consumer.

The OS/host and SQLite are the trust boundary. Hashes detect stale/corrupt data;
they do not authenticate malicious code with direct host/database write access.
"""
from dataclasses import dataclass, asdict
import base64
import hashlib
import json
from pathlib import Path
from semantic_types import *
from semantic_admission import TrustedAdmission, TrustedState
from semantic_validator import validate_with_fallback
from semantic_renderer import render, RENDERER_VERSION

MODES={'OFF','TRUSTED','BOUNDED'}
CONSUMERS={'display','history','next_turn_context','memory','evaluation','candidate','blind','audit','review'}
_ACCEPTED=object()

def runtime_identity():
    root=Path(__file__).parent
    names=('semantic_types.py','semantic_admission.py','semantic_validator.py',
           'semantic_renderer.py','accepted_output.py','chat.py','transcript_store.py',
           'semantic_binding.py','trusted_admission_adapter.py','operations.py')
    return {n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}

def install(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS semantic_session_policy(
      session_id TEXT PRIMARY KEY REFERENCES sessions(session_id), mode TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS semantic_raw_outputs(
      turn_id TEXT PRIMARY KEY REFERENCES turns(turn_id),
      raw_provider_response BLOB NOT NULL, raw_assistant_text TEXT NOT NULL,
      raw_sha256 TEXT NOT NULL, raw_text_sha256 TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS accepted_outputs(
      turn_id TEXT PRIMARY KEY REFERENCES turns(turn_id),
      record_json TEXT NOT NULL, record_sha256 TEXT NOT NULL);
    CREATE TRIGGER IF NOT EXISTS semantic_raw_no_update BEFORE UPDATE ON semantic_raw_outputs
      BEGIN SELECT RAISE(ABORT,'RAW_OUTPUT_IMMUTABLE'); END;
    CREATE TRIGGER IF NOT EXISTS semantic_raw_no_delete BEFORE DELETE ON semantic_raw_outputs
      BEGIN SELECT RAISE(ABORT,'RAW_OUTPUT_IMMUTABLE'); END;
    CREATE TRIGGER IF NOT EXISTS accepted_no_update BEFORE UPDATE ON accepted_outputs
      BEGIN SELECT RAISE(ABORT,'ACCEPTED_OUTPUT_IMMUTABLE'); END;
    CREATE TRIGGER IF NOT EXISTS accepted_no_delete BEFORE DELETE ON accepted_outputs
      BEGIN SELECT RAISE(ABORT,'ACCEPTED_OUTPUT_IMMUTABLE'); END;
    ''')

def session_mode(db,session_id):
    table=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='semantic_session_policy'").fetchone()
    if not table: return 'OFF'
    row=db.execute('SELECT mode FROM semantic_session_policy WHERE session_id=?',(session_id,)).fetchone()
    return row[0] if row else 'OFF'

def bind_mode(store,handle,mode):
    store._authenticate(handle)
    require(mode in MODES,'UNKNOWN_ACCEPTANCE_MODE')
    installed=store.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='semantic_session_policy'").fetchone()
    if not installed:
        if mode=='OFF': return
        require(not store.db.execute('SELECT 1 FROM turns WHERE session_id=?',(handle.session_id,)).fetchone(),
                'EXISTING_HISTORY_REQUIRES_EXPLICIT_MIGRATION')
        install(store.db)
    with store.transaction():
        row=store.db.execute('SELECT mode FROM semantic_session_policy WHERE session_id=?',(handle.session_id,)).fetchone()
        if row:
            require(row[0]==mode,'SESSION_ACCEPTANCE_POLICY_IMMUTABLE')
        else:
            require(mode=='OFF' or not store.db.execute('SELECT 1 FROM turns WHERE session_id=?',(handle.session_id,)).fetchone(),
                    'EXISTING_HISTORY_REQUIRES_EXPLICIT_MIGRATION')
            store.db.execute('INSERT INTO semantic_session_policy VALUES(?,?)',(handle.session_id,mode))
    if mode=='BOUNDED':
        store.db.executescript('''
        CREATE TABLE IF NOT EXISTS displayed_outputs(
          turn_id TEXT PRIMARY KEY REFERENCES turns(turn_id),
          record_json TEXT NOT NULL, record_sha256 TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS displayed_no_update BEFORE UPDATE ON displayed_outputs
          BEGIN SELECT RAISE(ABORT,'DISPLAYED_OUTPUT_IMMUTABLE'); END;
        CREATE TRIGGER IF NOT EXISTS displayed_no_delete BEFORE DELETE ON displayed_outputs
          BEGIN SELECT RAISE(ABORT,'DISPLAYED_OUTPUT_IMMUTABLE'); END;
        CREATE TABLE IF NOT EXISTS bounded_claim_outputs(
          turn_id TEXT PRIMARY KEY REFERENCES turns(turn_id),
          record_json TEXT NOT NULL, record_sha256 TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS bounded_claim_no_update BEFORE UPDATE ON bounded_claim_outputs
          BEGIN SELECT RAISE(ABORT,'BOUNDED_CLAIM_IMMUTABLE'); END;
        CREATE TRIGGER IF NOT EXISTS bounded_claim_no_delete BEFORE DELETE ON bounded_claim_outputs
          BEGIN SELECT RAISE(ABORT,'BOUNDED_CLAIM_IMMUTABLE'); END;
        ''')

@dataclass(frozen=True)
class AcceptedOutput:
    payload: str
    _seal: object

class SemanticAcceptance:
    """Host adapter. Callback supplies trusted typed state, never provider labels.

    Optional proposed_plan is a host test seam for offline parser simulations.
    Otherwise the captured visible provider string must be a strict proposal.
    """
    def __init__(self,admit=None,*,binding=None):
        self.admit=admit
        self.binding=binding

    def accept_display(self,*,handle,turn,context,raw_provider_response):
        """Display-purpose acceptance is never event admission or fact proof."""
        from semantic_binding import (validate_binding,strict_selected,DISPLAY_POLICY,
            BOUNDED_PERSISTENCE_VERSION,STATE_POLICY)
        from response_check import check_response
        from transcript_store import utc_now
        validate_binding(self.binding)
        require(self.binding['semantic_acceptance_mode']=='BOUNDED','BOUNDED_POLICY_REQUIRED')
        strict=None
        if strict_selected(self.binding):
            strict=json.loads(self.accept(handle=handle,turn=turn,context=context,
                raw_provider_response=raw_provider_response).payload)
            candidate=strict['accepted_assistant_text']
        else:
            candidate=turn['assistant_text']
        check=check_response(candidate,context)
        record={'version':BOUNDED_PERSISTENCE_VERSION,'schema_version':BOUNDED_PERSISTENCE_VERSION,
            'policy_version':DISPLAY_POLICY,'policy_purpose':'DISPLAY',
            'consumer_purpose':self.binding['consumer_purpose'],'feature_gate':'BOUNDED',
            'turn_id':turn['turn_id'],'session_id':handle.session_id,'entity_id':handle.entity_id,
            'mode':handle.mode,'acceptance_identity':self.binding,
            'request_context_digest':digest(context),'raw_provider_sha256':hashlib.sha256(raw_provider_response).hexdigest(),
            'raw_assistant_sha256':hashlib.sha256(turn['assistant_text'].encode()).hexdigest(),
            'candidate_visible_text':candidate,'candidate_visible_sha256':digest(candidate),
            'accepted_assistant_text':candidate if check['display_allowed'] else None,
            'display_decision':'ELIGIBLE' if check['display_allowed'] else 'WITHHOLD',
            'display_check':check,'display_acknowledgment':'PENDING',
            'authority':'CONVERSATIONAL','fact_true':None,'content_is_event_proof':False,
            'modality':None,'attribution':None,'metadata_absence':'No generic semantic classification requested',
            'typed_plan':strict['proposed_semantic_plan'] if strict else None,
            'strict_accepted_output':strict,'strict_policy_version':self.binding['strict_semantic_policy_version'],
            'state_admission_policy_version':STATE_POLICY,'state_admission_result':'NOT_REQUESTED',
            'runtime_commit_result':'NOT_REQUESTED','acceptance_timestamp':utc_now(),
            'source_runtime_identity':{'runtime_source_hashes':runtime_identity(),
                'submitted_context_digest':digest(context),'source_freeze':self.binding['acceptance_source_freeze']},
            'coverage':strict['coverage'] if strict else 'UNPARSED_CONVERSATIONAL',
            'transformation':{'action':'STRICT_CONTROLLED_RENDERER' if strict else 'DISPLAY_CHECK_ONLY',
                'provider_text_preserved':True,'source_text_sha256':digest(turn['assistant_text']),
                'candidate_text_sha256':digest(candidate)},
            'semantic_verdict':None,'raw_provider_violation':None}
        return AcceptedOutput(canonical(record),_ACCEPTED)

    def accept(self,*,handle,turn,context,raw_provider_response,proposed_plan=None):
        raw_text=turn['assistant_text']
        identity=(handle.session_id,handle.entity_id,turn['turn_id'],digest(turn['user_text']))
        if self.admit is None:
            a=TrustedAdmission(session_id=identity[0],entity_id=identity[1],turn_id=identity[2],raw_user_text=turn['user_text'])
            a.unparsed.append(digest(turn['user_text'])); state=a.freeze()
        else:
            state=self.admit(handle,{k:turn[k] for k in ('turn_id','session_id','user_text')},context)
        require(type(state) is TrustedState and state.identity==identity,'ADMISSION_CONTEXT_BINDING')
        state.check()
        parse_error=None
        raw_visible=raw_text
        original=proposed_plan if proposed_plan is not None else raw_text
        try:
            if self.binding is not None:
                from trusted_admission_adapter import parse_response
                require(proposed_plan is None,'FORMAL_PROVIDER_PROPOSAL_REQUIRED')
                plan,raw_visible=parse_response(raw_text)
                require(context.get('semantic_plan_request',{}).get('context_digest')==state.context_digest,
                        'FORMAL_REQUEST_ADMISSION_CHANGED')
                require(plan is not None,'UNPARSED_OR_UNSUPPORTED_INPUT')
            else:
                plan=parse_plan(original) if isinstance(original,str) else parse_plan(serialize_plan(original))
            result=validate_with_fallback(plan,state)
            if self.binding is not None:
                from semantic_binding import layer
                with layer('CERTIFICATE'):
                    result.check(state)
                with layer('RENDERER'):
                    rendered=render(result,state)
            else:
                rendered=render(result,state)
            validation=result.record()
            accepted_plan=[asdict(c.claim) for c in result.certificates]
            certificates=[{'certificate_id':d.certificate.certificate_id,**asdict(d.certificate),
                           'closure_certificate':asdict(d.closure) if d.closure else None}
                          for d in result.decisions if d.certificate]
            proposed=asdict(plan)
        except (SemanticError,TypeError,AttributeError) as exc:
            parse_error=str(exc) if isinstance(exc,SemanticError) else 'INVALID_PLAN_TYPE'
            validation={'version':VERSION,'decisions':[],'action':'BLOCK','reason':parse_error}
            accepted_plan=[]; certificates=[]; proposed=original if isinstance(original,str) else None
            rendered=None
        text=rendered.text if rendered else '这段信息还不能支持可靠判断，请补充明确的条件或来源。'
        transformed=raw_visible!=text
        from transcript_store import utc_now
        record={'version':VERSION,'turn_id':turn['turn_id'],'session_id':handle.session_id,'entity_id':handle.entity_id,
          'raw_provider_sha256':hashlib.sha256(raw_provider_response).hexdigest(),
          'raw_assistant_sha256':hashlib.sha256(raw_text.encode()).hexdigest(),
          'proposed_semantic_plan':proposed,'validation_result':validation,
          'certificate_refs':[c['certificate_id'] for c in certificates],'certificates':certificates,
          'accepted_assistant_text':text,'accepted_semantic_plan':accepted_plan,
          'acceptance_timestamp':utc_now(),'source_runtime_identity':{'architecture':VERSION,
              'runtime_source_hashes':runtime_identity(),
              'renderer':RENDERER_VERSION,'sources':state.public_state()['sources'],
              'trusted_context_digest':state.context_digest,'submitted_context_digest':digest(context)},
          'trusted_semantic_state':state.public_state(),'rendered_clauses':list(rendered.clauses) if rendered else [],
          'transformation':{'provider_text_preserved':True,'provider_prose_matches':not transformed,
              'action':'REBUILD_FROM_VALIDATED_STATE' if transformed else 'ALLOW',
              'visible_plan_consistency':'MISMATCH_REBUILT' if transformed else 'EXACT_HOST_REALIZATION',
              'parse_error':parse_error,'host_fallback_claims':[c['claim_id'] for c in accepted_plan
                  if c['claim_id'].startswith('_host_fallback_')]},
          'coverage':'TYPED_VALIDATED' if accepted_plan else 'UNPARSED_OR_UNSUPPORTED_FALLBACK',
          'raw_is_accepted':False,'feature_gate':'TRUSTED'}
        if self.binding is not None:
            from semantic_binding import validate_binding
            validate_binding(self.binding)
            decisions=validation.get('decisions',[])
            actions=[d['action'] for d in decisions]
            action=('BLOCK' if not accepted_plan else 'DOWNGRADE' if 'BLOCK' in actions or 'DOWNGRADE' in actions
                    or transformed else 'QUALIFY' if 'QUALIFY' in actions else 'ALLOW')
            violation=bool(parse_error or transformed or any(a!='ALLOW' for a in actions))
            record.update(acceptance_identity=self.binding,raw_visible_text=raw_visible,
                acceptance_disposition=action,
                acceptance_audit={
                    'raw_response_present':bool(raw_provider_response),'raw_visible_text_present':bool(raw_visible),
                    'semantic_admission_status':'ADMITTED_WITH_UNPARSED_REMAINDER' if state.evidence and state.unparsed_sha256
                        else 'ADMITTED' if state.evidence else 'UNPARSED',
                    'proposed_plan_present':isinstance(proposed,dict),'validator_result':validation,
                    'certificate_status':'HOST_CERTIFIED' if certificates else 'NO_AUTHORIZED_CLAIMS',
                    'acceptance_action':action,'accepted_text_present':bool(text),
                    'consumer_binding_status':'REQUIRED_ACCEPTED_ONLY',
                    'raw_provider_violation':violation,'guard_containment':violation,'guard_escape':False,
                    'violation_basis':parse_error or ('VISIBLE_REALIZATION_MISMATCH' if transformed else
                        'PLAN_TRANSFORMED' if violation else None)})
        return AcceptedOutput(canonical(record),_ACCEPTED)

def persist(store,handle,turn_id,raw_provider_response,accepted):
    store._authenticate(handle)
    require(type(accepted) is AcceptedOutput and accepted._seal is _ACCEPTED,'HOST_ACCEPTED_OUTPUT_REQUIRED')
    record=json.loads(accepted.payload); turn=store.get_turn(handle,turn_id)
    from semantic_binding import session_binding, require_session
    binding=session_binding(store.db,handle.session_id)
    if binding is not None:
        require_session(store.db,handle.session_id,binding)
        require(record.get('acceptance_identity')==binding,'ACCEPTED_POLICY_SOURCE_BINDING')
    require(session_mode(store.db,handle.session_id) in {'TRUSTED','BOUNDED'},'ACCEPTANCE_GATE_REQUIRED')
    require(record['turn_id']==turn_id and record['session_id']==handle.session_id and record['entity_id']==handle.entity_id,'ACCEPTED_IDENTITY_MISMATCH')
    raw_sha=hashlib.sha256(raw_provider_response).hexdigest()
    text_sha=hashlib.sha256(turn['assistant_text'].encode()).hexdigest()
    require(raw_sha==record['raw_provider_sha256'] and text_sha==record['raw_assistant_sha256'],'RAW_ACCEPTED_BINDING')
    call=store.db.execute('SELECT raw_response,context_json FROM provider_calls WHERE turn_id=?',(turn_id,)).fetchone()
    require(call is not None and bytes(call[0])==raw_provider_response
            and digest(json.loads(call[1]))==record['source_runtime_identity']['submitted_context_digest'],'PROVIDER_RECEIPT_BINDING')
    with store.transaction():
        existing=store.db.execute('SELECT record_json FROM accepted_outputs WHERE turn_id=?',(turn_id,)).fetchone()
        if existing:
            require(existing[0]==accepted.payload,'ACCEPTED_OUTPUT_IMMUTABLE')
        else:
            store.db.execute('INSERT INTO semantic_raw_outputs VALUES(?,?,?,?,?)',
               (turn_id,raw_provider_response,turn['assistant_text'],raw_sha,text_sha))
            store.db.execute('INSERT INTO accepted_outputs VALUES(?,?,?)',(turn_id,accepted.payload,digest(record)))
    return record

def load_record(db,turn_id):
    exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='accepted_outputs'").fetchone()
    if not exists: return None
    row=db.execute('SELECT record_json,record_sha256 FROM accepted_outputs WHERE turn_id=?',(turn_id,)).fetchone()
    if row is None: return None
    record=json.loads(row[0]); require(digest(record)==row[1],'ACCEPTED_RECORD_CORRUPT')
    from semantic_binding import BOUNDED_PERSISTENCE_VERSION,validate_binding
    bounded=record.get('version')==BOUNDED_PERSISTENCE_VERSION
    require(bounded or (record['version']==VERSION and record['source_runtime_identity']['renderer']==RENDERER_VERSION),
            'ACCEPTED_VERSION_CHANGED')
    require(record['source_runtime_identity']['runtime_source_hashes']==runtime_identity(),'ACCEPTED_RUNTIME_CHANGED')
    raw=db.execute('SELECT * FROM semantic_raw_outputs WHERE turn_id=?',(turn_id,)).fetchone()
    turn=db.execute('SELECT assistant_text,session_id FROM turns WHERE turn_id=?',(turn_id,)).fetchone()
    require(raw is not None and turn is not None,'ACCEPTED_RAW_MISSING')
    require(hashlib.sha256(bytes(raw['raw_provider_response'])).hexdigest()==record['raw_provider_sha256']==raw['raw_sha256']
       and hashlib.sha256(raw['raw_assistant_text'].encode()).hexdigest()==record['raw_assistant_sha256']==raw['raw_text_sha256']
       and raw['raw_assistant_text']==turn['assistant_text'] and record['session_id']==turn['session_id'],'ACCEPTED_RAW_CORRUPT')
    call=db.execute('SELECT raw_response,context_json FROM provider_calls WHERE turn_id=?',(turn_id,)).fetchone()
    require(call is not None and bytes(call[0])==bytes(raw['raw_provider_response'])
       and digest(json.loads(call[1]))==record['source_runtime_identity']['submitted_context_digest'],'ACCEPTED_RECEIPT_CHANGED')
    from semantic_binding import session_binding, require_session, consumer_text
    binding=session_binding(db,record['session_id'])
    if bounded:
        require(binding is not None,'BOUNDED_BINDING_REQUIRED')
        validate_binding(binding)
        require(record.get('feature_gate')=='BOUNDED' and record.get('schema_version')==BOUNDED_PERSISTENCE_VERSION
                and binding['semantic_acceptance_mode']=='BOUNDED','BOUNDED_RECORD_VERSION')
        entity=db.execute('SELECT entity_id,mode FROM sessions WHERE session_id=?',(record['session_id'],)).fetchone()
        require(entity is not None and entity[0]==record['entity_id'] and entity[1]==record['mode'],
                'BOUNDED_ENTITY_CHANGED')
        require(record['candidate_visible_sha256']==digest(record['candidate_visible_text']), 'DISPLAY_CANDIDATE_CHANGED')
        require(record['accepted_assistant_text']==(record['candidate_visible_text'] if record['display_decision']=='ELIGIBLE' else None),
                'DISPLAY_ACCEPTANCE_CHANGED')
    if binding is not None:
        require_session(db,record['session_id'],binding)
        require(record.get('acceptance_identity')==binding,'ACCEPTED_POLICY_SOURCE_CHANGED')
        if not bounded:
            clauses=record['rendered_clauses']
            expected=''.join(c['text'] for c in clauses) if clauses else '这段信息还不能支持可靠判断，请补充明确的条件或来源。'
            consumer_text(record,expected)
    return record

def acknowledge_display(store,handle,turn_id,text,at_utc):
    """Called in the same transaction as the actual sink acknowledgment."""
    store._authenticate(handle)
    record=load_record(store.db,turn_id)
    require(record is not None and record['session_id']==handle.session_id and record['entity_id']==handle.entity_id,
            'DISPLAY_ACK_IDENTITY')
    require(record['feature_gate']=='BOUNDED' and record['display_decision']=='ELIGIBLE'
            and text==record['accepted_assistant_text'],'DISPLAY_ACK_EXACT_CANDIDATE_REQUIRED')
    ack=store.db.execute('SELECT status,ack_at_utc FROM display_journal WHERE turn_id=?',(turn_id,)).fetchone()
    require(ack is not None and ack[0]=='DISPLAY_ACK' and ack[1]==at_utc,'DISPLAY_SINK_ACK_REQUIRED')
    value={'version':record['version'],'policy_version':record['policy_version'],'policy_purpose':'DISPLAY',
        'turn_id':turn_id,'session_id':handle.session_id,'entity_id':handle.entity_id,
        'accepted_output_sha256':digest(record),'displayed_text':text,'displayed_text_sha256':digest(text),
        'acknowledged_at_utc':at_utc,'status':'DISPLAY_ACK','human_read_receipt':False,
        'authority':'CONVERSATIONAL','content_is_event_proof':False}
    old=store.db.execute('SELECT record_json FROM displayed_outputs WHERE turn_id=?',(turn_id,)).fetchone()
    if old: require(old[0]==canonical(value),'DISPLAY_ACK_IMMUTABLE')
    else: store.db.execute('INSERT INTO displayed_outputs VALUES(?,?,?)',(turn_id,canonical(value),digest(value)))
    return value

def load_display_record(db,turn_id,record=None):
    record=record or load_record(db,turn_id)
    require(record is not None and record.get('feature_gate')=='BOUNDED','BOUNDED_DISPLAY_RECORD_REQUIRED')
    row=db.execute('SELECT record_json,record_sha256 FROM displayed_outputs WHERE turn_id=?',(turn_id,)).fetchone()
    if row is None: return None
    value=json.loads(row[0])
    require(digest(value)==row[1] and value['accepted_output_sha256']==digest(record),'DISPLAY_RECORD_CORRUPT')
    require(all(value[k]==record[k] for k in ('turn_id','session_id','entity_id','policy_version')),'DISPLAY_RECORD_IDENTITY')
    require(value['displayed_text']==record['accepted_assistant_text'] and
            value['displayed_text_sha256']==digest(value['displayed_text']),'DISPLAY_TEXT_CORRUPT')
    ack=db.execute('SELECT d.status,d.ack_at_utc,t.status,t.display_at_utc FROM display_journal d JOIN turns t USING(turn_id) WHERE turn_id=?',
                   (turn_id,)).fetchone()
    require(ack is not None and ack[0]=='DISPLAY_ACK' and ack[2]=='DISPLAYED' and
            ack[1]==ack[3]==value['acknowledged_at_utc'],'DISPLAY_ACK_CHANGED')
    return value

def certify_bounded_claim(store,handle,turn_id,proposed_plan):
    """Explicit host request for a separate finite proof on an observed turn.

    This never changes displayed words, issues event authority, or asks a
    provider. The existing frozen catalog, validator and renderer do the work.
    """
    from trusted_admission_adapter import TrustedAdmissionAdapter
    store._authenticate(handle)
    turn=store.get_turn(handle,turn_id)
    record=load_record(store.db,turn_id)
    displayed=load_display_record(store.db,turn_id,record)
    require(displayed is not None,'ACKNOWLEDGED_DISPLAY_REQUIRED')
    proposal=proposed_plan if isinstance(proposed_plan,str) else serialize_plan(proposed_plan)
    old=load_bounded_claim(store.db,turn_id,record,displayed)
    if old:
        require(old['proposal_sha256']==digest(proposal),'BOUNDED_CLAIM_IMMUTABLE')
        return old
    call=store.db.execute('SELECT raw_response,context_json FROM provider_calls WHERE turn_id=?',(turn_id,)).fetchone()
    acceptance=SemanticAcceptance(TrustedAdmissionAdapter(record['acceptance_identity']))
    result=json.loads(acceptance.accept(handle=handle,turn=turn,context=json.loads(call['context_json']),
        raw_provider_response=bytes(call['raw_response']),proposed_plan=proposal).payload)
    value={'version':record['version'],'policy_version':VERSION,'policy_purpose':'BOUNDED_CLAIM',
        'turn_id':turn_id,'session_id':handle.session_id,'entity_id':handle.entity_id,
        'acceptance_identity':record['acceptance_identity'],'displayed_output_sha256':digest(displayed),
        'proposal_sha256':digest(proposal),'strict_accepted_output':result,
        'state_authority_granted':False,'display_modified':False}
    with store.transaction():
        store.db.execute('INSERT INTO bounded_claim_outputs VALUES(?,?,?)',(turn_id,canonical(value),digest(value)))
    return value

def load_bounded_claim(db,turn_id,record=None,displayed=None):
    row=db.execute('SELECT record_json,record_sha256 FROM bounded_claim_outputs WHERE turn_id=?',(turn_id,)).fetchone()
    if row is None:return None
    record=record or load_record(db,turn_id)
    displayed=displayed or load_display_record(db,turn_id,record)
    value=json.loads(row[0]);strict=value['strict_accepted_output']
    require(digest(value)==row[1] and displayed is not None and value['displayed_output_sha256']==digest(displayed),
            'BOUNDED_CLAIM_RECORD_CORRUPT')
    require(all(value[k]==record[k]==strict[k] for k in ('turn_id','session_id','entity_id'))
            and value['acceptance_identity']==record['acceptance_identity'],'BOUNDED_CLAIM_IDENTITY_CHANGED')
    require(strict['source_runtime_identity']['runtime_source_hashes']==runtime_identity()
            and strict['raw_provider_sha256']==record['raw_provider_sha256']
            and strict['raw_assistant_sha256']==record['raw_assistant_sha256'],'BOUNDED_CLAIM_SOURCE_CHANGED')
    return value

def project_turn(db,row,purpose):
    """Explicit selection; assistant_text in this projection means accepted text.

    The underlying turns.assistant_text is always the immutable raw capture.
    Legacy sessions remain an explicit OFF-policy provenance, never certified.
    """
    require(purpose in CONSUMERS,'CONSUMER_MUST_SELECT_SOURCE')
    result=dict(row)
    tid=result['turn_id']
    sid=result.get('session_id')
    if sid is None: sid=db.execute('SELECT session_id FROM turns WHERE turn_id=?',(tid,)).fetchone()[0]
    from semantic_binding import session_binding
    session_binding(db,sid)  # A formal binding can never silently become OFF.
    if session_mode(db,sid)=='OFF':
        return result
    if session_mode(db,sid)=='BOUNDED':
        record=load_record(db,tid)
        displayed=load_display_record(db,tid,record) if record else None
        acknowledged=result.get('turn_status',result.get('status'))=='DISPLAYED'
        if acknowledged or purpose in {'display','memory','candidate','blind'}:
            require(displayed is not None,'ACKNOWLEDGED_DISPLAY_REQUIRED')
        raw=result.pop('assistant_text',None)
        result.update(assistant_text=displayed['displayed_text'] if displayed else None,
            displayed_text=displayed['displayed_text'] if displayed else None,
            output_provenance='HOST_ACKNOWLEDGED_DISPLAY' if displayed else 'UNACKNOWLEDGED_DISPLAY',
            display_record=displayed,accepted_output_sha256=digest(record) if record else None,
            authority='CONVERSATIONAL',content_is_event_proof=False)
        if purpose in {'audit','review','evaluation'}:
            result.update(raw_assistant_text=raw,accepted_assistant_text=record['accepted_assistant_text'] if record else None,
                accepted_output=record)
            result['bounded_claim_output']=load_bounded_claim(db,tid,record,displayed) if displayed else None
            trace=db.execute('SELECT trace_json FROM chat_traces WHERE turn_id=?',(tid,)).fetchone()
            result['state_lineage']=json.loads(trace[0]) if trace else None
        return result
    record=load_record(db,tid)
    result['raw_assistant_text']=result.get('assistant_text')
    result['accepted_assistant_text']=record['accepted_assistant_text'] if record else None
    result['assistant_text']=result['accepted_assistant_text']
    result['output_provenance']='HOST_ACCEPTED_OUTPUT' if record else 'UNACCEPTED_DRAFT'
    result['accepted_output']=record
    if result.get('turn_status',result.get('status'))=='DISPLAYED' or purpose in {'display','memory','candidate','blind'}:
        require(record is not None,'ACCEPTED_OUTPUT_REQUIRED')
    return result

def raw_text_for_audit(row):
    """Validate versioned export lineage before applying the legacy raw invariant."""
    if row.get('output_provenance')=='HOST_ACKNOWLEDGED_DISPLAY':
        from semantic_binding import BOUNDED_PERSISTENCE_VERSION,validate_binding
        record=row.get('accepted_output'); displayed=row.get('display_record')
        require(type(record) is dict and record.get('version')==BOUNDED_PERSISTENCE_VERSION
                and type(displayed) is dict,'BOUNDED_EXPORT_REQUIRED')
        validate_binding(record['acceptance_identity'])
        require(all(record[k]==row[k]==displayed[k] for k in ('turn_id','session_id')),'BOUNDED_EXPORT_IDENTITY')
        require(displayed['accepted_output_sha256']==digest(record) and displayed['status']=='DISPLAY_ACK',
                'BOUNDED_EXPORT_ACK_BINDING')
        require(row['assistant_text']==row['displayed_text']==displayed['displayed_text']==row['accepted_assistant_text']
                ==record['accepted_assistant_text'] and digest(row['assistant_text'])==displayed['displayed_text_sha256'],
                'BOUNDED_EXPORTED_DISPLAY_CHANGED')
        require(hashlib.sha256(row['raw_assistant_text'].encode()).hexdigest()==record['raw_assistant_sha256']
                and record['raw_provider_sha256']==row['raw_sha256'],'BOUNDED_EXPORTED_RAW_CHANGED')
        separate=row.get('bounded_claim_output')
        if separate is not None:
            require(separate.get('policy_purpose')=='BOUNDED_CLAIM' and separate.get('state_authority_granted') is False
                and separate.get('display_modified') is False and separate.get('displayed_output_sha256')==digest(displayed)
                and separate.get('acceptance_identity')==record['acceptance_identity'],'BOUNDED_EXPORTED_CLAIM_BINDING')
            claim=separate['strict_accepted_output']
            require(all(claim[k]==record[k]==separate[k] for k in ('turn_id','session_id','entity_id')) and
                    claim['raw_provider_sha256']==record['raw_provider_sha256'] and
                    claim['raw_assistant_sha256']==record['raw_assistant_sha256'],'BOUNDED_EXPORTED_CLAIM_SOURCE')
        return row['raw_assistant_text']
    if row.get('output_provenance')!='HOST_ACCEPTED_OUTPUT':
        require(not any(k in row for k in ('accepted_output','raw_assistant_text','accepted_assistant_text')),
                'INCOMPLETE_ACCEPTED_PROVENANCE')
        return row['assistant_text']
    record=row.get('accepted_output')
    require(type(record) is dict and record.get('version')==VERSION and record.get('feature_gate')=='TRUSTED','ACCEPTED_PROVENANCE_REQUIRED')
    require(record['turn_id']==row['turn_id'] and record['session_id']==row['session_id'],'EXPORTED_ACCEPTED_IDENTITY')
    require(record['accepted_assistant_text']==row['assistant_text']==row['accepted_assistant_text'], 'EXPORTED_ACCEPTED_TEXT_CHANGED')
    require(hashlib.sha256(row['raw_assistant_text'].encode()).hexdigest()==record['raw_assistant_sha256']
            and record['raw_provider_sha256']==row['raw_sha256'],'EXPORTED_RAW_BINDING')
    return row['raw_assistant_text']
