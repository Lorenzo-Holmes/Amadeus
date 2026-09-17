"""Read-only simulated-clock stress. Results never count as real natural days."""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import natural_day_validation_repaired_r047 as natural

ROOT=natural.ROOT; PLAN=natural.PLAN; TOKYO=natural.TOKYO
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def scenarios():
    pointer,runtime,_,_,_,_,_=natural.resolved(); db=runtime/'runtime.sqlite3'; before=sha(db)
    base=datetime(2026,9,12,12,0,tzinfo=TOKYO)
    points={'same_day_late':base.replace(hour=23,minute=59),'next_day_after_midnight':base+timedelta(days=1,hours=-11,minutes=-59),
      'plus_7_days':base+timedelta(days=7),'plus_30_days':base+timedelta(days=30),'rollback_previous_day':base-timedelta(days=1)}
    results={name:natural.evaluate(now=value.astimezone(timezone.utc)) for name,value in points.items()}
    after=sha(db)
    expected=(results['same_day_late']['today_already_counted'] and not results['same_day_late']['today_can_qualify']
      and all(not results[k]['today_can_qualify'] for k in ('next_day_after_midnight','plus_7_days','plus_30_days','rollback_previous_day')))
    return {'schema_version':'r047-simulated-time-stress-1','candidate_release_id':pointer['candidate_release_id'],'simulated_only':True,'counts_for_real_natural_day':False,
      'system_clock_modified':False,'candidate_db_sha256_before':before,'candidate_db_sha256_after':after,'candidate_bytes_unchanged':before==after,
      'scenarios':{k:{'simulated_local_time':points[k].isoformat(),'observed_local_date':v['observed_local_date'],'today_already_counted':v['today_already_counted'],'today_can_qualify':v['today_can_qualify'],'today_displayed_calls':v['today_displayed_calls']} for k,v in results.items()},
      'pass':expected and before==after,'conclusion':'Manual/future clock selection alone cannot manufacture a qualified day.'}

def main():
    r=scenarios(); out=PLAN/'evidence/R047-04/repaired_natural_day/SIMULATED_TIME_STRESS.json'
    if not out.exists(): out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(r,ensure_ascii=False,indent=2)); return 0 if r['pass'] else 2
if __name__=='__main__': raise SystemExit(main())
