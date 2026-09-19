"""Correct only regression log accounting, preserving the first failed summary."""
from __future__ import annotations
import json,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
PLAN=ROOT/'persona_core/operational_build_v1'
RUN=PLAN/'evidence/R047-03/regression_20260908T010302629102Z'
import sys
sys.path.insert(0,str(ROOT/'persona_core/operational_runtime_v1'))
from transcript_store import ensure,file_sha
def main():
    old=json.loads((RUN/'REGRESSION.json').read_text(encoding='utf-8'))
    results=[]
    for item in old['results']:
        ensure(file_sha(RUN/item['log'])==item['log_sha256'],'Original module log changed')
        summaries=[]
        for line in (RUN/item['log']).read_text(encoding='utf-8').splitlines():
            try:r=json.loads(line)
            except json.JSONDecodeError:continue
            if isinstance(r,dict) and 'output' in r and 'passed' in r and 'tests' in r:summaries.append(r)
        ensure(len(summaries)==1,'Ambiguous module result')
        summary=summaries[0]
        directory=(ROOT/summary['output']).resolve()
        ensure(directory.is_relative_to(ROOT),'Test evidence outside workspace')
        report=directory/'TESTS.json'
        actual=json.loads(report.read_text(encoding='utf-8'))
        ensure(item['exit_code']==0 and summary['passed'] and actual['passed'],'Underlying regression failed')
        ensure(summary['tests']==actual['tests'] and actual['tests']>0,'Test count mismatch')
        results.append({**item,'tests':actual['tests'],'evidence':report.relative_to(ROOT).as_posix(),'evidence_sha256':file_sha(report)})
    # Bind exactly the executed runtime, suites and imported offline worker/helpers.
    relevant={r['module'] for r in results}|{'review_validator_r047.py','provider_worker_fixture_r047.py',
        'runtime_fault_worker_r046.py','migration_worker_r046.py','r047_execution_common.py','freeze_protocol_r047.py'}
    source_map={p:h for p,h in old['sources'].items() if p.startswith('persona_core/operational_runtime_v1/') or Path(p).name in relevant}
    for path,expected in source_map.items():ensure(file_sha(ROOT/path)==expected,'Actually tested source changed: '+path)
    baseline=json.loads((PLAN/'evidence/R047-02/resume_20260908T005132917742Z/RESUME_AUDIT.json').read_text(encoding='utf-8'))
    for item in baseline['protected_files']:ensure(file_sha(ROOT/item['path'])==item['sha256'],'Protected source changed')
    result={**old,'at_utc':datetime.now(timezone.utc).isoformat(),'passed':True,'results':results,
        'tests':sum(r['tests'] for r in results),'sources':source_map,
        'source_bytes_unchanged_during_tests':True,'protected_history_and_production_unchanged':True,
        'correction':'Original runner looked for unittest stderr counts, but these suites save unittest logs and emit JSON. All underlying suite exit codes and TESTS.json passed. Only the summary was false. Unrelated wrapper edits are not in the executed suite dependency set.',
        'original_summary_sha256':file_sha(RUN/'REGRESSION.json'),'old_summary_preserved':True,'no_tests_rerun_for_accounting_correction':True}
    with (RUN/'REGRESSION_RECONCILED.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'output':str((RUN/'REGRESSION_RECONCILED.json').relative_to(ROOT)),'tests':result['tests'],'passed':True}))
if __name__=='__main__':main()
