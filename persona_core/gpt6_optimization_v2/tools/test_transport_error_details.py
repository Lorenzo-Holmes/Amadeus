"""Offline-only real-worker tests; never send a provider request."""
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'persona_core/operational_build_v1/tools'))
import test_worker_contract_r047 as old
import provider

CHILD = old.CHILD.replace("raise TimeoutError('AUTHORED_NO_ACTUAL_HTTP')",
    "import urllib.error\n        raise urllib.error.URLError(TimeoutError(10060, 'AUTHORED_PRIVATE_ERROR_WITH_DUMMY_KEY'))")


class Tests(unittest.TestCase):
    setUp, tearDown = old.capacity.CapacityTests.setUp, old.capacity.CapacityTests.tearDown

    def command(self):
        return [sys.executable, '-B', '-c', CHILD, str(old.CODE), 'raise']

    def test_details_only_include_allowlisted_class_and_integer_numbers(self):
        secret = 'AUTHORED_PRIVATE_ERROR_WITH_DUMMY_KEY'
        value = provider.network_error_details(urllib.error.URLError(TimeoutError(10060, secret)))
        self.assertEqual(value, {'reason_class': 'TimeoutError', 'errno': 10060, 'winerror': None})
        self.assertNotIn(secret, json.dumps(value))
        arbitrary = type('AUTHORED_SECRET_CLASS', (Exception,), {})('private')
        arbitrary.errno = 'AUTHORED_SECRET_NUMBER'; arbitrary.winerror = True
        self.assertEqual(provider.network_error_details(arbitrary),
                         {'reason_class': 'OTHER', 'errno': None, 'winerror': None})

    def test_real_child_error_is_bound_but_does_not_leak_messages(self):
        import subprocess
        raw = provider.canonical(old.frame(10))
        result = subprocess.run(self.command(), input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, timeout=8)
        self.assertEqual(result.returncode, 2)
        receipt = json.loads(result.stdout[len(provider.WORKER_REMOTE_UNKNOWN_HEADER):])
        self.assertEqual(receipt['network_error']['errno'], 10060)
        self.assertEqual(receipt['network_error']['reason_class'], 'TimeoutError')
        self.assertFalse(receipt['remote_outcome_known'])
        self.assertNotIn(b'AUTHORED_PRIVATE_ERROR_WITH_DUMMY_KEY', result.stdout + result.stderr)
        self.assertNotIn(old.frame(10)['credential'].encode(), result.stdout + result.stderr)

    def test_parent_journal_keeps_unknown_reserve_and_never_replays(self):
        def transport(payload, key):
            self.requests.append(payload)
            with patch.object(provider, '_worker_command', self.command):
                return provider.bounded_worker_transport(payload, key, 10)
        kwargs = dict(transport=transport, credential_reader=lambda: 'AUTHOR_OFFLINE_DUMMY_KEY')
        first = self.j.call(self.h, self.t['turn_id'], self.scope['batch_id'], 'one', self.context, **kwargs)
        second = self.j.call(self.h, self.t['turn_id'], self.scope['batch_id'], 'one', self.context, **kwargs)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(first['call_id'], second['call_id'])
        self.assertEqual(first['status'], 'SUBMITTED_STATUS_UNKNOWN')
        self.assertIsNone(first['estimate_peak_micro_cny'])
        self.assertGreater(first['reserve_micro_cny'], 0)
        self.assertEqual(self.s.db.execute('SELECT stopped FROM call_batches').fetchone()[0], 1)
        detail = json.loads(self.s.db.execute("SELECT detail_json FROM turn_lifecycle WHERE turn_id=? AND state='SUBMITTED_STATUS_UNKNOWN' ORDER BY seq DESC LIMIT 1", (self.t['turn_id'],)).fetchone()[0])
        self.assertEqual(detail['network_error'], {'reason_class': 'TimeoutError', 'errno': 10060, 'winerror': None})
        self.assertFalse(detail['remote_outcome_known'])

    def test_invalid_or_unbounded_diagnostic_receipt_is_rejected(self):
        script = "import sys,json,hashlib;raw=sys.stdin.buffer.read();d={'stage':'HTTP_CALL_OR_RESPONSE_READ','network_phase_entered':True,'remote_outcome_known':False,'frame_sha256':hashlib.sha256(raw).hexdigest(),'error_class':'URLError','network_error':json.loads(sys.argv[1])};sys.stdout.buffer.write(b'AMADEUS_WORKER_REMOTE_OUTCOME_UNKNOWN_V1\\n'+json.dumps(d).encode());sys.exit(2)"
        for change in ({'reason_class':'OSError','errno':True,'winerror':None},
                       {'reason_class':'OSError','errno':2**65,'winerror':None},
                       {'reason_class':'PRIVATE_TEXT','errno':None,'winerror':None},
                       {'reason_class':'OSError','errno':None,'winerror':None,'message':'PRIVATE_TEXT'}):
            with self.subTest(change=change), patch.object(provider, '_worker_command',
                    lambda: [sys.executable, '-B', '-c', script, json.dumps(change)]):
                with self.assertRaises(old.capacity.StoreGuard) as caught:
                    provider.bounded_worker_transport(b'{}', 'AUTHOR_OFFLINE', 10)
                self.assertNotIsInstance(caught.exception, provider.WorkerRemoteOutcomeUnknown)

    def test_legacy_five_field_receipt_keeps_unknown_without_invented_details(self):
        script = "import sys,json,hashlib;raw=sys.stdin.buffer.read();d={'stage':'HTTP_CALL_OR_RESPONSE_READ','network_phase_entered':True,'remote_outcome_known':False,'frame_sha256':hashlib.sha256(raw).hexdigest(),'error_class':'URLError'};sys.stdout.buffer.write(b'AMADEUS_WORKER_REMOTE_OUTCOME_UNKNOWN_V1\\n'+json.dumps(d).encode());sys.exit(2)"
        with patch.object(provider, '_worker_command', lambda: [sys.executable, '-B', '-c', script]):
            with self.assertRaises(provider.WorkerRemoteOutcomeUnknown) as caught:
                provider.bounded_worker_transport(b'{}', 'AUTHOR_OFFLINE', 10)
        self.assertIsNone(caught.exception.network_error)
        self.assertEqual(caught.exception.reason, 'URLError')

    def test_plain_reason_text_is_not_serialized_and_os_numbers_are_bounded(self):
        value = provider.network_error_details(urllib.error.URLError('PRIVATE_URL_AND_TOKEN'))
        self.assertEqual(value, {'reason_class': 'URLError', 'errno': None, 'winerror': None})
        error = TimeoutError('PRIVATE_MESSAGE')
        error.errno = 2 ** 65
        error.winerror = 10060
        self.assertEqual(provider.network_error_details(error),
                         {'reason_class': 'TimeoutError', 'errno': None, 'winerror': 10060})


if __name__ == '__main__':
    unittest.main(verbosity=2)
