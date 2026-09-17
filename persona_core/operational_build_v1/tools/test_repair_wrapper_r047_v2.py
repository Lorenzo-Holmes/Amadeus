"""Offline safety tests for the second named R047 repair revision.

All provider replies in this module are explicit authored fixtures. No network
or target-model request is permitted. The preserved repair_01 tree must remain
byte-for-byte unchanged throughout the test run.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import sqlite3
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import repair_revision_r047_v2 as wrapper
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
        return 200, canonical({
            'model': body['model'],
            'choices': [{'finish_reason': 'stop', 'message': {'content': 'repair_02 离线流程测试答复。'}}],
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


def captured_count(rev):
    path = rev / 'OFFLINE_TRANSPORT_COUNT.jsonl'
    return len(path.read_text(encoding='utf-8').splitlines()) if path.exists() else 0


def db(rev):
    return sqlite3.connect(rev / 'live/runtime.sqlite3')


class Repair02WrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repair01_before = hashes(wrapper.PREVIOUS)
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

    def test_previous_terminal_signature_is_required(self):
        state = wrapper.verify_previous_terminal()
        self.assertTrue(state['batch_stopped'])
        self.assertEqual(state['status_counts'], {'RESPONSE_CAPTURED': 6, 'RESPONSE_REJECTED': 1})
        self.assertEqual(state['terminal_failure']['slot_id'], 'N02_T1')
        self.assertEqual(state['terminal_failure']['error_category'], 'EMPTY_RESPONSE')
        self.assertTrue(state['terminal_failure']['final_content_empty'])

    def test_prepare_has_zero_target_calls_and_cannot_repeat(self):
        with db(self.rev) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM provider_calls').fetchone()[0], 0)
            self.assertEqual(connection.execute('SELECT batch_id FROM call_batches').fetchone()[0], wrapper.BATCH)
        before = hashes(self.rev)
        with self.assertRaises(StoreGuard):
            wrapper.dispatch('prepare', [])
        self.assertEqual(hashes(self.rev), before)

    def test_first_driver_capture_then_same_phase_no_resend(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_driver('first'), 0)
            self.assertEqual(run_driver('first'), 0)
        self.assertEqual(captured_count(self.rev), 3)
        with db(self.rev) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM provider_calls').fetchone()[0], 3)

    def test_unknown_submission_blocks_before_new_transport(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_driver('first'), 0)
        with db(self.rev) as connection:
            connection.execute("UPDATE provider_calls SET status='SUBMITTED_STATUS_UNKNOWN' WHERE slot_id='N01_T1'")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_driver('first'), 2)
        self.assertEqual(captured_count(self.rev), 3)

    def test_stopped_batch_cannot_be_manually_resumed_by_driver(self):
        with db(self.rev) as connection:
            connection.execute('UPDATE call_batches SET stopped=1 WHERE batch_id=?', (wrapper.BATCH,))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_driver('first'), 2)
        self.assertEqual(captured_count(self.rev), 0)

    def test_scope_mutation_is_rejected_even_if_manifest_hash_is_rebound(self):
        scope = read(self.rev / 'EXECUTION_SCOPE.json')
        scope['slots'][0]['user_text'] = 'mutated fixed input'
        (self.rev / 'EXECUTION_SCOPE.json').write_text(json.dumps(scope), encoding='utf-8')
        manifest = read(self.rev / 'REVISION.json')
        manifest['scope_file_sha256'] = wrapper.original.file_sha(self.rev / 'EXECUTION_SCOPE.json')
        (self.rev / 'REVISION.json').write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaises(StoreGuard):
            wrapper.load_revision()

    def test_prior_and_original_live_trees_remain_unchanged(self):
        self.assertEqual(hashes(wrapper.PREVIOUS), self.repair01_before)
        self.assertEqual(hashes(wrapper.original.LIVE), self.original_before)


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    with (OUT / 'TESTS.log').open('x', encoding='utf-8') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(Repair02WrapperTests))
    unchanged_previous = hashes(wrapper.PREVIOUS) == Repair02WrapperTests.repair01_before
    unchanged_original = hashes(wrapper.original.LIVE) == Repair02WrapperTests.original_before
    report = {
        'at_utc': datetime.now(timezone.utc).isoformat(),
        'tests': result.testsRun,
        'passed': result.wasSuccessful() and unchanged_previous and unchanged_original,
        'failures': len(result.failures),
        'errors': len(result.errors),
        'repair_01_unchanged': unchanged_previous,
        'original_r047_live_unchanged': unchanged_original,
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
