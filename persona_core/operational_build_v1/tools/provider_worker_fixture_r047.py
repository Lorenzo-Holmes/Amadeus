"""Local-only worker protocol fixture. Never imports or calls an HTTP client."""
import json
import sys
import time

request = json.loads(sys.stdin.buffer.read().decode('utf-8'))
mode = sys.argv[1]
if mode == 'stall':
    time.sleep(5)
elif mode == 'invalid':
    sys.stdout.buffer.write(b'NOT_A_VALID_HTTP_STATUS\nfixture')
elif mode == 'error':
    raise SystemExit(2)
else:
    result = {'fixture': 'LOCAL_AUTHORED_WORKER_NO_NETWORK', 'payload': request['payload'],
              'deadline': request['timeout_seconds'], 'credential_passed_in_argv': len(sys.argv) != 2}
    sys.stdout.buffer.write(b'200\n' + json.dumps(result).encode('utf-8'))
    sys.stdout.buffer.flush()
