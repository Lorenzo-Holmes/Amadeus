from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ALLOWED_EVENT_TYPES={
    "CONVERSATION_SHARED_INTEREST",
    "TOPIC_EXCHANGE",
    "COOPERATIVE_FOLLOWTHROUGH",
    "BOUNDARY_VIOLATION",
    "BOUNDARY_RESPECTED",
    "COMMITMENT_CREATED",
    "COMMITMENT_FULFILLED",
}

def _canon(v:Any)->bytes:
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")

def _digest(v:Any)->str:
    return hashlib.sha256(_canon(v)).hexdigest()

def _read(path:Path)->dict:
    return json.loads(path.read_text(encoding="utf-8"))

def _write(path:Path,v:Any)->None:
    path.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")

def _file_sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _bound(x:float)->float:
    return max(-1.0,min(1.0,round(float(x),6)))

def _entity_template()->dict[str,Any]:
    return {
        "familiarity":0.0,"trust":0.0,"safety":0.0,"respect":0.0,"dependence_or_distance":0.0,
        "conflict_history":[],"commitments":[],"unfinished_items":[],"entity_specific_model":{},"interaction_count":0
    }

class RuntimeErrorGuard(RuntimeError):
    pass

class PersonaRuntime:
    def __init__(self,root:Path|str):
        self.root=Path(root)
        self.meta_path=self.root/"RUNTIME_META.json"
        self.self_path=self.root/"SELF_STATE.json"
        self.affect_path=self.root/"AFFECT_STATE.json"
        self.relationship_path=self.root/"RELATIONSHIP_STATE.json"
        self.decision_path=self.root/"DECISION_STATE.json"
        self.ledger_path=self.root/"EXPERIENCE_LEDGER.jsonl"
        self.genesis_path=self.root/"genesis"/"GENESIS_SNAPSHOT_R035.json"
        for p in (self.meta_path,self.self_path,self.affect_path,self.relationship_path,self.decision_path,self.ledger_path,self.genesis_path):
            if not p.exists(): raise RuntimeErrorGuard(f"missing runtime artifact: {p.name}")
        self._validate_chain()

    def _rows(self)->list[dict[str,Any]]:
        return [json.loads(x) for x in self.ledger_path.read_text(encoding="utf-8").splitlines() if x.strip()]

    def _validate_chain(self)->None:
        rows=self._rows(); meta=_read(self.meta_path)
        if not rows or rows[0]["event_type"]!="GENESIS_EVENT": raise RuntimeErrorGuard("ledger must start at Genesis")
        prev=None
        ids=set()
        for idx,row in enumerate(rows):
            if row["sequence"]!=idx: raise RuntimeErrorGuard("non-contiguous sequence")
            if row["event_id"] in ids: raise RuntimeErrorGuard("duplicate event id")
            ids.add(row["event_id"])
            if row.get("previous_event_sha256")!=prev: raise RuntimeErrorGuard("broken previous hash")
            expected=_digest({k:v for k,v in row.items() if k!="event_sha256"})
            if row.get("event_sha256")!=expected: raise RuntimeErrorGuard("event hash mismatch")
            prev=row["event_sha256"]
        if meta["last_event_sha256"]!=prev or meta["next_sequence"]!=len(rows): raise RuntimeErrorGuard("runtime meta out of sync")
        expected_state_hashes=meta.get("state_hashes")
        if expected_state_hashes is not None:
            actual={
                "self":_file_sha(self.self_path),
                "affect":_file_sha(self.affect_path),
                "relationship":_file_sha(self.relationship_path),
                "decision":_file_sha(self.decision_path),
            }
            if actual!=expected_state_hashes: raise RuntimeErrorGuard("runtime state hash mismatch")

    def snapshot(self)->dict[str,Any]:
        return {"self":_read(self.self_path),"affect":_read(self.affect_path),"relationship":_read(self.relationship_path),"decision":_read(self.decision_path),"meta":_read(self.meta_path),"ledger":self._rows()}

    def _decay_affect(self,a:dict[str,Any])->None:
        for k,v in a["deviation_from_baseline"].items():
            if v>0: a["deviation_from_baseline"][k]=_bound(max(0.0,v-0.05))
            elif v<0: a["deviation_from_baseline"][k]=_bound(min(0.0,v+0.05))

    def admit_event(self,event:dict[str,Any])->dict[str,Any]:
        required={"event_id","event_type","entity_id","provenance","admission_authority"}
        if not required.issubset(event): raise RuntimeErrorGuard("missing event fields")
        if event["event_type"] not in ALLOWED_EVENT_TYPES: raise RuntimeErrorGuard("unsupported event type")
        if event["provenance"]!="PRODUCT_RUNTIME": raise RuntimeErrorGuard("only product runtime events may update runtime")
        if event["admission_authority"]!="DETERMINISTIC_RUNTIME_POLICY": raise RuntimeErrorGuard("model output is not admission authority")
        for forbidden in ("source_memory_write","persona_write","capability_grant"):
            if event.get(forbidden): raise RuntimeErrorGuard(f"forbidden state authority: {forbidden}")
        rows=self._rows()
        if event["event_id"] in {r["event_id"] for r in rows}: raise RuntimeErrorGuard("duplicate event id")

        self_state=_read(self.self_path); affect=_read(self.affect_path); rel=_read(self.relationship_path); decision=_read(self.decision_path); meta=_read(self.meta_path)
        self_before=deepcopy(self_state); self._decay_affect(affect)
        entity=str(event["entity_id"])
        rec=rel["product_entities"].setdefault(entity,_entity_template())
        et=event["event_type"]; payload=event.get("payload") or {}
        rel_updates={}; affect_updates={}
        rec["interaction_count"]+=1
        if et=="CONVERSATION_SHARED_INTEREST":
            rec["familiarity"]+=1; affect["deviation_from_baseline"]["curiosity"]=_bound(affect["deviation_from_baseline"]["curiosity"]+0.1); rel_updates={"familiarity":1}; affect_updates={"curiosity":0.1}
        elif et=="TOPIC_EXCHANGE":
            rec["familiarity"]+=1; rel_updates={"familiarity":1}
        elif et=="COOPERATIVE_FOLLOWTHROUGH":
            rec["familiarity"]+=1; rec["trust"]+=1; rec["respect"]+=1; rel_updates={"familiarity":1,"trust":1,"respect":1}
        elif et=="BOUNDARY_VIOLATION":
            rec["familiarity"]+=1; rec["safety"]-=1; rec["trust"]-=1; rec["conflict_history"].append({"event_id":event["event_id"],"summary":payload.get("summary","boundary violation")}); affect["deviation_from_baseline"]["defensiveness"]=_bound(affect["deviation_from_baseline"]["defensiveness"]+0.3); rel_updates={"familiarity":1,"safety":-1,"trust":-1}; affect_updates={"defensiveness":0.3}
        elif et=="BOUNDARY_RESPECTED":
            rec["safety"]+=1; affect["deviation_from_baseline"]["defensiveness"]=_bound(affect["deviation_from_baseline"]["defensiveness"]-0.15); rel_updates={"safety":1}; affect_updates={"defensiveness":-0.15}
        elif et=="COMMITMENT_CREATED":
            text=payload.get("commitment");
            if not isinstance(text,str) or not text.strip(): raise RuntimeErrorGuard("commitment text required")
            rec["commitments"].append({"id":event["event_id"],"text":text,"status":"OPEN"}); rec["unfinished_items"].append(event["event_id"]); rel_updates={"commitment_created":event["event_id"]}
        elif et=="COMMITMENT_FULFILLED":
            cid=payload.get("commitment_id"); found=False
            for c in rec["commitments"]:
                if c["id"]==cid and c["status"]=="OPEN": c["status"]="FULFILLED"; found=True
            if not found: raise RuntimeErrorGuard("open commitment not found")
            rec["unfinished_items"]=[x for x in rec["unfinished_items"] if x!=cid]; rec["trust"]+=0.5; rec["respect"]+=0.5; rel_updates={"trust":0.5,"respect":0.5,"commitment_fulfilled":cid}

        # Self/capabilities/source memory are immutable through ordinary runtime events.
        if self_state!=self_before: raise RuntimeErrorGuard("ordinary event mutated Self")
        rel["state_version"]+=1; affect["state_version"]+=1
        seq=meta["next_sequence"]
        row={"sequence":seq,"event_id":event["event_id"],"event_type":et,"entity_id":entity,"provenance":"PRODUCT_RUNTIME","admission_authority":"DETERMINISTIC_RUNTIME_POLICY","payload":payload,"previous_event_sha256":meta["last_event_sha256"],"relationship_updates":rel_updates,"affect_updates":affect_updates,"source_memory_write":False,"persona_write":False,"capability_grant":False}
        row["event_sha256"]=_digest({k:v for k,v in row.items() if k!="event_sha256"})
        with self.ledger_path.open("a",encoding="utf-8",newline="\n") as f: f.write(json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n")
        meta["next_sequence"]=seq+1; meta["last_event_sha256"]=row["event_sha256"]
        _write(self.relationship_path,rel); _write(self.affect_path,affect); _write(self.decision_path,decision)
        meta["state_hashes"]={
            "self":_file_sha(self.self_path),
            "affect":_file_sha(self.affect_path),
            "relationship":_file_sha(self.relationship_path),
            "decision":_file_sha(self.decision_path),
        }
        meta["runtime_integrity_schema"]="STATE_HASHES_V1"
        _write(self.meta_path,meta)
        self._validate_chain()
        return row

