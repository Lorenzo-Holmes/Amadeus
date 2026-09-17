"""Deduplicated local usage/risk ledger. Estimates are never represented as billing."""
from __future__ import annotations
import json,sqlite3
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; PLAN=ROOT/'persona_core/operational_build_v1'

def runtime_databases():
    paths=[]
    for base in (PLAN/'evidence/R047-03',PLAN/'evidence/R047-04'):
        if base.is_dir(): paths.extend(p/'live/runtime.sqlite3' for p in base.iterdir() if p.is_dir() and (p/'live/runtime.sqlite3').is_file())
    comp=PLAN/'evidence/R047-03/composite_full82_repaired_01/components'
    if comp.is_dir(): paths.extend(p/'live/runtime.sqlite3' for p in comp.iterdir() if p.is_dir() and (p/'live/runtime.sqlite3').is_file())
    r5=PLAN/'evidence/R047-05'
    if r5.is_dir(): paths.extend(p/'runtime/runtime.sqlite3' for p in r5.iterdir() if p.is_dir() and (p/'runtime/runtime.sqlite3').is_file() and (p.name.startswith('candidate_') or p.name.startswith('repaired_candidate_')))
    return sorted(set(paths))

def scan():
    calls={}; batches={}; unreadable=[]; incompatible=[]
    for dbp in runtime_databases():
            try:
                db=sqlite3.connect(dbp.resolve().as_uri()+'?mode=ro',uri=True); db.row_factory=sqlite3.Row
            except (sqlite3.DatabaseError,OSError) as exc:
                unreadable.append({'path':dbp.relative_to(ROOT).as_posix(),'error':type(exc).__name__}); continue
            try:
                try: tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                except sqlite3.DatabaseError as exc:
                    unreadable.append({'path':dbp.relative_to(ROOT).as_posix(),'error':type(exc).__name__}); continue
                if 'provider_calls' not in tables: continue
                cols={r[1] for r in db.execute('PRAGMA table_info(provider_calls)')}
                required={'call_id','batch_id','slot_id','model','status','estimate_peak_micro_cny','reserve_micro_cny','error_category'}
                if not required.issubset(cols):
                    incompatible.append({'path':dbp.relative_to(ROOT).as_posix(),'missing_columns':sorted(required-cols)}); continue
                for r in db.execute('SELECT call_id,batch_id,slot_id,model,status,estimate_peak_micro_cny,reserve_micro_cny,error_category FROM provider_calls'):
                    item=dict(r); old=calls.get(r['call_id'])
                    if old is not None and old!=item: raise ValueError('Divergent duplicate call ID: '+r['call_id'])
                    calls[r['call_id']]=item
                if 'call_batches' in tables and {'batch_id','scope_sha256','scope_json','stopped'}.issubset({r[1] for r in db.execute('PRAGMA table_info(call_batches)')}):
                    for r in db.execute('SELECT batch_id,scope_sha256,scope_json,stopped FROM call_batches'):
                        scope=json.loads(r['scope_json']); sig=(r['scope_sha256'],scope.get('total_guard_cny')); old=batches.get(r['batch_id'])
                        if old is not None and old['signature']!=sig: raise ValueError('Divergent duplicate batch: '+r['batch_id'])
                        batches[r['batch_id']]={'signature':sig,'guard_cny':scope.get('total_guard_cny'),'stopped':bool(r['stopped'])}
            finally: db.close()
    known=sum((x['estimate_peak_micro_cny'] or 0) for x in calls.values())/1e6; unknown=[x for x in calls.values() if x['status']=='SUBMITTED_STATUS_UNKNOWN']; unknown_reserve=sum(x['reserve_micro_cny'] or 0 for x in unknown)/1e6
    by_model=defaultdict(lambda:{'calls':0,'known_estimate_cny':0.0,'unknown_reserve_cny':0.0})
    for x in calls.values():
        row=by_model[x['model']]; row['calls']+=1; row['known_estimate_cny']+=(x['estimate_peak_micro_cny'] or 0)/1e6
        if x['status']=='SUBMITTED_STATUS_UNKNOWN': row['unknown_reserve_cny']+=(x['reserve_micro_cny'] or 0)/1e6
    return {'schema_version':'r047-cost-governance-1','at_utc':datetime.now(timezone.utc).isoformat(),'unique_calls':len(calls),'unique_batches':len(batches),
      'status_counts':dict(Counter(x['status'] for x in calls.values())),'known_peak_usage_estimate_cny_subtotal':round(known,6),'remote_unknown_reserve_cny_not_usage':round(unknown_reserve,6),
      'aggregate_unique_logical_guard_cny':round(sum(float(x['guard_cny'] or 0) for x in batches.values()),6),'by_model':dict(by_model),
      'unreadable_databases':unreadable,'unreadable_database_count':len(unreadable),'incompatible_fixture_databases':incompatible,'incompatible_fixture_database_count':len(incompatible),'scan_complete':not unreadable,
      'billing_verified':False,'estimates_are_not_billing':True,'unknown_reserve_is_not_spend':True,'automatic_paid_retries':0}

def main():
    r=scan(); out=PLAN/'evidence/R047-04/COST_GOVERNANCE_CURRENT.json'; out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(r,ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
