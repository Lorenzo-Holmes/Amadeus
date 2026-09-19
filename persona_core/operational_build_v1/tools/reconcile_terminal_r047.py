"""Snapshot real journals and reconcile terminal executions without network I/O.

Never changes a journal, batch stop flag, raw capture, or canonical task file.
Reported usage is an estimate at each batch's frozen guard rates, not billing.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import zipfile
from collections import Counter
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / 'persona_core/operational_build_v1'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value) -> None:
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def usage_estimate(usage, rates):
    if not isinstance(usage, dict):
        raise ValueError('USAGE_MISSING')
    for name in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
        if type(usage.get(name)) is not int or usage[name] < 0:
            raise ValueError('INVALID_USAGE')
    if usage['total_tokens'] != usage['prompt_tokens'] + usage['completion_tokens']:
        raise ValueError('USAGE_TOTAL_MISMATCH')
    hit = usage.get('prompt_cache_hit_tokens', 0)
    miss = usage.get('prompt_cache_miss_tokens', usage['prompt_tokens'] - hit)
    if type(hit) is not int or type(miss) is not int or min(hit, miss) < 0 or hit + miss != usage['prompt_tokens']:
        raise ValueError('CACHE_USAGE_MISMATCH')
    details = usage.get('completion_tokens_details')
    if details is not None:
        if not isinstance(details, dict):
            raise ValueError('INVALID_COMPLETION_DETAILS')
        reasoning = details.get('reasoning_tokens')
        if reasoning is not None and (type(reasoning) is not int or not 0 <= reasoning <= usage['completion_tokens']):
            raise ValueError('INVALID_REASONING_TOKEN_ACCOUNTING')
    amount = (Decimal(miss) * Decimal(str(rates['input_miss'])) +
              Decimal(hit) * Decimal(str(rates['input_hit'])) +
              Decimal(usage['completion_tokens']) * Decimal(str(rates['output'])))
    return int(amount.to_integral_value(rounding=ROUND_CEILING))


def unique_batch_guards(batches):
    """Copied journals do not create another authorization or another bill."""
    guards = {}
    for batch in batches:
        signature = (batch['scope_sha256'], Decimal(str(batch['guard_cny'])))
        old = guards.setdefault(batch['batch_id'], signature)
        if old != signature:
            raise ValueError('A copied batch has divergent scope or guard')
    return guards


def named_local_disposition(call_id, journal):
    """One explicitly investigated old worker error; never infer from timeout."""
    if call_id != 'call_65df5a4dbb844432bdad8e63a8c68db5':
        return None
    proof_path = PLAN / 'evidence/R047-03/capacity_probe_01/local_reconciliation_20260911T024206815047Z/RECONCILIATION.json'
    proof = json.loads(proof_path.read_text(encoding='utf-8'))
    if (ROOT / proof['journal']).resolve() != journal.resolve() or sha(journal) != proof['journal_sha256']:
        raise ValueError('Named local disposition journal binding changed')
    if proof['disposition'] != 'LOCAL_PRE_HTTP_CONFIGURATION_REJECTION_DETERMINISTICALLY_RECONCILED' or proof['original_status_rewritten']:
        raise ValueError('Invalid local reconciliation disposition')
    for filename, key in [('BOUND_ORIGINAL_WORKER.py', 'worker_bound_sha256'), ('BOUND_ORIGINAL_PROVIDER.py', 'provider_bound_sha256')]:
        if sha(proof_path.parent / filename) != proof[key]:
            raise ValueError('Local reconciliation source evidence changed')
    result = proof['controlled_process_result']
    if result['worker_exit_code'] != 2 or result['transport_attempts'] != 0 or result['socket_events']:
        raise ValueError('Pre-HTTP controlled replay does not support disposition')
    return {'path': proof_path.relative_to(ROOT).as_posix(), 'sha256': sha(proof_path),
            'type': proof['disposition'], 'original_unknown_row_retained': True,
            'remote_receipt_or_independent_billing': False}


def main() -> int:
    now = datetime.now(timezone.utc)
    out = PLAN / 'evidence/R047-03' / ('reconciliation_' + now.strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir(parents=True, exist_ok=False)
    (out / 'journals').mkdir()
    journals = [
        PLAN / 'evidence/R045-03/live_01/runtime.sqlite3',
        PLAN / 'evidence/R045-04/repair_live_01/runtime.sqlite3',
        PLAN / 'evidence/R047-02/live_01/runtime.sqlite3',
    ]
    revisions = sorted(p for p in (PLAN / 'evidence/R047-03').iterdir()
                       if p.is_dir() and (p/'live/runtime.sqlite3').is_file())
    journals.extend(p / 'live/runtime.sqlite3' for p in revisions if (p / 'live/runtime.sqlite3').is_file())
    entries = [ROOT / name for name in ('AGENTS.md', 'AMADEUS_PERSONA_CORE_MASTER_GOAL.md',
               'PERSONA_CORE_PROGRESS.md', 'PERSONA_CORE_CONTINUATION_PROTOCOL.md', 'PERSONA_CORE_DECISION_LOG.md')]
    entries += [PLAN / name for name in ('TASK_STATE.json', 'ACCEPTANCE_MATRIX.json', 'START_HERE.md')]
    entries += sorted((ROOT / 'persona_core/operational_runtime_v1').glob('*.py'))
    entries += sorted((PLAN / 'tools').glob('*.py'))
    entries += sorted(p for p in (ROOT / 'persona_core/runtime').rglob('*')
                      if p.is_file() and '__pycache__' not in p.parts)
    entries += sorted(p for p in (PLAN / 'evidence/R047-01').rglob('*')
                      if p.is_file() and 'freeze_' in str(p.parent) and p.suffix in {'.json', '.zip'})
    entries = sorted(set(p for p in entries if p.is_file()))
    before = {p.relative_to(ROOT).as_posix(): sha(p) for p in entries}
    with zipfile.ZipFile(out / 'BEFORE_FILES.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in entries:
            archive.writestr(path.relative_to(ROOT).as_posix(), path.read_bytes())
    findings, batches, unique = [], [], {}
    for index, path in enumerate(journals):
        if not path.is_file():
            raise FileNotFoundError(path)
        original_hash = sha(path)
        wal = path.with_name(path.name + '-wal')
        wal_hash = sha(wal) if wal.is_file() else None
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        db.row_factory = sqlite3.Row
        snapshot = out / 'journals' / (str(index) + '.sqlite3')
        try:
            db.execute('BEGIN')
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Journal integrity failure: ' + str(path))
            backup = sqlite3.connect(snapshot)
            try:
                db.backup(backup)
                if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Snapshot integrity failure')
            finally:
                backup.close()
            active_rows = db.execute("SELECT key,value FROM metadata WHERE key IN ('r047_active_driver','r047_capacity_driver')").fetchall()
            active_value = {r[0]: r[1] for r in active_rows}
            runs = []
            for report in sorted((path.parent / 'execution_runs').glob('*/EXECUTION.json')):
                value = json.loads(report.read_text(encoding='utf-8'))
                runs.append({'path': report.relative_to(ROOT).as_posix(), 'sha256': sha(report),
                             **{k: value.get(k) for k in ('run_id', 'phase', 'pid', 'status', 'exit_code', 'finished_at_utc')}})
            for batch in db.execute('SELECT * FROM call_batches ORDER BY created_at_utc'):
                scope = json.loads(batch['scope_json'])
                rows = [dict(r) for r in db.execute('SELECT p.*,t.status AS turn_status FROM provider_calls p JOIN turns t USING(turn_id) WHERE p.batch_id=? ORDER BY submitted_at_utc', (batch['batch_id'],))]
                calls = []
                for row in rows:
                    capture = {'call_id': row['call_id'], 'slot_id': row['slot_id'], 'status': row['status'],
                               'turn_status': row['turn_status'], 'capture_origin': row['capture_origin'],
                               'model_requested': row['model'], 'model_returned': row['provider_model'],
                               'error_category': row['error_category'], 'http_status': row['http_status'],
                               'finish_reason': row['finish_reason'], 'recorded_peak_micro_cny': row['estimate_peak_micro_cny'],
                               'reserve_micro_cny': row['reserve_micro_cny'], 'request_sha256': row['request_sha256'],
                               'raw_sha256': row['raw_sha256'], 'reconciled_peak_micro_cny': None,
                               'submitted_at_utc': row['submitted_at_utc'], 'response_at_utc': row['response_at_utc']}
                    if hashlib.sha256(row['request_json'].encode('utf-8')).hexdigest() != row['request_sha256']:
                        raise ValueError('Request hash mismatch')
                    raw = row['raw_response']
                    if raw is not None and not row['raw_was_redacted']:
                        if hashlib.sha256(raw).hexdigest() != row['raw_sha256']:
                            raise ValueError('Raw response hash mismatch')
                        try:
                            body = json.loads(raw)
                            usage = body.get('usage')
                            saved_usage = json.loads(row['usage_json']) if row['usage_json'] else None
                            if saved_usage is not None and usage != saved_usage:
                                raise ValueError('Stored usage differs from raw capture')
                            rates = scope.get('peak_rates_cny_per_million_tokens', {}).get(row['model'])
                            if rates is None:
                                rates = {'input_miss': 3, 'input_hit': .1, 'output': 9} if row['model'] == 'deepseek-v4-flash' else {'input_miss': 9, 'input_hit': .3, 'output': 27}
                            capture['reconciled_peak_micro_cny'] = usage_estimate(usage, rates)
                            capture['usage'] = usage
                            content = body['choices'][0]['message'].get('content')
                            capture['final_content_characters'] = len(content) if isinstance(content, str) else None
                            capture['estimate_basis'] = 'RAW_CAPTURE_USAGE_AT_ORIGINAL_PINNED_GUARD_RATES_NOT_BILLING'
                        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
                            capture['estimate_unavailable_reason'] = type(error).__name__
                    local = named_local_disposition(row['call_id'], path) if row['status'] == 'SUBMITTED_STATUS_UNKNOWN' else None
                    if local is not None:
                        capture['reconciled_peak_micro_cny'] = 0
                        capture['local_disposition'] = local
                        capture['estimate_basis'] = 'LOCAL_PRE_HTTP_REJECTION_INFERRED_FROM_BOUND_SOURCE_AND_CONTROLLED_REPLAY_NOT_BILLING'
                    if local is None and capture['recorded_peak_micro_cny'] is None and capture['reconciled_peak_micro_cny'] is not None:
                        findings.append({'code': 'VALID_REJECTED_USAGE_OMITTED_FROM_OLD_ESTIMATE', 'batch_id': batch['batch_id'], 'call_id': row['call_id']})
                    signature = (row['request_sha256'], row['raw_sha256'])
                    if row['call_id'] in unique:
                        if unique[row['call_id']]['signature'] != signature:
                            raise ValueError('Duplicate call ID has divergent capture')
                    else:
                        unique[row['call_id']] = {'signature': signature, 'estimate': capture['reconciled_peak_micro_cny'],
                            'raw_status': row['status'], 'provider_response_present': raw is not None,
                            'local_disposition': local}
                    calls.append(capture)
                batches.append({'batch_id': batch['batch_id'], 'journal': path.relative_to(ROOT).as_posix(),
                    'snapshot': snapshot.relative_to(ROOT).as_posix(), 'snapshot_sha256': sha(snapshot),
                    'scope_sha256': batch['scope_sha256'], 'fixed_slots': len(scope['slots']),
                    'submitted': len(rows), 'not_submitted': len(scope['slots']) - len(rows),
                    'counts': dict(Counter(r['status'] for r in rows)), 'stopped': bool(batch['stopped']),
                    'active_driver': active_value, 'unknown_submissions': sum(r['status'] == 'SUBMITTED_STATUS_UNKNOWN' for r in rows),
                    'guard_cny': scope['total_guard_cny'], 'calls': calls, 'execution_runs': runs,
                    'recorded_peak_subtotal_cny': sum(r['estimate_peak_micro_cny'] or 0 for r in rows) / 1e6,
                    'reconciled_peak_usage_estimate_cny': sum(c['reconciled_peak_micro_cny'] for c in calls) / 1e6 if all(c['reconciled_peak_micro_cny'] is not None for c in calls) else None})
            db.rollback()
        finally:
            db.close()
        if sha(path) != original_hash or (sha(wal) if wal.is_file() else None) != wal_hash:
            raise ValueError('Journal changed during snapshot; preserve evidence and reconcile again')
    after = {p.relative_to(ROOT).as_posix(): sha(p) for p in entries}
    if before != after:
        raise ValueError('Source changed during recovery snapshot')
    guards = unique_batch_guards(batches)
    report = {'at_utc': now.isoformat(), 'at_asia_tokyo': now.astimezone(timezone(timedelta(hours=9))).isoformat(),
              'batches': batches, 'findings': findings, 'unique_calls': len(unique),
              'reconciled_peak_usage_estimate_cny': sum(x['estimate'] for x in unique.values()) / 1e6 if all(x['estimate'] is not None for x in unique.values()) else None,
              'aggregate_guard_cny': float(sum((value[1] for value in guards.values()), Decimal(0))),
              'unique_batches': len(guards), 'batch_copies': len(batches),
              'unknown_submissions': sum(v['raw_status'] == 'SUBMITTED_STATUS_UNKNOWN' for v in unique.values()),
              'unresolved_remote_outcomes_after_named_local_reconciliation': sum(v['raw_status'] == 'SUBMITTED_STATUS_UNKNOWN' and v['local_disposition'] is None for v in unique.values()),
              'locally_reconciled_pre_http_attempts': sum(v['local_disposition'] is not None for v in unique.values()),
              'unique_provider_response_calls': sum(v['provider_response_present'] for v in unique.values()),
              'raw_journals_modified': False, 'source_files_modified': False, 'source_hashes': before,
              'canonical_updated_by_this_tool': False, 'new_target_calls': 0,
              'billing_verified': False, 'semantic_acceptance': False,
              'build_scope_complete': False, 'product_acceptance_complete': False}
    dump(out / 'RECONCILIATION.json', report)
    dump(out / 'SNAPSHOT_MANIFEST.json', {'files_zip_sha256': sha(out / 'BEFORE_FILES.zip'),
         'source_files': before, 'reconciliation_sha256': sha(out / 'RECONCILIATION.json')})
    print(json.dumps({'output': out.relative_to(ROOT).as_posix(), 'batches': len(batches),
                     **{k: report[k] for k in ('unique_calls', 'reconciled_peak_usage_estimate_cny', 'aggregate_guard_cny', 'unknown_submissions', 'new_target_calls')},
                     'batch_counts': [{'batch_id': b['batch_id'], 'counts': b['counts']} for b in batches]}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
