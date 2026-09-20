"""Isolated offline consumer/identity/restart tests; no target-model evidence."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'persona_core/operational_runtime_v1'),str(Path(__file__).parent),
              str(ROOT/'persona_core/operational_build_v1/tools')]
import copy, json, shutil, socket, unittest, uuid, os
from unittest.mock import patch
from dataclasses import replace,asdict
import evaluation_runner as runner
from semantic_binding import *
from semantic_types import digest,canonical,SemanticError
from semantic_acceptance_fixtures import scenario
from test_formal_acceptance_integration import catalog
from accepted_output import load_record,load_display_record,project_turn,raw_text_for_audit,session_mode
from transcript_store import TranscriptStore,create_sandbox,StoreGuard
from operations import open_chat
from test_chat_r045 import scope as legacy_scope,body

P1=ROOT/'persona_core/gpt6_optimization_v2/architecture_scope_reconciliation_20260920_01'

class BoundedFixture:
    def __init__(self,*,strict=False,case='possible',typed_evidence=False):
        self.name='bounded_fixture_'+uuid.uuid4().hex
        self.work=ROOT/'work/bounded_p2_p3/fixtures'/self.name
        self.work.mkdir(parents=True)
        self.root=ROOT/'persona_core/operational_build_v1/evidence'/self.name
        create_sandbox(self.root)
        self.store=TranscriptStore(self.root)
        self.scope=legacy_scope()
        self.scope.update(batch_id=self.name,formal_validation=True,total_guard_cny=4.0,
            reserved_upper_micro_cny=1096992,
            slots=[{'id':f's{i}','model':'deepseek-v4-flash','entity_label':'A','user_text':None} for i in range(1,13)])
        self.state,self.plan=scenario(case)
        self.strict=strict
        self.catalog=self.work/'catalog.json'
        runner.write_new(self.catalog,catalog(self.state) if strict or typed_evidence else runner.read(runner.CODE/'trusted_semantic_catalog.json'))
        self.files=runner.source_bindings()
        self.files.update({runner.relative(p):runner.sha(p) for p in P1.glob('*') if p.name in
            {'CONTRACT_FREEZE_MANIFEST.json','EXTERNAL44_CRITERION_ROUTING.json','CONSUMER_AUTHORITY_MATRIX.json'}})
        self.files[runner.relative(self.catalog)]=runner.sha(self.catalog)
        self.freeze=self.work/'source.json'
        runner.write_new(self.freeze,{'freeze_id':self.name,'files':self.files,'status':'OFFLINE_TEST_ONLY'})
        ref=lambda p:{'path':runner.relative(p),'sha256':runner.sha(p)}
        self.config={'semantic_acceptance_mode':'BOUNDED','acceptance_policy_version':DISPLAY_POLICY,
            'acceptance_source_freeze':self.name,'acceptance_source_manifest':ref(self.freeze),
            'trusted_semantic_runtime_version':RUNTIME_VERSION,'semantic_source':ref(self.catalog),
            'architecture_contract':ARCHITECTURE_CONTRACT,'contract_manifest':ref(P1/'CONTRACT_FREEZE_MANIFEST.json'),
            'criterion_routing':ref(P1/'EXTERNAL44_CRITERION_ROUTING.json'),
            'consumer_authority_matrix':ref(P1/'CONSUMER_AUTHORITY_MATRIX.json'),
            'display_policy_version':DISPLAY_POLICY,'state_admission_policy_version':STATE_POLICY,
            'strict_semantic_policy_version':VERSION,'consumer_purpose':'BOUNDED_CLAIM' if strict else 'DISPLAY',
            'task_role':'STRICT_BOUNDED_CLAIM' if strict else 'CONVERSATION'}
        self.config_path=self.work/'acceptance.json';runner.write_new(self.config_path,self.config)
        self.binding=runner.build_acceptance_binding(self.scope,{'cases_path':runner.GOAL/'external_failure_v1/CASES.json'},
            self.config_path,rubric_path=runner.GOAL/'external_failure_v1/PRIVATE_RUBRIC.json',offline=True)
        self.scope['semantic_acceptance_binding']=self.binding
        self.handle=self.store.open_session(self.scope['principal_id'],'A')
        self.chat=open_chat(self.store,self.handle,self.scope)
        self.sent=[]; self.displayed=[]; self.behavior='valid'
        self.reply='如果两组条件相同，可以先比较差值，再检查重复测量是否一致。'

    def transport(self,payload,key):
        request=json.loads(payload);self.sent.append(request)
        if not self.strict:
            assert not any(m['content'].startswith('Host semantic proposal contract:') for m in request['messages'])
            return 200,body(self.reply)
        from semantic_validator import validate
        from semantic_renderer import render
        contract=json.loads(next(m['content'] for m in request['messages'] if
            m['content'].startswith('Host semantic proposal contract:')).split('\n',1)[1])
        inv=contract['trusted_inventory']
        state=replace(self.state,identity=tuple(inv['identity']),unparsed_sha256=tuple(inv['unparsed_sha256']))
        plan=replace(self.plan,context_digest=contract['context_digest'])
        value={'kind':'PROPOSED_SEMANTIC_PLAN','plan':asdict(plan),
               'visible_text':render(validate(plan,state),state).text}
        if self.behavior=='null': value.update(plan=None,visible_text=self.reply)
        elif self.behavior=='forged': value['certificate_valid']=True
        elif self.behavior=='false_visible': value['visible_text']=self.reply
        elif self.behavior=='plan_override': value['plan']=self.plan_override(asdict(plan))
        return 200,body(canonical(value))

    def send(self,text='请按上述条件给一个具体检查方法。',*,slot=None,key=None,display=True):
        slot=slot or 's'+str(len(self.sent)+1)
        return self.chat.send_text(text,key or slot,slot_id=slot,
            display=self.displayed.append if display else None,transport=self.transport,
            credential_reader=lambda:'OFFLINE_FIXTURE_NOT_A_REAL_KEY')

    def restart(self):
        sid=self.handle.session_id
        self.store.close();self.store=TranscriptStore(self.root)
        self.handle=self.store.resume(self.scope['principal_id'],sid)
        self.chat=open_chat(self.store,self.handle,self.scope)

    def row(self,tid,purpose='evaluation'):
        row=dict(self.store.db.execute('SELECT t.*,p.raw_sha256 FROM turns t JOIN provider_calls p USING(turn_id) WHERE turn_id=?',(tid,)).fetchone())
        return project_turn(self.store.db,row,purpose)

    def effect(self,kind,payload=None,*,tid=None,entity=None,evidence=None):
        cid=self.chat.admission.propose(self.handle,kind,payload or {'text':self.reply},key=uuid.uuid4().hex,
            source_turn_ids=[tid] if tid else [],claimed_entity_id=entity)
        return self.chat.admission.decide(self.handle,cid,evidence)

    def close(self):
        evidence=os.environ.get('APCORE_OFFLINE_EVIDENCE_DIR')
        if evidence:
            out=Path(evidence).resolve()
            assert out.is_relative_to(runner.GOAL) and 'bounded_boundary_p2_p3_' in str(out)
            tables=('accepted_outputs','displayed_outputs','bounded_claim_outputs','chat_traces','runtime_events',
                    'event_candidates','admission_decisions','evidence_receipts','display_journal','turn_lifecycle')
            snapshot={'fixture':self.name,'test':getattr(self,'test_name',None),'source_hashes':self.files,
                      'network_mode':'MOCK_ONLY','provider_requests':0,'mock_calls':len(self.sent),
                      'actual_displayed_text':self.displayed,'records':{}}
            for table in tables:
                snapshot['records'][table]=[dict(r) for r in self.store.db.execute('SELECT * FROM '+table)]
            runner.write_new(out/(self.name+'.json'),snapshot)
        self.store.close()
        for p,base in ((self.root,ROOT/'persona_core/operational_build_v1/evidence'),
                       (self.work,ROOT/'work/bounded_p2_p3/fixtures')):
            assert p.resolve().parent==base.resolve() and p.name.startswith('bounded_fixture_')
            shutil.rmtree(p)


class BoundedConsumerTests(unittest.TestCase):
    def setUp(self):
        self.fixtures=[]
        self.guards=[patch.object(socket.socket,'connect',side_effect=AssertionError('OFFLINE_NETWORK_FORBIDDEN')),
                     patch.object(socket.socket,'connect_ex',side_effect=AssertionError('OFFLINE_NETWORK_FORBIDDEN'))]
        for g in self.guards:g.start()
    def tearDown(self):
        for f in self.fixtures:f.close()
        for g in self.guards:g.stop()
    def fixture(self,**kw):
        f=BoundedFixture(**kw);f.test_name=self.id();self.fixtures.append(f);return f
    def test_display_history_next_turn_and_working_context(self):
        f=self.fixture();first=f.send();tid=first['turn_id']
        self.assertEqual(first['status'],'DISPLAYED')
        self.assertEqual(f.displayed[0],f.row(tid,'history')['assistant_text'])
        self.assertEqual(f.row(tid,'next_turn_context')['assistant_text'],f.displayed[0])
        f.send('刚才的第二步具体怎样做？')
        history=next(m['content'] for m in f.sent[1]['messages'] if m['content'].startswith('以下是按时间排列'))
        self.assertIn(f.displayed[0],history)
        self.assertNotIn('raw_assistant_text',history)
        self.assertIn('计划或自述仍按原意',history)
    def test_raw_display_and_accepted_separate(self):
        f=self.fixture(strict=True);tid=f.send()['turn_id'];row=f.row(tid)
        self.assertNotEqual(row['raw_assistant_text'],row['displayed_text'])
        self.assertEqual(raw_text_for_audit(row),row['raw_assistant_text'])
        self.assertIsNotNone(row['accepted_output']['strict_accepted_output'])
        for purpose in ('display','history','next_turn_context','memory','candidate','blind'):
            self.assertNotIn('raw_assistant_text',f.row(tid,purpose))
    def test_ordinary_lineage_is_not_fact_or_strict_acceptance(self):
        f=self.fixture();tid=f.send()['turn_id'];row=f.row(tid);r=row['accepted_output']
        self.assertEqual(r['coverage'],'UNPARSED_CONVERSATIONAL')
        self.assertIsNone(r['strict_accepted_output']);self.assertIsNone(r['fact_true'])
        self.assertIsNone(r['semantic_verdict']);self.assertFalse(r['content_is_event_proof'])
        self.assertEqual(r['state_admission_result'],'NOT_REQUESTED')
    def test_observation_and_durable_memory_preserve_speech_only(self):
        f=self.fixture();f.reply='也许装置存在偏差，目前还缺少对照。';tid=f.send()['turn_id']
        rows=f.store.db.execute('SELECT event_json FROM runtime_events').fetchall()
        events=[json.loads(r[0]) for r in rows]
        self.assertEqual(len(events),1);event=events[0]
        self.assertEqual(event['event_type'],'UTTERANCE_OBSERVED')
        self.assertEqual(event['payload']['assistant_text'],f.displayed[0])
        self.assertFalse(event['payload']['described_events_proven']);self.assertFalse(event['payload']['content_is_event_proof'])
        self.assertIn('displayed_output_sha256',event['payload'])
        retrieved=f.chat.memory_provider.search(f.handle,'具体检查方法',include_source=False)
        speech=next(r for r in retrieved if r['record_kind']=='UTTERANCE_OBSERVED')
        self.assertEqual(speech['assistant_utterance'],f.reply)
        self.assertFalse(speech['assistant_utterance_is_fact_authority'])
        self.assertEqual(f.chat.admission.runtime.verify()['integrity'],'ok')
    def test_restart_and_idempotent_ack_recovery(self):
        f=self.fixture();r=f.send();before=f.row(r['turn_id']);f.restart()
        again=f.send(slot='s1',key='s1')
        self.assertEqual(again['status'],'ALREADY_DISPLAYED');self.assertEqual(len(f.sent),1)
        self.assertEqual(len(f.displayed),1);self.assertEqual(before,f.row(r['turn_id']))
        self.assertEqual(f.store.db.execute('SELECT count(*) FROM runtime_events').fetchone()[0],1)
    def test_delivery_unknown_no_redisplay_or_observation(self):
        f=self.fixture()
        with self.assertRaises(RuntimeError):
            f.chat.send_text('请给建议。','s1',slot_id='s1',display=lambda _:(_ for _ in ()).throw(RuntimeError('sink crash')),
                transport=f.transport,credential_reader=lambda:'OFFLINE_FIXTURE_NOT_A_REAL_KEY')
        f.restart();r=f.send('请给建议。',slot='s1',key='s1')
        self.assertEqual(r['status'],'DELIVERY_STATUS_UNKNOWN');self.assertEqual(len(f.sent),1)
        self.assertEqual(f.store.db.execute('SELECT count(*) FROM runtime_events').fetchone()[0],0)
        self.assertIsNone(f.store.conversation_recent(f.handle,purpose='history')[0]['assistant_text'])
    def test_wrong_entity_display_and_state(self):
        f=self.fixture();tid=f.send()['turn_id'];other=f.store.open_session(f.scope['principal_id'],'B')
        with self.assertRaises(StoreGuard):f.store.conversation_turn(other,tid,purpose='history')
        d=f.effect('FACT_CORRECTED',tid=tid,entity=other.entity_id)
        self.assertEqual(d.verdict,'REJECT')
    def test_corrupt_binding_fails_closed(self):
        f=self.fixture();f.send()
        f.store.db.execute('DROP TRIGGER semantic_binding_no_update')
        f.store.db.execute("UPDATE semantic_session_binding SET binding_sha256='corrupt'")
        with self.assertRaises(BindingError):f.store.conversation_recent(f.handle,purpose='history')
    def test_missing_policy_cannot_fall_back_to_raw(self):
        f=self.fixture();f.send();f.store.db.execute('DROP TRIGGER formal_policy_no_delete')
        f.store.db.execute('DELETE FROM semantic_session_policy')
        with self.assertRaises(BindingError):f.store.conversation_recent(f.handle,purpose='history')
    def test_source_mismatch_explicit_legacy_rejection(self):
        f=self.fixture();tid=f.send()['turn_id']
        from accepted_output import bind_mode
        with self.assertRaises(SemanticError):bind_mode(f.store,f.handle,'TRUSTED')
        with patch('accepted_output.runtime_identity',return_value={'incompatible':'source'}):
            with self.assertRaises(SemanticError):load_record(f.store.db,tid)
        self.assertEqual(session_mode(f.store.db,f.handle.session_id),'BOUNDED')
    def test_raw_and_display_immutable_and_tamper_detected(self):
        import sqlite3
        f=self.fixture();tid=f.send()['turn_id']
        for table in ('semantic_raw_outputs','accepted_outputs','displayed_outputs'):
            with self.assertRaises(sqlite3.IntegrityError):f.store.db.execute('DELETE FROM '+table)
        f.store.db.execute('DROP TRIGGER displayed_no_update')
        f.store.db.execute("UPDATE displayed_outputs SET record_sha256='corrupt'")
        with self.assertRaises(SemanticError):f.row(tid,'history')
    def test_evaluation_blind_audit_and_export_consumers(self):
        from blind_review_v2 import approved_display_projection
        from capture_export import export_calls
        f=self.fixture();tid=f.send()['turn_id'];row=f.row(tid)
        p=runner.display_state_provenance(row,f.binding)
        self.assertEqual(p['conversation_utility'],'UNREVIEWED');self.assertEqual(p['state_integrity'],'UNREVIEWED')
        visible,restricted=approved_display_projection(f.store.db,f.store.get_turn(f.handle,tid))
        self.assertEqual(set(visible),{'user_text','assistant_text'});self.assertEqual(visible['assistant_text'],f.displayed[0])
        self.assertIsNotNone(restricted['display_record'])
        exported=export_calls(f.store,f.root/'export')
        names={Path(x['path']).name for r in exported['exports'] for x in r['files']}
        self.assertTrue({'RAW_RESPONSE.json','ACCEPTED_OUTPUT.json','DISPLAYED_OUTPUT.json','STATE_ADMISSION.json'}<=names)
        self.assertEqual(exported,export_calls(f.store,f.root/'export'))
    def test_dual_gate_never_inherits_display_or_guard_pass(self):
        import semantic_review as review
        f=self.fixture();tid=f.send()['turn_id'];row=f.row(tid);trace=row['state_lineage']
        routes=review.bounded_routes(f.binding);self.assertEqual(len(routes),176)
        a={'verdict':'PASS','quote':f.reply,'rationale':'The conditional response gives a relevant check.'}
        evidence={k+'_sha256':digest(trace[k]) for k in ('state_before','state_after','events')};evidence['trace_sha256']=digest(trace)
        item={'verdict':'PASS','conversation_utility':a,'state_integrity':{'verdict':'PASS','rationale':'Only speech observed.','evidence':evidence}}
        self.assertEqual(review.bind_dual_judgment(row,item,'BOTH'),'PASS')
        for change in ('missing','state_fail','utility_fail','wrong_quote','wrong_trace'):
            bad=copy.deepcopy(item)
            if change=='missing':bad['state_integrity']=None
            elif change=='state_fail':bad['state_integrity']['verdict']='FAIL'
            elif change=='utility_fail':bad['conversation_utility']['verdict']='FAIL'
            elif change=='wrong_quote':bad['conversation_utility']['quote']='not displayed'
            else:bad['state_integrity']['evidence']['trace_sha256']='corrupt'
            with self.assertRaises(review.ReviewError):review.bind_dual_judgment(row,bad,'BOTH')
    def test_actual_formal_driver_uses_bounded_display_and_zero_call_preflight(self):
        from test_formal_acceptance_integration import FormalMock
        from formal_binding_preflight import preflight
        f=self.fixture();formal=FormalMock(config=lambda _:f.config)
        try:
            formal.prepare()
            def transport(payload,key):
                request=json.loads(payload)
                self.assertFalse(any(m['content'].startswith('Host semantic proposal contract:') for m in request['input']))
                return 200,runner.canonical({'model':request['model'],'responses_api_status':'completed',
                    'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120},
                    'choices':[{'finish_reason':'stop','message':{'content':f.reply}}]})
            formal.transport=transport
            self.assertEqual(formal.worker()['status'],'PAUSED_KNOWN_PREFIX')
            row=formal.rows()[0]
            self.assertEqual(row['displayed_text'],f.reply)
            self.assertEqual(row['evaluation_provenance']['conversation_utility'],'UNREVIEWED')
            self.assertEqual((formal.manifest['expected_turn_count'],formal.manifest['expected_criteria_count']),(44,176))
            result=preflight(f.config_path,formal.transport_policy,formal.route_policy)
            self.assertEqual(result['status'],'BOUNDED_CONVERSATION_STATE_BINDING_READY')
            self.assertEqual(result['provider_call_invocations'],0)
            self.assertTrue(all(s['mode']=='BOUNDED' for s in result['session_checks']))
        finally:formal.close()
    def test_full_dual_review_denominator_and_major_blocker_algebra(self):
        """Synthetic binder unit: no 44-turn target capture or quality claim."""
        import semantic_review as review
        f=self.fixture();tid=f.send()['turn_id'];row=f.row(tid);trace=row['state_lineage']
        routes=review.bounded_routes(f.binding);sids=sorted({sid for sid,c in routes})
        criteria=sorted({c for sid,c in routes})
        case={'id':'OFFLINE_ALGEBRA','category':'synthetic','quality_eligible':True,
              'turns':[{'id':sid,'quality_eligible':True} for sid in sids]}
        bundle=review.Bundle([case],criteria,review.MINIMUMS,{sid:row for sid in sids},
                            {'semantic_acceptance_binding':f.binding},{},{})
        stamp=runner.now()
        declaration={'name_or_identifier':'OFFLINE_BINDER_FIXTURE','role':'DEVELOPER','review_started_at_utc':stamp,
            'review_completed_at_utc':stamp,'authorship_confirmed':True,
            'participated_in_implementation_tuning_or_case_design':True,
            'prior_exposure_to_development_outputs':True,'conflicts_of_interest':False}
        evidence={k+'_sha256':digest(trace[k]) for k in ('state_before','state_after','events')};evidence['trace_sha256']=digest(trace)
        with patch.object(review,'fresh',return_value=bundle):
            form=review.blank_review(bundle);form.update(reviewer=declaration,findings_complete=True)
            for turn in form['cases'][0]['turn_reviews']:
                for item in turn['judgments']:
                    item.update(verdict='PASS',quote=f.reply,rationale='Synthetic judgment binding fixture.',finding_ids=[])
                    item['conversation_utility'].update(verdict='PASS',quote=f.reply,rationale='Synthetic display judgment.')
                    if item['state_integrity'] is not None:
                        item['state_integrity'].update(verdict='PASS',rationale='Synthetic state judgment.',evidence=evidence)
            for q,item in form['cases'][0]['quality'].items():
                item.update(score=review.MINIMUMS[q],rationale='Exercise unchanged threshold algebra only.',
                            evidence=[{'slot_id':sids[0],'quote':f.reply}])
            result=review.bind_review(bundle,form)
            self.assertEqual(result['coverage']['criteria'],176)
            self.assertEqual(result['dual_gate']['conversation_subchecks'],{'PASS':176})
            self.assertEqual(result['dual_gate']['state_subchecks'],{'PASS':132})
            self.assertTrue(result['recorded_review_gate_met']);self.assertFalse(result['product_acceptance_complete'])
            form['findings']=[{'id':'synthetic_major','severity':'MAJOR','status':'OPEN','rationale':'Open major blocks the gate.',
                'affected_slots':[sids[0]],'evidence':[{'slot_id':sids[0],'quote':f.reply}]}]
            self.assertFalse(review.bind_review(bundle,form)['recorded_review_gate_met'])
    def test_missing_display_ack_cannot_be_promoted_by_legacy_marker(self):
        f=self.fixture();r=f.send(display=False)
        self.assertEqual(r['status'],'READY_TO_DISPLAY')
        with self.assertRaises(SemanticError):f.store.mark_displayed(f.handle,r['turn_id'])
        self.assertEqual(f.store.db.execute('SELECT count(*) FROM runtime_events').fetchone()[0],0)

if __name__=='__main__':unittest.main(verbosity=2)
