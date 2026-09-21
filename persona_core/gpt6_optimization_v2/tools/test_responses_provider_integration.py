from __future__ import annotations

import io
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
CODE = ROOT / "persona_core" / "operational_runtime_v1"
OLD = ROOT / "persona_core" / "operational_build_v1" / "tools"
sys.path[:0] = [str(CODE), str(OLD)]

import provider
import provider_transport as pt
import test_provider_v2_r047 as old


POLICY = {
    "version": pt.VERSION,
    "connect_timeout_seconds": 1,
    "read_timeout_seconds": 1,
    "worker_deadline_seconds": 4,
}


def responses_wire() -> bytes:
    created = {
        "type": "response.created",
        "sequence_number": 0,
        "response": {"id": "resp_test", "model": "deepseek-v4-pro", "status": "in_progress"},
    }
    delta = {"type": "response.output_text.delta", "sequence_number": 1, "delta": "这是具名的离线最终答复。"}
    completed = {
        "type": "response.completed",
        "sequence_number": 2,
        "response": {
            "id": "resp_test",
            "model": "deepseek-v4-pro",
            "status": "completed",
            "output": [{"type": "message", "role": "assistant", "content": [
                {"type": "output_text", "text": "这是具名的离线最终答复。"}
            ]}],
            "usage": {
                "input_tokens": 100,
                "input_tokens_details": {"cached_tokens": 10},
                "output_tokens": 20,
                "output_tokens_details": {"reasoning_tokens": 12},
                "total_tokens": 120,
            },
        },
    }
    def event(name, obj):
        return b"event: " + name.encode() + b"\n" + b"data: " + pt.encode(obj) + b"\n\n"
    return event("response.created", created) + event("response.output_text.delta", delta) + event("response.completed", completed)


def records():
    return [json.loads(block.split(b'data: ', 1)[1]) for block in responses_wire().strip().split(b'\n\n')]


def wire_records(values):
    return b''.join(b'event: '+v['type'].encode()+b'\ndata: '+pt.encode(v)+b'\n\n' for v in values)


def normalized(wire=None):
    assembly = pt.ResponsesAssembly(pt.Lifecycle())
    assembly.feed(wire or responses_wire())
    return assembly.body()


class Response:
    status = 200
    def __init__(self, wire):
        self.reader = io.BytesIO(wire)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return None
    def read1(self, n):
        return self.reader.read(min(n, 17))


class ResponsesTransportTests(unittest.TestCase):
    def test_formal_readiness_prepares_isolated_journal_and_refuses_second_scope(self):
        import uuid
        import shutil
        import responses_formal_readiness as formal
        runner = formal.runner
        token = 'AUTHOR_OFFLINE_'+uuid.uuid4().hex
        root = runner.GOAL / ('formal_responses_readiness_'+token)
        second = runner.GOAL / (root.name+'_second')
        freeze_root = runner.ROOT/'work'/token
        freeze_root.mkdir()
        freeze_path = freeze_root/'SOURCE_MANIFEST.json'
        runner.write_new(freeze_path, {'core_status': 'FROZEN_FOR_VALIDATION', 'offline_integration_passed': True,
                                       'files': runner.source_bindings()})
        price = runner.checked_pricing(None, True)
        try:
            with patch.object(runner, 'checked_pricing', return_value=price):
                result = formal.prepare(root, freeze_path, None)
                self.assertEqual(result['provider_requests'], 0)
                prep = runner.read(root/'PREPARATION.json')
                self.assertEqual(runner.ROOT/prep['runtime'], formal.runtime_root(root))
                import sqlite3
                from contextlib import closing
                with closing(sqlite3.connect(formal.runtime_root(root)/'runtime.sqlite3')) as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM provider_calls').fetchone()[0], 0)
                with self.assertRaisesRegex(ValueError, 'ONE_FORMAL_READINESS_PER_FREEZE'):
                    formal.prepare(second, freeze_path, None)
                self.assertFalse(second.exists())
        finally:
            for path in (root, formal.runtime_root(root).parent, freeze_root):
                self.assertTrue(path.resolve().is_relative_to(runner.ROOT.resolve()))
                self.assertIn(token, path.name)
                if path.exists(): shutil.rmtree(path)

    def test_actual_worker_ipc_dispatches_responses_operation_without_network(self):
        child = (
            "import sys;sys.path[:0]="+repr([str(CODE), str(Path(__file__).parent)])+";"
            "import provider_transport as p,provider_http_worker as w;"
            "from test_responses_provider_integration import responses_wire,normalized;"
            "p.responses_http_exchange=lambda payload,key,policy,sink:p.TransportResult(200,normalized(),responses_wire());"
            "raise SystemExit(w.main())"
        )
        events = []
        result = pt.worker_exchange(pt.encode({'stream': True}), 'DUMMY', 5, POLICY,
            [sys.executable, '-X', 'utf8', '-B', '-c', child], ROOT, events.append, responses=True)
        self.assertEqual(result.body, normalized()); self.assertEqual(result.wire, responses_wire())
        self.assertEqual([e['event'] for e in events], ['child_started', 'child_exit', 'parent_receipt'])

    def test_completed_status_must_match_event(self):
        for status in ('failed', 'incomplete', 'in_progress', None):
            values = records(); values[-1]['response']['status'] = status
            with self.subTest(status=status), self.assertRaises(ValueError): normalized(wire_records(values))

    def test_final_and_streamed_text_must_both_exist_and_match(self):
        for change in ('no_delta', 'no_output', 'empty_output', 'changed_output', 'tool_output'):
            values = records()
            if change == 'no_delta': del values[1]
            elif change == 'no_output': del values[-1]['response']['output']
            elif change == 'empty_output': values[-1]['response']['output'] = []
            elif change == 'changed_output': values[-1]['response']['output'][0]['content'][0]['text'] = 'different'
            else: values[-1]['response']['output'].append({'type': 'function_call'})
            with self.subTest(change=change):
                body=json.loads(normalized(wire_records(values)))
                self.assertIn('responses_terminal_rejection',body)
                self.assertEqual(body['choices'][0]['message']['content'],'')

    def test_usage_structure_integer_bounds_and_totals(self):
        mutations = [('input_tokens', True), ('output_tokens', -1), ('total_tokens', 121),
                     ('input_tokens_details', []), ('output_tokens_details', 'invalid'),
                     ('input_tokens_details', {'cached_tokens': 101}),
                     ('input_tokens_details', {'cached_tokens': True}),
                     ('output_tokens_details', {'reasoning_tokens': 21})]
        for key, value in mutations:
            values = records(); values[-1]['response']['usage'][key] = value
            with self.subTest(key=key, value=value):
                body=json.loads(normalized(wire_records(values)))
                self.assertIn('responses_terminal_rejection',body)
                self.assertIsNone(body['usage'])
        values = records(); del values[-1]['response']['usage']
        self.assertIn('responses_terminal_rejection',json.loads(normalized(wire_records(values))))

    def test_identity_sequence_event_type_and_duplicate_json_fail_closed(self):
        for key, value in [('id', 'changed'), ('model', 'changed')]:
            values = records(); values[-1]['response'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): normalized(wire_records(values))
        for value in (True, 0, -1):
            values = records(); values[1]['sequence_number'] = value
            with self.subTest(sequence=value), self.assertRaises(ValueError): normalized(wire_records(values))
        with self.assertRaises(ValueError): normalized(responses_wire().replace(b'event: response.created', b'event: response.failed'))
        with self.assertRaises(ValueError): normalized(responses_wire().replace(b'"sequence_number":0', b'"sequence_number":0,"sequence_number":1'))
        values = records(); del values[0]['type']
        assembly = pt.ResponsesAssembly(pt.Lifecycle())
        with self.assertRaises(ValueError): assembly.record('response.created', pt.encode(values[0]))

    def test_missing_terminal_and_partial_trailing_record_fail_closed(self):
        with self.assertRaises(ValueError): normalized(wire_records(records()[:-1]))
        with self.assertRaises(ValueError): normalized(responses_wire()+b'data: {')

    def test_incomplete_and_failed_remain_non_successful_terminals(self):
        for status, finish in [('incomplete', 'length'), ('failed', 'aborted')]:
            values = records(); values[-1]['type'] = 'response.'+status; values[-1]['response']['status'] = status
            body = json.loads(normalized(wire_records(values)))
            self.assertEqual(body['choices'][0]['finish_reason'], finish)
            self.assertEqual(body['responses_api_status'], status)

    def test_later_socket_event_after_terminal_is_not_ignored(self):
        late = {'type': 'response.output_text.delta', 'sequence_number': 3, 'delta': 'late'}
        class Opener:
            def __init__(self, lifecycle): pass
            def open(self, *args, **kwargs): return Response(responses_wire()+wire_records([late]))
        with self.assertRaises(pt.TransportFault):
            pt.responses_http_exchange(pt.encode({'stream': True}), 'DUMMY', POLICY, opener_factory=Opener)

    def test_official_responses_stream_normalizes_to_existing_provider_contract(self):
        events = []
        class Opener:
            def __init__(self, lifecycle):
                self.lifecycle = lifecycle
            def open(self, *args, **kwargs):
                self.lifecycle.emit("first_response_header", http_status=200)
                return Response(responses_wire())
        payload = pt.encode({
            "model": "deepseek-v4-pro",
            "input": [{"role": "user", "content": "synthetic"}],
            "reasoning": {"effort": "max"},
            "max_output_tokens": 8192,
            "stream": True,
        })
        result = pt.responses_http_exchange(payload, "DUMMY", POLICY, events.append, opener_factory=Opener)
        body = json.loads(result.body)
        self.assertEqual(body["choices"][0]["finish_reason"], "stop")
        self.assertEqual(body["choices"][0]["message"]["content"], "这是具名的离线最终答复。")
        self.assertEqual(body["usage"]["prompt_cache_hit_tokens"], 10)
        self.assertEqual(body["usage"]["prompt_cache_miss_tokens"], 90)
        self.assertEqual(body["usage"]["completion_tokens_details"]["reasoning_tokens"], 12)
        self.assertIn("provider_finish", [event["event"] for event in events])


class ProviderJournalResponsesTests(unittest.TestCase):
    def setUp(self):
        self.root = old.create_sandbox(old.OUT / self._testMethodName)
        self.store = old.TranscriptStore(self.root)
        self.handle = self.store.open_session("OFFLINE_OPERATOR", "A")
        self.journal = provider.ProviderJournal(self.store)
        self.scope = old.scope()
        self.scope.update({
            "schema_version": "apcore-provider-scope-4",
            "endpoint": provider.RESPONSES_ENDPOINT,
            "api_protocol": "responses",
            "stream": True,
            "request_timeout_seconds": 5,
            "transport_policy": POLICY,
            "capacity_policy_id": "EXTENDED_MAX_REASONING_20260911",
            "output_budget_includes_reasoning": True,
            "automatic_capacity_escalation": False,
        })
        self.journal.register_batch(self.scope)
        self.turn = self.store.begin_turn(self.handle, "第一轮问题", "one")
        self.context = old.build_context(self.store, self.handle, self.turn["turn_id"])

    def tearDown(self):
        self.store.close()

    def test_provider_journal_builds_responses_payload_and_keeps_accounting(self):
        captured = {}
        body = json.loads(normalized())

        def fake_worker(payload, credential, total, policy, command, cwd, sink, *, catalogue=False, responses=False):
            captured["payload"] = json.loads(payload)
            captured["responses"] = responses
            sink({"event": "parent_receipt", "elapsed_ms": 1})
            return pt.TransportResult(200, provider.canonical(body), responses_wire())

        with patch.object(provider.lifecycle_transport, "worker_exchange", fake_worker):
            row = self.journal.call(
                self.handle,
                self.turn["turn_id"],
                self.scope["batch_id"],
                "one",
                self.context,
                credential_reader=lambda: "DUMMY",
            )
        self.assertEqual(row["status"], "RESPONSE_CAPTURED")
        self.assertTrue(captured["responses"])
        request = captured["payload"]
        self.assertEqual(request["input"], self.context["messages"])
        self.assertEqual(request["reasoning"], {"effort": "max"})
        self.assertEqual(request["max_output_tokens"], 8192)
        self.assertTrue(request["stream"])
        self.assertNotIn("messages", request)
        self.assertNotIn("thinking", request)
        self.assertNotIn("stream_options", request)
        self.assertEqual(self.store.get_turn(self.handle, self.turn["turn_id"])["assistant_text"], "这是具名的离线最终答复。")

    def test_scope4_requires_responses_endpoint_and_protocol(self):
        provider.scope_check(self.scope)
        bad = dict(self.scope)
        bad["endpoint"] = provider.ENDPOINT
        with self.assertRaises(old.StoreGuard):
            provider.scope_check(bad)

    def test_scope4_rejects_missing_policy_disabled_reasoning_and_unguarded_bounds(self):
        changes = [('api_protocol', 'chat_completions'), ('stream', False), ('thinking', {'type': 'disabled'}),
                   ('reasoning_effort', 'high'), ('automatic_paid_retries', 1),
                   ('max_output_tokens', 0), ('request_timeout_seconds', 0), ('total_guard_cny', float('inf'))]
        for key, value in changes:
            bad = copy.deepcopy(self.scope); bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): provider.scope_check(bad)
        bad = dict(self.scope); del bad['transport_policy']
        with self.assertRaises(ValueError): provider.scope_check(bad)

    def test_journal_first_unknown_stops_batch_and_turn_never_replays(self):
        attempts = []
        def interrupted(*args, **kwargs):
            attempts.append(1)
            import sqlite3
            with sqlite3.connect(self.root/'runtime.sqlite3') as db:
                self.assertEqual(db.execute('SELECT status FROM provider_calls').fetchone()[0], 'SUBMITTED_STATUS_UNKNOWN')
            raise pt.TransportFault('INACTIVITY_TIMEOUT', wire_records(records()[:-1]), 200)
        with patch.object(provider.lifecycle_transport, 'worker_exchange', interrupted):
            row = self.journal.call(self.handle, self.turn['turn_id'], self.scope['batch_id'], 'one', self.context, credential_reader=lambda: 'DUMMY')
            repeated = self.journal.call(self.handle, self.turn['turn_id'], self.scope['batch_id'], 'one', self.context, credential_reader=lambda: self.fail('must not read key again'))
        self.assertEqual(row['status'], 'SUBMITTED_STATUS_UNKNOWN'); self.assertEqual(row, repeated)
        self.assertEqual(len(attempts), 1)
        self.assertIsNone(self.store.get_turn(self.handle, self.turn['turn_id'])['assistant_text'])
        self.assertEqual(self.store.db.execute('SELECT stopped FROM call_batches').fetchone()[0], 1)
        capture = self.store.db.execute('SELECT * FROM transport_wire_captures').fetchone()
        self.assertEqual(capture['complete'], 0)
        self.assertEqual(capture['wire_sha256'], hashlib.sha256(capture['wire_bytes']).hexdigest())

    def test_terminal_rejection_never_becomes_assistant_reply(self):
        values = records(); values[-1]['type'] = 'response.incomplete'; values[-1]['response']['status'] = 'incomplete'
        wire = wire_records(values)
        with patch.object(provider.lifecycle_transport, 'worker_exchange', return_value=pt.TransportResult(200, normalized(wire), wire)):
            row = self.journal.call(self.handle, self.turn['turn_id'], self.scope['batch_id'], 'one', self.context, credential_reader=lambda: 'DUMMY')
        self.assertEqual(row['status'], 'RESPONSE_REJECTED_TERMINAL_KNOWN')
        self.assertIsNone(self.store.get_turn(self.handle, self.turn['turn_id'])['assistant_text'])
        self.assertEqual(row['finish_reason'], 'length')

    def test_raw_wire_binding_detects_tampering_before_candidate_or_blind_consumption(self):
        with patch.object(provider.lifecycle_transport, 'worker_exchange', return_value=pt.TransportResult(200, normalized(), responses_wire())):
            row = self.journal.call(self.handle, self.turn['turn_id'], self.scope['batch_id'], 'one', self.context, credential_reader=lambda: 'DUMMY')
        captured = dict(self.store.db.execute('SELECT * FROM provider_calls').fetchone())
        captured['user_text'] = self.turn['user_text']
        import candidate_day_v2 as gates
        gates.verify_protocol_capture(self.store.db, captured, self.scope)
        self.store.db.execute("UPDATE transport_wire_captures SET wire_sha256=?", ('0'*64,))
        with self.assertRaisesRegex(ValueError, 'WIRE_HASH'): gates.verify_protocol_capture(self.store.db, captured, self.scope)

    def test_old_scope_versions_keep_chat_completions_semantics(self):
        base = old.scope()
        provider.scope_check(base)
        v3 = copy.deepcopy(self.scope)
        v3.update(schema_version='apcore-provider-scope-3', endpoint=provider.ENDPOINT)
        del v3['api_protocol']; provider.scope_check(v3)
        v3['api_protocol'] = 'responses'
        with self.assertRaises(ValueError): provider.scope_check(v3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
