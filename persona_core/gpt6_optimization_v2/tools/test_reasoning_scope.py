"""Authored mechanism tests; lexical binding and conditional schema, not LLM grading."""
import copy
import json
from pathlib import Path
import sys
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'persona_core/operational_runtime_v1'),str(Path(__file__).parent)]
from claim_evidence import utterance, interpret, build_graph, prompt_projection
from reasoning_scope_fixtures import FIXTURES
from context_router import build_context
from transcript_store import TranscriptStore,create_sandbox,StoreGuard
from dialogue_admission import DialogueAdmissionController
from retrieval import RetrievalService
from runtime_store import RuntimeStore
from chat import ChatService
from provider import canonical

def unit(text, speaker='user'):
    return utterance(entity_id='author',mode='PRODUCT_RUNTIME',turn_id='t1',speaker=speaker,text=text)
def graph(text,speaker='user'):
    return build_graph(entity_id='author',mode='PRODUCT_RUNTIME',current={'turn_id':'t1','user_text':text},
                       history=[],retrieval=[])
def proposed(text,**reasoning):
    u=unit(text)
    return interpret(u,{'span':[0,len(text)],'quote':text,'reasoning':reasoning})

class ReasoningScopeTests(unittest.TestCase):
    def test_all_authored_examples_reach_typed_surface_view(self):
        for name,text,expected in FIXTURES:
            with self.subTest(name=name):
                g=graph(text); row=g['units'][0]['reasoning_scope']
                self.assertEqual(row['origin'],'USER_SUPPLIED')
                self.assertEqual(row['world_verification'],'NOT_ESTABLISHED_BY_WORDS')
                self.assertEqual(row['claim_kind'],'UNRESOLVED')
                self.assertTrue(expected <= {m['kind'] for m in row['markers']})
                for mark in row['markers']:
                    start,end=mark['span'];self.assertEqual(text[start:end],mark['quote'])
                self.assertEqual(row['relations'],[])
                self.assertEqual(row['candidate_set_completeness'],'UNRESOLVED')
                self.assertFalse(g['projection_grants_authority'])

    def test_supplied_premise_and_reported_observation_are_different_readings(self):
        for kind in ('SUPPLIED_PREMISE','REPORTED_OBSERVATION','INFERRED_CONSEQUENCE','UNRESOLVED_POSSIBILITY'):
            x=proposed('标尺已经校准。',claim_kind=kind)
            self.assertEqual(x['reasoning']['claim_kind'],kind)
            self.assertFalse(x['admission_eligible'])
            self.assertEqual(x['world_event_status'],'UNRESOLVED')
            self.assertFalse(x['reasoning']['semantic_entailment_verified'])

    def test_conditional_consequence_keeps_both_unverified_premises(self):
        x=proposed('两次投影的长度可以比较。',claim_kind='INFERRED_CONSEQUENCE',
            premises=['标尺已经校准','镜头位置固定'],inference_strength='CONDITIONAL_ON_PREMISES')
        self.assertEqual(x['reasoning']['premises'],['标尺已经校准','镜头位置固定'])
        self.assertFalse(x['reasoning']['premises_verified'])
        self.assertEqual(x['authority'],'NONE_INTERPRETATION_ONLY')

    def test_conditional_without_premises_rejected(self):
        with self.assertRaises(ValueError):
            proposed('可以比较。',inference_strength='CONDITIONAL_ON_PREMISES')

    def test_eliminations_do_not_make_an_exhaustive_set(self):
        x=proposed('已知潮湿和虫害都不是原因。',candidate_set={'members':['潮湿','虫害','照明'],'completeness':'OPEN','closure_basis':[]})
        self.assertEqual(x['reasoning']['candidate_set']['completeness'],'OPEN')
        with self.assertRaises(ValueError):
            proposed('剩下白色。',candidate_set={'members':['红','蓝','白'],'completeness':'EXHAUSTIVE_WITHIN_PREMISES','closure_basis':[]})

    def test_explicit_finite_universe_can_be_represented_without_world_upgrade(self):
        x=proposed('在这个游戏内剩下白色。',premises=['规则限定三种颜色'],
             candidate_set={'members':['红','蓝','白'],'completeness':'EXHAUSTIVE_WITHIN_PREMISES','closure_basis':['规则限定三种颜色']})
        self.assertEqual(x['reasoning']['candidate_set']['completeness'],'EXHAUSTIVE_WITHIN_PREMISES')
        self.assertFalse(x['reasoning']['semantic_entailment_verified'])
        self.assertFalse(x['admission_eligible'])

    def test_five_relation_axes_remain_separate_and_have_their_own_basis(self):
        for kind in ('FIELD_COMPARISON','SAMPLING_ORDER','RECORD_ORDER','CAUSAL_ORDER','PAIRING_IDENTITY'):
            relation={'kind':kind,'left':'甲','right':'乙','relation':'UNRESOLVED','basis':['作者给出的待核实关系'],'confidence':'UNRESOLVED'}
            x=proposed('只讨论这个关系。',relations=[relation])
            self.assertEqual(x['reasoning']['relations'],[relation])
            self.assertEqual(len(x['reasoning']['relations']),1)
            self.assertFalse(x['relations_admitted'])

    def test_field_comparison_cannot_be_encoded_as_record_relation(self):
        with self.assertRaises(ValueError):
            proposed('读数甲小于乙。',relations=[{'kind':'RECORD_ORDER','left':'甲','right':'乙','relation':'LESS_THAN','basis':['原文'],'confidence':'EXPLICIT_REPORT'}])

    def test_relation_without_evidence_basis_rejected(self):
        with self.assertRaises(ValueError):
            proposed('甲先记录。',relations=[{'kind':'RECORD_ORDER','left':'甲','right':'乙','relation':'BEFORE','basis':[],'confidence':'EXPLICIT_REPORT'}])

    def test_negated_or_quoted_cue_is_never_a_premise_fact(self):
        for text in ('不要假设展柜已密封。','“假设展柜已密封”是未经批准的提案。'):
            row=graph(text)['units'][0]['reasoning_scope']
            self.assertEqual(row['claim_kind'],'UNRESOLVED')
            self.assertEqual(row['marker_semantics'],'LEXICAL_OCCURRENCE_ONLY_READ_ENCLOSING_TEXT')
            self.assertEqual(row['relations'],[])

    def test_quoted_pronoun_has_a_local_unresolved_perspective(self):
        text='他说“你已经处理好了”。'
        row=graph(text)['units'][0]['reasoning_scope'];q=row['quotes'][0]
        self.assertEqual(text[slice(*q['span'])],'你已经处理好了')
        self.assertEqual(q['speaker'],'UNRESOLVED');self.assertEqual(q['addressee'],'UNRESOLVED')
        self.assertTrue(q['closed'])

    def test_nested_quotes_and_unclosed_quote_keep_scope(self):
        for text in ('阿宁说：“贝拉写道‘你已经处理好了’。”','他说“你已经处理好了'):
            row=graph(text)['units'][0]['reasoning_scope']
            for q in row['quotes']:
                self.assertEqual(q['addressee'],'UNRESOLVED')
            self.assertTrue(row['quotes'])
        self.assertFalse(row['quotes'][0]['closed'])

    def test_explicit_addressee_is_only_a_proposed_reading(self):
        text='阿宁对贝拉说：“你已经处理好了。”';u=unit(text)
        x=interpret(u,{'span':[0,len(text)],'quote':text,'quoted_speech':'QUOTED',
              'reported_speaker':'阿宁','reported_addressee':'贝拉'})
        self.assertEqual(x['interpretation']['reported_addressee'],'贝拉')
        self.assertFalse(x['admission_eligible'])

    def test_authority_and_unbounded_reasoning_fields_are_rejected(self):
        for data in ({'claim_kind':'HOST_VERIFIED_EVENT'},{'premises_verified':True},
                     {'premises':['x']*33},{'inference_strength':'PROVEN_WORLD_FACT'},
                     {'candidate_set':{'members':['x'],'completeness':'EXHAUSTIVE','closure_basis':['x']}},
                     {'relations':[{}]},{'premises':[True]}):
            with self.subTest(data=data), self.assertRaises(ValueError): proposed('原话。',**data)

    def test_candidate_mutation_does_not_change_source_or_prior_candidate(self):
        text='可能只是通风不足。';u=unit(text)
        candidate={'span':[0,len(text)],'quote':text,'reasoning':{'premises':['风扇未开']}}
        before=copy.deepcopy(candidate);x=interpret(u,candidate)
        self.assertEqual(before,candidate)
        candidate['reasoning']['premises'].append('另一个猜想')
        self.assertEqual(x['reasoning']['premises'],['风扇未开'])
        self.assertEqual(x['enclosing_evidence']['raw_text'],text)

    def test_prompt_contains_independent_invariants_even_without_cues(self):
        p=prompt_projection(graph('晚上好。'))
        rules=p['reasoning_invariants']
        self.assertFalse(rules['premise_acceptance_verifies_world'])
        self.assertFalse(rules['elimination_establishes_exhaustiveness'])
        self.assertEqual(set(rules['independent_relations']),{'FIELD_COMPARISON','SAMPLING_ORDER','RECORD_ORDER','CAUSAL_ORDER','PAIRING_IDENTITY'})
        self.assertEqual(rules['cross_relation_inference'],'REQUIRES_EXPLICIT_BRIDGE_PREMISES')

    def test_compact_groups_recover_every_location_speaker_and_authority(self):
        g=build_graph(entity_id='author',mode='PRODUCT_RUNTIME',current={'turn_id':'new','user_text':'接着讨论。'},
            history=[{'turn_id':'old','status':'DISPLAYED','user_text':'假设标尺校准。','assistant_text':'可能仍需核对。'}],retrieval=[])
        p=prompt_projection(g);by={u['proposition_id']:u for u in g['units']}
        restored=[]
        for speaker,authority,rows in p['evidence']:
            for pid,location,*facets in rows:
                self.assertEqual((speaker,authority),(by[pid]['speaker'],by[pid]['authority']))
                restored.append({'proposition_id':pid,'path':location})
        self.assertCountEqual(restored,g['locations'])

    def test_dense_surface_metadata_is_bounded_without_claiming_exhaustive_coverage(self):
        text=('如果条件成立，那么再看“另一个假设”。'*100)
        g=graph(text);s=g['units'][0]['reasoning_scope']
        self.assertLessEqual(len(s['markers']),24);self.assertLessEqual(len(s['quotes']),24)
        self.assertEqual(s['surface_coverage'],'BOUNDED')
        self.assertEqual(g['units'][0]['raw_text'],text)
        self.assertEqual(prompt_projection(g)['reasoning_scopes'][0][1]['surface_coverage'],'BOUNDED_NOT_EXHAUSTIVE')

    def test_ascii_escaped_quotes_and_contractions_do_not_bind_pronouns(self):
        text='She said "don\'t assume \\"you\\" is the reader".'
        s=graph(text)['units'][0]['reasoning_scope']
        self.assertEqual(len(s['quotes']),1)
        self.assertTrue(s['quotes'][0]['closed'])
        self.assertEqual(s['quotes'][0]['addressee'],'UNRESOLVED')

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.path=ROOT/'persona_core/operational_build_v1/evidence/G6_V2_reasoning_scope_tests'/uuid.uuid4().hex
        self.store=TranscriptStore(create_sandbox(self.path));self.addCleanup(self.store.close)
        self.h=self.store.open_session('AUTHOR_ONLY','SCOPE')
        self.admission=DialogueAdmissionController(self.store)
        self.runtime=RuntimeStore(self.store,self.admission);self.memory=RetrievalService(self.runtime)
    def observe(self,text,reply='已收到这段文字。'):
        t=self.store.begin_turn(self.h,text,uuid.uuid4().hex)
        self.store.capture_reply(self.h,t['turn_id'],reply,uuid.uuid4().hex,origin='AUTHORED_TEST_STUB')
        self.store.mark_displayed(self.h,t['turn_id']);self.admission.observe_turn(self.h,t['turn_id'])
        return t
    def test_history_retrieval_current_all_project_same_bound_surface(self):
        original=self.observe('展柜：如果密封完好，那么湿度可能稳定。')
        for i in range(11): self.observe('讨论绘画编号'+str(i))
        current=self.store.begin_turn(self.h,'回顾展柜密封条件。',uuid.uuid4().hex)
        before=list(self.store.db.iterdump())
        c=build_context(self.store,self.h,current['turn_id'],memory_provider=self.memory)
        self.assertEqual(before,list(self.store.db.iterdump()))
        u=next(u for u in c['claim_evidence_graph']['units'] if u['raw_text']==original['user_text'])
        self.assertTrue(u['reasoning_scope']['markers'])
        self.assertTrue(any(x[0]==u['proposition_id'] for x in c['prompt_claim_evidence_projection']['reasoning_scopes']))
        self.assertIn('reasoning_invariants',''.join(x['content'] for x in c['messages']))
        self.assertEqual(c['messages'][-1]['content'],'回顾展柜密封条件。')
        self.assertFalse(c['context_is_state_authority'])
    def test_reasoning_descriptor_does_not_authorize_runtime_fact(self):
        t=self.observe('假设装订已经完成。')
        descriptor=proposed(t['user_text'],claim_kind='REPORTED_OBSERVATION')
        cid=self.admission.propose(self.h,'COMMITMENT_FULFILLED',{'reading':descriptor},key='invalid-authority',source_turn_ids=[t['turn_id']])
        d=self.admission.decide(self.h,cid,evidence=descriptor)
        self.assertEqual(d.verdict,'REJECT')
        with self.assertRaises(StoreGuard):self.runtime.commit(self.h,d)
        self.assertEqual(self.runtime.snapshot(self.h)['relationship']['verified_completions'],0)
    def test_actual_chat_transport_receives_scope_and_source_unchanged(self):
        from provider import ENDPOINT,RATES
        scope={'batch_id':'scope-pipeline','principal_id':'AUTHOR_ONLY','purpose':'Authored offline scope transport',
               'endpoint':ENDPOINT,'automatic_paid_retries':0,'pricing_verified_date':'2026-09-07',
               'pricing_sources':['OFFLINE_FIXTURE'],'max_input_bytes':24576,'max_output_tokens':600,
               'input_overhead_reserve_tokens':4096,'total_guard_cny':1.0,
               'slots':[{'id':'s1','model':'deepseek-v4-flash','entity_label':'SCOPE','user_text':None}]}
        scope['reserved_upper_micro_cny']=(24576+4096)*RATES['deepseek-v4-flash'][0]+600*RATES['deepseek-v4-flash'][1]
        chat=ChatService(self.store,self.h,scope,memory_provider=self.memory,admission_controller=self.admission)
        seen=[]
        def transport(payload,credential):
            data=json.loads(payload);seen.append(data)
            return 200,canonical({'model':data['model'],'choices':[{'message':{'content':'这是一条作者编写的测试回包。'},'finish_reason':'stop'}],
                                  'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}})
        slot=scope['slots'][0]
        text=slot['user_text'] or '假设展柜密封完好，那么再讨论湿度。'
        result=chat.send_text(text,'scope-send',slot_id=slot['id'],transport=transport,credential_reader=lambda:'OFFLINE-STUB',display=lambda _:None)
        self.assertEqual(result['status'],'DISPLAYED')
        self.assertEqual(seen[0]['messages'][-1]['content'],text)
        self.assertIn('reasoning_invariants',''.join(m['content'] for m in seen[0]['messages']))
        self.assertEqual(len(seen),1)

if __name__=='__main__': unittest.main(verbosity=2)
