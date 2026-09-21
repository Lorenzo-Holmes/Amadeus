"""Actual isolated wrapper paths with authored transport; zero paid calls."""
from __future__ import annotations
import contextlib
import copy
import io
import json
import shutil
import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import repair_revision_r047_v5 as wrapper
import execute_r047 as driver
from provider import canonical
from transcript_store import StoreGuard

REAL = wrapper.REV
OUT = REAL / ('wrapper_tests_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
OPEN_CHAT = driver.open_chat


def activate(root):
    wrapper.REV, wrapper.LIVE = root, root / 'live'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def offline_chat(store, handle, scope):
    chat = OPEN_CHAT(store, handle, scope)
    send = chat.send_text
    def transport(payload, key):
        request = json.loads(payload)
        with (wrapper.REV / 'OFFLINE_CALLS.jsonl').open('a', encoding='utf-8') as log:
            log.write(json.dumps({'model': request['model'], 'origin': 'AUTHORED_TEST_FIXTURE'}) + '\n')
        returned = 'deepseek-flash' if request['model'] == 'deepseek-v4-flash' else request['model']
        return 200, canonical({'model': returned,
            'choices': [{'finish_reason': 'stop', 'message': {'content': '这是具名离线驱动测试，不是实际人物答复。'}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120}})
    def wrapped(*args, **kwargs):
        return send(*args, **kwargs, transport=transport, credential_reader=lambda: 'AUTHORED_NOT_REAL_KEY')
    chat.send_text = wrapped
    return chat


def run_first():
    with patch.object(driver, 'open_chat', offline_chat), contextlib.redirect_stdout(io.StringIO()):
        return wrapper.dispatch('execute', ['--phase', 'first'])


def count(root):
    path = root / 'OFFLINE_CALLS.jsonl'
    return len(path.read_text(encoding='utf-8').splitlines()) if path.exists() else 0


class WrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = OUT / 'prepared'
        cls.base.mkdir(parents=True)
        for name in ('EXECUTION_SCOPE.json', 'REVISION.json', 'OFFICIAL_PREFLIGHT.json'):
            shutil.copy2(REAL / name, cls.base / name)
        activate(cls.base)
        with contextlib.redirect_stdout(io.StringIO()):
            wrapper.dispatch('prepare', [])
    def setUp(self):
        self.root = OUT / self._testMethodName
        shutil.copytree(self.base, self.root)
        activate(self.root)
    def tearDown(self):
        activate(REAL)
    def db(self):
        return sqlite3.connect(self.root / 'live/runtime.sqlite3')
    def test_preparation_zero_calls_and_repeated_prepare_denied(self):
        with self.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM provider_calls').fetchone()[0], 0)
        with self.assertRaises(StoreGuard):
            wrapper.dispatch('prepare', [])
        self.assertEqual(count(self.root), 0)
    def test_main_and_switch_roles_explicit_original_texts_unchanged(self):
        parent = wrapper.common.load_frozen()[0]
        scope = wrapper.load_revision()[0]
        self.assertEqual(len(scope['slots']), 82)
        self.assertEqual([s['user_text'] for s in scope['slots']], [s['user_text'] for s in parent['slots']])
        self.assertEqual(sum(s['model'] == 'deepseek-v4-flash' for s in scope['slots']), 76)
        self.assertTrue(all(s['model'] == 'deepseek-v4-pro' for s in scope['slots'] if '_S' in s['id']))
        self.assertEqual(scope['reserved_upper_micro_cny'], 17326080)
        self.assertEqual(scope['reasoning_effort'], 'max')
    def test_first_then_repeat_does_not_resend(self):
        self.assertEqual(run_first(), 0)
        self.assertEqual(run_first(), 0)
        self.assertEqual(count(self.root), 3)
        with self.db() as db:
            self.assertEqual(db.execute('SELECT DISTINCT capture_origin FROM provider_calls').fetchall(), [('AUTHORED_PROVIDER_TEST_FIXTURE',)])
    def test_unknown_blocks_transport_without_clearing_status(self):
        self.assertEqual(run_first(), 0)
        with self.db() as db:
            db.execute("UPDATE provider_calls SET status='SUBMITTED_STATUS_UNKNOWN' WHERE slot_id='N01_T1'")
        self.assertEqual(run_first(), 2)
        self.assertEqual(count(self.root), 3)
    def test_stopped_batch_is_not_unlocked(self):
        with self.db() as db:
            db.execute('UPDATE call_batches SET stopped=1')
        self.assertEqual(run_first(), 2)
        self.assertEqual(count(self.root), 0)
        with self.db() as db:
            self.assertEqual(db.execute('SELECT stopped FROM call_batches').fetchone()[0], 1)
    def test_rebound_scope_mutation_is_rejected(self):
        scope = read(self.root / 'EXECUTION_SCOPE.json')
        scope['slots'][0]['user_text'] = 'Changed user input'
        (self.root / 'EXECUTION_SCOPE.json').write_text(json.dumps(scope), encoding='utf-8')
        manifest = read(self.root / 'REVISION.json')
        manifest['scope_file_sha256'] = wrapper.common.file_sha(self.root / 'EXECUTION_SCOPE.json')
        (self.root / 'REVISION.json').write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaises(StoreGuard):
            wrapper.load_revision()
    def test_missing_official_check_is_not_silently_replaced(self):
        (self.root / 'OFFICIAL_PREFLIGHT.json').rename(self.root / 'REMOVED_FOR_TEST.json')
        with self.assertRaises(FileNotFoundError):
            run_first()
        self.assertEqual(count(self.root), 0)
    def test_authorless_fixture_is_not_real_capture_acceptance(self):
        self.assertEqual(run_first(), 0)
        with contextlib.redirect_stdout(io.StringIO()):
            wrapper.dispatch('audit', [])
        audit_path = next((self.root / 'evidence/R047-02').glob('audit_*/CAPTURE_AUDIT.json'))
        audit = read(audit_path)
        self.assertFalse(audit['complete_captures_and_delivery'])
        self.assertTrue(audit['known_development_regression'])
        self.assertFalse(audit['new_heldout_claim'])
        self.assertTrue(any(f['code'] == 'AUTHORED_CAPTURE_NOT_REAL_TARGET' for f in audit['binding_findings']))


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    previous_hash = wrapper.common.file_sha(wrapper.PREVIOUS / 'live/runtime.sqlite3')
    with (OUT / 'TESTS.log').open('x', encoding='utf-8') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(WrapperTests))
    unchanged = previous_hash == wrapper.common.file_sha(wrapper.PREVIOUS / 'live/runtime.sqlite3')
    report = {'tests': result.testsRun, 'passed': result.wasSuccessful() and unchanged,
        'failures': len(result.failures), 'errors': len(result.errors), 'previous_journal_unchanged': unchanged,
        'target_calls': 0, 'network_calls': 0, 'all_provider_data': 'AUTHORED_TEST_FIXTURE',
        'tested_sources': wrapper.common.source_bindings()}
    wrapper.dump(OUT / 'TESTS.json', report)
    print(json.dumps({'output': OUT.relative_to(wrapper.ROOT).as_posix(), **{k: report[k] for k in ('tests', 'passed', 'errors', 'target_calls')}}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
