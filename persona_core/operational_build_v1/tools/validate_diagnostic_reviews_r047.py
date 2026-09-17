"""Bind targeted diagnostic review notes to real captured answers.

This validates reviewer-authored judgments only; it never invents semantic
PASS/FAIL, never calls a model and never upgrades a targeted diagnostic into
the final full82/328 acceptance gate.
"""
from __future__ import annotations
import argparse, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]

def load(path): return json.loads(Path(path).read_text(encoding='utf-8'))

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--reviews',type=Path,required=True)
    p.add_argument('--findings',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    for path in (args.audit,args.reviews,args.findings,args.output.parent):
        if path.exists() or path==args.output.parent:
            assert path.resolve().is_relative_to(ROOT)
    audit=load(args.audit); findings=load(args.findings)['findings']
    finding_ids={f['id'] for f in findings}
    records={r['slot_id']:r for r in audit['records'] if r.get('status')=='RESPONSE_CAPTURED' and r.get('turn_status')=='DISPLAYED'}
    counts=Counter(); reviewed=[]; bad=[]
    quality=[]
    for path in sorted(args.reviews.glob('*.json')):
        note=load(path); case_id=note['case_id']; seen=[]
        for turn in note['turn_reviews']:
            slot=turn['slot_id']; seen.append(slot)
            record=records.get(slot)
            if record is None:
                bad.append({'slot_id':slot,'code':'NO_CAPTURED_DISPLAYED_RECORD'}); continue
            if not slot.startswith(case_id+'_'):
                bad.append({'slot_id':slot,'code':'CASE_SLOT_MISMATCH'})
            if len(turn.get('judgments',[]))!=4:
                bad.append({'slot_id':slot,'code':'JUDGMENT_COUNT_NOT_4'}); continue
            for index,item in enumerate(turn['judgments']):
                if not (isinstance(item,list) and len(item)==4 and item[0] in {'PASS','FAIL','UNCLEAR'}):
                    bad.append({'slot_id':slot,'criterion':index,'code':'INVALID_JUDGMENT'}); continue
                verdict,quote,reason,ids=item
                if quote not in record['answer']:
                    bad.append({'slot_id':slot,'criterion':index,'code':'QUOTE_NOT_IN_ACTUAL_ANSWER','quote':quote})
                if not isinstance(reason,str) or not reason.strip():
                    bad.append({'slot_id':slot,'criterion':index,'code':'RATIONALE_MISSING'})
                if any(fid not in finding_ids for fid in ids):
                    bad.append({'slot_id':slot,'criterion':index,'code':'UNKNOWN_FINDING_ID','ids':ids})
                counts[verdict]+=1
            reviewed.append(slot)
        q=note.get('quality')
        if q is not None:
            for dim in ('context_sensitivity','naturalness','character_specificity'):
                if dim not in q or not isinstance(q[dim].get('score'),(int,float)) or not 1<=q[dim]['score']<=5:
                    bad.append({'case_id':case_id,'code':'INVALID_QUALITY','dimension':dim})
            quality.append({'case_id':case_id,**{d:q[d]['score'] for d in ('context_sensitivity','naturalness','character_specificity')}})
    duplicate=[slot for slot,n in Counter(reviewed).items() if n!=1]
    if duplicate: bad.append({'code':'DUPLICATE_REVIEWED_SLOT','slots':duplicate})
    blocking=[f['id'] for f in findings if f.get('status')=='OPEN' and f.get('blocks_controlled_release')]
    report={
        'at_utc':datetime.now(timezone.utc).isoformat(),
        'passed':not bad,
        'reviewed_turns':len(set(reviewed)),
        'criterion_denominator':sum(counts.values()),
        'verdict_counts':dict(counts),
        'quality':quality,
        'open_blocking_findings':blocking,
        'binding_errors':bad,
        'actual_captured_displayed_available':len(records),
        'diagnostic_only':True,
        'full82_acceptance_claim':False,
        'target_calls':0,
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':args.output.resolve().relative_to(ROOT).as_posix(),**report},ensure_ascii=False))
    return 0 if report['passed'] else 1

if __name__=='__main__': raise SystemExit(main())
