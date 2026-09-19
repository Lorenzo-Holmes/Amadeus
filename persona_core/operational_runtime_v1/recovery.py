"""Content-bearing SQLite snapshots and anchored, non-overwriting recovery.

The caller retains the returned manifest hash outside the backup. An attacker
who controls both that trusted reference and all local bytes is out of scope.
Archived Python is evidence only: restore never executes archived source.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from admission import AdmissionController
from provider import canonical, digest
from runtime_store import RuntimeStore, REDUCER_VERSION, SCHEMA_VERSION
from transcript_store import TranscriptStore, safe_root, ensure, file_sha, utc_now

FORMAT = 'APCORE_SQLITE_CONTENT_BACKUP_1'

def logical_summary(db: sqlite3.Connection) -> dict:
    tables = {}
    for name, sql in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        quoted = '"' + name.replace('"', '""') + '"'
        hashes = []
        for row in db.execute('SELECT * FROM ' + quoted):
            values = [{'blob_bytes': len(v), 'sha256': hashlib.sha256(v).hexdigest()} if isinstance(v, bytes) else v for v in row]
            hashes.append(digest(values))
        tables[name] = {'rows': len(hashes), 'rows_sha256': digest(sorted(hashes)), 'schema_sha256': digest(sql)}
    version = db.execute('PRAGMA user_version').fetchone()[0]
    current = db.execute('SELECT state_json,state_sha256,next_sequence,last_event_sha256 FROM runtime_current WHERE singleton=1').fetchone()
    ensure(current is not None and digest(json.loads(current[0])) == current[1], 'Snapshot current state binding failed')
    pending = []
    if 'provider_calls' in tables:
        pending = [list(r) for r in db.execute("SELECT call_id,batch_id,slot_id,status FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN' ORDER BY call_id")]
    return {'schema_version': version, 'tables': tables, 'logical_sha256': digest(tables),
            'event_tail_sha256': current[3], 'state_sha256': current[1], 'next_sequence': current[2],
            'genesis_sha256': json.loads(current[0])['genesis_sha256'], 'unresolved_calls': pending}

def _read_database(path: Path) -> sqlite3.Connection:
    # Only complete Online Backup output is read with immutable=1, never a live WAL database.
    db = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
    try:
        ensure(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'Backup database is corrupt')
        ensure(not db.execute('PRAGMA foreign_key_check').fetchall(), 'Backup foreign keys failed')
        ensure(db.execute('PRAGMA user_version').fetchone()[0] == SCHEMA_VERSION, 'Unsupported backup schema')
        return db
    except BaseException:
        db.close()
        raise

def create_backup(store: TranscriptStore, runtime: RuntimeStore, destination: Path | str) -> dict:
    ensure(runtime.store is store, 'Backup authority/database mismatch')
    runtime.verify()
    destination = safe_root(destination)
    ensure(not destination.is_relative_to(store.root), 'Backup must not be inside the live source root')
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copy2(store.root / 'SANDBOX.json', destination / 'SANDBOX.json')
    shutil.copytree(store.root / 'legacy_runtime', destination / 'legacy_runtime', ignore=shutil.ignore_patterns('__pycache__'))
    code = destination / 'source_snapshot'
    code.mkdir()
    for path in Path(__file__).resolve().parent.glob('*.py'):
        shutil.copy2(path, code / path.name)
    target = sqlite3.connect(destination / 'runtime.sqlite3')
    try:
        store.db.backup(target, pages=128, sleep=0.01)
    finally:
        target.close()
    db = _read_database(destination / 'runtime.sqlite3')
    try:
        summary = logical_summary(db)
    finally:
        db.close()
    files = [{'path': p.relative_to(destination).as_posix(), 'size': p.stat().st_size, 'sha256': file_sha(p)}
             for p in sorted(destination.rglob('*')) if p.is_file()]
    manifest = {'format': FORMAT, 'created_at_utc': utc_now(), 'schema_version': SCHEMA_VERSION,
                'reducer_version': REDUCER_VERSION, 'content_complete': True, 'method': 'SQLITE_ONLINE_BACKUP_API',
                'summary': summary, 'files': files, 'archived_code_is_executed': False,
                'trust_model': 'Caller-held manifest SHA; OS owner can rewrite trusted references and is out of scope.'}
    with (destination / 'BACKUP_MANIFEST.json').open('xb') as f:
        f.write(canonical(manifest))
    anchor = file_sha(destination / 'BACKUP_MANIFEST.json')
    verified = verify_backup(destination, anchor)
    return {'backup_root': str(destination), 'manifest_sha256': anchor, 'summary': verified['summary'],
            'source_is_unchanged_by_backup': True, 'restored': False}

def verify_backup(root: Path | str, manifest_sha256: str) -> dict:
    root = safe_root(root)
    ensure(isinstance(manifest_sha256, str) and re.fullmatch('[0-9a-f]{64}', manifest_sha256) is not None,
           'Caller-held manifest SHA-256 required')
    path = root / 'BACKUP_MANIFEST.json'
    ensure(file_sha(path) == manifest_sha256, 'Backup manifest differs from trusted caller reference')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    ensure(manifest.get('format') == FORMAT and manifest.get('content_complete') is True, 'Not a complete supported backup')
    ensure(manifest.get('schema_version') == SCHEMA_VERSION and manifest.get('reducer_version') == REDUCER_VERSION,
           'Backup code/schema incompatible; use its supported read-only recovery path')
    names = set()
    for item in manifest['files']:
        relative = Path(item['path'])
        member = (root / relative).resolve()
        ensure(not relative.is_absolute() and member.is_relative_to(root) and '..' not in relative.parts,
               'Unsafe manifest member path')
        ensure(item['path'] not in names, 'Duplicate backup member')
        names.add(item['path'])
        ensure(member.is_file() and member.stat().st_size == item['size'] and file_sha(member) == item['sha256'],
               'Missing or changed backup member: ' + item['path'])
    ensure({'runtime.sqlite3', 'SANDBOX.json', 'legacy_runtime/genesis/GENESIS_SNAPSHOT_R035.json'}.issubset(names),
           'Backup lacks essential content')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    ensure(actual == names | {'BACKUP_MANIFEST.json'}, 'Unexpected backup files; do not merge unverified sidecars')
    marker = json.loads((root / 'SANDBOX.json').read_text(encoding='utf-8'))
    ensure(marker['sandbox'] is True, 'Backup is not an isolated runtime')
    ensure(file_sha(root / 'legacy_runtime/genesis/GENESIS_SNAPSHOT_R035.json') == marker['source_genesis_sha256'],
           'Backup Genesis mismatch')
    db = _read_database(root / 'runtime.sqlite3')
    try:
        summary = logical_summary(db)
    finally:
        db.close()
    ensure(summary == manifest['summary'] and summary['genesis_sha256'] == marker['source_genesis_sha256'],
           'Backup logical/identity summary mismatch')
    return manifest

def restore_backup(backup: Path | str, destination: Path | str, manifest_sha256: str, *, dry_run: bool = False) -> dict:
    manifest = verify_backup(backup, manifest_sha256)
    backup, destination = safe_root(backup), safe_root(destination)
    ensure(not destination.exists(), 'Recovery never overwrites an existing path')
    ensure(not destination.is_relative_to(backup), 'Restore must not modify the backup directory')
    if dry_run:
        return {'verified': True, 'dry_run': True, 'destination_created': False, 'summary': manifest['summary']}
    destination.mkdir(parents=True, exist_ok=False)
    for item in manifest['files']:
        target = destination / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup / item['path'], target)
    store = TranscriptStore(destination)
    try:
        runtime = RuntimeStore(store, AdmissionController(store))
        replay = runtime.verify()
        actual = logical_summary(store.db)
        ensure(actual == manifest['summary'], 'Restored logical contents differ from snapshot')
        return {'verified': True, 'dry_run': False, 'destination_created': True, 'destination': str(destination),
                'replay': replay, 'summary': actual, 'provider_resubmissions': 0, 'genesis_reinstalled': False}
    finally:
        store.close()

def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='strict')
    p = argparse.ArgumentParser(description='Amadeus content backup, verify and non-overwriting restore')
    p.add_argument('action', choices=['backup', 'verify', 'restore'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--destination', type=Path)
    p.add_argument('--manifest-sha256')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    if args.action == 'backup':
        ensure(args.destination is not None, 'Backup destination required')
        s = TranscriptStore(args.root)
        try:
            result = create_backup(s, RuntimeStore(s, AdmissionController(s)), args.destination)
        finally:
            s.close()
    elif args.action == 'verify':
        result = verify_backup(args.root, args.manifest_sha256)
    else:
        ensure(args.destination is not None, 'Restore destination required')
        result = restore_backup(args.root, args.destination, args.manifest_sha256, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
