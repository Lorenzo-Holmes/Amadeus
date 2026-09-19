from __future__ import annotations
import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def rd(n): return json.loads((ROOT/n).read_text(encoding="utf-8"))
class Tests(unittest.TestCase):
 def test_persona(self):
  p=rd("PERSONA_CONSTITUTION_FROZEN_R034.json"); self.assertEqual(p["status"],"FROZEN_PERSONA_CONSTITUTION"); self.assertEqual(len(p["behavior_clauses"]),10); self.assertTrue(p["gates"]["persona_constitution_frozen"]); self.assertFalse(p["formation_policy"]["causal_formation_approved"])
 def test_source(self):
  s=rd("SOURCE_IDENTITY_FROZEN_R034.json"); self.assertEqual(s["source_snapshot_id"],"KURISU_V03_SG0_GAME_MARCH_2010"); self.assertEqual(s["known_cutoff_month"],"2010-03"); self.assertIsNone(s["exact_cutoff_day"]); self.assertFalse(s["route_merge_allowed"])
 def test_memory(self):
  m=rd("MEMORY_ADMISSION_FROZEN_R034.json"); rc=next(x for x in m["decision_records"] if x["id"]=="RC-R005-001"); self.assertEqual(rc["decision"],"ADMIT_AT_GENESIS"); self.assertFalse(rc["installed"]); self.assertEqual(len(m["claim_level_holds"]),4)
 def test_contracts(self):
  for n in ("SELF_MODEL_FROZEN_R034.json","AFFECT_MODEL_FROZEN_R034.json","RELATIONSHIP_MODEL_FROZEN_R034.json","DECISION_MODEL_FROZEN_R034.json"):
   x=rd(n); self.assertEqual(x["authority"],"FROZEN_CONTRACT"); self.assertFalse(x["model_output_direct_write_allowed"]); self.assertFalse(x["runtime_installed"])
 def test_product_boundary_separate(self):
  b=rd("PRODUCT_BOUNDARY_FROZEN_R034.json"); self.assertFalse(b["persona_trait"]); self.assertFalse(b["model_output_permission_authority"])
 def test_unknowns_preserved(self): self.assertTrue(rd("FREEZE_MANIFEST_R034.json")["unknowns_preserved"])
 def test_not_installed(self):
  m=rd("FREEZE_MANIFEST_R034.json"); self.assertFalse(m["genesis_approved"]); self.assertFalse(m["runtime_installed"])
if __name__=="__main__":unittest.main(verbosity=2)
