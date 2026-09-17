from __future__ import annotations
import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; PROJECT=ROOT.parent.parent; RUNTIME=PROJECT/"persona_core"/"runtime"
def rd(path): return json.loads(path.read_text(encoding="utf-8"))
class Tests(unittest.TestCase):
 def test_genesis(self):
  g=rd(RUNTIME/"genesis"/"GENESIS_SNAPSHOT_R035.json"); self.assertEqual(g["status"],"GENESIS_FROZEN_AND_INSTALLED"); self.assertTrue(g["genesis_approved"]); self.assertTrue(g["runtime_installed"]); self.assertEqual(g["source_snapshot_id"],"KURISU_V03_SG0_GAME_MARCH_2010")
 def test_memory_scope(self):
  g=rd(RUNTIME/"genesis"/"GENESIS_SNAPSHOT_R035.json"); self.assertEqual([x["id"] for x in g["encoded_autobiographical_memory"]],["RC-R005-001"]); self.assertEqual(len(g["claim_level_holds"]),4)
 def test_user_relationship_empty(self): self.assertEqual(rd(RUNTIME/"RELATIONSHIP_STATE.json")["product_entities"],{})
 def test_capabilities(self):
  c=rd(RUNTIME/"SELF_STATE.json")["capabilities"]; self.assertTrue(c["text_response"]); self.assertFalse(c["body"]); self.assertEqual(c["external_tools"],[]); self.assertFalse(c["physical_item_delivery"])
 def test_affect_baseline(self): self.assertTrue(all(v==0.0 for v in rd(RUNTIME/"AFFECT_STATE.json")["deviation_from_baseline"].values()))
 def test_ledger(self):
  rows=[json.loads(x) for x in (RUNTIME/"EXPERIENCE_LEDGER.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]; self.assertEqual(len(rows),1); self.assertEqual(rows[0]["event_type"],"GENESIS_EVENT"); self.assertFalse(rows[0]["source_memory_write"]); self.assertFalse(rows[0]["persona_write"])
 def test_meta(self):
  m=rd(RUNTIME/"RUNTIME_META.json"); self.assertTrue(m["runtime_installed"]); self.assertEqual(m["next_sequence"],1); self.assertFalse(m["model_output_direct_state_write_allowed"]); self.assertFalse(m["source_mutation_allowed"])
 def test_frozen_copies(self):
  g=rd(RUNTIME/"genesis"/"GENESIS_SNAPSHOT_R035.json");
  for rec in g["frozen_components"]:
   p=PROJECT/rec["path"]; self.assertTrue(p.exists()); self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),rec["sha256"])
if __name__=="__main__": unittest.main(verbosity=2)
