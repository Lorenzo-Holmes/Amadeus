"""Freeze a prepared evaluation protocol before any R047 output. No API calls.

This validates protocol structure/budget only, not runtime readiness, semantics
or character quality. The generated scope is deliberately rejected by the old
R045 provider contract until a tested scope-v2 implementation exists.
"""
from __future__ import annotations
import copy
import hashlib
import json
import sqlite3
import sys
import unittest
import zipfile
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
PLAN=ROOT/'persona_core/operational_build_v1'
HOME=PLAN/'evidence/R047-01'
NAMES=['NEW_MULTITURN_CASES.json','EVALUATION_PROTOCOL.md','PRIVATE_RUBRIC.json',
       'FIXTURE_CONTRACT.json','MODEL_BUDGET_SCOPE.json','OFFICIAL_INTERFACE_OBSERVATION.md']

def load(name):return json.loads((HOME/name).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(condition,reason):
    if not condition:raise ValueError(reason)

def compile_scope(cases:dict,rubric:dict,base:dict,fixture:dict,matrix:dict) -> dict:
    main=[c for c in cases['cases'] if c['classification']=='NEW_AT_FREEZE']
    regression=[c for c in cases['cases'] if c['classification']=='EXPLICIT_REGRESSION_NOT_HELDOUT']
    require(len(main)==12 and all(len(c['user_turns'])==6 for c in main),'Exactly twelve new six-turn scenarios required')
    require(len({c['id'] for c in cases['cases']})==len(cases['cases']),'Duplicate scenario IDs')
    require(len(regression)==2 and all(len(c['user_turns'])==2 for c in regression),'Explicit regression denominator changed')
    categories={c['category'] for c in main}
    require(len(categories)==6 and all(sum(c['category']==g for c in main)==2 for g in categories),'Category coverage changed')
    targets=matrix['proposed_quality_targets_to_pin_before_r047_generation']
    for key,value in rubric['quality_targets'].items():
        require(targets[key]==value,'Quality threshold differs from the pre-observation acceptance target')
    require(rubric['static_lint_is_semantic_pass'] is False and rubric['threshold_changes_after_observation_allowed'] is False,'No automatic semantic acceptance or post-observation threshold changes')
    require(fixture['historical_fixtures_use_separate_sessions'] is True
            and fixture['main_conversation_starts_without_authored_assistant_turns'] is True,'Authored assistant history may not replace target outputs')
    require(fixture['old_agreement']['same_entity_irrelevant_records_after_agreement']>=120
            and fixture['corrected_statement']['same_entity_irrelevant_records']>=120,'Long-history test shortened')
    require(base['automatic_paid_retries']==0 and base['execute_before_r046_06_pass'] is False,'Unsafe execution/paid-retry policy')
    require(base['thinking']=={'type':'enabled'} and base['reasoning_effort']=='max','Pinned target reasoning configuration changed')
    require(base['target_calls_submitted_at_preparation']==0,'Protocol cannot be first frozen after observation')
    result=copy.deepcopy(base)
    result['schema_version']='apcore-provider-scope-2'
    result['slots']=[]
    for case in cases['cases']:
        for number,text in enumerate(case['user_turns'],1):
            require(isinstance(text,str) and text.strip() and '\n' not in text,'Each fixed ordinary CLI user turn must be one nonempty line')
            result['slots'].append({'id':case['id']+'_T'+str(number),'model':base['primary_model'],
                'entity_label':case['entity_label'],'user_text':text,'case_id':case['id'],
                'evaluation_phase':case['classification']})
        for number,text in enumerate(case.get('switch_tail',[]),1):
            result['slots'].append({'id':case['id']+'_S'+str(number),'model':base['switch_model'],
                'entity_label':case['entity_label'],'user_text':text,'case_id':case['id'],
                'evaluation_phase':'SAME_INSTANCE_MODEL_SWITCH_NOT_PAIRED_PERFORMANCE_COMPARISON'})
    require(len(result['slots'])==82,'Whole logical batch count differs from82')
    require(sum(s['model']=='deepseek-v4-pro' for s in result['slots'])==76,'Primary model count differs from76')
    require(sum(s['model']=='deepseek-v4-flash' for s in result['slots'])==6,'Switch model count differs from6')
    reserve=0
    for slot in result['slots']:
        rates=base['peak_rates_cny_per_million_tokens'][slot['model']]
        reserve+=(base['max_input_bytes']+base['input_overhead_reserve_tokens'])*rates['input_miss']+base['max_output_tokens']*rates['output']
    require(reserve==base['reserved_upper_micro_cny'],'Whole-batch reserve mismatch')
    require(reserve<=int(Decimal(str(base['total_guard_cny']))*1_000_000),'Whole logical batch exceeds guard')
    result['protocol_file_bindings']={name:sha(HOME/name) for name in NAMES}
    result['compiled_slot_count']=len(result['slots'])
    result['runtime_readiness_verified']=False
    result['compilation_is_semantic_acceptance']=False
    return result

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.c,self.r,self.b,self.f=load('NEW_MULTITURN_CASES.json'),load('PRIVATE_RUBRIC.json'),load('MODEL_BUDGET_SCOPE.json'),load('FIXTURE_CONTRACT.json')
        self.m=json.loads((PLAN/'ACCEPTANCE_MATRIX.json').read_text(encoding='utf-8'))
    def compile(self):return compile_scope(self.c,self.r,self.b,self.f,self.m)
    def test_full_structure(self):self.assertEqual(len(self.compile()['slots']),82)
    def test_missing_new_case_rejected(self):
        self.c['cases'].pop(0)
        with self.assertRaises(ValueError):self.compile()
    def test_shortened_case_rejected(self):
        self.c['cases'][0]['user_turns'].pop()
        with self.assertRaises(ValueError):self.compile()
    def test_lowered_quality_threshold_rejected(self):
        self.r['quality_targets']['category_mean_character_specificity_min']=2
        with self.assertRaises(ValueError):self.compile()
    def test_inadequate_budget_rejected(self):
        self.b['total_guard_cny']=1
        with self.assertRaises(ValueError):self.compile()
    def test_retries_rejected(self):
        self.b['automatic_paid_retries']=1
        with self.assertRaises(ValueError):self.compile()
    def test_authored_target_history_rejected(self):
        self.f['main_conversation_starts_without_authored_assistant_turns']=False
        with self.assertRaises(ValueError):self.compile()
    def test_short_history_fixture_rejected(self):
        self.f['old_agreement']['same_entity_irrelevant_records_after_agreement']=8
        with self.assertRaises(ValueError):self.compile()
    def test_private_rubric_not_compiled_to_slots(self):
        scope=self.compile()
        text=json.dumps(scope['slots'],ensure_ascii=False)
        self.assertNotIn(self.r['private_marker'],text)
        self.assertNotIn('private_expectations',text)
        self.assertNotIn('SABLE-COPPER-47',text)
    def test_deterministic_slot_compilation(self):self.assertEqual(self.compile(),self.compile())
    def test_switch_preserves_entity_label(self):
        scope=self.compile()
        for cid in ['N05','N09','N12']:
            slots=[s for s in scope['slots'] if s['case_id']==cid]
            self.assertEqual(len({s['entity_label'] for s in slots}),1)
            self.assertEqual([s['model'] for s in slots],['deepseek-v4-pro']*6+['deepseek-v4-flash']*2)
    def test_preobserved_freeze_rejected(self):
        self.b['target_calls_submitted_at_preparation']=1
        with self.assertRaises(ValueError):self.compile()

def main():
    state=json.loads((PLAN/'TASK_STATE.json').read_text(encoding='utf-8'))
    tasks={t['id']:t for t in state['tasks']}
    require(tasks['R045-04']['status']=='DONE' and tasks['R044-04']['status']=='DONE','Preparation dependencies incomplete')
    require(tasks['R047-02']['status'] in {'PENDING','READY'},'Generation already started; do not replace protocol')
    target_root=PLAN/'evidence/R047-02/evaluation_live_01'
    require(not target_root.exists(),'Target root already exists; inspect before freezing')
    for relative in ['evidence/R045-03/live_01','evidence/R045-04/repair_live_01']:
        database=PLAN/relative/'runtime.sqlite3'
        db=sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)
        try:
            require(db.execute("SELECT COUNT(*) FROM provider_calls WHERE batch_id LIKE 'APCORE-R047%'").fetchone()[0]==0,'An R047 submission already exists')
        finally:db.close()
    scope=compile_scope(load('NEW_MULTITURN_CASES.json'),load('PRIVATE_RUBRIC.json'),load('MODEL_BUDGET_SCOPE.json'),load('FIXTURE_CONTRACT.json'),
        json.loads((PLAN/'ACCEPTANCE_MATRIX.json').read_text(encoding='utf-8')))
    existing=list(HOME.glob('freeze_*/EXECUTION_SCOPE.json'))
    if existing:
        require(len(existing)==1 and json.loads(existing[0].read_text(encoding='utf-8'))==scope,'Existing protocol differs; use a named revision, not overwrite')
        print(json.dumps({'already_frozen':str(existing[0].relative_to(ROOT)),'new_target_calls':0}));return
    out=HOME/('freeze_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir(parents=True,exist_ok=False)
    with (out/'TESTS.log').open('x',encoding='utf-8') as f:
        result=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProtocolTests))
    require(result.wasSuccessful(),'Protocol mutation/calibration tests failed; not frozen')
    with zipfile.ZipFile(out/'PREOBSERVATION_PROTOCOL.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
        for name in NAMES:z.writestr(name,(HOME/name).read_bytes())
        z.writestr('freeze_protocol_r047.py',Path(__file__).read_bytes())
    (out/'EXECUTION_SCOPE.json').write_text(json.dumps(scope,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report={'at_utc':datetime.now(timezone.utc).isoformat(),'plan_id':state['plan_id'],
        'protocol_id':scope['batch_id'],'protocol_frozen_before_observation':True,'new_target_calls':0,
        'target_root_absent_verified':True,'known_live_provider_journals_have_r047_calls':False,
        'tests':result.testsRun,'passed':result.wasSuccessful(),'new_scenarios':12,'main_turns':72,
        'switch_turns':6,'explicit_regression_turns':4,'fixed_total_calls':82,
        'worst_case_reserve_cny':scope['reserved_upper_micro_cny']/1e6,'finite_guard_cny':scope['total_guard_cny'],
        'scope_sha256':sha(out/'EXECUTION_SCOPE.json'),'protocol_zip_sha256':sha(out/'PREOBSERVATION_PROTOCOL.zip'),
        'reviewer':'CURRENT_SESSION_DEVELOPER_NONBLIND','runtime_ready':False,'semantic_or_quality_pass':False,
        'files':{name:sha(HOME/name) for name in NAMES},'freeze_tool_sha256':sha(Path(__file__))}
    (out/'FREEZE_VERIFICATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':out.relative_to(ROOT).as_posix(),'tests':result.testsRun,'passed':result.wasSuccessful(),
        'fixed_calls':82,'new_target_calls':0,'reserve_cny':scope['reserved_upper_micro_cny']/1e6},ensure_ascii=True))

if __name__=='__main__':main()
