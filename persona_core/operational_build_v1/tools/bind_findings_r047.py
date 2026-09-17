"""Bind authored findings to literal captured spans; never generate verdicts."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'persona_core/operational_runtime_v1'))
from transcript_store import ensure


def bind(document, audit):
    ensure(document.get('reviewer') == 'CURRENT_SESSION_DEVELOPER_NONBLIND', 'Reviewer identity missing')
    ensure(audit.get('binding_checks_passed') is True, 'Capture audit binding failed')
    by_slot = {r['slot_id']: r for r in audit['records']}
    ensure(len(by_slot) == len(audit['records']) == audit['frozen_denominator'], 'Capture denominator mismatch')
    output, seen = [], set()
    for finding in document['findings']:
        ensure(finding['id'] not in seen and finding.get('rationale'), 'Finding missing rationale or duplicate ID')
        seen.add(finding['id'])
        ensure(finding['status'] == 'OPEN', 'Pre-repair findings cannot be closed by this binder')
        ensure(finding['severity'] in {'CRITICAL', 'MAJOR', 'MINOR'}, 'Unknown severity')
        ensure(finding.get('evidence'), 'Finding has no evidence')
        evidence = []
        for item in finding['evidence']:
            row = by_slot.get(item['slot_id'])
            ensure(row is not None and row['status'] == 'RESPONSE_CAPTURED' and row['turn_status'] == 'DISPLAYED', 'Not a displayed capture')
            ensure(isinstance(item.get('quote'), str) and item['quote'].strip() and item['quote'] in row['answer'], 'Quote is not a literal answer span')
            ensure(hashlib.sha256(row['answer'].encode('utf-8')).hexdigest() == row['answer_sha256'], 'Answer hash mismatch')
            evidence.append({**item, **{k: row[k] for k in ('call_id', 'request_sha256', 'answer_sha256', 'raw_response_sha256')}})
        output.append({**finding, 'evidence': evidence})
    return {'findings': output, 'findings_bound': len(output), 'quotes_bound': sum(len(f['evidence']) for f in output),
            'mechanical_binding_only': True, 'semantic_verdicts_generated': False,
            'full_criterion_review_complete': False, 'gate_passed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('notes', type=Path)
    args = parser.parse_args()
    notes = args.notes.resolve()
    ensure(notes.is_relative_to(ROOT), 'Notes must be inside project')
    document = json.loads(notes.read_text(encoding='utf-8'))
    audit_path = (ROOT / document['audit']).resolve()
    ensure(audit_path.is_relative_to(ROOT), 'Audit must be inside project')
    result = bind(document, json.loads(audit_path.read_text(encoding='utf-8')))
    result.update(notes_sha256=hashlib.sha256(notes.read_bytes()).hexdigest(),
                  audit_sha256=hashlib.sha256(audit_path.read_bytes()).hexdigest())
    out = notes.parent / ('BOUND_PRIOR_FINDINGS_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    with out.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'output': out.relative_to(ROOT).as_posix(), 'findings': result['findings_bound'], 'quotes': result['quotes_bound'], 'gate_passed': False}))


if __name__ == '__main__':
    main()
