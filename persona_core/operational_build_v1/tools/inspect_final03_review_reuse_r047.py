"""Read-only helper: compare prior explicit review quotes with final03 captures.

This tool never generates semantic verdicts and never edits evidence. It only
reports whether an exact quote used by a prior human review is still present in
the corresponding final03 answer, so stale review text cannot be silently
reused as acceptance evidence.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / 'persona_core/operational_build_v1'
DB = PLAN / 'evidence/R047-03/final_full82_03/live/runtime.sqlite3'

REVIEW_SOURCES = {
    'N01': PLAN / 'evidence/R047-03/epistemic_probe_01/reviews/N01.json',
    'N02': PLAN / 'evidence/R047-03/epistemic_probe_01/reviews/N02.json',
    'N03': PLAN / 'evidence/R047-03/repair_06/reviews/N03.json',
    'N04': PLAN / 'evidence/R047-03/repair_06/reviews/N04.json',
    'N05': PLAN / 'evidence/R047-03/repair_06/reviews/N05.json',
    'N06': PLAN / 'evidence/R047-03/epistemic_probe_04/reviews/N06.json',
    'N07': PLAN / 'evidence/R047-03/epistemic_probe_02/reviews/N07.json',
    'N08': PLAN / 'evidence/R047-03/epistemic_probe_03/reviews/N08.json',
    'N09': PLAN / 'evidence/R047-03/repair_06/reviews/N09.json',
    'N10': PLAN / 'evidence/R047-03/repair_06/reviews/N10.json',
    'N11': PLAN / 'evidence/R047-03/epistemic_probe_03/reviews/N11.json',
    'N12': PLAN / 'evidence/R047-03/repair_06/reviews/N12.json',
}


def main() -> int:
    db = sqlite3.connect(DB.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        answers = {
            row['slot_id']: row['assistant_text'] or ''
            for row in db.execute(
                'SELECT p.slot_id,t.assistant_text FROM provider_calls p '
                'JOIN turns t USING(turn_id) ORDER BY p.submitted_at_utc'
            )
        }
    finally:
        db.close()
    report = {}
    for case_id, path in REVIEW_SOURCES.items():
        note = json.loads(path.read_text(encoding='utf-8'))
        total = 0
        matched = 0
        missing = []
        for turn in note['turn_reviews']:
            answer = answers.get(turn['slot_id'], '')
            for item in turn['judgments']:
                quote = item[1] if isinstance(item, list) else item['quote']
                total += 1
                if quote in answer:
                    matched += 1
                else:
                    missing.append({'slot_id': turn['slot_id'], 'quote': quote})
        report[case_id] = {
            'source': path.relative_to(ROOT).as_posix(),
            'matched_quotes': matched,
            'total_quotes': total,
            'all_quotes_match': matched == total,
            'missing': missing,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
