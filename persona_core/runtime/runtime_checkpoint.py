from __future__ import annotations
import hashlib,json
from pathlib import Path
from runtime_core import PersonaRuntime

def sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def create_checkpoint(runtime_root:Path|str,output:Path|str)->dict:
    root=Path(runtime_root); rt=PersonaRuntime(root); snap=rt.snapshot(); out=Path(output)
    state_hashes={
        "self":sha(root/"SELF_STATE.json"),"affect":sha(root/"AFFECT_STATE.json"),
        "relationship":sha(root/"RELATIONSHIP_STATE.json"),"decision":sha(root/"DECISION_STATE.json")
    }
    cp={
        "schema_version":"pcore-runtime-checkpoint-1","genesis_id":snap["meta"]["genesis_id"],
        "genesis_sha256":snap["meta"]["genesis_sha256"],"ledger_event_count":len(snap["ledger"]),
        "last_event_sha256":snap["meta"]["last_event_sha256"],"next_sequence":snap["meta"]["next_sequence"],
        "state_hashes":state_hashes,"relationship_entity_count":len(snap["relationship"]["product_entities"]),
        "open_commitments":{eid:list(rec["unfinished_items"]) for eid,rec in snap["relationship"]["product_entities"].items() if rec["unfinished_items"]}
    }
    out.write_text(json.dumps(cp,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); return cp

