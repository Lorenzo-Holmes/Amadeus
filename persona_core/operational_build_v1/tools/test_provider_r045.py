"""R045-03 provider fault/budget tests. Fake transport never counts as API output."""
from __future__ import annotations
import copy
import json
import sys
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CODE = ROOT / "persona_core/operational_runtime_v1"
sys.path.insert(0, str(CODE))
from transcript_store import create_sandbox, TranscriptStore, StoreGuard, file_sha
from context_router import build_context
from provider import ProviderJournal, ENDPOINT, canonical, scope_check

OUT = ROOT / "persona_core/operational_build_v1/evidence/R045-03" / ("run_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
TEST_KEY = "AUTHORED_PROVIDER_TEST_SECRET_NOT_A_REAL_CREDENTIAL"

def scope():
    return {"batch_id":"AUTHORED_PROVIDER_TEST", "principal_id":"TEST_OPERATOR", "purpose":"Offline fault injection only",
        "endpoint":ENDPOINT,"automatic_paid_retries":0,"pricing_verified_date":"2026-09-07",
        "pricing_sources":["OFFLINE_FIXTURE"],"max_input_bytes":24576,"max_output_tokens":600,
        "input_overhead_reserve_tokens":4096,"total_guard_cny":1.0,"reserved_upper_micro_cny":182832,
        "slots":[{"id":"s1","model":"deepseek-v4-flash","entity_label":"SYNTHETIC_A","user_text":"测试问题"},
                 {"id":"s2","model":"deepseek-v4-flash","entity_label":"SYNTHETIC_A","user_text":"另一个测试问题"}]}

def body(text="明确标记的测试桩答复", finish="stop", model="deepseek-v4-flash"):
    return canonical({"model":model,"choices":[{"finish_reason":finish,"message":{"role":"assistant","content":text}}],
        "usage":{"prompt_tokens":100,"completion_tokens":20,"total_tokens":120,"prompt_cache_hit_tokens":40,"prompt_cache_miss_tokens":60}})

class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.root = create_sandbox(OUT / self._testMethodName)
        self.s = TranscriptStore(self.root)
        self.h = self.s.open_session("TEST_OPERATOR", "SYNTHETIC_A")
        self.j = ProviderJournal(self.s)
        self.scope = scope(); self.j.register_batch(self.scope)
        self.t = self.s.begin_turn(self.h, "测试问题", "s1")
        self.ctx = build_context(self.s, self.h, self.t["turn_id"])
        self.requests = []
    def tearDown(self):
        self.s.close()
    def transport(self, payload, key):
        self.requests.append(payload)
        return 200, body()
    def invoke(self, transport=None, key=lambda: TEST_KEY):
        return self.j.call(self.h, self.t["turn_id"], self.scope["batch_id"], "s1", self.ctx,
                           transport=transport or self.transport, credential_reader=key)
    def test_fixed_scope_and_capture(self):
        c = self.invoke()
        self.assertEqual(c["status"], "RESPONSE_CAPTURED")
        self.assertEqual(c["capture_origin"], "AUTHORED_PROVIDER_TEST_FIXTURE")
        self.assertEqual(self.s.get_turn(self.h, self.t["turn_id"])["response_provenance"], "AUTHORED_TEST_STUB")
        self.assertNotIn("tools", json.loads(self.requests[0]))
        self.assertEqual(json.loads(self.requests[0])["thinking"], {"type":"disabled"})
    def test_same_turn_never_resends(self):
        first = self.invoke(); second = self.invoke()
        self.assertEqual(first["call_id"], second["call_id"])
        self.assertEqual(len(self.requests), 1)
    def test_timeout_unknown_and_no_retry(self):
        def timeout(payload, key):
            self.requests.append(payload)
            raise TimeoutError("never log " + key)
        first = self.invoke(timeout); second = self.invoke()
        self.assertEqual(first["status"], "SUBMITTED_STATUS_UNKNOWN")
        self.assertEqual(second["status"], first["status"])
        self.assertEqual(len(self.requests), 1)
        self.assertNotIn(TEST_KEY, json.dumps(self.j.summary(self.scope["batch_id"])))
    def test_unknown_stops_future_slot(self):
        self.invoke(lambda p,k: (_ for _ in ()).throw(TimeoutError()))
        row = self.s.begin_turn(self.h, "另一个测试问题", "s2")
        with self.assertRaises(StoreGuard):
            self.j.call(self.h,row["turn_id"],self.scope["batch_id"],"s2",build_context(self.s,self.h,row["turn_id"]), transport=self.transport,credential_reader=lambda:TEST_KEY)
    def test_process_abort_intent_survives_restart(self):
        def abort(p,k):
            raise SystemExit("AUTHORED_CRASH_AFTER_INTENT")
        with self.assertRaises(SystemExit):
            self.invoke(abort)
        sid = self.h.session_id
        self.s.close(); self.s = TranscriptStore(self.root)
        self.h = self.s.resume("TEST_OPERATOR", sid); self.j = ProviderJournal(self.s)
        self.assertEqual(self.invoke()["status"], "SUBMITTED_STATUS_UNKNOWN")
        self.assertEqual(self.requests, [])
    def test_http_error_retains_raw_and_stops(self):
        self.assertEqual(self.invoke(lambda p,k:(503,b'{"error":"temporary"}'))["status"], "RESPONSE_REJECTED")
        self.assertEqual(self.j.summary(self.scope["batch_id"])["calls_submitted"],1)
    def test_invalid_json_retained(self):
        self.assertEqual(self.invoke(lambda p,k:(200,b'not-json'))["error_category"],"JSONDecodeError")
        raw = self.s.db.execute("SELECT raw_response FROM provider_calls").fetchone()[0]
        self.assertEqual(raw,b'not-json')
    def test_truncation_not_accepted(self):
        self.assertEqual(self.invoke(lambda p,k:(200,body(finish="length")))["error_category"],"TRUNCATED_OR_OTHER_FINISH")
        self.assertIsNone(self.s.get_turn(self.h,self.t["turn_id"])["assistant_text"])
    def test_empty_response_not_accepted(self):
        self.assertEqual(self.invoke(lambda p,k:(200,body(text="")))["error_category"],"EMPTY_RESPONSE")
    def test_missing_usage_not_accepted(self):
        raw=json.loads(body()); raw.pop("usage")
        self.assertEqual(self.invoke(lambda p,k:(200,canonical(raw)))["error_category"],"INVALID_USAGE")
    def test_model_mismatch_not_accepted(self):
        self.assertEqual(self.invoke(lambda p,k:(200,body(model="unapproved-model")))["error_category"],"PROVIDER_MODEL_MISMATCH")
    def test_no_secret_in_saved_response(self):
        c=self.invoke(lambda p,k:(200,body(text=k)))
        self.assertEqual(c["error_category"],"SECRET_ECHO_QUARANTINED")
        self.assertEqual(c["raw_was_redacted"],1)
        raw=self.s.db.execute("SELECT raw_response FROM provider_calls").fetchone()[0]
        self.assertNotIn(TEST_KEY.encode(),raw)
    def test_secret_in_context_refused_before_submission(self):
        self.ctx["messages"].insert(-1,{"role":"user","content":TEST_KEY})
        with self.assertRaises(StoreGuard): self.invoke()
        self.assertEqual(self.j.summary(self.scope["batch_id"])["calls_submitted"],0)
    def test_missing_key_does_not_charge(self):
        with self.assertRaises(StoreGuard): self.invoke(key=lambda:None)
        self.assertEqual(self.j.summary(self.scope["batch_id"])["calls_submitted"],0)
    def test_scope_immutable(self):
        altered=copy.deepcopy(self.scope); altered["slots"][0]["user_text"]="changed"
        with self.assertRaises(StoreGuard): self.j.register_batch(altered)
    def test_inadequate_cap_refused(self):
        altered=copy.deepcopy(self.scope); altered["total_guard_cny"]=0.001
        with self.assertRaises(StoreGuard): scope_check(altered)
    def test_prompt_byte_limit(self):
        self.ctx["messages"].insert(-1,{"role":"user","content":"极长文本"*10000})
        with self.assertRaises(StoreGuard): self.invoke()
        self.assertEqual(self.requests,[])
    def test_wrong_slot_entity_refused(self):
        other=self.s.open_session("TEST_OPERATOR","SYNTHETIC_B")
        row=self.s.begin_turn(other,"测试问题","different")
        with self.assertRaises(StoreGuard):
            self.j.call(other,row["turn_id"],self.scope["batch_id"],"s1",build_context(self.s,other,row["turn_id"]),transport=self.transport,credential_reader=lambda:TEST_KEY)
    def test_usage_over_bound_rejected(self):
        raw=json.loads(body()); raw["usage"].update(prompt_tokens=100000,total_tokens=100020,prompt_cache_hit_tokens=0,prompt_cache_miss_tokens=100000)
        self.assertEqual(self.invoke(lambda p,k:(200,canonical(raw)))["error_category"],"USAGE_EXCEEDS_RESERVED_BOUND")
    def test_context_not_semantically_approved(self):
        self.invoke()
        traces=[json.loads(r[0]) for r in self.s.db.execute("SELECT detail_json FROM turn_lifecycle")]
        self.assertTrue(any(r.get("semantic_verdict","ABSENT") is None for r in traces))

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    code=list(CODE.glob("*.py"))+[Path(__file__)]
    with zipfile.ZipFile(OUT/"TESTED_SOURCE.zip","x",compression=zipfile.ZIP_DEFLATED) as z:
        for p in code: z.writestr(p.relative_to(ROOT).as_posix(),p.read_bytes())
    with (OUT/"TESTS.log").open("x",encoding="utf-8") as f:
        result=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProviderTests))
    report={"at_utc":datetime.now(timezone.utc).isoformat(),"tests":result.testsRun,"errors":len(result.errors),"failures":len(result.failures),"passed":result.wasSuccessful(),
        "target_calls":0,"origin":"AUTHORED_PROVIDER_TEST_FIXTURES","source_snapshot_sha256":file_sha(OUT/"TESTED_SOURCE.zip"),
        "tested_sources":[{"path":p.relative_to(ROOT).as_posix(),"sha256":file_sha(p)} for p in code]}
    (OUT/"TESTS.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":OUT.relative_to(ROOT).as_posix(),"tests":result.testsRun,"passed":result.wasSuccessful()},ensure_ascii=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)

if __name__=="__main__": main()
