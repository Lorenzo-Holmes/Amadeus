"""Isolated OFFLINE worker for genuine process death and SQLite concurrency.

No provider call, credential lookup or network access. The test harness starts
only this worker in a precreated project sandbox and records every process ID.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'persona_core/operational_runtime_v1'))
from transcript_store import TranscriptStore,ensure,utc_now
from admission import AdmissionController
from runtime_store import RuntimeStore

def write_record(path:Path,value:dict):
    path=path.resolve()
    ensure(path.is_relative_to(ROOT/'persona_core/operational_build_v1/evidence'),'Worker record outside evidence root')
    with path.open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2)
        f.write('\n'); f.flush(); os.fsync(f.fileno())

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--session',required=True)
    p.add_argument('--principal',required=True)
    p.add_argument('--decision',action='append',default=[])
    p.add_argument('--event-id')
    p.add_argument('--observe-turn')
    p.add_argument('--fault',default='NONE')
    p.add_argument('--record',type=Path,required=True)
    p.add_argument('--ready',type=Path)
    p.add_argument('--barrier',type=Path)
    args=p.parse_args()
    store=TranscriptStore(args.root)
    pid=os.getpid()
    try:
        handle=store.resume(args.principal,args.session)
        controller=AdmissionController(store)
        runtime=RuntimeStore(store,controller)
        if args.ready:
            write_record(args.ready,{'pid':pid,'at_utc':utc_now(),'state':'READY_BEFORE_BARRIER'})
        if args.barrier:
            ensure(args.barrier.resolve().is_relative_to(ROOT/'persona_core/operational_build_v1/evidence'),'Barrier outside evidence')
            deadline=time.monotonic()+20
            while not args.barrier.exists():
                ensure(time.monotonic()<deadline,'Offline test barrier timeout')
                time.sleep(0.01)
        def fault(point):
            if args.fault==point:
                write_record(args.record,{'pid':pid,'at_utc':utc_now(),'fault_point':point,
                    'action':'ACTUAL_OS_EXIT_77_WITHOUT_FINALLY','source':'AUTHORED_OFFLINE_FAULT_INJECTION'})
                os._exit(77)
        results=[]
        if args.observe_turn:
            fault('BEFORE_CANDIDATE')
            turn=store.get_turn(handle,args.observe_turn)
            payload={'turn_id':turn['turn_id'],'user_text':turn['user_text'],'assistant_text':turn['assistant_text'],
                'input_provenance':turn['input_provenance'],'response_provenance':turn['response_provenance'],'described_events_proven':False}
            token=controller._issue(handle,'UTTERANCE_OBSERVED',payload,[turn['turn_id']])
            cid=controller.propose(handle,'UTTERANCE_OBSERVED',payload,key=token.receipt_id,
                source_turn_ids=[turn['turn_id']],proposer_kind='HOST_OBSERVATION')
            fault('BEFORE_DECISION_WRITE')
            decision=controller.decide(handle,cid,token)
            results.append(runtime.commit(handle,decision,event_id=args.event_id,fault=fault))
        for did in args.decision:
            decision=controller.load_decision(handle,did)
            results.append(runtime.commit(handle,decision,event_id=args.event_id,fault=fault))
        write_record(args.record,{'pid':pid,'at_utc':utc_now(),'results':results,'fault_point':args.fault,
            'source':'AUTHORED_OFFLINE_WORKER','verification':runtime.verify()})
        print(json.dumps({'pid':pid,'results':results},ensure_ascii=True),flush=True)
    finally:
        store.close()

if __name__=='__main__':main()
