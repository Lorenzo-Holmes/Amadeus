"""A new fixed diagnostic after the actual child-process contract was repaired.

The previous UNKNOWN row and stopped flag remain untouched. An immutable local
source-bound reconciliation explains why that attempt could not reach HTTP;
this is not a remote receipt. The new batch runs only in a fresh clone.
"""
from __future__ import annotations
import sys
import capacity_probe_r047 as base

OLD = base.REV
PROOF = OLD / 'local_reconciliation_20260911T024206815047Z/RECONCILIATION.json'
PROOF_DIR = PROOF.parent


def verify_local_disposition():
    proof = base.common.read_json(PROOF)
    base.ensure(proof['call_id'] == 'call_65df5a4dbb844432bdad8e63a8c68db5', 'Wrong local attempt disposition')
    base.ensure(proof['disposition'] == 'LOCAL_PRE_HTTP_CONFIGURATION_REJECTION_DETERMINISTICALLY_RECONCILED', 'Local attempt is not reconciled')
    base.ensure(proof['original_status_rewritten'] is False and proof['old_batch_stays_stopped'] is True and proof['old_slot_may_be_retried'] is False,
                'Historical unknown/stop flags must remain intact')
    base.ensure(base.common.file_sha(base.ROOT / proof['journal']) == proof['journal_sha256'], 'The preserved old journal changed')
    base.ensure(base.common.file_sha(PROOF_DIR / 'BOUND_ORIGINAL_WORKER.py') == proof['worker_bound_sha256'], 'Bound old worker changed')
    base.ensure(base.common.file_sha(PROOF_DIR / 'BOUND_ORIGINAL_PROVIDER.py') == proof['provider_bound_sha256'], 'Bound old provider changed')
    result = proof['controlled_process_result']
    base.ensure(result['worker_exit_code'] == 2 and result['transport_attempts'] == 0 and result['socket_events'] == [], 'Required local replay evidence absent')
    return {'path': PROOF.relative_to(base.ROOT).as_posix(), 'sha256': base.common.file_sha(PROOF),
            'scope': 'LOCAL_DETERMINISTIC_PRE_HTTP_REJECTION_NOT_REMOTE_RECEIPT',
            'historical_unknown_row_retained': True}


def activate():
    base.REV = base.PLAN / 'evidence/R047-03/capacity_probe_02'
    base.LIVE = base.REV / 'live'
    base.BATCH = 'APCORE-R047-CAPACITY-PROBE-02'
    base.AGGREGATE_GUARD = 256.5


def main():
    proof = verify_local_disposition()
    activate()
    if len(sys.argv) > 1 and sys.argv[1] == 'prepare':
        result = base.main()
        base.dump(base.REV / 'PREVIOUS_LOCAL_FAILURE_DISPOSITION.json', proof)
        return result
    pinned = base.common.read_json(base.REV / 'PREVIOUS_LOCAL_FAILURE_DISPOSITION.json')
    base.ensure(pinned == proof, 'Pinned predecessor disposition changed')
    return base.main()


if __name__ == '__main__':
    raise SystemExit(main())
