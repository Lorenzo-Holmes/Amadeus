"""Exercise diagnostic idempotency and authority on copied authored test runs."""
from __future__ import annotations
import contextlib
import io
import json
import shutil
import sqlite3
import unittest
from datetime import datetime, timezone
import capacity_probe_r047 as probe
from provider import canonical

REAL = probe.REV
OUT = REAL / ('tests_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.root = OUT / self._testMethodName
        self.root.mkdir(parents=True)
        for name in ('EXECUTION_SCOPE.json', 'PREPARATION.json'):
            shutil.copy2(REAL / name, self.root / name)
        shutil.copytree(REAL / 'live', self.root / 'live')
        probe.REV, probe.LIVE = self.root, self.root / 'live'
        self.calls = []
    def tearDown(self):
        probe.REV, probe.LIVE = REAL, REAL / 'live'
    def transport(self, payload, key):
        request = json.loads(payload)
        self.calls.append(request)
        return 200, canonical({'model': 'deepseek-flash', 'choices': [{'finish_reason': 'stop', 'message': {'content': '这是具名的离线流程测试答复。'}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120}})
    def execute(self, transport=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return probe.execute(transport=transport or self.transport, credential_reader=lambda: 'AUTHORED_NOT_REAL_KEY')
    def db(self):
        return sqlite3.connect(self.root / 'live/runtime.sqlite3')
    def test_actual_saved_history_and_four_new_authored_slots(self):
        self.assertEqual(self.execute(), 0)
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(self.calls[0]['max_tokens'], 131072)
        self.assertEqual(self.calls[0]['reasoning_effort'], 'max')
        self.assertTrue(any(m['role'] == 'assistant' and m['content'] == '同意约定：三项控制清单' for m in self.calls[0]['messages']))
        with self.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM provider_calls WHERE batch_id=?', (probe.BATCH,)).fetchone()[0], 4)
            self.assertEqual(db.execute('SELECT DISTINCT capture_origin FROM provider_calls WHERE batch_id=?', (probe.BATCH,)).fetchall(), [('AUTHORED_PROVIDER_TEST_FIXTURE',)])
    def test_completed_diagnostic_does_not_resubmit(self):
        self.assertEqual(self.execute(), 0)
        self.assertEqual(self.execute(), 0)
        self.assertEqual(len(self.calls), 4)
    def test_unknown_submission_stops_remaining_without_erasing_intent(self):
        def timeout(payload, key):
            self.calls.append(payload)
            raise TimeoutError('AUTHORED_TRANSPORT_TIMEOUT')
        self.assertEqual(self.execute(timeout), 2)
        self.assertEqual(self.execute(), 2)
        self.assertEqual(len(self.calls), 1)
        with self.db() as db:
            self.assertEqual(db.execute('SELECT status FROM provider_calls WHERE batch_id=?', (probe.BATCH,)).fetchall(), [('SUBMITTED_STATUS_UNKNOWN',)])
    def test_original_stopped_batch_stays_stopped(self):
        self.assertEqual(self.execute(), 0)
        with self.db() as db:
            self.assertEqual(db.execute('SELECT stopped FROM call_batches WHERE batch_id<>?', (probe.BATCH,)).fetchall(), [(1,)])
            self.assertEqual(db.execute('SELECT count(*) FROM provider_calls WHERE batch_id<>?', (probe.BATCH,)).fetchone()[0], 27)
    def test_preexisting_driver_is_not_cleared(self):
        with self.db() as db:
            db.execute("INSERT INTO metadata(key,value) VALUES('r047_capacity_driver','UNRECONCILED_TEST_DRIVER')")
        self.assertEqual(self.execute(), 2)
        self.assertEqual(self.calls, [])
        with self.db() as db:
            self.assertEqual(db.execute("SELECT value FROM metadata WHERE key='r047_capacity_driver'").fetchone()[0], 'UNRECONCILED_TEST_DRIVER')
    def test_truncated_diagnostic_cannot_be_reclassified_as_success(self):
        def truncated(payload, key):
            self.calls.append(payload)
            return 200, canonical({'model': 'deepseek-flash',
                'choices': [{'finish_reason': 'length', 'message': {'content': ''}}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 131072, 'total_tokens': 131172,
                          'completion_tokens_details': {'reasoning_tokens': 131072}}})
        self.assertEqual(self.execute(truncated), 2)
        self.assertEqual(self.execute(), 2)
        self.assertEqual(len(self.calls), 1)
        with self.db() as db:
            row = db.execute('SELECT status,estimate_peak_micro_cny FROM provider_calls WHERE batch_id=?', (probe.BATCH,)).fetchone()
            self.assertEqual(row[0], 'RESPONSE_REJECTED')
            self.assertEqual(row[1], 100*3 + 131072*9)


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    original = probe.verify_parent()
    with (OUT / 'TESTS.log').open('x', encoding='utf-8') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProbeTests))
    unchanged = original == probe.verify_parent()
    report = {'tests': result.testsRun, 'passed': result.wasSuccessful() and unchanged,
        'failures': len(result.failures), 'errors': len(result.errors),
        'target_network_calls': 0, 'original_journal_unchanged': unchanged,
        'new_responses': 'AUTHORED_TEST_FIXTURES_ONLY', 'semantic_acceptance': False,
        'tested_sources': probe.common.source_bindings()}
    probe.dump(OUT / 'TESTS.json', report)
    print(json.dumps({'output': OUT.relative_to(probe.ROOT).as_posix(), **{k: report[k] for k in ('tests', 'passed', 'errors', 'target_network_calls')}}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
