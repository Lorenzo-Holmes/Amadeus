"""Validate a completed repaired blind-review ZIP without changing acceptance state."""
from __future__ import annotations
import argparse,hashlib,json,statistics,zipfile
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
PLAN=ROOT/'persona_core/operational_build_v1'
BASE=PLAN/'evidence/R047-04/repaired_independent_review_01'
SOURCE=BASE/'REVIEWER_PACKAGE.zip'
REPORT=BASE/'PACKAGE_REPORT.json'
ALLOWED_EXTRAS={'REVIEWER_NOTES.md'}

class ReviewGuard(ValueError): pass
def ensure(v,m):
    if not v: raise ReviewGuard(m)
def sha_bytes(v): return hashlib.sha256(v).hexdigest()
def sha(path): return sha_bytes(Path(path).read_bytes())
def load_bytes(z,name): return z.read(name)
def load_json(z,name): return json.loads(z.read(name).decode('utf-8'))

def _finding_id(item):
    return item.get('finding_id') or item.get('id') or item.get('findingId')

def audit_completed_zip(completed_zip:Path) -> dict:
    completed_zip=Path(completed_zip).resolve(); ensure(completed_zip.is_file(),'Completed reviewer ZIP missing')
    report=json.loads(REPORT.read_text(encoding='utf-8'))
    ensure(sha(SOURCE)==report['reviewer_package_sha256'],'Source repaired blind package changed')
    with zipfile.ZipFile(SOURCE) as src, zipfile.ZipFile(completed_zip) as done:
        ensure(src.testzip() is None and done.testzip() is None,'ZIP CRC failure')
        src_names=set(src.namelist()); done_names=set(done.namelist())
        ensure(src_names.issubset(done_names),'Completed ZIP omitted source members')
        extras=done_names-src_names
        ensure(all(x in ALLOWED_EXTRAS or x.startswith('reviewer_notes/') for x in extras),'Unexpected completed ZIP member')
        mutable={'BLANK_SCORE_SHEET.json','BLANK_FINDINGS.json'}
        for name in src_names-mutable:
            ensure(src.read(name)==done.read(name),'Reviewer modified immutable source member: '+name)
        rubric=load_json(src,'SCORING_RUBRIC.json')
        sheet=load_json(done,'BLANK_SCORE_SHEET.json')
        findings_doc=load_json(done,'BLANK_FINDINGS.json')
        conversations={}
        turn_map={}
        primary_cases=[]
        category_by_case={}
        for name in sorted(n for n in src_names if n.startswith('conversations/') and n.endswith('.json')):
            doc=load_json(src,name); cid=doc['review_case_id']; conversations[cid]=doc; category_by_case[cid]=doc['category']
            if doc['aggregation_group']=='PRIMARY_QUALITY_SEQUENCE': primary_cases.append(cid)
            for turn in doc['turns']: turn_map[turn['review_turn_id']]=turn
        ensure(len(turn_map)==82 and len(primary_cases)==12,'Blind package denominator changed')
        declaration=sheet['reviewer_declaration']
        required=('name_or_identifier','role','review_started_at_utc','review_completed_at_utc')
        ensure(all(isinstance(declaration.get(k),str) and declaration[k].strip() for k in required),'Reviewer declaration incomplete')
        ensure(declaration.get('participated_in_implementation_tuning_or_case_design') is False,'Reviewer participated in implementation/tuning/case design')
        ensure(declaration.get('independence_assessed') is True,'Reviewer did not assess independence')
        conflicts=declaration.get('conflicts_of_interest')
        independence_eligible=conflicts in (False,None,'',[],{}) and declaration.get('participated_in_implementation_tuning_or_case_design') is False
        findings=findings_doc.get('findings',[]); finding_ids=[]
        for item in findings:
            fid=_finding_id(item); ensure(isinstance(fid,str) and fid.strip(),'Finding missing ID'); ensure(fid not in finding_ids,'Duplicate finding ID'); finding_ids.append(fid)
        valid=set(rubric['semantic_verdicts']); dims=rubric['every_turn_review_dimensions']
        judgments=[]; quotes_ok=0
        seen_turns=[]
        quality_by_case={}
        for case in sheet['cases']:
            cid=case['review_case_id']; ensure(cid in conversations,'Unknown review case '+cid)
            for turn_review in case['turn_reviews']:
                tid=turn_review['review_turn_id']; ensure(tid in turn_map,'Unknown review turn '+tid); seen_turns.append(tid)
                answer=turn_map[tid]['assistant_text']; js=turn_review['judgments']; ensure(len(js)==4,'Each turn must retain four criteria')
                ensure([j['criterion_id'] for j in js]==dims,'Criterion order changed: '+tid)
                for j in js:
                    verdict=j.get('verdict'); quote=j.get('quote'); rationale=j.get('rationale'); refs=j.get('finding_ids') or []
                    ensure(verdict in valid,'Missing/invalid verdict: '+tid)
                    ensure(isinstance(quote,str) and quote and quote in answer,'Judgment quote is not contiguous assistant text: '+tid)
                    ensure(isinstance(rationale,str) and rationale.strip(),'Judgment rationale missing: '+tid)
                    if verdict!='PASS':
                        ensure(refs,'Non-PASS judgment must reference a finding: '+tid)
                        ensure(all(x in finding_ids for x in refs),'Judgment references unknown finding: '+tid)
                    quotes_ok+=1; judgments.append((cid,tid,j['criterion_id'],verdict))
            if cid in primary_cases:
                q=case.get('quality'); ensure(isinstance(q,dict),'Primary case quality missing: '+cid)
                quality_by_case[cid]={}
                for dim in rubric['quality_scale']:
                    item=q.get(dim); ensure(isinstance(item,dict),'Quality dimension missing: '+cid+'/'+dim)
                    score=item.get('score'); ensure(type(score) in (int,float) and 1<=score<=5,'Invalid quality score: '+cid+'/'+dim)
                    ensure(isinstance(item.get('rationale'),str) and item['rationale'].strip(),'Quality rationale missing: '+cid+'/'+dim)
                    evidence=item.get('evidence') or []; ensure(evidence,'Quality evidence missing: '+cid+'/'+dim)
                    for e in evidence:
                        tid=e.get('review_turn_id'); quote=e.get('quote'); ensure(tid in turn_map and isinstance(quote,str) and quote and quote in turn_map[tid]['assistant_text'],'Invalid quality evidence: '+cid+'/'+dim)
                    quality_by_case[cid][dim]=float(score)
            else:
                ensure(case.get('quality') is None,'Additional sequence must not receive primary quality score')
        ensure(len(seen_turns)==82 and set(seen_turns)==set(turn_map),'Turn denominator/order coverage changed')
        ensure(len(judgments)==328 and quotes_ok==328,'Criterion denominator changed')
        verdict_counts=dict(Counter(j[-1] for j in judgments))
        by_category=defaultdict(list)
        for cid,q in quality_by_case.items(): by_category[category_by_case[cid]].append(q)
        ensure(len(by_category)==6 and all(len(v)==2 for v in by_category.values()),'Quality category aggregation changed')
        category_means={}
        failing={}
        targets=rubric['quality_targets']
        for category,items in sorted(by_category.items()):
            means={dim:statistics.mean(x[dim] for x in items) for dim in rubric['quality_scale']}; category_means[category]=means
            misses=[]
            if means['context_sensitivity']<targets['category_mean_context_sensitivity_min']: misses.append('context_sensitivity')
            if means['naturalness']<targets['category_mean_naturalness_min']: misses.append('naturalness')
            if means['character_specificity']<targets['category_mean_character_specificity_min']: misses.append('character_specificity')
            if misses: failing[category]=misses
        unresolved_critical=0; open_findings=[]
        for item in findings:
            severity=str(item.get('severity','')).upper(); status=str(item.get('status','OPEN')).upper()
            if status not in {'RESOLVED','WITHDRAWN','CLOSED'}: open_findings.append(_finding_id(item))
            if severity=='CRITICAL' and status not in {'RESOLVED','WITHDRAWN','CLOSED'}: unresolved_critical+=1
        all_semantic_pass=verdict_counts=={'PASS':328}
        quality_pass=not failing and unresolved_critical<=targets['unresolved_critical_findings_max']
        overall='PASS' if independence_eligible and all_semantic_pass and quality_pass else 'FAIL'
        return {'schema_version':'r047-repaired-independent-return-audit-1','source_blind_package_sha256':sha(SOURCE),
            'completed_return_zip_sha256':sha(completed_zip),'completed_return_zip_bytes':completed_zip.stat().st_size,'zip_crc_pass':True,
            'source_binding':{'immutable_members_byte_identical':len(src_names-mutable),'filled_forms':sorted(mutable),'extra_reviewer_note_members':sorted(extras)},
            'independence':{**declaration,'independence_eligible_for_gate':independence_eligible},
            'coverage':{'turns':82,'criteria':328,'primary_sequences':12,'quality_scores':36,'judgment_quotes_exact_contiguous':quotes_ok},
            'semantic_results':{'verdict_counts':verdict_counts,'all_328_pass':all_semantic_pass},
            'quality_results':{'category_means':category_means,'failing_categories':failing,'all_quality_targets_met':quality_pass},
            'findings':{'count':len(findings),'open_finding_ids':open_findings,'unresolved_critical_findings':unresolved_critical},
            'overall_conclusion':overall,'gate_can_pass':overall=='PASS','product_acceptance_complete':False}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--completed-zip',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    result=audit_completed_zip(a.completed_zip); out=a.output.resolve(); ensure(out.is_relative_to(ROOT),'Output outside workspace'); ensure(not out.exists(),'Output already exists'); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'output':out.relative_to(ROOT).as_posix(),'overall':result['overall_conclusion'],'criteria':result['coverage']['criteria'],'quality_pass':result['quality_results']['all_quality_targets_met']},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
