"""Single-database atomic event/state authority, deterministic replay and dedup.

Full state is compact JSON inside the SAME SQLite transaction as the immutable
ledger and derived index. It is not a return to uncoordinated JSON files.
"""
from __future__ import annotations
import json
import math
from copy import deepcopy
from datetime import datetime
from typing import Callable, Any
from admission import AdmissionController, AdmissionDecision
from context_router import _load_frozen
from legacy_import import inspect_legacy
from provider import canonical, digest
from transcript_store import TranscriptStore, SessionHandle, ensure, utc_now

SCHEMA_VERSION = 46
REDUCER_VERSION = 'runtime-reducer-46.1'

def initial_state(genesis_sha: str) -> dict:
    return {'schema_version':SCHEMA_VERSION,'genesis_sha256':genesis_sha,'event_count':0,
            'relationships':{},'affect':{},'commitments':{},'superseded':{}}

def relationship_template() -> dict:
    return {'familiarity':0.0,'trust':0.0,'respect':0.0,'safety':0.0,'observed_turn_count':0,
            'boundary_violations':0,'verified_completions':0,'interest_topics':[],
            'familiarity_day':None,'interest_familiarity_today':0.0,
            'permissions':[],'romantic_relationship':False}

def document_for_event(event:dict,state:dict) -> dict:
    """Derived material only; recomputable from the verified event stream."""
    payload,kind=event['payload'],event['event_type']
    text=payload.get('user_text',payload.get('text',payload.get('topic',payload.get('replacement',''))))
    scope='UTTERANCE_ONLY_NOT_DESCRIBED_EVENT_PROOF'
    if kind=='COMMITMENT_OPEN':
        scope='MUTUAL_TEXT_AGREEMENT_NOT_FULFILLMENT'
    elif kind=='COMMITMENT_FULFILLED':
        text=state['commitments'][payload['commitment_id']]['text']
        scope='VERIFIED_TEXT_SUBMISSION_ONLY'
    elif kind=='FACT_CORRECTED':
        scope='CORRECTED_USER_STATEMENT_NOT_EXTERNAL_TRUTH'
    return {'event_id':event['event_id'],'entity_id':event['entity_id'],'event_type':kind,
        'text_content':text,'provenance':'PRODUCT_RUNTIME' if event['mode']=='PRODUCT_RUNTIME' else 'SIMULATION_OR_AUDIT_ONLY',
        'admitted_scope':scope,'superseded_by':None,'sequence':event['sequence']}

def apply_event(state: dict, event: dict) -> dict:
    result = deepcopy(state)
    result['event_count'] += 1
    if event['mode'] != 'PRODUCT_RUNTIME':
        ensure(event['event_type']=='UTTERANCE_OBSERVED','Simulation/audit may not update runtime relationships')
        return result
    eid, kind, payload = event['entity_id'],event['event_type'],event['payload']
    rel = result['relationships'].setdefault(eid,relationship_template())
    now = datetime.fromisoformat(event['created_at_utc'])
    ensure(now.tzinfo is not None,'Timezone-aware event time required')
    affect = result['affect'].setdefault(eid,{'curiosity':0.0,'defensiveness':0.0,'valence':0.0,
        'last_at_utc':event['created_at_utc'],'last_event_id':None,'clock_rollback_clamped':False})
    elapsed = (now-datetime.fromisoformat(affect['last_at_utc'])).total_seconds()
    affect['clock_rollback_clamped'] = elapsed<0
    decay = math.exp(-min(max(elapsed,0.0),30*86400)/3600)
    for k in ('curiosity','defensiveness','valence'):
        affect[k] = round(affect[k]*decay,8)
    if elapsed>=0:
        affect['last_at_utc']=event['created_at_utc']
    affect['last_event_id']=event['event_id']
    if kind=='UTTERANCE_OBSERVED':
        rel['observed_turn_count'] += 1
    elif kind=='INTEREST_OBSERVED':
        topic=payload['topic']
        if topic not in rel['interest_topics']:
            rel['interest_topics'].append(topic)
            day=now.date().isoformat()
            if rel['familiarity_day']!=day:
                rel['familiarity_day'],rel['interest_familiarity_today']=day,0.0
            increment=min(0.1,max(0.0,0.2-rel['interest_familiarity_today']))
            rel['familiarity']=round(min(5.0,rel['familiarity']+increment),6)
            rel['interest_familiarity_today']=round(rel['interest_familiarity_today']+increment,6)
            affect['curiosity']=round(min(1.0,affect['curiosity']+0.1),8)
    elif kind=='COMMITMENT_OPEN':
        cid=payload['commitment_id']
        ensure(cid not in result['commitments'],'Commitment already exists')
        result['commitments'][cid]={**payload,'entity_id':eid,'opened_event_id':event['event_id'],
                                    'closed_event_id':None,'status':'OPEN'}
    elif kind=='COMMITMENT_FULFILLED':
        commitment=result['commitments'].get(payload['commitment_id'])
        ensure(commitment is not None and commitment['entity_id']==eid and commitment['status']=='OPEN','Open same-entity commitment required')
        ensure(payload['observed_text_sha256']==commitment['expected_text_sha256']
               and payload['verification_policy']==commitment['verification_policy'],'Completion proof does not match terms')
        commitment.update(status='FULFILLED',closed_event_id=event['event_id'],
                          completion_evidence_fingerprint=event['evidence_fingerprint'])
        rel['verified_completions']+=1
        rel['trust']=round(min(5.0,rel['trust']+0.25),6)
        rel['respect']=round(min(5.0,rel['respect']+0.25),6)
        rel['familiarity']=round(min(5.0,rel['familiarity']+0.1),6)
        affect['valence']=round(min(1.0,affect['valence']+0.1),8)
    elif kind=='BOUNDARY_VIOLATION':
        rel['boundary_violations']+=1
        rel['trust']=round(max(-5.0,rel['trust']-0.2),6)
        rel['safety']=round(max(-5.0,rel['safety']-0.2),6)
        affect['defensiveness']=round(min(1.0,affect['defensiveness']+0.2+min(0.05,abs(rel['safety'])*0.01)),8)
        affect['valence']=round(max(-1.0,affect['valence']-0.1),8)
    elif kind=='APOLOGY_OBSERVED':
        pass  # An apology utterance is not verified repair and never restores trust.
    elif kind=='FACT_CORRECTED':
        result['superseded'][payload['supersedes_event_id']]=event['event_id']
    else:
        ensure(False,'Unsupported reducer event')
    ensure(rel['permissions']==[] and rel['romantic_relationship'] is False,'Ordinary events cannot grant permissions or romance')
    return result

class RuntimeStore:
    def __init__(self, store: TranscriptStore, controller: AdmissionController, *, clock: Callable[[],str] | None=None):
        ensure(controller.store is store,'Controller and transaction store must share one database')
        self.store,self.controller=store,controller
        self.clock=clock or utc_now
        self.time_source='SIMULATED_TEST_CLOCK' if clock is not None else 'REAL_UTC_HOST_CLOCK'
        _load_frozen(store)
        version=store.db.execute('PRAGMA user_version').fetchone()[0]
        if version==46:
            row=store.db.execute("SELECT value FROM metadata WHERE key='operations_schema_version'").fetchone()
            ensure(row is not None and row[0]=='46','Missing operations migration metadata')
            tables={r[0] for r in store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            ensure({'runtime_current','runtime_events','state_versions','retrieval_documents','migration_history','legacy_import'}.issubset(tables),
                   'Unsupported/incomplete schema46 draft; restore its matching source or explicitly migrate a copy, never recreate missing authority tables')
        else:
            ensure(version==45,'Unsupported migration source')
            self._migrate_schema()
        controller.runtime=self
        self.verify()

    def _migrate_schema(self) -> None:
        legacy=inspect_legacy(self.store.root/'legacy_runtime',self.store.marker['source_genesis_sha256'])
        statements=[
            '''CREATE TABLE runtime_current(singleton INTEGER PRIMARY KEY CHECK(singleton=1),
               state_json TEXT NOT NULL,state_sha256 TEXT NOT NULL,next_sequence INTEGER NOT NULL,last_event_sha256 TEXT NOT NULL)''',
            '''CREATE TABLE runtime_events(sequence INTEGER PRIMARY KEY,event_id TEXT UNIQUE NOT NULL,
               entity_id TEXT NOT NULL REFERENCES entities(entity_id),event_type TEXT NOT NULL,
               decision_id TEXT UNIQUE NOT NULL REFERENCES admission_decisions(decision_id),
               semantic_key TEXT UNIQUE NOT NULL,event_json TEXT NOT NULL,event_sha256 TEXT NOT NULL)''',
            '''CREATE TABLE state_versions(sequence INTEGER PRIMARY KEY REFERENCES runtime_events(sequence),
               state_sha256 TEXT NOT NULL,policy_version TEXT NOT NULL)''',
            '''CREATE TABLE retrieval_documents(event_id TEXT PRIMARY KEY REFERENCES runtime_events(event_id),
               entity_id TEXT NOT NULL REFERENCES entities(entity_id),event_type TEXT NOT NULL,text_content TEXT NOT NULL,
               provenance TEXT NOT NULL,admitted_scope TEXT NOT NULL,superseded_by TEXT,sequence INTEGER NOT NULL)''',
            '''CREATE TABLE migration_history(migration_id TEXT PRIMARY KEY,from_version INTEGER NOT NULL,
               to_version INTEGER NOT NULL,at_utc TEXT NOT NULL,genesis_sha256 TEXT NOT NULL)''',
            '''CREATE TABLE legacy_import(singleton INTEGER PRIMARY KEY CHECK(singleton=1),
               report_json TEXT NOT NULL,report_sha256 TEXT NOT NULL)''',
            'CREATE INDEX retrieval_entity_sequence ON retrieval_documents(entity_id,sequence)',
            "CREATE TRIGGER runtime_events_no_update BEFORE UPDATE ON runtime_events BEGIN SELECT RAISE(ABORT,'runtime ledger is append-only'); END",
            "CREATE TRIGGER runtime_events_no_delete BEFORE DELETE ON runtime_events BEGIN SELECT RAISE(ABORT,'runtime ledger is append-only'); END",
        ]
        genesis=self.store.marker['source_genesis_sha256']
        state=initial_state(genesis)
        with self.store.transaction():
            for statement in statements:
                self.store.db.execute(statement)
            self.store.db.execute('INSERT INTO runtime_current VALUES(1,?,?,1,?)',(canonical(state).decode('utf-8'),digest(state),genesis))
            self.store.db.execute('INSERT INTO migration_history VALUES(?,?,?,?,?)',('TRANSCRIPT45_TO_OPERATIONS46',45,46,utc_now(),genesis))
            self.store.db.execute('INSERT INTO legacy_import VALUES(1,?,?)',(canonical(legacy).decode('utf-8'),digest(legacy)))
            self.store.db.execute("INSERT INTO metadata VALUES('operations_schema_version','46')")
            self.store.db.execute('PRAGMA user_version=46')

    def _current(self) -> tuple[dict,dict]:
        row=self.store.db.execute('SELECT * FROM runtime_current WHERE singleton=1').fetchone()
        ensure(row is not None,'Runtime state missing')
        state=json.loads(row['state_json'])
        ensure(digest(state)==row['state_sha256'],'Current state hash mismatch')
        ensure(state['genesis_sha256']==self.store.marker['source_genesis_sha256'],'Genesis identity mismatch')
        return state,dict(row)

    def snapshot(self, handle: SessionHandle) -> dict:
        self.store._authenticate(handle)
        state,_=self._current()
        return {'entity_id':handle.entity_id,'genesis_sha256':state['genesis_sha256'],
            'relationship':state['relationships'].get(handle.entity_id,relationship_template()),
            'affect':state['affect'].get(handle.entity_id,{}),
            'commitments':{k:v for k,v in state['commitments'].items() if v['entity_id']==handle.entity_id},
            'scope':'CURRENT_ENTITY_ONLY','parameters_are_engineering_not_source_psychology':True}

    def get_commitment(self, handle: SessionHandle, commitment_id: str) -> dict:
        record=self.snapshot(handle)['commitments'].get(commitment_id)
        ensure(record is not None,'Commitment unavailable for this entity')
        return record

    def get_event(self, handle: SessionHandle, event_id: str) -> dict:
        self.store._authenticate(handle)
        row=self.store.db.execute('SELECT event_json,event_sha256 FROM runtime_events WHERE event_id=? AND entity_id=?',
                                  (event_id,handle.entity_id)).fetchone()
        ensure(row is not None,'Event unavailable for this entity')
        value=json.loads(row[0])
        ensure(digest(value)==row[1],'Event hash mismatch')
        return value

    def _semantic_key(self, handle: SessionHandle, decision: AdmissionDecision) -> str:
        payload=json.loads(decision.payload_json)
        if decision.effect_kind=='INTEREST_OBSERVED':
            return digest(['INTEREST',handle.entity_id,payload['topic']])
        if decision.effect_kind=='COMMITMENT_OPEN':
            return digest(['COMMITMENT_OPEN',handle.entity_id,payload['commitment_id']])
        return digest([decision.effect_kind,handle.entity_id,decision.evidence_fingerprint])

    def _index_event(self, event: dict) -> None:
        state,_=self._current()
        document=document_for_event(event,state)
        p=event['payload']
        if event['event_type']=='FACT_CORRECTED':
            old=self.store.db.execute('SELECT entity_id,superseded_by FROM retrieval_documents WHERE event_id=?',(p['supersedes_event_id'],)).fetchone()
            ensure(old is not None and old['entity_id']==event['entity_id'],'Correction target outside entity scope')
            ensure(old['superseded_by'] is None,'Old statement already corrected; correct its latest version')
            self.store.db.execute('UPDATE retrieval_documents SET superseded_by=? WHERE event_id=?',(event['event_id'],p['supersedes_event_id']))
        self.store.db.execute('INSERT INTO retrieval_documents VALUES(?,?,?,?,?,?,NULL,?)',
            (document['event_id'],document['entity_id'],document['event_type'],document['text_content'],
             document['provenance'],document['admitted_scope'],document['sequence']))

    def commit(self, handle: SessionHandle, decision: AdmissionDecision, *, event_id: str | None=None,
               fault: Callable[[str],None] | None=None) -> dict:
        self.controller.validate_decision(handle,decision)
        ensure(handle.mode=='PRODUCT_RUNTIME' or decision.effect_kind=='UTTERANCE_OBSERVED','Non-runtime mode cannot update personal state')
        event_id=event_id or 'event_'+digest(decision.decision_id)
        ensure(isinstance(event_id,str) and 0<len(event_id)<=200,'Invalid event id')
        trigger=fault or (lambda point:None)
        key=self._semantic_key(handle,decision)
        trigger('BEFORE_TRANSACTION')
        with self.store.transaction():
            self.controller.validate_decision(handle,decision)
            trigger('AFTER_BEGIN')
            same_id=self.store.db.execute('SELECT * FROM runtime_events WHERE event_id=?',(event_id,)).fetchone()
            if same_id:
                ensure(same_id['decision_id']==decision.decision_id,'Event id collision with different decision')
                return {'event_id':event_id,'sequence':same_id['sequence'],'idempotent':True,'semantic_duplicate':False}
            existing=self.store.db.execute('SELECT * FROM runtime_events WHERE semantic_key=?',(key,)).fetchone()
            if existing:
                return {'event_id':existing['event_id'],'sequence':existing['sequence'],'idempotent':True,'semantic_duplicate':True}
            state,current=self._current()
            row=self.store.db.execute('SELECT candidate_id FROM admission_decisions WHERE decision_id=?',(decision.decision_id,)).fetchone()
            event={'sequence':current['next_sequence'],'event_id':event_id,'entity_id':handle.entity_id,
                'session_id':handle.session_id,'mode':handle.mode,'event_type':decision.effect_kind,
                'candidate_id':row[0],'decision_id':decision.decision_id,'payload':json.loads(decision.payload_json),
                'evidence_fingerprint':decision.evidence_fingerprint,'previous_event_sha256':current['last_event_sha256'],
                'policy_version':REDUCER_VERSION,'created_at_utc':self.clock(),'time_source':self.time_source}
            event_hash=digest(event)
            self.store.db.execute('INSERT INTO runtime_events VALUES(?,?,?,?,?,?,?,?)',
                (event['sequence'],event_id,handle.entity_id,decision.effect_kind,decision.decision_id,key,canonical(event).decode('utf-8'),event_hash))
            trigger('AFTER_EVENT_INSERT')
            updated=apply_event(state,event)
            self.store.db.execute('UPDATE runtime_current SET state_json=?,state_sha256=?,next_sequence=?,last_event_sha256=? WHERE singleton=1',
                (canonical(updated).decode('utf-8'),digest(updated),event['sequence']+1,event_hash))
            trigger('AFTER_STATE_WRITE')
            self._index_event(event)
            trigger('AFTER_INDEX_WRITE')
            self.store.db.execute('INSERT INTO state_versions VALUES(?,?,?)',(event['sequence'],digest(updated),REDUCER_VERSION))
            trigger('BEFORE_COMMIT')
        trigger('AFTER_COMMIT_BEFORE_RETURN')
        return {'event_id':event_id,'sequence':event['sequence'],'event_sha256':event_hash,'idempotent':False,'semantic_duplicate':False}

    def verify(self, *, check_index:bool=True) -> dict[str,Any]:
        ensure(self.store.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','SQLite integrity check failed')
        ensure(not self.store.db.execute('PRAGMA foreign_key_check').fetchall(),'Foreign-key check failed')
        # One read transaction observes a consistent ledger/state version even
        # while another process is committing under WAL.
        self.store.db.execute('BEGIN')
        try:
            legacy=self.store.db.execute('SELECT report_json,report_sha256 FROM legacy_import WHERE singleton=1').fetchone()
            ensure(legacy is not None and digest(json.loads(legacy[0]))==legacy[1],'Legacy import binding missing or changed')
            current_legacy=inspect_legacy(self.store.root/'legacy_runtime',self.store.marker['source_genesis_sha256'])
            ensure(digest(current_legacy)==legacy[1],'Legacy migration input changed after import')
            state,current=self._current()
            expected=initial_state(self.store.marker['source_genesis_sha256'])
            previous=expected['genesis_sha256']
            expected_documents={}
            rows=self.store.db.execute('SELECT * FROM runtime_events ORDER BY sequence').fetchall()
            for number,row in enumerate(rows,1):
                event=json.loads(row['event_json'])
                ensure(row['sequence']==number==event['sequence'],'Non-contiguous event sequence')
                ensure(event['previous_event_sha256']==previous and digest(event)==row['event_sha256'],'Event chain mismatch')
                ensure(event['event_id']==row['event_id'] and event['entity_id']==row['entity_id']
                       and event['decision_id']==row['decision_id'] and event['event_type']==row['event_type'],'Event column binding mismatch')
                session=self.store.db.execute('SELECT principal_id FROM sessions WHERE session_id=?',(event['session_id'],)).fetchone()
                ensure(session is not None,'Event session missing')
                handle=self.store.resume(session[0],event['session_id'])
                decision=self.controller.load_decision(handle,event['decision_id'])
                ensure(decision.verdict=='ADMIT' and decision.effect_kind==event['event_type']
                       and json.loads(decision.payload_json)==event['payload']
                       and decision.evidence_fingerprint==event['evidence_fingerprint'],'Event/decision authority binding mismatch')
                self.controller.validate_persisted_evidence(handle,decision)
                expected=apply_event(expected,event)
                if event['event_type']=='FACT_CORRECTED':
                    old=expected_documents.get(event['payload']['supersedes_event_id'])
                    ensure(old is not None and old['entity_id']==event['entity_id'] and old['superseded_by'] is None,'Correction replay target mismatch')
                    old['superseded_by']=event['event_id']
                expected_documents[event['event_id']]=document_for_event(event,expected)
                version=self.store.db.execute('SELECT state_sha256,policy_version FROM state_versions WHERE sequence=?',(number,)).fetchone()
                ensure(version is not None and version[0]==digest(expected) and version[1]==REDUCER_VERSION,'State-version replay mismatch')
                previous=row['event_sha256']
            ensure(expected==state and current['next_sequence']==len(rows)+1 and current['last_event_sha256']==previous,'Runtime state/ledger replay mismatch')
            if check_index:
                actual_documents={r['event_id']:dict(r) for r in self.store.db.execute('SELECT * FROM retrieval_documents')}
                ensure(actual_documents==expected_documents,'Derived index content/provenance/supersession mismatch')
            return {'schema_version':SCHEMA_VERSION,'events':len(rows),'tail_sha256':previous,'state_sha256':digest(state),
                    'genesis_sha256':state['genesis_sha256'],'integrity':'ok','replay_equal':True,
                    'threat_limit':'Does not defend against an OS owner rewriting all bytes and trusted references.'}
        finally:
            self.store.db.execute('ROLLBACK')

    def rebuild_index(self) -> dict:
        """Explicit derived-index repair, never ledger/state hash laundering."""
        self.verify(check_index=False)
        with self.store.transaction():
            # The write lock freezes the stream while rebuilding derived data.
            state=initial_state(self.store.marker['source_genesis_sha256'])
            documents={}
            for row in self.store.db.execute('SELECT event_json,event_sha256 FROM runtime_events ORDER BY sequence'):
                event=json.loads(row[0]); ensure(digest(event)==row[1],'Event changed before index rebuild')
                state=apply_event(state,event)
                if event['event_type']=='FACT_CORRECTED':
                    documents[event['payload']['supersedes_event_id']]['superseded_by']=event['event_id']
                documents[event['event_id']]=document_for_event(event,state)
            self.store.db.execute('DELETE FROM retrieval_documents')
            for d in documents.values():
                self.store.db.execute('INSERT INTO retrieval_documents VALUES(?,?,?,?,?,?,?,?)',
                    tuple(d[k] for k in ['event_id','entity_id','event_type','text_content','provenance','admitted_scope','superseded_by','sequence']))
        return {'repaired_component':'DERIVED_INDEX_ONLY','verified':self.verify(),'authority_history_modified':False}
