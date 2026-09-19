"""Exactly one freeze-bound synthetic readiness through the formal ProviderJournal.

No evaluation inputs, automatic retries, resume, or replacement requests. All
wire data stays in the private journal. Run only after offline closeout/freeze.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import evaluation_runner as runner

POLICY = {'version': 'apcore-transport-lifecycle-1', 'connect_timeout_seconds': 15,
          'read_timeout_seconds': 120, 'worker_deadline_seconds': 595}
SYSTEM = 'This is a synthetic transport stress probe. Do not call tools or discuss real users or projects.'
USER = ('Produce exactly 600 numbered items. Each item must be one grammatical sentence of 12 to 20 '
        'English words about an invented neutral topic. Do not stop early and do not add a preface or conclusion.')


def runtime_root(root):
    return runner.EVIDENCE / ('G6_TRANSPORT_' + Path(root).name) / 'runtime'


def prepare(root, freeze_path, pricing_path):
    root, freeze_path = Path(root).resolve(), Path(freeze_path).resolve()
    runner.require(root.parent == runner.GOAL and root.name.startswith('formal_responses_readiness_'), 'READINESS_PATH')
    freeze = runner.read(freeze_path)
    runner.require(freeze.get('core_status') == 'FROZEN_FOR_VALIDATION'
                   and freeze.get('offline_integration_passed') is True, 'OFFLINE_FREEZE_REQUIRED')
    runner.require(freeze['files'] == runner.source_bindings(), 'FROZEN_SOURCE_CHANGED')
    runner.require(not root.exists(), 'READINESS_ALREADY_EXISTS_NO_REPEAT')
    # An exclusive binding outside the request directory prevents accidental
    # second readiness after renaming a directory or losing a shell session.
    binding = freeze_path.parent/'FORMAL_READINESS_BINDING.json'
    runner.require(not binding.exists(), 'ONE_FORMAL_READINESS_PER_FREEZE')
    price = runner.checked_pricing(pricing_path, False, ['deepseek-v4-pro'])
    scope = runner.build_scope(root.name, {'slots': [{'id': 'FORMAL_RESPONSES_1',
        'model': 'deepseek-v4-pro', 'entity_label': 'SYNTHETIC_TRANSPORT_ONLY', 'user_text': USER}]},
        price, 'deepseek-v4-pro', 'deepseek-flash', max_output_tokens=32768, guard_cny=1.15,
        timeout_seconds=600, transport_policy=POLICY, api_protocol='responses')
    scope['purpose'] = 'Exactly one formal synthetic Responses transport readiness; no semantic evaluation.'
    provider, transcript, *_ = runner.runtime_modules()
    runtime = transcript.safe_root(runtime_root(root))
    runner.require(not runtime.exists(), 'READINESS_RUNTIME_ALREADY_EXISTS')
    root.mkdir(exist_ok=False)
    runner.write_new(binding, {'root': runner.relative(root), 'source_manifest': runner.relative(freeze_path),
                             'source_manifest_sha256': runner.sha(freeze_path), 'scope_sha256': runner.value_sha(scope)})
    runner.write_new(root/'SCOPE.json', scope)
    runner.write_new(root/'BINDING.json', runner.read(binding))
    transcript.create_sandbox(runtime)
    store = transcript.TranscriptStore(runtime)
    try:
        provider.ProviderJournal(store).register_batch(scope)
        handle = store.open_session(scope['principal_id'], scope['slots'][0]['entity_label'], 'CHARACTER_SIMULATION')
        runner.write_new(root/'PREPARATION.json', {'session_id': handle.session_id, 'principal_id': handle.principal_id,
            'runtime': runner.relative(runtime),
            'scope_sha256': runner.sha(root/'SCOPE.json'), 'source_manifest_sha256': runner.sha(freeze_path),
            'synthetic_only': True, 'evaluation_inputs_used': False, 'generation_requests': 0})
    finally: store.close()
    return {'status': 'PREPARED', 'root': runner.relative(root), 'provider_requests': 0}


def run(root):
    root = Path(root).resolve()
    runner.require(root.parent == runner.GOAL and root.name.startswith('formal_responses_readiness_'), 'READINESS_PATH')
    binding = runner.read(root/'BINDING.json')
    freeze_path = runner.ROOT/binding['source_manifest']
    runner.require(runner.sha(freeze_path) == binding['source_manifest_sha256'], 'FREEZE_CHANGED')
    runner.require(runner.read(freeze_path.parent/'FORMAL_READINESS_BINDING.json') == binding, 'READINESS_BINDING_CHANGED')
    runner.require(runner.read(freeze_path)['files'] == runner.source_bindings(), 'FROZEN_SOURCE_CHANGED')
    scope = runner.read(root/'SCOPE.json'); preparation = runner.read(root/'PREPARATION.json')
    runner.require(runner.value_sha(scope) == binding['scope_sha256']
                   and runner.sha(root/'SCOPE.json') == preparation['scope_sha256'], 'READINESS_SCOPE_CHANGED')
    runner.require(scope['pricing_verified_date'] == runner.pricing_date(), 'PRICING_NOT_CURRENT')
    provider, transcript, *_ = runner.runtime_modules()
    import provider_transport
    runner.require(runner.ROOT/preparation['runtime'] == runtime_root(root), 'READINESS_RUNTIME_BINDING_CHANGED')
    store = transcript.TranscriptStore(runtime_root(root))
    journal = provider.ProviderJournal(store)
    try:
        runner.require(not (root/'SUBMISSION_INTENT.json').exists()
                       and store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0] == 0, 'READINESS_NOT_REPEATABLE')
        handle = store.resume(preparation['principal_id'], preparation['session_id'])
        slot = scope['slots'][0]
        turn = store.begin_turn(handle, slot['user_text'], 'ONE_FORMAL_RESPONSES_REQUEST')
        context = {'turn_id': turn['turn_id'], 'mode': handle.mode, 'messages': [
            {'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': slot['user_text']}]}
        runner.write_new(root/'SUBMISSION_INTENT.json', {'at_utc': runner.now(), 'turn_id': turn['turn_id'],
            'context_sha256': runner.value_sha(context), 'automatic_paid_retries': 0, 'maximum_requests': 1})
        started = time.monotonic()
        call = journal.call(handle, turn['turn_id'], scope['batch_id'], slot['id'], context)
        events = [json.loads(r[0]) for r in store.db.execute(
            "SELECT detail_json FROM turn_lifecycle WHERE turn_id=? AND state='TRANSPORT_LIFECYCLE' ORDER BY seq", (turn['turn_id'],))]
        names = {e['event'] for e in events}
        required = {'worker_started','request_write_complete','first_response_header','first_response_byte',
                    'first_token','provider_finish','worker_terminal','child_exit','parent_receipt'}
        if call['status'] == 'RESPONSE_CAPTURED':
            row = dict(store.db.execute('SELECT * FROM provider_calls WHERE call_id=?', (call['call_id'],)).fetchone())
            provider_transport.verify_responses_wire(store.db, row, scope)
        passed = (call['status'] == 'RESPONSE_CAPTURED' and required <= names
                  and runner.read(freeze_path)['files'] == runner.source_bindings())
        with store.transaction(): store.db.execute('UPDATE call_batches SET stopped=1 WHERE batch_id=?', (scope['batch_id'],))
        report = {'schema_version': 'g6-formal-responses-readiness-1', 'at_utc': runner.now(),
            'status': 'PASS' if passed else call['status'], 'readiness_passed': passed,
            'call': call, 'elapsed_seconds': round(time.monotonic()-started, 3), 'lifecycle': events,
            'lifecycle_complete': required <= names, 'spend': journal.summary(scope['batch_id']),
            'generation_requests': 1, 'automatic_paid_retries': 0, 'source_manifest': binding,
            'synthetic_only': True, 'semantic_acceptance': False, 'production_activated': False,
            'new_unknown_count': int(call['status'] == 'SUBMITTED_STATUS_UNKNOWN')}
        runner.write_new(root/'READINESS_REPORT.json', report)
        runner.write_new(root/'NO_REPLAY.json', {'old_batch_resume_allowed': False, 'resend_allowed': False,
            'retry_allowed': False, 'replacement_allowed': False, 'status': call['status'], 'call_id': call['call_id']})
        return {k: report[k] for k in ('status','readiness_passed','elapsed_seconds','generation_requests','new_unknown_count')}
    finally: store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare','run'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--freeze', type=Path)
    parser.add_argument('--pricing', type=Path)
    args = parser.parse_args()
    result = prepare(args.root, args.freeze, args.pricing) if args.command == 'prepare' else run(args.root)
    print(json.dumps(result))
    return 0 if result['status'] in ('PASS','PREPARED') else 2

if __name__ == '__main__': raise SystemExit(main())
