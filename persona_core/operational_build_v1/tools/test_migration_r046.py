"""Real subprocess migration/restart/recovery drills. All provider text is authored."""
from __future__ import annotations
import json
import sqlite3
import subprocess
import sys
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CODE = ROOT / 'persona_core/operational_runtime_v1'
sys.path.insert(0, str(CODE))
from transcript_store import TranscriptStore, create_sandbox, file_sha, StoreGuard
from migration import migrate_clone, writer_compatibility
from recovery import logical_summary
from admission import AdmissionController
from runtime_store import RuntimeStore

OUT = ROOT / 'persona_core/operational_build_v1/evidence/R046-06' / ('run_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
WORKER = Path(__file__).with_name('migration_worker_r046.py')

class MigrationTests(unittest.TestCase):
    def root(self):
        return OUT / self._testMethodName

    def worker(self, root, action, expected=0):
        command = [sys.executable, '-B', str(WORKER), action, '--root', str(root)]
        result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
        (root / (action + '_stdout.txt')).write_bytes(result.stdout)
        (root / (action + '_stderr.txt')).write_bytes(result.stderr)
        (root / (action + '_PROCESS.json')).write_text(json.dumps({'command': command, 'returncode': result.returncode,
            'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'expected_returncode': expected,
            'fixture_target_calls': 0}, indent=2), encoding='utf-8')
        self.assertEqual(result.returncode, expected, result.stderr.decode('utf-8', errors='replace'))
        if expected == 0:
            return json.loads((root / ('WORKER_' + action + '.json')).read_text(encoding='utf-8'))
        return None

    def test_actual_new_process_restart_then_backup_restore_and_rollback_boundary(self):
        root = create_sandbox(self.root())
        first = self.worker(root, 'initialize')
        second = self.worker(root, 'continue')
        self.assertNotEqual(first['pid'], second['pid'])
        self.assertEqual(first['session_id'], second['session_id'])
        self.assertEqual(first['schema_before_open'], 45)
        self.assertEqual(second['schema_before_open'], 46)
        self.assertEqual(first['verification']['genesis_sha256'], second['verification']['genesis_sha256'])
        self.assertEqual(second['verification']['events'], 4)
        self.assertTrue(second['restored_state_and_retrieval_equal'])
        self.assertEqual(second['before_state']['relationship']['verified_completions'], 1)
        self.assertFalse(second['rollback_to_old_writer']['write_allowed'])
        self.assertEqual(second['rollback_to_old_writer']['events_discarded'], 0)
        self.assertEqual(second['restored']['summary']['unresolved_calls'], [])

    def test_actual_display_ack_admission_crash_recovers_without_display_or_network(self):
        root = create_sandbox(self.root())
        self.worker(root, 'display_crash', 79)
        with sqlite3.connect(root / 'runtime.sqlite3') as db:
            self.assertEqual(db.execute('SELECT status FROM turns').fetchone()[0], 'DISPLAYED')
            self.assertEqual(db.execute('SELECT count(*) FROM runtime_events').fetchone()[0], 0)
        recovered = self.worker(root, 'display_recover')
        self.assertEqual(recovered['verification']['events'], 1)
        self.assertEqual(recovered['new_provider_submissions'], 0)
        self.assertEqual(recovered['new_displays'], 0)
        self.assertEqual(recovered['provider_calls'], 1)

    def test_cli_migration_entry_creates_clone_not_genesis_install(self):
        root = self.root()
        command = [sys.executable, '-B', str(CODE / 'migration.py'), 'clone', '--root', str(root)]
        result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
        report = json.loads(result.stdout)
        self.assertFalse(report['genesis_reinstalled'])
        self.assertFalse(report['production_modified'])
        self.assertEqual(report['verification']['events'], 0)
        self.assertEqual(report['verification']['genesis_sha256'], file_sha(ROOT / 'persona_core/runtime/genesis/GENESIS_SNAPSHOT_R035.json'))
        (root / 'MIGRATION_CLI.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    def test_compatibility_read_only_does_not_rewrite_database(self):
        root = self.root()
        migrate_clone(root)
        before = file_sha(root / 'runtime.sqlite3')
        self.assertFalse(writer_compatibility(root, 43)['write_allowed'])
        self.assertFalse(writer_compatibility(root, 45)['write_allowed'])
        self.assertTrue(writer_compatibility(root, 46)['write_allowed'])
        self.assertEqual(before, file_sha(root / 'runtime.sqlite3'))

    def test_existing_clone_is_not_overwritten(self):
        root = self.root()
        migrate_clone(root)
        before = file_sha(root / 'runtime.sqlite3')
        with self.assertRaises(FileExistsError):
            migrate_clone(root)
        self.assertEqual(before, file_sha(root / 'runtime.sqlite3'))

    def test_formal_runtime_is_not_a_migration_target(self):
        with self.assertRaises(StoreGuard):
            migrate_clone(ROOT / 'persona_core/runtime/should_never_exist')

def main():
    OUT.mkdir(parents=True, exist_ok=False)
    sources = list(CODE.glob('*.py')) + [Path(__file__), WORKER]
    production = {p.relative_to(ROOT).as_posix(): file_sha(p) for p in (ROOT / 'persona_core/runtime').rglob('*') if p.is_file()}
    with zipfile.ZipFile(OUT / 'TESTED_SOURCE.zip', 'x', zipfile.ZIP_DEFLATED) as z:
        for p in sources:
            z.writestr(p.relative_to(ROOT).as_posix(), p.read_bytes())
    with (OUT / 'TESTS.log').open('x', encoding='utf-8') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MigrationTests))
    after = {p.relative_to(ROOT).as_posix(): file_sha(p) for p in (ROOT / 'persona_core/runtime').rglob('*') if p.is_file()}
    passed = result.wasSuccessful() and production == after
    report = {'at_utc': datetime.now(timezone.utc).isoformat(), 'tests': result.testsRun, 'passed': passed,
              'failures': len(result.failures), 'errors': len(result.errors), 'target_model_calls': 0,
              'origin': 'ACTUAL_PROCESSES_AUTHORED_TRANSPORT_REAL_MIGRATION_BACKUP_RESTORE',
              'production_unchanged': production == after, 'production_hashes': production,
              'source_snapshot_sha256': file_sha(OUT / 'TESTED_SOURCE.zip'),
              'tested_sources': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': file_sha(p)} for p in sources]}
    (OUT / 'TESTS.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': OUT.relative_to(ROOT).as_posix(), 'tests': result.testsRun, 'passed': passed}))
    raise SystemExit(0 if passed else 1)

if __name__ == '__main__':
    main()
