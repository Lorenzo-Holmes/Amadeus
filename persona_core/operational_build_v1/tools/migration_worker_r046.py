"""Owned test worker; authored provider only. No network or credentials used."""
from __future__ import annotations
import argparse
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'persona_core/operational_runtime_v1'))
from transcript_store import TranscriptStore, safe_root, ensure, utc_now
from provider import ENDPOINT, canonical
from operations import open_chat
from recovery import create_backup, restore_backup
from retrieval import RetrievalService
from runtime_store import RuntimeStore
from admission import AdmissionController
from migration import writer_compatibility

def scope() -> dict:
    return {'batch_id': 'R046_AUTHORED_INTEGRATION', 'principal_id': 'OFFLINE_OPERATOR',
            'purpose': 'Real process migration with authored transport; no real target call',
            'endpoint': ENDPOINT, 'automatic_paid_retries': 0, 'pricing_verified_date': '2026-09-07',
            'pricing_sources': ['OFFLINE_FIXTURE'], 'max_input_bytes': 24576, 'max_output_tokens': 600,
            'input_overhead_reserve_tokens': 4096, 'total_guard_cny': 1.0, 'reserved_upper_micro_cny': 182832,
            'slots': [{'id': 'one', 'model': 'deepseek-v4-flash', 'entity_label': 'A', 'user_text': None},
                      {'id': 'two', 'model': 'deepseek-v4-flash', 'entity_label': 'A', 'user_text': None}]}

def authored_transport(payload: bytes, credential: str):
    return 200, canonical({'model': 'deepseek-v4-flash', 'choices': [{'finish_reason': 'stop',
        'message': {'role': 'assistant', 'content': '这份文字清单的代号是棱镜；这里只确认我们说过的内容。'}}],
        'usage': {'prompt_tokens': 100, 'completion_tokens': 30, 'total_tokens': 130,
                  'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 100}})

def authored_turn(store, handle, text, reply):
    row = store.begin_turn(handle, text, uuid.uuid4().hex)
    store.capture_reply(handle, row['turn_id'], reply, 'AUTHORED_' + uuid.uuid4().hex, origin='AUTHORED_TEST_STUB')
    store.mark_displayed(handle, row['turn_id'])
    return row['turn_id']

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['initialize', 'continue', 'display_crash', 'display_recover'])
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = safe_root(args.root)
    store = TranscriptStore(root)
    report = {'pid': os.getpid(), 'action': args.action, 'started_at_utc': utc_now(),
              'target_model_calls': 0, 'fixture_origin': 'AUTHORED_TRANSPORT_NOT_REAL_MODEL'}
    try:
        existing = store.list_sessions('OFFLINE_OPERATOR')
        handle = store.resume('OFFLINE_OPERATOR', existing[0]['session_id']) if existing else store.open_session('OFFLINE_OPERATOR', 'A')
        report['schema_before_open'] = store.db.execute('PRAGMA user_version').fetchone()[0]
        chat = open_chat(store, handle, scope())
        runtime, controller = chat.admission.runtime, chat.admission
        report['session_id'] = handle.session_id
        sink = []
        text = '我们把文字清单的代号定为棱镜，只确认名字。'
        if args.action in {'initialize', 'display_crash'}:
            if args.action == 'display_crash':
                def crash_after_display(*unused):
                    print(json.dumps({'pid': os.getpid(), 'at_utc': utc_now(), 'fault': 'DISPLAY_ACK_BEFORE_ADMISSION'}, ensure_ascii=True), flush=True)
                    os._exit(79)
                controller.observe_turn = crash_after_display
            result = chat.send_text(text, 'INTEGRATION:one', slot_id='one', display=sink.append,
                transport=authored_transport, credential_reader=lambda: 'NOT_A_REAL_CREDENTIAL')
            report['chat_result'] = result
            terms, expected = '提交棱镜的三项校验条件', '同容器、同温度、同光照'
            t1 = authored_turn(store, handle, '我们约定' + terms + '；验收内容：' + expected, '同意约定：' + terms)
            t2 = authored_turn(store, handle, '确认约定：' + terms, '已确认的是文字约定，不是已经完成。')
            decision = controller.confirm_agreement(handle, t1, t2, terms, expected)
            runtime.commit(handle, decision)
            report['verification'] = runtime.verify()
        elif args.action == 'continue':
            result = chat.send_text('重启后，棱镜这份清单的约定是什么？', 'INTEGRATION:two', slot_id='two',
                display=sink.append, transport=authored_transport, credential_reader=lambda: 'NOT_A_REAL_CREDENTIAL')
            trace = json.loads(store.db.execute('SELECT trace_json FROM chat_traces WHERE turn_id=?', (result['turn_id'],)).fetchone()[0])
            histories = [json.loads(m['content'].split('\n', 1)[1]) for m in trace['context']['messages'] if m['role'] == 'user' and m['content'].startswith('以下是按时间排列的历史逐轮原文')]
            ensure(any(row == {'user': text, 'assistant': '这份文字清单的代号是棱镜；这里只确认我们说过的内容。'} for rows in histories for row in rows), 'Actual prior displayed output missing after restart')
            ensure(any(r['record_kind'] == 'COMMITMENT' for r in trace['context']['retrieval']), 'Old agreement not retrieved through actual chat context')
            commitment = next(iter(runtime.snapshot(handle)['commitments'].values()))
            tid = authored_turn(store, handle, '同容器、同温度、同光照', '本轮只核对文字提交。')
            runtime.commit(handle, controller.verify_text_submission(handle, commitment['commitment_id'], tid))
            before_query = RetrievalService(runtime).search(handle, '棱镜约定完成了吗')
            before_state = runtime.snapshot(handle)
            backup = create_backup(store, runtime, root.with_name(root.name + '_backup'))
            destination = root.with_name(root.name + '_restored')
            restored = restore_backup(backup['backup_root'], destination, backup['manifest_sha256'])
            s2 = TranscriptStore(destination)
            try:
                r2 = RuntimeStore(s2, AdmissionController(s2))
                h2 = s2.resume('OFFLINE_OPERATOR', handle.session_id)
                ensure(r2.snapshot(h2) == before_state, 'Restored scoped state differs')
                ensure(RetrievalService(r2).search(h2, '棱镜约定完成了吗') == before_query, 'Restored retrieval differs')
            finally:
                s2.close()
            report.update(chat_result=result, context_trace=trace, before_state=before_state,
                          backup=backup, restored=restored, verification=runtime.verify(),
                          rollback_to_old_writer=writer_compatibility(root, 45),
                          restored_state_and_retrieval_equal=True)
            ensure(report['rollback_to_old_writer']['write_allowed'] is False, 'Old writer accepted new schema')
        else:
            def must_not_call(*unused):
                raise AssertionError('A recovered displayed turn must not call the provider or display again')
            result = chat.send_text(text, 'INTEGRATION:one', slot_id='one', display=must_not_call,
                                    transport=must_not_call, credential_reader=must_not_call)
            ensure(result['status'] == 'ALREADY_DISPLAYED', 'Unexpected recovery result')
            ensure(runtime.verify()['events'] == 1, 'Missing or duplicate recovered observation')
            ensure(store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0] == 1, 'Recovery duplicated provider intent')
            again = chat.send_text(text, 'INTEGRATION:one', slot_id='one', display=must_not_call,
                                  transport=must_not_call, credential_reader=must_not_call)
            ensure(runtime.verify()['events'] == 1, 'Second recovery duplicated observation')
            report.update(chat_result=result, second_recovery=again, verification=runtime.verify(),
                          provider_calls=1, new_provider_submissions=0, new_displays=0)
        report['finished_at_utc'] = utc_now()
        with (root / ('WORKER_' + args.action + '.json')).open('x', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(json.dumps({'pid': report['pid'], 'action': args.action, 'session_id': handle.session_id,
                          'events': runtime.verify()['events'], 'target_model_calls': 0}), flush=True)
        return 0
    finally:
        store.close()

if __name__ == '__main__':
    raise SystemExit(main())
