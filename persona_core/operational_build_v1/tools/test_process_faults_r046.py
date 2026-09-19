"""Real subprocess kill/reopen and simultaneous-writer tests; strictly offline."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
import unittest
import uuid
import zipfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
CODE=ROOT/'persona_core/operational_runtime_v1'
WORKER=Path(__file__).with_name('runtime_fault_worker_r046.py')
sys.path.insert(0,str(CODE))
from transcript_store import create_sandbox,TranscriptStore,file_sha,utc_now
from admission import AdmissionController
from runtime_store import RuntimeStore

OUT=ROOT/'persona_core/operational_build_v1/evidence/R046-02'/('process_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))

class ProcessFaultTests(unittest.TestCase):
    def setUp(self):
        self.root=create_sandbox(OUT/self._testMethodName)
        self.s=TranscriptStore(self.root)
        self.h=self.s.open_session('OFFLINE_OPERATOR','A')
        self.b=self.s.open_session('OFFLINE_OPERATOR','B')
        self.a=AdmissionController(self.s)
        self.r=RuntimeStore(self.s,self.a)
        self.children=[]
    def tearDown(self):
        for proc,stdout,stderr in self.children:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=10)
            stdout.close();stderr.close()
        self.s.close()
    def turn(self,text,handle=None):
        h=handle or self.h
        turn=self.s.begin_turn(h,text,uuid.uuid4().hex)
        self.s.capture_reply(h,turn['turn_id'],'具名离线测试答复','FIXTURE_'+uuid.uuid4().hex,origin='AUTHORED_TEST_STUB')
        self.s.mark_displayed(h,turn['turn_id'])
        return turn['turn_id']
    def prepare_decision(self,text,handle=None):
        h=handle or self.h
        tid=self.turn(text,h)
        turn=self.s.get_turn(h,tid)
        payload={'turn_id':tid,'user_text':text,'assistant_text':turn['assistant_text'],
            'input_provenance':turn['input_provenance'],'response_provenance':turn['response_provenance'],'described_events_proven':False}
        return self.a._observed_decision(h,'UTTERANCE_OBSERVED',payload,[tid])
    def reopen(self):
        sid,bid=self.h.session_id,self.b.session_id
        self.s.close()
        self.s=TranscriptStore(self.root)
        self.h=self.s.resume('OFFLINE_OPERATOR',sid)
        self.b=self.s.resume('OFFLINE_OPERATOR',bid)
        self.a=AdmissionController(self.s);self.r=RuntimeStore(self.s,self.a)
    def launch(self,name,extra,handle=None,barrier=None):
        h=handle or self.h
        record=self.root/(name+'_RESULT.json')
        ready=self.root/(name+'_READY.json')
        command=[sys.executable,'-B',str(WORKER),'--root',str(self.root),'--session',h.session_id,
                 '--principal','OFFLINE_OPERATOR','--record',str(record)]+extra
        if barrier:
            command+=['--ready',str(ready),'--barrier',str(barrier)]
        (self.root/(name+'_INVOCATION.json')).write_text(json.dumps({'command':command,'parent_pid':os.getpid(),
            'started_at_utc':utc_now(),'network_calls':0},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        stdout=(self.root/(name+'_STDOUT.txt')).open('xb')
        stderr=(self.root/(name+'_STDERR.txt')).open('xb')
        proc=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr,
                              env={**os.environ,'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1'})
        self.children.append((proc,stdout,stderr))
        return proc,record,ready
    def wait(self,worker,expected_code=0):
        proc,record,_=worker
        code=proc.wait(timeout=40)
        self.assertEqual(code,expected_code,'Worker failed; original STDERR preserved at '+str(record))
        self.assertTrue(record.exists())
        result=json.loads(record.read_text(encoding='utf-8'))
        self.assertNotEqual(result['pid'],os.getpid())
        self.assertEqual(result['pid'],proc.pid)
        return result
    def fault_case(self,point):
        turn=self.turn('故障注入下的普通离线记录')
        crashed=self.launch('crash',['--observe-turn',turn,'--fault',point])
        record=self.wait(crashed,77)
        self.assertEqual(record['fault_point'],point)
        self.reopen()
        expected=1 if point=='AFTER_COMMIT_BEFORE_RETURN' else 0
        self.assertEqual(self.r.verify()['events'],expected)
        retry=self.launch('reconcile',['--observe-turn',turn])
        recovery=self.wait(retry)
        self.reopen()
        self.assertEqual(self.r.verify()['events'],1)
        self.assertEqual(self.r.snapshot(self.h)['relationship']['observed_turn_count'],1)
        self.assertEqual(recovery['results'][0]['idempotent'],point=='AFTER_COMMIT_BEFORE_RETURN')
    def test_f0_before_candidate_process_death(self):
        self.fault_case('BEFORE_CANDIDATE')
    def test_f1_before_decision_process_death(self):
        self.fault_case('BEFORE_DECISION_WRITE')
    def test_f2_after_begin_process_death(self):
        self.fault_case('AFTER_BEGIN')
    def test_f3_after_event_insert_process_death(self):
        self.fault_case('AFTER_EVENT_INSERT')
    def test_f4_after_state_write_process_death(self):
        self.fault_case('AFTER_STATE_WRITE')
    def test_f4b_after_index_write_process_death(self):
        self.fault_case('AFTER_INDEX_WRITE')
    def test_f5_before_commit_process_death(self):
        self.fault_case('BEFORE_COMMIT')
    def test_f6_after_commit_before_return_process_death(self):
        self.fault_case('AFTER_COMMIT_BEFORE_RETURN')
    def release_barrier(self,workers,barrier):
        deadline=time.monotonic()+15
        while not all(w[2].exists() for w in workers):
            if any(w[0].poll() is not None for w in workers):
                self.fail('Worker exited before ready barrier; logs retained')
            if time.monotonic()>deadline:
                self.fail('Worker readiness timeout; logs retained')
            time.sleep(0.02)
        self.assertNotEqual(workers[0][0].pid,workers[1][0].pid)
        barrier.write_text(json.dumps({'released_at_utc':utc_now(),'parent_pid':os.getpid()}),encoding='utf-8')
    def test_f7_two_processes_same_event_id(self):
        decision=self.prepare_decision('并发提交的同一事件')
        barrier=self.root/'START.json'
        workers=[self.launch('writer'+str(i),['--decision',decision.decision_id,'--event-id','SAME_EVENT'],barrier=barrier) for i in range(2)]
        self.release_barrier(workers,barrier)
        outputs=[self.wait(w) for w in workers]
        self.reopen()
        self.assertEqual(self.r.verify()['events'],1)
        self.assertEqual(sorted(o['results'][0]['idempotent'] for o in outputs),[False,True])
    def test_f8_two_processes_different_entities_no_lost_events(self):
        decisions_a=[self.prepare_decision('A私密'+str(i)) for i in range(10)]
        decisions_b=[self.prepare_decision('B私密'+str(i),self.b) for i in range(10)]
        barrier=self.root/'START.json'
        workers=[]
        for name,handle,decisions in [('writerA',self.h,decisions_a),('writerB',self.b,decisions_b)]:
            extra=[part for d in decisions for part in ['--decision',d.decision_id]]
            workers.append(self.launch(name,extra,handle,barrier))
        self.release_barrier(workers,barrier)
        outputs=[self.wait(w) for w in workers]
        self.reopen()
        self.assertEqual(self.r.verify()['events'],20)
        for handle in [self.h,self.b]:
            self.assertEqual(self.r.snapshot(handle)['relationship']['observed_turn_count'],10)
            self.assertEqual(self.r.snapshot(handle)['relationship']['trust'],0)
        event_a=outputs[0]['results'][0]['event_id']
        from transcript_store import StoreGuard
        with self.assertRaises(StoreGuard):self.r.get_event(self.b,event_a)
    def test_f9_same_receipt_different_event_ids_concurrent(self):
        text='提交固定口令';expected='OFFLINE-COMPLETE-ONLY'
        t1=self.turn('我们约定'+text+'；验收内容：'+expected)
        # Replace the test fixture's unshown response through a fresh explicit
        # proposal, not by mutating an already captured immutable response.
        t1row=self.s.begin_turn(self.h,'明确提议：'+text+'；验收内容：'+expected,uuid.uuid4().hex)
        self.s.capture_reply(self.h,t1row['turn_id'],'同意约定：'+text,'FIXTURE_AGREEMENT',origin='AUTHORED_TEST_STUB')
        self.s.mark_displayed(self.h,t1row['turn_id'])
        t2=self.turn('确认约定：'+text)
        opened=self.a.confirm_agreement(self.h,t1row['turn_id'],t2,text,expected)
        self.r.commit(self.h,opened)
        cid=json.loads(opened.payload_json)['commitment_id']
        completion=self.a.verify_text_submission(self.h,cid,self.turn(expected))
        barrier=self.root/'START.json'
        workers=[self.launch('receipt'+str(i),['--decision',completion.decision_id,'--event-id','DIFFERENT_EVENT_'+str(i)],barrier=barrier) for i in range(2)]
        self.release_barrier(workers,barrier)
        outputs=[self.wait(w) for w in workers]
        self.reopen()
        self.assertEqual(self.r.verify()['events'],2)
        self.assertEqual(self.r.snapshot(self.h)['relationship']['trust'],0.25)
        self.assertEqual(self.r.snapshot(self.h)['relationship']['verified_completions'],1)
        self.assertEqual(sorted(o['results'][0]['idempotent'] for o in outputs),[False,True])

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    paths=list(CODE.glob('*.py'))+[Path(__file__),WORKER]
    with zipfile.ZipFile(OUT/'TESTED_SOURCE.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
        for path in paths:z.writestr(path.relative_to(ROOT).as_posix(),path.read_bytes())
    with (OUT/'TESTS.log').open('x',encoding='utf-8') as f:
        result=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProcessFaultTests))
    report={'at_utc':utc_now(),'tests':result.testsRun,'passed':result.wasSuccessful(),
        'errors':len(result.errors),'failures':len(result.failures),'target_model_calls':0,
        'actual_os_exit_points':['BEFORE_CANDIDATE','BEFORE_DECISION_WRITE','AFTER_BEGIN','AFTER_EVENT_INSERT',
             'AFTER_STATE_WRITE','AFTER_INDEX_WRITE','BEFORE_COMMIT','AFTER_COMMIT_BEFORE_RETURN'],
        'actual_two_process_tests':3,'origin':'AUTHORED_OFFLINE_FAULTS_NOT_REAL_USER_EXPERIENCE',
        'source_snapshot_sha256':file_sha(OUT/'TESTED_SOURCE.zip'),
        'tested_sources':[{'path':p.relative_to(ROOT).as_posix(),'sha256':file_sha(p)} for p in paths]}
    (OUT/'TESTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':OUT.relative_to(ROOT).as_posix(),'tests':result.testsRun,'passed':result.wasSuccessful()},ensure_ascii=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)

if __name__=='__main__':main()
