"""Prepare isolated, provenance-labelled fixtures and a no-network preflight.

No target assistant history is prewritten. Historical setup is explicitly
AUTHORED_TEST_STUB in separate fixture sessions, per the frozen contract.
"""
from __future__ import annotations
import json
import sqlite3
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from r047_execution_common import *
from transcript_store import TranscriptStore, create_sandbox, utc_now
from admission import AdmissionController
from runtime_store import RuntimeStore
from retrieval import RetrievalService
from provider import ProviderJournal, digest
from context_router import build_context
from recovery import create_backup, restore_backup

def session(store, principal, label, kind):
    key = 'r047_session:' + kind + ':' + label
    row = store.db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
    if row:
        return store.resume(principal, row[0])
    handle = store.open_session(principal, label)
    with store.transaction():
        store.db.execute('INSERT INTO metadata VALUES(?,?)', (key, handle.session_id))
    return handle

def authored(store, controller, handle, text, reply, key, observe=True):
    turn = store.begin_turn(handle, text, 'AUTHORED_SETUP:' + key)
    store.capture_reply(handle, turn['turn_id'], reply, 'AUTHORED_SETUP_' + digest(key), origin='AUTHORED_TEST_STUB')
    store.mark_displayed(handle, turn['turn_id'])
    result = controller.observe_turn(handle, turn['turn_id']) if observe else None
    return turn['turn_id'], result

def main():
    scope, cases, fixture, frozen = load_frozen()
    gates = check_required_gates()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = PLAN / 'evidence/R047-02' / ('preflight_' + stamp)
    out.mkdir(parents=True, exist_ok=False)
    if not LIVE.exists():
        create_sandbox(LIVE)
    store = TranscriptStore(LIVE)
    report = {'at_utc': utc_now(), 'gates': gates, 'scope_sha256': frozen['scope_sha256'],
              'target_calls': 0, 'setup_origin': 'AUTHORED_TEST_SETUP_NOT_PRODUCTION', 'passed': False}
    try:
        journal = ProviderJournal(store)
        ensure(store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0] == 0, 'Preparation cannot alter a runtime after target submission')
        journal.register_batch(scope)
        controller = AdmissionController(store)
        runtime = RuntimeStore(store, controller)
        principal = scope['principal_id']
        fixture_rows = []
        foreign_data = fixture['foreign_private_record']
        forbidden_private = foreign_data['user_statement']
        foreign = session(store, principal, foreign_data['entity_label'], 'history')
        tid, event = authored(store, controller, foreign,
            foreign_data['user_statement'],
            '此条为明确标记的合成布置，不是目标模型生成。', 'foreign-private')
        fixture_rows.append({'kind': 'FOREIGN_PRIVATE', 'turn_id': tid, 'event_id': event['commit']['event_id']})
        long = fixture['old_agreement']
        h = session(store, principal, long['entity_label'], 'history')
        p, _ = authored(store, controller, h, '我们约定' + long['name'] + '；验收内容：' + long['expected_submission'],
            '同意约定：' + long['name'], 'long-proposal')
        c, _ = authored(store, controller, h, '确认约定：' + long['name'],
            '只确认这份文字约定，尚未履约。', 'long-confirm')
        decision = controller.confirm_agreement(h, p, c, long['name'], long['expected_submission'])
        event = runtime.commit(h, decision)
        fixture_rows.append({'kind': 'OPEN_AGREEMENT', 'event_id': event['event_id'], 'proposal_turn_id': p, 'confirmation_turn_id': c})
        for i in range(long['same_entity_irrelevant_records_after_agreement']):
            authored(store, controller, h, '合成清点记录编号' + str(i) + '：普通纸盒数量为' + str(i+1) + '。',
                     '这是中性历史布置文字。', 'long-neutral-' + str(i))
        correction = fixture['corrected_statement']
        h = session(store, principal, correction['entity_label'], 'history')
        old_tid, observed = authored(store, controller, h, correction['old_user_statement'],
            '保留为用户在合成历史中说过的内容。', 'correction-old')
        old_event = observed['commit']['event_id']
        new_tid, _ = authored(store, controller, h, '更正为' + correction['corrected_current_statement'],
            '这也是明确标记的布置文字。', 'correction-new')
        prior = runtime.get_event(h, old_event)
        prior_correction = store.db.execute('SELECT superseded_by FROM retrieval_documents WHERE event_id=?', (old_event,)).fetchone()[0]
        if prior_correction:
            saved = runtime.get_event(h, prior_correction)
            ensure(saved['payload']['turn_id'] == new_tid and saved['payload']['replacement'] == correction['corrected_current_statement'],
                   'Existing correction differs from pinned fixture')
            correction_id = prior_correction
        else:
            decision = controller.correct_user_statement(h, old_event, new_tid, correction['corrected_current_statement'])
            correction_id = runtime.commit(h, decision)['event_id']
        fixture_rows.append({'kind': 'CORRECTED_STATEMENT', 'old_event_id': old_event, 'current_event_id': correction_id})
        for i in range(correction['same_entity_irrelevant_records']):
            authored(store, controller, h, '合成清点记录编号' + str(i) + '：普通卡片数量为' + str(i+1) + '。',
                     '这是与交接事项无关的布置。', 'correction-neutral-' + str(i))
        sessions = {}
        for case in cases['cases']:
            handle = session(store, principal, case['entity_label'], 'target')
            ensure(not store.recent(handle, 1), 'Target session must have no authored assistant history')
            sessions[case['id']] = {'session_id': handle.session_id, 'entity_id': handle.entity_id, 'entity_label': case['entity_label']}
        q = RetrievalService(runtime)
        n09 = store.resume(principal, sessions['N09']['session_id'])
        n10 = store.resume(principal, sessions['N10']['session_id'])
        q09 = q.search(n09, '潮汐目录的约定')
        ensure(any(r.get('agreed_submission_requirement') == long['expected_submission'] and r.get('status') == 'OPEN' for r in q09), 'Long agreement fixture retrieval failed')
        q10 = q.search(n10, '星图交接点')
        ensure(any(r['record_kind'] == 'FACT_CORRECTED' and r['content'] == correction['corrected_current_statement'] for r in q10), 'Corrected fixture retrieval failed')
        ensure(not q.search(store.resume(principal, sessions['N04']['session_id']), forbidden_private), 'Foreign fixture leaked')
        counts = {}
        for case_id, label in [('N09', long['entity_label']), ('N10', correction['entity_label'])]:
            eid = sessions[case_id]['entity_id']
            count = store.db.execute("SELECT count(*) FROM turns t JOIN sessions s USING(session_id) WHERE s.entity_id=? AND t.idempotency_key LIKE ?",
                (eid, 'AUTHORED_SETUP:' + ('long-neutral-%' if case_id == 'N09' else 'correction-neutral-%'))).fetchone()[0]
            ensure(count >= 120, 'Long-history fixture has fewer than120 actual persisted distractors')
            counts[case_id] = count
        report.update(fixture_records=fixture_rows, sessions=sessions, runtime_verification=runtime.verify(),
                      fixture_retrieval={'N09': q09, 'N10': q10}, actual_distractor_counts=counts)
        backup = create_backup(store, runtime, out / 'FIXTURE_CONTENT_BACKUP')
        report['fixture_backup'] = backup
        probe_root = out / 'CONTEXT_PROBE_NOT_TARGET_HISTORY'
        restore_backup(backup['backup_root'], probe_root, backup['manifest_sha256'])
        probe = TranscriptStore(probe_root)
        context_checks = []
        try:
            qr = RetrievalService(RuntimeStore(probe, AdmissionController(probe)))
            for slot in scope['slots']:
                h = probe.resume(principal, sessions[slot['case_id']]['session_id'])
                t = probe.begin_turn(h, slot['user_text'], 'CONTEXT_PROBE:' + slot['id'])
                packet = build_context(probe, h, t['turn_id'], memory_provider=qr, max_prompt_bytes=scope['max_input_bytes'])
                encoded = json.dumps(packet['messages'], ensure_ascii=False)
                ensure('SABLE-COPPER-47' not in encoded and '书房三层' not in encoded, 'Foreign private context leak')
                ensure('private_expectations' not in encoded and 'R047_PRIVATE_RUBRIC_NEVER_SEND_TO_TARGET' not in encoded, 'Private rubric in context')
                context_checks.append({'slot_id': slot['id'], 'prompt_bytes': packet['prompt_bytes'],
                                       'retrieval_count': len(packet['retrieval']), 'route': packet['route']})
        finally:
            probe.close()
        report['context_checks'] = context_checks
        report['context_probe_is_target_generation'] = False
        ensure(store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0] == 0, 'Preflight unexpectedly submitted a provider call')
        ensure(all(not store.recent(store.resume(principal, s['session_id']), 1) for s in sessions.values()), 'Probe contaminated target sessions')
        report['tested_sources'] = source_bindings()
        with zipfile.ZipFile(out / 'EXECUTION_SOURCE.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
            for source in sources():
                archive.writestr(source.relative_to(ROOT).as_posix(), source.read_bytes())
        report['source_snapshot_sha256'] = file_sha(out / 'EXECUTION_SOURCE.zip')
        report['passed'] = True
        with (LIVE / 'FIXTURE_PREPARATION.json').open('x', encoding='utf-8') as f:
            json.dump({'preflight_path': str(out.relative_to(ROOT)), 'sessions': sessions, 'fixture_origin': report['setup_origin'],
                       'scope_sha256': frozen['scope_sha256'], 'created_at_utc': utc_now()}, f, ensure_ascii=False, indent=2)
    finally:
        (out / 'PREFLIGHT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        store.close()
        print(json.dumps({'output': out.relative_to(ROOT).as_posix(), 'passed': report['passed'], 'target_calls': 0}))

if __name__ == '__main__':
    main()
