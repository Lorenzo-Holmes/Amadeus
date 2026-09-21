"""Preserve and reproduce a bound pre-HTTP worker rejection without network.

This does not rewrite UNKNOWN in the original journal or retry its slot. The
disposition is a local source-bound execution inference, not a remote receipt
or an independently checked billing statement.
"""
from __future__ import annotations
import ast
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import r047_execution_common as common

ROOT, PLAN = common.ROOT, common.PLAN
PROBE = PLAN / 'evidence/R047-03/capacity_probe_01'
EXPECTED_CALL = 'call_65df5a4dbb844432bdad8e63a8c68db5'


def dump(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def main():
    preparation = common.read_json(PROBE / 'PREPARATION.json')
    scope = common.read_json(PROBE / 'EXECUTION_SCOPE.json')
    worker = ROOT / 'persona_core/operational_runtime_v1/provider_http_worker.py'
    provider = ROOT / 'persona_core/operational_runtime_v1/provider.py'
    hashes = {r['path']: r['sha256'] for r in preparation['sources']}
    for path in (worker, provider):
        common.ensure(common.file_sha(path) == hashes[path.relative_to(ROOT).as_posix()], 'Source differs from the attempted execution binding')
    common.ensure(scope['request_timeout_seconds'] == 1200 and scope['schema_version'] == 'apcore-provider-scope-3', 'Unexpected attempted timeout contract')
    common.ensure(common.file_sha(PROBE / 'EXECUTION_SCOPE.json') == preparation['scope_sha256'], 'Attempt scope changed')
    db_path = PROBE / 'live/runtime.sqlite3'
    before = common.file_sha(db_path)
    db = sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        row = dict(db.execute('SELECT * FROM provider_calls WHERE call_id=?', (EXPECTED_CALL,)).fetchone())
        common.ensure(row['status'] == 'SUBMITTED_STATUS_UNKNOWN' and row['error_category'] == 'StoreGuard', 'Expected historical unknown row not found')
        common.ensure(row['batch_id'] == scope['batch_id'] and row['slot_id'] == 'N05_T3', 'Wrong diagnostic attempt')
        common.ensure(db.execute('SELECT stopped FROM call_batches WHERE batch_id=?', (scope['batch_id'],)).fetchone()[0] == 1, 'Old probe not stopped')
        common.ensure(db.execute("SELECT value FROM metadata WHERE key='r047_capacity_driver'").fetchone()[0] == '', 'Diagnostic driver remains active')
    finally:
        db.close()
    text = worker.read_text(encoding='utf-8')
    tree = ast.parse(text)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    body = function.body[0]
    common.ensure(isinstance(body, ast.Try), 'Worker main changed shape')
    validations = [node for node in body.body if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == 'ensure']
    timeout_guard = next(node for node in validations if 'Invalid worker timeout' in ast.get_source_segment(text, node))
    guard_source = ast.get_source_segment(text, timeout_guard)
    common.ensure("request['timeout_seconds'] <= 240" in guard_source, 'Expected pre-HTTP bound not present')
    operation = next(node for node in body.body if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == 'official_transport')
    common.ensure(timeout_guard.lineno < operation.lineno, 'Network call is not after the rejecting guard')
    out = PROBE / ('local_reconciliation_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(worker, out / 'BOUND_ORIGINAL_WORKER.py')
    shutil.copy2(provider, out / 'BOUND_ORIGINAL_PROVIDER.py')
    shutil.copy2(PROBE / 'EXECUTION_SCOPE.json', out / 'BOUND_SCOPE.json')
    # The real child executes the bound worker main, with any transport attempt
    # replaced by a sentinel and all socket operations denied independently.
    child = r'''
import importlib.util,io,json,sys
sys.path.insert(0,sys.argv[2])
frame=json.loads(sys.stdin.buffer.read())
network=[]
def audit(event,args):
    if event.startswith('socket.'):
        network.append(event)
        raise RuntimeError('NETWORK_DENIED_IN_OFFLINE_REPLAY')
sys.addaudithook(audit)
spec=importlib.util.spec_from_file_location('bound_worker',sys.argv[1])
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
attempts=[]
def forbidden_transport(*args,**kwargs):
    attempts.append('HTTP_WOULD_HAVE_BEEN_CALLED')
    raise RuntimeError('AUTHORED_NETWORK_SENTINEL')
module.official_transport=forbidden_transport
original_stdin=sys.stdin
original_stderr=sys.stderr
class Input:
    buffer=io.BytesIO(json.dumps(frame,ensure_ascii=False).encode('utf-8'))
sys.stdin=Input();sys.stderr=io.StringIO()
code=module.main();error=sys.stderr.getvalue()
sys.stdin=original_stdin;sys.stderr=original_stderr
print(json.dumps({'worker_exit_code':code,'error_class':error.strip(),'transport_attempts':len(attempts),'socket_events':network,'timeout_seconds':frame['timeout_seconds']}))
'''
    frame = {'payload': row['request_json'], 'credential': 'AUTHORED_OFFLINE_CREDENTIAL_NOT_USER_SECRET', 'timeout_seconds': 1200}
    replay = subprocess.run([sys.executable, '-B', '-c', child, str(out / 'BOUND_ORIGINAL_WORKER.py'), str(provider.parent)],
        input=json.dumps(frame, ensure_ascii=False).encode('utf-8'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, timeout=15)
    (out / 'REPLAY_STDOUT.log').write_bytes(replay.stdout)
    (out / 'REPLAY_STDERR.log').write_bytes(replay.stderr)
    common.ensure(replay.returncode == 0, 'Controlled replay process failed')
    result = json.loads(replay.stdout)
    common.ensure(result['worker_exit_code'] == 2 and result['error_class'] == 'StoreGuard' and result['transport_attempts'] == 0 and not result['socket_events'], 'Replay does not prove the expected pre-HTTP rejection')
    common.ensure(common.file_sha(db_path) == before, 'Historical journal changed during reconciliation')
    report = {'at_utc': datetime.now(timezone.utc).isoformat(), 'call_id': EXPECTED_CALL,
        'batch_id': scope['batch_id'], 'journal': db_path.relative_to(ROOT).as_posix(), 'journal_sha256': before,
        'original_journal_status': row['status'], 'original_status_rewritten': False,
        'disposition': 'LOCAL_PRE_HTTP_CONFIGURATION_REJECTION_DETERMINISTICALLY_RECONCILED',
        'basis': 'The attempt-bound provider sends timeout1200 to this exact worker; its unconditional <=240 input guard precedes the only HTTP call. The controlled real-process replay hits that guard before the transport sentinel.',
        'original_network_activity_inferred_from_bound_code_not_remote_receipt': True,
        'reviewer': 'CURRENT_SESSION_DEVELOPER_NONBLIND_LOCAL_EXECUTION_RECONCILIATION',
        'worker_bound_sha256': common.file_sha(out / 'BOUND_ORIGINAL_WORKER.py'),
        'provider_bound_sha256': common.file_sha(out / 'BOUND_ORIGINAL_PROVIDER.py'),
        'scope_sha256': preparation['scope_sha256'], 'request_sha256': row['request_sha256'],
        'guard_source': guard_source, 'guard_line': timeout_guard.lineno, 'http_call_line': operation.lineno,
        'controlled_process_result': result, 'controlled_process_exit_code': replay.returncode,
        'trust_limit': 'Assumes the trusted local host did not swap verified Python source between parent verification and child import; does not attest provider billing.',
        'old_batch_stays_stopped': True, 'old_slot_may_be_retried': False,
        'local_expected_provider_cost_cny': 0, 'billing_verified': False,
        'new_model_calls': 0, 'semantic_acceptance': False}
    dump(out / 'RECONCILIATION.json', report)
    print(json.dumps({'output': out.relative_to(ROOT).as_posix(), 'disposition': report['disposition'],
                      'original_status_rewritten': False, 'offline_transport_attempts': result['transport_attempts'], 'new_model_calls': 0}))


if __name__ == '__main__':
    main()
