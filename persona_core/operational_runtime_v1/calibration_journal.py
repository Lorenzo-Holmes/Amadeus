"""An additive journal for the one fixed second request, never another turn."""
from __future__ import annotations
import hashlib
import json
import uuid
from transcript_store import ensure, utc_now
import provider_contract as pc
import provider_transport as pt
import provider_adapters as adapters
import provider_structural as ps
import provider_deepseek_formal as ds
import claim_calibration as cc


def install(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS calibration_calls_v2(
      call_id TEXT PRIMARY KEY, turn_id TEXT UNIQUE NOT NULL, batch_id TEXT NOT NULL,
      slot_id TEXT NOT NULL, parent_call_id TEXT NOT NULL, session_id TEXT NOT NULL,
      status TEXT NOT NULL, request_json TEXT NOT NULL, request_sha256 TEXT NOT NULL,
      input_json TEXT NOT NULL, input_sha256 TEXT NOT NULL, scope_json TEXT NOT NULL,
      origin TEXT NOT NULL, submitted_at_utc TEXT NOT NULL, response_at_utc TEXT,
      http_status INTEGER, wire BLOB, wire_sha256 TEXT, raw_response BLOB, raw_sha256 TEXT,
      visible_text TEXT, accounting_json TEXT, reserve_micro_cny INTEGER NOT NULL,
      error_category TEXT, UNIQUE(batch_id,slot_id));
    CREATE TABLE IF NOT EXISTS calibration_lifecycle_v2(
      seq INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT NOT NULL, at_utc TEXT NOT NULL, event_json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS calibration_outputs_v2(
      turn_id TEXT PRIMARY KEY, record_json TEXT NOT NULL, record_sha256 TEXT NOT NULL);
    CREATE TRIGGER IF NOT EXISTS calibration_request_no_update
      BEFORE UPDATE OF call_id,turn_id,batch_id,slot_id,parent_call_id,session_id,request_json,request_sha256,
                       input_json,input_sha256,scope_json,origin,submitted_at_utc,reserve_micro_cny
      ON calibration_calls_v2 BEGIN SELECT RAISE(ABORT,'CALIBRATION_REQUEST_IMMUTABLE'); END;
    CREATE TRIGGER IF NOT EXISTS calibration_terminal_no_update BEFORE UPDATE ON calibration_calls_v2
      WHEN OLD.status != 'SUBMITTED_STATUS_UNKNOWN'
      BEGIN SELECT RAISE(ABORT,'CALIBRATION_TERMINAL_IMMUTABLE'); END;
    CREATE TRIGGER IF NOT EXISTS calibration_call_no_delete BEFORE DELETE ON calibration_calls_v2
      BEGIN SELECT RAISE(ABORT,'CALIBRATION_CALL_IMMUTABLE'); END;
    CREATE TRIGGER IF NOT EXISTS calibration_output_no_update BEFORE UPDATE ON calibration_outputs_v2
      BEGIN SELECT RAISE(ABORT,'CALIBRATION_OUTPUT_IMMUTABLE'); END;
    CREATE TRIGGER IF NOT EXISTS calibration_output_no_delete BEFORE DELETE ON calibration_outputs_v2
      BEGIN SELECT RAISE(ABORT,'CALIBRATION_OUTPUT_IMMUTABLE'); END;
    ''')


def _save(store, turn_id, value):
    record = dict(value, turn_id=turn_id, version='APCORE_STAGE_OUTPUT_BINDING_1',
                  pipeline_identity=ps.pipeline_identity(), state_authority_granted=False)
    with store.transaction():
        old = store.db.execute('SELECT record_json FROM calibration_outputs_v2 WHERE turn_id=?', (turn_id,)).fetchone()
        if old:
            ensure(old[0] == pc.canonical(record).decode(), 'CALIBRATION_DISPOSITION_IMMUTABLE')
        else:
            store.db.execute('INSERT INTO calibration_outputs_v2 VALUES(?,?,?)',
                             (turn_id, pc.canonical(record).decode(), pc.digest(record)))
        if record['decision'] == 'HOLD':
            store.db.execute('UPDATE call_batches SET stopped=1 WHERE batch_id=?', (record['batch_id'],))
    return record


def hold(store, scope, turn_id, reason, *, call_id=None, input_identity=None):
    return _save(store, turn_id, {'batch_id':scope['batch_id'],'decision':'HOLD','final_text':None,
        'final_text_sha256':None,'call_id':call_id,'input_identity':input_identity,
        'reason':reason,'calibration':None,'semantic_verdict':None})


def load(db, turn_id):
    table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='calibration_outputs_v2'").fetchone()
    if not table:
        return None
    row = db.execute('SELECT * FROM calibration_outputs_v2 WHERE turn_id=?', (turn_id,)).fetchone()
    if not row:
        return None
    value = json.loads(row['record_json'])
    ensure(pc.digest(value) == row['record_sha256'] and value['turn_id'] == turn_id
           and value['pipeline_identity'] == ps.pipeline_identity(), 'CALIBRATION_RECORD_CORRUPT')
    if value['call_id'] is not None:
        call = verify_call(db, value['call_id'])
        ensure(call['turn_id'] == turn_id and call['batch_id'] == value['batch_id'], 'CALIBRATION_OUTPUT_CALL_BINDING')
        if value['decision'] != 'HOLD':
            supplied = json.loads(call['input_json'])
            calibrated = cc.validate(call['visible_text'], supplied)
            ensure(value['calibration'] == calibrated and value['final_text'] == calibrated['final_text']
                   and value['final_text_sha256'] == calibrated['final_text_sha256'], 'CALIBRATION_FINAL_CHANGED')
    return value


def verify_call(db, call_id):
    row = db.execute('SELECT * FROM calibration_calls_v2 WHERE call_id=?', (call_id,)).fetchone()
    ensure(row is not None, 'CALIBRATION_CALL_MISSING')
    call = dict(row)
    ensure(cc.text_sha(call['request_json']) == call['request_sha256']
           and cc.text_sha(call['input_json']) == call['input_sha256'], 'CALIBRATION_REQUEST_CORRUPT')
    supplied, scope = json.loads(call['input_json']), json.loads(call['scope_json'])
    ensure(scope['pipeline_identity'] == ps.pipeline_identity(), 'CALIBRATION_SOURCE_CHANGED')
    identity = supplied['input_identity']
    ensure(identity['turn_id'] == call['turn_id'] and identity['parent_call_id'] == call['parent_call_id']
           and identity['pipeline_identity'] == scope['pipeline_identity']
           and identity['draft_sha256'] == cc.text_sha(supplied['DRAFT'])
           and identity['messages_sha256'] == pc.digest(supplied['ELIGIBLE_CONTEXT']), 'CALIBRATION_PARENT_IDENTITY')
    request = json.loads(call['request_json'])
    ensure(request['input'] == [{'role':'system','content':cc.POLICY},
                               {'role':'user','content':pc.canonical(supplied).decode()}], 'CALIBRATION_CONTEXT_CHANGED')
    ps.input_guard_receipt(scope, call['request_json'].encode(), call['slot_id'])
    if not call['parent_call_id'].startswith('AUTHORED_PROBE:'):
        parent = db.execute('SELECT * FROM provider_calls WHERE call_id=?', (call['parent_call_id'],)).fetchone()
        ensure(parent is not None and parent['turn_id'] == call['turn_id'] and parent['batch_id'] == call['batch_id']
               and parent['session_id'] == call['session_id'] and parent['status'] == 'RESPONSE_CAPTURED'
               and parent['request_sha256'] == identity['parent_request_sha256']
               and pc.digest(json.loads(parent['context_json'])) == identity['context_sha256']
               and json.loads(parent['context_json'])['messages'] == supplied['ELIGIBLE_CONTEXT']
               and json.loads(parent['raw_response'])['choices'][0]['message']['content'] == supplied['DRAFT'],
               'CALIBRATION_PARENT_RAW_CHANGED')
    if call['wire'] is not None:
        ensure(hashlib.sha256(call['wire']).hexdigest() == call['wire_sha256'], 'CALIBRATION_WIRE_CORRUPT')
    if call['raw_response'] is not None:
        ensure(hashlib.sha256(call['raw_response']).hexdigest() == call['raw_sha256'], 'CALIBRATION_RAW_CORRUPT')
    if call['status'] in {'RESPONSE_CAPTURED','RESPONSE_REJECTED_TERMINAL_KNOWN'}:
        adapter = ps.StructuralAdapter()
        adapters.verified_result(adapter, scope, pt.TransportResult(call['http_status'],call['raw_response'],call['wire']))
        body = json.loads(call['raw_response'])
        ensure(json.loads(call['accounting_json']) == ds.accounting(body.get('native_usage'),scope,ds.MODEL),
               'CALIBRATION_ACCOUNTING_CORRUPT')
        if call['status'] == 'RESPONSE_CAPTURED':
            text, _ = pc.usable_reply(body, responses_api=True)
            ensure(text == call['visible_text'] and adapter.terminal(scope,body)[0] == 'completed',
                   'CALIBRATION_VISIBLE_CHANGED')
            adapter.validate_model(ds.MODEL, body['model'])
    return call


def counts(db, batch_id):
    drafts = db.execute('SELECT count(*) FROM provider_calls WHERE batch_id=?', (batch_id,)).fetchone()[0]
    calibrations = db.execute('SELECT count(*) FROM calibration_calls_v2 WHERE batch_id=?', (batch_id,)).fetchone()[0]
    return {'product_turns_submitted':drafts,'draft_calls':drafts,'calibration_calls':calibrations,
            'total_provider_requests':drafts+calibrations}


def before_draft(db, scope, turn_id):
    # Prevent a direct ChatService invocation from bypassing a previous stage's
    # uncertain outcome. The formal review-prefix gate remains separate.
    ensure(not db.execute("SELECT 1 FROM calibration_calls_v2 WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchone(),
           'CALIBRATION_PRIOR_UNKNOWN')
    pending=db.execute("SELECT p.turn_id FROM provider_calls p LEFT JOIN calibration_outputs_v2 c USING(turn_id) "
                       "WHERE p.batch_id=? AND p.status='RESPONSE_CAPTURED' AND c.turn_id IS NULL AND p.turn_id!=?",
                       (scope['batch_id'],turn_id)).fetchone()
    ensure(pending is None,'CALIBRATION_PREVIOUS_PIPELINE_INCOMPLETE')
    limits = scope['request_limits']
    c = counts(db,scope['batch_id'])
    exists = db.execute('SELECT 1 FROM provider_calls WHERE turn_id=?', (turn_id,)).fetchone()
    ensure(exists or (c['draft_calls'] < limits['draft'] and c['total_provider_requests'] < limits['total']),
           'STRUCTURAL_REQUEST_CAP')
    if not exists and scope['validation_purpose']=='NON_BENCHMARK_SMOKE':
        from transcript_store import WORKSPACE
        from pathlib import Path
        rows=db.execute('SELECT turn_id,slot_id,raw_sha256 FROM provider_calls WHERE batch_id=?',(scope['batch_id'],)).fetchall()
        for row in rows:
            path=WORKSPACE/'work/structural_calibration_20260921_01/smoke/reviews'/(row['slot_id']+'.json')
            ensure(path.is_file(),'SMOKE_REVIEW_REQUIRED_BEFORE_NEXT_REQUEST')
            review=json.loads(path.read_text(encoding='utf-8'))
            output=load(db,row['turn_id'])
            ensure(review.get('verdict')=='PASS' and review.get('draft_raw_sha256')==row['raw_sha256']
                   and output is not None and review.get('calibration_output_sha256')==pc.digest(output),
                   'SMOKE_REVIEW_FAIL_UNCLEAR_OR_IDENTITY_CHANGED')


def run(store, handle, scope, turn, *, transport=None, credential_reader=None):
    from provider import official_transport, existing_credential, _worker_command, WorkerNotSubmitted
    store._authenticate(handle)
    existing = load(store.db,turn['turn_id'])
    if existing:
        return existing
    parent = store.db.execute('SELECT * FROM provider_calls WHERE turn_id=?', (turn['turn_id'],)).fetchone()
    ensure(parent is not None and parent['status'] == 'RESPONSE_CAPTURED', 'CALIBRATION_USABLE_PARENT_REQUIRED')
    context = json.loads(parent['context_json'])
    from response_check import check_response
    check = check_response(turn['assistant_text'],context)
    if not check['display_allowed']:
        return hold(store,scope,turn['turn_id'],'KNOWN_INITIAL_DISPLAY_BOUNDARY')
    try:
        supplied, messages = cc.input_record(context,turn['assistant_text'],turn_id=turn['turn_id'],
            parent_call_id=parent['call_id'],parent_request_sha256=parent['request_sha256'],
            pipeline_identity=scope['pipeline_identity'])
    except ValueError as exc:
        return hold(store,scope,turn['turn_id'],str(exc))
    return run_input(store,handle,scope,parent['slot_id'],supplied,messages,
                     transport=transport,credential_reader=credential_reader)


def run_input(store, handle, scope, slot_id, supplied, messages, *, transport=None, credential_reader=None):
    from provider import official_transport, existing_credential, _worker_command, WorkerNotSubmitted
    store._authenticate(handle)
    tid = supplied['input_identity']['turn_id']
    identity=supplied['input_identity']
    ensure(identity['pipeline_identity']==scope['pipeline_identity']==ps.pipeline_identity()
           and identity['draft_sha256']==cc.text_sha(supplied['DRAFT'])
           and identity['messages_sha256']==pc.digest(supplied['ELIGIBLE_CONTEXT']), 'CALIBRATION_SUPPLIED_IDENTITY')
    if identity['parent_call_id'].startswith('AUTHORED_PROBE:'):
        probe=next((p for p in scope.get('authored_probes',[]) if p['id']==slot_id),None)
        ensure(probe is not None and identity['parent_call_id']=='AUTHORED_PROBE:'+slot_id
               and supplied['DRAFT']==probe['authored_draft']
               and supplied['ELIGIBLE_CONTEXT'][-1]=={'role':'user','content':probe['input']}, 'CALIBRATION_AUTHORED_PROBE_BINDING')
    else:
        parent=store.db.execute('SELECT * FROM provider_calls WHERE call_id=?',(identity['parent_call_id'],)).fetchone()
        ensure(parent is not None and parent['turn_id']==tid and parent['slot_id']==slot_id
               and parent['session_id']==handle.session_id and parent['batch_id']==scope['batch_id']
               and parent['status']=='RESPONSE_CAPTURED' and identity['parent_request_sha256']==parent['request_sha256']
               and identity['context_sha256']==pc.digest(json.loads(parent['context_json']))
               and supplied['ELIGIBLE_CONTEXT']==json.loads(parent['context_json'])['messages']
               and supplied['DRAFT']==json.loads(parent['raw_response'])['choices'][0]['message']['content'],
               'CALIBRATION_PRE_REQUEST_PARENT_BINDING')
    ensure(messages==[{'role':'system','content':cc.POLICY},{'role':'user','content':pc.canonical(supplied).decode()}],
           'CALIBRATION_PRE_REQUEST_MESSAGES')
    prior = load(store.db,tid)
    if prior:
        return prior
    adapter = ps.StructuralAdapter()
    stage_scope = dict(scope, request_stage='CALIBRATION')
    payload = pc.canonical(adapter.serialize(stage_scope,ds.MODEL,messages))
    ps.input_guard_receipt(stage_scope,payload,slot_id)
    old = store.db.execute('SELECT call_id FROM calibration_calls_v2 WHERE turn_id=?', (tid,)).fetchone()
    if old:
        call = verify_call(store.db,old[0])
        ensure(call['request_json'] == payload.decode(), 'CALIBRATION_REENTRY_INPUT_CHANGED')
    else:
        transport = transport or official_transport
        actual = transport is official_transport
        if actual:
            ps.require_paid_activation(stage_scope)
        key = (credential_reader or existing_credential)()
        ensure(isinstance(key,str) and key.strip() and key not in payload.decode(), 'CALIBRATION_CREDENTIAL_UNAVAILABLE_OR_ECHO')
        cid = 'cal_'+uuid.uuid4().hex
        with store.transaction():
            batch = store.db.execute('SELECT * FROM call_batches WHERE batch_id=?', (scope['batch_id'],)).fetchone()
            ensure(batch is not None and not batch['stopped'] and batch['scope_sha256'] == pc.digest(scope), 'CALIBRATION_BATCH_STOPPED')
            ensure(not store.db.execute("SELECT 1 FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchone()
                   and not store.db.execute("SELECT 1 FROM calibration_calls_v2 WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchone(),
                   'CALIBRATION_PRIOR_UNKNOWN')
            c = counts(store.db,scope['batch_id'])
            ensure(c['calibration_calls'] < scope['request_limits']['calibration'] and
                   c['total_provider_requests'] < scope['request_limits']['total'], 'CALIBRATION_REQUEST_CAP')
            amount = ps.reserve(stage_scope,ds.MODEL,len(pc.canonical(messages)))
            ensure((c['total_provider_requests']+1)*amount <= scope['reserved_upper_micro_cny'], 'CALIBRATION_FEE_CAP')
            store.db.execute('INSERT INTO calibration_calls_v2(call_id,turn_id,batch_id,slot_id,parent_call_id,session_id,status,'
                'request_json,request_sha256,input_json,input_sha256,scope_json,origin,submitted_at_utc,reserve_micro_cny)'
                ' VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (cid,tid,scope['batch_id'],slot_id,supplied['input_identity']['parent_call_id'],handle.session_id,
                 'SUBMITTED_STATUS_UNKNOWN',payload.decode(),hashlib.sha256(payload).hexdigest(),pc.canonical(supplied).decode(),
                 pc.digest(supplied),pc.canonical(stage_scope).decode(),
                 'TARGET_PROVIDER_CAPTURE' if actual else 'AUTHORED_PROVIDER_TEST_FIXTURE',utc_now(),amount))
        def event(value):
            pt.check_event(value)
            with store.transaction():
                store.db.execute('INSERT INTO calibration_lifecycle_v2(call_id,at_utc,event_json) VALUES(?,?,?)',
                                 (cid,utc_now(),pc.canonical(value).decode()))
        try:
            result = adapter.exchange(stage_scope,payload,key,event,_worker_command()) if actual else transport(payload,key)
            # Capture original wire before validation; a protocol failure retains
            # the submitted request and the observed bytes as UNKNOWN.
            ensure(isinstance(result,pt.TransportResult), 'CALIBRATION_UNTRUSTED_TRANSPORT')
            with store.transaction():
                wire = result.wire.replace(key.encode(), b'[REDACTED_CONFIGURED_CREDENTIAL]')
                raw = result.body.replace(key.encode(), b'[REDACTED_CONFIGURED_CREDENTIAL]')
                store.db.execute('UPDATE calibration_calls_v2 SET http_status=?,wire=?,wire_sha256=?,raw_response=?,raw_sha256=? WHERE call_id=?',
                    (result.status,wire,hashlib.sha256(wire).hexdigest(),raw,hashlib.sha256(raw).hexdigest(),cid))
            ensure(wire == result.wire and raw == result.body, 'CALIBRATION_SECRET_ECHO')
            adapters.verified_result(adapter,stage_scope,result)
            body = json.loads(raw)
            terminal, _, rejection = adapter.terminal(stage_scope,body)
            accounting = ds.accounting(body.get('native_usage'),stage_scope,ds.MODEL)
            visible = None
            category = rejection or accounting['rejection']
            try:
                adapter.validate_model(ds.MODEL,body['model'])
                if terminal == 'completed' and category is None:
                    visible, _ = pc.usable_reply(body,responses_api=True)
            except (ValueError,KeyError,TypeError,IndexError) as exc:
                category = type(exc).__name__
            status = 'RESPONSE_CAPTURED' if visible is not None else 'RESPONSE_REJECTED_TERMINAL_KNOWN'
            with store.transaction():
                store.db.execute('UPDATE calibration_calls_v2 SET status=?,response_at_utc=?,visible_text=?,accounting_json=?,error_category=? WHERE call_id=?',
                    (status,utc_now(),visible,pc.canonical(accounting).decode(),category,cid))
        except Exception as exc:
            with store.transaction():
                if isinstance(exc,pt.TransportFault):
                    wire = exc.wire.replace(key.encode(),b'[REDACTED_CONFIGURED_CREDENTIAL]')
                    store.db.execute('UPDATE calibration_calls_v2 SET http_status=?,wire=?,wire_sha256=? WHERE call_id=?',
                                     (exc.status,wire,hashlib.sha256(wire).hexdigest(),cid))
                local = isinstance(exc,WorkerNotSubmitted) and exc.request_sha256 == hashlib.sha256(payload).hexdigest()
                store.db.execute('UPDATE calibration_calls_v2 SET status=?,error_category=? WHERE call_id=?',
                    ('LOCAL_REJECTED_BEFORE_NETWORK' if local else 'SUBMITTED_STATUS_UNKNOWN',type(exc).__name__,cid))
                store.db.execute('UPDATE call_batches SET stopped=1 WHERE batch_id=?', (scope['batch_id'],))
            # Do not expose exception text; it may contain provider headers.
        finally:
            key = None
        call = verify_call(store.db,cid)
    if call['status'] != 'RESPONSE_CAPTURED':
        return hold(store,scope,tid,call['status'],call_id=call['call_id'],input_identity=supplied['input_identity'])
    try:
        calibrated = cc.validate(call['visible_text'],supplied)
    except (ValueError,TypeError,KeyError,IndexError):
        return hold(store,scope,tid,'CALIBRATION_PROTOCOL_HOLD',call_id=call['call_id'],input_identity=supplied['input_identity'])
    return _save(store,tid,{'batch_id':scope['batch_id'],'decision':calibrated['decision'],
        'final_text':calibrated['final_text'],'final_text_sha256':calibrated['final_text_sha256'],
        'call_id':call['call_id'],'input_identity':supplied['input_identity'],
        'reason':calibrated['audit']['decision_reason'],'calibration':calibrated,'semantic_verdict':None})


def accounting_summary(db,batch_id):
    result=counts(db,batch_id)
    rows=[verify_call(db,r[0]) for r in db.execute('SELECT call_id FROM calibration_calls_v2 WHERE batch_id=?',(batch_id,))]
    estimates=[json.loads(r['accounting_json']).get('estimate_micro_cny') if r['accounting_json'] else None for r in rows]
    result.update(calibration_reserved_micro_cny=sum(r['reserve_micro_cny'] for r in rows),
                  calibration_known_estimate_micro_cny=sum(v or 0 for v in estimates),
                  calibration_unestimated_calls=sum(v is None for v in estimates),
                  calibration_provider_unknown=sum(r['status']=='SUBMITTED_STATUS_UNKNOWN' for r in rows),
                  calibration_terminal_rejected=sum(r['status']=='RESPONSE_REJECTED_TERMINAL_KNOWN' for r in rows),
                  calibration_local_rejected=sum(r['status']=='LOCAL_REJECTED_BEFORE_NETWORK' for r in rows))
    return result
