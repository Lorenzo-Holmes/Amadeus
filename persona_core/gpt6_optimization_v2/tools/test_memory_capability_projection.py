"""Authored offline memory-capability probes; no benchmarks or real requests."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid
import zipfile

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]
CODE = ROOT / "persona_core/operational_runtime_v1"
sys.path.insert(0, str(CODE))
from admission import AdmissionController
from context_router import build_context
from provider import ProviderJournal, canonical
from recovery import logical_summary
from retrieval import RetrievalService
from runtime_store import RuntimeStore
from transcript_store import TranscriptStore, StoreGuard, create_sandbox

OUT = ROOT / "persona_core/gpt6_optimization_v2/component_checks" / ("memory_capability_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
def host_data(messages):
    return json.loads(next(m["content"] for m in messages if m["content"].startswith("宿主只读范围")).split("：", 1)[1])


class Tests(unittest.TestCase):
    def setUp(self):
        self.sandbox_parent = ROOT / "persona_core/operational_build_v1/evidence/G6_V2_memory_capability" / OUT.name
        self.path = create_sandbox(self.sandbox_parent / self._testMethodName)
        self.store = TranscriptStore(self.path)
        self.addCleanup(self.store.close)
        self.handle = self.store.open_session("OFFLINE_OPERATOR", "OFFLINE_NORTH")
        self.admission = AdmissionController(self.store)
        self.runtime = RuntimeStore(self.store, self.admission)
        self.provider = RetrievalService(self.runtime)

    def observed(self, text, handle=None):
        h = handle or self.handle
        turn = self.store.begin_turn(h, text, uuid.uuid4().hex)
        self.store.capture_reply(h, turn["turn_id"], "这是署名离线答复，不是服务商输出。", uuid.uuid4().hex, origin="AUTHORED_TEST_STUB")
        self.store.mark_displayed(h, turn["turn_id"])
        return self.admission.observe_turn(h, turn["turn_id"])["commit"]["event_id"]

    def context(self, text="这次我们先安排桌面上的阅读笔记。", *, handle=None, provider="builtin"):
        h = handle or self.handle
        turn = self.store.begin_turn(h, text, uuid.uuid4().hex)
        p = self.provider if provider == "builtin" else provider
        return build_context(self.store, h, turn["turn_id"], memory_provider=p)

    def capability(self, packet):
        core = host_data(packet["messages"])
        self.assertIn("runtime_memory_capability", core)
        self.assertEqual(packet["memory_capability_projection"], core["runtime_memory_capability"])
        return core["runtime_memory_capability"]

    def test_empty_retrieval_still_projects_available_scoped_capability(self):
        packet = self.context()
        value = self.capability(packet)
        self.assertEqual(value["status"], "AVAILABLE")
        self.assertEqual(value["scope"], {"entity_id": self.handle.entity_id, "mode": "PRODUCT_RUNTIME"})
        self.assertTrue(value["same_entity_mode_across_sessions"])
        self.assertTrue(value["after_store_reopen"])
        self.assertEqual(value["query"]["returned_record_count"], 0)
        self.assertFalse(value["empty_result_proves_no_records"])
        self.assertFalse(value["all_future_recall_guaranteed"])
        self.assertFalse(value["external_tools_or_cross_entity_access"])
        self.assertFalse(value["scheduled_reminders"])

    def test_actual_provider_payload_contains_capability_not_only_trace(self):
        packet = self.context("留一个阅读清单标题，以后我们仍按这个对象讨论。")
        scope = json.loads((ROOT / "persona_core/operational_build_v1/evidence/R047-04/NATURAL_DAY_OBSERVATION_SCOPE.json").read_text(encoding="utf-8"))
        scope["batch_id"] = "OFFLINE_CAPABILITY_" + uuid.uuid4().hex
        scope["principal_id"] = "OFFLINE_OPERATOR"
        for slot in scope["slots"]: slot["entity_label"] = "OFFLINE_NORTH"
        journal = ProviderJournal(self.store); journal.register_batch(scope)
        seen = []
        def transport(payload, credential):
            request = json.loads(payload); seen.append(request)
            return 200, canonical({"model": request["model"], "choices": [{"finish_reason": "stop", "message": {"content": "离线接口封包检查。"}}],
                                   "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}})
        result = journal.call(self.handle, packet["turn_id"], scope["batch_id"], scope["slots"][0]["id"], packet,
                              transport=transport, credential_reader=lambda: "OFFLINE_DUMMY_NO_REAL_KEY")
        self.assertEqual(result["capture_origin"], "AUTHORED_PROVIDER_TEST_FIXTURE")
        self.assertEqual(result["status"], "RESPONSE_CAPTURED")
        self.assertIn("runtime_memory_capability", host_data(seen[0]["messages"]))
        self.assertEqual(host_data(seen[0]["messages"])["runtime_memory_capability"], self.capability(packet))

    def test_record_available_does_not_promote_description_to_world_event(self):
        event = self.observed("我把阅读书单交给了朋友，这只是我的自述。")
        packet = self.context("阅读书单交给朋友那次说了什么？")
        self.assertIn(event, [r["record_id"] for r in packet["retrieval"]])
        value = self.capability(packet)
        self.assertFalse(value["described_world_events_verified_by_utterance"])
        self.assertEqual(value["record_scope"], "RECORDED_UTTERANCES_AND_ADMITTED_RUNTIME_EVENTS")

    def test_missed_query_is_separate_from_storage_capability(self):
        self.observed("储物箱标签是木桥备品。")
        packet = self.context("UNRELATED_READONLY_QUERY_80415")
        value = self.capability(packet)
        self.assertEqual((value["status"], value["query"]["returned_record_count"]), ("AVAILABLE", 0))
        self.assertFalse(value["empty_result_proves_no_records"])

    def test_frozen_source_memory_is_separate_from_runtime_record_capability(self):
        packet = self.context("来源记忆的范围是什么？")
        value = self.capability(packet)
        self.assertEqual(value["source_memory"], "SEPARATE_FROZEN_SOURCE_PROVENANCE")
        self.assertIn("memory", host_data(packet["messages"]))
        self.assertTrue(any(r["record_kind"] == "FROZEN_SOURCE" for r in packet["retrieval"]))

    def test_generic_callable_cannot_claim_persistence_by_adding_method(self):
        class UnknownCallable:
            def __init__(self): self.claimed = 0
            def __call__(self, *_): return []
            def memory_capability(self, *_):
                self.claimed += 1
                return {"status": "AVAILABLE"}
        custom = UnknownCallable()
        packet = self.context(provider=custom)
        value = self.capability(packet)
        self.assertEqual(value["status"], "UNKNOWN")
        self.assertTrue(packet["retrieval_provider_attached"])
        self.assertIsNone(packet["long_term_retrieval_implemented"])
        self.assertEqual(custom.claimed, 0)
        self.assertNotIn("same_entity_mode_across_sessions", value)

    def test_no_provider_does_not_claim_general_amnesia(self):
        packet = self.context(provider=None)
        value = self.capability(packet)
        self.assertEqual(value["status"], "UNKNOWN")
        self.assertFalse(packet["retrieval_provider_attached"])
        self.assertFalse(packet["long_term_retrieval_implemented"])
        self.assertNotIn("all_memory_absent", value)

    def test_subclass_override_is_not_implicitly_trusted(self):
        class OtherProvider(RetrievalService):
            def memory_capability(self, *_): raise AssertionError("untrusted override must not be used")
        packet = self.context(provider=OtherProvider(self.runtime))
        self.assertEqual(self.capability(packet)["status"], "UNKNOWN")

    def test_capability_authenticates_exact_store_and_handle_without_full_verify(self):
        method = getattr(self.provider, "memory_capability", None)
        self.assertTrue(callable(method))
        other = TranscriptStore(create_sandbox(self.sandbox_parent / (self._testMethodName + "_other")))
        self.addCleanup(other.close)
        with self.assertRaises(StoreGuard): method(other, self.handle)
        second = self.store.open_session("OFFLINE_OPERATOR", "OFFLINE_SOUTH")
        with self.assertRaises(StoreGuard): method(self.store, replace(self.handle, entity_id=second.entity_id))
        with patch.object(self.runtime, "verify", wraps=self.runtime.verify) as verified:
            value = method(self.store, self.handle)
        self.assertEqual(value["status"], "AVAILABLE")
        self.assertEqual(verified.call_count, 0)

    def test_projection_is_readonly_and_does_not_add_third_full_verification(self):
        self.observed("这个对象讨论过红木抽屉里的备用纸。")
        turn = self.store.begin_turn(self.handle, "备用纸的讨论是什么？", uuid.uuid4().hex)
        before = logical_summary(self.store.db)
        with patch.object(self.runtime, "verify", wraps=self.runtime.verify) as checked:
            packet = build_context(self.store, self.handle, turn["turn_id"], memory_provider=self.provider)
        self.capability(packet)
        self.assertEqual(checked.call_count, 2)
        self.assertEqual(logical_summary(self.store.db), before)

    def test_actual_process_reopen_and_new_session_keep_same_entity_record(self):
        event = self.observed("青铜书签放在右侧收纳盒。")
        self.store.close()
        output = self.path / "OFFLINE_REOPEN.json"
        process = subprocess.run([sys.executable, "-B", str(Path(__file__)), "--worker", str(self.path), str(output)],
                                 cwd=ROOT, capture_output=True, timeout=20)
        self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8", errors="replace"))
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertNotEqual(result["pid"], os.getpid())
        self.assertEqual(result["entity_id"], self.handle.entity_id)
        self.assertNotEqual(result["session_id"], self.handle.session_id)
        self.assertIn(event, result["retrieved_record_ids"])
        self.assertEqual(result["capability"]["status"], "AVAILABLE")

    def test_other_entity_and_mode_cannot_receive_saved_record(self):
        event = self.observed("琥珀箱里存的是封存目录。")
        other = self.store.open_session("OFFLINE_OPERATOR", "OFFLINE_SOUTH")
        simulation = self.store.open_session("OFFLINE_OPERATOR", "OFFLINE_NORTH", "CHARACTER_SIMULATION")
        for handle in (other, simulation):
            with self.subTest(mode=handle.mode):
                packet = self.context("琥珀箱的封存目录是什么？", handle=handle)
                self.assertNotIn(event, [r["record_id"] for r in packet["retrieval"]])
                self.assertEqual(self.capability(packet)["scope"], {"entity_id": handle.entity_id, "mode": handle.mode})


def worker(root, output):
    store = TranscriptStore(Path(root))
    try:
        handle = store.open_session("OFFLINE_OPERATOR", "OFFLINE_NORTH")
        runtime = RuntimeStore(store, AdmissionController(store)); provider = RetrievalService(runtime)
        turn = store.begin_turn(handle, "青铜书签放在哪里？", "OFFLINE_REOPEN_QUERY")
        packet = build_context(store, handle, turn["turn_id"], memory_provider=provider)
        result = {"pid": os.getpid(), "entity_id": handle.entity_id, "session_id": handle.session_id,
            "retrieved_record_ids": [r["record_id"] for r in packet["retrieval"]],
            "capability": host_data(packet["messages"]).get("runtime_memory_capability"), "offline_only": True}
        Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        store.close()


def main():
    global OUT
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(sys.argv[2], sys.argv[3]); return 0
    if len(sys.argv) > 1:
        OUT = ROOT / "persona_core/gpt6_optimization_v2/component_checks" / sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=False)
    files = list(CODE.glob("*.py")) + [Path(__file__)]
    before = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    with zipfile.ZipFile(OUT / "TESTED_SOURCE.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for path in files: archive.writestr(path.relative_to(ROOT).as_posix(), path.read_bytes())
    with (OUT / "TESTS.log").open("x", encoding="utf-8", newline="\n") as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    report = {"classification": "AUTHORED_OFFLINE_CAPABILITY_PROJECTION_NOT_SEMANTIC_ACCEPTANCE", "tests": result.testsRun,
        "passed": result.wasSuccessful(), "failures": len(result.failures), "errors": len(result.errors),
        "target_calls": 0, "source_sha256": before,
        "sources_unchanged_during_tests": all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == expected for p, expected in before.items()),
        "source_zip_sha256": hashlib.sha256((OUT / "TESTED_SOURCE.zip").read_bytes()).hexdigest(),
        "log_sha256": hashlib.sha256((OUT / "TESTS.log").read_bytes()).hexdigest(),
        "at_utc": datetime.now(timezone.utc).isoformat()}
    (OUT / "TESTS.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUT), "tests": result.testsRun, "passed": result.wasSuccessful(), "failures": len(result.failures), "errors": len(result.errors)}))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__": raise SystemExit(main())
