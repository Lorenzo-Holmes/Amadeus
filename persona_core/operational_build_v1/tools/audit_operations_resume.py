"""Read-only runtime reconciliation and a new, non-overwriting evidence snapshot.

No provider is imported and no network request is made. The only writes are a
new evidence directory, a SQLite online backup, and immutable audit outputs.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / 'persona_core/operational_build_v1'
LIVE = PLAN / 'evidence/R045-03/live_01'

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> None:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = PLAN / 'evidence/R045-04' / ('resume_' + stamp)
    out.mkdir(parents=True, exist_ok=False)
    state = json.loads((PLAN / 'TASK_STATE.json').read_text(encoding='utf-8'))
    database = LIVE / 'runtime.sqlite3'
    source = sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)
    source.row_factory = sqlite3.Row
    try:
        source.execute('PRAGMA query_only=ON')
        integrity = source.execute('PRAGMA integrity_check').fetchall()
        calls = [dict(r) for r in source.execute(
            'SELECT call_id,slot_id,status,model,error_category,reserve_micro_cny,estimate_peak_micro_cny FROM provider_calls')]
        batches = [dict(r) for r in source.execute('SELECT batch_id,stopped,scope_sha256 FROM call_batches')]
        sessions = [dict(r) for r in source.execute('SELECT * FROM sessions')]
        turns = [dict(r) for r in source.execute('SELECT turn_id,status,request_id FROM turns')]
        with sqlite3.connect(out / 'LIVE_DATABASE_BACKUP.sqlite3') as target:
            source.backup(target)
            assert target.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    finally:
        source.close()
    files = sorted((ROOT / 'persona_core/runtime').rglob('*'))
    production = [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                  for p in files if p.is_file() and '__pycache__' not in p.parts]
    preserve = [ROOT / n for n in ('AGENTS.md', 'AMADEUS_PERSONA_CORE_MASTER_GOAL.md',
                'PERSONA_CORE_PROGRESS.md', 'PERSONA_CORE_CONTINUATION_PROTOCOL.md', 'PERSONA_CORE_DECISION_LOG.md')]
    preserve += list((ROOT / 'persona_core/operational_runtime_v1').glob('*.py'))
    preserve += [PLAN / n for n in ('TASK_STATE.json', 'ACCEPTANCE_MATRIX.json')]
    preserve += [ROOT / r['path'] for r in production]
    with zipfile.ZipFile(out / 'PRECHANGE_SOURCE.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in preserve:
            archive.writestr(path.relative_to(ROOT).as_posix(), path.read_bytes())
    report = {
        'at_utc': datetime.now(timezone.utc).isoformat(), 'workspace': str(ROOT),
        'active_task': state['active_task'], 'python': sys.version, 'sqlite': sqlite3.sqlite_version,
        'database_integrity': [r[0] for r in integrity], 'provider_calls': calls,
        'call_batches': batches, 'sessions': sessions, 'turns': turns,
        'unresolved_calls': [r for r in calls if r['status'] == 'SUBMITTED_STATUS_UNKNOWN'],
        'production_files': production,
        'prechange_snapshot_sha256': sha(out / 'PRECHANGE_SOURCE.zip'),
        'database_backup_sha256': sha(out / 'LIVE_DATABASE_BACKUP.sqlite3'),
        'new_target_calls': 0, 'paid_retries': 0, 'production_writes': False,
        'tool_recovery': 'Initial HTTP 502 and a blocked read-only query; subsequent reads and the same query succeeded. Failed recovery note confirmed absent.',
        'acceptance_verdict': None,
    }
    (out / 'RESUME_AUDIT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': out.relative_to(ROOT).as_posix(), 'calls': calls,
                      'integrity': report['database_integrity'], 'unresolved': len(report['unresolved_calls'])}, ensure_ascii=True))
    if report['unresolved_calls'] or report['database_integrity'] != ['ok']:
        raise SystemExit(2)

if __name__ == '__main__':
    main()
