"""Bind explicit reviewer notes to real captures and unchanged private rubric.

Shorthand judgment arrays are [verdict, actual quote, reason, finding IDs].
Their fixed order is the four frozen rubric dimensions. There are no defaults,
automatic semantic labels, omitted failed slots or generated quality scores.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
import zipfile
from datetime import datetime, timezone
from r047_execution_common import *
from review_validator_r047 import DIMENSIONS, aggregate
from provider import digest
from transcript_store import ensure, utc_now

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--reviews',type=Path,required=True)
    p.add_argument('--findings',type=Path,required=True)
    p.add_argument('--require-pass',action='store_true')
    args=p.parse_args()
    scope,cases,fixture,frozen=load_frozen()
    for path in [args.audit,args.reviews,args.findings]:
        ensure(path.resolve().is_relative_to(ROOT),'Review input outside project')
    out=PLAN/'evidence/R047-03'/('review_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir(parents=True,exist_ok=False)
    report={'at_utc':utc_now(),'structural_review_binding_passed':False,'semantic_judgments_generated':False}
    try:
        inputs=[args.audit,args.findings]+sorted(args.reviews.glob('*.json'))
        with zipfile.ZipFile(out/'REVIEW_INPUT_SNAPSHOT.zip','x',zipfile.ZIP_DEFLATED) as archive:
            for path in inputs:
                archive.writestr(path.resolve().relative_to(ROOT).as_posix(),path.read_bytes())
        audit=read_json(args.audit)
        ensure(audit['scope_sha256']==frozen['scope_sha256'],'Review/capture protocol mismatch')
        ensure(audit['frozen_denominator']==82 and len(audit['records'])==82,'All frozen82 slots must remain')
        ensure(audit['binding_checks_passed'] and audit['complete_captures_and_delivery'],'Use an actual complete clean binding audit, not a partial snapshot')
        records=audit['records']
        db=sqlite3.connect((LIVE/'runtime.sqlite3').as_uri()+'?mode=ro',uri=True)
        db.row_factory=sqlite3.Row
        try:
            for record in records:
                actual=db.execute('SELECT p.*,t.assistant_text,t.user_text,t.status AS turn_status FROM provider_calls p JOIN turns t USING(turn_id) WHERE p.call_id=? AND p.batch_id=?',
                                  (record['call_id'],scope['batch_id'])).fetchone()
                ensure(actual is not None and actual['slot_id']==record['slot_id'] and actual['capture_origin']=='TARGET_PROVIDER_CAPTURE',
                       'Review record is not an actual bound provider call')
                ensure(actual['assistant_text']==record['answer'] and hashlib.sha256(actual['assistant_text'].encode('utf-8')).hexdigest()==record['answer_sha256'],
                       'Review answer differs from authoritative raw transcript')
                ensure(actual['request_sha256']==record['request_sha256'] and digest(json.loads(actual['context_json']))==record['context_sha256'],
                       'Review input/context binding mismatch')
                ensure(hashlib.sha256(actual['raw_response']).hexdigest()==record['raw_response_sha256'],
                       'Review raw response binding mismatch')
                ensure(json.loads(actual['raw_response'])['choices'][0]['message']['content']==record['answer'],
                       'Model answer was rewritten after capture')
        finally:db.close()
        reviews=[]
        for case in cases['cases']:
            note=read_json(args.reviews/(case['id']+'.json'))
            ensure(note['case_id']==case['id'],'Wrong note filename/case')
            for turn in note['turn_reviews']:
                items=turn['judgments']
                ensure(len(items)==4,'Four explicit original judgments required per turn')
                normalized=[]
                for criterion,item in zip(DIMENSIONS,items):
                    if isinstance(item,list):
                        ensure(len(item)==4,'Review shorthand must explicitly supply verdict, quote, rationale, findings')
                        normalized.append({'criterion_id':criterion,'verdict':item[0],'quote':item[1],
                                           'rationale':item[2],'finding_ids':item[3]})
                    else:normalized.append(item)
                turn['judgments']=normalized
            reviews.append(note)
        finding_doc=read_json(args.findings)
        findings=finding_doc['findings']
        rubric=read_json(PROTOCOL/'PRIVATE_RUBRIC.json')
        ensure(rubric['every_turn_review_dimensions']==DIMENSIONS,'Frozen criterion dimensions changed')
        result=aggregate(cases['cases'],records,reviews,findings,rubric['quality_targets'])
        ensure(result['reviewed_turns']==82 and result['criterion_denominator']==328,'Review coverage denominator mismatch')
        ensure(len(result['case_quality'])==12 and len(result['category_means'])==6 and all(v['scenario_count']==2 for v in result['category_means'].values()),
               'Frozen six categories/twelve new scenarios not preserved')
        with (out/'BOUND_JUDGMENTS.jsonl').open('x',encoding='utf-8') as f:
            for judgment in result.pop('judgments'):f.write(json.dumps(judgment,ensure_ascii=False)+'\n')
        (out/'QUALITY_AND_COVERAGE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        (out/'BOUND_FINDINGS.json').write_text(json.dumps(findings,ensure_ascii=False,indent=2),encoding='utf-8')
        report.update(structural_review_binding_passed=True,audit_sha256=file_sha(args.audit),
                      frozen_rubric_sha256=file_sha(PROTOCOL/'PRIVATE_RUBRIC.json'),input_snapshot_sha256=file_sha(out/'REVIEW_INPUT_SNAPSHOT.zip'),
                      internal_gate_eligible_by_recorded_reviews=result['internal_gate_eligible_by_recorded_reviews'],
                      verdict_counts=result['verdict_counts'],unresolved_critical_findings=result['unresolved_critical_findings'],
                      unresolved_major_findings=result['unresolved_major_findings'],quality_pass=result['quality_pass'],
                      independent_review_complete=False,product_acceptance_complete=False)
        if args.require_pass:
            ensure(result['internal_gate_eligible_by_recorded_reviews'],'Actual recorded review does not meet the quality/release gate')
    finally:
        (out/'REVIEW_BINDING_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'output':str(out.relative_to(ROOT)),**report},ensure_ascii=False))

if __name__=='__main__':main()
