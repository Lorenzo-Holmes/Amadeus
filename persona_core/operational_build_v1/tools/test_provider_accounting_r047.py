"""Offline failure/usage regression; neither reads credentials nor calls an API."""
from __future__ import annotations
import copy
import json
import unittest
import zipfile
from pathlib import Path
import test_provider_v2_r047 as helpers
from provider import canonical, ProviderJournal
from transcript_store import StoreGuard, file_sha
from reconcile_terminal_r047 import unique_batch_guards, usage_estimate

OUT = helpers.OUT


class AccountingTests(unittest.TestCase):
    setUp, tearDown = helpers.V2Tests.setUp, helpers.V2Tests.tearDown
    call, transport = helpers.V2Tests.call, helpers.V2Tests.transport

    def send_body(self, body):
        def captured(payload, key):
            self.requests.append(json.loads(payload))
            return 200, canonical(body)
        return self.call(captured)

    def test_empty_final_retains_cost_and_raw_but_not_answer(self):
        body = helpers.response(completion=72, reasoning=72)
        body['choices'][0]['message']['content'] = ''
        result = self.send_body(body)
        self.assertEqual(result['status'], 'RESPONSE_REJECTED')
        self.assertEqual(result['error_category'], 'EMPTY_RESPONSE')
        self.assertEqual(result['estimate_peak_micro_cny'], 100 * 9 + 72 * 27)
        self.assertEqual(self.s.db.execute('SELECT raw_response FROM provider_calls').fetchone()[0], canonical(body))
        self.assertIsNone(self.s.get_turn(self.h, self.t['turn_id'])['assistant_text'])
        self.assertEqual(self.s.db.execute('SELECT stopped FROM call_batches').fetchone()[0], 1)
        self.assertTrue(self.j.summary(self.scope['batch_id'])['estimate_complete'])

    def test_rejected_slot_never_reads_key_or_resubmits(self):
        body = helpers.response()
        body['choices'][0]['message']['content'] = ''
        first = self.send_body(body)
        def forbidden(*args):
            raise AssertionError('Unexpected credential access or transport retry')
        again = self.j.call(self.h, self.t['turn_id'], self.scope['batch_id'], 'one', self.context,
                            transport=forbidden, credential_reader=forbidden)
        self.assertEqual(first['call_id'], again['call_id'])
        self.assertEqual(len(self.requests), 1)

    def test_stopped_batch_still_blocks_new_slot(self):
        body = helpers.response()
        body['choices'][0]['message']['content'] = ''
        self.send_body(body)
        turn = self.s.begin_turn(self.h, '第二轮追问', 'second')
        context = helpers.build_context(self.s, self.h, turn['turn_id'])
        with self.assertRaises(StoreGuard):
            self.j.call(self.h, turn['turn_id'], self.scope['batch_id'], 'two', context,
                        transport=self.transport, credential_reader=lambda: 'AUTHORED_NOT_REAL_KEY')
        self.assertEqual(len(self.requests), 1)

    def test_truncated_answer_still_accounts_reported_usage(self):
        result = self.send_body(helpers.response(finish='length'))
        self.assertEqual(result['error_category'], 'TRUNCATED_OR_OTHER_FINISH')
        self.assertEqual(result['estimate_peak_micro_cny'], 27900)

    def test_whitespace_does_not_become_displayable_answer(self):
        body = helpers.response()
        body['choices'][0]['message']['content'] = ' \n\t '
        result = self.send_body(body)
        self.assertEqual(result['error_category'], 'EMPTY_RESPONSE')
        self.assertIsNotNone(result['estimate_peak_micro_cny'])

    def test_tool_call_is_rejected_but_usage_is_not_lost(self):
        body = helpers.response()
        body['choices'][0]['message']['tool_calls'] = [{'id': 'AUTHORED_TOOL'}]
        result = self.send_body(body)
        self.assertEqual(result['error_category'], 'UNEXPECTED_TOOL_CALL')
        self.assertEqual(result['estimate_peak_micro_cny'], 27900)

    def test_invalid_cache_usage_is_not_estimated(self):
        body = helpers.response()
        body['usage']['prompt_cache_hit_tokens'] = -1
        result = self.send_body(body)
        self.assertEqual(result['error_category'], 'CACHE_USAGE_MISMATCH')
        self.assertIsNone(result['estimate_peak_micro_cny'])

    def test_missing_estimate_is_not_reported_as_zero_total(self):
        self.call(lambda *_: (_ for _ in ()).throw(TimeoutError('AUTHORED')))
        summary = self.j.summary(self.scope['batch_id'])
        self.assertIsNone(summary['peak_usage_estimate_cny'])
        self.assertEqual(summary['known_peak_usage_subtotal_cny'], 0)
        self.assertEqual(summary['unestimated_call_count'], 1)
        self.assertFalse(summary['estimate_complete'])

    def test_malformed_message_is_terminal_captured_rejection(self):
        body = helpers.response()
        body['choices'][0]['message'] = None
        result = self.send_body(body)
        self.assertEqual(result['error_category'], 'INVALID_RESPONSE_MESSAGE')
        self.assertEqual(result['status'], 'RESPONSE_REJECTED')
        self.assertEqual(result['estimate_peak_micro_cny'], 27900)
        self.assertEqual(self.s.db.execute('SELECT raw_response FROM provider_calls').fetchone()[0], canonical(body))

    def test_nonobject_response_is_terminal_not_left_unknown(self):
        result = self.send_body([])
        self.assertEqual(result['error_category'], 'INVALID_RESPONSE_OBJECT')
        self.assertEqual(result['status'], 'RESPONSE_REJECTED')

    def test_invalid_choices_preserve_valid_reported_cost(self):
        body = helpers.response()
        body['choices'] = [None]
        result = self.send_body(body)
        self.assertEqual(result['error_category'], 'INVALID_RESPONSE_CHOICES')
        self.assertEqual(result['estimate_peak_micro_cny'], 27900)

    def test_decimal_estimate_and_snapshot_batch_deduplication(self):
        usage = {'prompt_tokens': 10, 'completion_tokens': 0, 'total_tokens': 10,
                 'prompt_cache_hit_tokens': 10, 'prompt_cache_miss_tokens': 0}
        self.assertEqual(usage_estimate(usage, {'input_miss': 9, 'input_hit': .3, 'output': 27}), 3)
        batch = {'batch_id': 'A', 'scope_sha256': 'frozen', 'guard_cny': 1}
        self.assertEqual(len(unique_batch_guards([batch, copy.deepcopy(batch)])), 1)
        with self.assertRaises(ValueError):
            unique_batch_guards([batch, {**batch, 'scope_sha256': 'changed'}])

    def test_reopen_does_not_mutate_old_rejected_estimate(self):
        body = helpers.response()
        body['choices'][0]['message']['content'] = ''
        self.send_body(body)
        self.s.db.execute('UPDATE provider_calls SET estimate_peak_micro_cny=NULL')
        before = list(self.s.db.iterdump())
        ProviderJournal(self.s).summary(self.scope['batch_id'])
        self.assertEqual(before, list(self.s.db.iterdump()))


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    files = list(helpers.CODE.glob('*.py')) + [Path(__file__), Path(helpers.__file__), Path(__file__).with_name('reconcile_terminal_r047.py')]
    with zipfile.ZipFile(OUT / 'TESTED_SOURCE.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.writestr(path.relative_to(helpers.ROOT).as_posix(), path.read_bytes())
    with (OUT / 'TESTS.log').open('x', encoding='utf-8') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AccountingTests))
    report = {'tests': result.testsRun, 'passed': result.wasSuccessful(), 'errors': len(result.errors),
              'failures': len(result.failures), 'target_calls': 0, 'network_calls': 0,
              'origin': 'AUTHORED_FIXTURES_REAL_JOURNAL_PATHS_NOT_TARGET_GENERATION',
              'tested_sources': [{'path': p.relative_to(helpers.ROOT).as_posix(), 'sha256': file_sha(p)} for p in files]}
    (OUT / 'TESTS.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': OUT.relative_to(helpers.ROOT).as_posix(), **{k: report[k] for k in ('tests', 'passed', 'errors', 'failures', 'target_calls')}}))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
