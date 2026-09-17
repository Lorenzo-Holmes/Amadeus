"""Versioned high-reasoning adapter and owned-worker deadlines, no API calls."""
from __future__ import annotations
import copy
import json
import subprocess
import sys
import time
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
CODE = ROOT / 'persona_core/operational_runtime_v1'
sys.path.insert(0, str(CODE))
from transcript_store import TranscriptStore, create_sandbox, StoreGuard, file_sha
from provider import ProviderJournal, ENDPOINT, RATES, canonical, scope_check, bounded_worker_transport
from context_router import build_context
from test_provider_r045 import scope as legacy_scope

OUT = ROOT / 'persona_core/operational_build_v1/evidence/R047-02' / ('provider_v2_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
WORKER_FIXTURE = Path(__file__).with_name('provider_worker_fixture_r047.py')

def scope():
    return {'schema_version': 'apcore-provider-scope-2', 'batch_id': 'OFFLINE_SCOPE_V2',
            'principal_id': 'OFFLINE_OPERATOR', 'purpose': 'Authored adapter fixtures, zero network',
            'endpoint': ENDPOINT, 'automatic_paid_retries': 0, 'pricing_verified_date': '2026-09-08',
            'pricing_sources': ['OFFLINE_FIXTURE'], 'max_input_bytes': 24576, 'max_output_tokens': 8192,
            'input_overhead_reserve_tokens': 4096, 'total_guard_cny': 1.0, 'reserved_upper_micro_cny': 638976,
            'thinking': {'type': 'enabled'}, 'reasoning_effort': 'max', 'stream': False, 'tools_allowed': False,
            'request_timeout_seconds': 240,
            'peak_rates_cny_per_million_tokens': {m: {'input_miss': v[0], 'output': v[1], 'input_hit': v[2]} for m, v in RATES.items()},
            'slots': [{'id': 'one', 'model': 'deepseek-v4-pro', 'entity_label': 'A', 'user_text': '第一轮问题'},
                      {'id': 'two', 'model': 'deepseek-v4-flash', 'entity_label': 'A', 'user_text': '第二轮追问'}]}

def response(model='deepseek-v4-pro', finish='stop', completion=1000, reasoning=900):
    return {'model': model, 'choices': [{'finish_reason': finish, 'message': {'role': 'assistant',
        'content': '这是具名的离线最终答复。', 'reasoning_content': 'AUTHORED_REASONING_MUST_NOT_ENTER_HISTORY'}}],
        'usage': {'prompt_tokens': 100, 'completion_tokens': completion, 'total_tokens': 100+completion,
                  'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 100,
                  'completion_tokens_details': {'reasoning_tokens': reasoning}}}

class V2Tests(unittest.TestCase):
    def setUp(self):
        self.root = create_sandbox(OUT / self._testMethodName)
        self.s = TranscriptStore(self.root)
        self.h = self.s.open_session('OFFLINE_OPERATOR', 'A')
        self.j = ProviderJournal(self.s)
        self.scope = scope()
        self.j.register_batch(self.scope)
        self.t = self.s.begin_turn(self.h, '第一轮问题', 'one')
        self.context = build_context(self.s, self.h, self.t['turn_id'])
        self.requests = []
    def tearDown(self):
        self.s.close()
    def transport(self, payload, credential):
        self.requests.append(json.loads(payload))
        return 200, canonical(response())
    def call(self, transport=None):
        return self.j.call(self.h, self.t['turn_id'], self.scope['batch_id'], 'one', self.context,
            transport=transport or self.transport, credential_reader=lambda: 'AUTHORED_NOT_REAL_KEY')
    def test_max_reasoning_payload_and_final_text_separated(self):
        result = self.call()
        self.assertEqual(result['status'], 'RESPONSE_CAPTURED')
        payload = self.requests[0]
        self.assertEqual(payload['thinking'], {'type': 'enabled'})
        self.assertEqual(payload['reasoning_effort'], 'max')
        self.assertEqual(payload['max_tokens'], 8192)
        self.assertNotIn('tools', payload)
        self.assertNotIn('temperature', payload)
        self.assertEqual(self.s.get_turn(self.h, self.t['turn_id'])['assistant_text'], '这是具名的离线最终答复。')
    def test_reasoning_usage_included_in_reserved_completion_bound(self):
        result = self.call()
        self.assertEqual(result['estimate_peak_micro_cny'], 100*9 + 1000*27)
        self.assertEqual(json.loads(result['usage_json'])['completion_tokens_details']['reasoning_tokens'], 900)
    def test_reasoning_content_preserved_in_raw_not_next_history(self):
        self.call()
        self.s.mark_displayed(self.h, self.t['turn_id'])
        next_turn = self.s.begin_turn(self.h, '第二轮追问', 'two')
        context = build_context(self.s, self.h, next_turn['turn_id'])
        self.assertNotIn('AUTHORED_REASONING_MUST_NOT_ENTER_HISTORY', json.dumps(context['messages']))
        raw = self.s.db.execute('SELECT raw_response FROM provider_calls').fetchone()[0]
        self.assertIn(b'AUTHORED_REASONING_MUST_NOT_ENTER_HISTORY', raw)
    def test_thinking_token_overflow_rejected(self):
        result = self.call(lambda p,k: (200, canonical(response(completion=8193, reasoning=8190))))
        self.assertEqual(result['error_category'], 'USAGE_EXCEEDS_RESERVED_BOUND')
    def test_invalid_reasoning_accounting_rejected(self):
        result = self.call(lambda p,k: (200, canonical(response(completion=10, reasoning=11))))
        self.assertEqual(result['error_category'], 'INVALID_REASONING_TOKEN_ACCOUNTING')
    def test_truncated_reasoning_not_silently_repaired(self):
        result = self.call(lambda p,k: (200, canonical(response(finish='length'))))
        self.assertEqual(result['status'], 'RESPONSE_REJECTED')
        again = self.call()
        self.assertEqual(again['call_id'], result['call_id'])
        self.assertEqual(self.requests, [])
    def test_empty_final_even_with_reasoning_is_rejected(self):
        body = response()
        body['choices'][0]['message']['content'] = ''
        self.assertEqual(self.call(lambda p,k: (200, canonical(body)))['error_category'], 'EMPTY_RESPONSE')
    def test_unknown_submission_stops_remaining_slots(self):
        self.call(lambda p,k: (_ for _ in ()).throw(TimeoutError('Authored deadline')))
        next_turn = self.s.begin_turn(self.h, '第二轮追问', 'two')
        with self.assertRaises(StoreGuard):
            self.j.call(self.h, next_turn['turn_id'], self.scope['batch_id'], 'two', build_context(self.s,self.h,next_turn['turn_id']),
                transport=self.transport, credential_reader=lambda: 'AUTHORED_NOT_REAL_KEY')
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0], 1)
    def test_same_slot_never_resends(self):
        first = self.call()
        self.assertEqual(self.call()['call_id'], first['call_id'])
        self.assertEqual(len(self.requests), 1)
    def test_config_change_after_registration_refused(self):
        changed = copy.deepcopy(self.scope)
        changed['reasoning_effort'] = 'high'
        with self.assertRaises(StoreGuard):
            self.j.register_batch(changed)
    def test_arbitrary_model_suffix_refused(self):
        result = self.call(lambda p,k: (200, canonical(response(model='deepseek-v4-pro-unapproved'))))
        self.assertEqual(result['error_category'], 'PROVIDER_MODEL_VERSION_NOT_RECOGNIZED')
    def test_explicit_provider_version_suffix_accepted(self):
        self.assertEqual(self.call(lambda p,k: (200,canonical(response(model='deepseek-v4-pro-0813'))))['status'], 'RESPONSE_CAPTURED')
    def test_flash_canonical_response_alias_accepted(self):
        self.call()
        self.s.mark_displayed(self.h, self.t['turn_id'])
        turn = self.s.begin_turn(self.h, '第二轮追问', 'two')
        context = build_context(self.s, self.h, turn['turn_id'])
        result = self.j.call(self.h, turn['turn_id'], self.scope['batch_id'], 'two', context,
            transport=lambda p,k: (200, canonical(response(model='deepseek-flash'))),
            credential_reader=lambda: 'AUTHORED_NOT_REAL_KEY')
        self.assertEqual(result['status'], 'RESPONSE_CAPTURED')
        self.assertEqual(result['provider_model'], 'deepseek-flash')
    def test_flash_alias_does_not_authorize_pro_substitution(self):
        result = self.call(lambda p,k: (200, canonical(response(model='deepseek-flash'))))
        self.assertEqual(result['error_category'], 'PROVIDER_MODEL_MISMATCH')
    def test_illegal_scope_variants_refused_before_network(self):
        mutations = [({'schema_version': 'unknown'}, 'version'), ({'total_guard_cny': 0.01}, 'cap'),
            ({'total_guard_cny': float('inf')}, 'unbounded'), ({'total_guard_cny': 51}, 'excessive'),
            ({'thinking': {'type': 'invented'}}, 'thinking'), ({'reasoning_effort': 'magic'}, 'effort'),
            ({'request_timeout_seconds': 241}, 'deadline'), ({'stream': True}, 'stream'),
            ({'tools_allowed': True}, 'tools'), ({'automatic_paid_retries': 1}, 'retry'),
            ({'endpoint': 'https://example.invalid'}, 'endpoint'), ({'pricing_verified_date': 'unknown'}, 'price-date')]
        for changes, label in mutations:
            with self.subTest(label=label):
                changed = copy.deepcopy(self.scope)
                changed.update(changes)
                with self.assertRaises(StoreGuard):
                    scope_check(changed)
    def test_tampered_peak_rates_refused(self):
        changed = copy.deepcopy(self.scope)
        changed['peak_rates_cny_per_million_tokens']['deepseek-v4-pro']['output'] = 1
        with self.assertRaises(StoreGuard):
            scope_check(changed)
    def test_legacy_contract_still_refuses_larger_output_or_budget(self):
        old = legacy_scope()
        scope_check(old)
        for change in [{'max_output_tokens': 8192}, {'total_guard_cny': 45}, {'schema_version': 'PREPARED_NOT_EXECUTABLE'}]:
            altered = copy.deepcopy(old)
            altered.update(change)
            with self.assertRaises(StoreGuard):
                scope_check(altered)
    def test_frozen_evaluation_scope_accepted_without_rewriting(self):
        p = ROOT / 'persona_core/operational_build_v1/evidence/R047-01/freeze_20260907T164424498856Z/EXECUTION_SCOPE.json'
        before = file_sha(p)
        frozen = json.loads(p.read_text(encoding='utf-8'))
        scope_check(frozen)
        self.assertEqual(len(frozen['slots']), 82)
        self.assertEqual(frozen['reserved_upper_micro_cny'], 37380096)
        self.assertEqual(file_sha(p), before)
    def test_switch_model_payload_uses_same_session_actual_history(self):
        self.call()
        self.s.mark_displayed(self.h, self.t['turn_id'])
        turn = self.s.begin_turn(self.h, '第二轮追问', 'two')
        context = build_context(self.s,self.h,turn['turn_id'])
        observed = []
        def transport(payload,key):
            observed.append(json.loads(payload))
            return 200,canonical(response(model='deepseek-v4-flash'))
        result = self.j.call(self.h,turn['turn_id'],self.scope['batch_id'],'two',context,
                             transport=transport,credential_reader=lambda: 'AUTHORED_NOT_REAL_KEY')
        self.assertEqual(result['session_id'], self.h.session_id)
        self.assertEqual(observed[0]['model'], 'deepseek-v4-flash')
        histories = [json.loads(m['content'].split('\n', 1)[1]) for m in observed[0]['messages'] if m['role'] == 'user' and m['content'].startswith('以下是按时间排列的历史逐轮原文')]
        self.assertEqual(histories, [[{'user': '第一轮问题', 'assistant': '这是具名的离线最终答复。'}]])

class WorkerTests(unittest.TestCase):
    def test_real_owned_worker_protocol_no_credential_in_arguments(self):
        command = [sys.executable,'-B',str(WORKER_FIXTURE),'success']
        with patch('provider._worker_command', return_value=command):
            status, raw = bounded_worker_transport(b'{"fixture":true}', 'AUTHORED_FAKE_SECRET', 5)
        result = json.loads(raw)
        self.assertEqual(status,200)
        self.assertFalse(result['credential_passed_in_argv'])
        self.assertNotIn('AUTHORED_FAKE_SECRET', json.dumps(command))
        self.assertNotIn(b'AUTHORED_FAKE_SECRET', raw)
    def test_actual_owned_stalled_child_is_terminated_at_deadline(self):
        command = [sys.executable,'-B',str(WORKER_FIXTURE),'stall']
        started = time.monotonic()
        with patch('provider._worker_command', return_value=command):
            with self.assertRaises(subprocess.TimeoutExpired):
                bounded_worker_transport(b'{}', 'AUTHORED_FAKE_SECRET', 0.25)
        self.assertLess(time.monotonic()-started, 4)
    def test_bad_worker_frame_is_not_accepted(self):
        command = [sys.executable,'-B',str(WORKER_FIXTURE),'invalid']
        with patch('provider._worker_command', return_value=command):
            with self.assertRaises(ValueError):
                bounded_worker_transport(b'{}', 'AUTHORED_FAKE_SECRET', 5)
    def test_worker_error_is_unknown_not_a_fake_model_response(self):
        command = [sys.executable,'-B',str(WORKER_FIXTURE),'error']
        with patch('provider._worker_command', return_value=command):
            with self.assertRaises(StoreGuard):
                bounded_worker_transport(b'{}', 'AUTHORED_FAKE_SECRET', 5)

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    sources = list(CODE.glob('*.py')) + [Path(__file__),WORKER_FIXTURE,Path(__file__).with_name('test_provider_r045.py')]
    with zipfile.ZipFile(OUT/'TESTED_SOURCE.zip','x',zipfile.ZIP_DEFLATED) as z:
        for p in sources:
            z.writestr(p.relative_to(ROOT).as_posix(),p.read_bytes())
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(V2Tests), unittest.defaultTestLoader.loadTestsFromTestCase(WorkerTests)])
    with (OUT/'TESTS.log').open('x',encoding='utf-8') as f:
        result = unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
    report = {'at_utc':datetime.now(timezone.utc).isoformat(),'tests':result.testsRun,'passed':result.wasSuccessful(),
              'failures':len(result.failures),'errors':len(result.errors),'target_calls':0,'network_calls':0,
              'origin':'AUTHORED_PROVIDER_DATA_AND_REAL_LOCAL_WORKER_DEADLINE_TESTS',
              'source_snapshot_sha256':file_sha(OUT/'TESTED_SOURCE.zip'),
              'tested_sources':[{'path':p.relative_to(ROOT).as_posix(),'sha256':file_sha(p)} for p in sources]}
    (OUT/'TESTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':OUT.relative_to(ROOT).as_posix(),'tests':result.testsRun,'passed':result.wasSuccessful()}))
    raise SystemExit(0 if result.wasSuccessful() else 1)

if __name__=='__main__':
    main()
