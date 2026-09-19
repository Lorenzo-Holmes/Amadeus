"""Freeze-bound, one-shot local Provider2 validation. Never opens a socket.

Only authored short/long fixtures are permitted. No benchmark selection,
credentials, semantic scoring, readiness or paid-provider execution is exposed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'persona_core/operational_runtime_v1'))
from transcript_store import TranscriptStore, create_sandbox, safe_root, ensure, utc_now
from provider import ProviderJournal, canonical
from provider_fixture import make_scope


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open('xb') as stream: stream.write(canonical(value) + b'\n')


def run_local(destination, source_manifest):
    destination = safe_root(destination); source_manifest = Path(source_manifest).resolve()
    ensure(source_manifest.is_relative_to(ROOT), 'SOURCE_MANIFEST_OUTSIDE_WORKSPACE')
    manifest = json.loads(source_manifest.read_text(encoding='utf-8'))
    ensure(manifest.get('offline_integration_passed') is True and manifest.get('core_status') == 'FROZEN_FOR_VALIDATION', 'OFFLINE_FREEZE_REQUIRED')
    ensure(manifest.get('independent_validation_only') is True and manifest.get('semantic_acceptance') is False, 'INDEPENDENT_FREEZE_REQUIRED')
    files = manifest.get('files')
    ensure(isinstance(files, dict) and files, 'SOURCE_FILES_REQUIRED')
    for name, expected in files.items():
        path = (ROOT/name).resolve()
        ensure(path.is_relative_to(ROOT) and path.is_file() and sha(path) == expected, 'FROZEN_SOURCE_CHANGED')
    prefix = 'persona_core/operational_runtime_v1/'
    ensure({name for name in files if name.startswith(prefix) and name.endswith('.py')} ==
           {prefix+p.name for p in (ROOT/prefix).glob('*.py')}, 'SOURCE_MEMBERSHIP_CHANGED')
    # Exclusive directory creation permanently consumes this validation scope.
    destination.mkdir(parents=True, exist_ok=False)
    binding = {'source_manifest_sha256': sha(source_manifest), 'freeze_id': manifest['freeze_id'],
               'provider_id': 'local_fixture', 'cases': ['short', 'long'], 'at_utc': utc_now(),
               'automatic_paid_retries': 0, 'remote_requests': 0, 'semantic_acceptance': False}
    write_new(destination/'VALIDATION_INTENT.json', binding)
    results = []
    for case in binding['cases']:
        scope = make_scope('PROVIDER2_' + destination.name + '_' + case.upper(), case=case)
        runtime = create_sandbox(destination/case/'runtime')
        write_new(destination/case/'SCOPE.json', scope)
        store = TranscriptStore(runtime)
        try:
            journal = ProviderJournal(store); journal.register_batch(scope)
            slot = scope['slots'][0]
            handle = store.open_session(scope['principal_id'], slot['entity_label'], 'CHARACTER_SIMULATION')
            turn = store.begin_turn(handle, slot['user_text'], slot['id'])
            context = {'turn_id': turn['turn_id'], 'mode': handle.mode,
                       'messages': [{'role': 'user', 'content': slot['user_text']}]}
            call = journal.call(handle, turn['turn_id'], scope['batch_id'], slot['id'], context)
            results.append({'case': case, 'status': call['status'], 'generation_identity': call['provider_binding']['generation_identity'],
                            'summary': journal.summary(scope['batch_id'])})
            with store.transaction():
                store.db.execute('UPDATE call_batches SET stopped=1 WHERE batch_id=?', (scope['batch_id'],))
        finally: store.close()
        if call['status'] != 'RESPONSE_CAPTURED': break
    report = {**binding, 'completed_at_utc': utc_now(), 'results': results,
              'passed': len(results) == 2 and all(r['status'] == 'RESPONSE_CAPTURED' for r in results),
              'evidence_kind': 'DETERMINISTIC_LOCAL_FIXTURE_NOT_REMOTE_PROVIDER',
              'deepseek_recovered': False, 'g6_07_satisfied': False, 'billing_certified': False}
    write_new(destination/'VALIDATION_REPORT.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-manifest', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    result = run_local(args.destination, args.source_manifest)
    print(json.dumps({'passed': result['passed'], 'remote_requests': 0, 'semantic_acceptance': False,
                      'report': str(args.destination/'VALIDATION_REPORT.json')}))
    return 0 if result['passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
