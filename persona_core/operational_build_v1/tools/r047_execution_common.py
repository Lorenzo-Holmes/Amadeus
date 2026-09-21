"""Frozen R047 inputs and safe execution prerequisites; no network on import."""
from __future__ import annotations
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CODE = ROOT / 'persona_core/operational_runtime_v1'
PLAN = ROOT / 'persona_core/operational_build_v1'
PROTOCOL = PLAN / 'evidence/R047-01'
FREEZE = PROTOCOL / 'freeze_20260907T164424498856Z'
LIVE = PLAN / 'evidence/R047-02/live_01'
sys.path.insert(0, str(CODE))
from transcript_store import ensure, file_sha
from provider import scope_check

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def load_frozen():
    report = read_json(FREEZE / 'FREEZE_VERIFICATION.json')
    ensure(report['passed'] and report['protocol_frozen_before_observation'], 'Protocol is not verified pre-observation')
    ensure(file_sha(FREEZE / 'PREOBSERVATION_PROTOCOL.zip') == report['protocol_zip_sha256'], 'Frozen protocol archive changed')
    ensure(file_sha(FREEZE / 'EXECUTION_SCOPE.json') == report['scope_sha256'], 'Frozen scope bytes changed')
    with zipfile.ZipFile(FREEZE / 'PREOBSERVATION_PROTOCOL.zip') as archive:
        ensure(archive.testzip() is None, 'Protocol archive CRC failure')
        for name, expected in report['files'].items():
            ensure(file_sha(PROTOCOL / name) == expected, 'Current protocol member differs from frozen input: ' + name)
    scope = read_json(FREEZE / 'EXECUTION_SCOPE.json')
    scope_check(scope)
    cases = read_json(PROTOCOL / 'NEW_MULTITURN_CASES.json')
    fixture = read_json(PROTOCOL / 'FIXTURE_CONTRACT.json')
    return scope, cases, fixture, report

def check_required_gates():
    state = read_json(PLAN / 'TASK_STATE.json')
    gates = read_json(PLAN / 'ACCEPTANCE_MATRIX.json')
    needed = ['R045-04','R045-05','R046-01','R046-02','R046-03','R046-04','R046-05','R046-06','R047-01']
    tasks = {t['id']: t for t in state['tasks']}
    by_gate = {g['task_id']: g for g in gates['gates']}
    for task in needed:
        ensure(tasks[task]['status'] == 'DONE' and by_gate[task]['status'] == 'PASS', 'Dependency not accepted: ' + task)
        for relative in by_gate[task]['evidence']:
            path = (PLAN / relative).resolve()
            ensure(path.is_relative_to(ROOT) and path.exists(), 'Missing gate evidence: ' + relative)
    return {'verified_gate_ids': needed, 'task_state_sha256': file_sha(PLAN / 'TASK_STATE.json'),
            'acceptance_matrix_sha256': file_sha(PLAN / 'ACCEPTANCE_MATRIX.json')}

def sources():
    return list(sorted(CODE.glob('*.py'))) + list(sorted((PLAN / 'tools').glob('*r047*.py')))

def source_bindings():
    return [{'path': p.relative_to(ROOT).as_posix(), 'sha256': file_sha(p)} for p in sources()]

def verify_source_bindings(bindings):
    for item in bindings:
        path = ROOT / item['path']
        ensure(path.is_relative_to(ROOT) and path.is_file() and file_sha(path) == item['sha256'], 'Execution source changed: ' + item['path'])
