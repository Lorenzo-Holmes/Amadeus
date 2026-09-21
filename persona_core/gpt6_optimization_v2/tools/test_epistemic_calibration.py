"""Independent synthetic request-path contracts; authored replies are not model evidence."""
from pathlib import Path
import copy,json,sys,unittest,uuid
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'persona_core/operational_runtime_v1'),str(Path(__file__).parent)]
import expression_prompt as expression
import calibration_synthetic_cases as corpus
import provider_deepseek_formal as ds
import provider_contract as pc
import test_deepseek_successor_binding as fixture
import evaluation_runner as runner
from transcript_store import TranscriptStore,create_sandbox
from operations import open_chat

class CalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=ROOT/'work/deepseek_successor/calibration_tests'/uuid.uuid4().hex
        cls.scope,cls.cfg,cls.transport,cls.route,cls.auth,cls.price=fixture.offline_config(cls.root)
        cls.constitution=runner.read(ROOT/'persona_core/runtime/genesis/frozen/PERSONA_CONSTITUTION_FROZEN_R034.json')
        cls.self_model=runner.read(ROOT/'persona_core/runtime/genesis/frozen/SELF_MODEL_FROZEN_R034.json')

    def test_domain_kind_coverage_and_no_case_collisions(self):
        rows=corpus.cases()
        self.assertEqual(len(rows),50)
        self.assertEqual(len({c['id'] for c in rows}),50)
        self.assertEqual(len({c['input'] for c in rows}),50)
        for prompts in corpus.CASES.values(): self.assertEqual(len(prompts),5)

    def test_both_compositions_keep_source_persona_and_mode(self):
        for mode in ('PRODUCT_RUNTIME','CHARACTER_SIMULATION','SOURCE_AUDIT'):
            for grounded in (None,'SEMANTIC_GROUNDING_1'):
                system=expression.build_system(mode,[],self.constitution,self.self_model,grounding_contract=grounded)
                self.assertEqual(system.count(expression.CALIBRATION_POLICY),1)
                self.assertIn(self.self_model['ontology_boundary'],system)
                for cid in expression._FALLBACK_IDS:
                    source=next(c for c in self.constitution['behavior_clauses'] if c['id']==cid)
                    self.assertIn(source['behavioral_tendency'],system)
                    for limit in source['counterexamples_and_limits']: self.assertIn(limit,system)

    def test_new_configuration_is_real_product_change_and_old_registration_retained(self):
        old=ds.configuration();new=ds.configuration(ds.CALIBRATED_CANDIDATE)
        self.assertNotEqual(old['candidate_id'],new['candidate_id'])
        for k in ('models','requested_payload_template','dataset_identity','rubric_identity','criterion_routing_identity','schedule_identity','host_policies'):
            self.assertEqual(old[k],new[k])
        self.assertEqual(new['generation_calibration']['version'],expression.CALIBRATION_POLICY_VERSION)

    def test_new_candidate_uses_same_closed_formal_binding(self):
        auth=ROOT/ds.CALIBRATED_DIRECTORY/'EXECUTION_AUTHORIZATION.json'
        suite=runner.load_suite('external44',ds.MODEL,ds.MODEL,allow_single_model=True)
        scope=ds.build_scope('calibrated_offline',suite,runner.read(self.price),runner.read(self.transport),runner.read(self.route),
            authorization_file=auth,pricing_file=self.price,acceptance_config_file=self.cfg)
        scope['semantic_acceptance_binding']=runner.build_acceptance_binding(scope,suite,self.cfg,
            rubric_path=runner.GOAL/'external_failure_v1/PRIVATE_RUBRIC.json',offline=True)
        fixture.p.scope_check(scope)
        self.assertEqual(scope['candidate_id'],ds.CALIBRATED_CANDIDATE)
        for mutate in ('candidate_id','configuration','authorization'):
            bad=copy.deepcopy(scope)
            if mutate=='candidate_id': bad['candidate_id']=ds.CANDIDATE
            elif mutate=='configuration': bad['identity_references']['configuration']['sha256']='0'*64
            else: bad['spend_policy']['authorization_identity']=ds.reference(self.auth)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError): fixture.p.scope_check(bad)

def request_case(case):
    def test(self):
        base=self.root/case['id'];create_sandbox(base)
        store=TranscriptStore(base)
        try:
            fixture.p.ProviderJournal(store)
            # Open runtime session is isolated from every acceptance case. The
            # formal serializer is exercised without submitting an evaluation slot.
            h=store.open_session('INDEPENDENT_CALIBRATION',case['domain'],'PRODUCT_RUNTIME')
            from context_router import build_context
            turn=store.begin_turn(h,case['input'],case['id'])
            context=build_context(store,h,turn['turn_id'],max_prompt_bytes=24576)
            self.assertEqual(context['messages'][-1],{'role':'user','content':case['input']})
            system='\n'.join(m['content'] for m in context['messages'] if m['role']=='system')
            self.assertEqual(system.count(expression.CALIBRATION_POLICY),1)
            self.assertNotIn(case['expectation'],system)
            payload=ds.DeepSeekFormalAdapter().serialize(self.scope,ds.MODEL,context['messages'])
            receipt=ds.input_guard_receipt(self.scope,pc.canonical(payload),self.scope['slots'][0]['id'])
            self.assertLessEqual(receipt['canonical_message_bytes'],24576)
            self.assertEqual(payload['input'],context['messages'])
            self.assertEqual(store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0],0)
        finally:store.close()
    return test
for case in corpus.cases(): setattr(CalibrationTests,'test_request_'+case['id'],request_case(case))

class CalibratedFormalPathTests(fixture.DeepSeekSuccessorTests):
    """Run real journal/display/evaluator/review contracts under the new identity."""
    @classmethod
    def setUpClass(cls):
        cls.base=ROOT/'work/deepseek_successor/calibration_formal_tests'/uuid.uuid4().hex
        _,cls.cfg,cls.transport,cls.route,_,cls.price=fixture.offline_config(cls.base)
        cls.auth=ROOT/ds.CALIBRATED_DIRECTORY/'EXECUTION_AUTHORIZATION.json'
        suite=runner.load_suite('external44',ds.MODEL,ds.MODEL,allow_single_model=True)
        cls.scope=ds.build_scope(cls.base.name,suite,runner.read(cls.price),runner.read(cls.transport),runner.read(cls.route),
            authorization_file=cls.auth,pricing_file=cls.price,acceptance_config_file=cls.cfg)
        cls.scope['semantic_acceptance_binding']=runner.build_acceptance_binding(cls.scope,suite,cls.cfg,
            rubric_path=runner.GOAL/'external_failure_v1/PRIVATE_RUBRIC.json',offline=True)

    def test_synthetic_fact_hypothesis_and_condition_are_not_state_authority(self):
        replies=[
            '按给定规则，17减2等于15。',
            '这个高值可以有几种解释：真实变化、接触问题或偏置；单次读数还不能选定原因。',
            '按你给的恒定偏置假设，减2可以消除这项误差。',
            '样本中90次偏高，所以这份样本里偏高很常见；其他环境还没测。',
            '读数偏高通常都是校准造成的。',
        ]
        for reply in replies:
            with self.subTest(reply=reply):
                store,h,chat,slot,result,shown,_=self.send(fixture.response(text=reply))
                self.assertEqual(shown,[reply])
                from accepted_output import CONSUMERS,project_turn
                row=dict(store.db.execute('SELECT * FROM turns WHERE turn_id=?',(result['turn_id'],)).fetchone())
                for purpose in CONSUMERS:
                    projected=project_turn(store.db,row,purpose)
                    self.assertEqual(projected['assistant_text'],reply)
                    self.assertFalse(projected['content_is_event_proof'])
                # Even a confident authored overclaim stays visible for quality
                # review: display eligibility is never a truth certificate.
                candidate=store.db.execute('SELECT requested_effects_json FROM event_candidates ORDER BY created_at_utc DESC LIMIT 1').fetchone()
                self.assertEqual(json.loads(candidate[0]),[])

    def test_allocation_uses_new_identity_once_and_preserves_old_allocation(self):
        from formal_binding_preflight import deepseek_successor_preflight
        from unittest.mock import patch
        evidence=self.base/'allocation_evidence';evidence.mkdir()
        old=evidence/('SUCCESSOR_ALLOCATION_'+ds.CANDIDATE+'.json')
        runner.write_new(old,{'revision':'immutable-prior-failed-candidate'})
        before=old.read_bytes()
        # A sealed authored marker may contain a reused PID. Only a live paid
        # driver blocks allocation; the same preflight classifier governs both.
        marker=evidence/'G6_V2_authored';marker.mkdir()
        runner.write_new(marker/'ACTIVE_RUN.json',{'pid':12345})
        runner.write_new(marker/'MANIFEST.json',{'capture_mode':runner.OFFLINE})
        runner.write_new(marker/'MANIFEST_SEAL.json',{'sha256':runner.sha(marker/'MANIFEST.json')})
        frozen=runner.read(self.base/'SOURCE.json');frozen['status']='FROZEN_FOR_FRESH_VALIDATION'
        # Exclusively authored fixture: rebind its new manifest explicitly.
        source=self.base/'ALLOCATION_SOURCE.json';runner.write_new(source,frozen)
        config=runner.read(self.cfg);config['acceptance_source_manifest']=ds.reference(source)
        cfg=self.base/'allocation_acceptance.json';runner.write_new(cfg,config)
        with patch.object(runner,'EVIDENCE',evidence),patch.object(runner,'process_alive',return_value=True):
            preflight=deepseek_successor_preflight(cfg,self.transport,self.route,authorization_file=self.auth,pricing_file=self.price)
            ready=self.base/'allocation_preflight.json';runner.write_new(ready,preflight)
            kwargs=dict(suite='external44',offline=False,formal_validation=True,acceptance_config_file=cfg,
                primary=ds.MODEL,secondary=ds.MODEL,max_output_tokens=32768,api_protocol='responses',
                transport_policy_file=self.transport,network_route_policy_file=self.route,
                successor_authorization_file=self.auth,pricing_record=self.price,preflight_file=ready)
            with patch.object(ds.DeepSeekFormalAdapter,'credential',return_value=fixture.KEY),\
                 patch.object(fixture.p.ProviderJournal,'call',side_effect=AssertionError('NO_PROVIDER_CALL')) as calls:
                result=runner.prepare('calibration_alloc_'+uuid.uuid4().hex,**kwargs)
                self.assertEqual(result['recorded_calls'],0)
                with self.assertRaises((FileExistsError,ValueError)):
                    runner.prepare('calibration_second_'+uuid.uuid4().hex,**kwargs)
                calls.assert_not_called()
        self.assertEqual(old.read_bytes(),before)
        self.assertTrue((evidence/('SUCCESSOR_ALLOCATION_'+ds.CALIBRATED_CANDIDATE+'.json')).is_file())

if __name__=='__main__': unittest.main(verbosity=2)
