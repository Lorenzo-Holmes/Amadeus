"""Direct text console; no process launcher and no automatic evaluation loop."""
from __future__ import annotations
import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from capture_export import export_calls
from chat import ChatService
from transcript_store import TranscriptStore, StoreGuard, WORKSPACE, ensure, utc_now

def main() -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description='Amadeus 中文文本入口。普通输入无需 tags 或事件 JSON。')
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--scope', type=Path, required=True)
    p.add_argument('--principal', required=True)
    p.add_argument('--entity', required=True)
    p.add_argument('--operations', action='store_true', help='Use schema46 transactional runtime, trusted admission and long-term retrieval')
    args = p.parse_args()
    scope_path = args.scope.resolve()
    ensure(scope_path.is_relative_to(WORKSPACE), 'Scope must be inside the workspace')
    scope = json.loads(scope_path.read_text(encoding='utf-8'))
    store = TranscriptStore(args.root)
    run_id = None
    exit_code = 2
    try:
        sessions = [s for s in store.list_sessions(args.principal) if s['label'] == args.entity]
        handle = (store.resume(args.principal, sessions[-1]['session_id']) if sessions
                  else store.open_session(args.principal, args.entity))
        if args.operations:
            from operations import open_chat
            service = open_chat(store, handle, scope)
        else:
            service = ChatService(store, handle, scope)
        store.db.execute('''CREATE TABLE IF NOT EXISTS cli_process_runs(
          run_id TEXT PRIMARY KEY, process_id INTEGER NOT NULL,
          session_id TEXT NOT NULL REFERENCES sessions(session_id),
          started_at_utc TEXT NOT NULL, ended_at_utc TEXT, exit_code INTEGER)''')
        run_id = 'cli_' + uuid.uuid4().hex
        with store.transaction():
            store.db.execute('INSERT INTO cli_process_runs VALUES(?,?,?,?,NULL,NULL)',
                             (run_id, os.getpid(), handle.session_id, utc_now()))
        print('Amadeus 文本候选；/help 查看命令，/exit 退出。', flush=True)
        print('SESSION ' + handle.session_id, flush=True)
        for line in sys.stdin:
            text = line.rstrip('\r\n')
            if not text.strip():
                continue
            if text in {'/exit', '/quit'}:
                exit_code = 0
                return 0
            if text == '/help':
                print('/status 状态；/sessions 本操作者会话；/inspect 查看上次原始答复（不重发）；/exit 退出。', flush=True)
                continue
            if text == '/status':
                print(json.dumps(service.status(), ensure_ascii=False), flush=True)
                continue
            if text == '/sessions':
                print(json.dumps(store.list_sessions(args.principal), ensure_ascii=False), flush=True)
                continue
            if text == '/inspect':
                print(json.dumps(service.inspect_last(), ensure_ascii=False), flush=True)
                continue
            if text.startswith('/'):
                print('未知控制命令。', flush=True)
                continue
            slot = service.next_slot(text)
            result = service.send_text(text, scope['batch_id'] + ':' + slot['id'], slot_id=slot['id'],
                display=lambda answer: print('Amadeus：' + answer, flush=True))
            export_calls(store, store.root / 'captures')
            if result['status'] != 'DISPLAYED':
                print('本轮未展示：' + result['status'] + '。不会自动重发。', flush=True)
                return 2
        exit_code = 0
        return 0
    except (StoreGuard, OSError, ValueError) as exc:
        print('入口停止：' + type(exc).__name__ + '；请核对本地记录，不会自动重发。', file=sys.stderr, flush=True)
        return 2
    finally:
        if run_id is not None:
            with store.transaction():
                store.db.execute('UPDATE cli_process_runs SET ended_at_utc=?,exit_code=? WHERE run_id=?',
                                 (utc_now(), exit_code, run_id))
        store.close()

if __name__ == '__main__':
    raise SystemExit(main())
