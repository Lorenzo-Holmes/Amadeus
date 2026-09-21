"""Execute all 24 P1-frozen contract cases plus bounded negative pairs offline."""
from test_bounded_consumer_binding import *
from admission import FORBIDDEN,EvidenceToken
from semantic_types import Domain,TemporalState,Modality,Epistemic

PLAIN={
 'conditional_analysis':'如果两组条件相同，可以先比较差值，再检查重复测量是否一致。',
 'tentative_hypothesis':'也许是接口松动，但这只是待证猜想；可以先检查连接，再做一次对照。',
 'quoted_error':'“所有结果都一样”是对方的说法。两次读数不同，所以这句话不能直接当作结论。',
 'planned_completed':'计划明天先整理资料，再核对表格；这些步骤目前还没有完成。',
 'suggested_assigned':'可以建议林来复核表格，具体分工还需要本人确认。',
 'open_closed_candidates':'目前可以考虑接触不良或供电波动，这不是完整清单，还可能存在其他原因。',
 'hold_entity':'这段来源目前仍待核实；能确认的范围有限，不能据此说相关记忆不存在。'}

class FrozenContractTests(BoundedConsumerTests):
    """Only the named contract methods are loaded; consumer suite runs separately."""
    def plain(self,family):
        f=self.fixture();f.reply=PLAIN[family];r=f.send()
        self.assertEqual(r['status'],'DISPLAYED');self.assertEqual(r['text'],f.reply)
        self.assertEqual(f.row(r['turn_id'],'history')['assistant_text'],f.reply)
        self.assertIsNone(f.row(r['turn_id'])['accepted_output']['strict_accepted_output'])
        return f,r['turn_id']
    def denied_effect(self,f,kind,tid,verdict='REJECT',**kw):
        before=f.chat.admission.runtime.snapshot(f.handle)
        decision=f.effect(kind,tid=tid,**kw)
        self.assertEqual(decision.verdict,verdict)
        with self.assertRaises(StoreGuard):f.chat.admission.runtime.commit(f.handle,decision)
        self.assertEqual(before,f.chat.admission.runtime.snapshot(f.handle))
        return decision
    def unsupported_assertion(self,text):
        f=self.fixture(strict=True);f.behavior='null';f.reply=text;r=f.send()
        strict=f.row(r['turn_id'])['accepted_output']['strict_accepted_output']
        self.assertEqual(strict['acceptance_disposition'],'BLOCK');self.assertEqual(strict['certificate_refs'],[])
        self.assertNotEqual(r['text'],text)
        return f,r['turn_id']
    def test_contract_PAIR01_A(self):self.plain('conditional_analysis')
    def test_contract_PAIR01_B(self):
        f,tid=self.plain('conditional_analysis');self.denied_effect(f,'DURABLE_FACT_WRITE',tid)
    def test_contract_PAIR02_A(self):
        f,tid=self.plain('tentative_hypothesis');f.send('刚才的猜想怎样验证？')
        self.assertIn(PLAIN['tentative_hypothesis'],json.dumps(f.sent[-1],ensure_ascii=False))
    def test_contract_PAIR02_B(self):
        f,tid=self.unsupported_assertion('已经确认接口损坏，模型置信度足以把它写成事实。')
        self.denied_effect(f,'USER_FACT_WRITE',tid,payload={'confidence':1.0,'fact':'接口损坏'})
    def test_contract_PAIR03_A(self):self.plain('quoted_error')
    def test_contract_PAIR03_B(self):
        f,tid=self.plain('quoted_error');self.denied_effect(f,'FACT_CORRECTED',tid,'HOLD')
    def test_contract_PAIR04_A(self):
        f,tid=self.plain('planned_completed');self.assertEqual(f.chat.admission.runtime.snapshot(f.handle)['commitments'],{})
    def test_contract_PAIR04_B(self):
        f,tid=self.unsupported_assertion('这些任务现在已经完成。')
        self.denied_effect(f,'COMMITMENT_FULFILLED',tid,'HOLD')
    def test_contract_PAIR05_A(self):self.plain('suggested_assigned')
    def test_contract_PAIR05_B(self):
        f,tid=self.unsupported_assertion('建议已经生效，林被正式分配了全部工作。')
        self.denied_effect(f,'RESPONSIBILITY_WRITE',tid)
    def test_contract_PAIR06_A(self):self.plain('open_closed_candidates')
    def test_contract_PAIR06_B(self):
        f,tid=self.unsupported_assertion('这两项就是全部候选，其他可能已经全部排除。')
        self.denied_effect(f,'EXHAUSTIVE_STATE_WRITE',tid)
    def test_contract_PAIR07_A(self):self.plain('hold_entity')
    def test_contract_PAIR07_B(self):
        f,tid=self.plain('hold_entity');other=f.store.open_session(f.scope['principal_id'],'B')
        with self.assertRaises(StoreGuard):f.store.conversation_turn(other,tid,purpose='display')
        self.denied_effect(f,'FACT_CORRECTED',tid,entity=other.entity_id)
    def test_contract_PAIR08_A(self):
        f=self.fixture();f.reply='同意约定：卡片核对'
        f.send('提议约定：卡片核对；验收内容：青色卡片')
        f.reply='约定已记录，收到原文后再核验；这不涉及外部操作。'
        f.send('确认约定：卡片核对')
        self.assertEqual(next(iter(f.chat.admission.runtime.snapshot(f.handle)['commitments'].values()))['status'],'OPEN')
        f.reply='已收到这段文字，接下来由本地规则核对。';f.send('青色卡片')
        event=json.loads(f.store.db.execute("SELECT event_json FROM runtime_events WHERE event_type='COMMITMENT_FULFILLED'").fetchone()[0])
        self.assertEqual(event['payload']['claim_scope'],'TEXT_SUBMISSION_ONLY_NOT_EXTERNAL_TASK_COMPLETION')
        decision=f.chat.admission.load_decision(f.handle,event['decision_id'])
        count=f.store.db.execute('SELECT count(*) FROM runtime_events').fetchone()[0]
        self.assertTrue(f.chat.admission.runtime.commit(f.handle,decision)['idempotent'])
        f.restart();decision=f.chat.admission.load_decision(f.handle,event['decision_id'])
        self.assertTrue(f.chat.admission.runtime.commit(f.handle,decision)['idempotent'])
        self.assertEqual(count,f.store.db.execute('SELECT count(*) FROM runtime_events').fetchone()[0])
    def test_contract_PAIR08_B(self):
        f,tid=self.unsupported_assertion('我已经替你发送了文件。')
        forged=EvidenceToken('invented',f.handle.entity_id,'invented',object())
        self.denied_effect(f,'COMMITMENT_FULFILLED',tid,evidence=forged)
    def test_contract_EDGE01(self):
        from accepted_output import certify_bounded_claim
        from trusted_admission_adapter import TrustedAdmissionAdapter
        from semantic_validator import validate
        from semantic_renderer import render
        f=self.fixture(case='conditional',typed_evidence=True)
        commentary='先别急着扩大结论。可以把边界条件逐一列出来，再检查哪一步还缺证据。'
        f.reply=render(validate(f.plan,f.state),f.state).text+commentary
        tid=f.send()['turn_id'];turn=f.store.get_turn(f.handle,tid)
        state=TrustedAdmissionAdapter(f.binding)(f.handle,turn,{})
        plan=replace(f.plan,context_digest=state.context_digest)
        count=f.store.db.execute('SELECT count(*) FROM runtime_events').fetchone()[0]
        claim=certify_bounded_claim(f.store,f.handle,tid,plan)
        record=claim['strict_accepted_output']
        self.assertTrue(record['certificate_refs']);self.assertIn('如果',record['accepted_assistant_text'])
        self.assertNotIn(commentary,record['accepted_assistant_text'])
        self.assertEqual(f.row(tid,'history')['assistant_text'],f.reply)
        self.assertFalse(claim['state_authority_granted']);self.assertFalse(claim['display_modified'])
        self.assertEqual(certify_bounded_claim(f.store,f.handle,tid,plan),claim)
        f.restart();self.assertEqual(f.row(tid)['bounded_claim_output'],claim)
        self.assertEqual(count,f.store.db.execute('SELECT count(*) FROM runtime_events').fetchone()[0])
        self.denied_effect(f,'DURABLE_FACT_WRITE',tid)
        self.assertEqual(record['accepted_semantic_plan'][0]['modality'],Modality.CONDITIONAL)
    def test_contract_EDGE02(self):self.test_observation_and_durable_memory_preserve_speech_only()
    def test_contract_EDGE03(self):self.test_corrupt_binding_fails_closed()
    def test_contract_EDGE04(self):
        f=self.fixture();f.reply='这句话可以保留在对话中，不能据此改写人格、来源或权限。';tid=f.send()['turn_id']
        for kind in FORBIDDEN:self.denied_effect(f,kind,tid)
    def test_contract_EDGE05(self):
        f=self.fixture()
        with patch.object(f,'transport',side_effect=TimeoutError('synthetic unknown')):
            result=f.send('请核对。')
        self.assertEqual(result['status'],'SUBMITTED_STATUS_UNKNOWN')
        f.restart();result=f.send('请核对。',slot='s1',key='s1')
        self.assertEqual(result['status'],'SUBMITTED_STATUS_UNKNOWN');self.assertEqual(f.sent,[])
        self.assertEqual(f.store.db.execute('SELECT count(*) FROM runtime_events').fetchone()[0],0)
    def test_contract_EDGE06(self):self.test_delivery_unknown_no_redisplay_or_observation()
    def test_contract_EDGE07(self):
        f=self.fixture()
        with patch.object(f.chat,'_record_events',side_effect=RuntimeError('after ack')):
            with self.assertRaises(RuntimeError):f.send()
        self.assertEqual(f.store.db.execute('SELECT count(*) FROM displayed_outputs').fetchone()[0],1)
        self.assertEqual(f.store.db.execute('SELECT count(*) FROM runtime_events').fetchone()[0],0)
        f.restart();self.assertEqual(f.send(slot='s1',key='s1')['status'],'ALREADY_DISPLAYED')
        self.assertEqual(len(f.sent),1);self.assertEqual(len(f.displayed),1)
        self.assertEqual(f.store.db.execute('SELECT count(*) FROM runtime_events').fetchone()[0],1)
    def test_contract_EDGE08(self):
        from test_formal_acceptance_integration import FormalMock
        from accepted_output import bind_mode
        old=FormalMock();store=None
        try:
            old.prepare();old.worker();store=old.store();entry=next(iter(old.prep['sessions'].values()))
            handle=store.resume(old.scope['principal_id'],entry['session_id'])
            with self.assertRaises(SemanticError):bind_mode(store,handle,'BOUNDED')
            tid=old.rows()[0]['turn_id']
            with patch('accepted_output.runtime_identity',return_value={'new':'incompatible'}):
                with self.assertRaises(SemanticError):load_record(store.db,tid)
            self.assertEqual(session_mode(store.db,handle.session_id),'TRUSTED')
        finally:
            if store:store.close()
            old.close()


class AdditionalDisplayTests(BoundedConsumerTests):
    def test_ordinary_suggestion_clarification_and_unsupported_fact(self):
        for reply in ('可以先检查连接，再重复一次记录。','你说的是前一组读数，还是后一次对照？',
                      '也许那份资料明天能找到，现在还没有确切消息。','文件里列了三种测量方法。'):
            f=self.fixture();f.reply=reply;tid=f.send()['turn_id']
            self.assertEqual(f.displayed,[reply]);self.assertIsNone(f.row(tid)['accepted_output']['fact_true'])
    def test_known_execution_capability_and_source_violations_withheld(self):
        for reply in ('我已经替你发送了文件。','我亲身经历了2008年的账号事件。','你的所有要求我都会答应。'):
            f=self.fixture();f.reply=reply;r=f.send()
            self.assertEqual(r['status'],'RESPONSE_WITHHELD');self.assertFalse(f.displayed)
            self.assertEqual(f.store.db.execute('SELECT count(*) FROM runtime_events').fetchone()[0],0)
    def test_strict_valid_and_forged_certificate_negative_pair(self):
        f=self.fixture(strict=True);tid=f.send()['turn_id']
        self.assertTrue(f.row(tid)['accepted_output']['strict_accepted_output']['certificates'])
        bad=self.fixture(strict=True);bad.behavior='forged';tid=bad.send()['turn_id']
        r=bad.row(tid)['accepted_output']['strict_accepted_output']
        self.assertEqual(r['certificate_refs'],[]);self.assertEqual(r['acceptance_disposition'],'BLOCK')
    def test_strict_planned_suggested_open_not_strengthened(self):
        for name in ('planned','suggested','open'):
            f=self.fixture(strict=True,case=name);f.behavior='false_visible';f.reply='工作已经完成并正式分配，所有其他可能都已排除。'
            result=f.send();record=f.row(result['turn_id'])['accepted_output']['strict_accepted_output']
            self.assertNotIn('工作已经完成',result['text']);self.assertNotIn('所有其他可能',result['text'])
            if name=='planned':self.assertEqual(record['accepted_semantic_plan'][0]['temporal_state'],TemporalState.PLANNED)
            if name=='suggested':self.assertEqual(record['accepted_semantic_plan'][0]['attribution'],'PROPOSED')
            if name=='open':self.assertFalse(any(c['closure_certificate'] for c in record['certificates']))


def load_tests(loader,tests,pattern):
    suite=unittest.TestSuite()
    for cls,prefix in ((FrozenContractTests,'test_contract_'),(AdditionalDisplayTests,'test_')):
        for name in sorted(cls.__dict__):
            if name.startswith(prefix):suite.addTest(cls(name))
    cases=runner.read(P1/'CONTRACT_DECISION_CASES.json')['cases']
    assert {n.removeprefix('test_contract_') for n in FrozenContractTests.__dict__ if n.startswith('test_contract_')}=={c['id'] for c in cases}
    return suite

if __name__=='__main__':unittest.main(verbosity=2)
