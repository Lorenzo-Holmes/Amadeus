"""Run current-source regression suites once and retain full logs/source bytes."""
from __future__ import annotations
import hashlib,json,re,subprocess,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
PLAN=ROOT/'persona_core/operational_build_v1'
TOOLS=PLAN/'tools'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=PLAN/'evidence/R047-03'/('regression_'+stamp)
    out.mkdir(parents=True,exist_ok=False)
    modules=['test_transcript_r045.py','test_context_r045.py','test_provider_r045.py',
             'test_chat_r045.py','test_admission_runtime_r046.py','test_dialogue_admission_r046.py',
             'test_process_faults_r046.py','test_recovery_r046.py','test_retrieval_r046.py',
             'test_migration_r046.py','test_provider_v2_r047.py','test_review_validator_r047.py',
             'test_state_projection_r047.py','test_provider_accounting_r047.py', 'test_provider_capacity_r047.py', 'test_worker_contract_r047.py', 'test_epistemic_expression_r047.py', 'test_capture_audit_accounting_r047.py', 'test_live_root_guard_r047.py', 'test_unknown_quarantine_r047.py', 'test_release_guard_r047.py', 'test_epistemic_diagnostic_v2_r047.py', 'test_probe02_continuation_r047.py', 'test_epistemic_diagnostic_v3_r047.py', 'test_epistemic_diagnostic_v4_r047.py', 'test_final_full82_validation_r047.py', 'test_final_full82_validation_v2_r047.py', 'test_final_full82_validation_v3_r047.py', 'test_final_full82_validation_v4_r047.py', 'test_final_full82_validation_v5_r047.py', 'test_composite_full82_repaired_r047.py', 'test_repaired_release_contract_r047.py', 'test_natural_day_validation_r047.py', 'test_natural_day_validation_repaired_r047.py', 'test_audit_repaired_review_return_r047.py', 'test_longitudinal_assessment_r047.py', 'test_final_product_acceptance_r047.py', 'test_simulated_time_stress_r047.py', 'test_adversarial_prompt_contract_r047.py', 'test_fault_recovery_matrix_r047.py', 'test_upgrade_continuity_contract_r047.py', 'test_long_run_storage_stress_r047.py', 'test_external_review_repair_probe_r047.py']
    sources=sorted((ROOT/'persona_core/operational_runtime_v1').glob('*.py'))+sorted(TOOLS.glob('*.py'))
    before={p.relative_to(ROOT).as_posix():sha(p) for p in sources}
    protected=PLAN/'evidence/R047-02/resume_20260908T005132917742Z/RESUME_AUDIT.json'
    manifest=json.loads(protected.read_text(encoding='utf-8'))
    with zipfile.ZipFile(out/'TESTED_SOURCE.zip','x',zipfile.ZIP_DEFLATED) as z:
        for p in sources:z.writestr(p.relative_to(ROOT).as_posix(),p.read_bytes())
    results=[]
    for name in modules:
        path=TOOLS/name
        assert path.is_file(),name
        run=subprocess.run([sys.executable,'-B',str(path)],cwd=ROOT,capture_output=True)
        log=run.stdout+b'\n'+run.stderr
        (out/(name+'.log')).write_bytes(log)
        text=log.decode('utf-8',errors='replace')
        counts=re.findall(r'Ran (\d+) tests?',text)
        for line in text.splitlines():
            try:
                summary=json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(summary,dict) and type(summary.get('tests')) is int and 'passed' in summary:
                counts=[str(summary['tests'])]
        item={'module':name,'exit_code':run.returncode,'tests':int(counts[-1]) if counts else None,'log':name+'.log','log_sha256':sha(out/(name+'.log'))}
        results.append(item)
        print(json.dumps(item),flush=True)
    intact=all(sha(ROOT/p)==h for p,h in before.items())
    unchanged=all(sha(ROOT/p['path'])==p['sha256'] for p in manifest['protected_files'])
    passed=all(r['exit_code']==0 and r['tests'] for r in results) and intact and unchanged
    report={'at_utc':datetime.now(timezone.utc).isoformat(),'passed':passed,'results':results,
        'tests':sum(r['tests'] or 0 for r in results),'sources':before,'source_bytes_unchanged_during_tests':intact,
        'protected_history_and_production_unchanged':unchanged,'target_calls':0,'semantic_review':False,
        'source_archive_sha256':sha(out/'TESTED_SOURCE.zip')}
    (out/'REGRESSION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(out.relative_to(ROOT)),'passed':passed,'tests':report['tests']}),flush=True)
    return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())
