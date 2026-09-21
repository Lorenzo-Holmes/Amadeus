from __future__ import annotations
import json,shutil,unittest,zipfile
from pathlib import Path
import audit_repaired_review_return_r047 as a

OUT=a.PLAN/'evidence/R047-04/review_return_audit_tests_static'

def completed_zip(path:Path, *, one_fail=False):
    if path.exists(): path.unlink()
    with zipfile.ZipFile(a.SOURCE) as src:
        conversations={}
        for name in src.namelist():
            if name.startswith('conversations/') and name.endswith('.json'):
                doc=json.loads(src.read(name));
                for turn in doc['turns']: conversations[turn['review_turn_id']]=turn['assistant_text']
        sheet=json.loads(src.read('BLANK_SCORE_SHEET.json')); findings=json.loads(src.read('BLANK_FINDINGS.json'))
        sheet['reviewer_declaration'].update(name_or_identifier='TEST-REVIEWER',role='independent test reviewer',review_started_at_utc='2026-09-12T00:00:00+00:00',review_completed_at_utc='2026-09-12T01:00:00+00:00',participated_in_implementation_tuning_or_case_design=False,prior_exposure_to_development_outputs=False,conflicts_of_interest=False,materials_read=['all package'],independence_assessed=True)
        failed=False
        for case in sheet['cases']:
            for turn in case['turn_reviews']:
                for j in turn['judgments']:
                    verdict='FAIL' if one_fail and not failed else 'PASS'; failed=failed or verdict=='FAIL'; j['verdict']=verdict; j['quote']=conversations[turn['review_turn_id']]; j['rationale']='Independent explicit rationale for this criterion.'
                    if verdict!='PASS': j['finding_ids']=['F-TEST-1']
            if case['quality'] is not None:
                first=case['turn_reviews'][0]['review_turn_id']
                for item in case['quality'].values(): item.update(score=4,rationale='Independent quality rationale.',evidence=[{'review_turn_id':first,'quote':conversations[first]}])
        if one_fail: findings['findings']=[{'finding_id':'F-TEST-1','severity':'LOW','status':'OPEN','summary':'test finding'}]
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as out:
            for name in src.namelist():
                if name=='BLANK_SCORE_SHEET.json': out.writestr(name,json.dumps(sheet,ensure_ascii=False,indent=2))
                elif name=='BLANK_FINDINGS.json': out.writestr(name,json.dumps(findings,ensure_ascii=False,indent=2))
                else: out.writestr(name,src.read(name))

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if OUT.exists(): shutil.rmtree(OUT)
        OUT.mkdir(parents=True)
    def test_full_pass_can_pass_gate(self):
        path=OUT/'pass.zip'; completed_zip(path); r=a.audit_completed_zip(path); self.assertEqual(r['overall_conclusion'],'PASS'); self.assertEqual(r['semantic_results']['verdict_counts'],{'PASS':328})
    def test_one_fail_fails_gate(self):
        path=OUT/'fail.zip'; completed_zip(path,one_fail=True); r=a.audit_completed_zip(path); self.assertEqual(r['overall_conclusion'],'FAIL'); self.assertEqual(r['semantic_results']['verdict_counts']['FAIL'],1)
    def test_modified_conversation_rejected(self):
        path=OUT/'tampered.zip'; completed_zip(path)
        temp=OUT/'tmp.zip'
        with zipfile.ZipFile(path) as src, zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as out:
            for name in src.namelist(): out.writestr(name,b'{}' if name=='conversations/C01.json' else src.read(name))
        temp.replace(path)
        with self.assertRaises(a.ReviewGuard): a.audit_completed_zip(path)

def main():
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests)); print(json.dumps({'tests':r.testsRun,'passed':r.wasSuccessful(),'target_calls':0})); return 0 if r.wasSuccessful() else 1
if __name__=='__main__': raise SystemExit(main())
