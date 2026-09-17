"""Read-only binding/coverage audit of actual R047 captures, not semantic scoring.

Every slot in the hash-verified scope remains in the denominator (82 for the
original full protocol). A named diagnostic may have a smaller scope, but its
completion never passes the full82 review compiler. Missing/failed/unknown
slots are explicit; this tool cannot create semantic PASS or quality scores.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from r047_execution_common import *
from provider import canonical, digest
from transcript_store import utc_now

def usage_totals(records):
    """An unknown submitted charge is not zero; unsubmitted slots are separate."""
    submitted = [r for r in records if r['status'] != 'NOT_SUBMITTED']
    missing = sum(r.get('peak_usage_estimate_micro_cny') is None for r in submitted)
    known = sum(r.get('peak_usage_estimate_micro_cny') or 0 for r in submitted) / 1e6
    return {'peak_usage_estimate_cny': None if missing else known,
            'known_peak_usage_subtotal_cny': known,
            'unestimated_submitted_call_count': missing,
            'estimate_complete': missing == 0}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--require-complete', action='store_true')
    args = p.parse_args()
    scope, cases, fixture, frozen = load_frozen()
    out = PLAN / 'evidence/R047-02' / ('audit_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir(parents=True, exist_ok=False)
    db = sqlite3.connect((LIVE / 'runtime.sqlite3').as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    findings, records = [], []
    def check(ok, code, slot=None):
        if not ok:
            findings.append({'code': code, 'slot_id': slot})
    try:
        db.execute('BEGIN')
        check(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'SQLITE_INTEGRITY_FAILURE')
        check(not db.execute('PRAGMA foreign_key_check').fetchall(), 'SQLITE_FOREIGN_KEYS_FAILURE')
        calls = [dict(r) for r in db.execute('SELECT * FROM provider_calls WHERE batch_id=? ORDER BY submitted_at_utc', (scope['batch_id'],))]
        by_slot = {r['slot_id']: r for r in calls}
        check(len(by_slot) == len(calls), 'DUPLICATE_SLOT')
        check(set(by_slot).issubset({s['id'] for s in scope['slots']}), 'OUT_OF_SCOPE_CALL')
        for slot in scope['slots']:
            record = {'slot_id': slot['id'], 'case_id': slot['case_id'], 'evaluation_phase': slot['evaluation_phase'],
                      'model_expected': slot['model'], 'user_text': slot['user_text'], 'status': 'NOT_SUBMITTED',
                      'semantic_verdict': 'UNREVIEWED', 'quality_scores': None}
            row = by_slot.get(slot['id'])
            if row is None:
                records.append(record)
                continue
            turn = dict(db.execute('SELECT * FROM turns WHERE turn_id=?', (row['turn_id'],)).fetchone())
            session = dict(db.execute('SELECT * FROM sessions WHERE session_id=?', (row['session_id'],)).fetchone())
            entity = dict(db.execute('SELECT * FROM entities WHERE entity_id=?', (session['entity_id'],)).fetchone())
            request = json.loads(row['request_json'])
            context = json.loads(row['context_json'])
            check(row['capture_origin'] == 'TARGET_PROVIDER_CAPTURE', 'AUTHORED_CAPTURE_NOT_REAL_TARGET', slot['id'])
            check(row['request_sha256'] == hashlib.sha256(row['request_json'].encode('utf-8')).hexdigest(), 'REQUEST_HASH_MISMATCH', slot['id'])
            check(request['model'] == slot['model'] and request['thinking'] == scope['thinking'] and request['reasoning_effort'] == scope['reasoning_effort']
                  and request['max_tokens'] == scope['max_output_tokens'] and request['stream'] is False and 'tools' not in request,
                  'REQUEST_PARAMETERS_DIFFER_FROM_FROZEN_SCOPE', slot['id'])
            check(session['principal_id'] == scope['principal_id'] and entity['label'] == slot['entity_label'] and session['mode'] == 'PRODUCT_RUNTIME',
                  'ACTOR_ENTITY_MODE_MISMATCH', slot['id'])
            check(turn['user_text'] == slot['user_text'] and request['messages'][-1] == {'role': 'user', 'content': slot['user_text']},
                  'FIXED_INPUT_MISMATCH', slot['id'])
            check(request['messages'] == context['messages'], 'REQUEST_CONTEXT_MISMATCH', slot['id'])
            serialized = json.dumps(request['messages'], ensure_ascii=False)
            check('SABLE-COPPER-47' not in serialized and '书房三层' not in serialized, 'FOREIGN_PRIVATE_FIXTURE_IN_INPUT', slot['id'])
            check('private_expectations' not in serialized and 'R047_PRIVATE_RUBRIC_NEVER_SEND_TO_TARGET' not in serialized,
                  'PRIVATE_RUBRIC_IN_INPUT', slot['id'])
            record.update(status=row['status'], call_id=row['call_id'], turn_id=row['turn_id'], session_id=row['session_id'],
                          entity_id=session['entity_id'], turn_status=turn['status'], request_sha256=row['request_sha256'],
                          context_sha256=digest(context), raw_response_sha256=row['raw_sha256'],
                          submitted_at_utc=row['submitted_at_utc'], response_at_utc=row['response_at_utc'],
                          error_category=row['error_category'], reserve_micro_cny=row['reserve_micro_cny'],
                          peak_usage_estimate_micro_cny=row['estimate_peak_micro_cny'], usage=json.loads(row['usage_json']) if row['usage_json'] else None,
                          answer=turn['assistant_text'], answer_sha256=hashlib.sha256((turn['assistant_text'] or '').encode('utf-8')).hexdigest(),
                          route=context['route'], retrieval=context['retrieval'], context=context,
                          history_messages_truncated=context['history_messages_truncated'])
            if row['raw_response'] is not None:
                check(row['raw_was_redacted'] == 0 and hashlib.sha256(row['raw_response']).hexdigest() == row['raw_sha256'], 'RAW_CAPTURE_CHANGED_OR_REDACTED', slot['id'])
                if row['status'] == 'RESPONSE_CAPTURED':
                    body = json.loads(row['raw_response'])
                    check(body['choices'][0]['message']['content'] == turn['assistant_text'], 'ACTUAL_ANSWER_TRANSCRIPT_MISMATCH', slot['id'])
                    check(body['usage'] == record['usage'], 'ACTUAL_USAGE_MISMATCH', slot['id'])
                    check(body['choices'][0]['finish_reason'] == 'stop', 'NONSTOP_FINISH', slot['id'])
            trace = db.execute('SELECT trace_json FROM chat_traces WHERE turn_id=?', (row['turn_id'],)).fetchone()
            if trace:
                record['chat_trace'] = json.loads(trace[0])
                check(record['chat_trace']['state_before'] is not None and record['chat_trace']['state_after'] is not None,
                      'MISSING_ACTUAL_STATE_TRACE', slot['id'])
                check(record['chat_trace']['events'].get('workflow_version') == 'EXPLICIT_DIALOGUE_EVIDENCE_46_1',
                      'FULL_ADMISSION_PATH_NOT_USED', slot['id'])
            elif turn['status'] == 'DISPLAYED':
                check(False, 'DISPLAYED_TURN_MISSING_EVENT_TRACE', slot['id'])
            previous = db.execute("SELECT assistant_text,response_provenance,turn_id FROM turns WHERE session_id=? AND seq<? AND status='DISPLAYED' ORDER BY seq DESC LIMIT 1",
                                  (row['session_id'], turn['seq'])).fetchone()
            if previous:
                check(previous['response_provenance'] == 'TARGET_PROVIDER_CAPTURE', 'AUTHORED_MAIN_ASSISTANT_HISTORY', slot['id'])
                check(any(m['role'] == 'assistant' and m['content'] == previous['assistant_text'] for m in request['messages']),
                      'IMMEDIATE_REAL_PRIOR_ANSWER_MISSING_FROM_CONTEXT', slot['id'])
                record['prior_actual_turn_id'] = previous['turn_id']
            for memory in context['retrieval']:
                check(memory.get('entity_id') in {None, session['entity_id']}, 'CROSS_ENTITY_RETRIEVAL', slot['id'])
                check(memory.get('provenance') in {'PRODUCT_RUNTIME','HOLD','SOURCE_FACT_ONLY','ENCODED_SOURCE_MEMORY'}, 'PROVENANCE_LOST', slot['id'])
            records.append(record)
        current = db.execute('SELECT state_json,state_sha256,next_sequence,last_event_sha256 FROM runtime_current WHERE singleton=1').fetchone()
        state = json.loads(current[0])
        check(digest(state) == current[1], 'CURRENT_STATE_HASH_MISMATCH')
        state_record = {'state': state, 'state_sha256': current[1], 'next_sequence': current[2], 'event_tail_sha256': current[3]}
        db.execute('ROLLBACK')
    finally:
        db.close()
    by_case = {}
    for record in records:
        by_case.setdefault(record['case_id'], []).append(record)
    switch_checks = []
    for case in cases['cases']:
        if not case.get('switch_tail'):
            continue
        done = [r for r in by_case[case['id']] if r['status'] != 'NOT_SUBMITTED']
        if done:
            check(len({r['session_id'] for r in done}) == 1 and len({r['entity_id'] for r in done}) == 1,
                  'MODEL_SWITCH_REINITIALIZED_IDENTITY', case['id'])
        switch_checks.append({'case_id': case['id'], 'submitted': len(done), 'same_session': len({r['session_id'] for r in done}) <= 1})
    counts = {status: sum(r['status'] == status for r in records) for status in sorted({r['status'] for r in records})}
    denominator = len(scope['slots'])
    complete = len(calls) == denominator and all(r['status'] == 'RESPONSE_CAPTURED' and r.get('turn_status') == 'DISPLAYED' for r in records)
    result = {'at_utc': utc_now(), 'frozen_denominator': denominator, 'submitted_calls': len(calls), 'status_counts': counts,
              'complete_captures_and_delivery': complete, 'binding_findings': findings, 'binding_checks_passed': not findings,
              'scope_sha256': frozen['scope_sha256'], 'switch_identity_checks': switch_checks,
              **usage_totals(records),
              'reserved_cny': sum(r.get('reserve_micro_cny') or 0 for r in records) / 1e6,
              'billing_verified': False, 'semantic_reviewed_turns': 0, 'quality_gate_passed': False,
              'records': records, 'runtime_state': state_record}
    with (out / 'CAPTURE_AUDIT.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    for case_id, rows in by_case.items():
        with (out / (case_id + '_REVIEW_INPUT.json')).open('x', encoding='utf-8') as f:
            json.dump({'case_id': case_id, 'case': next(c for c in cases['cases'] if c['id'] == case_id),
                       'records': rows, 'reviewer': 'NOT_YET_REVIEWED'}, f, ensure_ascii=False, indent=2)
    print(json.dumps({'output': out.relative_to(ROOT).as_posix(), 'counts': counts, 'binding_findings': findings,
                      'complete': complete, 'peak_usage_estimate_cny': result['peak_usage_estimate_cny']}, ensure_ascii=False))
    if args.require_complete:
        ensure(complete and not findings, 'Captured runtime evidence is incomplete or has binding findings; do not claim R047-02 passed')

if __name__ == '__main__':
    main()
