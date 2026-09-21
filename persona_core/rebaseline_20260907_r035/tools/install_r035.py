from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
PROJECT=ROOT.parent.parent
FREEZE=ROOT.parent/"rebaseline_20260907_r034"
RUNTIME=PROJECT/"persona_core"/"runtime"

def sha(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path:Path,v): path.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")

def main():
    manifest=json.loads((FREEZE/"FREEZE_MANIFEST_R034.json").read_text(encoding="utf-8"))
    assert manifest["persona_frozen"] and manifest["state_contracts_frozen"] and manifest["memory_admission_frozen"] and manifest["product_boundary_frozen"]
    for rec in manifest["files"]:
        src=PROJECT/rec["path"]
        assert src.exists() and sha(src)==rec["sha256"]
    assert not RUNTIME.exists(), "runtime already exists; refusing destructive reinstall"
    (RUNTIME/"genesis"/"frozen").mkdir(parents=True)
    copied=[]
    for rec in manifest["files"]:
        src=PROJECT/rec["path"]
        dst=RUNTIME/"genesis"/"frozen"/src.name
        shutil.copy2(src,dst)
        assert sha(dst)==rec["sha256"]
        copied.append({"path":str(dst.relative_to(PROJECT)).replace("\\","/"),"sha256":rec["sha256"]})

    memory=json.loads((FREEZE/"MEMORY_ADMISSION_FROZEN_R034.json").read_text(encoding="utf-8"))
    rc=next(x for x in memory["decision_records"] if x["id"]=="RC-R005-001")
    assert rc["decision"]=="ADMIT_AT_GENESIS"
    source=json.loads((FREEZE/"SOURCE_IDENTITY_FROZEN_R034.json").read_text(encoding="utf-8"))
    now=datetime.now(timezone.utc).isoformat()
    genesis={
      "schema_version":"pcore-genesis-snapshot-1","genesis_id":"AMADEUS-KURISU-GENESIS-R035","status":"GENESIS_FROZEN_AND_INSTALLED","installed_at_utc":now,
      "source_snapshot_id":source["source_snapshot_id"],"known_cutoff_month":source["known_cutoff_month"],"exact_cutoff_day":source["exact_cutoff_day"],
      "frozen_components":copied,
      "encoded_autobiographical_memory":[{"id":"RC-R005-001","kind":rc["kind"],"supporting_events":rc["supporting_events"],"scope":rc["safe_first_person_scope_candidate"],"limits":rc["limits"]}],
      "source_relationship_roots":{"Maho":{"kind":"SOURCE_RELATIONSHIP_ROOT","runtime_user_relationship":False},"Leskinen":{"kind":"SOURCE_RELATIONSHIP_ROOT","runtime_user_relationship":False}},
      "source_fact_only_not_first_person_memory":memory["source_fact_only_not_first_person_memory"],
      "claim_level_holds":memory["claim_level_holds"],
      "unknowns_and_conflicts":source["unknowns_and_conflicts"],
      "product_relationships_at_genesis":{},"product_experience_count_at_genesis":0,
      "genesis_approved":True,"runtime_installed":True
    }
    gpath=RUNTIME/"genesis"/"GENESIS_SNAPSHOT_R035.json"; dump(gpath,genesis); gsha=sha(gpath)
    self_state={"schema_version":"pcore-self-state-1","genesis_id":genesis["genesis_id"],"identity_continuity":"PRODUCT_RUNTIME_INSTANCE","source_person_identity":"Makise Kurisu","autobiographical_memory_ids":["RC-R005-001"],"capabilities":{"text_response":True,"body":False,"external_tools":[],"environment_control":False,"physical_item_delivery":False},"ontology_status":"UNKNOWN_NOT_SELF_DECLARED","future_orientation":[],"state_version":0}
    affect_state={"schema_version":"pcore-affect-state-1","genesis_id":genesis["genesis_id"],"deviation_from_baseline":{"valence":0.0,"arousal":0.0,"defensiveness":0.0,"curiosity":0.0,"embarrassment":0.0,"concern_for_other":0.0},"state_version":0}
    relationship_state={"schema_version":"pcore-relationship-state-1","genesis_id":genesis["genesis_id"],"product_entities":{},"source_relationship_roots":genesis["source_relationship_roots"],"state_version":0}
    decision_state={"schema_version":"pcore-decision-state-1","genesis_id":genesis["genesis_id"],"current_goals":[],"pending_commitments":[],"state_version":0}
    dump(RUNTIME/"SELF_STATE.json",self_state); dump(RUNTIME/"AFFECT_STATE.json",affect_state); dump(RUNTIME/"RELATIONSHIP_STATE.json",relationship_state); dump(RUNTIME/"DECISION_STATE.json",decision_state)
    event={"sequence":0,"event_id":"GENESIS_EVENT_R035","event_type":"GENESIS_EVENT","occurred_at_utc":now,"genesis_id":genesis["genesis_id"],"genesis_sha256":gsha,"previous_event_sha256":None,"source_memory_write":False,"persona_write":False,"relationship_updates":{},"affect_updates":{},"note":"Runtime boundary event. Source history is not rewritten."}
    event["event_sha256"]=hashlib.sha256(json.dumps({k:v for k,v in event.items() if k!="event_sha256"},ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
    (RUNTIME/"EXPERIENCE_LEDGER.jsonl").write_text(json.dumps(event,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8")
    meta={"schema_version":"pcore-runtime-meta-1","genesis_id":genesis["genesis_id"],"genesis_sha256":gsha,"runtime_installed":True,"next_sequence":1,"last_event_sha256":event["event_sha256"],"model_output_direct_state_write_allowed":False,"source_mutation_allowed":False,"persona_mutation_requires_governed_proposal":True,"created_at_utc":now}
    dump(RUNTIME/"RUNTIME_META.json",meta)
    lock={"schema_version":"pcore-install-lock-1","genesis_id":genesis["genesis_id"],"genesis_sha256":gsha,"r034_manifest_sha256":sha(FREEZE/"FREEZE_MANIFEST_R034.json"),"installed_at_utc":now,"reinstall_policy":"FORBIDDEN_WITHOUT_EXPLICIT_MIGRATION_OR_NEW_GENESIS_REVISION"}
    dump(RUNTIME/"INSTALL_LOCK.json",lock)
    report={"schema_version":"pcore-r035-install-report-1","status":"GENESIS_INSTALLED","genesis_id":genesis["genesis_id"],"genesis_sha256":gsha,"copied_frozen_components":len(copied),"installed_autobiographical_memory_ids":["RC-R005-001"],"product_relationships":0,"experience_ledger_events":1,"runtime_installed":True}
    dump(ROOT/"INSTALL_REPORT_R035.json",report)
    print(json.dumps(report,ensure_ascii=True,indent=2))

if __name__=="__main__": main()
