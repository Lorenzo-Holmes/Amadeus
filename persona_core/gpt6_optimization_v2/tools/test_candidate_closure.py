"""Candidate closure and real context contracts, with authored offline inputs."""
import copy
import json
from pathlib import Path
import sys
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'persona_core/operational_runtime_v1'),str(Path(__file__).parent)]
from reasoning_scope import candidate_closure_view, validate_reasoning, unparsed_candidate_closure
from claim_evidence import utterance, interpret, build_graph, prompt_projection, evidence_message
from candidate_closure_fixtures import FIXTURES
import test_reasoning_scope as scope_helpers
from context_router import build_context
from transcript_store import StoreGuard
from chat import ChatService
from provider import canonical,ENDPOINT,RATES

def fixture(name): return copy.deepcopy(next(x for x in FIXTURES if x['id']==name))
def view(f): return candidate_closure_view(f['candidate_set'],f['premises'])
def graph(text):
    return build_graph(entity_id='author',mode='PRODUCT_RUNTIME',current={'turn_id':'t','user_text':text},history=[],retrieval=[])

class ClosureTests(unittest.TestCase):
    def test_all_ten_authored_cases_are_structurally_bound_not_world_facts(self):
        self.assertEqual(len(FIXTURES),10)
        for f in FIXTURES:
            with self.subTest(f=f['id']):
                u=utterance(entity_id='author',mode='PRODUCT_RUNTIME',turn_id=f['id'],speaker='user',text=f['text'])
                r=interpret(u,{'span':[0,len(f['text'])],'quote':f['text'],
                    'reasoning':{'premises':f['premises'],'candidate_set':f['candidate_set']}})
                self.assertFalse(r['admission_eligible'])
                self.assertEqual(r['enclosing_evidence']['raw_text'],f['text'])
                c=r['reasoning']['candidate_closure']
                for k in ('premises_verified','exclusions_verified','semantic_entailment_verified','world_exhaustiveness_established','admission_eligible'):
                    self.assertIs(c[k],False)

    def test_two_exclusions_leave_one_listed_member_but_no_unique_world_cause(self):
        c=view(fixture('two_removed_unknown_universe'))
        self.assertEqual(c['unresolved_candidates'],['缺肥'])
        self.assertIsNone(c['conditional_finite_remainder'])
        self.assertEqual(c['unknown_remainder'],'UNRESOLVED')

    def test_supplied_condition_remains_unverified(self):
        c=view(fixture('user_condition_unverified'))
        self.assertEqual(c['proposed_exclusions'][0]['basis'],['滤片干净'])
        self.assertFalse(c['premises_verified']);self.assertFalse(c['exclusions_verified'])

    def test_explicit_finite_rule_permits_scoped_conditional_remainder(self):
        c=view(fixture('finite_rule'))
        self.assertEqual(c['conditional_finite_remainder'],['三角'])
        self.assertEqual(c['scope'],'本桌游的有效棋子形状')
        self.assertFalse(c['world_exhaustiveness_established'])

    def test_excluding_all_listed_members_leaves_unknown_space(self):
        c=view(fixture('unlisted_space'))
        self.assertEqual(c['unresolved_candidates'],[])
        self.assertEqual(c['unknown_remainder'],'UNRESOLVED')
        self.assertIsNone(c['conditional_finite_remainder'])

    def test_user_discussion_restriction_does_not_expand_to_world(self):
        c=view(fixture('discussion_only'))
        self.assertEqual(c['conditional_finite_remainder'],['审批'])
        self.assertIn('演练',c['scope']);self.assertFalse(c['world_exhaustiveness_established'])

    def test_two_domain_bases_cannot_close_a_third(self):
        f=fixture('third_domain_unresolved');self.assertEqual(view(f)['unresolved_domains'],['测量链'])
        f['candidate_set'].update(completeness='EXHAUSTIVE_WITHIN_PREMISES',scope='假定完整的装置模型',closure_basis=['完整模型限定这些候选'])
        f['premises'].append('完整模型限定这些候选')
        with self.assertRaisesRegex(ValueError,'required domain'):view(f)

    def test_all_explicit_domain_bases_enable_only_conditional_closure(self):
        f=fixture('third_domain_unresolved')
        f['premises']+=['测量链已纳入','模型全集限定三项']
        f['candidate_set'].update(completeness='EXHAUSTIVE_WITHIN_PREMISES',scope='给定的三域模型',closure_basis=['模型全集限定三项'])
        f['candidate_set']['domain_basis']['测量链']=['测量链已纳入']
        self.assertEqual(view(f)['unresolved_domains'],[])
        self.assertEqual(len(view(f)['conditional_finite_remainder']),3)

    def test_reopened_description_does_not_apply_old_exclusions_or_erase_history(self):
        old=fixture('discussion_only');before=copy.deepcopy(old);previous=view(old)
        reopened=view(fixture('reopened'))
        self.assertEqual(old,before);self.assertEqual(previous['conditional_finite_remainder'],['审批'])
        self.assertEqual(reopened['unresolved_candidates'],['审批','沟通'])
        self.assertIsNone(reopened['conditional_finite_remainder'])

    def test_pause_keeps_unknown_without_automatic_narrowing(self):
        c=view(fixture('paused'))
        self.assertEqual(c['unresolved_candidates'],c['known_candidates'])
        self.assertIsNone(c['conditional_finite_remainder']);self.assertEqual(c['unknown_remainder'],'UNRESOLVED')

    def test_science_case_does_not_lose_unlisted_causes(self):
        c=view(fixture('ordinary_science'))
        self.assertEqual(c['unresolved_candidates'],['材料吸收','散射'])
        self.assertIsNone(c['conditional_finite_remainder'])

    def test_software_case_does_not_equate_remaining_member_with_unique_cause(self):
        c=view(fixture('software_failure'))
        self.assertEqual(c['unresolved_candidates'],['版本兼容'])
        self.assertIsNone(c['conditional_finite_remainder'])

    def test_missing_closure_basis_is_rejected(self):
        f=fixture('finite_rule');f['candidate_set']['closure_basis']=[]
        with self.assertRaises(ValueError):view(f)

    def test_foreign_closure_or_exclusion_basis_is_rejected(self):
        for field in ('closure','exclusion'):
            f=fixture('finite_rule')
            if field=='closure':f['candidate_set']['closure_basis']=['未列的依据']
            else:f['candidate_set']['exclusions'][0]['basis']=['未列的依据']
            with self.subTest(field=field),self.assertRaises(ValueError):view(f)

    def test_unknown_duplicate_members_and_duplicate_exclusions_are_rejected(self):
        for mode in ('unknown','duplicate_member','duplicate_exclusion'):
            f=fixture('finite_rule');c=f['candidate_set']
            if mode=='unknown':c['exclusions'][0]['member']='未列候选'
            elif mode=='duplicate_member':c['members'].append(c['members'][0])
            else:c['exclusions'].append(copy.deepcopy(c['exclusions'][0]))
            with self.subTest(mode=mode),self.assertRaises(ValueError):view(f)

    def test_forged_authority_fields_cannot_be_supplied(self):
        for field in ('world_exhaustiveness_established','admission_eligible','premises_verified'):
            f=fixture('finite_rule');f['candidate_set'][field]=True
            with self.subTest(field=field),self.assertRaises(ValueError):view(f)

    def test_paused_or_reopened_scope_cannot_stay_exhaustive(self):
        for state in ('PAUSED','REOPENED'):
            f=fixture('finite_rule');f['candidate_set']['inquiry_status']=state
            with self.subTest(state=state),self.assertRaises(ValueError):view(f)

    def test_foreign_or_empty_domain_basis_rejected(self):
        for domain,basis in [('外来域',['材料一致']),('材料',[])]:
            f=fixture('third_domain_unresolved');f['candidate_set']['domain_basis'][domain]=basis
            with self.subTest(domain=domain),self.assertRaises(ValueError):view(f)

    def test_descriptions_and_sources_are_not_mutated(self):
        f=fixture('finite_rule');before=copy.deepcopy(f);c=view(f)
        c['proposed_exclusions'][0]['basis'].append('外部修改');c['known_candidates'].append('修改')
        self.assertEqual(f,before)

    def test_legacy_three_field_candidate_api_remains_conditional(self):
        x=validate_reasoning({'premises':['规则只允许甲乙'], 'candidate_set':{
            'members':['甲','乙'],'completeness':'EXHAUSTIVE_WITHIN_PREMISES','closure_basis':['规则只允许甲乙']}})
        self.assertEqual(x['candidate_closure']['scope'],'WITHIN_STATED_PREMISES_ONLY')
        self.assertFalse(x['premises_verified'])

    def test_unparsed_is_not_an_empty_universe(self):
        c=unparsed_candidate_closure()
        for key in ('known','excluded','unresolved','basis'):self.assertIsNone(c[key])
        self.assertEqual(c['authority'],'NONE')

    def test_actual_projection_has_closure_state_even_without_lexical_cues(self):
        g=graph('你好。');p=prompt_projection(g)
        self.assertEqual(p['reasoning_scopes'],[])
        self.assertEqual(p['candidate_closure'],unparsed_candidate_closure())
        self.assertEqual(json.loads(evidence_message(g)['content'].split('\n',1)[1]),p)

    def test_quoted_exhaustiveness_does_not_change_projected_unknown(self):
        p=prompt_projection(graph('她写下“候选全集仅有甲乙”，随后划掉这句话。'))
        self.assertIsNone(p['candidate_closure']['exhaustive'])
        self.assertIsNone(p['candidate_closure']['remainder'])
        self.assertEqual(p['candidate_closure']['authority'],'NONE')

    def test_neutral_inputs_share_the_same_closure_contract(self):
        views=[prompt_projection(graph(f['text']))['candidate_closure'] for f in FIXTURES]
        self.assertTrue(all(v==views[0] for v in views))

class ClosurePipelineTests(unittest.TestCase):
    setUp=scope_helpers.PipelineTests.setUp
    observe=scope_helpers.PipelineTests.observe

    def test_current_history_and_retrieval_share_index_and_do_not_write_state(self):
        self.observe('花园里可能还有未知的环境因素。')
        t=self.store.begin_turn(self.h,'继续讨论花园。',uuid.uuid4().hex)
        before=list(self.store.db.iterdump());c=build_context(self.store,self.h,t['turn_id'],memory_provider=self.memory)
        self.assertEqual(before,list(self.store.db.iterdump()))
        projection=c['prompt_claim_evidence_projection'];self.assertIn('candidate_closure',projection)
        self.assertTrue(any(x['path'].startswith('history/') for x in c['claim_evidence_graph']['locations']))
        actual=next(m for m in c['messages'] if m['content'].startswith('只读陈述索引：'))
        self.assertEqual(json.loads(actual['content'].split('\n',1)[1]),projection)

    def test_budget_counts_closure_and_refuses_before_transport(self):
        t=self.store.begin_turn(self.h,'你好。',uuid.uuid4().hex)
        c=build_context(self.store,self.h,t['turn_id'],memory_provider=self.memory)
        size=len(json.dumps(c['messages'],ensure_ascii=False,separators=(',',':')).encode())
        self.assertEqual(size,c['prompt_bytes'])
        with self.assertRaises(StoreGuard):build_context(self.store,self.h,t['turn_id'],memory_provider=self.memory,max_prompt_bytes=size-1)
        tables={x[0] for x in self.store.db.execute("select name from sqlite_master where type='table'")}
        self.assertNotIn('provider_calls',tables)

    def test_closure_descriptor_does_not_admit_completion(self):
        f=fixture('finite_rule');t=self.observe(f['text']);c=view(f)
        cid=self.admission.propose(self.h,'COMMITMENT_FULFILLED',{'closure':c},key='closure-test',source_turn_ids=[t['turn_id']])
        decision=self.admission.decide(self.h,cid,evidence=c)
        self.assertEqual(decision.verdict,'REJECT')
        with self.assertRaises(StoreGuard):self.runtime.commit(self.h,decision)

    def test_actual_transport_receives_same_closure_state_as_journal_context(self):
        scope={'batch_id':'authored-closure','principal_id':'AUTHOR_ONLY','purpose':'Authored offline closure payload',
            'endpoint':ENDPOINT,'automatic_paid_retries':0,'pricing_verified_date':'2026-09-07',
            'pricing_sources':['OFFLINE_FIXTURE'],'max_input_bytes':24576,'max_output_tokens':600,
            'input_overhead_reserve_tokens':4096,'total_guard_cny':1.0,
            'slots':[{'id':'s1','model':'deepseek-v4-flash','entity_label':'SCOPE','user_text':None}]}
        scope['reserved_upper_micro_cny']=(24576+4096)*RATES['deepseek-v4-flash'][0]+600*RATES['deepseek-v4-flash'][1]
        chat=ChatService(self.store,self.h,scope,memory_provider=self.memory,admission_controller=self.admission)
        seen=[]
        def transport(payload,credential):
            data=json.loads(payload);seen.append(data)
            return 200,canonical({'model':data['model'],'choices':[{'message':{'content':'这是离线作者回包。'},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}})
        result=chat.send_text('你好。','closure-send',slot_id='s1',transport=transport,credential_reader=lambda:'OFFLINE-STUB',display=lambda _:None)
        self.assertEqual(result['status'],'DISPLAYED');self.assertEqual(len(seen),1)
        bound=self.store.db.execute('select context_json from provider_calls').fetchone()[0]
        ctx=json.loads(bound);self.assertEqual(seen[0]['messages'],ctx['messages'])
        actual=next(m for m in seen[0]['messages'] if m['content'].startswith('只读陈述索引：'))
        self.assertEqual(json.loads(actual['content'].split('\n',1)[1])['candidate_closure'],ctx['prompt_claim_evidence_projection']['candidate_closure'])

if __name__=='__main__':unittest.main(verbosity=2)
