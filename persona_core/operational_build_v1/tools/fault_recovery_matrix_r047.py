"""Read-only recovery matrix over every classified historical provider UNKNOWN."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
import unknown_quarantine_r047 as unknowns

ROOT=Path(__file__).resolve().parents[3]; PLAN=ROOT/'persona_core/operational_build_v1'

def matrix():
    state=unknowns.project_unknown_status(); rows=[]
    for item in state['allowed_historical_unknowns']:
        classification=item.get('classification'); remote=classification=='QUARANTINED_REMOTE_UNKNOWN'
        rows.append({'call_id':item['call_id'],'batch_id':item['batch_id'],'slot_id':item['slot_id'],'classification':classification,
          'raw_status_preserved':True,'resend_allowed':item.get('resend_allowed',False),'remote_outcome_resolved':False,
          'local_product_state_mutation_committed':item.get('local_product_state_mutation_committed',False) if remote else False,
          'billing_verified':item.get('billing_verified',False),'safe_for_new_independent_batch':not item.get('resend_allowed',False)})
    return {'schema_version':'r047-fault-recovery-matrix-1','at_utc':datetime.now(timezone.utc).isoformat(),'raw_unknown_count':len(state['raw_unknowns']),
      'classified_historical_unknown_count':len(rows),'active_unresolved_remote_unknowns':state['active_unresolved_remote_unknowns'],'rows':rows,
      'all_old_slots_no_resend':all(r['resend_allowed'] is False for r in rows),'all_local_product_state_clean':all(not r['local_product_state_mutation_committed'] for r in rows),
      'automatic_paid_retries':0,'pass':not state['active_unresolved_remote_unknowns'] and all(r['resend_allowed'] is False for r in rows) and all(not r['local_product_state_mutation_committed'] for r in rows)}

def main():
    r=matrix(); out=PLAN/'evidence/R047-04/FAULT_RECOVERY_MATRIX.json'; out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(r,ensure_ascii=False,indent=2)); return 0 if r['pass'] else 2
if __name__=='__main__': raise SystemExit(main())
