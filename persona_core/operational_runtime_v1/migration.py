"""Explicit R043-clone migration and non-destructive writer rollback boundary."""
from __future__ import annotations
import argparse
import json
import sqlite3
import sys
from pathlib import Path
from admission import AdmissionController
from runtime_store import RuntimeStore, SCHEMA_VERSION
from transcript_store import TranscriptStore, create_sandbox, safe_root, ensure

def writer_compatibility(root: Path | str, supported_schema: int = SCHEMA_VERSION) -> dict:
    root = safe_root(root)
    db_path = root / 'runtime.sqlite3'
    ensure(db_path.is_file(), 'Runtime database missing; do not initialize it as rollback')
    db = sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True)
    try:
        actual = db.execute('PRAGMA user_version').fetchone()[0]
        allowed = actual == supported_schema
        return {'actual_schema': actual, 'writer_supported_schema': supported_schema,
                'write_allowed': allowed, 'mode': 'COMPATIBLE' if allowed else 'READ_ONLY_RECOVERY_REQUIRED',
                'downgrade_performed': False, 'events_discarded': 0,
                'legacy_snapshot_is_current_runtime': False,
                'instructions': '保留当前数据库和所有新事件；不兼容时只读查看旧快照，禁止用旧格式覆盖或清空当前实例。'}
    finally:
        db.close()

def migrate_clone(destination: Path | str) -> dict:
    root = create_sandbox(destination)
    store = TranscriptStore(root)
    try:
        before = store.db.execute('PRAGMA user_version').fetchone()[0]
        runtime = RuntimeStore(store, AdmissionController(store))
        return {'destination': str(root), 'from_transcript_schema': before,
                'to_schema': SCHEMA_VERSION, 'genesis_reinstalled': False,
                'production_modified': False, 'verification': runtime.verify(),
                'writer_boundary': writer_compatibility(root)}
    finally:
        store.close()

def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='strict')
    p = argparse.ArgumentParser(description='Migrate a new isolated R043 clone or inspect writer compatibility read-only')
    p.add_argument('action', choices=['clone', 'compatibility'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--writer-schema', type=int, default=SCHEMA_VERSION)
    args = p.parse_args()
    result = migrate_clone(args.root) if args.action == 'clone' else writer_compatibility(args.root, args.writer_schema)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
