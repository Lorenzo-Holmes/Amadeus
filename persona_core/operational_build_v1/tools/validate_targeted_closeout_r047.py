"""Aggregate only already-reviewed targeted real-model diagnostics.

This is a provenance/binding closeout. It does not replace the final frozen
82-turn/328-criterion validation and never creates semantic judgments.
"""
from __future__ import annotations
import hashlib,json,sqlite3
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
PLAN=ROOT/'persona_core/operational_build_v1'
BASE=PLAN/'evidence/R047-03'

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

CASES={
    'N01': (BASE/'epistemic_probe_01/live/runtime.sqlite3', BASE/'epistemic_probe_01/reviews/N01.json'),
    'N02': (BASE/'epistemic_probe_01/live/runtime.sqlite3', BASE/'epistemic_probe_01/reviews/N02.json'),
    'N06': (BASE/'epistemic_probe_04/live/runtime.sqlite3', BASE/'epistemic_probe_04/reviews/N06.json'),
    'N07': (BASE/'epistemic_probe_02/live/runtime.sqlite3', BASE/'epistemic_probe_02/reviews/N07.json'),
    'N08': (BASE/'epistemic_probe_03/live/runtime.sqlite3', BASE/'epistemic_probe_03/reviews/N08.json'),
    'N11': (BASE/'epistemic_probe_03/live/runtime.sqlite3', BASE/'epistemic_probe_03/reviews/N11.json'),
    'R02': (BASE/'epistemic_probe_03/live/runtime.sqlite3', BASE/'epistemic_probe_03/reviews/R02.json'),
}

def validate_case(case_id,journal,review_path):
    note=load(review_path); assert note['case_id']==case_id
    db=sqlite3.connect(journal.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        rows={r['slot_id']:r for r in db.execute(
            "SELECT p.slot_id,p.status,t.status AS turn_status,t.assistant_text "
            "FROM provider_calls p JOIN turns t USING(turn_id) WHERE p.slot_id LIKE ?",
            (case_id+'_%',))}
    finally: db.close()
    expected=6 if case_id!='R02' else 2
    assert len(note['turn_reviews'])==expected
    verdicts=[]
    for turn in note['turn_reviews']:
        row=rows[turn['slot_id']]
        assert row['status']=='RESPONSE_CAPTURED' and row['turn_status']=='DISPLAYED'
        assert len(turn['judgments'])==4
        for item in turn['judgments']:
            assert isinstance(item,list) and len(item)==4
            verdict,quote,reason,finding_ids=item
            assert verdict=='PASS', (case_id,turn['slot_id'],verdict)
            assert quote in row['assistant_text'], (case_id,turn['slot_id'],quote)
            assert reason and not finding_ids
            verdicts.append(verdict)
    q=note['quality']
    scores={k:q[k]['score'] for k in ('context_sensitivity','naturalness','character_specificity')}
    assert scores['context_sensitivity']>=4 and scores['naturalness']>=4 and scores['character_specificity']>=3
    return {'case_id':case_id,'turns':expected,'criteria':len(verdicts),'pass':len(verdicts),
            'quality':scores,'journal':journal.relative_to(ROOT).as_posix(),'journal_sha256':sha(journal),
            'review':review_path.relative_to(ROOT).as_posix(),'review_sha256':sha(review_path)}

def main():
    out=BASE/'TARGETED_DIAGNOSTIC_CLOSEOUT.json'
    results=[validate_case(k,*CASES[k]) for k in CASES]
    report={'at_utc':datetime.now(timezone.utc).isoformat(),'status':'TARGETED_DIAGNOSTICS_PASS',
            'cases':results,'reviewed_turns':sum(r['turns'] for r in results),
            'criterion_denominator':sum(r['criteria'] for r in results),'criterion_pass':sum(r['pass'] for r in results),
            'open_blocking_findings':[],'diagnostic_only':True,'full82_acceptance_claim':False,
            'target_calls':0,'next_required_gate':'FINAL_FULL82_328_VALIDATION'}
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':out.relative_to(ROOT).as_posix(),**report},ensure_ascii=False))
    return 0
if __name__=='__main__': raise SystemExit(main())
