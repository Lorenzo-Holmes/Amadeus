from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime_core import PersonaRuntime

TAG_TO_CLAUSES={
    "science_evidence":["PC12-01","PC12-02"],
    "social_repair":["PC12-03"],
    "private_boundary":["PC12-04"],
    "relationship_claim":["PC12-05"],
    "shared_interest":["PC12-05"],
    "contribution":["PC12-06"],
    "help":["PC12-07"],
    "humor":["PC12-08"],
    "future":["PC12-09"],
    "consent":["PC12-10"],
}

def _read(path:Path)->dict[str,Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def _entity_state(snapshot:dict[str,Any],entity_id:str)->dict[str,Any]:
    return snapshot["relationship"]["product_entities"].get(entity_id,{
        "familiarity":0.0,"trust":0.0,"safety":0.0,"respect":0.0,"dependence_or_distance":0.0,
        "conflict_history":[],"commitments":[],"unfinished_items":[],"entity_specific_model":{},"interaction_count":0
    })

def build_messages(runtime_root:Path|str,entity_id:str,tags:list[str],user_message:str)->list[dict[str,str]]:
    root=Path(runtime_root); rt=PersonaRuntime(root); snap=rt.snapshot()
    persona=_read(root/"genesis"/"frozen"/"PERSONA_CONSTITUTION_FROZEN_R034.json")
    product=_read(root/"genesis"/"frozen"/"PRODUCT_BOUNDARY_FROZEN_R034.json")
    self_contract=_read(root/"genesis"/"frozen"/"SELF_MODEL_FROZEN_R034.json")
    genesis=_read(root/"genesis"/"GENESIS_SNAPSHOT_R035.json")
    clause_ids=[]
    for tag in tags:
        for cid in TAG_TO_CLAUSES.get(tag,[]):
            if cid not in clause_ids: clause_ids.append(cid)
    by={c["id"]:c for c in persona["behavior_clauses"]}
    selected=[by[cid] for cid in clause_ids]
    rel=_entity_state(snap,entity_id)
    all_entity_events=[r for r in snap["ledger"] if r.get("entity_id")==entity_id]
    events=[{"event_type":r["event_type"],"payload":r.get("payload",{}),"relationship_updates":r.get("relationship_updates",{})} for r in all_entity_events[-8:]]
    internal={
        "entity_id":entity_id,
        "relationship_state":rel,
        "affect_deviation":snap["affect"]["deviation_from_baseline"],
        "admitted_runtime_event_count_for_entity":len(all_entity_events),
        "recent_admitted_runtime_events_for_entity":events,
        "capabilities":snap["self"]["capabilities"],
        "ontology_status":snap["self"]["ontology_status"]
    }
    if "memory" in tags or "identity" in tags:
        internal["genesis_memory_context"]={
            "source_snapshot_id":genesis["source_snapshot_id"],
            "known_cutoff_month":genesis["known_cutoff_month"],
            "exact_cutoff_day":genesis["exact_cutoff_day"],
            "encoded_autobiographical_memory":genesis["encoded_autobiographical_memory"],
            "source_fact_only_not_first_person_memory":genesis["source_fact_only_not_first_person_memory"],
            "claim_level_holds":genesis["claim_level_holds"],
            "unknowns_and_conflicts":genesis["unknowns_and_conflicts"]
        }
    tendencies=[{"id":c["id"],"tendency":c["behavioral_tendency"],"inhibitors":c.get("inhibitors",[])} for c in selected]
    boundary=product["r029"]["expression_zh"]+"\n"+product["r032"]["global_boundary"]
    system=(
        "你是已安装Genesis后的Amadeus Kurisu文本运行实例。只根据当前已准入Runtime状态、冻结Persona条款和来源/能力边界自然回应。"
        "不要把工程字段、数值或评测术语主动说给对方听；把关系状态自然地表达出来。"
        "模型输出本身没有状态写权限，不能创造新经历、关系、能力或记忆。\n"
        "关系状态按entity隔离。当前entity上下文中未展示其他人的关系细节，不代表那些其他entity的已准入经历从未发生；不要仅因为当前entity记录为空就否认与其他entity的既有运行经历。即使其他关系存在，也不能把其trust/familiarity自动转移给当前对象。\n"
        "当前最小Persona条款："+json.dumps(tendencies,ensure_ascii=False)+"\n"
        "当前只读Runtime状态："+json.dumps(internal,ensure_ascii=False)+"\n"
        "产品呈现/能力边界："+boundary+"\n"
        "Self本体边界："+self_contract.get("ontology_boundary","")+
        ("\nMemory provenance boundary：claim-level HOLD只表示某细节是否在截止点前被编码/是否可准入仍未知，不能反向说成‘我没有这段记忆’或‘我肯定不记得’。"
         "source_fact_only_not_first_person_memory中的事实可以作为来源知识说明，但不得说成‘我回忆起/我记得/我的经历’。"
         "当用户询问未准入的细节时，说明‘来源记录里有/没有什么’或‘该细节的第一人称记忆准入未证’，不要自行裁决其记忆存在性。" if ("memory" in tags or "identity" in tags) else "")
    )
    return [{"role":"system","content":system},{"role":"user","content":user_message}]


