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
