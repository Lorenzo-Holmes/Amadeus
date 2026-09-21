"""Mechanical expression-contract tests, not target-model semantic grading.

Authored examples cover request scope and evidence axes without importing a
benchmark case or expecting an answer. Literal checks pin the general prompt
contract; they do not prove the model follows it or performs the reasoning.
"""
from pathlib import Path
import copy
import itertools
import json
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'persona_core/operational_runtime_v1'))
from expression_prompt import build_system, compact_focus

TOPICS = ('EXACT_OUTPUT_SHAPE', 'THIRD_PARTY_UNCERTAINTY', 'ATTRIBUTION_AND_TENSE',
          'DRAFT_EVIDENCE', 'SCIENTIFIC_SCOPE', 'MEMORY_EPISTEMICS',
          'RESERVED_CARE', 'AGREEMENT_PLAIN_LANGUAGE')
MODES = ('PRODUCT_RUNTIME', 'CHARACTER_SIMULATION', 'SOURCE_AUDIT')


class ExpressionAxesV9Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frozen = ROOT / 'persona_core/runtime/genesis/frozen'
        cls.constitution = json.loads((frozen / 'PERSONA_CONSTITUTION_FROZEN_R034.json').read_text(encoding='utf-8'))
        cls.self_model = json.loads((frozen / 'SELF_MODEL_FROZEN_R034.json').read_text(encoding='utf-8'))

    def system(self, mode='PRODUCT_RUNTIME'):
        return build_system(mode, [], self.constitution, self.self_model)

    def focus(self, text, prior=(), topics=()):
        return compact_focus(text, prior, False, 'PRODUCT_RUNTIME', {'topics': list(topics)})

    def test_default_draft_policy_preserves_explicit_explanation_and_restatement(self):
        prompt = self.system()
        self.assertIn('明确要求的解释、多份输出或完整重述照做', prompt)
        self.assertNotIn('澄清只答新差异。', prompt)

    def test_responsibility_start_and_completion_have_separate_evidence_contract(self):
        prompt = self.system()
        self.assertIn('Evidence per fact/draft', prompt)
        self.assertIn('duty/start/completion/promise', prompt)
        # Stating that completion needs evidence is not by itself enough to
        # rule out an unsupported transition from responsibility to started.
        self.assertNotIn('原话说负责某事，不等于已经做完', prompt)

    def test_reasoning_contract_checks_direction_and_logical_conditions(self):
        prompt = self.system()
        self.assertIn('Check definitions, quantities/signs', prompt)
        self.assertIn('necessary/sufficient', prompt)
        self.assertIn('assume givens.', prompt)
        self.assertIn('/auxiliary premises', prompt)

    def test_general_risk_contract_is_not_limited_to_creative_tasks(self):
        ordinary = self.system()
        self.assertIn('Advice/risk≠necessity', ordinary)
        focus = self.focus('比较几个做法的利弊。', topics=['THIRD_PARTY_UNCERTAINTY'])
        self.assertIn('建议或风险', focus['instruction'])
        self.assertNotIn('创作建议只讲', focus['instruction'])

    def test_scientific_explanation_does_not_inherit_an_earlier_draft_contract(self):
        focus = self.focus('请完整解释这个模型的假设和推导，分三段分析。',
                           ['请润色这份通知。'], ['DRAFT_EVIDENCE', 'SCIENTIFIC_SCOPE'])
        self.assertIsNone(focus['current_contract'])
        self.assertIn('仅要成品时', focus['instruction'])
        self.assertNotIn('默认一份', focus['instruction'])

    def test_explicit_restatement_overrides_followup_delta_default(self):
        focus = self.focus('这轮请把先前的推导从头讲一遍，包括每一步。',
                           ['解释这个模型的量纲。'], ['SCIENTIFIC_SCOPE'])
        self.assertIsNone(focus['current_contract'])
        self.assertIn('未要求重述时', focus['instruction'])
        self.assertNotIn('\n续问只答新差异；', focus['instruction'])

    def test_requested_draft_plus_explanation_retains_current_intent_authority(self):
        focus = self.focus('请改写这段通知，再解释修改理由。', topics=['DRAFT_EVIDENCE'])
        self.assertEqual(focus['current_contract'], 'FAITHFUL_REWRITE')
        self.assertIn('明确要求优先', focus['instruction'])
        self.assertIn('未要求的', focus['instruction'])

    def test_new_epistemic_rules_never_interpolate_user_or_prior_claims(self):
        marker = 'UNTRUSTED_AXES_TEST_MARKER'
        supplied = {'topics': list(TOPICS), 'instruction': marker}
        prior = [marker + '请完整解释这个模型。']
        before = copy.deepcopy((supplied, prior))
        focus = compact_focus(marker, prior, True, 'PRODUCT_RUNTIME', supplied)
        self.assertNotIn(marker, focus['instruction'])
        self.assertEqual((supplied, prior), before)
        self.assertFalse(focus['user_facts_inferred'])
        self.assertEqual(focus['authority'], 'NONE_EXPRESSION_SELECTION_ONLY')

    def test_no_new_external_action_is_needed_to_build_expression(self):
        with patch('socket.socket', side_effect=AssertionError('No provider call allowed')):
            self.system()
            self.focus('比较这个推导的两个方向。', topics=['SCIENTIFIC_SCOPE'])

    def test_all_topic_contract_mode_and_phase_combinations_stay_bounded(self):
        texts = ('继续讨论。', '请拟一份通知。', '先保留未知。', '不想听说教。')
        for flags, text, mode, phase, prior in itertools.product(
                itertools.product((False, True), repeat=len(TOPICS)), texts, MODES,
                (None, 'RECEIVED_PENDING_VERIFICATION'), ([], ['active context'])):
            selected = [t for t, on in zip(TOPICS, flags) if on]
            focus = compact_focus(text, prior, True, mode, {'topics': selected},
                                  submission_phase=phase)
            size = len(json.dumps(focus, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
            self.assertLess(size, 1600)
        for mode in MODES:
            self.assertLess(len(self.system(mode).encode('utf-8')), 4500)


if __name__ == '__main__':
    unittest.main(verbosity=2)
