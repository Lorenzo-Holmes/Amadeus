"""Offline safety tests for repair_04. No target provider calls."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import repair_revision_r047_v4 as wrapper
import execute_r047 as driver
from provider import canonical
from transcript_store import StoreGuard

ROOT = wrapper.ROOT
REAL_REV = wrapper.REV
OUT = REAL_REV / ('wrapper_tests_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}


def activate(rev):
    wrapper.REV = Path(rev)
    wrapper.LIVE = wrapper.REV / 'live'


def clone_config(destination):
    destination.mkdir(parents=True)
    for name in ['EXECUTION_SCOPE.json', 'REVISION.json', 'OFFICIAL_PREFLIGHT.json']:
        shutil.copy2(REAL_REV / name, destination / name)


ORIGINAL_OPEN_CHAT = driver.open_chat


def offline_chat(store, handle, scope):
    chat = ORIGINAL_OPEN_CHAT(store, handle, scope)
    actual_send = chat.send_text

    def transport(payload, key):
        body = json.loads(payload)
        with (wrapper.REV / 'OFFLINE_TRANSPORT_COUNT.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'model': body['model'], 'origin': 'AUTHORED_TEST_FIXTURE', 'pid': os.getpid()}) + '\n')
        returned_model = 'deepseek-flash' if body['model'] == 'deepseek-v4-flash' else body['model']
        return 200, canonical({
            'model': returned_model,
            'choices': [{'finish_reason': 'stop', 'message': {'content': 'repair_04 离线流程测试答复。'}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120},
        })

    def send(*args, **kwargs):
        return actual_send(*args, **kwargs, transport=transport,
                           credential_reader=lambda: 'AUTHORED_NOT_A_CREDENTIAL')

    chat.send_text = send
    return chat


def run_driver(phase):
    with patch.object(driver, 'open_chat', offline_chat):
        return wrapper.dispatch('execute', ['--phase', phase])


def db(rev):
    return sqlite3.connect(rev / 'live/runtime.sqlite3')


class Repair04WrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repair03_before = hashes(wrapper.PREVIOUS)
        cls.original_before = hashes(wrapper.original.LIVE)
        cls.base = OUT / 'prepared_base'
        clone_config(cls.base)
        activate(cls.base)
        with contextlib.redirect_stdout(io.StringIO()):
            wrapper.dispatch('prepare', [])

    @classmethod
    def tearDownClass(cls):
        activate(REAL_REV)

    def setUp(self):
        self.rev = OUT / self._testMethodName
        shutil.copytree(self.base, self.rev)
        activate(self.rev)

    def tearDown(self):
        activate(REAL_REV)

    def test_previous_terminal_signature(self):
        state = wrapper.verify_previous_terminal()
        self.assertEqual(state['status_counts'], {'RESPONSE_CAPTURED': 30, 'RESPONSE_REJECTED': 1})
        self.assertEqual(state['terminal_failure']['slot_id'], 'N05_S1')
        self.assertEqual(state['terminal_failure']['error_category'], 'PROVIDER_MODEL_MISMATCH')
        self.assertEqual(state['terminal_failure']['provider_model'], 'deepseek-flash')
        self.assertTrue(state['terminal_failure']['final_content_nonempty'])

    def test_prepare_zero_calls_and_repeat_refused(self):
        with db(self.rev) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM provider_calls').fetchone()[0], 0)
        before = hashes(self.rev)
        with self.assertRaises(StoreGuard):
            wrapper.dispatch('prepare', [])
        self.assertEqual(hashes(self.rev), before)

    def test_first_phase_is_idempotent(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_driver('first'), 0)
            self.assertEqual(run_driver('first'), 0)
        with db(self.rev) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM provider_calls').fetchone()[0], 3)

    def test_unknown_submission_stops_before_new_call(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_driver('first'), 0)
        count_path = self.rev / 'OFFLINE_TRANSPORT_COUNT.jsonl'
        before = len(count_path.read_text(encoding='utf-8').splitlines())
        with db(self.rev) as connection:
            connection.execute("UPDATE provider_calls SET status='SUBMITTED_STATUS_UNKNOWN' WHERE slot_id='N01_T1'")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_driver('first'), 2)
        after = len(count_path.read_text(encoding='utf-8').splitlines())
        self.assertEqual(before, after)

    def test_scope_mutation_rejected(self):
        scope = read(self.rev / 'EXECUTION_SCOPE.json')
        scope['slots'][0]['user_text'] = 'changed'
        (self.rev / 'EXECUTION_SCOPE.json').write_text(json.dumps(scope), encoding='utf-8')
        manifest = read(self.rev / 'REVISION.json')
        manifest['scope_file_sha256'] = wrapper.original.file_sha(self.rev / 'EXECUTION_SCOPE.json')
        (self.rev / 'REVISION.json').write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaises(StoreGuard):
            wrapper.load_revision()

    def test_prior_and_original_unchanged(self):
        self.assertEqual(hashes(wrapper.PREVIOUS), self.repair03_before)
        self.assertEqual(hashes(wrapper.original.LIVE), self.original_before)


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    with (OUT / 'TESTS.log').open('x', encoding='utf-8') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(Repair04WrapperTests))
    prior_ok = hashes(wrapper.PREVIOUS) == Repair04WrapperTests.repair03_before
    original_ok = hashes(wrapper.original.LIVE) == Repair04WrapperTests.original_before
    report = {
        'at_utc': datetime.now(timezone.utc).isoformat(),
        'tests': result.testsRun,
        'passed': result.wasSuccessful() and prior_ok and original_ok,
        'failures': len(result.failures),
        'errors': len(result.errors),
        'repair_03_unchanged': prior_ok,
        'original_r047_live_unchanged': original_ok,
        'target_network_calls': 0,
        'all_replies': 'AUTHORED_PROVIDER_TEST_FIXTURE',
        'semantic_acceptance_proven': False,
    }
    wrapper.dump(OUT / 'TESTS.json', report)
    print(json.dumps({'output': str(OUT.relative_to(ROOT)), 'tests': result.testsRun,
                      'passed': report['passed'], 'target_calls': 0}, ensure_ascii=False))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
