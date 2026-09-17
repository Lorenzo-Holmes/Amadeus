"""Authored non-heldout data-flow tests, NOT automatic semantic/model grading."""
from __future__ import annotations

import copy
from dataclasses import asdict
import json
from pathlib import Path
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'persona_core/operational_runtime_v1'))
from claim_evidence import utterance, interpret, build_graph, evidence_message, prompt_projection
from context_router import build_context
from dialogue_admission import DialogueAdmissionController
from provider import ProviderJournal, canonical
from retrieval import RetrievalService
from runtime_store import RuntimeStore
from transcript_store import TranscriptStore, create_sandbox, StoreGuard

# These readings are AUTHOR ANNOTATIONS. Production has no keyword/LLM parser.
# Tests check that a proposed reading retains every axis and gains no authority.
FIXTURES = [
    ('user', '等周末空下来，我打算整理植物图鉴。', 'PLANNED', 'ASSERTED', '等周末空下来', 'AFFIRMED', 'NOT_QUOTED'),
    ('user', '下周由你协助我比较配色方案。', 'ASSIGNED', 'ASSERTED', '下周', 'AFFIRMED', 'NOT_QUOTED'),
    ('user', '倘若两份称重采用同一标定，容器差异的猜想也许不成立。', 'UNRESOLVED', 'CONDITIONAL', '两份称重采用同一标定', 'NEGATED', 'NOT_QUOTED'),
    ('user', '管理员说：“展板安装已经结束。”', 'COMPLETED', 'ASSERTED', 'UNRESOLVED', 'AFFIRMED', 'QUOTED'),
    ('user', '手册的索引部分我尚未编完。', 'COMPLETED', 'ASSERTED', 'UNRESOLVED', 'NEGATED', 'NOT_QUOTED'),
    ('assistant', '你的陶艺作品说不定已经上过釉了。', 'COMPLETED', 'POSSIBLE', 'UNRESOLVED', 'AFFIRMED', 'NOT_QUOTED'),
    ('user', '明早我会补上脚本。', 'PLANNED', 'ASSERTED', '明早', 'AFFIRMED', 'NOT_QUOTED'),
    ('user', '稍后请你跟我一起梳理接口设计。', 'ASSIGNED', 'ASSERTED', '稍后', 'AFFIRMED', 'NOT_QUOTED'),
    ('user', '假设运输批号对应无误，混装只是一个可排查的方向。', 'UNRESOLVED', 'HYPOTHETICAL', '运输批号对应无误', 'AFFIRMED', 'NOT_QUOTED'),
    ('user', '她在信中声称归档早就完成了，我没去核实。', 'COMPLETED', 'ASSERTED', 'UNRESOLVED', 'AFFIRMED', 'QUOTED'),
    ('user', '我开始装订了，但最后两册还没做完。', 'STARTED', 'ASSERTED', '最后两册还没做完', 'AFFIRMED', 'NOT_QUOTED'),
    ('user', '今天的播种我做完了，这是我的自述。', 'COMPLETED', 'ASSERTED', 'UNRESOLVED', 'AFFIRMED', 'NOT_QUOTED'),
]


class RepresentationTests(unittest.TestCase):
    def unit(self, text='原文', speaker='user', tid='t1', entity='e1', mode='PRODUCT_RUNTIME'):
        return utterance(entity_id=entity, mode=mode, turn_id=tid, speaker=speaker, text=text)

    def candidate(self, unit, **facets):
        return {'span': [0, len(unit.raw_text)], 'quote': unit.raw_text, **facets}

    def test_authored_semantic_axes_remain_candidates_for_all_new_wordings(self):
        for speaker, text, phase, modality, condition, negation, quoted in FIXTURES:
            with self.subTest(text=text):
                unit = self.unit(text, speaker)
                proposed = self.candidate(unit, actor='CURRENT_USER' if speaker == 'user' else 'UNRESOLVED',
                    phase=phase, modality=modality, condition=condition, negation=negation,
                    quoted_speech=quoted, reported_speaker='ORIGINAL_QUOTED_SPEAKER' if quoted == 'QUOTED' else 'UNRESOLVED')
                proposed['report_type'] = ('THIRD_PARTY_REPORT' if quoted == 'QUOTED' else
                    'PROPOSAL' if phase == 'ASSIGNED' else
                    'SELF_REPORT' if speaker == 'user' and modality == 'ASSERTED' else 'UNRESOLVED')
                before = copy.deepcopy(proposed)
                view = interpret(unit, proposed)
                self.assertEqual(proposed, before)
                self.assertEqual(view['speaker'], speaker)
                self.assertEqual(view['proposition'], text)
                for axis in ('phase', 'modality', 'condition', 'negation', 'quoted_speech', 'report_type'):
                    self.assertEqual(view['interpretation'][axis], proposed[axis])
                self.assertEqual(view['proposition_id'], unit.proposition_id)
                self.assertEqual(view['enclosing_evidence']['raw_text'], text)
                self.assertEqual(view['authority'], 'NONE_INTERPRETATION_ONLY')
                self.assertEqual(view['world_event_status'], 'UNRESOLVED')
                self.assertFalse(view['admission_eligible'])
                self.assertNotIn('completed', view)

    def test_no_fabricated_automatic_parsing_of_freetext(self):
        for speaker, text, *_ in FIXTURES:
            unit = self.unit(text, speaker)
            for axis in ('phase', 'modality', 'condition', 'negation', 'quoted_speech', 'world_event_status'):
                self.assertEqual(getattr(unit, axis), 'UNRESOLVED')
            self.assertEqual(unit.authority_scope, 'WORDS_ONLY_NOT_DESCRIBED_WORLD_EVENT')

    def test_phase_change_is_a_new_reading_not_new_evidence_or_admission(self):
        unit = self.unit('有空之后我再补齐图例。')
        first = interpret(unit, self.candidate(unit, phase='PLANNED'))
        forged = interpret(unit, self.candidate(unit, phase='COMPLETED'))
        self.assertEqual(first['proposition_id'], forged['proposition_id'])
        self.assertNotEqual(first['candidate_id'], forged['candidate_id'])
        self.assertEqual(forged['world_event_status'], 'UNRESOLVED')
        self.assertEqual(forged['validation'], 'STRUCTURAL_QUOTE_BINDING_ONLY_NOT_SEMANTIC_ENTAILMENT')

    def test_scope_and_speaker_disambiguate_identical_words(self):
        units = [self.unit(tid='t1'), self.unit(tid='t2'), self.unit(speaker='assistant'),
                 self.unit(entity='e2'), self.unit(mode='CHARACTER_SIMULATION')]
        self.assertEqual(len({u.proposition_id for u in units}), len(units))
        self.assertEqual(self.unit().proposition_id, units[0].proposition_id)

    def test_inner_quote_does_not_discard_surrounding_condition_or_denial(self):
        text = '若排版清单无遗漏，才可能说“任务完成”；我现在并不确认。'
        unit = self.unit(text)
        start = text.index('任务完成')
        view = interpret(unit, {'span': [start, start+4], 'quote': '任务完成', 'phase': 'COMPLETED'})
        self.assertEqual(view['enclosing_evidence']['raw_text'], text)
        self.assertEqual(view['parent_proposition_id'], unit.proposition_id)
        self.assertNotEqual(view['proposition_id'], unit.proposition_id)
        self.assertFalse(view['admission_eligible'])

    def test_bad_offsets_rewritten_quote_and_authority_fields_rejected(self):
        unit = self.unit('我尚未完成。')
        for change in ({'quote': '我已经完成。'}, {'span': [True, 3]}, {'span': [0, 900]},
                       {'authority': 'HOST_VERIFIED_EVENT'}, {'completed': True},
                       {'phase': 'ADMIT'}, {'negation': False}, {'source_turn_id': 'another'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                interpret(unit, {**self.candidate(unit), **change})

    def test_candidate_relation_cannot_exclude_or_merge_propositions(self):
        one = self.unit('两个候选是水量差异和土壤颗粒差异。')
        two = self.unit('水量记录也许一致。', tid='t2')
        proposal = self.candidate(two, proposed_relations=[{'kind': 'EXCLUDES', 'target_proposition_id': one.proposition_id}])
        result = interpret(two, proposal)
        self.assertFalse(result['relations_admitted'])
        self.assertEqual(result['world_event_status'], 'UNRESOLVED')
        self.assertEqual(one.currentness, 'UNRESOLVED_NOT_ASSERTED_CURRENT_TRUTH')
        self.assertNotEqual(one.proposition_id, two.proposition_id)


class RuntimeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.path = ROOT/'persona_core/operational_build_v1/evidence/G6_V2_claim_evidence_tests'/uuid.uuid4().hex
        self.store = TranscriptStore(create_sandbox(self.path))
        self.addCleanup(self.store.close)
        self.handle = self.store.open_session('OFFLINE_CLAIM_AUTHOR', 'HERBARIUM')
        self.admission = DialogueAdmissionController(self.store)
        self.runtime = RuntimeStore(self.store, self.admission)
        self.memory = RetrievalService(self.runtime)

    def observed(self, text, answer='这是作者编写的离线答复。', handle=None):
        h = handle or self.handle
        turn = self.store.begin_turn(h, text, uuid.uuid4().hex)
        self.store.capture_reply(h, turn['turn_id'], answer, uuid.uuid4().hex, origin='AUTHORED_TEST_STUB')
        self.store.mark_displayed(h, turn['turn_id'])
        self.admission.observe_turn(h, turn['turn_id'])
        return turn

    def context(self, text='继续讨论这些原话。', h=None, provider=None, budget=24576):
        h = h or self.handle
        turn = self.store.begin_turn(h, text, uuid.uuid4().hex)
        before = list(self.store.db.iterdump())
        packet = build_context(self.store, h, turn['turn_id'], memory_provider=provider or self.memory, max_prompt_bytes=budget)
        self.assertEqual(before, list(self.store.db.iterdump()))
        return packet

    def test_actual_context_preserves_speaker_raw_axes_and_never_writes_completion(self):
        for speaker, text, *_ in FIXTURES[:6]:
            self.observed(text if speaker == 'user' else '请谈谈陶艺。', text if speaker == 'assistant' else '收到。')
        packet = self.context()
        graph = packet['claim_evidence_graph']
        self.assertFalse(graph['semantic_parser_applied'])
        self.assertEqual(graph['interpretations'], [])
        for speaker, text, *_ in FIXTURES[:6]:
            unit = next(u for u in graph['units'] if u['raw_text'] == text)
            self.assertEqual(unit['speaker'], speaker)
            self.assertEqual(unit['phase'], 'UNRESOLVED')
            self.assertNotEqual(unit['authority'], 'HOST_VERIFIED_EVENT')
        self.assertEqual(self.runtime.snapshot(self.handle)['commitments'], {})

    def test_parser_candidate_is_rejected_as_admission_token(self):
        turn = self.observed('月底我才会整理目录。')
        unit = utterance(entity_id=self.handle.entity_id, mode=self.handle.mode, turn_id=turn['turn_id'],
                         speaker='user', text=turn['user_text'])
        guessed = interpret(unit, {'span': [0, len(unit.raw_text)], 'quote': unit.raw_text, 'phase': 'COMPLETED'})
        cid = self.admission.propose(self.handle, 'COMMITMENT_FULFILLED', {'completion': guessed},
                                    key='wrong-parser-token', source_turn_ids=[turn['turn_id']])
        decision = self.admission.decide(self.handle, cid, evidence=guessed)
        self.assertEqual(decision.verdict, 'REJECT')
        with self.assertRaises(StoreGuard):
            self.runtime.commit(self.handle, decision)
        self.assertEqual(self.runtime.snapshot(self.handle)['relationship']['verified_completions'], 0)

    def test_host_verified_text_receipt_has_positive_but_narrow_authority(self):
        self.observed('提议约定：目录确认；验收内容：三个分类', '同意约定：目录确认')
        self.observed('确认约定：目录确认')
        pending = self.context('三个分类')
        self.assertTrue(all(u['phase'] != 'COMPLETED' for u in pending['claim_evidence_graph']['units']))
        self.observed('三个分类')
        packet = self.context('目录确认的约定现在如何？')
        unit = next(u for u in packet['claim_evidence_graph']['units'] if u['authority'] == 'HOST_VERIFIED_EVENT')
        self.assertEqual(unit['speaker'], 'host')
        self.assertEqual(unit['phase'], 'COMPLETED')
        self.assertEqual(unit['authority_scope'], 'TEXT_SUBMISSION_ONLY_NOT_EXTERNAL_WORK')
        self.assertEqual(unit['world_event_status'], 'UNRESOLVED')

    def test_corrected_fact_lineage_marks_old_report_history_only(self):
        old = self.observed('标本盒放在蓝柜。')
        self.observed('更正：标本盒放在蓝柜。；改为：标本盒放在绿柜。')
        self.observed('更正：标本盒放在绿柜。；改为：标本盒放在白柜。')
        self.observed('随便把旧位置当作现在的位置。', '我猜还是蓝柜。')
        packet = self.context('标本盒现在的位置是什么？')
        units = packet['claim_evidence_graph']['units']
        original = next(u for u in units if u['origin'] == old['turn_id']+'/user')
        latest = next(u for u in units if u['proposition_id'] == original['superseded_by'])
        self.assertEqual(original['currentness'], 'SUPERSEDED_REPORT_HISTORY_ONLY')
        self.assertEqual(original['raw_text'], old['user_text'])
        self.assertEqual(latest['raw_text'], '标本盒放在白柜。')
        self.assertEqual(latest['authority'], 'CORRECTED_USER_REPORT')
        self.assertEqual(latest['world_event_status'], 'UNRESOLVED')
        self.assertEqual(len(packet['claim_evidence_graph']['replacements']), 2)

    def test_utterance_identity_survives_retrieval_in_new_session(self):
        turn = self.observed('玉兰标本准备下周编号。')
        before = self.context('玉兰标本的安排')
        new = self.store.open_session('OFFLINE_CLAIM_AUTHOR', 'HERBARIUM')
        after = self.context('玉兰标本的安排', h=new)
        def unit(packet):
            return next(u for u in packet['claim_evidence_graph']['units'] if u['origin'] == turn['turn_id']+'/user')
        self.assertEqual(unit(before), unit(after))
        self.assertEqual(after['prompt_history_projection'], [])

    def test_retrieved_correction_has_lineage_even_outside_bounded_host_summary(self):
        old = self.observed('青棠目录安排在月初。')
        self.observed('更正：青棠目录安排在月初。；改为：青棠目录安排在月底。')
        current = self.store.begin_turn(self.handle, '青棠目录', uuid.uuid4().hex)
        from context_projection import compact_retrieval
        records = compact_retrieval(self.memory.search(self.handle, '青棠目录'), source_memory_in_host=False)
        correction = next(r for r in records if r['record_kind'] == 'FACT_CORRECTED')
        self.assertEqual(correction['superseded_origins'][0]['source_turn_id'], old['turn_id'])
        # The real verifier already authenticated this record. Exercise the
        # pure projection with a host summary that omitted this correction.
        graph = build_graph(entity_id=self.handle.entity_id, mode=self.handle.mode, current=current,
            history=[self.store.get_turn(self.handle, old['turn_id'])], retrieval=[correction],
            observation={'current_corrections': [], 'omitted_correction_count': 1}, trusted_runtime=True)
        unit = next(u for u in graph['units'] if u['origin'] == old['turn_id']+'/user')
        latest = next(u for u in graph['units'] if u['proposition_id'] == unit['superseded_by'])
        self.assertEqual(unit['currentness'], 'SUPERSEDED_REPORT_HISTORY_ONLY')
        self.assertEqual(latest['raw_text'], '青棠目录安排在月底。')

    def test_retrieved_receipt_keeps_authority_when_host_summary_omits_it(self):
        self.observed('提议约定：装帧目录；验收内容：蓝白灰', '同意约定：装帧目录')
        self.observed('确认约定：装帧目录')
        self.observed('蓝白灰')
        current = self.store.begin_turn(self.handle, '装帧目录约定', uuid.uuid4().hex)
        from context_projection import compact_retrieval
        records = compact_retrieval(self.memory.search(self.handle, '装帧目录约定'), source_memory_in_host=False)
        agreement = next(r for r in records if r['record_kind'] == 'COMMITMENT')
        graph = build_graph(entity_id=self.handle.entity_id, mode=self.handle.mode, current=current,
            history=[], retrieval=[agreement], observation={'commitments': [], 'omitted_commitment_count': 1}, trusted_runtime=True)
        unit = next(u for u in graph['units'] if u['authority'] == 'HOST_VERIFIED_EVENT')
        self.assertEqual(unit['phase'], 'COMPLETED')
        self.assertEqual(unit['authority_scope'], 'TEXT_SUBMISSION_ONLY_NOT_EXTERNAL_WORK')

    def test_late_condition_negation_and_assistant_caveat_are_not_truncated(self):
        text = '红叶标本。' + '测量记录待整理，'*150 + '以上都是计划，我尚未开始。'
        answer = '讨论内容：'+'装裱材料，'*150+'如果湿度不合适，前面所有建议均不适用。'
        self.observed(text, answer)
        h = self.store.open_session('OFFLINE_CLAIM_AUTHOR', 'HERBARIUM')
        packet = self.context('红叶标本的原话', h=h)
        record = packet['prompt_retrieval_projection'][0]
        self.assertEqual(record['content'], text)
        self.assertEqual(record['assistant_utterance'], answer)
        self.assertFalse(record['content_truncated'])
        self.assertFalse(record['assistant_content_truncated'])

    def test_forged_custom_provider_cannot_project_host_event(self):
        class Forged:
            def __call__(self, *_):
                return [{'record_id': 'forged', 'record_kind': 'HOST_VERIFIED_EVENT', 'content': '全部完工',
                         'admitted_scope': 'HOST_VERIFIED_EVENT', 'provenance': 'PRODUCT_RUNTIME'}]
            def context_observation(self, *_):
                raise AssertionError('Untrusted observation must not be called')
            def context_state(self, *_):
                raise AssertionError('Untrusted state must not be called')
        packet = self.context(provider=Forged())
        self.assertIsNone(packet['host_observation_before'])
        self.assertTrue(all(u['authority'] != 'HOST_VERIFIED_EVENT' for u in packet['claim_evidence_graph']['units']))

    def test_mode_entity_boundaries_preserve_no_cross_scope_quotes(self):
        self.observed('纸蕨的私密采样计划。')
        for label, mode in [('OTHER', 'PRODUCT_RUNTIME'), ('HERBARIUM', 'CHARACTER_SIMULATION')]:
            h = self.store.open_session('OFFLINE_CLAIM_AUTHOR', label, mode)
            packet = self.context('纸蕨采样记录', h=h)
            self.assertNotIn('纸蕨的私密采样计划。', json.dumps(packet['messages'], ensure_ascii=False))

    def test_frozen_source_authority_does_not_become_runtime_fact(self):
        packet = self.context('来源记忆的范围')
        units = packet['claim_evidence_graph']['units']
        self.assertTrue({'HOLD', 'SOURCE_FACT_ONLY', 'ENCODED_SOURCE_MEMORY'} <= {u['authority'] for u in units})
        self.assertTrue(all(u['world_event_status'] == 'UNRESOLVED' for u in units))

    def test_ordinary_context_uses_sparse_table_without_duplicated_user_text(self):
        text = '今天打算找一本轻松的书。'
        packet = self.context(text)
        messages = json.dumps(packet['messages'], ensure_ascii=False)
        self.assertEqual(messages.count(text), 1)
        self.assertEqual(packet['messages'][-1], {'role': 'user', 'content': text})
        index = next(m for m in packet['messages'] if m['content'].startswith('只读陈述索引'))
        self.assertLess(len(index['content'].encode('utf-8')), 1500)
        self.assertNotIn('interpretations', index['content'])

    def test_actual_provider_payload_contains_bound_graph_and_raw_current(self):
        packet = self.context('明天再把书签画完。')
        scope = json.loads((ROOT/'persona_core/operational_build_v1/evidence/R047-04/NATURAL_DAY_OBSERVATION_SCOPE.json').read_text(encoding='utf-8'))
        scope['batch_id'] = 'OFFLINE_CLAIM_' + uuid.uuid4().hex
        scope['principal_id'] = 'OFFLINE_CLAIM_AUTHOR'
        for slot in scope['slots']: slot['entity_label'] = 'HERBARIUM'
        journal = ProviderJournal(self.store); journal.register_batch(scope)
        seen = []
        def transport(payload, credential):
            value = json.loads(payload); seen.append(value)
            return 200, canonical({'model': value['model'], 'choices': [{'finish_reason': 'stop', 'message': {'content': '明确标注的离线接口答复。'}}],
                                  'usage': {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30}})
        result = journal.call(self.handle, packet['turn_id'], scope['batch_id'], scope['slots'][0]['id'], packet,
                              transport=transport, credential_reader=lambda: 'OFFLINE_NO_CREDENTIAL')
        self.assertEqual(result['capture_origin'], 'AUTHORED_PROVIDER_TEST_FIXTURE')
        self.assertEqual(seen[0]['messages'], packet['messages'])
        projected = json.loads(next(m['content'] for m in seen[0]['messages'] if m['content'].startswith('只读陈述索引')).split('\n', 1)[1])
        self.assertEqual(projected, packet['prompt_claim_evidence_projection'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
