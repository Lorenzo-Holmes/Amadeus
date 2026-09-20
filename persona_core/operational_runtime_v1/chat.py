"""Chinese text conversation lifecycle with explicit, non-replayed delivery.

The terminal is not transactional with SQLite. A crash after DISPLAY_INTENT
therefore produces DELIVERY_STATUS_UNKNOWN, never a claim of exactly-once
human receipt. Such output can be inspected explicitly without another API call.
"""
from __future__ import annotations
import json
from typing import Any, Callable
from context_router import build_context
from provider import ProviderJournal, canonical
from response_check import check_response
from transcript_store import TranscriptStore, SessionHandle, ensure, utc_now

class ChatService:
    def __init__(self, store: TranscriptStore, handle: SessionHandle, scope: dict,
                 *, memory_provider=None, admission_controller=None, growth_controller=None,
                 semantic_acceptance_mode=None, semantic_acceptance=None,semantic_acceptance_binding=None):
        store._authenticate(handle)
        self.store, self.handle, self.scope = store, handle, scope
        self.memory_provider = memory_provider
        self.admission = admission_controller
        self.growth = growth_controller
        from accepted_output import bind_mode, session_mode, SemanticAcceptance
        from semantic_binding import require as binding_require, install_binding, session_binding
        self.acceptance_binding=semantic_acceptance_binding
        formal=scope.get('formal_validation') or 'semantic_acceptance_binding' in scope or session_binding(store.db,handle.session_id) is not None
        if formal:
            from trusted_admission_adapter import TrustedAdmissionAdapter
            binding_require(semantic_acceptance_mode in {'TRUSTED','BOUNDED'} and semantic_acceptance_binding is not None
                and semantic_acceptance_binding==scope.get('semantic_acceptance_binding'),
                'ADMISSION','EXPLICIT_FORMAL_ACCEPTANCE_REQUIRED')
            from semantic_binding import strict_selected
            binding_require(type(semantic_acceptance) is SemanticAcceptance
                and semantic_acceptance.binding==semantic_acceptance_binding
                and (not strict_selected(semantic_acceptance_binding) or
                     (type(semantic_acceptance.admit) is TrustedAdmissionAdapter
                      and semantic_acceptance.admit.binding==semantic_acceptance_binding)),
                'ADMISSION','TRUSTED_ADMISSION_ADAPTER_REQUIRED')
            install_binding(store,handle,semantic_acceptance_binding,scope)
        self.acceptance_mode = semantic_acceptance_mode or session_mode(store.db, handle.session_id)
        ensure(self.acceptance_mode!='BOUNDED' or self.acceptance_binding is not None,'Explicit bounded policy binding required')
        bind_mode(store, handle, self.acceptance_mode)
        self.acceptance = semantic_acceptance or SemanticAcceptance()
        ensure(type(self.acceptance) is SemanticAcceptance, 'Host semantic acceptance adapter required')
        self.journal = ProviderJournal(store)
        self.journal.register_batch(scope)
        store.db.executescript('''
        CREATE TABLE IF NOT EXISTS response_checks(
          turn_id TEXT PRIMARY KEY REFERENCES turns(turn_id),
          checked_at_utc TEXT NOT NULL, check_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS display_journal(
          turn_id TEXT PRIMARY KEY REFERENCES turns(turn_id),
          status TEXT NOT NULL, intent_at_utc TEXT NOT NULL, ack_at_utc TEXT);
        CREATE TABLE IF NOT EXISTS chat_traces(
          turn_id TEXT PRIMARY KEY REFERENCES turns(turn_id),
          trace_json TEXT NOT NULL);
        ''')

    def status(self) -> dict[str, Any]:
        self.store._authenticate(self.handle)
        turns = self.store.recent(self.handle, 100)
        unknown = [dict(r) for r in self.store.db.execute(
            'SELECT p.call_id,p.slot_id,p.status FROM provider_calls p '
            'WHERE p.session_id=? AND p.status=?',
            (self.handle.session_id, 'SUBMITTED_STATUS_UNKNOWN'))]
        return {'session_id': self.handle.session_id, 'entity_id': self.handle.entity_id,
                'mode': self.handle.mode, 'visible_turn_count': len(turns),
                'unresolved_calls': unknown, 'production': False}

    def next_slot(self, text: str) -> dict:
        label = self.store.db.execute('SELECT label FROM entities WHERE entity_id=?',
                                      (self.handle.entity_id,)).fetchone()[0]
        consumed = {r[0] for r in self.store.db.execute(
            'SELECT slot_id FROM provider_calls WHERE batch_id=?', (self.scope['batch_id'],))}
        candidates = [s for s in self.scope['slots'] if s['entity_label'] == label and s['id'] not in consumed]
        ensure(bool(candidates), 'Pinned batch has no remaining slot for this entity')
        slot = candidates[0]
        ensure(slot['user_text'] is None or slot['user_text'] == text,
               'Input does not match the next pinned evaluation turn')
        return slot

    def build_request_context(self, tid):
        """One construction path for formal preview and the submitted request."""
        if self.acceptance_binding is None:
            return build_context(self.store,self.handle,tid,max_prompt_bytes=self.scope['max_input_bytes'],
                                 memory_provider=self.memory_provider)
        from semantic_binding import validate_binding,require_session,require as binding_require,layer,strict_selected
        from trusted_admission_adapter import request_contract,TrustedAdmissionAdapter
        validate_binding(self.acceptance_binding,self.scope)
        require_session(self.store.db,self.handle.session_id,self.acceptance_binding)
        if not strict_selected(self.acceptance_binding):
            context=build_context(self.store,self.handle,tid,max_prompt_bytes=self.scope['max_input_bytes'],
                                  memory_provider=self.memory_provider)
            context['display_policy_binding']={'policy':self.acceptance_binding['display_policy_version'],
                'consumer_purpose':'DISPLAY','authority':'CONVERSATIONAL',
                'state_admission_policy':self.acceptance_binding['state_admission_policy_version']}
            return context
        binding_require(self.acceptance_mode in {'TRUSTED','BOUNDED'} and type(self.acceptance.admit) is TrustedAdmissionAdapter,
                        'ADMISSION','FORMAL_ADAPTER_MISSING')
        turn=self.store.get_turn(self.handle,tid)
        state=self.acceptance.admit(self.handle,turn,{})
        contract=request_contract(state,self.acceptance_binding)
        message={'role':'system','content':'Host semantic proposal contract:\n'+canonical(contract).decode('utf-8')}
        reserve=len(canonical([message]))+2
        with layer('ADMISSION'):
            context=build_context(self.store,self.handle,tid,max_prompt_bytes=self.scope['max_input_bytes']-reserve,
                                  memory_provider=self.memory_provider)
        context['messages'].insert(-1,message)
        context['semantic_plan_request']=contract
        context['prompt_bytes']=len(canonical(context['messages']))
        binding_require(context['prompt_bytes']<=self.scope['max_input_bytes'],'ADMISSION','CONTRACT_EXCEEDS_REQUEST_BUDGET')
        return context

    def send_text(self, text: str, idempotency_key: str, *, slot_id: str,
                  display: Callable[[str], None] | None = None,
                  transport=None, credential_reader=None) -> dict[str, Any]:
        if self.acceptance_binding is not None:
            from semantic_binding import require_session,require as binding_require,strict_selected,validate_binding
            from trusted_admission_adapter import TrustedAdmissionAdapter
            require_session(self.store.db,self.handle.session_id,self.acceptance_binding)
            validate_binding(self.acceptance_binding,self.scope)
            binding_require(self.acceptance_mode==self.acceptance_binding['semantic_acceptance_mode'] and
                            (not strict_selected(self.acceptance_binding) or type(self.acceptance.admit) is TrustedAdmissionAdapter),
                            'ADMISSION','FORMAL_ADAPTER_MISSING')
        turn = self.store.begin_turn(self.handle, text, idempotency_key)
        tid = turn['turn_id']
        if turn['status'] == 'DISPLAYED':
            # A process can die after display acknowledgement but before the
            # observation commit. Resume that internal step, never the API/display.
            saved = self.store.db.execute('SELECT * FROM provider_calls WHERE turn_id=?', (tid,)).fetchone()
            ensure(saved is not None and saved['batch_id'] == self.scope['batch_id'] and saved['slot_id'] == slot_id,
                   'Displayed turn belongs to another batch/slot')
            checked = self.store.db.execute('SELECT check_json FROM response_checks WHERE turn_id=?', (tid,)).fetchone()
            if checked is not None:
                self._record_events(tid, saved['call_id'], json.loads(saved['context_json']), json.loads(checked[0]))
            visible = self.store.conversation_turn(self.handle, tid, purpose='display')
            return {'turn_id': tid, 'status': 'ALREADY_DISPLAYED', 'text': visible['assistant_text'],
                    'provider_resubmitted': False, 'displayed_now': False}
        delivery = self.store.db.execute('SELECT status FROM display_journal WHERE turn_id=?', (tid,)).fetchone()
        if delivery and delivery[0] == 'DISPLAY_INTENT':
            return {'turn_id': tid, 'status': 'DELIVERY_STATUS_UNKNOWN', 'displayed_now': False,
                    'provider_resubmitted': False, 'text': None}
        call_row = self.store.db.execute('SELECT * FROM provider_calls WHERE turn_id=?', (tid,)).fetchone()
        if call_row:
            # Always use the exact submitted context when inspecting captured output.
            ensure(call_row['batch_id'] == self.scope['batch_id'] and call_row['slot_id'] == slot_id,
                   'Idempotency key belongs to another batch or slot')
            context = json.loads(call_row['context_json'])
        else:
            context = self.build_request_context(tid)
            with self.store.transaction():
                self.journal._transition(tid, 'CONTEXT_BUILT', {'route': context['route'], 'prompt_bytes': context['prompt_bytes']})
        kwargs = {}
        if transport is not None:
            kwargs['transport'] = transport
        if credential_reader is not None:
            kwargs['credential_reader'] = credential_reader
        call = self.journal.call(self.handle, tid, self.scope['batch_id'], slot_id, context, **kwargs)
        if call['status'] != 'RESPONSE_CAPTURED':
            return {'turn_id': tid, 'status': call['status'], 'call_id': call['call_id'],
                    'text': None, 'displayed_now': False, 'error_category': call.get('error_category')}
        turn = self.store.get_turn(self.handle, tid)
        if self.acceptance_mode == 'BOUNDED':
            from accepted_output import load_record,persist
            record=load_record(self.store.db,tid)
            if record is None:
                raw=self.store.db.execute('SELECT raw_response FROM provider_calls WHERE turn_id=?',(tid,)).fetchone()[0]
                selected=self.acceptance.accept_display(handle=self.handle,turn=turn,context=context,raw_provider_response=bytes(raw))
                record=persist(self.store,self.handle,tid,bytes(raw),selected)
            turn=dict(turn,assistant_text=record['candidate_visible_text'])
        if self.acceptance_mode == 'TRUSTED':
            from accepted_output import load_record, persist
            if load_record(self.store.db, tid) is None:
                raw = self.store.db.execute('SELECT raw_response FROM provider_calls WHERE turn_id=?', (tid,)).fetchone()[0]
                if self.acceptance_binding is not None:
                    from semantic_binding import layer, require_session
                    require_session(self.store.db,self.handle.session_id,self.acceptance_binding)
                    with layer('VALIDATOR'):
                        accepted = self.acceptance.accept(handle=self.handle, turn=turn, context=context,
                                                          raw_provider_response=bytes(raw))
                    with layer('PERSISTENCE'):
                        persist(self.store, self.handle, tid, bytes(raw), accepted)
                else:
                    accepted = self.acceptance.accept(handle=self.handle, turn=turn, context=context,
                                                      raw_provider_response=bytes(raw))
                    persist(self.store, self.handle, tid, bytes(raw), accepted)
        if self.acceptance_mode != 'BOUNDED':
            turn = self.store.conversation_turn(self.handle, tid, purpose='display')
        check = check_response(turn['assistant_text'], context)
        with self.store.transaction():
            old = self.store.db.execute('SELECT check_json FROM response_checks WHERE turn_id=?', (tid,)).fetchone()
            if old:
                check = json.loads(old[0])
            else:
                self.store.db.execute('INSERT INTO response_checks VALUES(?,?,?)',
                                      (tid, utc_now(), canonical(check).decode('utf-8')))
                self.journal._transition(tid, 'RESPONSE_CHECKED', check)
        if not check['display_allowed']:
            with self.store.transaction():
                self.store.db.execute('UPDATE call_batches SET stopped=1 WHERE batch_id=?', (self.scope['batch_id'],))
                self.journal._transition(tid, 'RESPONSE_WITHHELD', {'finding_codes': [f['code'] for f in check['findings']]})
            return {'turn_id': tid, 'status': 'RESPONSE_WITHHELD', 'text': None,
                    'call_id': call['call_id'], 'check': check, 'displayed_now': False}
        if display is None:
            return {'turn_id': tid, 'status': 'READY_TO_DISPLAY', 'text': turn['assistant_text'],
                    'call_id': call['call_id'], 'check': check, 'displayed_now': False}
        # Obtain a unique durable delivery intent before touching the terminal.
        with self.store.transaction():
            existing = self.store.db.execute('SELECT status FROM display_journal WHERE turn_id=?', (tid,)).fetchone()
            ensure(existing is None, 'Delivery already attempted; inspect rather than automatically repeat')
            self.store.db.execute('INSERT INTO display_journal VALUES(?,?,?,NULL)', (tid, 'DISPLAY_INTENT', utc_now()))
            self.journal._transition(tid, 'DISPLAY_INTENT', {'delivery_guarantee': 'AMBIGUOUS_ON_CRASH'})
        display(turn['assistant_text'])
        with self.store.transaction():
            now = utc_now()
            self.store.db.execute("UPDATE turns SET status='DISPLAYED',display_at_utc=? WHERE turn_id=?", (now, tid))
            self.store.db.execute("UPDATE display_journal SET status='DISPLAY_ACK',ack_at_utc=? WHERE turn_id=?", (now, tid))
            if self.acceptance_mode=='BOUNDED':
                from accepted_output import acknowledge_display
                acknowledge_display(self.store,self.handle,tid,turn['assistant_text'],now)
            self.journal._transition(tid, 'DISPLAYED', {'sink_acknowledged': True, 'human_read_receipt': False})
        event_result = self._record_events(tid, call['call_id'], context, check)
        return {'turn_id': tid, 'status': 'DISPLAYED', 'text': turn['assistant_text'],
                'call_id': call['call_id'], 'check': check, 'events': event_result, 'displayed_now': True}

    def _record_events(self, tid: str, call_id: str, context: dict, check: dict) -> dict:
        previous = self.store.db.execute('SELECT trace_json FROM chat_traces WHERE turn_id=?', (tid,)).fetchone()
        if previous is not None:
            return json.loads(previous[0])['events']
        event_result = self.admission.observe_turn(self.handle, tid) if self.admission is not None else {
            'status': 'NO_EVENT_AUTHORITY_INSTALLED', 'runtime_events_committed': 0}
        runtime = getattr(self.admission, 'runtime', None)
        trace = {'turn_id': tid, 'call_id': call_id, 'context': context, 'check': check,
                 'state_before': context.get('runtime_state_before'),
                 'state_after': runtime.snapshot(self.handle) if runtime is not None else None,
                 'events': event_result, 'displayed': True, 'model_text_is_event_proof': False}
        with self.store.transaction():
            self.store.db.execute('INSERT OR IGNORE INTO chat_traces VALUES(?,?)', (tid, canonical(trace).decode('utf-8')))
            self.journal._transition(tid, 'EVENT_CANDIDATES_RECORDED', event_result)
        return event_result

    def inspect_last(self) -> dict[str, Any] | None:
        """Explicit local inspection; never resends or marks a delivery as proven."""
        rows = self.store.conversation_recent(self.handle, 1, purpose='audit')
        return rows[0] if rows else None
