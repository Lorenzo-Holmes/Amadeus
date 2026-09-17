"""AUTHOR fixtures only. No actual candidate, held-out reads, sends or provider."""
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid
import zipfile

import blind_review_v2 as b
import semantic_review as sr
import candidate_day_v2 as g
import test_semantic_review as fixtures

sys.dont_write_bytecode = True
sys.path.insert(0, str(g.ROOT / 'persona_core/operational_runtime_v1'))


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.ReviewTests('test_blank_never_prefills_verdict_score_or_authorship')
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.fixture = fixture; self.root = fixture.root
        self.loaded = {'workspace': self.root, 'candidate_path': self.root / 'AUTHOR_CANDIDATE.json',
            'binding': {'classification': 'AUTHOR_OFFLINE_ONLY', 'candidate_sha256': 'a' * 64},
            'bundles': {name: fixture.bundle for name in g.DENOMINATORS},
            'source_facts': {'source_knowledge_only': ['AUTHOR literal source'],
                'unadmitted_memory_existence': 'UNKNOWN', 'unadmitted_memory_accessibility': 'UNKNOWN',
                'admission_list_is_exhaustive_life_or_memory_inventory': False},
            'evidence': {name: {slot: {'model_received_evidence_scope': {'source_memory_evidence_present': True},
                'host_admitted_before_reply': {'scope': 'AUTHOR fixture only', 'agreements': [], 'corrections': []}}
                for slot in fixture.bundle.captures} for name in g.DENOMINATORS}}
        self.loader = patch.object(b, '_load_candidate', return_value=self.loaded)
        self.loader.start(); self.addCleanup(self.loader.stop)
        self.public = self.root / 'AUTHOR_PUBLIC.zip'; self.private = self.root / 'AUTHOR_PRIVATE.json'
        self.candidate = self.loaded['candidate_path']

    def build(self):
        return b.build_package(self.candidate, self.public, self.private, workspace=self.root)

    def returned(self, edit=None):
        members = b._members(self.public.read_bytes())
        form = sr.parse_json(members['REVIEW.json'])
        rows = {t['slot_id']: t for c in sr.parse_json(members['DIALOGUES.json'])['cases'] for t in c['turns']}
        for group in form['groups']:
            self.fixture.fill(group, rows)
        if edit: edit(form, members)
        members['REVIEW.json'] = sr.json_bytes(form)
        returned = self.root / ('AUTHOR_RETURN_' + uuid.uuid4().hex + '.zip')
        returned.write_bytes(b._zip(members))
        proof = self.root / ('AUTHOR_PROVENANCE_' + uuid.uuid4().hex + '.txt')
        proof.write_text('AUTHOR OFFLINE PROVENANCE FIXTURE ONLY', encoding='utf-8')
        docs = []
        for kind, stamp in (('HANDOFF', '2025-12-31T23:59:00Z'), ('RETURN', '2026-01-01T00:02:00Z')):
            path = self.root / (kind + '_' + uuid.uuid4().hex + '.json')
            value = {'schema_version': 'g6-review-provenance-1', 'kind': kind,
                'recorded_by': 'AUTHOR OFFLINE', 'method': 'AUTHOR OFFLINE STRUCTURAL TEST',
                'observed_at_utc': stamp, 'public_zip_sha256': g.sha(self.public),
                'evidence_references': [g.ref(proof, self.root)]}
            if kind == 'RETURN': value['completed_zip_sha256'] = g.sha(returned)
            path.write_bytes(sr.json_bytes(value)); docs.append(path)
        return returned, *docs

    def bind(self, args):
        return b.bind_return(self.candidate, self.public, self.private, *args, workspace=self.root)

    def test_original_dialogue_exact_full_denominator_blank_forms_and_no_private_metadata(self):
        result = self.build(); self.assertEqual((result['turns'], result['criteria']), (12, 48))
        members = b._members(self.public.read_bytes())
        manifest = sr.parse_json(members['MANIFEST.json'])
        self.assertEqual(manifest['members'], {n: sr.sha_bytes(v) for n, v in members.items() if n != 'MANIFEST.json'})
        public = b'\n'.join(members.values()).decode('utf-8')
        for marker in ('private-provider-model', 'PRIVATE_IMPL', 'synthetic-test-revision', 'prior_score', 'private_expectations'):
            self.assertNotIn(marker, public)
        dialogues = sr.parse_json(members['DIALOGUES.json'])['cases']
        originals = list(self.fixture.bundle.captures.values())
        actual = [t for c in dialogues for t in c['turns']]
        self.assertEqual([(r['user_text'], r['assistant_text']) for r in actual],
                         [(r['user_text'], r['assistant_text']) for r in originals] * 3)
        self.assertIn('test-model', public)  # Literal dialogue is never scrubbed.
        for group in sr.parse_json(members['REVIEW.json'])['groups']:
            self.assertIsNone(group['findings_complete'])
            self.assertIsNone(group['reviewer']['authorship_confirmed'])
            self.assertTrue(all(j['verdict'] is None for c in group['cases'] for t in c['turn_reviews'] for j in t['judgments']))
        self.assertFalse(result['independent_review_complete'])

    def test_completed_return_binds_declarations_without_certifying_external_acceptance(self):
        self.build(); result = self.bind(self.returned())
        self.assertTrue(result['recorded_review_gate_met'])
        for key in ('reviewer_independence_authenticated', 'provider_execution_verified_by_this_tool',
                    'human_identity_authenticated', 'model_weight_identity_authenticated',
                    'provenance_truth_authenticated', 'independent_review_complete', 'product_acceptance_complete'):
            self.assertFalse(result[key])
        self.assertEqual(result['external_review'], 'WAITING_EXTERNAL')

    def test_unknown_keeps_named_finding_and_does_not_pass(self):
        self.build()
        def edit(form, _):
            group = form['groups'][0]; turn = group['cases'][0]['turn_reviews'][0]
            turn['judgments'][0].update(verdict='UNKNOWN', finding_ids=['UNRESOLVED_SCOPE'])
            group['findings'] = [{'id': 'UNRESOLVED_SCOPE', 'severity': 'MINOR', 'status': 'OPEN',
                'rationale': 'AUTHOR unknown evidence fixture', 'affected_slots': [turn['slot_id']],
                'evidence': [{'slot_id': turn['slot_id'], 'quote': turn['judgments'][0]['quote']}]}]
        result = self.bind(self.returned(edit))
        self.assertFalse(result['recorded_review_gate_met'])
        self.assertEqual(result['suite_reports']['external44']['verdict_counts']['UNKNOWN'], 1)

    def test_evidence_member_tampering_rejected(self):
        self.build()
        def edit(_, members): members['EVIDENCE.json'] += b' '
        with self.assertRaisesRegex(g.GateError, 'IMMUTABLE_MEMBER'):
            self.bind(self.returned(edit))

    def test_missing_turn_and_nonexact_quote_rejected_by_original_binder(self):
        self.build()
        for change, error in ((lambda f: f['groups'][0]['cases'][0]['turn_reviews'].pop(), 'TURN_COVERAGE'),
                (lambda f: f['groups'][0]['cases'][0]['turn_reviews'][0]['judgments'][0].update(quote='Invented quote'), 'QUOTE_NOT_EXACT')):
            with self.subTest(error=error):
                with self.assertRaisesRegex(sr.ReviewError, error):
                    self.bind(self.returned(lambda f, m: change(f)))

    def test_candidate_or_private_mapping_change_rejected(self):
        self.build(); args = self.returned()
        private = g.load(self.private); private['mapping'][0]['call_id'] = 'changed'
        self.private.write_bytes(sr.json_bytes(private))
        with self.assertRaisesRegex(g.GateError, 'PRIVATE_MAPPING'):
            self.bind(args)
        self.loaded['binding']['candidate_sha256'] = 'b' * 64
        with self.assertRaisesRegex(g.GateError, 'PRIVATE_CANDIDATE_BINDING'):
            self.bind(args)

    def test_actual_provenance_references_and_times_required(self):
        self.build(); args = self.returned()
        value = g.load(args[1]); value['evidence_references'] = []
        args[1].write_bytes(sr.json_bytes(value))
        with self.assertRaisesRegex(g.GateError, 'ACTUAL_HANDOFF_RETURN_REFERENCES'):
            self.bind(args)
        args = self.returned(); value = g.load(args[1]); value['observed_at_utc'] = '2026-01-01T00:00:30Z'
        args[1].write_bytes(sr.json_bytes(value))
        with self.assertRaisesRegex(g.GateError, 'REVIEW_OUTSIDE_HANDOFF_RETURN'):
            self.bind(args)

    def test_old_zip_and_duplicate_or_extra_members_are_refused(self):
        self.build(); members = b._members(self.public.read_bytes())
        for changed in ({k: v for k, v in members.items() if k in sr.PUBLIC_MEMBERS},
                        dict(members, **{'../../escape': b'x'})):
            with self.assertRaisesRegex(g.GateError, 'MEMBER_SET'):
                b._members(b._zip(changed))
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as z:
            for k, v in members.items(): z.writestr(k, v)
            z.writestr('REVIEW.json', members['REVIEW.json'])
        with self.assertRaisesRegex(g.GateError, 'MEMBER_SET'):
            b._members(data.getvalue())

    def test_new_destinations_and_double_load_guard(self):
        self.build()
        with self.assertRaisesRegex(g.GateError, 'NEW_DISTINCT_OUTPUTS'):
            self.build()
        with patch.object(b, '_load_candidate', side_effect=[self.loaded, dict(self.loaded, binding={'changed': True})]):
            with self.assertRaisesRegex(g.GateError, 'EVIDENCE_CHANGED_DURING_PACKAGE'):
                b.build_package(self.candidate, self.root/'new.zip', self.root/'new.json', workspace=self.root)
        self.assertFalse((self.root/'new.zip').exists())

    def test_actual_candidate_and_gates_required_before_any_output(self):
        self.loader.stop()
        with self.assertRaises((OSError, g.GateError)):
            b.build_package(self.root/'MISSING_CANDIDATE.json', self.public, self.private, workspace=self.root)
        self.assertFalse(self.public.exists()); self.assertFalse(self.private.exists())
        fake = {'gate_inputs': {'path': 'input.json', 'sha256': 'f' * 64}}
        with patch.object(g, 'verify_candidate_bindings', return_value=(fake, {})):
            with self.assertRaisesRegex(g.GateError, 'FILE_BINDING_CHANGED'):
                b.build_package(self.candidate, self.public, self.private, workspace=self.root)

    def test_legacy_switch_regression_quality_eligibility_and_private_expectations(self):
        f = self.fixture
        rubric = {'every_turn_review_dimensions': f.cases['criteria_per_turn'],
            'quality_targets': {**{'category_mean_' + q + '_min': v for q, v in sr.MINIMUMS.items()},
                                'unresolved_critical_findings_max': 0},
            'semantic_verdicts': ['PASS', 'FAIL', 'UNKNOWN'], 'quality_scale': 'AUTHOR 1 through 5',
            'hard_failures': ['AUTHOR global scope standard'], 'quality_aggregation': 'AUTHOR per-category means'}
        f.put(self.root/'RUBRIC.json', rubric)
        cases = []
        for index, case in enumerate(f.cases['cases']):
            cases.append({'id': case['id'], 'category': case['category'],
                'classification': 'NEW_AT_FREEZE' if index == 0 else 'EXPLICIT_REGRESSION_NOT_HELDOUT',
                'user_turns': [case['turns'][0]['user_text']], 'switch_tail': [case['turns'][1]['user_text']],
                'private_expectations': ['AUTHOR_PRIOR_FAILURE_SENTINEL', 'Private case constraint remains private.']})
        f.cases = {'cases': cases}
        for row in f.capture['turns']:
            row['slot_id'] = row['case_id'] + ('_T1' if row['slot_id'].endswith('T0') else '_S1')
        f.sync_cases(); freeze = g.load(f.freeze)
        freeze['files']['RUBRIC.json'] = g.sha(self.root/'RUBRIC.json'); f.put(f.freeze, freeze)
        f.sync_captures()
        bundle = sr.load_bundle(**dict(f.bundle.options, rubric=self.root/'RUBRIC.json'))
        self.loaded['bundles'] = {name: bundle for name in g.DENOMINATORS}
        self.loaded['evidence'] = {name: {slot: {'AUTHOR': 'fixture'} for slot in bundle.captures} for name in g.DENOMINATORS}
        self.build(); members = b._members(self.public.read_bytes())
        dialogues = sr.parse_json(members['DIALOGUES.json'])['cases']
        self.assertEqual([t['quality_eligible'] for c in dialogues[:2] for t in c['turns']], [True, False, False, False])
        public_rubric = sr.parse_json(members['RUBRIC.json'])['groups'][0]['rubric']
        for key, value in rubric.items(): self.assertEqual(public_rubric[key], value)
        self.assertEqual(public_rubric['quality_score_denominator'], 3)
        self.assertNotIn('AUTHOR_PRIOR_FAILURE_SENTINEL', b'\n'.join(members.values()).decode('utf-8'))
        result = self.bind(self.returned())
        self.assertTrue(result['recorded_review_gate_met'])
        self.assertEqual(result['suite_reports']['original82']['coverage']['quality_scores'], 3)


class HostEvidenceTests(unittest.TestCase):
    def setUp(self):
        from transcript_store import TranscriptStore, create_sandbox
        from dialogue_admission import DialogueAdmissionController
        import runtime_store
        self.runtime_mod = runtime_store
        destination = g.ROOT/'persona_core/operational_build_v1/evidence/G6_V2_blind_author_fixtures'/uuid.uuid4().hex
        self.store = TranscriptStore(create_sandbox(destination)); self.addCleanup(self.store.close)
        self.handle = self.store.open_session('AUTHOR_OFFLINE', 'EVIDENCE_BINDING')
        self.admission = DialogueAdmissionController(self.store)
        self.runtime = runtime_store.RuntimeStore(self.store, self.admission)
        self.expected = '便签记有长度、质量、温度'
        self.observed('提议约定：测试便签；验收内容：' + self.expected, '同意约定：测试便签')
        self.observed('确认约定：测试便签', 'AUTHOR confirmed')

    def observed(self, user, answer):
        turn = self.store.begin_turn(self.handle, user, uuid.uuid4().hex)
        self.store.capture_reply(self.handle, turn['turn_id'], answer, 'AUTHOR_OFFLINE_REPLY')
        self.store.mark_displayed(self.handle, turn['turn_id']); self.admission.observe_turn(self.handle, turn['turn_id'])
        return turn

    def context(self, user):
        from context_router import build_context
        from retrieval import RetrievalService
        turn = self.store.begin_turn(self.handle, user, uuid.uuid4().hex)
        context = build_context(self.store, self.handle, turn['turn_id'], memory_provider=RetrievalService(self.runtime))
        core = json.loads([m['content'][len(b.PREFIX):] for m in context['messages'] if m['content'].startswith(b.PREFIX)][0])
        row = {'turn_id': turn['turn_id'], 'session_id': self.handle.session_id, 'user_text': user,
               'submitted_at_utc': datetime.now(timezone.utc).isoformat()}
        return row, context, core

    def test_memory_capability_is_bound_and_published_without_entity_identifier(self):
        row, context, core = self.context('收纳盒的问题以后还能接着谈吗？')
        result = b._memory_capability(context, core, self.store, self.runtime, self.handle)
        self.assertEqual(result['status'], 'AVAILABLE')
        self.assertTrue(result['same_entity_mode_across_sessions'])
        self.assertTrue(result['after_store_reopen'])
        self.assertFalse(result['all_future_recall_guaranteed'])
        self.assertEqual(result['scope'], {'entity': 'CURRENT_CONVERSATION_ENTITY', 'mode': 'PRODUCT_RUNTIME'})
        self.assertNotIn(self.handle.entity_id, json.dumps(result))
        self.assertNotIn('query', result)  # Raw diagnostic hit counts are not received evidence.

    def test_forged_persistence_capability_is_rejected_before_publication(self):
        row, context, core = self.context('继续整理抽屉。')
        core['runtime_memory_capability']['all_future_recall_guaranteed'] = True
        with self.assertRaisesRegex(g.GateError, 'MEMORY_CAPABILITY'):
            b._memory_capability(context, core, self.store, self.runtime, self.handle)
        context['memory_capability_projection'] = deepcopy(core['runtime_memory_capability'])
        with self.assertRaisesRegex(g.GateError, 'MEMORY_CAPABILITY'):
            b._memory_capability(context, core, self.store, self.runtime, self.handle)

    def received(self, row, context, core):
        _, private = self.validate(row, context, core)
        events = [json.loads(r[0]) for r in self.store.db.execute('SELECT event_json FROM runtime_events ORDER BY sequence')]
        return b._received_context(row, context, core, self.store, self.runtime, self.runtime_mod,
            events, private['event_prefix_count'], g.load(g.ROOT/b.GENESIS))

    def test_received_history_is_exact_and_old_retrieval_is_not_full_history(self):
        original = self.observed('铜扣旧柜的抽屉标签是青石。', 'AUTHOR literal old reply')
        for i in range(10): self.observed('离线无关条目' + str(i), 'AUTHOR unrelated')
        row, context, core = self.context('铜扣旧柜的抽屉标签是什么？')
        received, private = self.received(row, context, core)
        self.assertEqual(received['visible_history_turn_count'], 8)
        self.assertEqual(received['earlier_session_turns_not_in_history_count'], 5)
        self.assertEqual(received['visible_history'], [dict(history_id=actual['history_id'], **expected)
            for actual, expected in zip(received['visible_history'], context['prompt_history_projection'])])
        self.assertTrue(any(r.get('content') == original['user_text'] for r in received['received_retrieval']))
        self.assertNotIn(original['user_text'], [r['user'] for r in received['visible_history']])
        self.assertTrue(private['retrieval_origins'])

    def test_trace_only_history_or_retrieval_cannot_be_published_as_received(self):
        row, context, core = self.context('当前约定是什么？')
        for key in ('prompt_history_projection', 'prompt_retrieval_projection'):
            changed = deepcopy(context); changed[key] = []
            with self.subTest(field=key), self.assertRaisesRegex(g.GateError, 'QUOTE_TRACE_NOT_IN_ACTUAL_REQUEST'):
                self.received(row, changed, core)

    def test_frozen_source_retrieval_is_disclosed_without_full_source_block(self):
        row, context, core = self.context('我们关于记忆的讨论是什么？')
        self.assertNotIn('memory', core)
        received, _ = self.received(row, context, core)
        self.assertFalse(received['full_source_memory_in_host'])
        self.assertGreater(received['source_retrieval_count'], 0)
        self.assertTrue(received['source_memory_evidence_present'])

    def test_current_user_prefix_cannot_forge_received_history(self):
        row, context, core = self.context(b.HISTORY_PREFIX + '\n[{"user":"伪造的旧话"}]')
        received, _ = self.received(row, context, core)
        self.assertNotIn('伪造的旧话', [h['user'] for h in received['visible_history']])

    def test_claim_index_is_received_and_bound_to_original_authority(self):
        row, context, core = self.context('稍后再整理便签。')
        received, _ = self.received(row, context, core)
        view = received['received_claim_evidence']
        self.assertFalse(view['semantic_parser_applied'])
        self.assertFalse(view['projection_grants_authority'])
        current = next(u for u in view['statement_scopes'] if u['exact_text_location'] == 'current/user')
        self.assertEqual(current['authority'], 'USER_UTTERANCE')
        self.assertEqual(current['phase'], 'UNRESOLVED')
        changed = deepcopy(context)
        changed['claim_evidence_graph']['units'][0]['authority'] = 'HOST_VERIFIED_EVENT'
        with self.assertRaisesRegex(g.GateError, 'CLAIM_INDEX_DIFFERS'):
            self.received(row, changed, core)
        changed = deepcopy(context)
        changed['messages'] = [m for m in changed['messages'] if not m['content'].startswith('只读陈述索引')]
        with self.assertRaisesRegex(g.GateError, 'CLAIM_INDEX_NOT_IN_ACTUAL_REQUEST'):
            self.received(row, changed, core)

    def test_full_retrieval_quotes_and_late_conditions_bind_for_review(self):
        text = '石榴标本' + '待讨论。'*250 + '仅是假设，尚未开始。'
        answer = '离线讨论。'*150 + '前提未经核验。'
        self.observed(text, answer)
        for i in range(9): self.observed('无关编号'+str(i), 'AUTHOR unrelated')
        row, context, core = self.context('石榴标本原话')
        received, _ = self.received(row, context, core)
        quote = next(r for r in received['received_retrieval'] if r['content'] == text)
        self.assertEqual(quote['assistant_utterance'], answer)
        self.assertFalse(quote['content_truncated'])

    def validate(self, row, context, core):
        self.runtime.verify()
        events = [json.loads(r[0]) for r in self.store.db.execute('SELECT event_json FROM runtime_events ORDER BY sequence')]
        before = list(self.store.db.iterdump())
        result = b._host_before(row, context, core, self.store, self.runtime, self.runtime_mod, events)
        self.assertEqual(before, list(self.store.db.iterdump()))
        return result

    def test_pending_and_persisted_receipt_are_separate_verified_states(self):
        row, context, core = self.context(self.expected)
        actual, private = self.validate(row, context, core)
        self.assertTrue(actual['current_input_comparison']['unique_exact_match_after_confirmation'])
        self.assertFalse(actual['current_input_comparison']['receipt_committed'])
        self.assertEqual(actual['agreements'][0]['receipt_state'], 'NOT_FULFILLED_BEFORE_REPLY')
        self.assertTrue(private['event_receipt_references'])
        self.store.capture_reply(self.handle, row['turn_id'], 'AUTHOR received', 'AUTHOR_OFFLINE_REPLY')
        self.store.mark_displayed(self.handle, row['turn_id']); self.admission.observe_turn(self.handle, row['turn_id'])
        row, context, core = self.context('当前约定是否核验')
        actual, private = self.validate(row, context, core)
        self.assertEqual(actual['agreements'][0]['receipt_state'], 'PERSISTED_BEFORE_REPLY')
        self.assertEqual(len(private['event_receipt_references']), 2)

    def test_wrong_projection_cannot_become_actual_host_truth(self):
        row, context, core = self.context('当前约定是否核验')
        for field, value in (('agreed_submission_requirement', '放宽成包含三项'),
                             ('verification_scope', 'UNKNOWN'), ('status', 'FULFILLED')):
            altered = deepcopy(context); altered['host_observation_before']['commitments'][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(g.GateError, 'AGREEMENT_TERMS_POLICY_OR_RECEIPT'):
                self.validate(row, altered, core)

    def test_cross_entity_and_pending_receipt_forgery_rejected(self):
        row, context, core = self.context(self.expected)
        altered = deepcopy(core); altered['current_entity_id'] = 'other'
        with self.assertRaisesRegex(g.GateError, 'ENTITY_OR_MODE'):
            self.validate(row, context, altered)
        changed = deepcopy(context); changed['host_observation_before']['current_text_submission_check']['receipt_committed'] = True
        with self.assertRaisesRegex(g.GateError, 'PENDING_COMPARISON'):
            self.validate(row, changed, core)

    def test_request_trace_and_source_cannot_be_replaced_behind_same_capture(self):
        row, context, core = self.context('来源记忆有哪些边界')
        genesis = g.load(g.ROOT/b.GENESIS)
        scope = {'max_output_tokens': 10, 'thinking': {'type': 'enabled'}, 'reasoning_effort': 'max'}
        request = {'model': 'AUTHOR_PRIVATE_MODEL', 'messages': context['messages'], 'max_tokens': 10,
                   'stream': False, 'thinking': scope['thinking'], 'reasoning_effort': 'max'}
        answer = 'AUTHOR offline response'; raw = sr.json_bytes({'choices': [{'message': {'content': answer}}]})
        row.update(call_id='AUTHOR_CALL', slot_id='AUTHOR_SLOT', raw_response=raw, raw_sha256=sr.sha_bytes(raw),
            assistant_text=answer, model='AUTHOR_PRIVATE_MODEL', request_json=g.canonical(request).decode('utf-8'),
            context_json=json.dumps(context, ensure_ascii=False), status='RESPONSE_CAPTURED',
            turn_status='DISPLAYED', capture_origin='TARGET_PROVIDER_CAPTURE')
        row['request_sha256'] = sr.sha_text(row['request_json'])
        capture = {k: row[k] for k in ('call_id','turn_id','session_id','raw_sha256','request_sha256')}
        receipt = dict(capture, slot_id=row['slot_id'], entity_id=self.handle.entity_id, status='DISPLAYED',
                       provider_status='RESPONSE_CAPTURED', preview_messages_sha256=g.digest(context['messages']))
        b._verify_call_context(row, capture, receipt, genesis, scope)
        forged = deepcopy(context); forged['source_memory_before']['SOURCE_FACT_ONLY'] = ['fabricated']
        changed = dict(row, context_json=json.dumps(forged, ensure_ascii=False))
        with self.assertRaisesRegex(g.GateError, 'SOURCE_ADMISSION_DIFFERS'):
            b._verify_call_context(changed, capture, receipt, genesis, scope)
        forged = deepcopy(context); forged['host_observation_before']['commitments'][0]['status'] = 'FULFILLED'
        changed = dict(row, context_json=json.dumps(forged, ensure_ascii=False))
        with self.assertRaisesRegex(g.GateError, 'HOST_TRACE_NOT_BOUND'):
            b._verify_call_context(changed, capture, receipt, genesis, scope)

    def test_current_correction_chain_preserves_original_and_replacement_scope(self):
        self.observed('标签为原始甲', 'AUTHOR observed')
        self.observed('更正：标签为原始甲；改为：标签为现行乙', 'AUTHOR corrected')
        row, context, core = self.context('现行更正是什么')
        actual, private = self.validate(row, context, core)
        self.assertEqual(actual['corrections'][0]['current_user_statement'], '标签为现行乙')
        self.assertEqual(actual['corrections'][0]['original_statement_for_topic_only'], '标签为原始甲')
        self.assertFalse(actual['corrections'][0]['old_statement_is_current'])
        changed = deepcopy(context)
        changed['host_observation_before']['current_corrections'][0]['current_user_statement'] = '标签为原始甲'
        with self.assertRaisesRegex(g.GateError, 'CORRECTION_SCOPE_OR_TEXT'):
            self.validate(row, changed, core)

    def test_real_verifier_runs_on_copy_and_original_journal_stays_unchanged(self):
        before = list(self.store.db.iterdump())
        expected = self.runtime.verify()
        with b._verified_copy(self.store.root/'runtime.sqlite3', g.ROOT,
                             self.store.marker['source_genesis_sha256']) as (_, _, _, _, actual):
            self.assertEqual(expected, actual)
        self.assertEqual(before, list(self.store.db.iterdump()))

    def test_source_evidence_retains_limits_and_unknown_is_not_absence(self):
        genesis = g.load(g.ROOT/b.GENESIS); before = deepcopy(genesis)
        facts = b._source_facts(genesis)
        self.assertEqual(facts['admitted_recollections'][0]['scope'], genesis['encoded_autobiographical_memory'][0]['scope'])
        self.assertEqual(facts['admitted_recollections'][0]['limits'], genesis['encoded_autobiographical_memory'][0]['limits'])
        self.assertEqual(facts['unadmitted_memory_existence'], 'UNKNOWN')
        self.assertEqual(facts['unadmitted_memory_accessibility'], 'UNKNOWN')
        self.assertFalse(facts['admission_list_is_exhaustive_life_or_memory_inventory'])
        self.assertEqual(genesis, before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
