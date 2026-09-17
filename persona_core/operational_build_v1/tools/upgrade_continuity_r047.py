"""Offline upgrade-continuity proof from the old Day-1 candidate into current repaired code."""
from __future__ import annotations
import argparse,hashlib,json,shutil,sqlite3,sys
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]; PLAN=ROOT/'persona_core/operational_build_v1'
OLD=PLAN/'evidence/R047-05/candidate_20260911T130857589500Z/runtime'
OLD_CP=PLAN/'evidence/R047-04/natural_day_observation/checkpoints/2026-09-11/CHECKPOINT.json'
CODE=ROOT/'persona_core/operational_runtime_v1'; sys.path.insert(0,str(CODE))
from transcript_store import TranscriptStore
from admission import AdmissionController
from runtime_store import RuntimeStore
from recovery import logical_summary

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def ro_summary(path):
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    try: return logical_summary(db)
    finally: db.close()

def run_upgrade(output:Path):
    cp=load(OLD_CP); sid=cp['session_ids'][0]; output=Path(output); runtime=output/'runtime'; runtime.mkdir(parents=True,exist_ok=False)
    shutil.copy2(OLD/'SANDBOX.json',runtime/'SANDBOX.json'); shutil.copytree(OLD/'legacy_runtime',runtime/'legacy_runtime',ignore=shutil.ignore_patterns('__pycache__'))
    source=sqlite3.connect((OLD/'runtime.sqlite3').resolve().as_uri()+'?mode=ro',uri=True); target=sqlite3.connect(runtime/'runtime.sqlite3')
    try: source.backup(target)
    finally: target.close(); source.close()
    before=ro_summary(runtime/'runtime.sqlite3')
    src=sqlite3.connect((OLD/'runtime.sqlite3').resolve().as_uri()+'?mode=ro',uri=True); src.row_factory=sqlite3.Row
    try:
        old_session=dict(src.execute('SELECT * FROM sessions WHERE session_id=?',(sid,)).fetchone()); old_turns=[dict(r) for r in src.execute('SELECT * FROM turns WHERE session_id=? ORDER BY seq',(sid,))]
    finally: src.close()
    store=TranscriptStore(runtime)
    try:
        controller=AdmissionController(store); rv=RuntimeStore(store,controller).verify(); handle=store.resume(old_session['principal_id'],sid); recent=store.recent(handle,20)
        current_session=dict(store.db.execute('SELECT * FROM sessions WHERE session_id=?',(sid,)).fetchone()); current_turns=[dict(r) for r in store.db.execute('SELECT * FROM turns WHERE session_id=? ORDER BY seq',(sid,))]
        provider_before=before['tables']['provider_calls']['rows']; provider_after=store.db.execute('SELECT count(*) FROM provider_calls').fetchone()[0]
    finally: store.close()
    after=ro_summary(runtime/'runtime.sqlite3')
    exact_turns=old_turns==current_turns and len(recent)==len(old_turns)
    result={'schema_version':'r047-upgrade-continuity-1','upgrade_kind':'CODE_UPGRADE_CONTINUITY_NO_SCHEMA_MIGRATION_REQUIRED','source_checkpoint':OLD_CP.relative_to(ROOT).as_posix(),
      'source_checkpoint_sha256':sha(OLD_CP),'old_session_id':sid,'session_identity_preserved':old_session==current_session,'turn_history_preserved_exactly':exact_turns,
      'old_turn_count':len(old_turns),'old_user_texts':[r['user_text'] for r in old_turns],'old_assistant_texts':[r['assistant_text'] for r in old_turns],
      'runtime_verify':rv,'logical_state_preserved':before==after,'provider_calls_before':provider_before,'provider_calls_after':provider_after,
      'provider_resubmissions':provider_after-provider_before,'current_runtime_source_hashes':{p.name:sha(p) for p in sorted(CODE.glob('*.py'))},
      'pass':old_session==current_session and exact_turns and before==after and provider_after==provider_before,'target_calls':0,'counts_for_natural_day':False}
    (output/'UPGRADE_CONTINUITY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); return result

def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path); a=p.parse_args(); out=(a.output or (PLAN/'evidence/R047-04'/('upgrade_continuity_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')))).resolve(); out.mkdir(parents=True,exist_ok=False)
    r=run_upgrade(out); print(json.dumps({'output':out.relative_to(ROOT).as_posix(),'pass':r['pass'],'turns':r['old_turn_count'],'provider_resubmissions':r['provider_resubmissions']},ensure_ascii=False)); return 0 if r['pass'] else 2
if __name__=='__main__': raise SystemExit(main())
