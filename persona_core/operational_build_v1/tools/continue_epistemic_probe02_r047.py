"""Continue only the remaining probe_02 slots after a clean first3 process.

This driver exists because the generic R047 rest gate historically hard-coded
N01_T1..T3. It does not alter that historical driver or the first3 evidence.
It is bound to the already-approved APCORE-R047-EPISTEMIC-DIAGNOSTIC-02
scope and submits only slots 4..26. Existing captured slots are recovered
idempotently; any rejection/UNKNOWN stops the batch with zero paid retry.
"""
from __future__ import annotations

import json
import os
import uuid

import epistemic_diagnostic_v2_r047 as probe
from capture_export import export_calls
from context_router import build_context
from operations import open_chat
from provider import ProviderJournal, canonical, digest
from transcript_store import TranscriptStore, ensure, utc_now

ROOT, REV, LIVE = probe.ROOT, probe.REV, probe.LIVE
BATCH = probe.BATCH


def verify_continuation_ready(store: TranscriptStore, scope: dict) -> dict:
    regression = probe.current_regression()
    auth = probe.common.read_json(REV / 'EXECUTION_AUTHORIZATION.json')
    ensure(auth.get('approved') is True and auth.get('batch_id') == BATCH
           and auth.get('guard_cny') == probe.GUARD_CNY,
           'probe_02 execution authorization is missing or changed')
    prepared = probe.common.read_json(REV / 'PREPARE_COMPLETE.json')
    ensure(prepared['fixture_preparation_sha256'] == probe.common.file_sha(LIVE / 'FIXTURE_PREPARATION.json'),
           'probe_02 preparation binding changed')
    official = probe.common.read_json(REV / 'OFFICIAL_PREFLIGHT.json')
    ensure(official.get('execution_recheck_complete') is True,
           'Current official provider recheck required')
    ensure(official['checked_date'] == probe.datetime.now(probe.timezone.utc).date().isoformat(),
           'Provider recheck date is stale')
    ensure(store.db.execute("SELECT count(*) FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchone()[0] == 0,
           'probe_02 has an unresolved provider request')
    batch = store.db.execute('SELECT stopped FROM call_batches WHERE batch_id=?', (BATCH,)).fetchone()
    ensure(batch is not None and batch[0] == 0, 'probe_02 batch is stopped')
    first_ids = [s['id'] for s in scope['slots'][:3]]
    rows = store.db.execute(
        'SELECT p.slot_id,p.status,t.status FROM provider_calls p JOIN turns t USING(turn_id) '
        'WHERE p.batch_id=? AND p.slot_id IN (?,?,?)', (BATCH, *first_ids)).fetchall()
    ensure(len(rows) == 3 and {r[0] for r in rows} == set(first_ids)
           and all(r[1] == 'RESPONSE_CAPTURED' and r[2] == 'DISPLAYED' for r in rows),
           'probe_02 first3 are not cleanly captured/displayed')
    first_runs = [probe.common.read_json(p) for p in (LIVE / 'execution_runs').glob('*/EXECUTION.json')]
    ensure(any(r.get('phase') == 'first' and r.get('status') == 'PHASE_COMPLETE'
               and r.get('exit_code') == 0 for r in first_runs),
           'genuine first3 process completion evidence missing')
    return {'regression': regression, 'first_slot_ids': first_ids}


def main() -> int:
    scope, _, _, frozen = probe.load()
    store = TranscriptStore(LIVE)
    run_id = 'run_' + uuid.uuid4().hex
    out = LIVE / 'execution_runs' / run_id
    out.mkdir(parents=True, exist_ok=False)
    acquired = False
    report = {'run_id': run_id, 'phase': 'probe02_rest', 'pid': os.getpid(),
              'started_at_utc': utc_now(), 'scope_sha256': frozen['scope_sha256'],
              'steps': [], 'automatic_paid_retries': 0, 'status': 'STARTING'}
    exit_code = 2
    try:
        report['readiness'] = verify_continuation_ready(store, scope)
        journal = ProviderJournal(store)
        journal.register_batch(scope)
        with store.transaction():
            existing = store.db.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone()
            ensure(existing is None or existing[0] == '', 'Another or interrupted driver is active')
            store.db.execute(
                "INSERT INTO metadata(key,value) VALUES('r047_active_driver',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (canonical({'run_id': run_id, 'pid': os.getpid(), 'started_at_utc': utc_now()}).decode('utf-8'),))
            acquired = True
        (out / 'START_INTENT.json').write_bytes(canonical(report))
        preparation = probe.common.read_json(LIVE / 'FIXTURE_PREPARATION.json')
        for slot in scope['slots'][3:]:
            handle = store.resume(scope['principal_id'], preparation['sessions'][slot['case_id']]['session_id'])
            chat = open_chat(store, handle, scope)
            consumed = store.db.execute(
                'SELECT p.*,t.status AS turn_status FROM provider_calls p JOIN turns t USING(turn_id) '
                'WHERE p.batch_id=? AND p.slot_id=?', (BATCH, slot['id'])).fetchone()
            key = BATCH + ':' + slot['id']
            if consumed:
                ensure(consumed['status'] == 'RESPONSE_CAPTURED' and consumed['turn_status'] == 'DISPLAYED',
                       'Consumed continuation slot is incomplete/unknown/rejected')
                recovered = chat.send_text(slot['user_text'], key, slot_id=slot['id'])
                ensure(recovered['status'] == 'ALREADY_DISPLAYED', 'Unexpected continuation recovery')
                report['steps'].append({'slot_id': slot['id'], 'status': 'PREVIOUSLY_DISPLAYED_NOT_RESUBMITTED',
                                        'call_id': consumed['call_id']})
                continue
            ensure(store.db.execute("SELECT count(*) FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchone()[0] == 0,
                   'Unresolved probe_02 request blocks next paid slot')
            turn = store.begin_turn(handle, slot['user_text'], key)
            preview = build_context(store, handle, turn['turn_id'], max_prompt_bytes=scope['max_input_bytes'],
                                    memory_provider=chat.memory_provider)
            serialized = json.dumps(preview['messages'], ensure_ascii=False)
            ensure('SABLE-COPPER-47' not in serialized and '书房三层' not in serialized,
                   'Foreign private material in continuation context')
            ensure('R047_PRIVATE_RUBRIC_NEVER_SEND_TO_TARGET' not in serialized,
                   'Private rubric in continuation context')
            step = {'slot_id': slot['id'], 'model': slot['model'], 'entity_id': handle.entity_id,
                    'session_id': handle.session_id, 'turn_id': turn['turn_id'],
                    'started_at_utc': utc_now(), 'preview_messages_sha256': digest(preview['messages'])}
            (out / (slot['id'] + '_INTENT.json')).write_bytes(canonical(step))
            print('SUBMIT ' + slot['id'] + ' ' + slot['model'], flush=True)

            def display(answer: str) -> None:
                with (out / (slot['id'] + '_DISPLAYED.txt')).open('x', encoding='utf-8') as stream:
                    stream.write(answer + '\n'); stream.flush(); os.fsync(stream.fileno())
                print('Amadeus：' + answer, flush=True)

            result = chat.send_text(slot['user_text'], key, slot_id=slot['id'], display=display)
            step.update(status=result['status'], finished_at_utc=utc_now(), call_id=result.get('call_id'),
                        response_check=result.get('check'), event_result=result.get('events'))
            report['steps'].append(step)
            export_calls(store, LIVE / 'captures')
            if result['status'] != 'DISPLAYED':
                report['status'] = 'STOPPED_WITH_PRESERVED_FAILURE_OR_UNKNOWN'
                (out / (slot['id'] + '_RESULT.json')).write_bytes(canonical(step))
                break
            call = store.db.execute('SELECT request_json,usage_json FROM provider_calls WHERE turn_id=?',
                                    (turn['turn_id'],)).fetchone()
            ensure(digest(json.loads(call['request_json'])['messages']) == step['preview_messages_sha256'],
                   'Submitted continuation context differs from preview')
            step['usage'] = json.loads(call['usage_json'])
            step['runtime_verification'] = chat.admission.runtime.verify()
            (out / (slot['id'] + '_RESULT.json')).write_bytes(canonical(step))
            summary = journal.summary(BATCH)
            print(json.dumps({'completed': slot['id'], 'captured': summary['calls_submitted'],
                              'peak_usage_estimate_cny': summary['peak_usage_estimate_cny'],
                              'billing_verified': False}, ensure_ascii=False), flush=True)
        else:
            report['status'] = 'PHASE_COMPLETE'; exit_code = 0
        report['provider_summary'] = journal.summary(BATCH)
    except Exception as exc:
        report['status'] = 'STOPPED_ERROR_RECONCILIATION_REQUIRED'
        report['error_category'] = type(exc).__name__
        print('STOPPED ' + type(exc).__name__ + '；保留日志，不自动重发。', flush=True)
    finally:
        report['finished_at_utc'] = utc_now(); report['exit_code'] = exit_code
        try:
            report['provider_summary'] = ProviderJournal(store).summary(BATCH)
            export_calls(store, LIVE / 'captures')
            if acquired:
                with store.transaction():
                    current = store.db.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone()
                    if current is not None and current[0] and json.loads(current[0])['run_id'] == run_id:
                        store.db.execute("UPDATE metadata SET value='' WHERE key='r047_active_driver'")
        finally:
            (out / 'EXECUTION.json').write_bytes(canonical(report)); store.close()
            print(json.dumps({'run': str(out.relative_to(ROOT)), 'status': report['status'],
                              'exit_code': exit_code}), flush=True)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
