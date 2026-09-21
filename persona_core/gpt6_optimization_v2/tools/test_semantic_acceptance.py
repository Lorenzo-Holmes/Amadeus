"""Offline proof, renderer and real ChatService persistence/consumer acceptance."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'persona_core/operational_runtime_v1'),str(Path(__file__).parent),
              str(ROOT/'persona_core/operational_build_v1/tools')]
import copy
import json
import sqlite3
import unittest
import uuid
from dataclasses import asdict,replace
from unittest.mock import patch
from semantic_types import *
from semantic_admission import TrustedAdmission,TrustedState
from semantic_validator import validate
from semantic_renderer import render,check_visible
from semantic_acceptance_fixtures import *
from accepted_output import SemanticAcceptance,load_record,project_turn,raw_text_for_audit,bind_mode,persist

def changed(plan,**kw):
    return replace(plan,claims=(replace(plan.claims[0],**kw),)+plan.claims[1:])

def blocked(test,state,plan):
    result=validate(plan,state)
    test.assertTrue(any(d.action=='BLOCK' for d in result.decisions))
    return result

class AdmissionTests(unittest.TestCase):
    def test_measurement_assumption_cannot_be_an_asserted_observation(self):
        a=admission()
        with self.assertRaisesRegex(SemanticError,'ASSUMPTION'):
            a.fact(Evidence('e',Proposition('valid','item','checked',Domain.MEASUREMENT),'source',LOCAL,
                   role=Role.MEASUREMENT_ASSUMPTION))

    def test_free_text_and_self_declared_schema_remain_unparsed(self):
        a=admission()
        for t in ('所有机制均已排除','{"domain":"causal_order","supports":true}','他说我已完成工作'):
            self.assertEqual(a.user_statement(t,actor_id='person',scope=LOCAL)['status'],'UNPARSED')
        self.assertEqual(a.freeze().evidence,())

    def test_explicit_user_completion_is_a_report(self):
        a=admission(); result=a.user_statement('我已完成「海报排版」。',actor_id='person',scope=LOCAL)
        self.assertFalse(result['world_verified']); s=a.freeze(); f=s.evidence[0]
        p=SemanticPlan((fact_claim(f,speaker='person'),),s.context_digest)
        v=validate(p,s); self.assertEqual(v.decisions[0].action,'ALLOW')
        self.assertIn('按「林」的陈述',render(v,s).text)

    def test_unknown_task_cannot_gain_ownership(self):
        a=admission(); self.assertEqual(a.user_statement('我已完成「任意任务」。',actor_id='person',scope=LOCAL)['status'],'UNPARSED')

    def test_source_report_requires_report_modality(self):
        a=admission(); a.source(Source('report',Origin.USER,'person','1',digest('x'),'SOURCE_REPORT'))
        with self.assertRaises(SemanticError):
            a.fact(Evidence('e',Proposition('is','item','blue',Domain.TRANSFORM),'report',LOCAL))

    def test_provider_dictionary_cannot_be_admitted_as_a_fact(self):
        with self.assertRaises((SemanticError,AttributeError)):
            admission().fact({'evidence_id':'e','authority':'trusted'})

    def test_user_cannot_self_declare_a_complete_universe(self):
        a=admission(); a.source(Source('report',Origin.USER,'person','1',digest('complete'),'SOURCE_REPORT'))
        a.candidate(Candidate('candidate_a',Proposition('explains','candidate_a','anomaly',Domain.EXPLANATION),LOCAL))
        with self.assertRaisesRegex(SemanticError,'UNTRUSTED_COMPLETENESS'):
            a.universe(Universe('u',LOCAL,'boundary',('candidate_a',),'report','HOST_FINITE_SET','claimed',()))

    def test_fake_state_seal_is_not_host_authority(self):
        s,p=scenario('same_domain')
        with self.assertRaises(SemanticError): validate(p,replace(s,_seal=object()))

class ClaimCertificateTests(unittest.TestCase):
    def test_limitation_is_a_scoped_failure_to_establish_not_negation(self):
        s,p=scenario('observed_order'); target=replace(p.claims[0].proposition,relation_domain=Domain.TIMESTAMP)
        claim=replace(p.claims[0],claim_type='LIMITATION',proposition=target,source_refs=tuple(x.source_id for x in s.sources))
        v=validate(replace(p,claims=(claim,)),s); self.assertEqual(v.decisions[0].action,'ALLOW')
        self.assertIn('仅凭当前信息',render(v,s).text)

    def test_limitation_cannot_hide_an_existing_proof(self):
        s,p=scenario('direct'); c=replace(p.claims[0],claim_type='LIMITATION',source_refs=tuple(x.source_id for x in s.sources))
        blocked(self,s,replace(p,claims=(c,)))

    def test_certificate_binds_context_sources_and_rule(self):
        s,p=scenario('same_domain'); d=validate(p,s).decisions[0]
        self.assertEqual(d.action,'ALLOW'); self.assertEqual(d.certificate.context_digest,s.context_digest)
        self.assertEqual(set(d.certificate.source_refs),{'source','rule_source'})

    def test_same_domain_does_not_entail_unrelated_predicate(self):
        s,p=scenario('direct'); blocked(self,s,changed(p,proposition=replace(p.claims[0].proposition,object='round')))

    def test_source_existence_is_required(self):
        s,p=scenario('direct'); blocked(self,s,changed(p,source_refs=('invented',)))

    def test_source_cannot_be_omitted(self):
        s,p=scenario('same_domain'); blocked(self,s,changed(p,source_refs=('source',)))

    def test_unresolved_dependencies_cannot_be_invented(self):
        s,p=scenario('direct'); blocked(self,s,changed(p,unresolved_dependencies=('condition',)))

    def test_conflicting_atom_cannot_be_hidden_from_support(self):
        s,p=scenario('conflict'); blocked(self,s,p)

    def test_prior_context_certificate_cannot_be_replayed(self):
        s,p=scenario('direct'); other,_=scenario('direct',('session','entity','new_turn','new input'))
        with self.assertRaisesRegex(SemanticError,'STALE'): validate(p,other)

    def test_scope_widening_is_blocked(self):
        s,p=scenario('direct'); blocked(self,s,changed(p,scope=GLOBAL))

class ClosureCertificateTests(unittest.TestCase):
    def test_open_strength_plan_cannot_render_closed_text(self):
        s,p=scenario('finite'); c=replace(p.claims[-1],strength=Strength())
        blocked(self,s,replace(p,claims=p.claims[:-1]+(c,)))

    def test_finite_survivor_requires_all_members(self):
        s,p=scenario('finite'); v=validate(p,s); c=v.decisions[-1].closure
        self.assertEqual(c.remaining_members,('candidate_b',)); self.assertEqual(c.unresolved_remainder,())
        self.assertEqual(v.decisions[-1].action,'ALLOW')

    def test_empty_remaining_allows_exhaustion(self):
        s,p=scenario('exhaustive'); v=validate(p,s)
        self.assertEqual(v.decisions[-1].closure.proof_status,'EXPLICITLY_EXHAUSTED')
        self.assertIn('全部候选都已排除',render(v,s).text)

    def test_remaining_member_cannot_be_declared_exhausted(self):
        s,p=scenario('finite'); last=replace(p.claims[-1],strength=Strength(Epistemic.SUPPORTED,Disposition.UNASSESSED,Coverage.EXHAUSTIVE))
        blocked(self,s,replace(p,claims=p.claims[:-1]+(last,)))

    def test_hidden_unassessed_member_is_blocked(self):
        s,p=scenario('finite'); blocked(self,s,replace(p,claims=p.claims[:-1]+(replace(p.claims[-1],member_claims=('c0',)),)))

    def test_duplicate_candidate_proof_cannot_replace_missing_member(self):
        s,p=scenario('finite'); duplicate=replace(p.claims[0],claim_id='duplicate')
        last=replace(p.claims[-1],member_claims=('c0','duplicate'))
        blocked(self,s,replace(p,claims=(p.claims[0],duplicate,last)))

    def test_closure_cycle_or_forward_reference_is_blocked(self):
        s,p=scenario('finite'); blocked(self,s,replace(p,claims=(p.claims[-1],)+p.claims[:-1]))

for name in ('partial','open','unknown_remainder','local_global'):
    def closure_case(self,name=name):
        s,p=scenario(name); v=blocked(self,s,p)
        self.assertNotIn('完整候选范围内',render(v,s).text)
    setattr(ClosureCertificateTests,'test_'+name,closure_case)

class RelationDomainTests(unittest.TestCase):
    def test_row_order_never_becomes_timestamp_value(self):
        s,p=scenario('row_order'); blocked(self,s,p)

    def test_measurement_precondition_is_not_exclusion(self):
        s,p=scenario('measurement'); blocked(self,s,p)

    def test_relation_domains_are_distinct_nominal_types(self):
        self.assertEqual(len(Domain),11)
        s,p=scenario('observed_order')
        for domain in Domain:
            if domain!=Domain.RECORD:
                with self.subTest(domain=domain): blocked(self,s,changed(p,proposition=replace(p.claims[0].proposition,relation_domain=domain)))

    def test_role_cannot_be_forged_into_an_exclusion_root(self):
        a=admission()
        with self.assertRaises(SemanticError):
            a.fact(Evidence('e',Proposition('excluded','candidate_a','anomaly',Domain.EXPLANATION),'source',LOCAL,
                 Strength(Epistemic.SUPPORTED,Disposition.EXCLUDED),role=Role.MEASUREMENT_ASSUMPTION))

class BridgeValidationTests(unittest.TestCase):
    def test_exclusion_certificate_binds_different_evidence_domain_and_bridge(self):
        s,p=scenario('bridge_exclusion'); c=validate(p,s).decisions[0].certificate
        self.assertEqual(c.candidate_domain,Domain.EXPLANATION.value)
        self.assertEqual(c.evidence_domains,(Domain.TRANSFORM.value,)); self.assertEqual(c.bridge_refs,('exclude',))

    def test_exclusion_loses_authority_without_its_bridge(self):
        s,p=scenario('bridge_exclusion'); blocked(self,s,changed(p,bridge_refs=()))

    def test_directed_bridge_allows_exact_registered_conclusion(self):
        s,p=scenario('bridge'); d=validate(p,s).decisions[0]
        self.assertEqual(d.action,'ALLOW'); self.assertEqual(d.certificate.bridge_refs,('implication',))

    def test_missing_bridge_reference_blocks(self):
        s,p=scenario('bridge'); blocked(self,s,changed(p,bridge_refs=()))

    def test_fake_bridge_label_blocks(self):
        s,p=scenario('no_bridge'); blocked(self,s,changed(p,rule_ref='fake',bridge_refs=('fake',)))

    def test_bridge_cannot_reverse_direction(self):
        s,p=scenario('bridge'); blocked(self,s,changed(p,proposition=s.evidence[0].proposition))

    def test_bridge_argument_substitution_blocks(self):
        s,p=scenario('bridge'); blocked(self,s,changed(p,proposition=replace(p.claims[0].proposition,subject='other')))

class ClaimStrengthTests(unittest.TestCase):
    def test_possible_cannot_become_certain(self):
        s,p=scenario('possible'); v=validate(changed(p,strength=Strength(Epistemic.CERTAIN)),s)
        self.assertEqual(v.decisions[0].action,'DOWNGRADE'); self.assertIn('待验证的可能',render(v,s).text)

    def test_supported_cannot_become_excluded(self):
        s,p=scenario('direct'); blocked(self,s,changed(p,strength=Strength(Epistemic.SUPPORTED,Disposition.EXCLUDED)))

    def test_excluded_cannot_become_exhaustive_without_universe(self):
        s,p=scenario('exhaustive'); first=replace(p.claims[0],strength=Strength(Epistemic.SUPPORTED,Disposition.EXCLUDED,Coverage.EXHAUSTIVE))
        blocked(self,s,replace(p,claims=(first,)))

    def test_axes_do_not_compensate_for_each_other(self):
        self.assertFalse(Strength(Epistemic.CERTAIN).permits(Strength(Epistemic.POSSIBLE,Disposition.EXCLUDED)))
        self.assertFalse(Strength(Epistemic.POSSIBLE,Disposition.EXCLUDED).permits(Strength(Epistemic.SUPPORTED)))

    def test_conditional_is_qualified_without_deleting_antecedent(self):
        s,p=scenario('conditional'); v=validate(changed(p,modality=Modality.ASSERTED,unresolved_dependencies=()),s)
        self.assertEqual(v.decisions[0].action,'QUALIFY'); self.assertIn('如果「密封圈完好」',render(v,s).text)

class ResponsibilityTests(unittest.TestCase):
    def test_inferred_and_unknown_attribution_never_promote(self):
        for attr,force in (('INFERRED',Epistemic.POSSIBLE),('UNKNOWN',Epistemic.UNKNOWN)):
            a=admission(); f=Evidence('e',Proposition('assigned','person','task',Domain.RESPONSIBILITY),
                  'source',LOCAL,Strength(force),Modality.HYPOTHETICAL,attribution=attr)
            a.fact(f); s=a.freeze(); p=SemanticPlan((fact_claim(f),),s.context_digest)
            self.assertEqual(validate(p,s).decisions[0].action,'ALLOW')
            blocked(self,s,changed(p,attribution='EXPLICITLY_ASSIGNED',temporal_state=TemporalState.ASSIGNED))

    def test_adjacent_task_ownership_is_blocked(self):
        s,p=scenario('assignment'); blocked(self,s,changed(p,proposition=replace(p.claims[0].proposition,object='adjacent')))

    def test_planned_never_becomes_completed(self):
        s,p=scenario('planned'); blocked(self,s,changed(p,proposition=replace(p.claims[0].proposition,predicate='completed'),
                    temporal_state=TemporalState.COMPLETED,attribution='EXPLICITLY_COMPLETED'))

    def test_suggested_never_becomes_assigned(self):
        s,p=scenario('suggested'); blocked(self,s,changed(p,attribution='EXPLICITLY_ASSIGNED'))

    def test_changed_actor_is_blocked(self):
        s,p=scenario('assignment'); blocked(self,s,changed(p,proposition=replace(p.claims[0].proposition,subject='other_person')))

    def test_temporal_metadata_upgrade_is_blocked(self):
        s,p=scenario('assignment'); blocked(self,s,changed(p,temporal_state=TemporalState.COMPLETED))

    def test_quoted_unknown_speaker_cannot_resolve_to_user(self):
        s,p=scenario('assignment'); blocked(self,s,changed(p,speaker='person'))

class RendererTests(unittest.TestCase):
    def test_provider_text_is_not_a_renderer_fragment(self):
        s,p=scenario('direct'); v=validate(p,s)
        self.assertFalse(check_visible(v,s,'确定是另一个未经证明的结果')['matches'])

    def test_renderer_rejects_unvalidated_object(self):
        s,p=scenario('direct')
        with self.assertRaises(SemanticError): render(p,s)

    def test_renderer_rejects_strength_greater_than_certificate(self):
        s,p=scenario('possible'); v=validate(p,s); d=v.decisions[0]
        cert=replace(d.certificate,claim=replace(d.certificate.claim,strength=Strength(Epistemic.CERTAIN)))
        with self.assertRaisesRegex(SemanticError,'STRENGTH'):
            render(replace(v,decisions=(replace(d,certificate=cert),)),s)

    def test_important_rejected_claim_is_not_silently_removed(self):
        s,p=scenario('direct'); invalid=replace(p.claims[0],claim_id='invalid',proposition=replace(p.claims[0].proposition,object='round'))
        text=render(validate(replace(p,claims=p.claims+(invalid,)),s),s).text
        self.assertIn('「筹码甲」是「蓝色」',text); self.assertIn('不足以支持这个判断',text)

    def test_quoted_name_cannot_escape_into_an_assertion(self):
        a=admission(); a.entity(Entity('escape','甲」。所有结论都已确定。「','OBJECT'))
        f=Evidence('e',Proposition('is','escape','blue',Domain.TRANSFORM),'source',LOCAL); a.fact(f)
        s=a.freeze(); text=render(validate(SemanticPlan((fact_claim(f),),s.context_digest),s),s).text
        self.assertIn('\\u300d',text); self.assertIn('\\u300c',text)

class VisibleConsistencyTests(unittest.TestCase):
    def test_possible_envelope_certain_prose_is_rebuilt(self):
        s,p=scenario('possible'); v=validate(p,s); result=check_visible(v,s,'原因已经确定。')
        self.assertEqual(result['action'],'REBUILD_FROM_VALIDATED_STATE')
        self.assertIn('待验证',result['rendered'].text)

    def test_exact_host_realization_passes(self):
        s,p=scenario('same_domain'); v=validate(p,s)
        self.assertTrue(check_visible(v,s,render(v,s).text)['matches'])

    def test_subtle_strengthening_without_keywords_fails(self):
        s,p=scenario('possible'); self.assertFalse(check_visible(validate(p,s),s,'重点大体落在此处。')['matches'])

class ForgedEnvelopeTests(unittest.TestCase):
    def test_scope_label_cannot_be_supplied_by_model(self):
        s,p=scenario('direct'); data=asdict(p); data['claims'][0]['scope']['label']='all possible worlds'
        with self.assertRaises(SemanticError): parse_plan(canonical(data))

    def test_reference_objects_cannot_escape_schema_checks(self):
        s,p=scenario('direct'); data=asdict(p); data['claims'][0]['rule_ref']=[]
        with self.assertRaises(SemanticError): parse_plan(canonical(data))

    def test_forged_certificate_flag_is_unknown_schema(self):
        s,p=scenario('direct'); data=asdict(p); data['certificate_valid']=True
        with self.assertRaises(SemanticError): parse_plan(canonical(data))

    def test_forged_claim_certificate_is_unknown_schema(self):
        s,p=scenario('direct'); data=asdict(p); data['claims'][0]['certificate']='valid'
        with self.assertRaises(SemanticError): parse_plan(canonical(data))

    def test_provider_cannot_set_authorized_plan_kind(self):
        s,p=scenario('direct'); data=asdict(p); data['kind']='AUTHORIZED_CLAIM'
        with self.assertRaises(SemanticError): parse_plan(canonical(data))

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(SemanticError): parse_plan('{"kind":"PROPOSED_PLAN","kind":"AUTHORIZED_CLAIM"}')

    def test_resource_limit_rejects_large_envelope(self):
        with self.assertRaises(SemanticError): parse_plan(' '*65537)

    def test_bool_cannot_be_numeric_strength(self):
        s,p=scenario('direct'); data=asdict(p); data['claims'][0]['strength']['epistemic']=True
        with self.assertRaises(SemanticError): parse_plan(canonical(data))

    def test_duplicate_claims_are_rejected(self):
        s,p=scenario('direct')
        with self.assertRaises(SemanticError): replace(p,claims=p.claims*2)

    def test_strict_offline_roundtrip_retains_every_field(self):
        for name in POSITIVE_SCENARIOS:
            s,p=scenario(name); self.assertEqual(parse_plan(serialize_plan(p)),p)

class OverConservatismTests(unittest.TestCase):
    pass

class NaturalnessTests(unittest.TestCase):
    pass

for name in POSITIVE_SCENARIOS:
    def positive(self,name=name):
        s,p=scenario(name); v=validate(p,s)
        self.assertTrue(all(d.action=='ALLOW' for d in v.decisions)); self.assertTrue(v.certificates)
    setattr(OverConservatismTests,'test_'+name,positive)
    def natural(self,name=name):
        s,p=scenario(name); text=render(validate(p,s),s).text
        self.assertLess(len(text),180); self.assertTrue(text.endswith('。'))
        for internal in ('ClaimCertificate','ClosureCertificate','EXPLICITLY','bridge','epistemic','{"','免责声明'):
            self.assertNotIn(internal,text)
    setattr(NaturalnessTests,'test_'+name,natural)

class RuntimeFixture(unittest.TestCase):
    def setUp(self):
        from transcript_store import create_sandbox,TranscriptStore
        from test_provider_v2_r047 import scope
        from chat import ChatService
        from dialogue_admission import DialogueAdmissionController
        from runtime_store import RuntimeStore
        from retrieval import RetrievalService
        self.root=create_sandbox(ROOT/'persona_core/operational_build_v1/evidence/typed_acceptance_tests'/uuid.uuid4().hex)
        self.store=TranscriptStore(self.root); self.handle=self.store.open_session('TEST_OPERATOR','A')
        self.scope=scope(); self.scope.update(principal_id='TEST_OPERATOR',max_output_tokens=600)
        self.scope['slots']=[{'id':'s'+str(i),'case_id':'case','model':'deepseek-v4-flash','entity_label':'A',
                            'user_text':'请按给定条件判断。'} for i in range(1,4)]
        import provider
        self.scope['reserved_upper_micro_cny']=sum((self.scope['max_input_bytes']+4096)*provider.RATES[s['model']][0]
                       +600*provider.RATES[s['model']][1] for s in self.scope['slots'])
        self.calls=0; self.visible=[]; self.case='same_domain'; self.raw=None
        self.admission=DialogueAdmissionController(self.store); self.runtime=RuntimeStore(self.store,self.admission)
        self.retrieval=RetrievalService(self.runtime)
        def admit(handle,turn,context):
            return scenario(self.case,(handle.session_id,handle.entity_id,turn['turn_id'],turn['user_text']))[0]
        self.acceptance=SemanticAcceptance(admit)
        self.chat=ChatService(self.store,self.handle,self.scope,memory_provider=self.retrieval,
            admission_controller=self.admission,semantic_acceptance_mode='TRUSTED',semantic_acceptance=self.acceptance)

    def tearDown(self):
        self.store.close()

    def transport(self,payload,key):
        from test_chat_r045 import body
        self.calls+=1; turn=self.store.recent(self.handle,1)[0]
        state,plan=scenario(self.case,(self.handle.session_id,self.handle.entity_id,turn['turn_id'],turn['user_text']))
        self.raw=serialize_plan(plan)
        return 200,body(self.raw)

    def send(self,slot='s1',display=True):
        return self.chat.send_text('请按给定条件判断。',slot,slot_id=slot,
            transport=self.transport,credential_reader=lambda:'OFFLINE_FIXTURE_NOT_A_REAL_KEY',
            display=self.visible.append if display else None)

class PersistenceTests(RuntimeFixture):
    def test_off_policy_keeps_old_database_schema(self):
        from transcript_store import create_sandbox,TranscriptStore
        root=create_sandbox(ROOT/'persona_core/operational_build_v1/evidence/typed_acceptance_tests'/uuid.uuid4().hex)
        store=TranscriptStore(root)
        try:
            h=store.open_session('legacy','A'); bind_mode(store,h,'OFF')
            names={r[0] for r in store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn('accepted_outputs',names); self.assertNotIn('semantic_session_policy',names)
        finally: store.close()

    def test_raw_and_accepted_are_independently_persisted(self):
        out=self.send(); record=load_record(self.store.db,out['turn_id'])
        self.assertEqual(out['status'],'DISPLAYED'); self.assertEqual(self.store.get_turn(self.handle,out['turn_id'])['assistant_text'],self.raw)
        self.assertNotEqual(self.raw,out['text']); self.assertEqual(record['accepted_assistant_text'],out['text'])
        self.assertTrue(record['certificates']); self.assertTrue(record['accepted_semantic_plan'])

    def test_raw_and_accepted_records_are_append_only(self):
        self.send()
        for table in ('semantic_raw_outputs','accepted_outputs'):
            with self.assertRaises(sqlite3.IntegrityError): self.store.db.execute('DELETE FROM '+table)

    def test_resume_reuses_accepted_output_without_generation(self):
        first=self.send(display=False); old=load_record(self.store.db,first['turn_id'])
        from transcript_store import TranscriptStore
        from chat import ChatService
        sid=self.handle.session_id; self.store.close(); self.store=TranscriptStore(self.root)
        self.handle=self.store.resume('TEST_OPERATOR',sid); self.chat=ChatService(self.store,self.handle,self.scope)
        second=self.send(); self.assertEqual(self.calls,1); self.assertEqual(second['text'],first['text'])
        self.assertEqual(load_record(self.store.db,second['turn_id']),old)

    def test_policy_cannot_be_disabled_after_binding(self):
        with self.assertRaisesRegex(SemanticError,'IMMUTABLE'): bind_mode(self.store,self.handle,'OFF')

    def test_raw_mutation_is_detected_on_consumer_read(self):
        out=self.send(); self.store.db.execute('UPDATE turns SET assistant_text=? WHERE turn_id=?',('tamper',out['turn_id']))
        with self.assertRaisesRegex(SemanticError,'CORRUPT'): load_record(self.store.db,out['turn_id'])

    def test_unaccepted_capture_cannot_bypass_lower_display_api(self):
        turn=self.store.begin_turn(self.handle,'user','direct')
        self.store.capture_reply(self.handle,turn['turn_id'],'unsupported','request')
        with self.assertRaisesRegex(SemanticError,'REQUIRED'): self.store.mark_displayed(self.handle,turn['turn_id'])

    def test_display_crash_retains_accepted_record_without_redisplay(self):
        with self.assertRaises(OSError):
            self.chat.send_text('请按给定条件判断。','s1',slot_id='s1',transport=self.transport,
                credential_reader=lambda:'OFFLINE_FIXTURE_NOT_A_REAL_KEY',display=lambda _:(_ for _ in ()).throw(OSError('sink')))
        self.assertEqual(self.send()['status'],'DELIVERY_STATUS_UNKNOWN'); self.assertEqual(self.calls,1)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM accepted_outputs').fetchone()[0],1)

class HistoryConsumerTests(RuntimeFixture):
    def test_history_reads_accepted_text(self):
        out=self.send(); row=self.store.conversation_recent(self.handle,1,purpose='history')[0]
        self.assertEqual(row['assistant_text'],out['text']); self.assertEqual(row['raw_assistant_text'],self.raw)

    def test_next_turn_context_uses_accepted_text(self):
        first=self.send(); self.send('s2')
        context=json.loads(self.store.db.execute("SELECT context_json FROM provider_calls WHERE slot_id='s2'").fetchone()[0])
        self.assertEqual(context['prompt_history_projection'][0]['assistant'],first['text'])
        self.assertNotIn('PROPOSED_PLAN',canonical(context['messages']))

    def test_displayed_resume_does_not_return_raw(self):
        first=self.send(); second=self.send(); self.assertEqual(second['text'],first['text']); self.assertEqual(self.calls,1)

class MemoryConsumerTests(RuntimeFixture):
    def test_observation_and_candidate_payload_use_accepted(self):
        out=self.send()
        event=json.loads(self.store.db.execute('SELECT event_json FROM runtime_events').fetchone()[0])
        self.assertEqual(event['payload']['assistant_text'],out['text'])
        self.assertEqual(event['payload']['output_provenance'],'HOST_ACCEPTED_OUTPUT')
        payload=json.loads(self.store.db.execute('SELECT payload_json FROM event_candidates').fetchone()[0])
        self.assertEqual(payload['assistant_text'],out['text']); self.assertFalse(payload['described_events_proven'])

    def test_runtime_reopen_verifies_accepted_observation(self):
        self.send()
        from transcript_store import TranscriptStore
        from dialogue_admission import DialogueAdmissionController
        from runtime_store import RuntimeStore
        sid=self.handle.session_id; self.store.close(); self.store=TranscriptStore(self.root)
        self.handle=self.store.resume('TEST_OPERATOR',sid)
        runtime=RuntimeStore(self.store,DialogueAdmissionController(self.store))
        self.assertIsInstance(runtime.snapshot(self.handle),dict)

class EvaluationConsumerTests(RuntimeFixture):
    def test_native_evaluation_checks_raw_and_display_separately(self):
        out=self.send(); import evaluation_runner as runner
        folder=self.root/'native_evaluation'; (folder/'displays').mkdir(parents=True)
        (folder/'displays/s1.txt').write_bytes((out['text']+'\n').encode())
        prep={'sessions':{'case':{'session_id':self.handle.session_id,'entity_id':self.handle.entity_id,'mode':self.handle.mode}}}
        rows,_=runner.validate_rows(self.store.db,folder,{'capture_mode':runner.OFFLINE},self.scope,prep)
        self.assertEqual(rows[0]['raw_assistant_text'],self.raw); self.assertEqual(rows[0]['assistant_text'],out['text'])

    def test_candidate_journal_reader_and_raw_audit_preserve_both(self):
        out=self.send(); import candidate_day_v2 as gate
        rows=gate._journal_rows(self.root/'runtime.sqlite3')
        gate.verify_raw(rows[0]); self.assertEqual(rows[0]['assistant_text'],out['text'])
        self.assertEqual(rows[0]['raw_assistant_text'],self.raw)

    def test_review_and_blind_package_contain_accepted_dialogue(self):
        import tempfile,zipfile
        from test_semantic_review import ReviewTests
        import semantic_review as sr
        out=self.send(); selected=project_turn(self.store.db,self.store.get_turn(self.handle,out['turn_id']),'review')
        call=self.store.db.execute('SELECT * FROM provider_calls').fetchone()
        fixture=ReviewTests(unittest.defaultTestLoader.getTestCaseNames(ReviewTests)[0])
        scratch=ROOT/'work/offline_test_temp'; scratch.mkdir(exist_ok=True)
        with patch.object(tempfile,'tempdir',str(scratch)):
            fixture.setUp()
        try:
            row=fixture.capture['turns'][0]
            row.update({k:selected[k] for k in ('turn_id','session_id','assistant_text','raw_assistant_text',
                       'accepted_assistant_text','accepted_output','output_provenance')})
            row['raw_sha256']=call['raw_sha256']
            (fixture.root/row['raw_path']).write_bytes(bytes(call['raw_response']))
            fixture.capture['turns'][1]['session_id']=self.handle.session_id
            fixture.sync_captures(); bundle=fixture.load()
            public=fixture.root/'accepted.zip'; private=fixture.root/'map.json'
            sr.build_package(bundle,public_zip=public,private_map=private)
            with zipfile.ZipFile(public) as archive:
                data=json.loads(archive.read('DIALOGUES.json'))
                self.assertEqual(data['cases'][0]['turns'][0]['assistant_text'],out['text'])
                self.assertNotIn(self.raw,json.dumps(data,ensure_ascii=False))
        finally: fixture.doCleanups()

    def test_evaluation_exposes_both_answers_and_transformation(self):
        out=self.send(); raw=self.store.get_turn(self.handle,out['turn_id'])
        raw['raw_sha256']=self.store.db.execute('SELECT raw_sha256 FROM provider_calls').fetchone()[0]
        selected=project_turn(self.store.db,raw,'evaluation')
        self.assertEqual(raw_text_for_audit(selected),self.raw); self.assertEqual(selected['assistant_text'],out['text'])
        self.assertEqual(selected['accepted_output']['transformation']['action'],'REBUILD_FROM_VALIDATED_STATE')

    def test_candidate_and_blind_projection_selects_accepted(self):
        out=self.send(); import candidate_day_v2 as gate
        raw=self.store.get_turn(self.handle,out['turn_id'])
        for purpose in ('candidate','blind','audit','review'):
            self.assertEqual(gate.accepted_projection(self.store.db,raw,purpose)['assistant_text'],out['text'])

    def test_export_keeps_raw_receipt_and_separate_accepted_record(self):
        self.send(); from capture_export import export_calls
        export=export_calls(self.store,self.root/'exports')
        names=[r['path'] for r in export['exports'][0]['files']]
        self.assertTrue(any(n.endswith('RAW_RESPONSE.json') for n in names))
        self.assertTrue(any(n.endswith('ACCEPTED_OUTPUT.json') for n in names))

    def test_exported_accepted_text_tampering_is_rejected(self):
        out=self.send(); raw=self.store.get_turn(self.handle,out['turn_id'])
        raw['raw_sha256']=self.store.db.execute('SELECT raw_sha256 FROM provider_calls').fetchone()[0]
        selected=project_turn(self.store.db,raw,'review'); selected['assistant_text']='stronger answer'
        with self.assertRaises(SemanticError): raw_text_for_audit(selected)

class VerticalSliceTests(RuntimeFixture):
    pass

for case in ('same_domain','bridge','no_bridge','finite','exhaustive','unknown_remainder','measurement',
             'assignment','completion','conditional','possible','bridge_exclusion','same_domain_exclusion'):
    def vertical(self,case=case):
        self.case=case; out=self.send(); record=load_record(self.store.db,out['turn_id'])
        self.assertEqual(out['status'],'DISPLAYED'); self.assertEqual(self.visible,[out['text']])
        self.assertTrue(record['accepted_semantic_plan']); self.assertEqual(self.calls,1)
        actions=[d['action'] for d in record['validation_result']['decisions']]
        if case in ('no_bridge','measurement','unknown_remainder'):
            self.assertIn('BLOCK',actions); self.assertIn('不足以支持',out['text'])
        else: self.assertTrue(all(a=='ALLOW' for a in actions))
        event=json.loads(self.store.db.execute('SELECT event_json FROM runtime_events').fetchone()[0])
        self.assertEqual(event['payload']['assistant_text'],out['text'])
    setattr(VerticalSliceTests,'test_'+case,vertical)

if __name__=='__main__': unittest.main(verbosity=2)
