"""Machine-verifiable quarantine for historical remote-unknown provider calls.

Quarantine is deliberately narrower than resolution:
- the raw journal row remains SUBMITTED_STATUS_UNKNOWN;
- remote execution/billing remains UNKNOWN;
- the old logical batch stays stopped and the old slot is never resent;
- a later *independent* batch may proceed only when every historical UNKNOWN is
  either a specifically proven pre-network local rejection or a validated
  historical development quarantine with no local product-state effects.

Nothing here rewrites journals or creates model calls.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import r047_execution_common as common

ROOT, PLAN = common.ROOT, common.PLAN
BASE = PLAN / 'evidence/R047-03'
UNKNOWN_BASES = (PLAN / 'evidence/R047-03', PLAN / 'evidence/R047-04')
ensure, file_sha = common.ensure, common.file_sha


def direct_live_roots(base: Path = BASE) -> list[Path]:
    """Discover direct R047 live journals regardless of revision naming."""
    base = Path(base)
    return sorted(p for p in base.iterdir()
                  if p.is_dir() and (p / 'live/runtime.sqlite3').is_file())


def validated_local_pre_http_unknowns() -> dict[str, dict]:
    """The one historical raw UNKNOWN that has deterministic pre-HTTP proof."""
    proof_path = BASE / 'capacity_probe_01/local_reconciliation_20260911T024206815047Z/RECONCILIATION.json'
    proof = json.loads(proof_path.read_text(encoding='utf-8'))
    ensure(proof['disposition'] == 'LOCAL_PRE_HTTP_CONFIGURATION_REJECTION_DETERMINISTICALLY_RECONCILED',
           'Named local disposition changed')
    ensure(proof['original_status_rewritten'] is False, 'Historical UNKNOWN must remain raw')
    journal = ROOT / proof['journal']
    ensure(journal.is_file() and file_sha(journal) == proof['journal_sha256'],
           'Named local disposition journal binding changed')
    result = proof['controlled_process_result']
    ensure(result['worker_exit_code'] == 2 and result['transport_attempts'] == 0 and not result['socket_events'],
           'Named local disposition no longer proves pre-HTTP rejection')
    return {proof['call_id']: {
        'classification': 'LOCAL_PRE_HTTP_REJECTION_DETERMINISTICALLY_RECONCILED',
        'evidence': proof_path.relative_to(ROOT).as_posix(),
        'evidence_sha256': file_sha(proof_path),
        'remote_outcome_known': False,
        'resend_allowed': False,
    }}


def quarantine_manifests(base: Path = BASE) -> list[Path]:
    return sorted(base.glob('unknown_quarantine_*/QUARANTINE.json'))


def validate_quarantine(path: Path) -> dict:
    """Validate one quarantine against the immutable stopped historical journal."""
    q = json.loads(path.read_text(encoding='utf-8'))
    required = {
        'schema_version', 'classification', 'call_id', 'batch_id', 'slot_id',
        'journal', 'journal_sha256', 'request_sha256', 'reserve_micro_cny',
        'reconciliation', 'reconciliation_sha256', 'remote_outcome',
        'resend_allowed', 'old_batch_resume_allowed',
        'new_independent_batch_allowed', 'release_risk_record_required',
        'local_product_state_mutation_committed', 'billing_verified',
    }
    ensure(required.issubset(q), 'Quarantine manifest missing required fields')
    ensure(q['schema_version'] == 'apcore-remote-unknown-quarantine-1', 'Unsupported quarantine schema')
    ensure(q['classification'] == 'QUARANTINED_REMOTE_UNKNOWN', 'Wrong quarantine classification')
    ensure(q['remote_outcome'] == 'UNKNOWN', 'Quarantine cannot resolve remote outcome')
    ensure(q['resend_allowed'] is False and q['old_batch_resume_allowed'] is False,
           'Quarantine must never authorize retry or old-batch resume')
    ensure(q['new_independent_batch_allowed'] is True,
           'Quarantine must state its only allowed continuation explicitly')
    ensure(q['release_risk_record_required'] is True and q['billing_verified'] is False,
           'Quarantine risk/billing boundary changed')
    ensure(q['local_product_state_mutation_committed'] is False,
           'A remote UNKNOWN with committed local product state is not quarantine-safe')

    journal = (ROOT / q['journal']).resolve()
    ensure(journal.is_relative_to(ROOT) and journal.is_file(), 'Quarantine journal missing/outside workspace')
    ensure(file_sha(journal) == q['journal_sha256'], 'Quarantined journal changed')
    reconciliation = (ROOT / q['reconciliation']).resolve()
    ensure(reconciliation.is_relative_to(ROOT) and reconciliation.is_file(), 'Quarantine reconciliation missing')
    ensure(file_sha(reconciliation) == q['reconciliation_sha256'], 'Quarantine reconciliation changed')
    r = json.loads(reconciliation.read_text(encoding='utf-8'))
    ensure(r['call_id'] == q['call_id'] and r['slot_id'] == q['slot_id'], 'Quarantine reconciliation target changed')
    ensure(r['status'] == 'SUBMITTED_STATUS_UNKNOWN', 'Quarantine reconciliation status changed')
    ensure(r['disposition'] == 'REMOTE_OUTCOME_UNRESOLVED_DO_NOT_RESEND',
           'Quarantine reconciliation must preserve unresolved remote state')
    ensure(r['request_sha256'] == q['request_sha256'] and r['reserve_micro_cny'] == q['reserve_micro_cny'],
           'Quarantine request/reserve binding changed')

    db = sqlite3.connect(journal.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        ensure(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'Quarantine journal integrity failure')
        row = db.execute(
            "SELECT p.call_id,p.batch_id,p.slot_id,p.status,p.request_sha256,p.reserve_micro_cny,"
            "t.status AS turn_status,t.assistant_text "
            "FROM provider_calls p JOIN turns t USING(turn_id) WHERE p.call_id=?",
            (q['call_id'],)).fetchone()
        ensure(row is not None, 'Quarantined call missing')
        ensure(row['batch_id'] == q['batch_id'] and row['slot_id'] == q['slot_id'], 'Quarantined call identity changed')
        ensure(row['status'] == 'SUBMITTED_STATUS_UNKNOWN' and row['turn_status'] == 'SUBMITTED_STATUS_UNKNOWN',
               'Quarantined raw UNKNOWN was rewritten')
        ensure(row['request_sha256'] == q['request_sha256'] and row['reserve_micro_cny'] == q['reserve_micro_cny'],
               'Quarantined request/reserve changed')
        ensure(row['assistant_text'] is None, 'Quarantined call unexpectedly has assistant text')
        stopped = db.execute('SELECT stopped FROM call_batches WHERE batch_id=?', (q['batch_id'],)).fetchone()
        ensure(stopped is not None and stopped[0] == 1, 'Quarantined logical batch must remain stopped')
        active = db.execute("SELECT value FROM metadata WHERE key='r047_active_driver'").fetchone()
        ensure(active is None or active[0] == '', 'Quarantined batch still has an active driver')
        turn_id = db.execute('SELECT turn_id FROM provider_calls WHERE call_id=?', (q['call_id'],)).fetchone()[0]
        ensure(db.execute('SELECT count(*) FROM display_journal WHERE turn_id=?', (turn_id,)).fetchone()[0] == 0,
               'Quarantined UNKNOWN has a display attempt')
        ensure(db.execute('SELECT count(*) FROM chat_traces WHERE turn_id=?', (turn_id,)).fetchone()[0] == 0,
               'Quarantined UNKNOWN has committed chat/event state')
    finally:
        db.close()
    return q


def validated_quarantined_unknowns(base: Path = BASE) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for path in quarantine_manifests(base):
        q = validate_quarantine(path)
        ensure(q['call_id'] not in result, 'Duplicate quarantine call ID')
        result[q['call_id']] = {**q, 'manifest': path.relative_to(ROOT).as_posix(),
                                'manifest_sha256': file_sha(path)}
    return result


def scan_unknowns(base: Path, allowed: dict[str, dict] | set[str] | None = None) -> dict:
    """Classify raw UNKNOWN rows. `allowed` is injectable only for offline tests."""
    base = Path(base)
    if allowed is None:
        allow_map: dict[str, dict] = {}
    elif isinstance(allowed, set):
        allow_map = {call_id: {'classification': 'TEST_ALLOWED'} for call_id in allowed}
    else:
        allow_map = allowed
    rows, active, allowed_rows = [], [], []
    for root in direct_live_roots(base):
        journal = root / 'live/runtime.sqlite3'
        db = sqlite3.connect(journal.as_uri() + '?mode=ro', uri=True)
        db.row_factory = sqlite3.Row
        try:
            ensure(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'UNKNOWN-scan journal integrity failure')
            for row in db.execute(
                    "SELECT call_id,batch_id,slot_id,error_category FROM provider_calls "
                    "WHERE status='SUBMITTED_STATUS_UNKNOWN' ORDER BY call_id"):
                item = {'journal': journal.relative_to(base).as_posix(), **dict(row)}
                rows.append(item)
                if row['call_id'] in allow_map:
                    allowed_rows.append({**item, **allow_map[row['call_id']]})
                else:
                    active.append(item)
        finally:
            db.close()
    return {'raw_unknowns': rows, 'allowed_historical_unknowns': allowed_rows,
            'active_unresolved_remote_unknowns': active}


def project_unknown_status() -> dict:
    allowed = {}
    allowed.update(validated_local_pre_http_unknowns())
    for base in UNKNOWN_BASES:
        if not base.is_dir():
            continue
        for call_id, item in validated_quarantined_unknowns(base).items():
            ensure(call_id not in allowed, 'Duplicate historical UNKNOWN classification across evidence roots')
            allowed[call_id] = item

    raw, historical, active = [], [], []
    for base in UNKNOWN_BASES:
        if not base.is_dir():
            continue
        status = scan_unknowns(base, allowed)
        root_label = base.relative_to(PLAN).as_posix()
        for key, target in (('raw_unknowns', raw),
                            ('allowed_historical_unknowns', historical),
                            ('active_unresolved_remote_unknowns', active)):
            for row in status[key]:
                target.append({**row, 'evidence_root': root_label})
    ids = [row['call_id'] for row in raw]
    ensure(len(ids) == len(set(ids)), 'Duplicate raw UNKNOWN call ID across evidence roots')
    return {'raw_unknowns': raw, 'allowed_historical_unknowns': historical,
            'active_unresolved_remote_unknowns': active}


def ensure_new_independent_batch_allowed() -> dict:
    status = project_unknown_status()
    ensure(not status['active_unresolved_remote_unknowns'],
           'Active unresolved remote UNKNOWN blocks a new paid batch')
    return status

