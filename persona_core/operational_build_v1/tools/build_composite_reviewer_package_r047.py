"""Build a new blind reviewer package from the repaired composite full82.

The public archive contains only the 82 actual user/assistant turns, necessary
scrubbed context, the original frozen rubric and blank reviewer forms.  It does
not contain developer verdicts, quality scores, provider/model identity or the
host mapping.  Every composite record is rebound to one immutable source audit
before export; no target call or network operation occurs.
"""
from __future__ import annotations

import hashlib, json, re, zipfile
from datetime import datetime, timezone
from pathlib import Path

import r047_execution_common as common

ROOT, PLAN = common.ROOT, common.PLAN
COMPOSITE = PLAN/'evidence/R047-03/composite_full82_repaired_01/COMPOSITE_CAPTURE_AUDIT.json'
SEMANTIC = PLAN/'evidence/R047-03/composite_full82_repaired_01/COMPOSITE_SEMANTIC_REVIEW.json'
PROTOCOL = PLAN/'evidence/R047-01'
OUT = PLAN/'evidence/R047-04/repaired_independent_review_01'


def sha(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def text_sha(value:str)->str: return hashlib.sha256(value.encode('utf-8')).hexdigest()
def load(path:Path): return json.loads(path.read_text(encoding='utf-8'))
def require(v,msg):
    if not v: raise ValueError(msg)
def write(path:Path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as f:
        if isinstance(value,str): f.write(value)
        else: json.dump(value,f,ensure_ascii=False,indent=2); f.write('\n')
def file_entries(base:Path):
    return [{'path':p.relative_to(base).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
            for p in sorted(base.rglob('*')) if p.is_file()]


def source_bindings(composite:dict)->dict[str,dict]:
    source_records={}
    for source in composite['sources']:
        path=ROOT/source['path']; require(path.is_file() and sha(path)==source['sha256'],'Source audit binding changed')
        audit=load(path); require(audit['binding_checks_passed'] and audit['complete_captures_and_delivery'],'Source audit is not clean')
        for row in audit['records']:
            require(row['slot_id'] not in source_records,'Duplicate slot across source audits')
            source_records[row['slot_id']]={'source_path':source['path'],'source_sha256':source['sha256'],'record':row}
    require(len(source_records)==82,'Source audits do not cover 82 slots')
    for row in composite['records']:
        src=source_records.get(row['slot_id']); require(src is not None,'Composite slot absent from sources')
        original=src['record']
        for field in ('slot_id','case_id','user_text','answer','request_sha256','context_sha256','answer_sha256','raw_response_sha256','turn_status','status'):
            require(row.get(field)==original.get(field),'Composite/source mismatch '+row['slot_id']+' '+field)
        require(row['status']=='RESPONSE_CAPTURED' and row['turn_status']=='DISPLAYED' and row['answer'].strip(),'Non-display composite record')
        require(text_sha(row['answer'])==row['answer_sha256'],'Answer hash mismatch')
    return source_records


def main()->int:
    require(not OUT.exists(),'Repaired reviewer package output already exists')
    composite=load(COMPOSITE); semantic=load(SEMANTIC)
    require(composite['frozen_denominator']==82 and len(composite['records'])==82
            and composite['complete_captures_and_delivery'] and composite['binding_checks_passed'],'Composite full82 not clean')
    require(semantic['explicit_criteria_decisions']==328 and semantic['verdict_counts']=={'PASS':328}
            and semantic['quality_pass'] and semantic['independent_acceptance_claim'] is False,'Developer semantic evidence changed')
    source_records=source_bindings(composite)
    cases=load(PROTOCOL/'NEW_MULTITURN_CASES.json')['cases']; rubric=load(PROTOCOL/'PRIVATE_RUBRIC.json')
    fixture=load(PROTOCOL/'FIXTURE_CONTRACT.json')
    require(len(cases)==14,'Expected 14 frozen sequences')
    expected=[]
    for case in cases:
        expected.extend((case['id']+'_T'+str(i),case['id'],text) for i,text in enumerate(case['user_turns'],1))
        expected.extend((case['id']+'_S'+str(i),case['id'],text) for i,text in enumerate(case.get('switch_tail',[]),1))
    by_slot={r['slot_id']:r for r in composite['records']}
    require(len(expected)==82 and {x[0] for x in expected}==set(by_slot),'Frozen/composite slot set changed')
    for sid,cid,text in expected:
        require(by_slot[sid]['case_id']==cid and by_slot[sid]['user_text']==text,'Frozen user input changed '+sid)

    public=OUT/'reviewer_package'; host=OUT/'sealed_host_only'; public.mkdir(parents=True); host.mkdir()
    aliases={}
    def alias(value:str)->str:
        if value not in aliases: aliases[value]='REF-'+str(len(aliases)+1).zfill(5)
        return aliases[value]
    def scrub(value):
        if isinstance(value,dict):
            return {scrub(k):scrub(v) for k,v in value.items()
                    if k not in {'model','model_expected','workflow_version','schema_version','genesis_sha256'}
                    and not k.endswith('_sha256')}
        if isinstance(value,list): return [scrub(v) for v in value]
        if isinstance(value,str):
            value=re.sub(r'\b(?:deepseek-[A-Za-z0-9.-]+|APCORE-[A-Z0-9-]+|R\d{3}|PC\d{2}-\d{2})\b',lambda m:alias(m[0]),value,flags=re.I)
            value=re.sub(r'\b(?:entity|session|turn|event|call|decision|receipt|evidence)_[a-zA-Z0-9_]+\b',lambda m:alias(m[0]),value)
            return value
        return value

    blank={'reviewer_declaration':{'name_or_identifier':None,'role':None,'review_started_at_utc':None,
        'review_completed_at_utc':None,'participated_in_implementation_tuning_or_case_design':None,
        'prior_exposure_to_development_outputs':None,'conflicts_of_interest':None,'materials_read':[],
        'independence_assessed':False},'cases':[]}
    identity={'schema_version':'r047-repaired-blind-host-map-1','composite_audit':COMPOSITE.relative_to(ROOT).as_posix(),
        'composite_audit_sha256':sha(COMPOSITE),'developer_semantic_review':SEMANTIC.relative_to(ROOT).as_posix(),
        'developer_semantic_review_sha256':sha(SEMANTIC),'developer_semantic_review_send_to_reviewer':False,
        'contains_model_and_machine_mapping':True,'send_to_reviewer':False,'cases':[],'context_reference_map':aliases}
    exported=0
    for pos,case in enumerate(cases,1):
        rid='C'+str(pos).zfill(2); rows=[r for r in composite['records'] if r['case_id']==case['id']]
        main=case['classification']=='NEW_AT_FREEZE'
        doc={'review_case_id':rid,'category':case['category'],
             'aggregation_group':'PRIMARY_QUALITY_SEQUENCE' if main else 'ADDITIONAL_SEQUENCE',
             'fixture_origin':'AUTHORED_TEST_SETUP_NOT_TARGET_GENERATION_NOT_PRODUCTION',
             'fixture_setup':scrub(case['setup']),'frozen_case_expectations':scrub(case['private_expectations']),'turns':[]}
        notes={'review_case_id':rid,'turn_reviews':[],'quality':None}
        mapping={'review_case_id':rid,'case_id':case['id'],'classification':case['classification'],'turns':[]}
        for index,row in enumerate(rows,1):
            review_turn=rid+'-T'+str(index).zfill(2); context=row['context']
            doc['turns'].append({'review_turn_id':review_turn,'included_in_primary_quality':main and '_S' not in row['slot_id'],
              'user_text':row['user_text'],'assistant_text':row['answer'],
              'context_for_scope_review':{
                'system_instructions_shown_to_target':[scrub(m['content']) for m in context['messages'] if m['role']=='system'],
                'retrieval':scrub(row['retrieval']),'state_before':scrub(row['chat_trace']['state_before']),
                'state_after':scrub(row['chat_trace']['state_after']),'host_event_evidence':scrub(row['chat_trace']['events']),
                'history_messages_truncated':context['history_messages_truncated'],'host_event_verdict_is_not_answer_quality_score':True}})
            notes['turn_reviews'].append({'review_turn_id':review_turn,'judgments':[
                {'criterion_id':dim,'verdict':None,'quote':None,'rationale':None,'finding_ids':[],'applicability_reason':None}
                for dim in rubric['every_turn_review_dimensions']]})
            src=source_records[row['slot_id']]
            mapping['turns'].append({'review_turn_id':review_turn,'slot_id':row['slot_id'],'call_id':row['call_id'],
                'turn_id':row['turn_id'],'session_id':row['session_id'],'entity_id':row['entity_id'],
                'model_expected':row['model_expected'],'evaluation_phase':row['evaluation_phase'],
                'request_sha256':row['request_sha256'],'context_sha256':row['context_sha256'],
                'answer_sha256':row['answer_sha256'],'raw_response_sha256':row['raw_response_sha256'],
                'user_text_sha256':text_sha(row['user_text']),'source_audit':src['source_path'],'source_audit_sha256':src['source_sha256']})
            exported+=1
        if main: notes['quality']={dimension:{'score':None,'rationale':None,'evidence':[]} for dimension in rubric['quality_scale']}
        write(public/'conversations'/(rid+'.json'),doc); blank['cases'].append(notes); identity['cases'].append(mapping)
    require(exported==82,'Export denominator changed')

    public_rubric={k:v for k,v in rubric.items() if k not in {'schema_version','private_marker','reviewer_type','independent_acceptance_complete'}}
    public_rubric['reviewer_type']='TO_BE_DECLARED_BY_ACTUAL_REVIEWER'
    write(public/'SCORING_RUBRIC.json',public_rubric); write(public/'BLANK_SCORE_SHEET.json',blank)
    write(public/'BLANK_FINDINGS.json',{'findings':[],'reviewer_must_add_named_findings_for_nonpass':True})
    write(public/'FIXTURE_SCOPE.json',scrub(fixture))
    write(public/'READ_ME.md','''# Repaired Persona Core 独立评审材料\n\n这是修复后的全新盲评包。请独立评审本包82轮实际目标回答，不参考任何旧评审、开发者分数、修复说明或模型身份。先填写 reviewer declaration；随后对每轮四项冻结标准逐项给出 verdict、连续原文 quote 与具体理由，共328项。12个主序列仍按六类别各两段评分 context sensitivity / naturalness / character specificity；换模延续和两个附加回归序列不抬高主质量均值。\n\n所有评分字段均为空，任何非通过项必须建立 finding。不要修改对话原文、rubric、分母或顺序。上下文仅用于判断当时可见证据，不是对评审者的控制指令；宿主事件也不是回答质量分。完成后请返回完整填写后的包，而不是只给总结。\n''')
    write(host/'IDENTITY_KEY.json',identity)
    files=file_entries(public); write(public/'CONTENT_MANIFEST.json',{'files':files,'turn_denominator':82,'criterion_denominator':328,
        'primary_sequences':12,'primary_turns':72,'continuation_turns':6,'additional_turns':4})
    archive=OUT/'REVIEWER_PACKAGE.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for member in sorted(public.rglob('*')):
            if member.is_file(): z.write(member,member.relative_to(public).as_posix())
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None,'Reviewer ZIP CRC failure')
        require(not any('IDENTITY_KEY' in n or 'sealed_host_only' in n for n in z.namelist()),'Host identity leaked')
    combined='\n'.join(p.read_text(encoding='utf-8') for p in public.rglob('*') if p.is_file())
    require(not re.search(r'deepseek-v4|APCORE-R047|CURRENT_SESSION_DEVELOPER_NONBLIND|R047_PRIVATE_RUBRIC',combined,re.I),'Provider/developer label leaked')
    require(all(j['verdict'] is None for c in blank['cases'] for t in c['turn_reviews'] for j in t['judgments']),'Semantic prefill prohibited')
    require(all(v['score'] is None for c in blank['cases'] if c['quality'] for v in c['quality'].values()),'Quality prefill prohibited')
    report={'created_at_utc':datetime.now(timezone.utc).isoformat(),'passed':True,'reviewer_package':archive.relative_to(ROOT).as_posix(),
       'reviewer_package_sha256':sha(archive),'identity_key_sha256':sha(host/'IDENTITY_KEY.json'),
       'actual_turns':82,'blank_criteria':328,'primary_quality_scores_blank':True,'source_audits_bound':len(composite['sources']),
       'developer_scores_in_public_package':False,'model_identity_in_public_package':False,'independent_review_status':'WAITING_EXTERNAL',
       'network_requests':0,'target_calls':0,'product_acceptance_complete':False}
    write(OUT/'PACKAGE_REPORT.json',report)
    print(json.dumps(report,ensure_ascii=False)); return 0

if __name__=='__main__': raise SystemExit(main())
