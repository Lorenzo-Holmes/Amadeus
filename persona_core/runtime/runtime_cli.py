from __future__ import annotations
import argparse,json
from pathlib import Path
from runtime_core import PersonaRuntime

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",required=True); ap.add_argument("--event-json"); ap.add_argument("--snapshot",action="store_true"); args=ap.parse_args(); rt=PersonaRuntime(Path(args.root))
    if args.event_json:
        event=json.loads(Path(args.event_json).read_text(encoding="utf-8")); print(json.dumps(rt.admit_event(event),ensure_ascii=False))
    elif args.snapshot: print(json.dumps(rt.snapshot(),ensure_ascii=False))
    else: raise SystemExit(2)
if __name__=="__main__": main()
