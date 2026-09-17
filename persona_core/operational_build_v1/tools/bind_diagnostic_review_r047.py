"""Bind the explicitly written diagnostic judgments to actual raw responses."""
from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import r047_execution_common as common
from provider import digest
from review_validator_r047 import DIMENSIONS, bind_judgment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('notes', type=Path)
    args = parser.parse_args()
    notes = args.notes.resolve()
    common.ensure(notes.is_relative_to(common.ROOT), 'Review path outside workspace')
    review = common.read_json(notes)
    journal = (common.ROOT / review['journal']).resolve()
    scope_path = (common.ROOT / review['scope']).resolve()
    common.ensure(journal.is_relative_to(common.ROOT) and scope_path.is_relative_to(common.ROOT), 'Diagnostic input outside workspace')
    scope = common.read_json(scope_path)
    common.ensure(scope['batch_id'] == review['batch_id'], 'Wrong batch binding')
    db = sqlite3.connect(journal.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    judgments, state_checks = [], []
    try:
        db.execute('BEGIN')
        common.ensure(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'Diagnostic journal integrity failure')
        rows = {r['slot_id']: dict(r) for r in db.execute('SELECT p.*,t.assistant_text,t.user_text,t.status AS turn_status FROM provider_calls p JOIN turns t USING(turn_id) WHERE p.batch_id=?', (scope['batch_id'],))}
        common.ensure(set(rows) == {s['id'] for s in scope['slots']} == {t['slot_id'] for t in review['turn_reviews']}, 'Diagnostic coverage differs')
        for turn in review['turn_reviews']:
            row = rows[turn['slot_id']]
            slot = next(s for s in scope['slots'] if s['id'] == turn['slot_id'])
            common.ensure(row['capture_origin'] == 'TARGET_PROVIDER_CAPTURE' and row['status'] == 'RESPONSE_CAPTURED' and row['turn_status'] == 'DISPLAYED', 'Actual displayed target capture required')
            raw = json.loads(row['raw_response'])
            common.ensure(raw['choices'][0]['message']['content'] == row['assistant_text'] and raw['choices'][0]['finish_reason'] == 'stop', 'Actual final text changed')
            common.ensure(hashlib.sha256(row['raw_response']).hexdigest() == row['raw_sha256'], 'Raw capture changed')
            common.ensure(hashlib.sha256(row['request_json'].encode('utf-8')).hexdigest() == row['request_sha256'], 'Request binding failed')
            common.ensure(row['user_text'] == slot['user_text'], 'Fixed input changed')
            record = {'slot_id': row['slot_id'], 'case_id': slot['case_id'], 'answer': row['assistant_text'],
                'answer_sha256': hashlib.sha256(row['assistant_text'].encode('utf-8')).hexdigest(),
                'request_sha256': row['request_sha256'], 'raw_response_sha256': row['raw_sha256'],
                'context_sha256': digest(json.loads(row['context_json'])), 'status': row['status']}
            common.ensure(len(turn['judgments']) == 4, 'All four explicit judgments required')
            for dimension, item in zip(DIMENSIONS, turn['judgments']):
                common.ensure(len(item) == 4, 'Malformed explicit judgment')
                judgments.append(bind_judgment(record, {'criterion_id': dimension, 'verdict': item[0],
                    'quote': item[1], 'rationale': item[2], 'finding_ids': item[3]}, review['reviewer']))
            trace = json.loads(db.execute('SELECT trace_json FROM chat_traces WHERE turn_id=?', (row['turn_id'],)).fetchone()[0])
            expected_count = 0 if slot['id'] in {'N05_T3', 'N05_T4'} else 1
            expected_status = 'OPEN' if expected_count == 0 else 'FULFILLED'
            current = trace['state_after']
            common.ensure(current['relationship']['verified_completions'] == expected_count, 'Completion counter differs from reviewed observation')
            common.ensure({c['status'] for c in current['commitments'].values()} == {expected_status}, 'Actual contract state differs')
            state_checks.append({'slot_id': slot['id'], 'state': expected_status, 'completion_count': expected_count,
                                 'trace_sha256': digest(trace)})
        db.rollback()
    finally:
        db.close()
    report = {'at_utc': datetime.now(timezone.utc).isoformat(), 'batch_id': scope['batch_id'],
        'reviewer': review['reviewer'], 'bound_judgments': judgments, 'state_checks': state_checks,
        'reviewed_turns': len(rows), 'criteria_reviewed': len(judgments),
        'review_notes_sha256': common.file_sha(notes), 'scope_sha256': common.file_sha(scope_path),
        'journal_sha256': common.file_sha(journal),
        'diagnostic_capture_and_binding_passed': True,
        'local_diagnostic_semantic_criteria_pass': all(j['verdict'] == 'PASS' for j in judgments),
        'semantic_judgments_generated_by_this_tool': False,
        'full_82_acceptance_complete': False, 'independent_review_complete': False,
        'capacity_increase_is_proven_cause': False}
    out = notes.parent / ('BOUND_DIAGNOSTIC_REVIEW_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    with out.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'output': out.relative_to(common.ROOT).as_posix(), 'turns': len(rows), 'criteria': len(judgments),
                      'diagnostic_pass': report['local_diagnostic_semantic_criteria_pass'], 'full_82_acceptance_complete': False}))


if __name__ == '__main__':
    main()
