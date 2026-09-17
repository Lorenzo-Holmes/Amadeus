"""Versioned larger reasoning envelope, never real provider traffic."""
from __future__ import annotations
import copy
import json
import unittest
import zipfile
from pathlib import Path
import test_provider_v2_r047 as helpers
from provider import ProviderJournal, RATES, canonical, scope_check
from transcript_store import StoreGuard, file_sha

OUT = helpers.OUT


def extended_scope():
    scope = helpers.scope()
    scope.update(schema_version='apcore-provider-scope-3', batch_id='OFFLINE_CAPACITY_V3',
        capacity_policy_id='EXTENDED_MAX_REASONING_20260911',
        output_budget_includes_reasoning=True, automatic_capacity_escalation=False,
        max_output_tokens=131072, request_timeout_seconds=1200, total_guard_cny=6)
    scope['reserved_upper_micro_cny'] = sum((scope['max_input_bytes'] + scope['input_overhead_reserve_tokens']) * RATES[s['model']][0] +
        scope['max_output_tokens'] * RATES[s['model']][1] for s in scope['slots'])
    return scope


class CapacityTests(unittest.TestCase):
    tearDown = helpers.V2Tests.tearDown
    def setUp(self):
        self.root = helpers.create_sandbox(OUT / self._testMethodName)
        self.s = helpers.TranscriptStore(self.root)
        self.h = self.s.open_session('OFFLINE_OPERATOR', 'A')
        self.j = ProviderJournal(self.s)
        self.scope = extended_scope()
        self.j.register_batch(self.scope)
        self.t = self.s.begin_turn(self.h, '第一轮问题', 'capacity')
        self.context = helpers.build_context(self.s, self.h, self.t['turn_id'])
        self.requests = []
    def call(self, body):
        def transport(payload, key):
            self.requests.append(json.loads(payload))
            return 200, canonical(body)
        return self.j.call(self.h, self.t['turn_id'], self.scope['batch_id'], 'one', self.context,
                           transport=transport, credential_reader=lambda: 'AUTHORED_NOT_REAL_KEY')
    def test_extended_payload_preserves_max_reasoning_and_bounded_total(self):
        result = self.call(helpers.response(completion=10000, reasoning=9800))
        self.assertEqual(result['status'], 'RESPONSE_CAPTURED')
        self.assertEqual(self.requests[0]['max_tokens'], 131072)
        self.assertEqual(self.requests[0]['thinking'], {'type': 'enabled'})
        self.assertEqual(self.requests[0]['reasoning_effort'], 'max')
        self.assertEqual(result['estimate_peak_micro_cny'], 270900)
    def test_large_cap_does_not_accept_empty_final(self):
        body = helpers.response(completion=20, reasoning=20)
        body['choices'][0]['message']['content'] = ''
        result = self.call(body)
        self.assertEqual(result['status'], 'RESPONSE_REJECTED')
        self.assertEqual(result['error_category'], 'EMPTY_RESPONSE')
        self.assertEqual(result['estimate_peak_micro_cny'], 1440)
    def test_exhausted_large_budget_still_stops_without_retry(self):
        result = self.call(helpers.response(finish='length', completion=131072, reasoning=131072))
        self.assertEqual(result['error_category'], 'TRUNCATED_OR_OTHER_FINISH')
        repeated = self.call(helpers.response())
        self.assertEqual(repeated['call_id'], result['call_id'])
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.s.db.execute('SELECT stopped FROM call_batches').fetchone()[0], 1)
    def test_scope2_cannot_silently_gain_scope3_limits(self):
        for changes in ({'max_output_tokens': 131072}, {'request_timeout_seconds': 1200}, {'total_guard_cny': 120}):
            old = helpers.scope()
            old.update(changes)
            with self.assertRaises(StoreGuard):
                scope_check(old)
    def test_explicit_capacity_policy_is_required(self):
        for changes in ({'capacity_policy_id': 'USER_SAYS_APPROVED'}, {'output_budget_includes_reasoning': False}, {'automatic_capacity_escalation': True}):
            changed = copy.deepcopy(self.scope)
            changed.update(changes)
            with self.assertRaises(StoreGuard):
                scope_check(changed)
    def test_extended_finite_caps_are_enforced(self):
        for changes in ({'max_output_tokens': 131073}, {'request_timeout_seconds': 1201}, {'total_guard_cny': 151}, {'total_guard_cny': float('inf')}):
            changed = copy.deepcopy(self.scope)
            changed.update(changes)
            with self.assertRaises(StoreGuard):
                scope_check(changed)
    def test_full_worst_case_reserve_cannot_be_omitted(self):
        changed = copy.deepcopy(self.scope)
        changed['total_guard_cny'] = 1
        with self.assertRaises(StoreGuard):
            scope_check(changed)
        changed = copy.deepcopy(self.scope)
        changed['reserved_upper_micro_cny'] -= 1
        with self.assertRaises(StoreGuard):
            scope_check(changed)
    def test_higher_budget_does_not_authorize_tool_calls(self):
        body = helpers.response()
        body['choices'][0]['message']['tool_calls'] = [{'id': 'AUTHORED_TOOL'}]
        self.assertEqual(self.call(body)['error_category'], 'UNEXPECTED_TOOL_CALL')


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    files = list(helpers.CODE.glob('*.py')) + [Path(__file__), Path(helpers.__file__)]
    with zipfile.ZipFile(OUT / 'TESTED_SOURCE.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.writestr(path.relative_to(helpers.ROOT).as_posix(), path.read_bytes())
    with (OUT / 'TESTS.log').open('x', encoding='utf-8') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CapacityTests))
    report = {'tests': result.testsRun, 'passed': result.wasSuccessful(), 'failures': len(result.failures), 'errors': len(result.errors),
        'target_calls': 0, 'network_calls': 0, 'origin': 'AUTHORED_PROVIDER_FIXTURES_NOT_REAL_GENERATION',
        'tested_sources': [{'path': p.relative_to(helpers.ROOT).as_posix(), 'sha256': file_sha(p)} for p in files]}
    (OUT / 'TESTS.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': OUT.relative_to(helpers.ROOT).as_posix(), **{k: report[k] for k in ('tests', 'passed', 'errors', 'target_calls')}}))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
