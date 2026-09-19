"""One HTTP operation for a host-owned provider deadline worker.

Receives credentials only through inherited stdin, never CLI arguments or files.
Writes status plus bounded raw body to the private parent pipe, not user output.
No retry, no tool execution and no runtime database access.
"""
from __future__ import annotations
import json
import hashlib
import math
import sys
from provider import (official_transport, MAX_RESPONSE_BYTES, MAX_WORKER_TIMEOUT_SECONDS,
                      WORKER_LOCAL_REJECTION_HEADER, WORKER_REMOTE_UNKNOWN_HEADER, canonical,
                      network_error_details)
from transcript_store import ensure
from provider_transport import check_policy, child_result
from provider_network_route import check_route_policy

def main() -> int:
    raw = b''
    try:
        raw = sys.stdin.buffer.read(250001)
        ensure(len(raw) <= 250000, 'Worker input too large')
        request = json.loads(raw.decode('utf-8'))
        base = {'payload', 'credential', 'timeout_seconds'}
        ensure(isinstance(request, dict) and set(request) in (base, base | {'transport_policy'},
               base | {'transport_policy', 'operation'}, base | {'transport_policy','network_route_policy'},
               base | {'transport_policy','operation','network_route_policy'}), 'Invalid worker contract')
        ensure(isinstance(request['payload'], str) and isinstance(request['credential'], str), 'Invalid worker data')
        ensure(type(request['timeout_seconds']) in {int, float} and math.isfinite(request['timeout_seconds'])
               and 0 < request['timeout_seconds'] <= MAX_WORKER_TIMEOUT_SECONDS, 'Invalid worker timeout')
        if 'transport_policy' in request:
            check_policy(request['transport_policy'], request['timeout_seconds'])
        if 'network_route_policy' in request:
            check_route_policy(request['network_route_policy'])
        if 'operation' in request:
            ensure(request['operation'] in {'CATALOGUE', 'RESPONSES'}, 'Invalid worker operation')
    except Exception as exc:
        # This branch is strictly before the HTTP call. The receipt is bound to
        # the private input frame; no credential or payload is echoed.
        receipt = {'stage': 'INPUT_VALIDATION', 'network_attempted': False,
                   'frame_sha256': hashlib.sha256(raw).hexdigest(), 'error_class': type(exc).__name__}
        sys.stdout.buffer.write(WORKER_LOCAL_REJECTION_HEADER + canonical(receipt))
        sys.stdout.buffer.flush()
        return 2
    if 'transport_policy' in request:
        output = child_result(request, hashlib.sha256(raw).hexdigest())
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
        return 0
    try:
        status, body = official_transport(request['payload'].encode('utf-8'), request['credential'],
                                          timeout_seconds=request['timeout_seconds'], hard_deadline=False)
        ensure(len(body) <= MAX_RESPONSE_BYTES + 1, 'Worker response exceeds capture bound')
        sys.stdout.buffer.write(str(status).encode('ascii') + b'\n' + body)
        sys.stdout.buffer.flush()
        return 0
    except Exception as exc:
        # The HTTP path was entered, so the remote outcome must remain unknown.
        # Emit only a frame-bound, credential-free diagnostic receipt.
        receipt = {'stage': 'HTTP_CALL_OR_RESPONSE_READ', 'network_phase_entered': True,
                   'remote_outcome_known': False, 'frame_sha256': hashlib.sha256(raw).hexdigest(),
                   'error_class': type(exc).__name__, 'network_error': network_error_details(exc)}
        sys.stdout.buffer.write(WORKER_REMOTE_UNKNOWN_HEADER + canonical(receipt))
        sys.stdout.buffer.flush()
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
