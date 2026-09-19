"""Run the eight unconsumed R045 slots through four actual CLI processes.

No retry of a consumed slot, even on a nonzero child exit. All writes stay in
the existing sandbox or a uniquely named evidence directory in this project.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / 'persona_core/operational_build_v1'
HOME = PLAN / 'evidence/R045-03/live_01'
SCOPE = PLAN / 'evidence/R045-03/LIVE_BATCH_SCOPE.json'
CODE = ROOT / 'persona_core/operational_runtime_v1'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    scope = json.loads(SCOPE.read_text(encoding='utf-8'))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = PLAN / 'evidence/R045-04' / ('live_cli_' + stamp)
    out.mkdir(parents=True, exist_ok=False)
    production = {p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT / 'persona_core/runtime').rglob('*') if p.is_file()}
    report = {'at_utc': datetime.now(timezone.utc).isoformat(), 'scope_sha256': sha(SCOPE),
              'stages': [], 'automatic_paid_retries': 0, 'semantic_review': 'NOT_PERFORMED'}
    with zipfile.ZipFile(out / 'EXECUTED_SOURCE.zip', 'x', zipfile.ZIP_DEFLATED) as z:
        for p in list(CODE.glob('*.py')) + [Path(__file__), SCOPE]:
            z.writestr(p.relative_to(ROOT).as_posix(), p.read_bytes())
    report['source_snapshot_sha256'] = sha(out / 'EXECUTED_SOURCE.zip')
    def journal():
        db = sqlite3.connect((HOME / 'runtime.sqlite3').as_uri() + '?mode=ro', uri=True)
        db.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in db.execute('SELECT p.slot_id,p.status,t.status AS turn_status,p.call_id FROM provider_calls p JOIN turns t USING(turn_id) WHERE p.batch_id=?', (scope['batch_id'],))]
        finally:
            db.close()
    try:
        rows = journal()
        assert any(r['slot_id'] == 'adapter_check' and r['status'] == 'RESPONSE_CAPTURED' for r in rows)
        assert all(r['status'] == 'RESPONSE_CAPTURED' for r in rows), 'Failed/unknown call: no more paid slots'
        for phase, label, ids in [('A_initial', 'SYNTHETIC_A', ['A1','A2','A3']),
                                  ('B_initial', 'SYNTHETIC_B', ['B1','B2','B3']),
                                  ('A_reopened', 'SYNTHETIC_A', ['A4']),
                                  ('B_reopened', 'SYNTHETIC_B', ['B4'])]:
            consumed = {r['slot_id']: r for r in journal()}
            assert all(r['status'] == 'RESPONSE_CAPTURED' for r in consumed.values())
            if all(i in consumed and consumed[i]['turn_status'] == 'DISPLAYED' for i in ids):
                report['stages'].append({'phase': phase, 'status': 'PREVIOUSLY_COMPLETED_NOT_REPLAYED'})
                continue
            assert not any(i in consumed for i in ids), 'Partial phase must be reconciled, never blindly rerun'
            texts = [next(s['user_text'] for s in scope['slots'] if s['id'] == i) for i in ids]
            command = [sys.executable, '-B', str(CODE / 'chat_cli.py'), '--root', str(HOME),
                       '--scope', str(SCOPE), '--entity', label, '--principal', scope['principal_id']]
            stage = {'phase': phase, 'slots': ids, 'started_at_utc': datetime.now(timezone.utc).isoformat(),
                     'command': command, 'status': 'PROCESS_START_INTENT'}
            report['stages'].append(stage)
            (out / (phase + '_INTENT.json')).write_text(json.dumps(stage, indent=2), encoding='utf-8')
            print('RUNNING ' + phase, flush=True)
            result = subprocess.run(command, cwd=ROOT, input=('\n'.join(texts + ['/exit']) + '\n').encode('utf-8'),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (out / (phase + '_stdout.txt')).write_bytes(result.stdout)
            (out / (phase + '_stderr.txt')).write_bytes(result.stderr)
            stage.update(exit_code=result.returncode, finished_at_utc=datetime.now(timezone.utc).isoformat(), status='PROCESS_EXITED')
            print('EXIT ' + phase + ' ' + str(result.returncode), flush=True)
            assert result.returncode == 0, 'CLI failed; preserve captures and stop this batch'
        report['calls'] = journal()
        report['all_eight_displayed'] = all(any(r['slot_id'] == i and r['turn_status'] == 'DISPLAYED' for r in report['calls']) for i in ['A1','A2','A3','A4','B1','B2','B3','B4'])
        assert report['all_eight_displayed']
    finally:
        after = {p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT / 'persona_core/runtime').rglob('*') if p.is_file()}
        report['production_unchanged'] = after == production
        (out / 'EXECUTION.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'output': out.relative_to(ROOT).as_posix(), 'production_unchanged': after == production}), flush=True)

if __name__ == '__main__':
    main()
