"""Fail-closed R047-04 real-natural-day checkpointing for the clean candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / 'persona_core/operational_build_v1'
R04704 = PLAN / 'evidence/R047-04'
OBS = R04704 / 'natural_day_observation'
CHECKPOINTS = OBS / 'checkpoints'
SCOPE_PATH = R04704 / 'NATURAL_DAY_OBSERVATION_SCOPE.json'
CANDIDATE = PLAN / 'evidence/R047-05/candidate_20260911T130857589500Z'
RUNTIME = CANDIDATE / 'runtime'
DB_PATH = RUNTIME / 'runtime.sqlite3'
RELEASE = CANDIDATE / 'RELEASE_MANIFEST.json'
INITIALIZATION = R04704 / 'preparation_20260908/candidate_initialization_20260911_r002/checkpoint/CHECKPOINT.json'
TOKYO = timezone(timedelta(hours=9), name='Asia/Tokyo')
BATCH = 'APCORE-R047-NATURAL-DAY-01'

sys.path.insert(0, str(ROOT / 'persona_core/operational_runtime_v1'))
from provider import digest, scope_check  # noqa: E402


class ObservationGuard(ValueError):
    pass


def ensure(value: bool, message: str) -> None:
    if not value:
        raise ObservationGuard(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def file_entries(base: Path) -> list[dict]:
    return [{'path': p.relative_to(base).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}
            for p in sorted(base.rglob('*')) if p.is_file()]


def fixed_scope() -> dict:
    scope = load(SCOPE_PATH)
    scope_check(scope)
    ensure(scope['batch_id'] == BATCH, 'Wrong natural-day batch id')
    ensure(len(scope['slots']) == 16, 'Natural-day slot denominator changed')
    ensure(sum(s['model'] == 'deepseek-v4-flash' for s in scope['slots']) == 15, 'Flash denominator changed')
    ensure(sum(s['model'] == 'deepseek-v4-pro' for s in scope['slots']) == 1, 'Pro denominator changed')
    ensure(scope['slots'][8]['id'] == 'USER_09' and scope['slots'][8]['model'] == 'deepseek-v4-pro',
           'Pinned model-switch slot changed')
    ensure(scope['reserved_upper_micro_cny'] == 2_875_392 and scope['total_guard_cny'] == 3.0,
           'Natural-day budget contract changed')
    return scope


def _table_exists(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _date(value: str) -> str:
    return datetime.fromisoformat(value).astimezone(TOKYO).date().isoformat()


def _prior_dates(checkpoint_root: Path = CHECKPOINTS) -> list[str]:
    values = []
    if checkpoint_root.exists():
        for path in sorted(checkpoint_root.glob('*/CHECKPOINT.json')):
            item = load(path)
            if item.get('qualified_observation_day') is True:
                values.append(item['observed_local_date'])
    return sorted(set(values))


def _logical_summary(db: sqlite3.Connection) -> dict:
    ensure(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'SQLite integrity failure')
    row = db.execute('SELECT state_json,state_sha256,last_event_sha256,next_sequence FROM runtime_current WHERE singleton=1').fetchone()
    ensure(row is not None, 'Missing runtime_current')
    state = json.loads(row[0])
    return {
        'state': state,
        'state_sha256': row[1],
        'event_tail_sha256': row[2],
        'next_sequence': row[3],
        'provider_calls': db.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0] if _table_exists(db, 'provider_calls') else 0,
        'turns': db.execute('SELECT COUNT(*) FROM turns').fetchone()[0] if _table_exists(db, 'turns') else 0,
        'runtime_events': db.execute('SELECT COUNT(*) FROM runtime_events').fetchone()[0] if _table_exists(db, 'runtime_events') else 0,
    }


def evaluate(db_path: Path = DB_PATH, *, now: datetime | None = None,
             checkpoint_root: Path = CHECKPOINTS) -> dict:
    scope = fixed_scope()
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(TOKYO).date().isoformat()
    db = sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        summary = _logical_summary(db)
        batch = db.execute('SELECT scope_sha256,stopped FROM call_batches WHERE batch_id=?', (BATCH,)).fetchone() if _table_exists(db, 'call_batches') else None
        if batch is not None:
            ensure(batch['scope_sha256'] == digest(scope), 'Registered natural-day scope differs from frozen scope')
        rows = []
        if _table_exists(db, 'provider_calls'):
            rows = [dict(r) for r in db.execute('''SELECT p.call_id,p.slot_id,p.model,p.status,p.error_category,
                p.session_id,p.context_json,t.turn_id,t.user_text,t.status AS turn_status,t.display_at_utc,
                t.input_provenance,t.response_provenance FROM provider_calls p JOIN turns t USING(turn_id)
                WHERE p.batch_id=? ORDER BY p.submitted_at_utc''', (BATCH,))]
        displayed = [r for r in rows if r['status'] == 'RESPONSE_CAPTURED' and r['turn_status'] == 'DISPLAYED' and r['display_at_utc']]
        today_rows = [r for r in displayed if _date(r['display_at_utc']) == today]
        bad = [r for r in rows if r['status'] != 'RESPONSE_CAPTURED' or r['turn_status'] != 'DISPLAYED']
        sessions = sorted({r['session_id'] for r in rows})
        dates_from_calls = sorted({_date(r['display_at_utc']) for r in displayed})
        process_rows = []
        if len(sessions) == 1 and _table_exists(db, 'cli_process_runs'):
            process_rows = [dict(r) for r in db.execute(
                'SELECT process_id,session_id,started_at_utc,ended_at_utc,exit_code FROM cli_process_runs WHERE session_id=? ORDER BY started_at_utc',
                (sessions[0],))]
        distinct_pids = sorted({r['process_id'] for r in process_rows})
        model_sequence = [r['model'] for r in rows]
        commitment_retrieval_calls = []
        for r in rows:
            try:
                retrieval = json.loads(r['context_json']).get('retrieval', [])
            except (TypeError, json.JSONDecodeError):
                retrieval = []
            if any(isinstance(x, dict) and x.get('record_kind') == 'COMMITMENT' for x in retrieval):
                commitment_retrieval_calls.append(r['call_id'])
        commitments = summary['state'].get('commitments', {})
    finally:
        db.close()
    prior = _prior_dates(checkpoint_root)
    today_already_counted = today in prior
    qualifies = bool(today_rows) and not bad and len(sessions) == 1 and not today_already_counted and bool(batch) and batch['stopped'] == 0
    return {
        'observed_at_utc': now.astimezone(timezone.utc).isoformat(),
        'observed_local_date': today,
        'batch_registered': batch is not None,
        'batch_stopped': None if batch is None else batch['stopped'],
        'submitted_calls': len(rows),
        'displayed_calls': len(displayed),
        'today_displayed_calls': len(today_rows),
        'bad_or_unresolved_calls': [{'call_id': r['call_id'], 'slot_id': r['slot_id'], 'status': r['status'], 'turn_status': r['turn_status'], 'error_category': r['error_category']} for r in bad],
        'session_ids': sessions,
        'single_session_continuity': len(sessions) == 1 if rows else False,
        'model_sequence': model_sequence,
        'same_session_model_switch_observed': len(sessions) == 1 and 'deepseek-v4-flash' in model_sequence and 'deepseek-v4-pro' in model_sequence,
        'cli_processes_for_session': process_rows,
        'real_restart_observed': len(distinct_pids) >= 2 and all(r['ended_at_utc'] and r['exit_code'] == 0 for r in process_rows[:-1]),
        'commitments': commitments,
        'commitment_retrieval_call_ids': commitment_retrieval_calls,
        'commitment_retrieval_observed': bool(commitment_retrieval_calls),
        'displayed_local_dates_in_runtime': dates_from_calls,
        'prior_qualified_dates': prior,
        'today_already_counted': today_already_counted,
        'today_can_qualify': qualifies,
        'qualified_date_count_if_checkpointed': len(prior) + (1 if qualifies else 0),
        'initialization_counts_as_observation': False,
        'logical_summary': summary,
        'scope_sha256': digest(scope),
        'scope_path': SCOPE_PATH.relative_to(ROOT).as_posix(),
    }


def checkpoint(*, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    status = evaluate(now=now)
    ensure(status['today_can_qualify'], 'Today is not a new qualified real observation day')
    ensure(DB_PATH.is_file() and RELEASE.is_file() and INITIALIZATION.is_file(), 'Candidate release/initialization evidence missing')
    day = status['observed_local_date']
    destination = CHECKPOINTS / day
    ensure(not destination.exists(), 'Qualified checkpoint for this local date already exists')
    destination.mkdir(parents=True, exist_ok=False)
    backup = destination / 'content_backup'
    backup.mkdir()
    before_main_sha = sha(DB_PATH)
    source = sqlite3.connect(DB_PATH.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        before = _logical_summary(source)
        target = sqlite3.connect(backup / 'runtime.sqlite3')
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    ensure(sha(DB_PATH) == before_main_sha, 'Main candidate database bytes changed while checkpointing')
    if (RUNTIME / 'SANDBOX.json').is_file():
        shutil.copy2(RUNTIME / 'SANDBOX.json', backup / 'SANDBOX.json')
    shutil.copytree(RUNTIME / 'legacy_runtime', backup / 'legacy_runtime', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(SCOPE_PATH, backup / 'NATURAL_DAY_OBSERVATION_SCOPE.json')
    verify = sqlite3.connect((backup / 'runtime.sqlite3').resolve().as_uri() + '?mode=ro&immutable=1', uri=True)
    try:
        after = _logical_summary(verify)
    finally:
        verify.close()
    ensure(before == after, 'Checkpoint logical state differs from candidate runtime')
    qualified_dates = status['prior_qualified_dates'] + [day]
    record = {
        'qualified_observation_day': True,
        'observed_at_utc': status['observed_at_utc'],
        'observed_local_date': day,
        'timezone': 'Asia/Tokyo',
        'qualified_observation_dates': qualified_dates,
        'qualified_observation_day_count': len(qualified_dates),
        'minimum_distinct_real_local_dates': 3,
        'candidate_release_manifest': RELEASE.relative_to(ROOT).as_posix(),
        'candidate_release_manifest_sha256': sha(RELEASE),
        'candidate_initialization_checkpoint': INITIALIZATION.relative_to(ROOT).as_posix(),
        'candidate_initialization_checkpoint_sha256': sha(INITIALIZATION),
        'observation_scope': SCOPE_PATH.relative_to(ROOT).as_posix(),
        'observation_scope_sha256': sha(SCOPE_PATH),
        'session_ids': status['session_ids'],
        'single_session_continuity': status['single_session_continuity'],
        'submitted_calls': status['submitted_calls'],
        'displayed_calls': status['displayed_calls'],
        'today_displayed_calls': status['today_displayed_calls'],
        'model_sequence': status['model_sequence'],
        'same_session_model_switch_observed': status['same_session_model_switch_observed'],
        'real_restart_observed': status['real_restart_observed'],
        'cli_processes_for_session': status['cli_processes_for_session'],
        'commitments': status['commitments'],
        'commitment_retrieval_call_ids': status['commitment_retrieval_call_ids'],
        'commitment_retrieval_observed': status['commitment_retrieval_observed'],
        'bad_or_unresolved_calls': status['bad_or_unresolved_calls'],
        'runtime_logical_summary': after,
        'runtime_main_db_sha256_at_checkpoint': before_main_sha,
        'content_backup_manifest': file_entries(backup),
        'initialization_without_real_user_interaction_counts': False,
        'same_local_date_duplicate_counts': False,
        'product_acceptance_complete': False
    }
    dump(destination / 'CHECKPOINT.json', record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['status', 'checkpoint'])
    args = parser.parse_args()
    try:
        result = evaluate() if args.action == 'status' else checkpoint()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, sqlite3.Error, ObservationGuard, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'error': str(exc), 'provider_calls_submitted_by_tool': 0}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
