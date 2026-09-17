"""Offline 100k-turn/100k-retrieval-row SQLite stress on disposable sandbox."""
from __future__ import annotations
import hashlib,json,shutil,sqlite3,sys,time
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]; PLAN=ROOT/'persona_core/operational_build_v1'; CODE=ROOT/'persona_core/operational_runtime_v1'; sys.path.insert(0,str(CODE))
from transcript_store import TranscriptStore
from recovery import restore_backup

def sanitized_backup(source:Path,destination:Path):
    manifest=json.loads((source/'BACKUP_MANIFEST.json').read_text(encoding='utf-8')); destination.mkdir(parents=True,exist_ok=False)
    shutil.copy2(source/'BACKUP_MANIFEST.json',destination/'BACKUP_MANIFEST.json')
    for item in manifest['files']:
        src=source/item['path']; dst=destination/item['path']; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    return destination

def run(output:Path,turn_count=100_000,retrieval_count=10_000):
    pointer=json.loads((PLAN/'evidence/R047-04/repaired_natural_day/CURRENT_CANDIDATE.json').read_text(encoding='utf-8'))
    candidate=ROOT/pointer['candidate_dir']; release=json.loads((candidate/'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
    clean=sanitized_backup(candidate/'CLEAN_BACKUP',output/'sanitized_backup')
    scratch=output/'scratch'; restore_backup(clean,scratch,release['clean_backup']['manifest_sha256'])
    store=TranscriptStore(scratch); handle=store.open_session('STRESS_PRINCIPAL','STRESS_ENTITY')
    started=time.perf_counter(); now='2026-09-12T00:00:00+00:00'
    rows=((f'turn_stress_{i}',handle.session_id,f'key_{i}',f'user {i}',f'assistant {i}',now,now,now,'DISPLAYED','AUTHORED_STRESS_FIXTURE','AUTHORED_TEST_STUB',f'request_{i}') for i in range(turn_count))
    with store.transaction():
        store.db.executemany('''INSERT INTO turns(turn_id,session_id,idempotency_key,user_text,assistant_text,created_at_utc,response_at_utc,display_at_utc,status,input_provenance,response_provenance,request_id)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',rows)
        candidates=[]; decisions=[]; events=[]; docs=[]
        for i in range(retrieval_count):
            cid=f'candidate_stress_{i}'; did=f'decision_stress_{i}'; eid=f'event_stress_{i}'; payload=json.dumps({'text':f'synthetic retrieval document {i}'},separators=(',',':'))
            candidates.append((cid,handle.session_id,handle.entity_id,handle.entity_id,'STRESS_FIXTURE',payload,'HOST','[]','[]',hashlib.sha256(cid.encode()).hexdigest(),now))
            decisions.append((did,cid,handle.entity_id,'ADMIT','UTTERANCE_OBSERVED',payload,None,'AUTHORED_STRESS_FIXTURE','stress-policy','[]',hashlib.sha256(did.encode()).hexdigest(),now))
            event_json=json.dumps({'event_id':eid,'payload':payload},separators=(',',':'))
            events.append((i+1,eid,handle.entity_id,'UTTERANCE_OBSERVED',did,f'stress:{i}',event_json,hashlib.sha256(event_json.encode()).hexdigest()))
            docs.append((eid,handle.entity_id,'UTTERANCE_OBSERVED',f'synthetic retrieval document {i}','AUTHORED_STRESS_FIXTURE','STRESS_ONLY',None,i+1))
        store.db.executemany('INSERT INTO event_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?)',candidates)
        store.db.executemany('INSERT INTO admission_decisions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',decisions)
        store.db.executemany('INSERT INTO runtime_events VALUES(?,?,?,?,?,?,?,?)',events)
        store.db.executemany('INSERT INTO retrieval_documents VALUES(?,?,?,?,?,?,?,?)',docs)
    insert_seconds=time.perf_counter()-started
    q0=time.perf_counter(); recent=store.recent(handle,100); recent_ms=(time.perf_counter()-q0)*1000
    q1=time.perf_counter(); tail=store.db.execute('SELECT text_content FROM retrieval_documents WHERE entity_id=? ORDER BY sequence DESC LIMIT 100',(handle.entity_id,)).fetchall(); retrieval_ms=(time.perf_counter()-q1)*1000
    size=(scratch/'runtime.sqlite3').stat().st_size
    backup=output/'stress_backup.sqlite3'; b0=time.perf_counter(); target=sqlite3.connect(backup)
    try: store.db.backup(target)
    finally: target.close()
    backup_seconds=time.perf_counter()-b0; store.close()
    result={'schema_version':'r047-long-run-storage-stress-1','turn_rows':turn_count,'retrieval_rows':retrieval_count,'insert_seconds':insert_seconds,
      'recent_100_latency_ms':recent_ms,'retrieval_tail_100_latency_ms':retrieval_ms,'runtime_sqlite_bytes':size,'online_backup_seconds':backup_seconds,
      'recent_count':len(recent),'retrieval_tail_count':len(tail),'provider_calls':0,'target_calls':0,'synthetic_fixture_only':True,
      'pass':len(recent)==100 and len(tail)==100 and recent_ms<1000 and retrieval_ms<1000}
    (output/'LONG_RUN_STORAGE_STRESS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    shutil.rmtree(scratch); backup.unlink(); shutil.rmtree(clean); result['bulk_scratch_deleted_after_measurement']=True
    return result

def main():
    out=PLAN/'evidence/R047-04'/('long_run_storage_stress_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')); out.mkdir(parents=True,exist_ok=False); r=run(out)
    print(json.dumps({'output':out.relative_to(ROOT).as_posix(),'pass':r['pass'],'turn_rows':r['turn_rows'],'retrieval_rows':r['retrieval_rows'],'recent_ms':r['recent_100_latency_ms'],'retrieval_ms':r['retrieval_tail_100_latency_ms']},ensure_ascii=False)); return 0 if r['pass'] else 2
if __name__=='__main__': raise SystemExit(main())
