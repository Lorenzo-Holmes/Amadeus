"""Long-history retrieval with real SQLite data paths and authored test dialogue."""
from __future__ import annotations
import json
import sys
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CODE = ROOT / 'persona_core/operational_runtime_v1'
sys.path.insert(0, str(CODE))
from transcript_store import TranscriptStore, create_sandbox, StoreGuard, file_sha
from admission import AdmissionController
from runtime_store import RuntimeStore
from retrieval import RetrievalService
from recovery import create_backup, restore_backup
from context_router import build_context
from test_admission_runtime_r046 import AdmissionRuntimeTests as Helpers

OUT = ROOT / 'persona_core/operational_build_v1/evidence/R046-04' / ('run_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))

class RetrievalTests(unittest.TestCase):
    turn, agreement, state = Helpers.turn, Helpers.agreement, Helpers.state
    def setUp(self):
        self.root = create_sandbox(OUT / self._testMethodName)
        self.s = TranscriptStore(self.root)
        self.h = self.s.open_session('OFFLINE_OPERATOR', 'A')
        self.b = self.s.open_session('OFFLINE_OPERATOR', 'B')
        self.a = AdmissionController(self.s)
        self.r = RuntimeStore(self.s, self.a)
        self.q = RetrievalService(self.r)
    def tearDown(self):
        self.s.close()
    def observed(self, text, handle=None, answer='这是具名离线答复。'):
        h = handle or self.h
        t = self.turn(text, answer, h)
        return self.a.observe_turn(h, t)['commit']['event_id']
    def search(self, text, handle=None, **kwargs):
        return self.q.search(handle or self.h, text, **kwargs)

    def test_120_unrelated_events_do_not_hide_early_agreement(self):
        cid, _, event = self.agreement(text='提交棱镜的原始测量表')
        for i in range(120):
            self.observed('无关的日常话题记录，编号' + str(i))
        result = self.search('早期棱镜原始测量表的约定是什么？')
        match = next(r for r in result if r['record_id'] == cid)
        self.assertEqual(match['status'], 'OPEN')
        self.assertIn(event['event_id'], match['event_ids'])
        self.assertGreaterEqual(self.r.verify()['events'], 121)
        (self.root / 'LONG_HISTORY_QUERY.json').write_text(json.dumps({'unrelated_records': 120, 'result': result}, ensure_ascii=False, indent=2), encoding='utf-8')

    def test_fulfillment_supersedes_open_status_after_120_events(self):
        cid, expected, _ = self.agreement(text='提交棱镜的原始测量表')
        for i in range(120):
            self.observed('另一类无关交互' + str(i))
        t = self.turn(expected)
        self.r.commit(self.h, self.a.verify_text_submission(self.h, cid, t))
        result = [r for r in self.search('棱镜测量表约定完成了吗') if r['record_id'] == cid]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['status'], 'FULFILLED')
        self.assertEqual(result[0]['admitted_scope'], 'VERIFIED_TEXT_SUBMISSION_ONLY')

    def test_correction_found_via_old_topic_but_old_value_not_returned(self):
        old = self.observed('棱镜测量表约好周三提交')
        t = self.turn('更正，改为周五，不是周三。')
        new = self.r.commit(self.h, self.a.correct_user_statement(self.h, old, t, '改为周五'))['event_id']
        result = self.search('棱镜测量表哪天')
        corrected = next(r for r in result if r['record_id'] == new)
        self.assertEqual(corrected['content'], '改为周五')
        self.assertIn(old, corrected['superseded_event_ids'])
        self.assertNotIn(old, [r['record_id'] for r in result])

    def test_multiple_corrections_resolve_latest(self):
        old = self.observed('光谱预约原先是周一')
        t = self.turn('更正为周二')
        middle = self.r.commit(self.h, self.a.correct_user_statement(self.h, old, t, '周二'))['event_id']
        t = self.turn('再次更正为周六')
        latest = self.r.commit(self.h, self.a.correct_user_statement(self.h, middle, t, '周六'))['event_id']
        result = self.search('光谱预约时间')
        row = next(r for r in result if r['record_id'] == latest)
        self.assertEqual(row['content'], '周六')
        self.assertEqual(set(row['superseded_event_ids']), {old, middle})

    def test_b_cannot_retrieve_a_private_agreement(self):
        cid, _, _ = self.agreement(text='保密棱镜方案提交约定')
        result = self.search('保密棱镜方案提交约定', self.b)
        self.assertNotIn(cid, [r['record_id'] for r in result])
        self.assertEqual(result, [])

    def test_similar_topic_still_filters_entity_before_ranking(self):
        a = self.observed('海报的私密版本A')
        b = self.observed('海报的私密版本B', self.b)
        result = self.search('海报', self.b)
        self.assertIn(b, [r['record_id'] for r in result])
        self.assertNotIn(a, [r['record_id'] for r in result])
        self.assertTrue(all(r['entity_id'] == self.b.entity_id for r in result))

    def test_absence_is_empty_results_not_a_never_happened_claim(self):
        self.observed('天气普通')
        self.assertEqual(self.search('UNMENTIONED_TOKEN_912X'), [])
        self.assertFalse(self.q.context_state(self.h)['retrieval_absence_means_never_happened'])

    def test_all_source_provenances_preserved(self):
        result = self.search('来源记忆', limit=12)
        self.assertTrue({'HOLD', 'SOURCE_FACT_ONLY', 'ENCODED_SOURCE_MEMORY'}.issubset({r['provenance'] for r in result}))
        for row in result:
            if row['provenance'] in {'HOLD', 'SOURCE_FACT_ONLY'}:
                self.assertEqual(row['first_person_scope'], 'NOT_FIRST_PERSON_AUTOBIOGRAPHY')
                self.assertFalse(row['hold_means_absence'])

    def test_runtime_provenance_not_upgraded_to_source(self):
        event = self.observed('我们讨论过棱镜的配色')
        row = next(r for r in self.search('棱镜配色') if r['record_id'] == event)
        self.assertEqual(row['provenance'], 'PRODUCT_RUNTIME')
        self.assertEqual(row['admitted_scope'], 'UTTERANCE_ONLY_NOT_DESCRIBED_EVENT_PROOF')

    def test_chat_context_uses_actual_retrieval_path(self):
        cid, _, _ = self.agreement(text='旧的光谱数据提交约定')
        t = self.s.begin_turn(self.h, '旧的光谱数据约定是什么', 'context-test')
        packet = build_context(self.s, self.h, t['turn_id'], memory_provider=self.q)
        self.assertTrue(packet['long_term_retrieval_implemented'])
        self.assertIn(cid, [r['record_id'] for r in packet['retrieval']])
        self.assertFalse(packet['context_is_state_authority'])

    def test_model_action_claim_remains_only_an_utterance(self):
        event = self.observed('说说发邮件的话题', answer='我已经把邮件发出去了。')
        row = next(r for r in self.search('发邮件') if r['record_id'] == event)
        self.assertFalse(row['assistant_utterance_is_fact_authority'])
        self.assertEqual(row['admitted_scope'], 'UTTERANCE_ONLY_NOT_DESCRIBED_EVENT_PROOF')

    def test_corrupt_index_refused_then_explicit_derived_rebuild(self):
        event = self.observed('真实保存的光谱话题')
        self.s.db.execute('UPDATE retrieval_documents SET text_content=? WHERE event_id=?', ('伪造的已履约记忆', event))
        with self.assertRaises(StoreGuard):
            self.search('光谱')
        self.r.rebuild_index()
        self.assertEqual(self.search('光谱')[0]['content'], '真实保存的光谱话题')

    def test_simulation_not_returned_as_product_experience(self):
        fictional = self.s.open_session('OFFLINE_OPERATOR', 'A', mode='CHARACTER_SIMULATION')
        self.observed('FICTIONAL_UNIQUE_EXPERIENCE_552', fictional)
        self.assertEqual(self.search('FICTIONAL_UNIQUE_EXPERIENCE_552'), [])
        result = self.search('FICTIONAL_UNIQUE_EXPERIENCE_552', fictional)
        self.assertEqual(result[0]['provenance'], 'SIMULATION_OR_AUDIT_ONLY')

    def test_query_text_cannot_become_sql_or_entity_selector(self):
        self.observed('只属于A的隐私内容')
        self.assertEqual(self.search("' OR 1=1 --", self.b), [])

    def test_restored_retrieval_results_match(self):
        self.agreement(text='光谱的历史约定')
        before = self.search('光谱历史约定')
        backup = create_backup(self.s, self.r, OUT / (self._testMethodName + '_backup'))
        destination = OUT / (self._testMethodName + '_restored')
        restore_backup(backup['backup_root'], destination, backup['manifest_sha256'])
        restored = TranscriptStore(destination)
        try:
            runtime = RuntimeStore(restored, AdmissionController(restored))
            handle = restored.resume('OFFLINE_OPERATOR', self.h.session_id)
            self.assertEqual(RetrievalService(runtime).search(handle, '光谱历史约定'), before)
        finally:
            restored.close()

    def test_forged_handle_rejected(self):
        from dataclasses import replace
        forged = replace(self.h, entity_id=self.b.entity_id)
        with self.assertRaises(StoreGuard):
            self.search('隐私', forged)

def main():
    OUT.mkdir(parents=True, exist_ok=False)
    sources = list(CODE.glob('*.py')) + [Path(__file__), Path(__file__).with_name('test_admission_runtime_r046.py')]
    with zipfile.ZipFile(OUT / 'TESTED_SOURCE.zip', 'x', zipfile.ZIP_DEFLATED) as z:
        for p in sources:
            z.writestr(p.relative_to(ROOT).as_posix(), p.read_bytes())
    with (OUT / 'TESTS.log').open('x', encoding='utf-8') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RetrievalTests))
    report = {'at_utc': datetime.now(timezone.utc).isoformat(), 'tests': result.testsRun, 'passed': result.wasSuccessful(),
              'failures': len(result.failures), 'errors': len(result.errors), 'target_model_calls': 0,
              'origin': 'AUTHORED_OFFLINE_DATA_ACTUAL_ENTITY_FILTERED_RETRIEVAL',
              'source_snapshot_sha256': file_sha(OUT / 'TESTED_SOURCE.zip'),
              'tested_sources': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': file_sha(p)} for p in sources]}
    (OUT / 'TESTS.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': OUT.relative_to(ROOT).as_posix(), 'tests': result.testsRun, 'passed': result.wasSuccessful()}))
    raise SystemExit(0 if result.wasSuccessful() else 1)

if __name__ == '__main__':
    main()
