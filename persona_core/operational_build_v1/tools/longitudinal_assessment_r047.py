"""Assess the three real repaired-candidate checkpoints; never manufactures dates."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]; PLAN=ROOT/'persona_core/operational_build_v1'
POINTER=PLAN/'evidence/R047-04/repaired_natural_day/CURRENT_CANDIDATE.json'
OUT=PLAN/'evidence/R047-04/repaired_natural_day/LONGITUDINAL_ASSESSMENT.json'
class LongitudinalGuard(ValueError): pass
def ensure(v,m):
    if not v: raise LongitudinalGuard(m)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))

def assess_records(records:list[dict], *, minimum=3) -> dict:
    dates=[r['observed_local_date'] for r in records]; release_ids={r['candidate_release_id'] for r in records}
    session_sets=[tuple(r.get('session_ids') or []) for r in records]; same_session=len({x for s in session_sets for x in s})==1 and all(len(s)==1 for s in session_sets)
    genesis=[r['runtime_logical_summary']['state']['genesis_sha256'] for r in records]
    seq=[r['runtime_logical_summary']['next_sequence'] for r in records]
    calls=[r['runtime_logical_summary']['provider_calls'] for r in records]; turns=[r['runtime_logical_summary']['turns'] for r in records]
    blockers=[]
    if len(records)<minimum: blockers.append('NEED_'+str(minimum)+'_DISTINCT_REAL_DATES')
    if len(dates)!=len(set(dates)) or dates!=sorted(dates): blockers.append('DATES_NOT_DISTINCT_AND_ORDERED')
    if len(release_ids)!=1: blockers.append('CANDIDATE_RELEASE_CHANGED')
    if not same_session: blockers.append('SESSION_CONTINUITY_FAILED')
    if len(set(genesis))!=1: blockers.append('GENESIS_CHANGED')
    if any(r.get('bad_or_unresolved_calls') for r in records): blockers.append('BAD_OR_UNRESOLVED_CALL_PRESENT')
    if any(b<a for a,b in zip(seq,seq[1:])) or any(b<a for a,b in zip(calls,calls[1:])) or any(b<a for a,b in zip(turns,turns[1:])): blockers.append('RUNTIME_COUNTER_ROLLBACK')
    restart=any(r.get('real_restart_observed') for r in records); switch=any(r.get('same_session_model_switch_observed') for r in records); retrieval=any(r.get('commitment_retrieval_observed') for r in records)
    if len(records)>=minimum and not restart: blockers.append('REAL_RESTART_NOT_OBSERVED')
    if len(records)>=minimum and not switch: blockers.append('SAME_SESSION_MODEL_SWITCH_NOT_OBSERVED')
    if len(records)>=minimum and not retrieval: blockers.append('COMMITMENT_RETRIEVAL_NOT_OBSERVED')
    return {'qualified_dates':dates,'qualified_date_count':len(records),'minimum_distinct_real_dates':minimum,'same_candidate_release':len(release_ids)==1,
        'single_session_continuity':same_session,'genesis_continuity':len(set(genesis))==1,'runtime_counters_monotonic':'RUNTIME_COUNTER_ROLLBACK' not in blockers,
        'real_restart_observed':restart,'same_session_model_switch_observed':switch,'commitment_retrieval_observed':retrieval,'blockers':blockers,
        'overall_conclusion':'PASS' if not blockers and len(records)>=minimum else 'PENDING_OR_FAIL'}

def current_records(pointer_path=POINTER):
    pointer=load(pointer_path); root=ROOT/pointer['checkpoint_root']; records=[]
    for path in sorted(root.glob('*/CHECKPOINT.json')):
        r=load(path); ensure(r.get('qualified_observation_day') is True,'Non-qualified checkpoint in repaired root'); ensure(r['candidate_release_id']==pointer['candidate_release_id'],'Checkpoint belongs to another candidate')
        ensure(r['candidate_release_manifest_sha256']==pointer['release_manifest_sha256'],'Checkpoint/release hash mismatch'); records.append(r)
    return pointer,records

def main():
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['status','finalize']); a=p.parse_args(); pointer,records=current_records(); result=assess_records(records)
    result.update(schema_version='r047-longitudinal-assessment-1',candidate_release_id=pointer['candidate_release_id'],checkpoint_count=len(records),product_acceptance_complete=False)
    if a.action=='finalize':
        ensure(result['overall_conclusion']=='PASS','Longitudinal gate not complete: '+','.join(result['blockers'])); ensure(not OUT.exists(),'Longitudinal assessment already exists')
        result['checkpoint_bindings']=[{'path':(ROOT/pointer['checkpoint_root']/r['observed_local_date']/'CHECKPOINT.json').relative_to(ROOT).as_posix(),'sha256':sha(ROOT/pointer['checkpoint_root']/r['observed_local_date']/'CHECKPOINT.json')} for r in records]
        OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
