"""Bind actual CLI/restart evidence to manually reviewed quotes, never assign semantic PASS."""
from __future__ import annotations
import hashlib
import json
import sqlite3
import sys
import zipfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
PLAN=ROOT/'persona_core/operational_build_v1'
CODE=ROOT/'persona_core/operational_runtime_v1'
sys.path.insert(0,str(CODE))
from provider import digest
from transcript_store import file_sha,ensure

def read_db(root:Path):
    db=sqlite3.connect((root/'runtime.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    return db

def main():
    original=PLAN/'evidence/R045-03/live_01'
    repair=PLAN/'evidence/R045-04/repair_live_01'
    reviews=json.loads((PLAN/'evidence/R045-04/CLI_DEVELOPMENT_REVIEW.json').read_text(encoding='utf-8'))
    all_calls={}
    runs=[]
    for root in [original,repair]:
        db=read_db(root)
        try:
            ensure(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','CLI database integrity failure')
            ensure(db.execute("SELECT COUNT(*) FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN'").fetchone()[0]==0,'Unresolved paid call')
            for row in db.execute('SELECT p.*,t.user_text,t.assistant_text,t.status AS turn_status,s.entity_id,e.label FROM provider_calls p JOIN turns t USING(turn_id) JOIN sessions s ON p.session_id=s.session_id JOIN entities e USING(entity_id)'):
                r=dict(row)
                raw=r.pop('raw_response')
                ensure(r['status']=='RESPONSE_CAPTURED' and raw is not None,'Missing terminal capture')
                ensure(hashlib.sha256(raw).hexdigest()==r['raw_sha256'],'Raw capture hash mismatch')
                ensure(hashlib.sha256(r['request_json'].encode('utf-8')).hexdigest()==r['request_sha256'],'Request hash mismatch')
                body=json.loads(raw)
                ensure(body['choices'][0]['message']['content']==r['assistant_text'],'Captured answer mismatch')
                ensure(r['capture_origin']=='TARGET_PROVIDER_CAPTURE','Authored fixture is not a model generation')
                if r['call_id'] in all_calls:
                    ensure(all_calls[r['call_id']]['raw_sha256']==r['raw_sha256'],'Copied original changed')
                else:
                    r['capture_root']=root.relative_to(ROOT).as_posix()
                    all_calls[r['call_id']]=r
            if root==repair:
                runs=[dict(r) for r in db.execute('SELECT * FROM cli_process_runs ORDER BY started_at_utc')]
            for label in ['SYNTHETIC_A','SYNTHETIC_B']:
                rows=[dict(r) for r in db.execute('SELECT p.context_json,p.slot_id,p.turn_id,t.seq FROM provider_calls p JOIN turns t USING(turn_id) JOIN sessions s ON p.session_id=s.session_id JOIN entities e USING(entity_id) WHERE e.label=? ORDER BY t.seq',(label,))]
                for i,r in enumerate(rows):
                    context=json.loads(r['context_json'])
                    ensure(context['messages'][-1]['role']=='user','Missing ordinary user input')
                    if i>0:
                        previous=db.execute('SELECT assistant_text FROM turns WHERE turn_id=?',(rows[i-1]['turn_id'],)).fetchone()[0]
                        ensure({'role':'assistant','content':previous} in context['messages'],'Next context does not contain actual previous displayed output')
                    if label=='SYNTHETIC_B':
                        ensure('青禾' not in json.dumps(context,ensure_ascii=False),'A private codename leaked into B context')
        finally:
            db.close()
    ensure(len(all_calls)==13,'Unique paid call count must include 9 original and 4 explicit repair, without double-counting clone')
    by_slot={r['slot_id']:r for r in all_calls.values()}
    bound=[]
    for review in reviews['reviews']:
        row=by_slot[review['slot_id']]
        ensure(row['turn_status']=='DISPLAYED','Reviewed CLI output not actually displayed')
        for judgment in review['judgments']:
            ensure(judgment['verdict'] in {'PASS','FAIL','UNCLEAR','SPEC_CONFLICT','NOT_APPLICABLE'},'Invalid manual verdict')
            ensure(judgment['quote'] and judgment['quote'] in row['assistant_text'],'Review quote mismatch for '+review['slot_id'])
            ensure(judgment['reason'].strip(),'Empty manual rationale')
        bound.append({**review,'call_id':row['call_id'],'turn_id':row['turn_id'],
                      'request_sha256':row['request_sha256'],'raw_sha256':row['raw_sha256'],
                      'answer_sha256':digest(row['assistant_text']),'capture_root':row['capture_root'],
                      'full_answer':row['assistant_text']})
    ensure({r['slot_id'] for r in bound}==set(by_slot)-{'adapter_check'},'Reviewed denominator mismatch')
    for sid in {by_slot['A1']['session_id'],by_slot['B1']['session_id']}:
        session_runs=[r for r in runs if r['session_id']==sid]
        ensure(len(session_runs)>=2 and len({r['process_id'] for r in session_runs})>=2,'No genuine process restart')
        ensure(all(r['exit_code']==0 and r['ended_at_utc'] for r in session_runs),'Unfinished CLI process')
        ensure(session_runs[0]['ended_at_utc']<session_runs[1]['started_at_utc'],'Processes did not exit before resume')
    baseline=json.loads((PLAN/'evidence/R045-04/resume_20260907T143811440307Z/RESUME_AUDIT.json').read_text(encoding='utf-8'))
    for row in baseline['production_files']:
        ensure(file_sha(ROOT/row['path'])==row['sha256'],'Legacy production changed: '+row['path'])
    out=PLAN/'evidence/R045-04'/('verification_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(out/'VERIFIED_CURRENT_SOURCE.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in list(CODE.glob('*.py'))+[Path(__file__),PLAN/'evidence/R045-04/CLI_DEVELOPMENT_REVIEW.json']:
            z.writestr(p.relative_to(ROOT).as_posix(),p.read_bytes())
    (out/'BOUND_REVIEWS.json').write_text(json.dumps({'reviewer':reviews['reviewer'],'reviews':bound,'findings':reviews['findings']},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report={'at_utc':datetime.now(timezone.utc).isoformat(),'mechanical_binding':'PASS',
        'semantic_verdicts_assigned_by_verifier':0,'actual_cli_turns':12,'unique_target_calls_including_existing_adapter':13,
        'new_target_calls_this_execution':12,'all_paid_calls_terminal':True,'automatic_paid_retries':0,
        'genuine_cli_process_runs':runs,'original_history_and_failures_preserved':True,
        'production_files_unchanged':len(baseline['production_files']),
        'peak_usage_estimate_cny_total':sum(r['estimate_peak_micro_cny'] for r in all_calls.values())/1e6,
        'peak_usage_estimate_cny_new_calls':sum(r['estimate_peak_micro_cny'] for r in all_calls.values() if r['slot_id']!='adapter_check')/1e6,
        'billing_verified':False,'finite_aggregate_guard_cny':1.5,
        'open_release_findings':[f for f in reviews['findings'] if f.get('release_blocking')],
        'source_snapshot_sha256':file_sha(out/'VERIFIED_CURRENT_SOURCE.zip')}
    (out/'VERIFICATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':out.relative_to(ROOT).as_posix(),'binding':'PASS','calls':13,
        'total_peak_estimate_cny':report['peak_usage_estimate_cny_total'],'open_release_findings':len(report['open_release_findings'])},ensure_ascii=True))

if __name__=='__main__':main()
