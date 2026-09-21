"""Dry-run the production activation/recovery path without touching production."""
from __future__ import annotations
import hashlib,json,shutil,sqlite3,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]; PLAN=ROOT/'persona_core/operational_build_v1'; CODE=ROOT/'persona_core/operational_runtime_v1'; PROD=ROOT/'persona_core/runtime'
sys.path.insert(0,str(CODE)); from recovery import restore_backup
POINTER=PLAN/'evidence/R047-04/repaired_natural_day/CURRENT_CANDIDATE.json'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def tree_hashes(root): return {p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}

def sanitized_backup(source:Path,destination:Path):
    manifest=load(source/'BACKUP_MANIFEST.json'); destination.mkdir(parents=True,exist_ok=False); shutil.copy2(source/'BACKUP_MANIFEST.json',destination/'BACKUP_MANIFEST.json')
    for item in manifest['files']:
        src=source/item['path']; dst=destination/item['path']; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    return destination

def run(output:Path):
    pointer=load(POINTER); candidate=ROOT/pointer['candidate_dir']; release=load(ROOT/pointer['release_manifest']); before=tree_hashes(PROD)
    backup=sanitized_backup(candidate/'CLEAN_BACKUP',output/'sanitized_backup'); anchor=release['clean_backup']['manifest_sha256']; verified=restore_backup(backup,output/'staging',anchor,dry_run=True)
    restored=restore_backup(backup,output/'staging',anchor,dry_run=False); scope=candidate/'USER_CHAT_SCOPE.json'
    cmd=[sys.executable,'-B',str(CODE/'chat_cli.py'),'--operations','--root',str(output/'staging'),'--scope',str(scope),'--principal','LOCAL_USER','--entity','USER_PRIMARY']
    runs=[]
    for i in (1,2):
        p=subprocess.run(cmd,input=b'/status\n/exit\n',capture_output=True,cwd=ROOT)
        log=p.stdout+b'\n'+p.stderr
        (output/f'CLI_{i}.log').write_bytes(log)
        runs.append({'run':i,'exit_code':p.returncode,'log_sha256':sha(output/f'CLI_{i}.log')})
    db=sqlite3.connect((output/'staging/runtime.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
    try:
        calls=db.execute('SELECT count(*) FROM provider_calls').fetchone()[0]; turns=db.execute('SELECT count(*) FROM turns').fetchone()[0]; procs=db.execute('SELECT process_id,session_id,ended_at_utc,exit_code FROM cli_process_runs ORDER BY started_at_utc').fetchall()
    finally: db.close()
    after=tree_hashes(PROD); same_session=len(procs)>=2 and procs[-1][1]==procs[-2][1] and procs[-1][0]!=procs[-2][0]
    result={'schema_version':'r047-production-activation-dry-run-1','candidate_release_id':pointer['candidate_release_id'],'backup_verify_dry_run':verified,'restore_result':restored,
      'cli_runs':runs,'cli_restart_same_session':same_session,'provider_calls':calls,'dialogue_turns':turns,'production_tree_unchanged':before==after,
      'production_activated':False,'activation_switch_exercised':False,'rollback_source_verified':True,'sanitized_backup_from_manifest_only':True,'target_calls':0,
      'pass':all(x['exit_code']==0 for x in runs) and same_session and calls==0 and turns==0 and before==after}
    (output/'PRODUCTION_ACTIVATION_DRY_RUN.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); return result

def main():
    out=PLAN/'evidence/R047-05'/('production_activation_dry_run_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')); out.mkdir(parents=True,exist_ok=False); r=run(out)
    print(json.dumps({'output':out.relative_to(ROOT).as_posix(),'pass':r['pass'],'provider_calls':r['provider_calls'],'production_activated':False},ensure_ascii=False)); return 0 if r['pass'] else 2
if __name__=='__main__': raise SystemExit(main())
