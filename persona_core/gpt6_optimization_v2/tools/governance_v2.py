"""Offline governance primitives. This module never imports or invokes a provider.

It classifies evidence, selects tests, verifies pinned byte manifests, and writes
versioned orchestration checkpoints. Historical scientific verdicts are inputs,
not writable state. Existing V1 writers are not silently migrated by this tool.
"""
from __future__ import annotations

import argparse
from fnmatch import fnmatchcase
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
G6 = 'persona_core/gpt6_optimization_v2'
CANONICAL = G6 + '/CANONICAL_MACHINE_STATE.json'
POLICY = G6 + '/CODEX_EXECUTION_POLICY.json'
MATRIX = G6 + '/TEST_INVALIDATION_MATRIX.json'
HEX = re.compile(r'^[0-9a-f]{64}$')
INVARIANTS = {'turns': 44, 'criteria': 176, 'gate_a': 176, 'gate_b': 132}


class GovernanceError(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise GovernanceError(code)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'DUPLICATE_JSON_KEY')
        value[key] = item
    return value


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(GovernanceError('NONFINITE_JSON')))


def local_path(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and bool(relative), 'PATH_REQUIRED')
    p = PurePosixPath(relative)
    require(not p.is_absolute() and '..' not in p.parts and '\\' not in relative
            and ':' not in relative and p.as_posix() == relative, 'UNSAFE_RELATIVE_PATH')
    resolved = (root / relative).resolve()
    require(resolved.is_relative_to(root.resolve()), 'PATH_ESCAPES_WORKSPACE')
    return resolved


def reference(root: Path, relative: str) -> dict:
    return {'path': relative, 'sha256': sha(local_path(root, relative).read_bytes())}


def verify_reference(root: Path, ref: dict) -> Path:
    require(isinstance(ref, dict) and HEX.fullmatch(str(ref.get('sha256', ''))) is not None,
            'UNPINNED_REFERENCE')
    path = local_path(root, ref['path'])
    require(sha(path.read_bytes()) == ref['sha256'], 'REFERENCE_HASH_MISMATCH')
    return path


def pinned_json(root: Path, ref: dict) -> Any:
    return load(verify_reference(root, ref))


def validate_policy(policy: dict) -> None:
    require(policy.get('schema_version') == 'APCORE_CODEX_GOVERNANCE_2_1', 'UNSUPPORTED_POLICY_VERSION')
    inv = policy.get('scientific_invariants', {})
    require(all(type(inv.get(k)) is int and inv[k] == v for k, v in INVARIANTS.items()),
            'SCIENTIFIC_DENOMINATOR_CHANGED')
    for key in ('unknown_auto_resend', 'provider_auto_retry', 'retry_until_pass',
                'historical_raw_overwrite', 'historical_revision_rewrite'):
        require(inv.get(key) is False, 'PROTECTED_BOUNDARY_CHANGED')
    cap = policy.get('draw_policy', {}).get('maximum_harness_replacements_per_lineage')
    require(type(cap) is int and cap == 1, 'REPLACEMENT_CAP_CHANGED')
    require(policy.get('task_authorization', {}).get('paid_validation_allowed') is False,
            'THIS_TASK_IS_OFFLINE_ONLY')


def classify_failure(facts: dict) -> dict:
    """Severity and observed consequences outrank a caller-supplied layer label."""
    counts = ('critical', 'model_blocking_major', 'state_integrity_major', 'quality_unclear')
    flags = ('benchmark_contamination', 'unauthorized_state_promotion',
             'rubric_unchanged', 'evidence_preserved', 'source_identity_confirmed',
             'all_affected_requests_audited', 'local_defect_proven')
    if not all(type(facts.get(k)) is int and facts[k] >= 0 for k in counts) or not all(
            type(facts.get(k)) is bool for k in flags):
        return {'action': 'HARD_STOP', 'reason': 'INSUFFICIENT_CLASSIFICATION_EVIDENCE',
                'paid_requests_allowed': False}
    for key in ('critical', 'model_blocking_major', 'state_integrity_major',
                'benchmark_contamination', 'unauthorized_state_promotion'):
        if facts[key]:
            return {'action': 'HARD_STOP', 'reason': key.upper(), 'paid_requests_allowed': False}
    if facts.get('provider_outcome') not in ('TERMINAL_KNOWN', 'NOT_SUBMITTED'):
        return {'action': 'HARD_STOP', 'reason': 'PROVIDER_UNKNOWN_OR_AMBIGUOUS',
                'paid_requests_allowed': False}
    if not all(facts[k] for k in ('rubric_unchanged', 'evidence_preserved',
                                 'source_identity_confirmed', 'all_affected_requests_audited')):
        return {'action': 'HARD_STOP', 'reason': 'INTEGRITY_NOT_ESTABLISHED', 'paid_requests_allowed': False}
    local = {'EVALUATOR', 'DRIVER', 'LOCAL_TEST', 'SERIALIZER', 'ACCOUNTING',
             'DB_PROJECTION', 'RECEIPT_READER', 'PRE_FLIGHT_IMPLEMENTATION', 'LOCAL_SCHEMA_PLUMBING'}
    if facts.get('failure_layer') in local and facts['local_defect_proven']:
        return {'action': 'LOCAL_REPAIR_CONTINUE', 'reason': 'PROVEN_LOCAL_DEFECT',
                'paid_requests_allowed': False,
                'replacement_review_required': facts['quality_unclear'] != 0}
    return {'action': 'MILESTONE_PAUSE', 'reason': 'CLASSIFICATION_OR_DECISION_REQUIRED',
            'paid_requests_allowed': False}


def replacement_blockers(facts: dict, checks: dict, lineage: dict, policy: dict) -> list[str]:
    """Diagnostic only. An empty list would still not invoke a model or allocate a revision."""
    blockers = []
    if classify_failure(facts)['action'] != 'LOCAL_REPAIR_CONTINUE':
        blockers.append('NOT_A_QUALIFIED_HARNESS_DEFECT')
    if facts.get('quality_unclear') != 0:
        blockers.append('UNRESOLVED_QUALITY_OBSERVATION')
    required = ('targeted_pass', 'affected_pass', 'completed_row_path_pass', 'full_suite_pass',
                'source_freeze_match', 'zero_provider_preflight_ready',
                'all_observed_quality_adjudicated', 'model_and_prompt_unchanged',
                'output_independent_defect', 'retrospective_exception_disclosed',
                'evidence_references_verified')
    blockers.extend(k.upper() for k in required if checks.get(k) is not True)
    if not isinstance(lineage.get('root_id'), str) or not lineage['root_id']:
        blockers.append('MISSING_IMMUTABLE_LINEAGE')
    used = lineage.get('replacement_allocations')
    if type(used) is not int or used < 0 or used >= 1:
        blockers.append('REPLACEMENT_CAP_REACHED_OR_UNKNOWN')
    if policy.get('task_authorization', {}).get('paid_validation_allowed') is not True:
        blockers.append('NO_PAID_VALIDATION_AUTHORIZATION_IN_THIS_TASK')
    return blockers


def plan_tests(paths: list[str], matrix: dict, *, milestone: bool = False) -> dict:
    selected = set(matrix['always_tests'])
    full = milestone
    legacy = False
    unknown = []
    protected = []
    for relative in paths:
        local_path(ROOT, relative)
        if any(fnmatchcase(relative, pattern) for pattern in matrix['protected_patterns']):
            protected.append(relative)
            continue
        if relative.startswith(G6 + '/tools/test_') and relative.endswith('.py'):
            selected.add(PurePosixPath(relative).name)
        matched = False
        for rule in matrix['rules']:
            if any(fnmatchcase(relative, pattern) for pattern in rule['patterns']):
                selected.update(rule['tests'])
                legacy = legacy or rule.get('legacy_required', False)
                full = full or (milestone and rule.get('freeze_full_suite', False))
                matched = True
        if not matched:
            unknown.append(relative)
            full = True
            legacy = True  # Unknown dependency coverage never means no test.
    return {'tests': sorted(selected), 'full_component_suite': full,
            'legacy_suite_or_dependency_review': legacy, 'unclassified_paths': unknown,
            'hard_stop_protected_paths': protected}


def verify_manifest(root: Path, ref: dict) -> dict:
    """Recompute leaf hashes on disk. A stored manifest's own hash is not tree integrity."""
    manifest = pinned_json(root, ref)
    files = manifest.get('files')
    require(type(files) is dict and bool(files), 'MANIFEST_HAS_NO_MEMBERS')
    mismatch = []
    current = {}
    for relative, expected in sorted(files.items()):
        require(HEX.fullmatch(str(expected)) is not None, 'INVALID_LEAF_DIGEST')
        path = local_path(root, relative)
        actual = sha(path.read_bytes()) if path.is_file() else None
        current[relative] = actual
        if actual != expected:
            mismatch.append(relative)
    additions = []
    for directory in manifest.get('closed_directories', []):
        base = local_path(root, directory)
        require(base.is_dir(), 'CLOSED_DIRECTORY_MISSING')
        for p in base.rglob('*'):
            if p.is_file():
                relative = p.relative_to(root).as_posix()
                local_path(root, relative)
                if relative not in files:
                    additions.append(relative)
    return {'status': 'MATCH' if not mismatch and not additions else 'MISMATCH',
            'member_count': len(files), 'expected_root': sha(canonical_bytes(files)),
            'observed_root': sha(canonical_bytes(current)),
            'mismatch_count': len(mismatch), 'changed_paths': mismatch[:30],
            'added_count': len(additions), 'added_paths': sorted(additions)[:30],
            'method': 'ACTUAL_LEAF_REHASH_NO_TRUSTED_CHANGE_JOURNAL_AVAILABLE'}


def immutable_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == data, 'IMMUTABLE_OBJECT_CONFLICT')
        return
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def public_view(payload: dict) -> dict:
    allowed = ('schema_version', 'status', 'active_task', 'mode', 'paid_requests_allowed',
               'next_action', 'migration_stage')
    result = {k: payload[k] for k in allowed if k in payload}
    if isinstance(payload.get('test_summary'), dict):
        result['test_summary'] = {k: v for k, v in payload['test_summary'].items()
                                  if k in ('tests_run', 'passed', 'failed', 'skipped')
                                  and type(v) is int and v >= 0}
    return result


def task_authorization(root: Path, payload: dict) -> dict:
    """An append-only task authorization cannot rewrite the offline policy."""
    require(isinstance(payload.get('task_authorization'), dict), 'PAID_STATE_WRITE_FORBIDDEN')
    auth = pinned_json(root, payload['task_authorization'])
    require(auth.get('kind') == 'POST_FAIL_PRODUCT_REPAIR_NEW_CANDIDATE'
            and auth.get('status') == 'PROJECT_COMPLETION_SPEND_AUTHORIZED_AS_NEEDED'
            and auth.get('source') == 'CURRENT_EXPLICIT_USER_REQUEST_20260921'
            and auth.get('task') == payload.get('active_task')
            and auth.get('candidate_id') == payload['draw_lineage']['candidate_id']
            and auth.get('paid_validation_allowed') is True
            and auth.get('max_fresh_revisions') == 1 and auth.get('max_generation_requests') == 44
            and auth.get('automatic_paid_retries') == auth.get('readiness_requests') == auth.get('count_api_requests') == 0
            and auth.get('fallback_allowed') is False
            and auth.get('replacement_draw') is False and auth.get('historical_draw_refunded') is False
            and auth.get('r18_preserved') is True and auth.get('r18_resume_replay_resend') is False,
            'TASK_AUTHORIZATION_MISMATCH')
    return auth


def validate_paid_state(root: Path, payload: dict) -> None:
    if payload.get('paid_requests_allowed') is False:
        return
    require(payload.get('paid_requests_allowed') is True, 'PAID_STATE_WRITE_FORBIDDEN')
    task_authorization(root, payload)
    require(payload.get('status') in {'READY_FOR_SINGLE_NEW_CANDIDATE_ATTEMPT', 'VALIDATING_NEW_CANDIDATE'}
            and payload.get('paid_validation_blockers') == [], 'PAID_GATE_BLOCKED')
    preflight = pinned_json(root, payload['preflight'])
    require(preflight.get('status') == 'READY'
            and preflight.get('kind') == 'ZERO_PROVIDER_FORMAL_BINDING_PREFLIGHT'
            and preflight.get('candidate_id') == payload['draw_lineage']['candidate_id']
            and preflight.get('denominators') == dict(turns=44, criteria=176, gate_a=176, gate_b=132)
            and preflight.get('source_manifest') == payload.get('source_freeze')
            and all(preflight.get(k) == 0 for k in ('provider_call_invocations', 'provider_call_rows',
                'generation_request_invocations', 'readiness_requests', 'token_count_request_invocations',
                'automatic_paid_retries', 'active_paid_driver_count')), 'PAID_PREFLIGHT_NOT_READY')
    receipt = pinned_json(root, payload['test_receipt'])
    freeze = pinned_json(root, payload['source_freeze'])
    require(receipt.get('status') == 'PASS' and receipt.get('source_files') == freeze['files']
            and verify_manifest(root, payload['source_freeze'])['status'] == 'MATCH'
            and all(r.get('exit_code') == 0 and r.get('tests', 0) > 0 and r.get('skipped') == 0
                    for r in receipt.get('results', [])) and bool(receipt.get('results')),
            'PAID_TESTED_SOURCE_MISMATCH')
    attempt = payload.get('formal_attempt', {})
    require(attempt.get('allocations') == 1 and isinstance(attempt.get('revision'), str)
            and bool(attempt['revision']) and attempt.get('kind') == 'POST_FAIL_PRODUCT_REPAIR_NEW_CANDIDATE',
            'SINGLE_NEW_CANDIDATE_ALLOCATION_REQUIRED')


def validate_new_lineage(root: Path, pointer: dict, old: dict, payload: dict) -> None:
    transition = payload.get('lineage_transition', {})
    require(transition.get('kind') == 'POST_FAIL_PRODUCT_REPAIR_NEW_CANDIDATE', 'DRAW_LINEAGE_CHANGED')
    auth = task_authorization(root, payload)
    require(transition.get('parent_checkpoint') == pointer.get('checkpoint') == auth.get('parent_checkpoint')
            and transition.get('parent_lineage') == old.get('draw_lineage')
            and payload.get('historical_lineages') == old.get('historical_lineages', []) + [old['draw_lineage']]
            and payload.get('r18') == old.get('r18') and bool(payload.get('r18'))
            and old.get('status') == 'HARD_STOP_REQUIRED_CONVERSATION_CRITERION_FAIL',
            'NEW_LINEAGE_PARENT_NOT_PRESERVED')
    new, previous = payload['draw_lineage'], old['draw_lineage']
    require(all(new[k] != previous[k] for k in ('root_id', 'candidate_id', 'configuration_sha256'))
            and new['benchmark_sha256'] == previous['benchmark_sha256']
            and new['replacement_allocations'] == 0
            and all(new['candidate_id'] != h['candidate_id'] for h in payload['historical_lineages']),
            'NEW_LINEAGE_NOT_NEW_PRODUCT')
    freeze = pinned_json(root, payload['source_freeze'])
    parent = pinned_json(root, old['source_freeze'])
    config = pinned_json(root, payload['configuration'])
    require(freeze.get('parent_manifest') == old['source_freeze']
            and payload['configuration']['sha256'] == new['configuration_sha256']
            and config.get('candidate_id') == new['candidate_id'], 'NEW_LINEAGE_SOURCE_CONFIGURATION_MISMATCH')
    implementation = config.get('generation_calibration', {}).get('implementation', {})
    verify_reference(root, implementation)
    require(freeze['files'].get(implementation['path']) == implementation['sha256']
            and parent['files'].get(implementation['path']) not in (None, implementation['sha256']),
            'NEW_LINEAGE_REQUIRES_REAL_PRODUCT_CHANGE')
    import zipfile
    archive = verify_reference(root, transition['parent_source_archive'])
    with zipfile.ZipFile(archive) as z:
        require(set(z.namelist()) == set(parent['files'])
                and all(sha(z.read(p)) == h for p, h in parent['files'].items()),
                'PARENT_SOURCE_ARCHIVE_MISMATCH')


def commit_state(root: Path, payload: dict, expected_current_sha: str) -> dict:
    """Single-writer CAS. Publish immutable generation first, then replace one pointer."""
    validate_paid_state(root, payload)
    require(all(payload.get('scientific_invariants', {}).get(k) == v for k, v in INVARIANTS.items()),
            'STATE_INVARIANT_MISMATCH')
    lineage = payload.get('draw_lineage', {})
    require(isinstance(lineage.get('root_id'), str) and bool(lineage['root_id'])
            and isinstance(lineage.get('candidate_id'), str) and bool(lineage['candidate_id'])
            and all(HEX.fullmatch(str(lineage.get(k, ''))) is not None
                    for k in ('configuration_sha256', 'benchmark_sha256'))
            and type(lineage.get('replacement_allocations')) is int
            and 0 <= lineage['replacement_allocations'] <= 1, 'INVALID_DRAW_LINEAGE')
    require(bool(payload.get('integrity_manifests')), 'NO_VERIFIED_INTEGRITY_ROOT')
    require(all(verify_manifest(root, ref)['status'] == 'MATCH' for ref in payload['integrity_manifests']),
            'STATE_EVIDENCE_INTEGRITY_MISMATCH')
    canonical = local_path(root, CANONICAL)
    require(HEX.fullmatch(expected_current_sha) is not None, 'EXPECTED_STATE_HASH_REQUIRED')
    lock = canonical.with_suffix('.lock')
    fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    temporary = canonical.with_suffix('.tmp')
    try:
        require(sha(canonical.read_bytes()) == expected_current_sha, 'STATE_CAS_CONFLICT')
        old_pointer = load(canonical)
        if old_pointer.get('schema_version') == 'APCORE_CANONICAL_POINTER_2_1':
            old = pinned_json(root, old_pointer['checkpoint'])
            previous_lineage = old.get('draw_lineage')
            if previous_lineage is not None:
                new_lineage = payload.get('draw_lineage', {})
                same = all(new_lineage.get(key) == previous_lineage.get(key)
                           for key in ('root_id', 'candidate_id', 'configuration_sha256', 'benchmark_sha256'))
                if not same:
                    validate_new_lineage(root, old_pointer, old, payload)
                else:
                    used = new_lineage.get('replacement_allocations')
                    require(type(used) is int and previous_lineage['replacement_allocations'] <= used <= 1,
                            'DRAW_COUNTER_RESET_OR_CAP_EXCEEDED')
                    prior_attempt = old.get('formal_attempt')
                    if prior_attempt:
                        attempt = payload.get('formal_attempt', {})
                        require(all(attempt.get(k) == prior_attempt.get(k) for k in ('allocations', 'revision', 'kind')),
                                'FORMAL_ATTEMPT_REPLACEMENT_FORBIDDEN')
                    for key in ('historical_lineages', 'lineage_transition'):
                        if key in old:
                            require(payload.get(key) == old[key], 'CANDIDATE_HISTORY_REWRITE_FORBIDDEN')
                    if 'lineage_transition' in old:
                        require(all(payload.get(k) == old.get(k) for k in ('r18', 'configuration', 'task_authorization')),
                                'CANDIDATE_IDENTITY_HISTORY_REWRITE_FORBIDDEN')
        policy_ref = reference(root, POLICY)
        validate_policy(pinned_json(root, policy_ref))
        data = canonical_bytes(payload)
        relative = G6 + '/governance_checkpoints/' + sha(data) + '/STATE_CHECKPOINT.json'
        checkpoint = local_path(root, relative)
        immutable_write(checkpoint, data)
        immutable_write(checkpoint.parent / 'PUBLIC_SUMMARY.json', canonical_bytes(public_view(payload)))
        pointer = {'schema_version': 'APCORE_CANONICAL_POINTER_2_1',
                   'policy': policy_ref, 'checkpoint': {'path': relative, 'sha256': sha(data)},
                   'previous_pointer_sha256': expected_current_sha,
                   'previous_checkpoint': old_pointer.get('checkpoint')}
        with temporary.open('xb') as stream:
            stream.write(canonical_bytes(pointer))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, canonical)
        return pointer
    finally:
        os.close(fd)
        lock.unlink()
        # A failed replace leaves the old pointer authoritative. Never rewrite checkpoints.
        if temporary.exists():
            temporary.unlink()


def resume(root: Path) -> dict:
    pointer = load(local_path(root, CANONICAL))
    require(pointer.get('schema_version') == 'APCORE_CANONICAL_POINTER_2_1', 'MIGRATION_NOT_COMPLETE')
    policy = pinned_json(root, pointer['policy'])
    validate_policy(policy)
    state = pinned_json(root, pointer['checkpoint'])
    validate_paid_state(root, state)
    for ref in policy.get('preserved_acceptance_references', []) + state.get('guidance_refs', []):
        verify_reference(root, ref)
    require(bool(state.get('integrity_manifests')), 'NO_VERIFIED_INTEGRITY_ROOT')
    integrity = [verify_manifest(root, ref) for ref in state['integrity_manifests']]
    require(all(r['status'] == 'MATCH' for r in integrity), 'DEEP_RECOVERY_REQUIRED')
    return {**public_view(state), 'checkpoint': pointer['checkpoint'],
            'paid_validation_blockers': state.get('paid_validation_blockers', []),
            'integrity': [{'status': r['status'], 'members': r['member_count'],
                           'root': r['observed_root']} for r in integrity]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('resume')
    plan = commands.add_parser('plan')
    plan.add_argument('paths', nargs='+')
    plan.add_argument('--milestone', action='store_true')
    verify = commands.add_parser('verify')
    verify.add_argument('path')
    verify.add_argument('--sha256', required=True)
    sync = commands.add_parser('sync')
    sync.add_argument('payload')
    sync.add_argument('--expected-current-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'resume':
        value = resume(ROOT)
    elif args.command == 'plan':
        value = plan_tests(args.paths, load(local_path(ROOT, MATRIX)), milestone=args.milestone)
    elif args.command == 'verify':
        value = verify_manifest(ROOT, {'path': args.path, 'sha256': args.sha256})
    else:
        value = commit_state(ROOT, load(local_path(ROOT, args.payload)), args.expected_current_sha256)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
