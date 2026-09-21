from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
PROJECT=ROOT.parent.parent
PCORE=PROJECT/"persona_core"
RUNTIME=PCORE/"runtime"

def sha(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def rd(path:Path): return json.loads(path.read_text(encoding="utf-8"))
def dump(path:Path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")

REPORTS={
    "behavior_final": PCORE/"rebaseline_20260907_r033"/"FINAL_SUITE_REPORT_R033.json",
    "freeze_manifest": PCORE/"rebaseline_20260907_r034"/"FREEZE_MANIFEST_R034.json",
    "genesis_install": PCORE/"rebaseline_20260907_r035"/"INSTALL_REPORT_R035.json",
    "cross_entity": PCORE/"rebaseline_20260907_r038"/"CROSS_ENTITY_REPORT_R038.json",
    "memory_final": PCORE/"rebaseline_20260907_r042"/"FINAL_MEMORY_RUNTIME_REPORT_R042.json",
}

def main():
    for p in REPORTS.values(): assert p.exists(),p
    behavior=rd(REPORTS["behavior_final"]); freeze=rd(REPORTS["freeze_manifest"]); install=rd(REPORTS["genesis_install"]); cross=rd(REPORTS["cross_entity"]); memory=rd(REPORTS["memory_final"])
    assert behavior["validation"]=="PASS" and behavior["all_original_rubrics_pass"] and behavior["boundary_clean"]
    assert behavior["full_character_route_repeat_sampling_complete"] and behavior["full_character_route_model_switch_complete"]
    assert freeze["persona_frozen"] and freeze["state_contracts_frozen"] and freeze["memory_admission_frozen"] and freeze["product_boundary_frozen"]
    assert install["status"]=="GENESIS_INSTALLED" and install["runtime_installed"]
    assert cross["validation"]=="PASS" and cross["cross_entity_history_false_denial_fixed"] and cross["relationship_transfer_still_forbidden"]
    assert memory["validation"]=="PASS" and memory["installed_memory_identity_suite_clean"] and memory["model_state_writes"]==0

    sys.path.insert(0,str(RUNTIME))
    from runtime_core import PersonaRuntime
    from runtime_checkpoint import create_checkpoint
    runtime=PersonaRuntime(RUNTIME); snap=runtime.snapshot()
    assert len(snap["ledger"])==1 and snap["ledger"][0]["event_type"]=="GENESIS_EVENT"
    checkpoint_path=RUNTIME/"CHECKPOINT_GENESIS_R043.json"
    cp=create_checkpoint(RUNTIME,checkpoint_path)
    genesis_path=RUNTIME/"genesis"/"GENESIS_SNAPSHOT_R035.json"
    genesis=rd(genesis_path)
    frozen_dir=RUNTIME/"genesis"/"frozen"
    frozen_hashes={p.name:sha(p) for p in sorted(frozen_dir.glob("*.json"))}
    runtime_code_hashes={p.name:sha(p) for p in sorted(RUNTIME.glob("*.py"))}
    meta=rd(RUNTIME/"RUNTIME_META.json")

    release={
        "schema_version":"pcore-operational-release-1",
        "release_id":"AMADEUS-PERSONA-CORE-R043",
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "status":"OPERATIONAL_PERSONA_CORE_COMPLETE",
        "genesis_id":genesis["genesis_id"],
        "genesis_sha256":sha(genesis_path),
        "source_snapshot_id":genesis["source_snapshot_id"],
        "known_source_cutoff_month":genesis["known_cutoff_month"],
        "exact_source_cutoff_day":genesis["exact_cutoff_day"],
        "installed_autobiographical_memory_ids":[x["id"] for x in genesis["encoded_autobiographical_memory"]],
        "claim_level_holds":genesis["claim_level_holds"],
        "frozen_component_hashes":frozen_hashes,
        "runtime_code_hashes":runtime_code_hashes,
        "runtime_integrity_schema":meta.get("runtime_integrity_schema"),
        "production_experience_ledger_events":len(snap["ledger"]),
        "production_product_relationship_entities":len(snap["relationship"]["product_entities"]),
        "checkpoint":{"path":str(checkpoint_path.relative_to(PROJECT)).replace("\\","/"),"sha256":sha(checkpoint_path),"last_event_sha256":cp["last_event_sha256"]},
        "acceptance_evidence":{
            "final_behavior_suite":{"path":str(REPORTS["behavior_final"].relative_to(PROJECT)).replace("\\","/"),"sha256":sha(REPORTS["behavior_final"]),"target_completions":behavior["target_completions"],"semantic_criteria":behavior["semantic_criteria"],"boundary_clean":behavior["boundary_clean"]},
            "freeze_manifest":{"path":str(REPORTS["freeze_manifest"].relative_to(PROJECT)).replace("\\","/"),"sha256":sha(REPORTS["freeze_manifest"])},
            "genesis_install":{"path":str(REPORTS["genesis_install"].relative_to(PROJECT)).replace("\\","/"),"sha256":sha(REPORTS["genesis_install"])},
            "runtime_cross_entity":{"path":str(REPORTS["cross_entity"].relative_to(PROJECT)).replace("\\","/"),"sha256":sha(REPORTS["cross_entity"])},
            "installed_memory_identity":{"path":str(REPORTS["memory_final"].relative_to(PROJECT)).replace("\\","/"),"sha256":sha(REPORTS["memory_final"])}
        },
        "operational_invariants":{
            "model_output_direct_state_write_allowed":False,
            "source_mutation_allowed":False,
            "runtime_experience_rewrites_genesis":False,
            "relationship_state_entity_scoped":True,
            "shared_interest_auto_trust":False,
            "body_capability_at_release":False,
            "external_tools_at_release":[],
            "physical_item_delivery_at_release":False
        },
        "known_unknowns_preserved":genesis["unknowns_and_conflicts"],
        "post_release_validation_pending":{
            "independent_blind_acceptance":True,
            "true_natural_day_longitudinal_runtime":True
        },
        "post_release_validation_note":"These are real-world longitudinal/independent validation activities, not missing construction components. They were not fabricated as completed in the current synchronous session.",
        "goal_complete_scope":"Persona Core construction, freeze, Genesis installation, deterministic runtime, restart/model-switch/integrity/memory-boundary validation are complete."
    }
    release_path=RUNTIME/"RUNTIME_RELEASE_R043.json"; dump(release_path,release)
    report={"status":"PASS","release_id":release["release_id"],"release_sha256":sha(release_path),"genesis_sha256":release["genesis_sha256"],"production_ledger_events":release["production_experience_ledger_events"],"persona_core_goal_complete":True,"post_release_validation_pending":release["post_release_validation_pending"]}
    dump(ROOT/"RELEASE_ACCEPTANCE_R043.json",report)
    print(json.dumps(report,ensure_ascii=True,indent=2))

if __name__=="__main__": main()
