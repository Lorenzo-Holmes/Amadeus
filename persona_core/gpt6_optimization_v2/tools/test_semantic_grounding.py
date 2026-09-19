"""General source-grounding contracts, authored data, zero remote generation."""
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'persona_core/operational_runtime_v1'),str(Path(__file__).parent)]
from semantic_grounding import (candidate_closure, responsibility_attribution, grounding_contract,
    grounding_projection, grounding_message, bind_evidence, CLOSURE_STATES, ATTRIBUTION_STATES)
from claim_evidence import build_graph, describe_grounding, utterance, interpret
from semantic_grounding_fixtures import FIXTURES, fixture, bind_fixture
from reasoning_scope import candidate_closure_view
from context_router import build_context
from transcript_store import TranscriptStore, create_sandbox, StoreGuard
from dialogue_admission import DialogueAdmissionController
from runtime_store import RuntimeStore
from retrieval import RetrievalService
from chat import ChatService
import provider
import provider_transport as pt
import test_responses_provider_integration as response_helpers


def evaluate(f):
    d,u=bind_fixture(f)
    return (candidate_closure if f['kind']=='CANDIDATE_CLOSURE' else responsibility_attribution)(d,u)


class AuthoredCases(unittest.TestCase):
    pass


def authored_test(name):
    def test(self):
        f=fixture(name); before=copy.deepcopy(f);result=evaluate(f)
        for key,value in f['expected'].items():
            self.assertEqual(result[key],value,key)
        self.assertEqual(f,before)
        self.assertEqual(result['authority'],'NONE')
        self.assertFalse(result['admission_eligible'])
        for e in result['evidence']:
            self.assertEqual(e['enclosing_text'][slice(*e['span'])],e['quote'])
            self.assertFalse(e['world_verified'])
        if f['kind']=='CANDIDATE_CLOSURE':
            self.assertFalse(result['world_exhaustiveness_established'])
        else:
            self.assertFalse(result['world_verified'])
    return test


for f in FIXTURES:
    setattr(AuthoredCases,'test_'+f['id'],authored_test(f['id']))


class AdversarialSupportTests(unittest.TestCase):
    def test_unrelated_reversed_or_unscoped_bridge_cannot_exclude(self):
        for key,value in [('from_domain','OTHER'),('to_domain','OTHER'),('scope','OTHER'),('candidate_ids',['green'])]:
            f=fixture('cross_domain_explicit_bridge');f['data']['bridges'][0][key]=value
            with self.subTest(key=key):
                r=evaluate(f);self.assertEqual(r['excluded_candidates'],[])
                self.assertEqual(r['closure_state'],'OPEN')

    def test_inferred_or_assistant_bridge_does_not_certify_exclusion(self):
        for mode in ('inferred','assistant','suggested'):
            f=fixture('cross_domain_explicit_bridge');s=f['data']['sources'][-1]
            if mode=='inferred':s['annotation']['confidence']='INFERRED'
            if mode=='assistant':s['speaker']='assistant'
            if mode=='suggested':s['annotation']['claim_type']='SUGGESTION'
            with self.subTest(mode=mode):self.assertEqual(evaluate(f)['excluded_candidates'],[])

    def test_exclusion_rule_needs_its_own_matching_source(self):
        for mode in ('domain','scope','missing','untyped'):
            f=fixture('same_domain_valid_exclusion');s=f['data']['sources'][1]
            if mode in ('domain','scope'):s['annotation'][mode]='OTHER'
            elif mode=='missing':f['data']['exclusions'][0]['rule_evidence_id']='missing'
            else:s['annotation']['claim_type']='UNKNOWN'
            with self.subTest(mode=mode):
                if mode=='missing':
                    with self.assertRaises(ValueError):evaluate(f)
                else:self.assertEqual(evaluate(f)['excluded_candidates'],[])

    def test_unhandled_member_blocks_finite_closure(self):
        f=fixture('finite_universe_complete_closure');f['data']['assessments']=[]
        r=evaluate(f);self.assertEqual(r['unhandled_candidates'],['green'])
        self.assertEqual(r['closure_state'],'PARTIALLY_CONSTRAINED')
        self.assertIsNone(r['conditional_finite_remainder'])

    def test_unknown_empty_or_incomplete_universe_cannot_close(self):
        for field,value in [('kind','UNKNOWN'),('candidate_ids',['red']),('evidence_ids',[]),('unresolved_remainder',None)]:
            f=fixture('finite_universe_complete_closure');f['data']['universe'][field]=value
            with self.subTest(field=field):self.assertIsNone(evaluate(f)['conditional_finite_remainder'])

    def test_generator_and_proof_remain_scoped_source_descriptions(self):
        for kind in ('BOUNDED_GENERATOR','COMPLETENESS_PROOF'):
            f=fixture('finite_universe_complete_closure');f['data']['universe']['kind']=kind
            with self.subTest(kind=kind):
                r=evaluate(f);self.assertEqual(r['closure_state'],'LOCALLY_CLOSED')
                self.assertFalse(r['semantic_entailment_verified'])

    def test_conflicting_retained_candidate_reopens_exclusion(self):
        f=fixture('finite_universe_complete_closure')
        f['data']['assessments'].append({'candidate_id':'red','status':'RETAINED','evidence_ids':['retain']})
        r=evaluate(f);self.assertNotIn('red',r['excluded_candidates'])
        self.assertIn('red',r['unhandled_candidates']);self.assertIsNone(r['conditional_finite_remainder'])

    def test_provenance_rejects_unknown_source_wrong_span_or_rewritten_quote(self):
        d,u=bind_fixture(fixture('explicit_assignment'))
        for key,value in [('source_id','foreign'),('span',[0,9999]),('span',[True,2]),('quote','伪造原文')]:
            bad=copy.deepcopy(d['evidence'][0]);bad[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):bind_evidence(u,bad)

    def test_provenance_rejects_source_hash_tampering_and_authority_injection(self):
        d,u=bind_fixture(fixture('explicit_assignment'));u[0]['raw_text']+='篡改'
        with self.assertRaises(ValueError):responsibility_attribution(d,u)
        d,u=bind_fixture(fixture('explicit_assignment'));d['evidence'][0]['world_verified']=True
        with self.assertRaises(ValueError):responsibility_attribution(d,u)

    def test_scope_unknown_is_not_a_matching_relation_domain(self):
        f=fixture('same_domain_valid_exclusion')
        f['data']['candidates'][0]['domain']='UNKNOWN'
        for s in f['data']['sources']:s['annotation']['domain']='UNKNOWN'
        self.assertEqual(evaluate(f)['excluded_candidates'],[])

    def test_assignment_and_plan_are_not_a_phase_ladder(self):
        f=fixture('explicit_assignment');plan=fixture('future_plan')['data']['sources'][0]
        plan['id']='different_reading';f['data']['sources'].append(plan)
        self.assertEqual(evaluate(f)['state'],'UNKNOWN')

    def test_ambiguous_quote_cannot_inherit_the_current_user_as_speaker(self):
        r=evaluate(fixture('speaker_ambiguity'))
        self.assertEqual(r['state'],'UNKNOWN')
        self.assertEqual(r['evidence'][0]['speaker'],'user')
        self.assertEqual(r['evidence'][0]['reported_speaker'],'UNKNOWN')

    def test_superseded_report_cannot_establish_current_responsibility(self):
        d,u=bind_fixture(fixture('explicit_assignment'))
        u[0]['currentness']='SUPERSEDED_REPORT_HISTORY_ONLY'
        self.assertEqual(responsibility_attribution(d,u)['state'],'UNKNOWN')

    def test_conditional_completion_stays_inferred(self):
        f=fixture('explicit_completion');f['data']['sources'][0]['annotation']['modality']='CONDITIONAL'
        self.assertEqual(evaluate(f)['state'],'INFERRED')

    def test_same_named_task_in_another_scope_is_not_owned_here(self):
        f=fixture('explicit_assignment');f['data']['scope']='DIFFERENT_GARDEN'
        self.assertEqual(evaluate(f)['state'],'UNKNOWN')

    def test_no_execution_report_does_not_cancel_explicit_ownership(self):
        f=fixture('explicit_assignment');negation=fixture('negated_completion')['data']['sources'][0]
        negation['id']='execution_denied';f['data']['sources'].append(negation)
        self.assertEqual(evaluate(f)['state'],'EXPLICITLY_ASSIGNED')

    def test_scoped_host_text_receipt_cannot_establish_external_execution(self):
        d,u=bind_fixture(fixture('explicit_completion'))
        u[0]['authority']='HOST_VERIFIED_EVENT'
        u[0]['authority_scope']='TEXT_SUBMISSION_ONLY_NOT_EXTERNAL_WORK'
        self.assertEqual(responsibility_attribution(d,u)['state'],'UNKNOWN')

    def test_nested_results_do_not_mutate_source_or_descriptions(self):
        f=fixture('finite_universe_complete_closure');d,u=bind_fixture(f);before=copy.deepcopy((d,u))
        r=candidate_closure(d,u);r['evidence'][0]['span'][0]=99;r['closure_basis']['evidence_ids'].append('foreign')
        self.assertEqual((d,u),before)

    def test_legacy_arithmetic_is_not_new_grounded_closure(self):
        r=candidate_closure_view({'members':['one','two'],'completeness':'EXHAUSTIVE_WITHIN_PREMISES',
            'closure_basis':['限定两项']},['限定两项'])
        self.assertEqual(r['conditional_finite_remainder'],['one','two'])
        self.assertFalse(r['grounded_closure_eligible']);self.assertEqual(r['closure_state'],'OPEN')


class ProjectionTests(unittest.TestCase):
    def test_sparse_full_keep_all_candidate_and_attribution_fields(self):
        for name in ('cross_domain_explicit_bridge','explicit_assignment','speaker_ambiguity'):
            f=fixture(name);d,u=bind_fixture(f);g=describe_grounding({'units':u},[{'kind':f['kind'],'description':d}])
            with self.subTest(name=name):
                a=grounding_projection(g,sparse=True);b=grounding_projection(g,sparse=False)
                self.assertEqual(a,b)
                self.assertEqual(a['closure'],list(CLOSURE_STATES))
                self.assertEqual(a['attribution_states'],list(ATTRIBUTION_STATES))
                actual=json.loads(grounding_message(g)['content'].split('\n',1)[1])
                self.assertEqual(actual,a)
                self.assertEqual(actual['descriptions'][0]['description']['evidence'][0]['quote'],d['evidence'][0]['quote'])

    def test_no_cue_input_still_has_both_unparsed_obligations(self):
        g=build_graph(entity_id='a',mode='PRODUCT_RUNTIME',current={'turn_id':'t','user_text':'你好'},history=[],retrieval=[])
        self.assertFalse(g['semantic_parser_applied'])
        p=grounding_projection(g)
        self.assertEqual(p,grounding_contract())
        self.assertIsNone(p['unparsed']['attributions']);self.assertIsNone(p['unparsed']['unresolved_remainder'])

    def test_same_contract_for_every_authored_domain_and_no_global_mutation(self):
        baseline=grounding_contract()
        for f in FIXTURES:
            p=grounding_projection({'units':bind_fixture(f)[1]})
            self.assertEqual(p,baseline)
            p['exclusion'].append('mutated')
        self.assertEqual(grounding_contract(),baseline)

    def test_shared_provenance_schema_retains_all_attribution_axes(self):
        p=grounding_contract()
        self.assertTrue({'source_id','source_span','speaker','modality','temporal_state','claim_type','scope','quotation','reported_speaker'} <= set(p['source']))
        self.assertTrue({'actor','task','scope','state','source'} <= set(p['attribution']))

    def test_unknown_companion_contract_is_rejected(self):
        from expression_prompt import build_system
        with self.assertRaisesRegex(ValueError,'companion grounding'):
            build_system('PRODUCT_RUNTIME',[],{}, {},grounding_contract='unsupported')

    def test_claim_interpretation_uses_same_support_validator(self):
        f=fixture('explicit_assignment');d,u=bind_fixture(f)
        unit=utterance(entity_id='AUTHOR_ONLY',mode='PRODUCT_RUNTIME',turn_id=f['id']+'/task_source',speaker='user',text=u[0]['raw_text'])
        result=interpret(unit,{'span':[0,len(unit.raw_text)],'quote':unit.raw_text,
            'grounding':[{'kind':'RESPONSIBILITY','description':d}]})
        self.assertEqual(result['grounded_descriptions'][0]['description']['state'],'EXPLICITLY_ASSIGNED')
        self.assertFalse(result['admission_eligible'])


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.root=ROOT/'persona_core/operational_build_v1/evidence/G6_SEMANTIC_GROUNDING_AUTHORED'/uuid.uuid4().hex
        self.store=TranscriptStore(create_sandbox(self.root));self.addCleanup(self.store.close)
        self.h=self.store.open_session('AUTHOR_ONLY','SCOPE')
        self.admission=DialogueAdmissionController(self.store)
        self.runtime=RuntimeStore(self.store,self.admission);self.memory=RetrievalService(self.runtime)

    def context(self, text='你好'):
        t=self.store.begin_turn(self.h,text,uuid.uuid4().hex)
        return t,build_context(self.store,self.h,t['turn_id'],memory_provider=self.memory)

    def test_actual_context_counts_contract_bytes_and_refuses_before_submission(self):
        t,c=self.context();before=list(self.store.db.iterdump())
        self.assertEqual(c['prompt_bytes'],len(json.dumps(c['messages'],ensure_ascii=False,separators=(',',':')).encode()))
        with self.assertRaises(StoreGuard):build_context(self.store,self.h,t['turn_id'],memory_provider=self.memory,max_prompt_bytes=c['prompt_bytes']-1)
        self.assertEqual(list(self.store.db.iterdump()),before)
        self.assertEqual(c['prompt_semantic_grounding_projection'],grounding_contract())

    def test_compact_base_preserves_frozen_suffix_and_has_exactly_one_companion(self):
        from expression_prompt import build_system, _BASE, _GROUNDED_BASE
        from context_router import _load_frozen
        _,frozen=_load_frozen(self.store)
        c=frozen['PERSONA_CONSTITUTION_FROZEN_R034.json'];s=frozen['SELF_MODEL_FROZEN_R034.json']
        standalone=build_system('PRODUCT_RUNTIME',[],c,s)
        compact=build_system('PRODUCT_RUNTIME',[],c,s,grounding_contract='SEMANTIC_GROUNDING_1')
        self.assertEqual(standalone[len(_BASE):],compact[len(_GROUNDED_BASE):])
        _,packet=self.context()
        self.assertTrue(packet['messages'][0]['content'].startswith(_GROUNDED_BASE))
        self.assertEqual(sum('"version":"SEMANTIC_GROUNDING_1"' in m['content'] for m in packet['messages']),1)

    def test_assistant_template_stays_assistant_evidence_in_actual_context(self):
        t=self.store.begin_turn(self.h,'目录编制计划由林承担。',uuid.uuid4().hex)
        self.store.capture_reply(self.h,t['turn_id'],'林还完成了展牌制作。',uuid.uuid4().hex,origin='AUTHORED_TEST_STUB')
        self.store.mark_displayed(self.h,t['turn_id'])
        _,c=self.context('把这段说明整理成一句话。')
        u=next(u for u in c['claim_evidence_graph']['units'] if u['raw_text']=='林还完成了展牌制作。')
        self.assertEqual(u['speaker'],'assistant');self.assertEqual(u['authority'],'ASSISTANT_PRIOR_STATEMENT')
        self.assertIsNone(c['prompt_semantic_grounding_projection']['unparsed']['attributions'])

    def test_grounded_assignment_does_not_admit_completion(self):
        t,_=self.context();r=evaluate(fixture('explicit_assignment'))
        cid=self.admission.propose(self.h,'COMMITMENT_FULFILLED',{'grounding':r},key='forged',source_turn_ids=[t['turn_id']])
        d=self.admission.decide(self.h,cid,evidence=r)
        self.assertEqual(d.verdict,'REJECT')
        with self.assertRaises(StoreGuard):self.runtime.commit(self.h,d)

    def test_actual_responses_payload_and_journal_keep_mandatory_contract(self):
        scope=response_helpers.old.scope()
        scope.update(batch_id='AUTHORED_GROUNDING',principal_id='AUTHOR_ONLY',schema_version='apcore-provider-scope-5',
            endpoint=provider.RESPONSES_ENDPOINT,api_protocol='responses',stream=True,request_timeout_seconds=5,
            transport_policy=response_helpers.POLICY,capacity_policy_id='EXTENDED_MAX_REASONING_20260911',
            output_budget_includes_reasoning=True,automatic_capacity_escalation=False,
            network_route_policy={'version':'apcore-network-route-1','host':'api.deepseek.com','mode':'DIRECT_NO_PROXY'})
        for slot in scope['slots']:slot.update(entity_label='SCOPE',user_text=None)
        chat=ChatService(self.store,self.h,scope,memory_provider=self.memory,admission_controller=self.admission)
        seen=[]
        def worker(payload,credential,*args,**kwargs):
            seen.append(json.loads(payload))
            return pt.TransportResult(200,response_helpers.normalized(),response_helpers.responses_wire())
        with patch.object(provider.lifecycle_transport,'worker_exchange',worker):
            result=chat.send_text('稍后我计划编制目录。','authored-grounding',slot_id='one',
                credential_reader=lambda:'OFFLINE-STUB',display=lambda _:None)
        self.assertEqual(result['status'],'DISPLAYED');self.assertEqual(len(seen),1)
        row=self.store.db.execute('select request_json,context_json from provider_calls').fetchone()
        req=json.loads(row['request_json']);ctx=json.loads(row['context_json'])
        self.assertEqual(req,seen[0]);self.assertEqual(req['input'],ctx['messages'])
        contract=next(m for m in req['input'] if m['role']=='system' and '"version":"SEMANTIC_GROUNDING_1"' in m['content'])
        self.assertEqual(json.loads(contract['content'].split('\n',1)[1]),ctx['prompt_semantic_grounding_projection'])
        self.assertEqual(req['reasoning'],{'effort':'max'})
        self.assertTrue(req['stream'])


if __name__=='__main__':unittest.main(verbosity=2)
