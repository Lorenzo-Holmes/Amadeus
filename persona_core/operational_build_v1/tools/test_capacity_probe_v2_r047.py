"""Re-run the real cloned diagnostic paths for the corrected worker contract."""
from __future__ import annotations
import capacity_probe_v2_r047 as revision
revision.verify_local_disposition()
revision.activate()
import test_capacity_probe_r047 as tests

if __name__ == '__main__':
    raise SystemExit(tests.main())
