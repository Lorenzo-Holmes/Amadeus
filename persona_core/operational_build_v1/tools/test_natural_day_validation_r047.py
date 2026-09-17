from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import natural_day_validation_r047 as n

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


def fixture(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.executescript('''
    CREATE TABLE runtime_current(singleton INTEGER PRIMARY KEY,state_json TEXT,state_sha256 TEXT,last_event_sha256 TEXT,next_sequence INTEGER);
    CREATE TABLE call_batches(batch_id TEXT PRIMARY KEY,scope_sha256 TEXT,stopped INTEGER);
    CREATE TABLE sessions(session_id TEXT PRIMARY KEY);
    CREATE TABLE turns(turn_id TEXT PRIMARY KEY,user_text TEXT,status TEXT,display_at_utc TEXT,input_provenance TEXT,response_provenance TEXT);
    CREATE TABLE provider_calls(call_id TEXT PRIMARY KEY,turn_id TEXT,session_id TEXT,batch_id TEXT,slot_id TEXT,model TEXT,status TEXT,error_category TEXT,context_json TEXT,submitted_at_utc TEXT);
    CREATE TABLE cli_process_runs(process_id INTEGER,session_id TEXT,started_at_utc TEXT,ended_at_utc TEXT,exit_code INTEGER);
    CREATE TABLE runtime_events(event_id TEXT);
    ''')
    state = {'commitments': {}, 'event_count': 0, 'schema_version': 46}
    db.execute('INSERT INTO runtime_current VALUES(1,?,?,?,1)', (json.dumps(state), 'state', 'tail'))
    db.commit()
    return db


def add_call(db, idx: int, *, model='deepseek-v4-flash', status='RESPONSE_CAPTURED', turn_status='DISPLAYED', context=None):
    sid = 'session_1'; tid = f'turn_{idx}'; cid = f'call_{idx}'
    db.execute('INSERT OR IGNORE INTO sessions VALUES(?)', (sid,))
    db.execute('INSERT INTO turns VALUES(?,?,?,?,?,?)', (tid, f'user {idx}', turn_status, '2026-09-11T12:00:00+00:00', 'RAW_USER_UTTERANCE_NOT_EVENT_PROOF', 'TARGET_PROVIDER_CAPTURE'))
    db.execute('INSERT INTO provider_calls VALUES(?,?,?,?,?,?,?,?,?,?)',
               (cid, tid, sid, n.BATCH, f'USER_{idx:02d}', model, status, None, json.dumps(context or {'retrieval': []}), '2026-09-11T11:59:00+00:00'))
    db.commit()


class Tests(unittest.TestCase):
    def test_scope_contract(self):
        s = n.fixed_scope()
        self.assertEqual(len(s['slots']), 16)
        self.assertEqual(s['slots'][8]['model'], 'deepseek-v4-pro')
        self.assertEqual(s['reserved_upper_micro_cny'], 2_875_392)
        self.assertEqual(s['total_guard_cny'], 3.0)

    def test_initialization_does_not_qualify(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'db.sqlite3'; db = fixture(path); db.close()
            result = n.evaluate(path, now=NOW, checkpoint_root=Path(td) / 'checkpoints')
            self.assertFalse(result['today_can_qualify'])
            self.assertEqual(result['today_displayed_calls'], 0)

    def test_real_displayed_turn_qualifies(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'db.sqlite3'; db = fixture(path)
            db.execute('INSERT INTO call_batches VALUES(?,?,0)', (n.BATCH, n.digest(n.fixed_scope())))
            add_call(db, 1); db.close()
            result = n.evaluate(path, now=NOW, checkpoint_root=Path(td) / 'checkpoints')
            self.assertTrue(result['today_can_qualify'])
            self.assertEqual(result['session_ids'], ['session_1'])

    def test_same_date_duplicate_does_not_count_twice(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'db.sqlite3'; db = fixture(path)
            db.execute('INSERT INTO call_batches VALUES(?,?,0)', (n.BATCH, n.digest(n.fixed_scope())))
            add_call(db, 1); db.close()
            cp = Path(td) / 'checkpoints/day'; cp.mkdir(parents=True)
            (cp / 'CHECKPOINT.json').write_text(json.dumps({'qualified_observation_day': True, 'observed_local_date': '2026-09-11'}), encoding='utf-8')
            result = n.evaluate(path, now=NOW, checkpoint_root=Path(td) / 'checkpoints')
            self.assertTrue(result['today_already_counted'])
            self.assertFalse(result['today_can_qualify'])

    def test_unknown_or_rejected_blocks_day(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'db.sqlite3'; db = fixture(path)
            db.execute('INSERT INTO call_batches VALUES(?,?,1)', (n.BATCH, n.digest(n.fixed_scope())))
            add_call(db, 1, status='SUBMITTED_STATUS_UNKNOWN', turn_status='SUBMITTED_STATUS_UNKNOWN'); db.close()
            result = n.evaluate(path, now=NOW, checkpoint_root=Path(td) / 'checkpoints')
            self.assertFalse(result['today_can_qualify'])
            self.assertEqual(len(result['bad_or_unresolved_calls']), 1)

    def test_restart_model_switch_and_commitment_retrieval_are_detected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'db.sqlite3'; db = fixture(path)
            db.execute('INSERT INTO call_batches VALUES(?,?,0)', (n.BATCH, n.digest(n.fixed_scope())))
            state = {'commitments': {'commitment_1': {'commitment_id': 'commitment_1', 'text': '早期约定', 'status': 'OPEN'}}, 'event_count': 1, 'schema_version': 46}
            db.execute('UPDATE runtime_current SET state_json=?', (json.dumps(state),))
            add_call(db, 1, context={'retrieval': []})
            add_call(db, 9, model='deepseek-v4-pro', context={'retrieval': [{'record_kind': 'COMMITMENT', 'record_id': 'commitment_1'}]})
            db.executemany('INSERT INTO cli_process_runs VALUES(?,?,?,?,?)', [
                (100, 'session_1', '2026-09-10T12:00:00+00:00', '2026-09-10T12:05:00+00:00', 0),
                (200, 'session_1', '2026-09-11T11:50:00+00:00', None, None)
            ])
            db.commit(); db.close()
            result = n.evaluate(path, now=NOW, checkpoint_root=Path(td) / 'checkpoints')
            self.assertTrue(result['same_session_model_switch_observed'])
            self.assertTrue(result['real_restart_observed'])
            self.assertTrue(result['commitment_retrieval_observed'])


def main():
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'tests': result.testsRun, 'passed': result.wasSuccessful(), 'target_calls': 0, 'network_calls': 0}))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
