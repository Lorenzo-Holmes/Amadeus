"""Four fixed diagnostic turns after a documented output-capacity repair.

Copies the terminal repair_05 sandbox with its actual displayed history. Old
call IDs and the old stopped flag stay intact. Only four new, named slots may
be submitted under a six-yuan guard. This is diagnostic regression, not full
acceptance and not a resumption/retry inside the old logical batch.
"""
from __future__ import annotations
import argparse
import copy
import json
import os
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
import r047_execution_common as common
from provider import ProviderJournal, RATES, canonical, digest
from transcript_store import TranscriptStore, ensure
from operations import open_chat
from context_router import build_context
from capture_export import export_calls

ROOT, PLAN = common.ROOT, common.PLAN
PREVIOUS = PLAN / 'evidence/R047-03/repair_05'
REV = PLAN / 'evidence/R047-03/capacity_probe_01'
LIVE = REV / 'live'
BATCH = 'APCORE-R047-CAPACITY-PROBE-01'
AGGREGATE_GUARD = 250.5
SELECTED = ('N05_T3', 'N05_T4', 'N05_T5', 'N05_T6')


def dump(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def make_scope(parent):
    scope = copy.deepcopy(parent)
    scope.update(schema_version='apcore-provider-scope-3', batch_id=BATCH,
        capacity_policy_id='EXTENDED_MAX_REASONING_20260911',
        output_budget_includes_reasoning=True, automatic_capacity_escalation=False,
        purpose='Four-turn named diagnostic after repair_05 final-output budget exhaustion; no prior slot or failed batch is unlocked.',
        max_output_tokens=131072, request_timeout_seconds=1200, total_guard_cny=6,
        all_operations_r045_plus_r047_guard_cny=AGGREGATE_GUARD)
    scope['slots'] = [s for s in scope['slots'] if s['id'] in SELECTED]
    ensure(tuple(s['id'] for s in scope['slots']) == SELECTED, 'Diagnostic inputs differ from parent sequence')
    scope['target_call_counts'] = {'diagnostic_main_turns': 4, 'total': 4}
    scope['reserved_upper_micro_cny'] = sum((scope['max_input_bytes'] + scope['input_overhead_reserve_tokens']) * RATES[s['model']][0] +
        scope['max_output_tokens'] * RATES[s['model']][1] for s in scope['slots'])
    common.scope_check(scope)
    return scope


def verify_parent():
    path = PREVIOUS / 'live/runtime.sqlite3'
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        ensure(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'Parent integrity failure')
        ensure(dict(db.execute('SELECT status,count(*) FROM provider_calls GROUP BY status')) == {'RESPONSE_CAPTURED': 26, 'RESPONSE_REJECTED': 1}, 'Parent counts differ')
        ensure(db.execute('SELECT stopped FROM call_batches').fetchall() == [(1,)], 'Parent not stopped')
        ensure(db.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone() == ('',), 'Parent lease active')
        failed = db.execute("SELECT slot_id,finish_reason,error_category,usage_json FROM provider_calls WHERE status='RESPONSE_REJECTED'").fetchone()
        ensure(failed[:3] == ('N05_T3', 'length', 'TRUNCATED_OR_OTHER_FINISH'), 'Parent terminal failure differs')
        usage = json.loads(failed[3])
        ensure(usage['completion_tokens'] == usage['completion_tokens_details']['reasoning_tokens'] == 8192, 'Parent exhaustion signature differs')
        return common.file_sha(path)
    finally:
        db.close()


def load():
    parent = common.read_json(PREVIOUS / 'EXECUTION_SCOPE.json')
    scope = common.read_json(REV / 'EXECUTION_SCOPE.json')
    manifest = common.read_json(REV / 'PREPARATION.json')
    ensure(scope == make_scope(parent), 'Diagnostic scope differs from fixed parameter revision')
    ensure(common.file_sha(REV / 'EXECUTION_SCOPE.json') == manifest['scope_sha256'], 'Diagnostic file hash changed')
    ensure(common.file_sha(PREVIOUS / 'EXECUTION_SCOPE.json') == manifest['parent_scope_sha256'], 'Parent scope changed')
    return scope, manifest


def prepare():
    before = verify_parent()
    ensure(not REV.exists(), 'Diagnostic already exists; reconcile rather than recreate')
    REV.mkdir(parents=True)
    shutil.copytree(PREVIOUS / 'live', LIVE)
    scope = make_scope(common.read_json(PREVIOUS / 'EXECUTION_SCOPE.json'))
    dump(REV / 'EXECUTION_SCOPE.json', scope)
    store = TranscriptStore(LIVE)
    try:
        journal = ProviderJournal(store)
        journal.register_batch(scope)
        sessions = common.read_json(PREVIOUS / 'live/FIXTURE_PREPARATION.json')['sessions']
        handle = store.resume(scope['principal_id'], sessions['N05']['session_id'])
        ensure(store.db.execute("SELECT count(*) FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchone()[0] == 0, 'Copied journal has unknown submissions')
        ensure(store.db.execute('SELECT count(*) FROM provider_calls WHERE batch_id=?', (BATCH,)).fetchone()[0] == 0, 'Diagnostic has already submitted')
        earlier = store.db.execute("SELECT t.assistant_text FROM turns t JOIN provider_calls p USING(turn_id) WHERE p.slot_id='N05_T2' AND t.status='DISPLAYED'").fetchone()
        ensure(earlier is not None and earlier[0] == '同意约定：三项控制清单', 'Actual preceding agreement acknowledgement missing')
        preparation = {'at_utc': datetime.now(timezone.utc).isoformat(),
            'scope_sha256': common.file_sha(REV / 'EXECUTION_SCOPE.json'),
            'parent_scope_sha256': common.file_sha(PREVIOUS / 'EXECUTION_SCOPE.json'),
            'parent_journal_sha256': before,
            'session_id': handle.session_id, 'copied_call_count': 27,
            'copied_calls_are_not_new_billing_or_new_generation': True,
            'actual_prior_acknowledgement_verified': True, 'target_calls_at_preparation': 0,
            'fresh_diagnostic_slots': list(SELECTED),
            'tested_sources_required_before_execute': True,
            'sources': common.source_bindings(),
            'pricing_and_api_checked_date': '2026-09-11',
            'official_sources': ['https://api-docs.deepseek.com/api/create-chat-completion/', 'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/'],
            'documented_max_effort_default_output_tokens': 131072,
            'reasoning_is_not_displayed_as_final': True,
            'whole_probe_guard_cny': 6, 'aggregate_guard_cny': AGGREGATE_GUARD,
            'automatic_paid_retries': 0, 'full_acceptance_claim': False}
        dump(REV / 'PREPARATION.json', preparation)
    finally:
        store.close()
    ensure(verify_parent() == before, 'Preparing the diagnostic modified the parent journal')
    print(json.dumps({'prepared': REV.relative_to(ROOT).as_posix(), 'new_calls': 0,
                      'fixed_slots': 4, 'reserve_micro_cny': scope['reserved_upper_micro_cny'], 'guard_cny': 6}))


def execute(regression=None, *, transport=None, credential_reader=None):
    scope, preparation = load()
    common.verify_source_bindings(preparation['sources'])
    real = transport is None
    if real:
        ensure(regression is not None, 'A current regression report is required before paid diagnostics')
        tests = common.read_json(regression)
        ensure(tests['passed'] and tests['protected_history_and_production_unchanged'], 'Current regression did not pass')
        for path, expected in tests['sources'].items():
            ensure(common.file_sha(ROOT / path) == expected, 'Tested source changed: ' + path)
        ensure(preparation['pricing_and_api_checked_date'] == datetime.now(timezone.utc).date().isoformat(), 'Official contract must be rechecked on the actual execution date')
        verify_parent()
    run_id = 'capacity_' + uuid.uuid4().hex
    out = REV / 'execution_runs' / run_id
    out.mkdir(parents=True, exist_ok=False)
    report = {'run_id': run_id, 'pid': os.getpid(), 'at_utc': datetime.now(timezone.utc).isoformat(),
              'batch_id': BATCH, 'real_provider_transport': real, 'steps': [],
              'automatic_paid_retries': 0, 'status': 'STARTING', 'full_acceptance_claim': False}
    store, acquired, code = TranscriptStore(LIVE), False, 2
    try:
        with store.transaction():
            lease = store.db.execute("SELECT value FROM metadata WHERE key='r047_capacity_driver'").fetchone()
            ensure(lease is None or not lease[0], 'Another or stale diagnostic driver exists')
            ensure(store.db.execute("SELECT count(*) FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchone()[0] == 0, 'Unknown provider submission blocks diagnostics')
            ensure(store.db.execute('SELECT stopped FROM call_batches WHERE batch_id=?', (BATCH,)).fetchone()[0] == 0, 'Diagnostic batch stopped; no automatic retry')
            store.db.execute("INSERT INTO metadata(key,value) VALUES('r047_capacity_driver',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (run_id,))
            acquired = True
        handle = store.resume(scope['principal_id'], preparation['session_id'])
        chat = open_chat(store, handle, scope)
        for slot in scope['slots']:
            common.verify_source_bindings(preparation['sources'])
            existing = store.db.execute('SELECT p.status,t.status,p.call_id FROM provider_calls p JOIN turns t USING(turn_id) WHERE p.batch_id=? AND p.slot_id=?', (BATCH, slot['id'])).fetchone()
            if existing:
                ensure(existing[:2] == ('RESPONSE_CAPTURED', 'DISPLAYED'), 'Consumed diagnostic slot cannot be resent')
                report['steps'].append({'slot_id': slot['id'], 'status': 'PREVIOUSLY_DISPLAYED_NOT_RESUBMITTED', 'call_id': existing[2]})
                continue
            key = BATCH + ':' + slot['id']
            turn = store.begin_turn(handle, slot['user_text'], key)
            preview = build_context(store, handle, turn['turn_id'], memory_provider=chat.memory_provider, max_prompt_bytes=scope['max_input_bytes'])
            serialized = json.dumps(preview['messages'], ensure_ascii=False)
            ensure('R047_PRIVATE_RUBRIC_NEVER_SEND_TO_TARGET' not in serialized and 'private_expectations' not in serialized, 'Private rubric in diagnostic prompt')
            ensure('SABLE-COPPER-47' not in serialized and '书房三层' not in serialized, 'Foreign entity private fixture leaked')
            print('SUBMIT_DIAGNOSTIC ' + slot['id'], flush=True)
            def display(answer):
                with (out / (slot['id'] + '_DISPLAYED.txt')).open('x', encoding='utf-8') as stream:
                    stream.write(answer + '\n'); stream.flush(); os.fsync(stream.fileno())
                print('Amadeus：' + answer, flush=True)
            options = {'transport': transport, 'credential_reader': credential_reader} if not real else {}
            result = chat.send_text(slot['user_text'], key, slot_id=slot['id'], display=display, **options)
            report['steps'].append({k: result.get(k) for k in ('turn_id', 'status', 'call_id', 'error_category')} | {'slot_id': slot['id']})
            export_calls(store, LIVE / 'captures')
            if result['status'] != 'DISPLAYED':
                report['status'] = 'STOPPED_WITH_PRESERVED_FAILURE_OR_UNKNOWN'
                break
        else:
            report['status'], code = 'DIAGNOSTIC_CAPTURE_COMPLETE', 0
    except Exception as error:
        report.update(status='STOPPED_RECONCILIATION_REQUIRED', error_type=type(error).__name__)
    finally:
        report['provider_summary'] = ProviderJournal(store).summary(BATCH)
        report['exit_code'] = code
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        if acquired:
            with store.transaction():
                store.db.execute("UPDATE metadata SET value='' WHERE key='r047_capacity_driver' AND value=?", (run_id,))
        store.close()
        dump(out / 'EXECUTION.json', report)
        print(json.dumps({'output': out.relative_to(ROOT).as_posix(), 'status': report['status'], 'exit_code': code,
                          'calls': report['provider_summary']['calls_submitted'], 'estimate_cny': report['provider_summary']['peak_usage_estimate_cny']}, ensure_ascii=False), flush=True)
    return code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'execute'])
    parser.add_argument('--regression', type=Path)
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    if args.action == 'prepare':
        prepare(); return 0
    return execute(args.regression)


if __name__ == '__main__':
    raise SystemExit(main())
