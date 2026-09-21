from __future__ import annotations
import hashlib,json,sqlite3,unittest
from datetime import datetime,timezone
from pathlib import Path
import natural_day_validation_repaired_r047 as n

ROOT=n.ROOT
OUT=n.PLAN/'evidence/R047-04'/('repaired_natural_day_tests_static')
NOW=datetime(2026,9,12,0,30,tzinfo=timezone.utc)

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def setup_case(name):
    root=OUT/name; root.mkdir(parents=True,exist_ok=True)
    runtime=root/'runtime'; runtime.mkdir(); checkpoints=root/'checkpoints'
    release=root/'RELEASE_MANIFEST.json'; release.write_text('{}',encoding='utf-8')
    init=root/'INITIALIZATION_CHECKPOINT.json'; init.write_text('{}',encoding='utf-8')
    scope=json.loads((n.PLAN/'evidence/R047-04/NATURAL_DAY_OBSERVATION_SCOPE.json').read_text(encoding='utf-8'))
    scope['batch_id']='TEST-REPAIRED-'+name; scope_path=root/'USER_CHAT_SCOPE.json'; scope_path.write_text(json.dumps(scope),encoding='utf-8')
    db=sqlite3.connect(runtime/'runtime.sqlite3')
    db.executescript('''
    CREATE TABLE runtime_current(singleton INTEGER PRIMARY KEY,state_json TEXT,state_sha256 TEXT,last_event_sha256 TEXT,next_sequence INTEGER);
    CREATE TABLE call_batches(batch_id TEXT PRIMARY KEY,scope_sha256 TEXT,stopped INTEGER);
    CREATE TABLE sessions(session_id TEXT PRIMARY KEY);
    CREATE TABLE turns(turn_id TEXT PRIMARY KEY,user_text TEXT,status TEXT,display_at_utc TEXT,input_provenance TEXT,response_provenance TEXT);
    CREATE TABLE provider_calls(call_id TEXT PRIMARY KEY,turn_id TEXT,session_id TEXT,batch_id TEXT,slot_id TEXT,model TEXT,status TEXT,error_category TEXT,context_json TEXT,submitted_at_utc TEXT);
    CREATE TABLE cli_process_runs(process_id INTEGER,session_id TEXT,started_at_utc TEXT,ended_at_utc TEXT,exit_code INTEGER);
    CREATE TABLE runtime_events(event_id TEXT);
    ''')
    state={'commitments':{},'event_count':0,'schema_version':46}; db.execute('INSERT INTO runtime_current VALUES(1,?,?,?,1)',(json.dumps(state),'state','tail')); db.commit(); db.close()
    pointer=root/'POINTER.json'; value={'schema_version':'r047-repaired-candidate-pointer-1','candidate_release_id':'TEST',
      'runtime':runtime.relative_to(ROOT).as_posix(),'release_manifest':release.relative_to(ROOT).as_posix(),'release_manifest_sha256':sha(release),
      'initialization_checkpoint':init.relative_to(ROOT).as_posix(),'initialization_checkpoint_sha256':sha(init),
      'scope':scope_path.relative_to(ROOT).as_posix(),'scope_sha256':sha(scope_path),'batch_id':scope['batch_id'],
      'checkpoint_root':checkpoints.relative_to(ROOT).as_posix()}
    pointer.write_text(json.dumps(value),encoding='utf-8'); return root,pointer,scope

def add_call(root,scope,idx,model='deepseek-v4-flash',status='RESPONSE_CAPTURED',turn_status='DISPLAYED',context=None):
    db=sqlite3.connect(root/'runtime/runtime.sqlite3'); sid='session_1'; tid=f'turn_{idx}'; cid=f'call_{idx}'
    db.execute('INSERT OR IGNORE INTO sessions VALUES(?)',(sid,))
    db.execute('INSERT INTO turns VALUES(?,?,?,?,?,?)',(tid,f'user {idx}',turn_status,'2026-09-12T00:30:00+00:00','RAW_USER_UTTERANCE_NOT_EVENT_PROOF','TARGET_PROVIDER_CAPTURE'))
    db.execute('INSERT INTO provider_calls VALUES(?,?,?,?,?,?,?,?,?,?)',(cid,tid,sid,scope['batch_id'],f'USER_{idx:02d}',model,status,None,json.dumps(context or {'retrieval':[]}),'2026-09-12T00:29:00+00:00'))
    db.commit(); db.close()

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if OUT.exists():
            import shutil; shutil.rmtree(OUT)
        OUT.mkdir(parents=True)
    def test_initialization_not_day(self):
        root,pointer,scope=setup_case('init'); result=n.evaluate(pointer,NOW); self.assertFalse(result['today_can_qualify'])
    def test_displayed_real_turn_qualifies(self):
        root,pointer,scope=setup_case('display'); db=sqlite3.connect(root/'runtime/runtime.sqlite3')
        from provider import digest; db.execute('INSERT INTO call_batches VALUES(?,?,0)',(scope['batch_id'],digest(scope))); db.commit(); db.close(); add_call(root,scope,1)
        self.assertTrue(n.evaluate(pointer,NOW)['today_can_qualify'])
    def test_duplicate_date_does_not_qualify_twice(self):
        root,pointer,scope=setup_case('duplicate'); from provider import digest
        db=sqlite3.connect(root/'runtime/runtime.sqlite3'); db.execute('INSERT INTO call_batches VALUES(?,?,0)',(scope['batch_id'],digest(scope))); db.commit(); db.close(); add_call(root,scope,1)
        cp=root/'checkpoints/2026-09-12'; cp.mkdir(parents=True); (cp/'CHECKPOINT.json').write_text(json.dumps({'qualified_observation_day':True,'observed_local_date':'2026-09-12'}),encoding='utf-8')
        result=n.evaluate(pointer,NOW); self.assertTrue(result['today_already_counted']); self.assertFalse(result['today_can_qualify'])
    def test_unknown_blocks_day(self):
        root,pointer,scope=setup_case('unknown'); from provider import digest
        db=sqlite3.connect(root/'runtime/runtime.sqlite3'); db.execute('INSERT INTO call_batches VALUES(?,?,1)',(scope['batch_id'],digest(scope))); db.commit(); db.close(); add_call(root,scope,1,status='SUBMITTED_STATUS_UNKNOWN',turn_status='SUBMITTED_STATUS_UNKNOWN')
        result=n.evaluate(pointer,NOW); self.assertFalse(result['today_can_qualify']); self.assertEqual(len(result['bad_or_unresolved_calls']),1)
    def test_switch_restart_and_commitment_retrieval_detected(self):
        root,pointer,scope=setup_case('longitudinal'); from provider import digest
        db=sqlite3.connect(root/'runtime/runtime.sqlite3'); db.execute('INSERT INTO call_batches VALUES(?,?,0)',(scope['batch_id'],digest(scope)))
        state={'commitments':{'c1':{'commitment_id':'c1','text':'约定','status':'OPEN'}},'event_count':1,'schema_version':46}; db.execute('UPDATE runtime_current SET state_json=?',(json.dumps(state),))
        db.executemany('INSERT INTO cli_process_runs VALUES(?,?,?,?,?)',[(100,'session_1','2026-09-11T00:00:00+00:00','2026-09-11T00:01:00+00:00',0),(200,'session_1','2026-09-12T00:00:00+00:00',None,None)]); db.commit(); db.close()
        add_call(root,scope,1,context={'retrieval':[]}); add_call(root,scope,9,model='deepseek-v4-pro',context={'retrieval':[{'record_kind':'COMMITMENT'}]})
        result=n.evaluate(pointer,NOW); self.assertTrue(result['same_session_model_switch_observed']); self.assertTrue(result['real_restart_observed']); self.assertTrue(result['commitment_retrieval_observed'])

def main():
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'tests':result.testsRun,'passed':result.wasSuccessful(),'target_calls':0}))
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__': raise SystemExit(main())
