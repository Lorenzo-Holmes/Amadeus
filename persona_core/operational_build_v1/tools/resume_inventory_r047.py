"""No-network, read-only reconciliation; new immutable evidence per execution."""
from __future__ import annotations
import hashlib,json,sqlite3,subprocess,zipfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
PLAN=ROOT/'persona_core/operational_build_v1'
LIVE=PLAN/'evidence/R047-02/live_01'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=PLAN/'evidence/R047-02'/('resume_'+stamp)
    out.mkdir(parents=True,exist_ok=False)
    db=sqlite3.connect((LIVE/'runtime.sqlite3').as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    try:
        db.execute('PRAGMA query_only=ON')
        integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
        calls=[dict(r) for r in db.execute('SELECT call_id,batch_id,slot_id,status,submitted_at_utc,response_at_utc,request_sha256,raw_sha256,error_category,estimate_peak_micro_cny FROM provider_calls')]
        batches=[dict(r) for r in db.execute('SELECT batch_id,stopped,scope_sha256 FROM call_batches')]
        lease=[dict(r) for r in db.execute("SELECT key,value FROM metadata WHERE key='r047_active_driver'")]
        statuses=[dict(r) for r in db.execute('SELECT status,count(*) AS n FROM turns GROUP BY status')]
        with sqlite3.connect(out/'LIVE_DATABASE_BACKUP.sqlite3') as target:
            db.backup(target)
            assert target.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    finally: db.close()
    processes=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?(3)?(.exe)?$' } | Select-Object ProcessId,ParentProcessId,CreationDate,ExecutablePath) | ConvertTo-Json -Compress"],capture_output=True,text=True,check=True).stdout.strip()
    protected=[]
    for name in ['runtime','rebaseline_20260907_r033','rebaseline_20260907_r034','rebaseline_20260907_r035','rebaseline_20260907_r043']:
        protected += [p for p in (ROOT/'persona_core'/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    records=[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(protected)]
    preserve=protected+list((ROOT/'persona_core/operational_runtime_v1').glob('*.py'))+list((PLAN/'tools').glob('*.py'))
    preserve += [ROOT/n for n in ['PERSONA_CORE_PROGRESS.md','PERSONA_CORE_DECISION_LOG.md']]+[PLAN/n for n in ['TASK_STATE.json','ACCEPTANCE_MATRIX.json']]
    with zipfile.ZipFile(out/'PRECHANGE_SOURCE_AND_PROTECTED.zip','x',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(set(preserve)): z.writestr(p.relative_to(ROOT).as_posix(),p.read_bytes())
    runs=[]
    for p in (LIVE/'execution_runs').glob('*/EXECUTION.json'):
        r=json.loads(p.read_text(encoding='utf-8'))
        runs.append({k:r[k] for k in ['run_id','phase','pid','started_at_utc','finished_at_utc','status','exit_code']})
        runs[-1]['step_count']=len(r['steps'])
    report={'at_utc':datetime.now(timezone.utc).isoformat(),'workspace':str(ROOT),'database_integrity':integrity,'provider_calls':calls,'call_batches':batches,'driver_lease':lease,'turn_statuses':statuses,'execution_runs':runs,'observed_python_processes':json.loads(processes) if processes else [],'protected_files':records,'unknown_calls':[r for r in calls if r['status']=='SUBMITTED_STATUS_UNKNOWN'],'new_target_calls':0,'automatic_paid_retries':0,'billing_verified':False,'peak_usage_estimate_cny':sum(r['estimate_peak_micro_cny'] or 0 for r in calls)/1e6,'artifacts':{n:sha(out/n) for n in ['LIVE_DATABASE_BACKUP.sqlite3','PRECHANGE_SOURCE_AND_PROTECTED.zip']},'original_consumed_slots_must_not_resubmit':True}
    (out/'RESUME_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':out.relative_to(ROOT).as_posix(),'calls':len(calls),'unknown':len(report['unknown_calls']),'integrity':integrity,'processes':report['observed_python_processes'],'runs':runs,'protected_files':len(records)},ensure_ascii=True))
    assert integrity=='ok' and not report['unknown_calls'] and all(r['value']=='' for r in lease)
if __name__=='__main__':main()
