"""Real backup/restore/corruption drills on authored isolated runtime fixtures."""
from __future__ import annotations
import json
import sqlite3
import sys
import unittest
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CODE = ROOT / 'persona_core/operational_runtime_v1'
sys.path.insert(0, str(CODE))
from transcript_store import TranscriptStore, create_sandbox, StoreGuard, file_sha
from admission import AdmissionController
from runtime_store import RuntimeStore
from recovery import create_backup, verify_backup, restore_backup, logical_summary
from context_router import build_context
from provider import ProviderJournal, ENDPOINT, canonical
from test_admission_runtime_r046 import AdmissionRuntimeTests as Helpers

OUT = ROOT / 'persona_core/operational_build_v1/evidence/R046-03' / ('run_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))

class RecoveryTests(unittest.TestCase):
    turn, agreement, state = Helpers.turn, Helpers.agreement, Helpers.state

    def setUp(self):
        self.root = create_sandbox(OUT / self._testMethodName)
        self.s = TranscriptStore(self.root)
        self.h = self.s.open_session('OFFLINE_OPERATOR', 'A')
        self.b = self.s.open_session('OFFLINE_OPERATOR', 'B')
        self.a = AdmissionController(self.s)
        self.r = RuntimeStore(self.s, self.a)
        self.back = OUT / (self._testMethodName + '_backup')
        self.dest = OUT / (self._testMethodName + '_restored')

    def tearDown(self):
        self.s.close()

    def populated(self):
        cid, expected, _ = self.agreement()
        t = self.turn('我喜欢莫扎特')
        self.r.commit(self.h, self.a.record_interest(self.h, t, '莫扎特'))
        t = self.turn('这是B的私密事项', handle=self.b)
        self.a.observe_turn(self.b, t)
        return cid, expected

    def backup(self):
        return create_backup(self.s, self.r, self.back)

    def test_real_content_restore_state_and_open_commitments(self):
        cid, _ = self.populated()
        before = self.state()
        summary = logical_summary(self.s.db)
        backup = self.backup()
        self.assertEqual(summary, backup['summary'])
        result = restore_backup(self.back, self.dest, backup['manifest_sha256'])
        self.assertTrue(result['replay']['replay_equal'])
        self.assertEqual(result['summary'], summary)
        restored = TranscriptStore(self.dest)
        try:
            runtime = RuntimeStore(restored, AdmissionController(restored))
            handle = restored.resume('OFFLINE_OPERATOR', self.h.session_id)
            self.assertEqual(runtime.snapshot(handle), before)
            self.assertEqual(runtime.get_commitment(handle, cid)['status'], 'OPEN')
        finally:
            restored.close()

    def test_fulfilled_commitment_restores_without_double_trust(self):
        cid, expected = self.populated()
        t = self.turn(expected)
        self.r.commit(self.h, self.a.verify_text_submission(self.h, cid, t))
        backup = self.backup()
        result = restore_backup(self.back, self.dest, backup['manifest_sha256'])
        self.assertEqual(result['summary']['state_sha256'], self.r.verify()['state_sha256'])
        self.assertEqual(self.state()['relationship']['trust'], 0.25)

    def test_unknown_provider_intent_survives_without_resubmission(self):
        journal = ProviderJournal(self.s)
        scope = {'batch_id': 'OFFLINE_UNKNOWN', 'principal_id': 'OFFLINE_OPERATOR', 'purpose': 'Authored crash intent, no network',
                 'endpoint': ENDPOINT, 'automatic_paid_retries': 0, 'pricing_verified_date': '2026-09-07',
                 'pricing_sources': ['OFFLINE_FIXTURE'], 'max_input_bytes': 24576, 'max_output_tokens': 600,
                 'input_overhead_reserve_tokens': 4096, 'total_guard_cny': 1.0, 'reserved_upper_micro_cny': 91416,
                 'slots': [{'id': 'one', 'model': 'deepseek-v4-flash', 'entity_label': 'A', 'user_text': '未决测试'}]}
        journal.register_batch(scope)
        turn = self.s.begin_turn(self.h, '未决测试', 'unknown')
        def abort(payload, credential):
            raise SystemExit('AUTHORED_LOCAL_CRASH_NO_NETWORK')
        with self.assertRaises(SystemExit):
            journal.call(self.h, turn['turn_id'], scope['batch_id'], 'one', build_context(self.s, self.h, turn['turn_id']),
                         transport=abort, credential_reader=lambda: 'NOT_A_REAL_CREDENTIAL')
        backup = self.backup()
        self.assertEqual(len(backup['summary']['unresolved_calls']), 1)
        result = restore_backup(self.back, self.dest, backup['manifest_sha256'])
        self.assertEqual(result['summary']['unresolved_calls'], backup['summary']['unresolved_calls'])
        self.assertEqual(result['provider_resubmissions'], 0)

    def test_dry_run_creates_nothing(self):
        b = self.backup()
        result = restore_backup(self.back, self.dest, b['manifest_sha256'], dry_run=True)
        self.assertTrue(result['dry_run'])
        self.assertFalse(self.dest.exists())

    def test_existing_destination_refused(self):
        b = self.backup()
        self.dest.mkdir()
        with self.assertRaises(StoreGuard):
            restore_backup(self.back, self.dest, b['manifest_sha256'])

    def test_backup_does_not_overwrite(self):
        b = self.backup()
        with self.assertRaises(FileExistsError):
            self.backup()
        self.assertEqual(file_sha(self.back / 'BACKUP_MANIFEST.json'), b['manifest_sha256'])

    def test_backup_not_inside_live_root(self):
        with self.assertRaises(StoreGuard):
            create_backup(self.s, self.r, self.root / 'nested_backup')

    def test_truncated_database_refused_and_healthy_source_kept(self):
        self.populated()
        b = self.backup()
        p = self.back / 'runtime.sqlite3'
        p.write_bytes(p.read_bytes()[:128])
        with self.assertRaises(StoreGuard):
            restore_backup(self.back, self.dest, b['manifest_sha256'])
        self.assertTrue(self.r.verify()['replay_equal'])
        self.assertFalse(self.dest.exists())

    def test_missing_genesis_refused(self):
        b = self.backup()
        (self.back / 'legacy_runtime/genesis/GENESIS_SNAPSHOT_R035.json').unlink()
        with self.assertRaises(StoreGuard):
            verify_backup(self.back, b['manifest_sha256'])

    def test_changed_manifest_refused_by_external_anchor(self):
        b = self.backup()
        p = self.back / 'BACKUP_MANIFEST.json'
        p.write_bytes(p.read_bytes() + b' ')
        with self.assertRaises(StoreGuard):
            verify_backup(self.back, b['manifest_sha256'])

    def test_wrong_schema_refused_even_with_recomputed_manifest(self):
        self.backup()
        path = self.back / 'runtime.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute('PRAGMA user_version=999')
        mp = self.back / 'BACKUP_MANIFEST.json'
        manifest = json.loads(mp.read_text(encoding='utf-8'))
        for member in manifest['files']:
            if member['path'] == 'runtime.sqlite3':
                member.update(size=path.stat().st_size, sha256=file_sha(path))
        mp.write_bytes(canonical(manifest))
        with self.assertRaises(StoreGuard):
            restore_backup(self.back, self.dest, file_sha(mp))

    def test_unverified_wal_sidecar_refused(self):
        b = self.backup()
        (self.back / 'runtime.sqlite3-wal').write_bytes(b'FAKE_UNVERIFIED_WAL')
        with self.assertRaises(StoreGuard):
            verify_backup(self.back, b['manifest_sha256'])

    def test_path_traversal_manifest_refused(self):
        self.backup()
        mp = self.back / 'BACKUP_MANIFEST.json'
        manifest = json.loads(mp.read_text(encoding='utf-8'))
        manifest['files'][0]['path'] = '../DO_NOT_READ'
        mp.write_bytes(canonical(manifest))
        with self.assertRaises(StoreGuard):
            restore_backup(self.back, self.dest, file_sha(mp))

    def test_production_destination_refused(self):
        b = self.backup()
        with self.assertRaises(StoreGuard):
            restore_backup(self.back, ROOT / 'persona_core/runtime/illegal_restore', b['manifest_sha256'])

    def test_source_advances_backup_stays_at_its_snapshot(self):
        self.populated()
        b = self.backup()
        old = b['summary']['next_sequence']
        self.a.observe_turn(self.h, self.turn('备份后的新记录'))
        self.assertGreater(self.r.verify()['events'] + 1, old)
        result = restore_backup(self.back, self.dest, b['manifest_sha256'])
        self.assertEqual(result['summary']['next_sequence'], old)

    def test_destroyed_source_restored_from_real_content(self):
        self.populated()
        b = self.backup()
        self.s.close()
        source = self.root / 'runtime.sqlite3'
        source.write_bytes(b'AUTHORED_DESTROYED_DB_FIXTURE')
        result = restore_backup(self.back, self.dest, b['manifest_sha256'])
        self.assertTrue(result['replay']['replay_equal'])
        self.assertEqual(source.read_bytes(), b'AUTHORED_DESTROYED_DB_FIXTURE')

def main():
    OUT.mkdir(parents=True, exist_ok=False)
    sources = list(CODE.glob('*.py')) + [Path(__file__), Path(__file__).with_name('test_admission_runtime_r046.py')]
    with zipfile.ZipFile(OUT / 'TESTED_SOURCE.zip', 'x', zipfile.ZIP_DEFLATED) as z:
        for p in sources:
            z.writestr(p.relative_to(ROOT).as_posix(), p.read_bytes())
    with (OUT / 'TESTS.log').open('x', encoding='utf-8') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RecoveryTests))
    report = {'at_utc': datetime.now(timezone.utc).isoformat(), 'tests': result.testsRun, 'passed': result.wasSuccessful(),
              'failures': len(result.failures), 'errors': len(result.errors), 'target_model_calls': 0,
              'origin': 'AUTHORED_OFFLINE_DATA_REAL_SQLITE_BACKUP_AND_RESTORE',
              'source_snapshot_sha256': file_sha(OUT / 'TESTED_SOURCE.zip'),
              'tested_sources': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': file_sha(p)} for p in sources]}
    (OUT / 'TESTS.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': OUT.relative_to(ROOT).as_posix(), 'tests': result.testsRun, 'passed': result.wasSuccessful()}))
    raise SystemExit(0 if result.wasSuccessful() else 1)

if __name__ == '__main__':
    main()
