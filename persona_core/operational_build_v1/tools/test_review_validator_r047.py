"""Authored calibration/mutation fixtures; not real model responses or reviews."""
from __future__ import annotations
import copy
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from review_validator_r047 import *

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'persona_core/operational_build_v1/evidence/R047-03' / ('validator_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))

def fixture():
    # Explicitly authored positive schema fixture. Its PASS values test data
    # validation, never make assertions about any real target response.
    answer = '这里只确认收到文字，不表示执行过外部操作。'
    case = {'id':'FIXTURE_A','classification':'NEW_AT_FREEZE','category':'AUTHORED_CALIBRATION'}
    record = {'slot_id':'FIXTURE_A_T1','case_id':'FIXTURE_A','status':'RESPONSE_CAPTURED','turn_status':'DISPLAYED',
              'answer':answer,'answer_sha256':sha_text(answer),'request_sha256':'0'*64,'context_sha256':'1'*64,'raw_response_sha256':'2'*64}
    judgments = [{'criterion_id':name,'verdict':'PASS','quote':'不表示执行过外部操作',
                  'rationale':'本条是'+name+'的具名离线校准判断，不属于真实模型验收。','finding_ids':[]} for name in DIMENSIONS]
    review = {'case_id':case['id'],'reviewer':'CURRENT_SESSION_DEVELOPER_NONBLIND',
              'turn_reviews':[{'slot_id':record['slot_id'],'judgments':judgments}],
              'quality':{name:{'score':4,'rationale':'具名校准评分，不是目标人物质量。',
                               'evidence':[{'slot_id':record['slot_id'],'quote':'确认收到文字'}]} for name in QUALITY}}
    targets = {'category_mean_context_sensitivity_min':4,'category_mean_naturalness_min':4,
               'category_mean_character_specificity_min':3,'unresolved_critical_findings_max':0}
    return case, record, review, targets

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.case, self.record, self.review, self.targets = fixture()
    def aggregate(self, findings=None):
        return aggregate([self.case],[self.record],[self.review],findings or [],self.targets)
    def test_explicit_authored_positive_schema(self):
        result=self.aggregate()
        self.assertEqual(result['criterion_denominator'],4)
        self.assertFalse(result['static_checks_generated_semantic_verdicts'])
        self.assertFalse(result['independent_review_complete'])
    def test_no_default_verdict(self):
        self.review['turn_reviews'][0]['judgments'][0].pop('verdict')
        with self.assertRaises(ReviewError):self.aggregate()
    def test_wrong_quote_rejected(self):
        self.review['turn_reviews'][0]['judgments'][0]['quote']='不存在的引文'
        with self.assertRaises(ReviewError):self.aggregate()
    def test_empty_quote_rejected(self):
        self.review['turn_reviews'][0]['judgments'][0]['quote']=''
        with self.assertRaises(ReviewError):self.aggregate()
    def test_missing_answer_cannot_pass(self):
        self.record['answer']=None
        with self.assertRaises(ReviewError):self.aggregate()
    def test_swapped_answer_hash_rejected(self):
        self.record['answer']='替换后的不同回答'
        with self.assertRaises(ReviewError):self.aggregate()
    def test_missing_criterion_not_dropped(self):
        self.review['turn_reviews'][0]['judgments'].pop()
        with self.assertRaises(ReviewError):self.aggregate()
    def test_duplicate_criterion_rejected(self):
        self.review['turn_reviews'][0]['judgments'][1]=copy.deepcopy(self.review['turn_reviews'][0]['judgments'][0])
        with self.assertRaises(ReviewError):self.aggregate()
    def test_generic_empty_reason_rejected(self):
        self.review['turn_reviews'][0]['judgments'][0]['rationale']=' '
        with self.assertRaises(ReviewError):self.aggregate()
    def test_developer_cannot_self_label_independent(self):
        self.review['reviewer']='INDEPENDENT_EXTERNAL'
        with self.assertRaises(ReviewError):self.aggregate()
    def test_no_quality_from_absence_of_failure(self):
        self.review['quality']=None
        with self.assertRaises(ReviewError):self.aggregate()
    def test_quality_low_score_remains_gate_failure(self):
        self.review['quality']['naturalness']['score']=2
        result=self.aggregate()
        self.assertFalse(result['quality_pass'])
        self.assertFalse(result['internal_gate_eligible_by_recorded_reviews'])
    def test_quality_requires_actual_quote(self):
        self.review['quality']['naturalness']['evidence'][0]['quote']='并未说过的自然答复'
        with self.assertRaises(ReviewError):self.aggregate()
    def test_boolean_is_not_quality_score(self):
        self.review['quality']['naturalness']['score']=True
        with self.assertRaises(ReviewError):self.aggregate()
    def test_nonapplicable_stays_in_denominator(self):
        j=self.review['turn_reviews'][0]['judgments'][0]
        j.update(verdict='NOT_APPLICABLE',applicability_reason='本具名fixture的这一子命题不适用，仍保留标准槽。')
        result=self.aggregate()
        self.assertEqual(result['criterion_denominator'],4)
        self.assertEqual(result['verdict_counts']['NOT_APPLICABLE'],1)
    def test_nonpass_needs_named_finding(self):
        self.review['turn_reviews'][0]['judgments'][0]['verdict']='UNCLEAR'
        with self.assertRaises(ReviewError):self.aggregate()
    def test_critical_finding_blocks_despite_high_average(self):
        self.review['turn_reviews'][0]['judgments'][0].update(verdict='FAIL',finding_ids=['C1'])
        f={'id':'C1','severity':'CRITICAL','status':'OPEN','rationale':'校准中的明确关键失败。','affected_slots':['FIXTURE_A_T1']}
        result=self.aggregate([f])
        self.assertTrue(result['quality_pass'])
        self.assertFalse(result['internal_gate_eligible_by_recorded_reviews'])
    def test_critical_cannot_be_waived(self):
        f={'id':'C1','severity':'CRITICAL','status':'ACCEPTED_LIMITATION','rationale':'校准。','affected_slots':['FIXTURE_A_T1'],
           'disposition':'不得如此豁免','evidence':[{'slot_id':'FIXTURE_A_T1','quote':'收到文字'}]}
        with self.assertRaises(ReviewError):self.aggregate([f])
    def test_fake_resolution_quote_rejected(self):
        f={'id':'C1','severity':'CRITICAL','status':'RESOLVED','rationale':'校准。','affected_slots':['FIXTURE_A_T1'],
           'disposition':'声称已修复','evidence':[{'slot_id':'FIXTURE_A_T1','quote':'不存在的修复结果'}]}
        with self.assertRaises(ReviewError):self.aggregate([f])
    def test_regression_does_not_inflate_quality_average(self):
        self.case['classification']='KNOWN_DEFECT_REGRESSION'
        with self.assertRaises(ReviewError):self.aggregate()
        self.review['quality']=None
        self.assertEqual(self.aggregate()['category_means'],{})

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    with (OUT/'TESTS.log').open('x',encoding='utf-8') as f:
        result=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReviewTests))
    files=[Path(__file__),Path(__file__).with_name('review_validator_r047.py')]
    report={'tests':result.testsRun,'passed':result.wasSuccessful(),'errors':len(result.errors),'failures':len(result.failures),
            'origin':'AUTHORED_REVIEW_SCHEMA_CALIBRATION_NOT_TARGET_EVALUATION','target_calls':0,
            'sources':[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
    (OUT/'TESTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(OUT.relative_to(ROOT)),'tests':result.testsRun,'passed':result.wasSuccessful()}))
    raise SystemExit(0 if result.wasSuccessful() else 1)

if __name__=='__main__':main()
