"""Real child-process wire tests; network is replaced and socket calls denied."""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import test_provider_capacity_r047 as capacity
import provider

ROOT, CODE, OUT = capacity.helpers.ROOT, capacity.helpers.CODE, capacity.OUT

CHILD = r'''
import json,sys
sys.path.insert(0,sys.argv[1])
def audit(event,args):
    if event.startswith('socket.'):
        raise AssertionError('NETWORK_FORBIDDEN_IN_WORKER_TEST')
sys.addaudithook(audit)
import provider_http_worker as worker
def transport(payload,key,**kwargs):
    sys.stderr.write('AUTHORED_TRANSPORT_REACHED\n')
    if sys.argv[2]=='raise':
        raise TimeoutError('AUTHORED_NO_ACTUAL_HTTP')
    request=json.loads(payload)
    answer='具名无网子进程测试答复。'
    if sys.argv[2]=='marker_answer':
        answer='AMADEUS_WORKER_NOT_SUBMITTED_V1'
    return 200, worker.canonical({'model':request['model'],
        'choices':[{'finish_reason':'stop','message':{'content':answer}}],
        'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120}})
worker.official_transport=transport
raise SystemExit(worker.main())
'''


def command(mode='success'):
    return [sys.executable, '-B', '-c', CHILD, str(CODE), mode]


def raw_child(frame, mode='success'):
    raw = frame if isinstance(frame, bytes) else provider.canonical(frame)
    return subprocess.run(command(mode), input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, timeout=8)


def frame(timeout):
    return {'payload': json.dumps({'model': 'deepseek-v4-pro'}), 'credential': 'AUTHORED_SENSITIVE_VALUE_NOT_A_KEY', 'timeout_seconds': timeout}


class WorkerTests(unittest.TestCase):
    setUp, tearDown = capacity.CapacityTests.setUp, capacity.CapacityTests.tearDown
    def journal_with_worker(self, timeout, mode='success'):
        def transport(payload, key):
            self.requests.append(payload)
            with patch.object(provider, '_worker_command', lambda: command(mode)):
                return provider.bounded_worker_transport(payload, key, timeout)
        return self.j.call(self.h, self.t['turn_id'], self.scope['batch_id'], 'one', self.context,
                           transport=transport, credential_reader=lambda: 'AUTHORED_NOT_REAL_KEY')
    def test_1200_second_host_contract_reaches_real_worker_transport(self):
        result = raw_child(frame(1200))
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.startswith(b'200\n'))
        self.assertEqual(result.stderr.count(b'AUTHORED_TRANSPORT_REACHED'), 1)
    def test_legacy_240_second_wire_remains_valid(self):
        result = raw_child(frame(240))
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.startswith(b'200\n'))
    def test_invalid_timeout_has_bound_receipt_before_transport(self):
        value = frame(1201)
        raw = provider.canonical(value)
        result = raw_child(raw)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(b'AUTHORED_TRANSPORT_REACHED', result.stderr)
        receipt = json.loads(result.stdout[len(provider.WORKER_LOCAL_REJECTION_HEADER):])
        self.assertFalse(receipt['network_attempted'])
        self.assertEqual(receipt['stage'], 'INPUT_VALIDATION')
        self.assertEqual(receipt['frame_sha256'], hashlib.sha256(raw).hexdigest())
    def test_boolean_timeout_is_not_accepted_as_one_second(self):
        result = raw_child(frame(True))
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(b'AUTHORED_TRANSPORT_REACHED', result.stderr)
    def test_nonfinite_timeout_rejected_in_actual_child(self):
        raw = json.dumps(frame(float('inf'))).encode('utf-8')
        result = raw_child(raw)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stdout.startswith(provider.WORKER_LOCAL_REJECTION_HEADER))
    def test_missing_fields_do_not_reach_transport(self):
        result = raw_child({'payload': '{}', 'credential': 'AUTHORED'})
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(b'AUTHORED_TRANSPORT_REACHED', result.stderr)
    def test_receipt_does_not_echo_payload_or_credential(self):
        value = frame(1201)
        value['payload'] = 'AUTHORED_PRIVATE_PAYLOAD'
        result = raw_child(value)
        self.assertNotIn(value['payload'].encode(), result.stdout + result.stderr)
        self.assertNotIn(value['credential'].encode(), result.stdout + result.stderr)
    def test_verified_local_rejection_is_zero_cost_but_stops_slot(self):
        result = self.journal_with_worker(1201)
        self.assertEqual(result['status'], 'LOCAL_REJECTED_BEFORE_NETWORK')
        self.assertEqual(result['estimate_peak_micro_cny'], 0)
        self.assertEqual(self.s.db.execute('SELECT stopped FROM call_batches').fetchone()[0], 1)
        self.assertIsNone(self.s.get_turn(self.h, self.t['turn_id'])['assistant_text'])
    def test_local_rejection_remains_nonretryable(self):
        first = self.journal_with_worker(1201)
        second = self.journal_with_worker(1200)
        self.assertEqual(first['call_id'], second['call_id'])
        self.assertEqual(second['status'], 'LOCAL_REJECTED_BEFORE_NETWORK')
        self.assertEqual(len(self.requests), 1)
    def test_failure_after_transport_is_still_unknown(self):
        result = self.journal_with_worker(1200, 'raise')
        self.assertEqual(result['status'], 'SUBMITTED_STATUS_UNKNOWN')
        self.assertIsNone(result['estimate_peak_micro_cny'])
        self.assertGreater(result['reserve_micro_cny'], 0)
        self.assertEqual(result['error_category'], 'PROVIDER_WORKER_REMOTE_OUTCOME_UNKNOWN/TimeoutError')
        trace = self.s.db.execute("SELECT detail_json FROM turn_lifecycle WHERE turn_id=? AND state='SUBMITTED_STATUS_UNKNOWN' ORDER BY seq DESC LIMIT 1",
                                  (self.t['turn_id'],)).fetchone()
        detail = json.loads(trace[0])
        self.assertTrue(detail['network_phase_entered'])
        self.assertFalse(detail['remote_outcome_known'])
        self.assertEqual(detail['child_error_class'], 'TimeoutError')
    def test_full_host_journal_to_real_worker_wiring_at_1200(self):
        result = self.journal_with_worker(1200)
        self.assertEqual(result['status'], 'RESPONSE_CAPTURED')
        self.assertEqual(self.s.get_turn(self.h, self.t['turn_id'])['assistant_text'], '具名无网子进程测试答复。')
        self.assertEqual(self.s.db.execute('SELECT capture_origin FROM provider_calls').fetchone()[0], 'AUTHORED_PROVIDER_TEST_FIXTURE')
    def test_http_answer_cannot_impersonate_pre_network_receipt(self):
        result = self.journal_with_worker(1200, 'marker_answer')
        self.assertEqual(result['status'], 'RESPONSE_CAPTURED')
        self.assertGreater(result['estimate_peak_micro_cny'], 0)
    def test_forged_receipt_with_wrong_binding_is_not_trusted(self):
        script = "import sys,json;sys.stdin.buffer.read();sys.stdout.buffer.write(b'AMADEUS_WORKER_NOT_SUBMITTED_V1\\n'+json.dumps({'stage':'INPUT_VALIDATION','network_attempted':False,'frame_sha256':'wrong','error_class':'StoreGuard'}).encode());sys.exit(2)"
        with patch.object(provider, '_worker_command', lambda: [sys.executable, '-B', '-c', script]):
            with self.assertRaises(capacity.StoreGuard) as caught:
                provider.bounded_worker_transport(b'{}', 'AUTHORED', 2)
        self.assertNotIsInstance(caught.exception, provider.WorkerNotSubmitted)
    def test_receipt_claiming_network_attempt_is_not_trusted(self):
        script = "import sys,json,hashlib;raw=sys.stdin.buffer.read();sys.stdout.buffer.write(b'AMADEUS_WORKER_NOT_SUBMITTED_V1\\n'+json.dumps({'stage':'INPUT_VALIDATION','network_attempted':True,'frame_sha256':hashlib.sha256(raw).hexdigest(),'error_class':'StoreGuard'}).encode());sys.exit(2)"
        with patch.object(provider, '_worker_command', lambda: [sys.executable, '-B', '-c', script]):
            with self.assertRaises(capacity.StoreGuard) as caught:
                provider.bounded_worker_transport(b'{}', 'AUTHORED', 2)
        self.assertNotIsInstance(caught.exception, provider.WorkerNotSubmitted)
    def test_remote_unknown_receipt_is_bound_and_nonretryable(self):
        first = self.journal_with_worker(1200, 'raise')
        second = self.journal_with_worker(1200, 'success')
        self.assertEqual(first['call_id'], second['call_id'])
        self.assertEqual(second['status'], 'SUBMITTED_STATUS_UNKNOWN')
        self.assertEqual(len(self.requests), 1)
    def test_forged_remote_unknown_receipt_with_wrong_binding_is_not_trusted(self):
        script = "import sys,json;sys.stdin.buffer.read();sys.stdout.buffer.write(b'AMADEUS_WORKER_REMOTE_OUTCOME_UNKNOWN_V1\\n'+json.dumps({'stage':'HTTP_CALL_OR_RESPONSE_READ','network_phase_entered':True,'remote_outcome_known':False,'frame_sha256':'wrong','error_class':'TimeoutError'}).encode());sys.exit(2)"
        with patch.object(provider, '_worker_command', lambda: [sys.executable, '-B', '-c', script]):
            with self.assertRaises(capacity.StoreGuard) as caught:
                provider.bounded_worker_transport(b'{}', 'AUTHORED', 2)
        self.assertNotIsInstance(caught.exception, provider.WorkerRemoteOutcomeUnknown)


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    files = list(CODE.glob('*.py')) + [Path(__file__)]
    with zipfile.ZipFile(OUT / 'TESTED_SOURCE.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.writestr(path.relative_to(ROOT).as_posix(), path.read_bytes())
    with (OUT / 'TESTS.log').open('x', encoding='utf-8') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(WorkerTests))
    report = {'tests': result.testsRun, 'passed': result.wasSuccessful(), 'failures': len(result.failures), 'errors': len(result.errors),
        'target_calls': 0, 'network_calls': 0, 'real_child_processes_used': True,
        'replies': 'AUTHORED_TEST_FIXTURES', 'semantic_acceptance': False,
        'tested_sources': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': capacity.file_sha(p)} for p in files]}
    (OUT / 'TESTS.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': OUT.relative_to(ROOT).as_posix(), **{k: report[k] for k in ('tests', 'passed', 'errors', 'target_calls')}}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
