"""Evidence-only final product-acceptance rollup. Does not activate production."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import unknown_quarantine_r047 as unknowns

ROOT=Path(__file__).resolve().parents[3]; PLAN=ROOT/'persona_core/operational_build_v1'; R04=PLAN/'evidence/R047-04'
RETURN=R04/'repaired_independent_review_return/RETURN_AUDIT.json'; LONG=R04/'repaired_natural_day/LONGITUDINAL_ASSESSMENT.json'; POINTER=R04/'repaired_natural_day/CURRENT_CANDIDATE.json'; OUT=R04/'PRODUCT_ACCEPTANCE_COMPLETE.json'
class AcceptanceGuard(ValueError): pass
def ensure(v,m):
    if not v: raise AcceptanceGuard(m)
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def evaluate(review=None,longitudinal=None,pointer=None,unknown_status=None):
    blockers=[]
    if review is None: blockers.append('NEW_INDEPENDENT_REVIEW_RETURN_MISSING')
    elif review.get('overall_conclusion')!='PASS' or review.get('gate_can_pass') is not True: blockers.append('NEW_INDEPENDENT_REVIEW_NOT_PASS')
    if longitudinal is None: blockers.append('LONGITUDINAL_ASSESSMENT_MISSING')
    elif longitudinal.get('overall_conclusion')!='PASS': blockers.append('LONGITUDINAL_ASSESSMENT_NOT_PASS')
    if pointer is None: blockers.append('REPAIRED_CANDIDATE_POINTER_MISSING')
    if unknown_status and unknown_status.get('active_unresolved_remote_unknowns'): blockers.append('ACTIVE_REMOTE_UNKNOWN_PRESENT')
    return {'blockers':blockers,'ready_for_product_acceptance':not blockers}

def main():
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['status','finalize']); a=p.parse_args()
    review=load(RETURN) if RETURN.is_file() else None; longitudinal=load(LONG) if LONG.is_file() else None; pointer=load(POINTER) if POINTER.is_file() else None; us=unknowns.project_unknown_status()
    result=evaluate(review,longitudinal,pointer,us); result.update(schema_version='r047-product-acceptance-rollup-1',product_acceptance_complete=False,production_activated=False)
    if a.action=='finalize':
        ensure(result['ready_for_product_acceptance'],'Final product acceptance blocked: '+','.join(result['blockers'])); ensure(not OUT.exists(),'Final acceptance record already exists')
        release=ROOT/pointer['release_manifest']; result.update(product_acceptance_complete=True,
            evidence={'independent_review':RETURN.relative_to(ROOT).as_posix(),'independent_review_sha256':sha(RETURN),'longitudinal':LONG.relative_to(ROOT).as_posix(),'longitudinal_sha256':sha(LONG),'candidate_release_manifest':release.relative_to(ROOT).as_posix(),'candidate_release_manifest_sha256':sha(release)},
            historical_unknowns_preserved=len(us['allowed_historical_unknowns']),active_unresolved_remote_unknowns=0)
        OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
