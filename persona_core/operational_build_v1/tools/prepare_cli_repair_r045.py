"""Offline preparation only: preserve original captures and clone their history.

No model is called. Existing output directories are never overwritten.
"""
from __future__ import annotations
import json
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT/'persona_core/operational_build_v1'
CODE = ROOT/'persona_core/operational_runtime_v1'
sys.path.insert(0,str(CODE))
from transcript_store import create_sandbox, file_sha, ensure
from provider import scope_check

def main():
    source = PLAN/'evidence/R045-03/live_01'
    target = PLAN/'evidence/R045-04/repair_live_01'
    ensure(not target.exists(), 'Repair directory exists; inspect it instead of recreating')
    scope = json.loads((PLAN/'evidence/R045-04/CLI_REPAIR_SCOPE.json').read_text(encoding='utf-8'))
    scope_check(scope)
    db = sqlite3.connect((source/'runtime.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
    db.row_factory = sqlite3.Row
    try:
        calls = [dict(r) for r in db.execute('''SELECT p.call_id,p.slot_id,p.status,p.request_sha256,p.raw_sha256,
          p.context_json,p.usage_json,p.estimate_peak_micro_cny,p.reserve_micro_cny,
          t.user_text,t.assistant_text,t.turn_id,t.status AS turn_status,
          s.session_id,s.entity_id,s.mode,e.label FROM provider_calls p JOIN turns t USING(turn_id)
          JOIN sessions s ON p.session_id=s.session_id JOIN entities e USING(entity_id)
          WHERE p.batch_id='APCORE-R045-LIVE-01' ORDER BY p.submitted_at_utc''')]
        ensure({c['slot_id'] for c in calls} == {'adapter_check','A1','A2','A3','A4','B1','B2','B3','B4'}, 'Original scope incomplete')
        ensure(all(c['status']=='RESPONSE_CAPTURED' for c in calls), 'Original unresolved/failed provider call; stop')
        ensure(all(c['turn_status']=='DISPLAYED' for c in calls if c['slot_id']!='adapter_check'), 'Original CLI display not completed')
        runs = [dict(r) for r in db.execute('SELECT * FROM cli_process_runs ORDER BY started_at_utc')]
        ensure(len(runs)>=4 and all(r['exit_code']==0 for r in runs), 'Original process exit not verified')
        create_sandbox(target)
        with sqlite3.connect(target/'runtime.sqlite3') as copy:
            db.backup(copy)
            ensure(copy.execute('PRAGMA integrity_check').fetchone()[0]=='ok','Clone integrity failure')
    finally:
        db.close()
    report = {'created_at_utc':datetime.now(timezone.utc).isoformat(), 'source':str(source.relative_to(ROOT)),
              'destination':str(target.relative_to(ROOT)), 'original_calls':calls, 'original_cli_processes':runs,
              'source_history_reused_not_regenerated':True, 'new_target_calls':0,
              'repair_scope_sha256':file_sha(PLAN/'evidence/R045-04/CLI_REPAIR_SCOPE.json'),
              'repair_criteria_sha256':file_sha(PLAN/'evidence/R045-04/CLI_REPAIR_CRITERIA.json'),
              'clone_database_sha256':file_sha(target/'runtime.sqlite3'), 'acceptance_verdict':None}
    (target/'PREPARATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    paths=list(CODE.glob('*.py'))+[Path(__file__),PLAN/'evidence/R045-04/CLI_REPAIR_SCOPE.json',PLAN/'evidence/R045-04/CLI_REPAIR_CRITERIA.json']
    with zipfile.ZipFile(target/'PREOUTPUT_SOURCE_AND_PROTOCOL.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in paths: z.writestr(p.relative_to(ROOT).as_posix(),p.read_bytes())
    print(json.dumps({'output':str(target.relative_to(ROOT)), 'original_calls':len(calls),
                      'original_peak_usage_estimate_cny':sum(c['estimate_peak_micro_cny'] for c in calls)/1e6,
                      'new_calls':0},ensure_ascii=True))

if __name__=='__main__': main()
