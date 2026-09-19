"""Mirror a real validation journal to the durable goal; never assign semantic PASS."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import uuid
import evaluation_runner as runner


def replace(path, value):
    temporary = path.with_name('.checkpoint_' + uuid.uuid4().hex + '.tmp')
    runner.write_new(temporary, value)
    os.replace(temporary, path)


def checkpoint(revision, state, next_action, blocker=None, task='G6-07', last_completed='G6-06'):
    root = runner.revision_root(revision)
    status = runner.status(revision)
    manifest, scope, _ = runner.read_contract(root)
    runner.require(manifest['capture_mode'] == runner.TARGET, 'TARGET_JOURNAL_REQUIRED')
    revision_cursor = runner.read(root / 'CURSOR.json')
    lease = runner.read(root / 'ACTIVE_RUN.json') if (root / 'ACTIVE_RUN.json').exists() else None
    active = bool(lease and runner.process_alive(lease['pid']))
    existing_goal = runner.read(runner.GOAL / 'GOAL_STATE.json')
    historical_unknown = existing_goal.get('IN_FLIGHT', {}).get('unresolved_requests', [])
    unresolved = {r['call_id']: r for r in historical_unknown}
    for row in revision_cursor.get('unresolved_requests', []):
        unresolved.setdefault(row['call_id'], row)
    unresolved = list(unresolved.values())
    in_flight = {'local_execution_active': active,
                 'revision_cursor': runner.relative(root / 'CURSOR.json'),
                 'external_effect': revision_cursor.get('in_flight_external_effect'),
                 'unresolved_requests': unresolved}
    entry = {'revision_id': revision, 'batch_id': scope['batch_id'],
             'journal': runner.relative(root / 'runtime/runtime.sqlite3'),
             'source_manifest_sha256': manifest['source_manifest_sha256'],
             'calls': status['recorded_calls'], 'captured_displayed': status['completed_slots'],
             'not_submitted': status['not_submitted'], 'unknown_count': status['unknown_count'],
             'guard_cny': scope['total_guard_cny'],
             'known_usage_estimate_cny': status['known_peak_usage_subtotal_micro_cny'] / 1e6,
             'total_usage_estimate_cny': status['known_peak_usage_subtotal_micro_cny'] / 1e6 if status['estimate_complete'] else None,
             'unknown_cost_reserve_cny': status['unknown_reserved_micro_cny'] / 1e6,
             'automatic_paid_retries': 0, 'billing_certified': False}
    ledger = runner.read(runner.GOAL / 'SPEND_LEDGER.json')
    batches = {b['revision_id']: b for b in ledger['batches']}
    batches[revision] = entry
    readiness = list({b['id']: b for b in ledger.get('readiness_batches', [])}.values())
    all_costs = list(batches.values()) + readiness
    ledger.update(batches=list(batches.values()), current_submitted_calls=sum(b['calls'] for b in all_costs),
                  known_usage_estimate=round(sum(b['known_usage_estimate_cny'] for b in all_costs), 6),
                  unknown_cost_reserve=round(sum(b['unknown_cost_reserve_cny'] for b in all_costs), 6),
                  total_usage_estimate_cny=(sum(b['total_usage_estimate_cny'] for b in batches.values())
                                           if not readiness and all(b['total_usage_estimate_cny'] is not None for b in batches.values()) else None),
                  updated_at_utc=runner.now())
    pending = [task + ' quote-bound semantic and quality review', 'G6-08 frozen 24/113/452',
               'G6-09 fresh original82/328', 'G6-10 candidate V2', 'G6-11 new blind package',
               'G6-12 actual external return', 'G6-13 new real dates 0/3', 'G6-14 product rollup']
    recovery = runner.relative(root / 'CURSOR.json')
    fields = {'LAST_COMPLETED': last_completed, 'CURRENT_STATE': state, 'NEXT_ACTION': next_action,
              'RECOVERY_POINT': recovery, 'BLOCKER': blocker, 'IN_FLIGHT': in_flight,
              'SPEND': entry, 'VALIDATION_PENDING': pending}
    cursor = runner.read(runner.GOAL / 'RECOVERY_CURSOR.json')
    cursor.update(fields, state='BLOCKED' if blocker else 'RUNNING', active_task=task,
                  last_completed_task=last_completed, next_action=next_action,
                  in_flight_external_effect=in_flight, safe_to_resume=status['safe_to_resume'] and not blocker,
                  active_revision=revision, updated_at_utc=runner.now())
    goal = runner.read(runner.GOAL / 'GOAL_STATE.json')
    goal.update(fields, state='BLOCKED' if blocker else 'RUNNING', current_state=state,
                active_task=task, active_revision=revision, role='VALIDATOR',
                product_acceptance_complete=False, production_activated=False,
                updated_at_utc=runner.now())
    graph = runner.read(runner.GOAL / 'TASK_GRAPH.json')
    graph.update(fields, updated_at_utc=runner.now())
    node = next(n for n in graph['tasks'] if n['id'] == task)
    node.update(status='BLOCKED' if blocker else 'IN_PROGRESS', active_revision=revision,
                blocker=blocker, recovery_point=recovery)
    for p in ('MANIFEST.json', 'CURSOR.json'):
        value = runner.relative(root / p)
        if value not in node['evidence']:
            node['evidence'].append(value)
    record = {'at_utc': runner.now(), **fields, 'journal_status': status,
              'canonical_updates': {'RECOVERY_CURSOR.json': cursor, 'GOAL_STATE.json': goal,
                                    'TASK_GRAPH.json': graph, 'SPEND_LEDGER.json': ledger}}
    target = runner.GOAL / 'checkpoints' / (uuid.uuid4().hex + '.json')
    runner.write_new(target, record)
    for name, value in record['canonical_updates'].items():
        replace(runner.GOAL / name, value)
    start, end = '<!-- G6_ACTIVE_START -->', '<!-- G6_ACTIVE_END -->'
    progress = runner.ROOT / 'PERSONA_CORE_PROGRESS.md'
    old = progress.read_text(encoding='utf-8-sig')
    if start in old:
        old = old.split(end, 1)[1].lstrip('\r\n')
    block = [start, '# APCORE-GPT6-OPTIMIZATION-V2 — current durable checkpoint', '']
    for key, value in fields.items():
        block += [key + ': ' + (json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value), '']
    block += ['Historical repair44/full82 and natural days are not current G6 evidence. '
              'R005 provenance closure remains NOT_ENOUGH_EVIDENCE. '
              'PRODUCT_ACCEPTANCE_COMPLETE=false; production_activated=false.', '', end, '']
    temp = progress.with_name('.progress_' + uuid.uuid4().hex + '.tmp')
    runner.write_bytes_new(temp, ('\n'.join(block) + '\n' + old).encode('utf-8'))
    os.replace(temp, progress)
    return {'checkpoint': runner.relative(target), 'state': state, 'blocker': blocker,
            'calls': status['recorded_calls'], 'completed': status['completed_slots']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--next-action', required=True)
    parser.add_argument('--blocker')
    args = vars(parser.parse_args())
    print(json.dumps(checkpoint(**args)))
