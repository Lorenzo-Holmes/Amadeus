"""Bounded actual R047 execution, one logical batch, no paid retries.

Run first three slots, exit this actual process, then run the remaining slots
using the same persisted identities. This script never synthesizes assistant
history, never accepts user-supplied event authority, and never clears unknown
provider calls. A stale driver lease requires read-only reconciliation.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import uuid
from r047_execution_common import *
from transcript_store import TranscriptStore, utc_now, ensure
from provider import ProviderJournal, canonical, digest
from operations import open_chat
from context_router import build_context
from capture_export import export_calls

OFFICIAL_PREFLIGHT_PATH = PLAN / 'evidence/R047-02/OFFICIAL_PREFLIGHT_20260908.json'

def main() -> int:
    parser = argparse.ArgumentParser(description='Execute only the pinned R047 slots through the actual operations chat')
    parser.add_argument('--phase', required=True, choices=['first', 'rest'])
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='strict')
    scope, cases, fixture, frozen = load_frozen()
    check_required_gates()
    preparation = read_json(LIVE / 'FIXTURE_PREPARATION.json')
    preflight_path = ROOT / preparation['preflight_path']
    ensure(preflight_path.is_relative_to(ROOT), 'Preflight path outside project')
    preflight = read_json(preflight_path / 'PREFLIGHT.json')
    ensure(preflight['passed'] and preflight['target_calls'] == 0, 'Preflight not accepted')
    verify_source_bindings(preflight['tested_sources'])
    official = read_json(OFFICIAL_PREFLIGHT_PATH)
    ensure(official['frozen_scope_parameters_changed'] is False and official['peak_rates_cny_per_million_tokens'] == scope['peak_rates_cny_per_million_tokens'],
           'Official verification differs from pinned pricing contract')
    slots = scope['slots'][:3] if args.phase == 'first' else scope['slots'][3:]
    run_id = 'run_' + uuid.uuid4().hex
    out = LIVE / 'execution_runs' / run_id
    out.mkdir(parents=True, exist_ok=False)
    store = TranscriptStore(LIVE)
    acquired = False
    report = {'run_id': run_id, 'phase': args.phase, 'pid': os.getpid(), 'started_at_utc': utc_now(),
              'scope_sha256': frozen['scope_sha256'], 'preflight_sha256': file_sha(preflight_path / 'PREFLIGHT.json'),
              'steps': [], 'automatic_paid_retries': 0, 'status': 'STARTING'}
    exit_code = 2
    try:
        journal = ProviderJournal(store)
        journal.register_batch(scope)
        if args.phase == 'rest':
            first_ids = [slot['id'] for slot in scope['slots'][:3]]
            ensure(len(first_ids) == 3, 'Rest phase requires three fixed first slots')
            first_rows = store.db.execute(
                "SELECT p.slot_id,p.status,t.status FROM provider_calls p JOIN turns t USING(turn_id) "
                "WHERE p.batch_id=? AND p.slot_id IN (?,?,?)",
                (scope['batch_id'], *first_ids)).fetchall()
            ensure(len(first_rows) == 3 and {r[0] for r in first_rows} == set(first_ids)
                   and all(r[1] == 'RESPONSE_CAPTURED' and r[2] == 'DISPLAYED' for r in first_rows),
                   'Actual first process has not completed its three slots')
            prior_runs = [read_json(p) for p in (LIVE / 'execution_runs').glob('*/EXECUTION.json')]
            ensure(any(r['phase'] == 'first' and r['status'] == 'PHASE_COMPLETE' and r['pid'] != os.getpid() for r in prior_runs),
                   'Required genuine exit/reopen evidence missing')
        with store.transaction():
            existing = store.db.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone()
            ensure(existing is None or existing[0] == '', 'Another or interrupted driver is active; reconcile it before resuming')
            ensure(store.db.execute("SELECT count(*) FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchone()[0] == 0,
                   'Unknown provider submission; no additional paid call allowed')
            batch = store.db.execute('SELECT stopped FROM call_batches WHERE batch_id=?', (scope['batch_id'],)).fetchone()
            ensure(batch is not None and batch[0] == 0, 'Logical batch is stopped')
            store.db.execute("INSERT INTO metadata(key,value) VALUES('r047_active_driver',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                             (canonical({'run_id': run_id, 'pid': os.getpid(), 'started_at_utc': utc_now()}).decode('utf-8'),))
            acquired = True
        (out / 'START_INTENT.json').write_bytes(canonical(report))
        for slot in slots:
            verify_source_bindings(preflight['tested_sources'])
            handle = store.resume(scope['principal_id'], preparation['sessions'][slot['case_id']]['session_id'])
            chat = open_chat(store, handle, scope)
            consumed = store.db.execute('SELECT p.*,t.status AS turn_status FROM provider_calls p JOIN turns t USING(turn_id) WHERE p.batch_id=? AND p.slot_id=?',
                                        (scope['batch_id'], slot['id'])).fetchone()
            key = scope['batch_id'] + ':' + slot['id']
            if consumed:
                ensure(consumed['status'] == 'RESPONSE_CAPTURED' and consumed['turn_status'] == 'DISPLAYED',
                       'Consumed slot is incomplete, rejected or delivery-unknown; do not regenerate it')
                recovered = chat.send_text(slot['user_text'], key, slot_id=slot['id'])
                ensure(recovered['status'] == 'ALREADY_DISPLAYED', 'Unexpected consumed-slot recovery')
                report['steps'].append({'slot_id': slot['id'], 'status': 'PREVIOUSLY_DISPLAYED_NOT_RESUBMITTED', 'call_id': consumed['call_id']})
                continue
            turn = store.begin_turn(handle, slot['user_text'], key)
            preview = build_context(store, handle, turn['turn_id'], max_prompt_bytes=scope['max_input_bytes'], memory_provider=chat.memory_provider)
            prompt_text = json.dumps(preview['messages'], ensure_ascii=False)
            ensure('SABLE-COPPER-47' not in prompt_text and '书房三层' not in prompt_text, 'Foreign private material in target context')
            ensure('private_expectations' not in prompt_text and 'R047_PRIVATE_RUBRIC_NEVER_SEND_TO_TARGET' not in prompt_text,
                   'Private evaluation standard in target context')
            step = {'slot_id': slot['id'], 'model': slot['model'], 'entity_id': handle.entity_id, 'session_id': handle.session_id,
                    'turn_id': turn['turn_id'], 'started_at_utc': utc_now(), 'preview_messages_sha256': digest(preview['messages'])}
            (out / (slot['id'] + '_INTENT.json')).write_bytes(canonical(step))
            print('SUBMIT ' + slot['id'] + ' ' + slot['model'], flush=True)
            def display(answer):
                # This is a real text-output sink; raw reasoning is never displayed.
                with (out / (slot['id'] + '_DISPLAYED.txt')).open('x', encoding='utf-8') as f:
                    f.write(answer + '\n')
                    f.flush()
                    os.fsync(f.fileno())
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
            call = store.db.execute('SELECT request_json,usage_json FROM provider_calls WHERE turn_id=?', (turn['turn_id'],)).fetchone()
            ensure(digest(json.loads(call['request_json'])['messages']) == step['preview_messages_sha256'],
                   'Submitted context differs from ordinary preflight context')
            step['usage'] = json.loads(call['usage_json'])
            step['runtime_verification'] = chat.admission.runtime.verify()
            (out / (slot['id'] + '_RESULT.json')).write_bytes(canonical(step))
            summary = journal.summary(scope['batch_id'])
            print(json.dumps({'completed': slot['id'], 'captured': summary['calls_submitted'],
                              'peak_usage_estimate_cny': summary['peak_usage_estimate_cny'], 'billing_verified': False}, ensure_ascii=False), flush=True)
        else:
            report['status'] = 'PHASE_COMPLETE'
            exit_code = 0
        report['provider_summary'] = journal.summary(scope['batch_id'])
    except Exception as exc:
        report['status'] = 'STOPPED_ERROR_RECONCILIATION_REQUIRED'
        report['error_category'] = type(exc).__name__
        # Do not echo exception bodies or possible credential-bearing transport data.
        print('STOPPED ' + type(exc).__name__ + '；保留日志，不自动重发。', flush=True)
    finally:
        report['finished_at_utc'] = utc_now()
        report['exit_code'] = exit_code
        try:
            report['provider_summary'] = ProviderJournal(store).summary(scope['batch_id'])
            export_calls(store, LIVE / 'captures')
            if acquired:
                with store.transaction():
                    current = store.db.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone()
                    if current is not None and current[0] and json.loads(current[0])['run_id'] == run_id:
                        store.db.execute("UPDATE metadata SET value='' WHERE key='r047_active_driver'")
        finally:
            (out / 'EXECUTION.json').write_bytes(canonical(report))
            store.close()
            print(json.dumps({'run': str(out.relative_to(ROOT)), 'status': report['status'], 'exit_code': exit_code}), flush=True)
    return exit_code

if __name__ == '__main__':
    raise SystemExit(main())
