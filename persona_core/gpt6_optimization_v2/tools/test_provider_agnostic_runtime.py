"""Authored synthetic contracts only; no credentials, network or Persona cases."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
CODE = ROOT/'persona_core/operational_runtime_v1'
OLD = ROOT/'persona_core/operational_build_v1/tools'
sys.path[:0] = [str(CODE), str(OLD)]
import provider as p
import provider_contract as c
import provider_adapters as a
import provider_fixture as f
import provider_transport as pt
from transcript_store import TranscriptStore, create_sandbox

OUT = ROOT/'persona_core/operational_build_v1/evidence'/('PROVIDER2_OFFLINE_' + uuid.uuid4().hex)


def payload(scope=None):
    scope = scope or f.make_scope('TEST')
    return p.canonical(a.select(scope).serialize(scope, scope['slots'][0]['model'],
        [{'role': 'user', 'content': scope['slots'][0]['user_text']}]))


def deepseek_scope():
    import test_provider_v2_r047 as old
    scope = old.scope()
    scope.update(schema_version='apcore-provider-scope-5', api_protocol='responses', endpoint=p.RESPONSES_ENDPOINT,
        capacity_policy_id='EXTENDED_MAX_REASONING_20260911', output_budget_includes_reasoning=True,
        automatic_capacity_escalation=False, stream=True, request_timeout_seconds=5,
        network_route_policy={'version':'apcore-network-route-1','mode':'DIRECT_NO_PROXY','host':'api.deepseek.com'},
        transport_policy=f.make_scope('POLICY')['transport_policy'])
    return scope


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.scope = f.make_scope('REGISTRY_TEST')

    def test_registry_has_two_distinct_adapters(self):
        registry = a.registry()
        self.assertEqual(set(registry.adapters), {'deepseek', 'local_fixture'})
        self.assertIsInstance(registry.select('deepseek'), a.DeepSeekAdapter)
        self.assertIsInstance(registry.select('local_fixture'), f.LocalFixtureAdapter)

    def test_registry_rejects_duplicate_ids(self):
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_PROVIDER'):
            a.ProviderRegistry([f.LocalFixtureAdapter(), f.LocalFixtureAdapter()])

    def test_registry_rejects_incomplete_contract(self):
        class Incomplete:
            provider_id = 'incomplete'; capabilities = f.CAPABILITIES
        with self.assertRaisesRegex(ValueError, 'CONTRACT_INCOMPLETE'): a.ProviderRegistry([Incomplete()])

    def test_registry_cannot_mutate_mapping(self):
        with self.assertRaises(TypeError): a.registry().adapters['other'] = f.LocalFixtureAdapter()

    def test_unknown_provider_rejected_before_submission(self):
        self.scope['provider_id'] = 'unregistered'
        with self.assertRaisesRegex(ValueError, 'NOT_REGISTERED'): p.scope_check(self.scope)

    def test_protocol_selected_independently_of_provider_name(self):
        self.scope['api_protocol'] = 'responses'
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_API_PROTOCOL'): p.scope_check(self.scope)

    def test_capability_declaration_cannot_claim_unsupported_protocol(self):
        self.scope['capabilities']['supports_responses_protocol'] = True
        with self.assertRaisesRegex(ValueError, 'CAPABILITY_CONTRACT_MISMATCH'): p.scope_check(self.scope)

    def test_fixture_cannot_be_routed_to_network(self):
        self.scope['network_route_policy']['mode'] = 'DIRECT_NO_PROXY'
        with self.assertRaisesRegex(ValueError, 'LOCAL_ROUTE_REQUIRED'): p.scope_check(self.scope)

    def test_source_binding_is_enforced(self):
        self.scope['source_binding']['sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'SOURCE_BINDING_CHANGED'): p.scope_check(self.scope)

    def test_retry_and_output_limits_are_enforced(self):
        for key, value in [('automatic_paid_retries', 1), ('automatic_paid_retries', False), ('max_output_tokens', 0)]:
            bad = copy.deepcopy(self.scope); bad[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): p.scope_check(bad)

    def test_generation_config_cannot_shadow_budget(self):
        self.scope['generation_config']['max_output_tokens'] += 1
        with self.assertRaisesRegex(ValueError, 'GENERATION_CONFIG_MISMATCH'): p.scope_check(self.scope)

    def test_no_fixture_price_is_invented(self):
        adapter = a.select(self.scope)
        self.assertIsNone(adapter.rates(self.scope, 'fixture-text-1'))
        self.assertIsNone(adapter.reserve(self.scope, 'fixture-text-1', 100))
        self.scope['spend_policy']['rates'] = [1, 2, 3]
        with self.assertRaisesRegex(ValueError, 'UNESTIMATED_POLICY'): p.scope_check(self.scope)

    def test_paid_adapter_rejects_missing_prices(self):
        with self.assertRaisesRegex(ValueError, 'REQUIRES_REVIEWED_PRICE'):
            a.DeepSeekAdapter().validate_spend(self.scope)

    def identity(self, scope=None, model='fixture-text-1'):
        return c.generation_identity(scope or self.scope, model, [{'role':'user','content':'same semantic input'}])

    def test_provider_change_alters_generation_and_scope_hash(self):
        changed = copy.deepcopy(self.scope); changed['provider_id'] = 'deepseek'
        self.assertNotEqual(self.identity(), self.identity(changed)); self.assertNotEqual(p.digest(self.scope), p.digest(changed))

    def test_model_change_alters_generation_identity(self):
        self.assertNotEqual(self.identity(), self.identity(model='fixture-text-2'))

    def test_protocol_change_alters_generation_identity(self):
        changed = copy.deepcopy(self.scope); changed['api_protocol'] = 'responses'
        self.assertNotEqual(self.identity(), self.identity(changed))

    def test_route_change_alters_generation_identity(self):
        changed = copy.deepcopy(self.scope); changed['network_route_policy']['mode'] = 'SYSTEM_PROXY'
        self.assertNotEqual(self.identity(), self.identity(changed))

    def test_config_source_and_transport_change_alter_identity(self):
        for field in ('generation_config', 'source_binding', 'transport_policy'):
            changed = copy.deepcopy(self.scope); changed[field]['test_change'] = 1
            with self.subTest(field=field): self.assertNotEqual(self.identity(), self.identity(changed))
        changed = copy.deepcopy(self.scope); changed['transport_contract_version'] = 'next-version'
        self.assertNotEqual(self.identity(), self.identity(changed))

    def test_same_semantic_input_is_not_cross_provider_identity(self):
        first = self.identity(); second = copy.deepcopy(self.scope); second['provider_id'] = 'another-provider'
        self.assertEqual(first, self.identity(copy.deepcopy(self.scope)))
        self.assertNotEqual(first, self.identity(second))

    def test_legacy_provider_metadata_injection_rejected(self):
        scope = deepseek_scope(); scope['provider_id'] = 'local_fixture'
        with self.assertRaisesRegex(ValueError, 'FORMAL_PROVIDER_SCOPE_MISMATCH'): p.scope_check(scope)

    def test_deepseek_adapter_serialization_matches_historical_request_bytes(self):
        messages = [{'role':'system','content':'synthetic'}, {'role':'user','content':'offline'}]
        scope = deepseek_scope(); p.scope_check(scope)
        expected = {'model':'deepseek-v4-pro','input':messages,'max_output_tokens':8192,'stream':True,'reasoning':{'effort':'max'}}
        self.assertEqual(p.canonical(a.DeepSeekAdapter().serialize(scope, 'deepseek-v4-pro', messages)), p.canonical(expected))

    def test_deepseek_chat_serialization_matches_historical_request_bytes(self):
        import test_provider_v2_r047 as old
        scope = old.scope(); scope['stream'] = True
        messages = [{'role':'user','content':'offline'}]
        expected = {'model':'deepseek-v4-pro','messages':messages,'max_tokens':8192,'stream':True,
                    'thinking':{'type':'enabled'},'reasoning_effort':'max','stream_options':{'include_usage':True}}
        self.assertEqual(p.canonical(a.DeepSeekAdapter().serialize(scope, 'deepseek-v4-pro', messages)), p.canonical(expected))


class DecoderTests(unittest.TestCase):
    def setUp(self):
        self.scope = f.make_scope('DECODER'); self.adapter = a.select(self.scope)
        self.wire = f.synthetic_wire(payload(self.scope))

    def test_native_terminal_normalizes_to_completed(self):
        body = json.loads(self.adapter.decode(self.scope, self.wire))
        self.assertEqual(self.adapter.terminal(self.scope, body), ('completed', 'fixture.seal', None))

    def test_native_usage_normalization(self):
        usage = json.loads(self.adapter.decode(self.scope, self.wire))['usage']
        self.assertEqual(c.validate_usage(usage), (2, 8))
        self.assertEqual(usage['completion_tokens_details']['reasoning_tokens'], 4)
        self.assertEqual(c.estimate_usage(usage, [9,27,0.3]), 289)
        self.assertIsNone(c.estimate_usage(usage, None))

    def test_fragmentation_preserves_exact_body(self):
        for size in (1, 7, 31, 8192):
            parser = f.FixtureAssembly(pt.Lifecycle())
            for i in range(0, len(self.wire), size): parser.feed(self.wire[i:i+size])
            self.assertEqual(parser.body(), self.adapter.decode(self.scope, self.wire))

    def test_missing_terminal_is_unknown(self):
        truncated = b'\n'.join(self.wire.split(b'\n')[:-2]) + b'\n'
        with self.assertRaises(ValueError): self.adapter.decode(self.scope, truncated)

    def test_sequence_identity_and_trailing_events_rejected(self):
        records = [json.loads(line) for line in self.wire.splitlines()]
        for mutation in ('sequence', 'identity', 'trailing', 'terminal'):
            changed = copy.deepcopy(records)
            if mutation == 'sequence': changed[1]['seq'] = 0
            if mutation == 'identity': changed[1]['id'] = 'foreign'
            if mutation == 'trailing': changed.append(changed[-1])
            if mutation == 'terminal': changed[-1]['data']['outcome'] = 'maybe'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.adapter.decode(self.scope, b''.join(p.canonical(r)+b'\n' for r in changed))

    def test_capabilities_do_not_certify_forged_normalized_body(self):
        result = pt.TransportResult(200, b'{}', self.wire)
        with self.assertRaises(pt.TransportFault): a.verified_result(self.adapter, self.scope, result)

    def test_malformed_receipt_types_become_safe_unknown(self):
        for result in (pt.TransportResult(200,b'{}','not bytes'), pt.TransportResult('200',b'{}',b''), (200,b'{}')):
            with self.subTest(result_type=type(result).__name__), self.assertRaises(pt.TransportFault) as caught:
                a.verified_result(self.adapter,self.scope,result)
            self.assertIsInstance(caught.exception.wire,bytes)

    def test_invalid_usage_is_not_reported_known(self):
        for usage in (None, {}, {'prompt_tokens':True,'completion_tokens':2,'total_tokens':3},
                      {'prompt_tokens':1,'completion_tokens':2,'total_tokens':4}):
            self.assertFalse(c.usage_known(json.dumps(usage)))

    def test_usage_rejects_boolean_negative_overflow_cache_and_reasoning(self):
        usage = json.loads(self.adapter.decode(self.scope, self.wire))['usage']
        for key, value in [('prompt_tokens', True), ('completion_tokens', -1), ('total_tokens', 100),
                           ('prompt_cache_hit_tokens', 100), ('completion_tokens_details', {'reasoning_tokens': 9})]:
            changed = copy.deepcopy(usage); changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): c.validate_usage(changed)

    def test_common_usability_never_promotes_reasoning(self):
        body = {'choices':[{'finish_reason':'stop','message':{'content':'','reasoning_content':'not an answer'}}]}
        with self.assertRaisesRegex(ValueError, 'EMPTY_RESPONSE'): c.usable_reply(body)

    def test_worker_contract_rejects_network_route_escape(self):
        contract = {'provider_id':'local_fixture','api_protocol':f.PROTOCOL,'endpoint':f.ENDPOINT,
                    'network_route_policy':dict(f.ROUTE),'transport_contract_version':c.TRANSPORT_VERSION}
        contract['endpoint'] = 'https://example.invalid'
        with self.assertRaises(ValueError): f.validate_worker_contract(contract)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.root = create_sandbox(OUT/self._testMethodName)
        self.store = TranscriptStore(self.root); self.addCleanup(self.store.close)
        self.journal = p.ProviderJournal(self.store)

    def prepare(self, case='short', batch='FIXTURE_BATCH'):
        scope = f.make_scope(batch, case=case); self.journal.register_batch(scope)
        handle = self.store.open_session(scope['principal_id'], scope['slots'][0]['entity_label'], 'CHARACTER_SIMULATION')
        turn = self.store.begin_turn(handle, scope['slots'][0]['user_text'], batch)
        context = {'turn_id':turn['turn_id'], 'mode':handle.mode, 'messages':[{'role':'user','content':turn['user_text']}]}
        return scope, handle, turn, context

    def submit(self, prepared, **kwargs):
        scope, handle, turn, context = prepared
        return self.journal.call(handle, turn['turn_id'], scope['batch_id'], 'SYNTHETIC_1', context, **kwargs)

    def test_short_fixture_uses_real_worker_and_is_never_target_capture(self):
        prepared = self.prepare()
        with patch.object(p, 'existing_credential', side_effect=AssertionError('must not load credentials')):
            result = self.submit(prepared)
        self.assertEqual(result['status'], 'RESPONSE_CAPTURED')
        self.assertEqual(result['capture_origin'], 'AUTHORED_PROVIDER_TEST_FIXTURE')
        events = [json.loads(r[0])['event'] for r in self.store.db.execute("SELECT detail_json FROM turn_lifecycle WHERE state='TRANSPORT_LIFECYCLE'")]
        self.assertTrue({'child_started','worker_started','provider_finish','worker_terminal','child_exit','parent_receipt'} <= set(events))
        self.assertFalse({'dns_started','tcp_started','request_write_started'} & set(events))
        self.assertIsNone(json.loads(self.store.db.execute("SELECT detail_json FROM turn_lifecycle WHERE state='RESPONSE_CAPTURED'").fetchone()[0])['semantic_verdict'])

    def test_long_fixture_is_complete_and_bounded(self):
        prepared = self.prepare('long'); result = self.submit(prepared)
        self.assertEqual(result['status'], 'RESPONSE_CAPTURED')
        text = self.store.get_turn(prepared[1], prepared[2]['turn_id'])['assistant_text']
        self.assertEqual(text.count('Synthetic long output.'), 128)
        self.assertLessEqual(json.loads(result['usage_json'])['completion_tokens'], prepared[0]['max_output_tokens'])

    def test_failed_native_terminal_is_known_rejection(self):
        result = self.submit(self.prepare('failed'))
        self.assertEqual(result['status'], 'RESPONSE_REJECTED_TERMINAL_KNOWN')
        self.assertEqual(result['error_category'], 'FIXTURE_FAILED')

    def test_incomplete_native_terminal_is_known_rejection(self):
        self.assertEqual(self.submit(self.prepare('incomplete'))['status'], 'RESPONSE_REJECTED_TERMINAL_KNOWN')

    def test_disconnect_is_unknown_with_reserve_and_batch_stop(self):
        result = self.submit(self.prepare('disconnect'))
        self.assertEqual(result['status'], 'SUBMITTED_STATUS_UNKNOWN')
        self.assertIsNone(result['reserve_micro_cny'])
        self.assertEqual(result['provider_binding']['reserve']['output_tokens'], 512)
        self.assertEqual(self.store.db.execute('SELECT stopped FROM call_batches').fetchone()[0], 1)
        self.assertEqual(self.store.db.execute('SELECT complete FROM transport_wire_captures').fetchone()[0], 0)

    def test_malformed_usage_is_known_terminal_not_capture(self):
        result = self.submit(self.prepare('malformed_usage'))
        self.assertEqual(result['status'], 'RESPONSE_REJECTED_TERMINAL_KNOWN')
        self.assertEqual(result['error_category'], 'FIXTURE_INVALID_USAGE')
        self.assertIsNone(result['estimate_peak_micro_cny'])

    def test_missing_usage_is_unestimated_known_rejection(self):
        result = self.submit(self.prepare('missing_usage'))
        self.assertEqual(result['status'], 'RESPONSE_REJECTED_TERMINAL_KNOWN')
        summary = self.journal.summary('FIXTURE_BATCH')
        self.assertEqual(summary['unestimated_call_count'], 1)
        self.assertEqual(summary['known_usage_count'], 0)

    def test_reasoning_only_has_no_assistant_reply(self):
        prepared = self.prepare('reasoning_only'); result = self.submit(prepared)
        self.assertEqual(result['status'], 'RESPONSE_REJECTED_TERMINAL_KNOWN')
        self.assertIsNone(self.store.get_turn(prepared[1], prepared[2]['turn_id'])['assistant_text'])

    def test_unknown_is_never_automatically_retried(self):
        prepared = self.prepare('disconnect'); first = self.submit(prepared)
        with patch.object(pt, 'worker_exchange', side_effect=AssertionError('retry forbidden')):
            second = self.submit(prepared)
        self.assertEqual(first['call_id'], second['call_id'])
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0], 1)

    def test_terminal_rejection_is_never_retried(self):
        prepared = self.prepare('failed'); first = self.submit(prepared)
        second = self.submit(prepared, transport=lambda *args: self.fail('retry'))
        self.assertEqual(first['call_id'], second['call_id'])

    def test_journal_intent_is_committed_before_transport(self):
        prepared = self.prepare()
        def transport(body, credential):
            with sqlite3.connect(self.root/'runtime.sqlite3') as db:
                self.assertEqual(db.execute('SELECT status FROM provider_calls').fetchone()[0], 'SUBMITTED_STATUS_UNKNOWN')
                self.assertEqual(db.execute('SELECT count(*) FROM provider_call_contracts').fetchone()[0], 1)
            return f.local_exchange(body, prepared[0]['transport_policy'], lambda e: None)
        self.assertEqual(self.submit(prepared, transport=transport)['status'], 'RESPONSE_CAPTURED')

    def test_forged_worker_receipt_stops_as_unknown(self):
        prepared = self.prepare()
        result = self.submit(prepared, transport=lambda body, key: pt.TransportResult(200,b'{}',f.synthetic_wire(body)))
        self.assertEqual(result['status'], 'SUBMITTED_STATUS_UNKNOWN')

    def test_provider_binding_cannot_be_reassigned_to_foreign_scope(self):
        prepared = self.prepare(); self.submit(prepared)
        other = copy.deepcopy(prepared[0]); other['provider_id'] = 'deepseek'
        with self.assertRaises(ValueError): self.journal.register_batch(other)
        with self.assertRaises(ValueError):
            self.journal.call(prepared[1], prepared[2]['turn_id'], 'OTHER_BATCH', 'SYNTHETIC_1', prepared[3])

    def test_separate_journal_does_not_inherit_prior_unknown(self):
        prepared = self.prepare('disconnect'); first = self.submit(prepared)
        root = create_sandbox(OUT/(self._testMethodName + '_isolated'))
        with_store = TranscriptStore(root)
        try:
            journal = p.ProviderJournal(with_store)
            self.assertEqual(with_store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0], 0)
            self.assertEqual(self.journal.get_call(prepared[1], first['call_id'])['status'], 'SUBMITTED_STATUS_UNKNOWN')
        finally: with_store.close()

    def test_local_fixture_never_reads_even_injected_credentials(self):
        result = self.submit(self.prepare(), credential_reader=lambda: self.fail('local fixture loaded a credential'))
        self.assertEqual(result['status'], 'RESPONSE_CAPTURED')

    def test_summary_distinguishes_usage_reserve_estimate_and_billing(self):
        self.submit(self.prepare()); summary = self.journal.summary('FIXTURE_BATCH')
        self.assertEqual(summary['known_usage_count'], 1)
        self.assertIsNone(summary['reserved_cny']); self.assertIsNone(summary['peak_usage_estimate_cny'])
        self.assertFalse(summary['estimate_complete']); self.assertFalse(summary['billing_certified'])
        self.assertEqual(summary['accounting_status'], 'UNESTIMATED')
        self.assertFalse(summary['semantic_acceptance']); self.assertEqual(summary['automatic_paid_retries'], 0)

    def test_deepseek_new_scope_uses_same_journal_and_common_usability(self):
        import test_responses_provider_integration as response_fixture
        scope = deepseek_scope()
        scope.update(schema_version=c.SCOPE_VERSION, provider_id='deepseek',
            capabilities=a.DeepSeekAdapter.capabilities.declaration(), transport_contract_version=c.TRANSPORT_VERSION,
            source_binding=c.runtime_source_binding(), validation_purpose='SYNTHETIC_INDEPENDENT_VALIDATION',
            generation_config={'stream':True,'max_output_tokens':scope['max_output_tokens'], 'reasoning':{'enabled':True,'effort':'max'}},
            slots=[{'id':'SYNTHETIC_1','model':'deepseek-v4-pro','entity_label':'SYNTHETIC_TRANSPORT_ONLY','user_text':'fixture:short'}],
            spend_policy={'mode':'REVIEWED_RATES','currency':'CNY','rates':{'deepseek-v4-pro':list(p.RATES['deepseek-v4-pro'])},
                          'price_evidence':{'sources':['AUTHORED_OFFLINE_ONLY'],'verified_date':'2026-09-19'}})
        scope['reserved_upper_micro_cny'] = a.DeepSeekAdapter().reserve(scope, 'deepseek-v4-pro', scope['max_input_bytes'])
        self.journal.register_batch(scope)
        handle = self.store.open_session(scope['principal_id'],'SYNTHETIC_TRANSPORT_ONLY','CHARACTER_SIMULATION')
        turn = self.store.begin_turn(handle,'fixture:short','SYNTHETIC_1')
        context = {'turn_id':turn['turn_id'],'mode':handle.mode,'messages':[{'role':'user','content':'fixture:short'}]}
        wire = response_fixture.responses_wire(); adapter = a.select(scope)
        result = self.submit((scope,handle,turn,context), credential_reader=lambda:'AUTHORED_NOT_REAL_KEY',
            transport=lambda payload,key:pt.TransportResult(200,adapter.decode(scope,wire),wire))
        self.assertEqual(result['status'],'RESPONSE_CAPTURED')
        self.assertEqual(result['provider_binding']['provider_id'],'deepseek')
        self.assertEqual(result['provider_binding']['api_protocol'],'responses')
        self.assertEqual(result['estimate_peak_micro_cny'],1353)

    def test_independent_scope_cannot_run_in_product_mode(self):
        scope = f.make_scope('MODE'); self.journal.register_batch(scope)
        handle = self.store.open_session(scope['principal_id'],scope['slots'][0]['entity_label'],'PRODUCT_RUNTIME')
        turn = self.store.begin_turn(handle,'fixture:short','MODE')
        context = {'turn_id':turn['turn_id'],'mode':handle.mode,'messages':[{'role':'user','content':'fixture:short'}]}
        with self.assertRaisesRegex(ValueError,'SIMULATION_MODE'):
            self.submit((scope,handle,turn,context))
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0],0)


class FormalGateTests(unittest.TestCase):
    def test_candidate_rejects_independent_provider_scope(self):
        import candidate_day_v2 as g
        with self.assertRaisesRegex(ValueError,'FORMAL_PROVIDER_SCOPE_MISMATCH'): g.generation_settings(f.make_scope('GATE'))

    def test_candidate_rejects_smuggled_provider_in_legacy_scope(self):
        import candidate_day_v2 as g
        scope = deepseek_scope(); scope['provider_id'] = 'other'
        with self.assertRaisesRegex(ValueError,'FORMAL_PROVIDER_SCOPE_MISMATCH'): g.generation_settings(scope)

    def test_blind_gate_rejects_provider_before_examining_reply(self):
        import blind_review_v2 as blind
        with self.assertRaisesRegex(ValueError,'FORMAL_PROVIDER_SCOPE_MISMATCH'):
            blind._verify_call_context({}, {}, {}, {}, f.make_scope('GATE'))

    def test_longitudinal_protocol_gate_rejects_provider_scope(self):
        import candidate_day_v2 as g
        with self.assertRaisesRegex(ValueError,'FORMAL_PROVIDER_SCOPE_MISMATCH'): g.verify_protocol_capture(None, {}, f.make_scope('GATE'))

    def test_candidate_host_rejects_provider_before_price_or_credentials(self):
        import candidate_host_v2 as host
        with self.assertRaisesRegex(ValueError,'FORMAL_PROVIDER_SCOPE_MISMATCH'):
            host.validate_pricing(None, None, f.make_scope('GATE'), None)


if __name__ == '__main__': unittest.main(verbosity=2)
