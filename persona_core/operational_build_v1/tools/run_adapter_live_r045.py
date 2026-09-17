"""Execute exactly the first pinned R045 live slot; never resend it on restart."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"persona_core/operational_runtime_v1"))
from transcript_store import TranscriptStore,create_sandbox
from context_router import build_context
from provider import ProviderJournal
from capture_export import export_calls

PLAN=ROOT/"persona_core/operational_build_v1"
HOME=PLAN/"evidence/R045-03/live_01"

def main():
    scope=json.loads((PLAN/"evidence/R045-03/LIVE_BATCH_SCOPE.json").read_text(encoding="utf-8"))
    if not HOME.exists(): create_sandbox(HOME)
    store=TranscriptStore(HOME)
    try:
        journal=ProviderJournal(store); journal.register_batch(scope)
        sessions=[r for r in store.list_sessions(scope["principal_id"]) if r["label"]=="SYNTHETIC_ADAPTER"]
        handle=store.resume(scope["principal_id"],sessions[0]["session_id"]) if sessions else store.open_session(scope["principal_id"],"SYNTHETIC_ADAPTER")
        slot=scope["slots"][0]
        turn=store.begin_turn(handle,slot["user_text"],slot["id"])
        context=build_context(store,handle,turn["turn_id"])
        result=journal.call(handle,turn["turn_id"],scope["batch_id"],slot["id"],context)
        export=export_calls(store,HOME/"captures")
        report={"status":result["status"],"scope":scope["batch_id"],"slot":slot["id"],
                "summary":journal.summary(scope["batch_id"]),"evidence":export,"production_modified":False}
        # A repeated invocation never silently rewrites an earlier recovery state.
        report_path=HOME/("ADAPTER_RESULT_"+result["call_id"]+".json")
        if not report_path.exists():
            with report_path.open("x",encoding="utf-8") as f: f.write(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
        print(json.dumps(report,ensure_ascii=False,indent=2))
        if result["status"]!="RESPONSE_CAPTURED": raise SystemExit(1)
    finally: store.close()

if __name__=="__main__": main()
