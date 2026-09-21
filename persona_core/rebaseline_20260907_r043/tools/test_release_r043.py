from __future__ import annotations
import hashlib,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; PROJECT=ROOT.parent.parent; RUNTIME=PROJECT/"persona_core"/"runtime"
def rd(p): return json.loads(p.read_text(encoding="utf-8"))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
class Tests(unittest.TestCase):
 def test_release_status(self):
  r=rd(RUNTIME/"RUNTIME_RELEASE_R043.json"); self.assertEqual(r["status"],"OPERATIONAL_PERSONA_CORE_COMPLETE"); self.assertEqual(r["release_id"],"AMADEUS-PERSONA-CORE-R043")
 def test_genesis_hash(self):
  r=rd(RUNTIME/"RUNTIME_RELEASE_R043.json"); self.assertEqual(r["genesis_sha256"],sha(RUNTIME/"genesis"/"GENESIS_SNAPSHOT_R035.json"))
 def test_only_genesis_in_production_ledger(self):
  rows=[json.loads(x) for x in (RUNTIME/"EXPERIENCE_LEDGER.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]; self.assertEqual(len(rows),1); self.assertEqual(rows[0]["event_type"],"GENESIS_EVENT")
 def test_no_product_relationships_yet(self): self.assertEqual(rd(RUNTIME/"RELATIONSHIP_STATE.json")["product_entities"],{})
 def test_memory(self):
  g=rd(RUNTIME/"genesis"/"GENESIS_SNAPSHOT_R035.json"); self.assertEqual([x["id"] for x in g["encoded_autobiographical_memory"]],["RC-R005-001"]); self.assertEqual(len(g["claim_level_holds"]),4)
 def test_capabilities(self):
  c=rd(RUNTIME/"SELF_STATE.json")["capabilities"]; self.assertFalse(c["body"]); self.assertEqual(c["external_tools"],[]); self.assertFalse(c["physical_item_delivery"])
 def test_runtime_loads(self):
  sys.path.insert(0,str(RUNTIME)); from runtime_core import PersonaRuntime; PersonaRuntime(RUNTIME)
 def test_pending_not_faked(self):
  r=rd(RUNTIME/"RUNTIME_RELEASE_R043.json"); self.assertTrue(r["post_release_validation_pending"]["independent_blind_acceptance"]); self.assertTrue(r["post_release_validation_pending"]["true_natural_day_longitudinal_runtime"])
if __name__=="__main__":unittest.main(verbosity=2)
