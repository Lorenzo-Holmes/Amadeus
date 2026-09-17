"""Read-only documentation checks. Never calls models or edits project state.

These checks validate this plan's dependency/evidence contract, not the Persona
Core implementation, source truth, semantic judgments, or model performance.
"""
from __future__ import annotations

import argparse
import copy
import json
import unittest
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(__file__).resolve().parent.parent


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load(path: Path) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            require(key not in value, f'Duplicate JSON key: {key}')
            value[key] = item
        return value
    result = json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique)
    require(isinstance(result, dict), f'Not an object: {path.name}')
    return result


def check(state: dict[str, Any], matrix: dict[str, Any], root: Path) -> dict[str, Any]:
    require(state['plan_id'] == matrix['plan_id'] == 'APCORE-OPERATIONS-V1', 'Plan binding mismatch')
    tasks = state['tasks']
    gates = matrix['gates']
    allowed_gate_statuses = {'NOT_RUN', 'IN_REVIEW', 'PASS', 'FAIL', 'UNCLEAR', 'SPEC_CONFLICT', 'WAITING_EXTERNAL', 'WAITING_REAL_TIME'}
    require(all(g['status'] in allowed_gate_statuses for g in gates), 'Invalid acceptance gate status')
    require(len(tasks) == 20, 'Expected 20 implementation tasks in v1')
    require(len({t['id'] for t in tasks}) == len(tasks), 'Duplicate task ID')
    require(len({g['id'] for g in gates}) == len(gates), 'Duplicate gate ID')
    task_map = {t['id']: t for t in tasks}
    gate_map = {g['id']: g for g in gates}
    require(len(gates) == len(tasks), 'Each task needs one gate')
    require(state['active_task'] in task_map, 'Unknown active task')
    require(state['next_action']['task_id'] in task_map, 'Unknown next task')
    require(state['workspace_sync_status'] in {'NOT_VERIFIED', 'VERIFIED'}, 'Invalid sync status')
    allowed = set(state['state_rules']['allowed_task_statuses'])
    plan_text = (root / 'BUILD_PLAN.md').read_text(encoding='utf-8')
    for task in tasks:
        tid = task['id']
        require(task['status'] in allowed, f'Invalid task status: {tid}')
        require(tid in plan_text, f'Task absent from BUILD_PLAN: {tid}')
        require(task['acceptance_gate'] in gate_map, f'Missing gate: {tid}')
        gate = gate_map[task['acceptance_gate']]
        require(gate['task_id'] == tid, f'Wrong gate binding: {tid}')
        require(gate['required_for_build_scope'] == task['required_for_build_scope'], f'Gate scope mismatch: {tid}')
        require(gate['static_check_is_semantic_acceptance'] is False, 'Static check cannot be semantic acceptance')
        require(task['deliverable_types'] == gate['required_evidence_types'], 'Deliverable/gate mismatch')
        require(len(task['depends_on']) == len(set(task['depends_on'])), 'Duplicate dependency')
        for dep in task['depends_on']:
            require(dep in task_map, f'Unknown dependency: {dep}')
        if task['status'] == 'DONE':
            require(bool(task['evidence']), f'DONE has no task evidence: {tid}')
            require(gate['status'] == 'PASS' and bool(gate['evidence']), f'DONE without verified gate: {tid}')
            require(all(task_map[d]['status'] == 'DONE' for d in task['depends_on']), f'Incomplete dependency: {tid}')
        if gate['status'] == 'PASS':
            require(bool(gate['evidence']) and gate['checked_at'] and gate['reviewer'], f'PASS gate lacks evidence/date/reviewer: {tid}')

    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(tid: str) -> None:
        require(tid not in visiting, f'Dependency cycle: {tid}')
        if tid in visited:
            return
        visiting.add(tid)
        for dep in task_map[tid]['depends_on']:
            visit(dep)
        visiting.remove(tid)
        visited.add(tid)
    for tid in task_map:
        visit(tid)

    complete = state['completion']
    if complete['build_scope_complete']:
        require(all(t['status'] == 'DONE' for t in tasks if t['required_for_build_scope']), 'Build completion is unsupported')
    if complete['product_acceptance_complete']:
        require(complete['build_scope_complete'], 'Product accepted before build completion')
        require(all(t['status'] == 'DONE' for t in tasks), 'Product acceptance lacks completed tasks')
        require(complete['independent_blind_acceptance'] == 'PASS', 'Independent acceptance is still pending')
        require(complete['true_natural_day_validation'] == 'PASS', 'Real-date validation is still pending')

    expected = {
        'START_HERE.md', 'BUILD_PLAN.md', 'TASK_STATE.json', 'ACCEPTANCE_MATRIX.json',
        'CONTINUE_PROMPT.md', 'BASELINE_AND_EVIDENCE.md', 'WORKSPACE_SYNC_INSTRUCTIONS.md',
        'WORKSPACE_ENTRYPOINT_PATCH.patch', 'CHANGELOG.md', 'tools/validate_plan.py'
    }
    require(all((root / name).is_file() for name in expected), 'Required documentation file missing')
    patch = (root / 'WORKSPACE_ENTRYPOINT_PATCH.patch').read_text(encoding='utf-8')
    targets = [s.split(': ', 1)[1] for s in patch.splitlines() if s.startswith('*** Update File: ')]
    require(len(targets) == 5 and set(targets) == {
        'AGENTS.md', 'AMADEUS_PERSONA_CORE_MASTER_GOAL.md', 'PERSONA_CORE_PROGRESS.md',
        'PERSONA_CORE_CONTINUATION_PROTOCOL.md', 'PERSONA_CORE_DECISION_LOG.md'
    }, 'Patch must only target the five documentation entrypoints')
    require(patch.startswith('*** Begin Patch\n') and patch.endswith('*** End Patch\n'), 'Malformed patch markers')
    ready = [t['id'] for t in tasks if t['status'] != 'DONE' and all(task_map[d]['status'] == 'DONE' for d in t['depends_on'])]
    return {
        'documentation_contract': 'PASS', 'tasks': len(tasks), 'acceptance_gates': len(gates),
        'dependencies_acyclic': True, 'eligible_unfinished_tasks': ready,
        'completed_implementation_tasks': sum(t['status'] == 'DONE' for t in tasks),
        'workspace_sync_status': state['workspace_sync_status'],
        'runtime_tests_executed_by_this_validator': 0,
        'semantic_reviews_executed_by_this_validator': 0,
        'model_calls_executed_by_this_validator': 0,
        'patch_applied_by_this_validator': False,
        'scope': 'DOCUMENTATION_ONLY_NOT_PROJECT_ACCEPTANCE'
    }


class ContractTests(unittest.TestCase):
    root = DEFAULT_ROOT
    def setUp(self) -> None:
        self.s = load(self.root / 'TASK_STATE.json')
        self.m = load(self.root / 'ACCEPTANCE_MATRIX.json')
        # Test the contract using a fresh fixture, not the live completion state.
        self.s = copy.deepcopy(self.s)
        self.m = copy.deepcopy(self.m)
        for task in self.s['tasks']:
            task.update(status='READY' if not task['depends_on'] else 'PENDING', evidence=[])
        for gate in self.m['gates']:
            gate.update(status='NOT_RUN', evidence=[], checked_at=None, reviewer=None)
        self.s['completion'].update(build_scope_complete=False, product_acceptance_complete=False, independent_blind_acceptance='PENDING_EXTERNAL', true_natural_day_validation='PENDING_REAL_TIME')
    def invalid(self) -> None:
        with self.assertRaises((ValueError, KeyError, TypeError)):
            check(self.s, self.m, self.root)
    def test_fresh_document_contract(self) -> None:
        self.assertEqual(check(self.s, self.m, self.root)['completed_implementation_tasks'], 0)
    def test_unknown_dependency(self) -> None:
        self.s['tasks'][1]['depends_on'] = ['missing']; self.invalid()
    def test_cycle(self) -> None:
        self.s['tasks'][0]['depends_on'] = ['R044-02']; self.invalid()
    def test_duplicate_task(self) -> None:
        self.s['tasks'][1]['id'] = self.s['tasks'][0]['id']; self.invalid()
    def test_duplicate_gate(self) -> None:
        self.m['gates'][1]['id'] = self.m['gates'][0]['id']; self.invalid()
    def test_missing_gate(self) -> None:
        self.s['tasks'][0]['acceptance_gate'] = 'absent'; self.invalid()
    def test_done_without_evidence(self) -> None:
        self.s['tasks'][0]['status'] = 'DONE'; self.invalid()
    def test_pass_without_evidence(self) -> None:
        self.m['gates'][0]['status'] = 'PASS'; self.invalid()
    def test_false_build_completion(self) -> None:
        self.s['completion']['build_scope_complete'] = True; self.invalid()
    def test_false_product_acceptance(self) -> None:
        self.s['completion']['product_acceptance_complete'] = True; self.invalid()
    def test_static_not_semantic(self) -> None:
        self.m['gates'][0]['static_check_is_semantic_acceptance'] = True; self.invalid()
    def test_wrong_plan_binding(self) -> None:
        self.m['plan_id'] = 'R043_COMPLETE'; self.invalid()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    root = args.root.resolve()
    if args.self_test:
        ContractTests.root = root
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests))
        return 0 if result.wasSuccessful() else 1
    try:
        report = check(load(root / 'TASK_STATE.json'), load(root / 'ACCEPTANCE_MATRIX.json'), root)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'documentation_contract': 'FAIL', 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
