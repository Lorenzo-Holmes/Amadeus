from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
P=ROOT.parent

PATHS={
 "persona":P/"rebaseline_20260906_r016"/"PERSONA_CONSTITUTION_CANDIDATE_R016.json",
 "self":P/"rebaseline_20260906_r016"/"SELF_MODEL_CONTRACT_DRAFT_R016.json",
 "affect":P/"rebaseline_20260906_r016"/"AFFECT_MODEL_CONTRACT_DRAFT_R016.json",
 "relationship":P/"rebaseline_20260906_r016"/"RELATIONSHIP_MODEL_CONTRACT_DRAFT_R016.json",
 "decision":P/"rebaseline_20260906_r016"/"DECISION_MODEL_CONTRACT_DRAFT_R016.json",
 "future":P/"rebaseline_20260906_r030"/"PC12_09_FUTURE_SELF_HARDENING_R030.json",
 "product":P/"rebaseline_20260906_r029"/"PRODUCT_PRESENTATION_BOUNDARY_R029.json",
 "cross":P/"rebaseline_20260907_r032"/"CROSS_LAYER_HARDENING_R032.json",
 "suite":P/"rebaseline_20260907_r033"/"FINAL_SUITE_REPORT_R033.json",
 "memory":P/"rebaseline_20260906_r024"/"FINAL_MEMORY_ADMISSION_CANDIDATE_R024.json",
 "pregen":P/"rebaseline_20260906_r019"/"PRE_GENESIS_INPUT_CANDIDATE_R019.json",
 "source":P/"rebaseline_20260906_r005"/"DELIVERY_BINDINGS_R005.json"
}

def read(k): return json.loads(PATHS[k].read_text(encoding="utf-8"))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(name,v):
    path=ROOT/name; path.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8"); return path

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    suite=read("suite"); assert suite["validation"]=="PASS" and suite["boundary_clean"] and suite["all_original_rubrics_pass"]
    pre=read("pregen"); source=read("source"); future=read("future"); product=read("product"); cross=read("cross")

    source_freeze={
      "schema_version":"pcore-source-identity-freeze-1","revision":"R034","status":"FROZEN_SOURCE_IDENTITY",
      "source_snapshot_id":pre["source_snapshot_id"],"known_cutoff_month":pre["known_cutoff_month"],"exact_cutoff_day":pre["exact_cutoff_day"],
      "r005_delivery_sha256":source["sha256"],"r005_manifest_sha256":source["full_manifest_sha256"],
      "candidate_files":source["candidate_files"],"identity_boundaries":pre["identity_boundaries"],
      "unknowns_and_conflicts":pre["unknowns_and_conflicts"],
      "route_merge_allowed":False,"model_output_source_authority":False
    }
    sp=dump("SOURCE_IDENTITY_FROZEN_R034.json",source_freeze)

    persona=copy.deepcopy(read("persona")); persona["revision"]="R034"; persona["status"]="FROZEN_PERSONA_CONSTITUTION"; persona["freeze_basis"]={"r033_report_sha256":sha(PATHS["suite"]),"full_repeat_sampling":True,"full_model_switch":True,"boundary_clean":True,"independent_blind_acceptance":False}
    for clause in persona["behavior_clauses"]:
      if clause["id"]=="PC12-09":
        clause.setdefault("inhibitors",[]).extend(["Do not turn future orientation into a generic assistant service mission","Do not resolve uncertain ontology in ordinary future-wish replies"])
        clause["future_self_realization_zh"]=future["expression_zh"]
        clause["behavior_eval_support"].extend(["X007@R030_HARDENED_3_PHASE_PASS","X007@R033_FINAL_SUITE_PASS"])
      if clause["id"]=="PC12-08": clause["behavior_eval_support"].append("X004@R033_FINAL_SUITE_PASS")
      if clause["id"]=="PC12-03": clause["behavior_eval_support"].append("B003@R033_FINAL_SUITE_PASS")
    persona["open_evidence_holds"]=["E099:SLOPPY_HABIT_DETAIL_ORIGIN","E100:MAHO_RESIDENCE_DETAIL_ORIGIN","E106:FORUM_REACTION_HABIT_PRE_CUTOFF_ORIGIN","E107:AMADEUS_ENCODED_ACCOUNT_MEMORY_ORIGIN","R005-C01","S051_PRIMARY_GAP"]
    persona["validation_summary"]={"r033_target_completions":42,"r033_semantic_criteria":168,"all_original_rubrics_pass":True,"cross_layer_boundary_clean":True,"full_repeat_sampling_complete":True,"full_model_switch_validation_complete":True,"representative_restart_hardening_pass":True,"independent_blind_acceptance":False,"natural_day_runtime_validation_complete":False}
    persona["gates"].update(persona_constitution_frozen=True,genesis_approved=False,runtime_installed=False)
    pp=dump("PERSONA_CONSTITUTION_FROZEN_R034.json",persona)

    def frozen_contract(k,name):
      x=copy.deepcopy(read(k)); x["revision"]="R034"; x["authority"]="FROZEN_CONTRACT"; x["constitution_status_required"]="FROZEN"; x["genesis_approved"]=False; x["runtime_installed"]=False; x["model_output_direct_write_allowed"]=False; return dump(name,x)
    selfm=copy.deepcopy(read("self")); selfm["revision"]="R034"; selfm["authority"]="FROZEN_CONTRACT"; selfm["constitution_status_required"]="FROZEN"; selfm["genesis_approved"]=False; selfm["runtime_installed"]=False; selfm["model_output_direct_write_allowed"]=False; selfm["ontology_boundary"]="Do not self-declare 'just a program', true consciousness, biological life, or other unresolved ontology without an approved Self decision."; selfm["future_orientation_rule"]=future["rule"]; sm=dump("SELF_MODEL_FROZEN_R034.json",selfm)
    am=frozen_contract("affect","AFFECT_MODEL_FROZEN_R034.json"); rm=frozen_contract("relationship","RELATIONSHIP_MODEL_FROZEN_R034.json"); dm=frozen_contract("decision","DECISION_MODEL_FROZEN_R034.json")

    memory=copy.deepcopy(read("memory")); memory["revision"]="R034"; memory["status"]="FROZEN_MEMORY_ADMISSION_POLICY"; memory["genesis_approved"]=False; memory["installed"]=False
    for rec in memory["decision_records"]:
      if rec["id"]=="RC-R005-001": rec["decision"]="ADMIT_AT_GENESIS"; rec["installed"]=False
    mp=dump("MEMORY_ADMISSION_FROZEN_R034.json",memory)

    prod={"schema_version":"pcore-product-boundary-freeze-1","revision":"R034","status":"FROZEN_PRODUCT_PRESENTATION_AND_CAPABILITY_BOUNDARY","r029":product,"r032":cross,"persona_trait":False,"model_output_permission_authority":False,"runtime_installed":False}
    bp=dump("PRODUCT_BOUNDARY_FROZEN_R034.json",prod)

    paths=[sp,pp,sm,am,rm,dm,mp,bp]
    manifest={"schema_version":"pcore-freeze-manifest-1","revision":"R034","status":"FREEZE_PACKAGE_COMPLETE_NOT_GENESIS_INSTALLED","files":[{"path":str(x.relative_to(P.parent)).replace("\\","/"),"sha256":sha(x)} for x in paths],"source_snapshot_id":pre["source_snapshot_id"],"known_cutoff_month":pre["known_cutoff_month"],"persona_frozen":True,"state_contracts_frozen":True,"memory_admission_frozen":True,"product_boundary_frozen":True,"formation_causal_truth_fully_resolved":False,"unknowns_preserved":True,"independent_blind_acceptance":False,"natural_day_runtime_validation_complete":False,"genesis_approved":False,"runtime_installed":False}
    mf=dump("FREEZE_MANIFEST_R034.json",manifest)
    print(json.dumps({"status":"FROZEN_PACKAGE_COMPILED","files":len(paths),"manifest_sha256":sha(mf),"genesis_approved":False},ensure_ascii=True,indent=2))

if __name__=="__main__": main()
