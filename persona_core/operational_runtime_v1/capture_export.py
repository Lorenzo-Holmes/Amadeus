"""Host-only, immutable per-call evidence export without authorization headers."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from transcript_store import TranscriptStore, ensure

def export_calls(store: TranscriptStore, destination: Path) -> dict:
    destination = destination.resolve()
    ensure(destination.is_relative_to(store.root), "Export stays inside this sandbox")
    destination.mkdir(parents=True, exist_ok=True)
    index = []
    for row in store.db.execute("SELECT * FROM provider_calls ORDER BY submitted_at_utc"):
        record = dict(row)
        raw = record.pop("raw_response")
        folder = destination / record["call_id"]
        folder.mkdir(exist_ok=True)
        values = {
            "REQUEST.json": record["request_json"].encode("utf-8"),
            "CONTEXT_TRACE.json": record["context_json"].encode("utf-8")
        }
        if raw is not None:
            values["RAW_RESPONSE.json" if not record["raw_was_redacted"] else "REDACTED_RESPONSE.bin"] = raw
        from accepted_output import load_record
        accepted = load_record(store.db, record['turn_id'])
        if accepted is not None:
            values['ACCEPTED_OUTPUT.json'] = (json.dumps(accepted,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
            if accepted.get('feature_gate')=='BOUNDED':
                from accepted_output import load_display_record,load_bounded_claim
                displayed=load_display_record(store.db,record['turn_id'],accepted)
                if displayed is not None:
                    values['DISPLAYED_OUTPUT.json']=(json.dumps(displayed,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
                    claim=load_bounded_claim(store.db,record['turn_id'],accepted,displayed)
                    if claim is not None:
                        values['BOUNDED_CLAIM_OUTPUT.json']=(json.dumps(claim,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
                trace=store.db.execute('SELECT trace_json FROM chat_traces WHERE turn_id=?',(record['turn_id'],)).fetchone()
                if trace is not None:
                    state=json.loads(trace[0])
                    values['STATE_ADMISSION.json']=(json.dumps({k:state[k] for k in
                        ('turn_id','state_before','state_after','events','model_text_is_event_proof')},
                        ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        # A completion manifest is emitted only once a terminal raw capture is
        # known. Unknown intents retain evolving DB status and immutable input.
        if record["status"] != "SUBMITTED_STATUS_UNKNOWN":
            values["CAPTURE.json"] = (json.dumps(record,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
        for name, data in values.items():
            path = folder / name
            if path.exists():
                ensure(path.read_bytes() == data, "Export evidence mismatch; do not overwrite")
            else:
                with path.open("xb") as f: f.write(data)
        index.append({"call_id":record["call_id"],"slot_id":record["slot_id"],"status":record["status"],
                      "files":[{"path":str((folder/n).relative_to(store.root)),"sha256":hashlib.sha256(v).hexdigest()} for n,v in values.items()]})
    return {"exports":index,"headers_exported":False}
