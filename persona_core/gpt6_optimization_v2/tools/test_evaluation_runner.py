"""Offline engineering tests; no provider network and no evaluation verdicts.

Run with C:\\Users\\skr\\anaconda3\\python.exe -B -m unittest discover -s
persona_core/gpt6_optimization_v2/tools -p test_evaluation_runner.py -v
Temporary G6_V2_runner_test_* evidence is removed after each test. No historical
runtime, shared goal state, frozen questions or credential adapter is edited.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluation_runner as runner


class EvaluationRunnerTests(unittest.TestCase):
    def setUp(self):
        self.roots = []

    def tearDown(self):
        base = runner.EVIDENCE.resolve()
        for root in self.roots:
            resolved = root.resolve()
            self.assertEqual(resolved.parent, base)
            self.assertTrue(resolved.name.startswith("G6_V2_runner_test_"))
            if resolved.exists():
                shutil.rmtree(resolved)

    def name(self):
        name = "runner_test_" + uuid.uuid4().hex
        self.roots.append(runner.revision_root(name))
        return name

    def small(self, n=3, *, offline=True):
        name = self.name()
        data = copy.deepcopy(runner.load_suite("heldout", "deepseek-v4-flash", "deepseek-v4-pro"))
        data["slots"] = data["slots"][:n]
        data["cases"] = data["cases"][:1]
        data["criteria_count"] = n * 4
        with patch.object(runner, "load_suite", return_value=data):
            result = runner.prepare(name, offline=offline)
        return name, runner.revision_root(name), result

    def worker(self, name, *, transport=None, max_turns=None):
        root = runner.revision_root(name)
        run_id = uuid.uuid4().hex
        lease = root / "ACTIVE_RUN.json"
        if lease.exists():
            run_id = runner.read(lease)["run_id"]
        else:
            runner.write_new(lease, {"run_id": run_id, "pid": os.getppid(), "at_utc": runner.now()})
        with patch.object(runner, "authored_transport", transport or runner.authored_transport):
            return runner.worker(name, "segment_000", run_id, max_turns=max_turns)

    def db_rows(self, root):
        scope = runner.read(root / "SCOPE.json")
        with runner.readonly_db(root) as db:
            return runner.call_rows(db, scope)

    def cli(self, *args, timeout=180):
        result = subprocess.run([str(runner.PYTHON), "-B", str(Path(runner.__file__)), *args],
                                cwd=runner.ROOT, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        self.assertEqual(result.stderr, "")
        return result, json.loads(result.stdout)

    def test_freeze_gate_refuses_before_any_write(self):
        name = self.name()
        original = runner.read

        def unfrozen(path):
            if Path(path).name == "GPT6_BASELINE_AUDIT.json":
                return {"status": "AUDITOR_IN_PROGRESS"}
            return original(path)

        with patch.object(runner, "read", side_effect=unfrozen):
            with self.assertRaisesRegex(runner.RunnerError, "BASELINE_AUDIT_NOT_FROZEN"):
                runner.prepare(name, offline=True)
        self.assertFalse(runner.revision_root(name).exists())

    def test_scope4_preparation_freezes_protocol_and_all_current_tools(self):
        name = self.name()
        policy = runner.GOAL/'tools'/'test_evaluation_runner.py'  # read is patched; no file mutation.
        original_read = runner.read
        with patch.object(runner, 'read', side_effect=lambda p: {
            'version': 'apcore-transport-lifecycle-1', 'connect_timeout_seconds': 15,
            'read_timeout_seconds': 120, 'worker_deadline_seconds': 595
        } if Path(p) == policy else original_read(p)):
            result = runner.prepare(name, suite='external44', offline=True, primary='deepseek-v4-pro',
                secondary='deepseek-flash', max_output_tokens=32768, transport_policy_file=policy, api_protocol='responses')
        root = runner.revision_root(name); scope = runner.read(root/'SCOPE.json')
        self.assertEqual(scope['schema_version'], 'apcore-provider-scope-4')
        self.assertEqual(scope['api_protocol'], 'responses')
        self.assertEqual(scope['endpoint'], 'https://api.deepseek.com/responses')
        self.assertEqual(result['recorded_calls'], 0)
        files = runner.read(root/'SOURCE_MANIFEST.json')['files']
        for tool in ('responses_api_transport.py', 'test_responses_provider_integration.py', 'candidate_host_v2.py',
                     'candidate_longitudinal_v2.py', 'blind_review_v2.py'):
            self.assertIn('persona_core/gpt6_optimization_v2/tools/'+tool, files)
        outcome = self.worker(name, max_turns=1)
        self.assertEqual(outcome['status'], 'PAUSED_KNOWN_PREFIX')
        self.assertEqual(runner.status(name)['recorded_calls'], 1)
        with runner.readonly_db(root) as db:
            request = json.loads(db.execute('SELECT request_json FROM provider_calls').fetchone()[0])
        self.assertIn('input', request); self.assertNotIn('messages', request)

    def test_heldout_denominator_actions_and_conservative_whole_batch_scope(self):
        data = runner.load_suite("heldout", "deepseek-v4-flash", "deepseek-v4-pro")
        scope = runner.build_scope("contract", data, runner.checked_pricing(None, True),
                                   "deepseek-v4-flash", "deepseek-v4-pro")
        self.assertEqual((len(data["cases"]), len(scope["slots"]), data["criteria_count"]), (24, 113, 452))
        self.assertEqual([s["id"] for s in scope["slots"] if s["host_action_before"] != "NONE"], ["H05_T04", "H13_T05"])
        self.assertEqual([s["id"] for s in scope["slots"] if s["model_role"] == "SECONDARY"], ["H05_T04", "H14_T04"])
        self.assertEqual(scope["automatic_paid_retries"], 0)
        self.assertFalse(scope["automatic_capacity_escalation"])
        self.assertGreater(scope["total_guard_cny"], 20)  # No artificial division at the old approval threshold.
        self.assertLessEqual(scope["reserved_upper_micro_cny"], round(scope["total_guard_cny"] * 1e6))
        self.assertEqual(sum(len(s["slot_ids"]) for s in runner.segments(scope["slots"])), 113)
        provider = runner.runtime_modules()[0]
        with self.assertRaises(ValueError):
            runner.build_scope("oversized", data, runner.checked_pricing(None, True),
                               "deepseek-v4-flash", "deepseek-v4-pro", guard_cny=1)
        provider.scope_check(scope)

    def test_original_inputs_roles_and_authored_historical_setup_are_preserved(self):
        name = self.name()
        result = runner.prepare(name, suite="original82", offline=True)
        root = runner.revision_root(name)
        scope = runner.read(root / "SCOPE.json")
        old = runner.read(runner.FREEZE / "EXECUTION_SCOPE.json")
        self.assertEqual([{k: s[k] for k in ("id", "case_id", "entity_label", "user_text")} for s in scope["slots"]],
                         [{k: s[k] for k in ("id", "case_id", "entity_label", "user_text")} for s in old["slots"]])
        self.assertEqual(sum(s["model_role"] == "PRIMARY" for s in scope["slots"]), 76)
        self.assertEqual(sum(s["model_role"] == "SECONDARY" for s in scope["slots"]), 6)
        self.assertEqual((result["recorded_calls"], result["authored_setup_turns_excluded"]), (0, 245))
        preparation = runner.read(root / "PREPARATION.json")
        with runner.readonly_db(root) as db:
            for session in preparation["sessions"].values():
                self.assertEqual(db.execute("SELECT count(*) FROM turns WHERE session_id=?", (session["session_id"],)).fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM turns WHERE response_provenance='AUTHORED_TEST_STUB'").fetchone()[0], 245)
        self.assertEqual(runner.read(root / "MANIFEST.json")["expected_criteria_count"], 328)

    def test_external44_preserves_whole_cases_roles_rubric_and_fresh_history(self):
        name = self.name()
        result = runner.prepare(name, suite="external44", offline=True)
        root = runner.revision_root(name)
        data = runner.load_suite("external44", "deepseek-flash", "deepseek-v4-pro")
        original = runner.load_suite("original82", "deepseek-flash", "deepseek-v4-pro")
        ids = ["N02", "N04", "N06", "N07", "N08", "N09", "N11"]
        self.assertEqual(data["slots"], [s for s in original["slots"] if s["case_id"] in ids])
        self.assertEqual(data["cases"], [c for c in original["cases"] if c["id"] in ids])
        self.assertEqual((len(data["cases"]), len(data["slots"]), data["criteria_count"]), (7, 44, 176))
        self.assertEqual([s["id"] for s in data["slots"] if s["model_role"] == "SECONDARY"], ["N09_S1", "N09_S2"])
        self.assertEqual((result["recorded_calls"], result["authored_setup_turns_excluded"]), (0, 245))
        self.assertEqual((runner.GOAL / "external_failure_v1/PRIVATE_RUBRIC.json").read_bytes(),
                         (runner.PROTOCOL / "PRIVATE_RUBRIC.json").read_bytes())
        with runner.readonly_db(root) as db:
            for session in runner.read(root / "PREPARATION.json")["sessions"].values():
                self.assertEqual(db.execute("SELECT count(*) FROM turns WHERE session_id=?",
                                           (session["session_id"],)).fetchone()[0], 0)
        self.assertEqual(runner.read(root / "MANIFEST.json")["expected_criteria_count"], 176)

    def test_external44_rejects_changed_selection_before_creating_revision(self):
        name = self.name()
        original_read = runner.read
        def changed(path):
            value = original_read(path)
            if Path(path) == runner.GOAL / "external_failure_v1/CASES.json":
                value["cases"][0]["user_turns"][0] += "changed"
            return value
        with patch.object(runner, "read", side_effect=changed):
            with self.assertRaisesRegex(runner.RunnerError, "EXTERNAL_SELECTION_INPUT_OR_RUBRIC_CHANGED"):
                runner.prepare(name, suite="external44", offline=True)
        self.assertFalse(runner.revision_root(name).exists())

    def test_heldout_decoy_is_private_and_never_a_provider_capture(self):
        name = self.name()
        result = runner.prepare(name, offline=True)
        root = runner.revision_root(name)
        self.assertEqual((result["recorded_calls"], result["authored_setup_turns_excluded"]), (0, 1))
        _, transcript, operations, *_ = runner.runtime_modules()
        preparation = runner.read(root / "PREPARATION.json")
        scope = runner.read(root / "SCOPE.json")
        store = transcript.TranscriptStore(root / "runtime")
        try:
            handle = store.resume(scope["principal_id"], preparation["sessions"]["H09"]["session_id"])
            chat = operations.open_chat(store, handle, scope)
            self.assertEqual(chat.memory_provider.search(handle, "HOLDOUT_OTHER_ONLY"), [])
            foreign = store.db.execute("SELECT entity_id FROM entities WHERE label='H09_OTHER'").fetchone()[0]
            self.assertNotEqual(foreign, handle.entity_id)
            self.assertEqual(store.db.execute("SELECT count(*) FROM provider_calls").fetchone()[0], 0)
        finally:
            store.close()

    def test_journal_and_recovery_intent_precede_transport(self):
        name, root, _ = self.small(2)
        observations = []
        authored = runner.authored_transport

        def transport(payload, credential):
            current = runner.read(root / "CURSOR.json")
            rows = self.db_rows(root)
            self.assertEqual(current["state"], "NETWORK_MAY_BE_SUBMITTED")
            self.assertEqual(rows[-1]["provider_status"], "SUBMITTED_STATUS_UNKNOWN")
            self.assertEqual(current["in_flight_external_effect"]["turn_id"], rows[-1]["turn_id"])
            self.assertEqual(runner.value_sha(json.loads(payload)), rows[-1]["request_sha256"])
            observations.append(rows[-1]["slot_id"])
            return authored(payload, credential)

        result = self.worker(name, transport=transport)
        self.assertEqual(result["status"], "SEGMENT_COMPLETE")
        self.assertEqual(len(observations), 2)
        self.assertTrue(all(runner.completed(r) for r in self.db_rows(root)))
        self.assertIsNone(runner.read(root / "CURSOR.json")["in_flight_external_effect"])

    def test_completed_prefix_resume_does_not_call_or_redisplay(self):
        name, root, _ = self.small(3)
        self.worker(name, max_turns=1)
        displayed = root / "displays/H01_T01.txt"
        old = (displayed.read_bytes(), displayed.stat().st_mtime_ns)
        calls = []
        authored = runner.authored_transport

        def transport(payload, credential):
            calls.append(json.loads(payload)["messages"][-1]["content"])
            return authored(payload, credential)

        result = self.worker(name, transport=transport)
        self.assertEqual(result["status"], "SEGMENT_COMPLETE")
        self.assertEqual(len(calls), 2)
        self.assertEqual((displayed.read_bytes(), displayed.stat().st_mtime_ns), old)
        with runner.readonly_db(root) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM display_journal").fetchone()[0], 3)
        with patch.object(runner, "authored_transport", side_effect=AssertionError("must not call")):
            self.assertEqual(self.worker(name)["status"], "SEGMENT_COMPLETE")
        self.assertEqual(len(self.db_rows(root)), 3)

    def test_unknown_stops_batch_preserves_reserve_and_cannot_resume(self):
        name, root, _ = self.small()
        calls = []

        def timeout(payload, credential):
            calls.append(1)
            raise TimeoutError("DO_NOT_ECHO_TRANSPORT_SECRET")

        result = self.worker(name, transport=timeout)
        self.assertEqual(result["status"], "STOPPED_RECONCILE_REQUIRED")
        row = self.db_rows(root)[0]
        self.assertEqual(row["provider_status"], "SUBMITTED_STATUS_UNKNOWN")
        self.assertIsNone(row["assistant_text"])
        self.assertGreater(row["reserve_micro_cny"], 0)
        self.assertIsNone(row["estimate_peak_micro_cny"])
        self.worker(name, transport=timeout)
        self.assertEqual(calls, [1])
        with patch.object(runner, "process_alive", return_value=False):
            reconciliation = runner.reconcile(name)
        self.assertEqual(reconciliation["unknown_count"], 1)
        self.assertEqual(self.db_rows(root), [row])
        self.assertEqual(reconciliation["unknown_reserved_micro_cny"], row["reserve_micro_cny"])
        with self.assertRaisesRegex(runner.RunnerError, "REVISION_NOT_RESUMABLE"):
            runner.run(name)
        self.assertEqual(len(runner.read(root / "CAPTURES.json")["turns"]), 1)
        for path in root.glob("runs/*/*/RESULT.json"):
            self.assertNotIn("DO_NOT_ECHO_TRANSPORT_SECRET", path.read_text(encoding="utf-8"))

    def test_delivery_crash_never_repeats_network_or_display(self):
        name, root, _ = self.small(2)
        original = runner.write_bytes_new
        attempts = []

        def failing_sink(path, data):
            if Path(path).parent.name == "displays":
                attempts.append(1)
                raise OSError("DO_NOT_ECHO_SINK_ERROR")
            return original(path, data)

        with patch.object(runner, "write_bytes_new", side_effect=failing_sink):
            result = self.worker(name)
        self.assertEqual(result["status"], "STOPPED_RECONCILE_REQUIRED")
        with runner.readonly_db(root) as db:
            self.assertEqual(db.execute("SELECT status FROM display_journal").fetchone()[0], "DISPLAY_INTENT")
        self.assertEqual(self.db_rows(root)[0]["provider_status"], "RESPONSE_CAPTURED")
        with patch.object(runner, "authored_transport", side_effect=AssertionError("must not resend")):
            self.worker(name)
        self.assertEqual(attempts, [1])
        self.assertEqual(len(self.db_rows(root)), 1)

    def test_empty_response_known_rejection_keeps_usage_and_stops(self):
        name, root, _ = self.small()
        authored = runner.authored_transport

        def empty(payload, credential):
            code, raw = authored(payload, credential)
            body = json.loads(raw)
            body["choices"][0]["message"]["content"] = ""
            return code, runner.canonical(body)

        self.worker(name, transport=empty)
        rows = self.db_rows(root)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["provider_status"], "RESPONSE_REJECTED")
        self.assertGreater(rows[0]["estimate_peak_micro_cny"], 0)
        self.assertEqual(runner.status(name)["unknown_count"], 0)
        self.assertEqual(runner.status(name)["generated_target_captures"], 0)

    def test_source_drift_prevents_first_call_and_new_module_is_bound(self):
        name, root, _ = self.small()
        changed = runner.source_bindings()
        changed["persona_core/operational_runtime_v1/new_module.py"] = "0" * 64
        with patch.object(runner, "source_bindings", return_value=changed):
            with self.assertRaisesRegex(runner.RunnerError, "CURRENT_SOURCE_BINDING_CHANGED"):
                runner.run(name)
        self.assertEqual(self.db_rows(root), [])
        self.assertFalse((root / "ACTIVE_RUN.json").exists())

    def test_source_drift_between_slots_stops_before_next_submission(self):
        name, root, _ = self.small()
        bound = runner.source_bindings()
        changed = dict(bound, unexpected_module="0" * 64)
        switched = [False]
        authored = runner.authored_transport

        def transport(payload, credential):
            switched[0] = True
            return authored(payload, credential)

        with patch.object(runner, "source_bindings", side_effect=lambda: changed if switched[0] else bound):
            result = self.worker(name, transport=transport)
        self.assertEqual(result["status"], "STOPPED_RECONCILE_REQUIRED")
        self.assertEqual(result["error_code"], "CURRENT_SOURCE_BINDING_CHANGED_NEW_REVISION_REQUIRED")
        self.assertEqual(len(self.db_rows(root)), 1)
        self.assertTrue(runner.completed(self.db_rows(root)[0]))

    def test_manifest_scope_and_final_captures_are_immutable(self):
        name, root, _ = self.small(1)
        with self.assertRaisesRegex(runner.RunnerError, "REVISION_ALREADY_EXISTS"):
            runner.prepare(name, offline=True)
        with self.assertRaises(FileExistsError):
            runner.write_new(root / "SCOPE.json", {})
        self.worker(name)
        path = runner.capture_snapshot(root, final=True)
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        self.assertEqual(runner.capture_snapshot(root, final=True), path)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        value = runner.read(path)
        required = {"case_id", "slot_id", "user_text", "assistant_text", "status", "provider_status", "model",
                    "call_id", "turn_id", "session_id", "raw_sha256"}
        self.assertTrue(required.issubset(value["turns"][0]))
        self.assertFalse(value["eligible_for_target_evaluation"])
        self.assertIsNone(value["semantic_acceptance"])
        self.assertEqual(value["source_manifest_sha256"], runner.sha(root / "SOURCE_MANIFEST.json"))
        self.assertEqual(value["cases_sha256"], runner.sha(runner.GOAL / "heldout_v1/CASES.json"))
        manifest = runner.read(root / "MANIFEST.json")
        manifest["expected_turn_count"] = 99
        (root / "MANIFEST.json").write_bytes(runner.canonical(manifest))
        with self.assertRaisesRegex(runner.RunnerError, "MANIFEST_SEAL_MISMATCH"):
            runner.status(name)

    def test_readonly_status_has_no_submission_display_or_file_mutation(self):
        name, root, _ = self.small()
        before = {p.relative_to(root).as_posix(): runner.sha(p) for p in root.rglob("*") if p.is_file()}
        self.assertEqual(runner.status(name)["state"], "PREPARED")
        after = {p.relative_to(root).as_posix(): runner.sha(p) for p in root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_concurrent_or_stale_driver_is_not_automatically_stolen(self):
        name, root, _ = self.small()
        runner.write_new(root / "ACTIVE_RUN.json", {"pid": os.getpid(), "run_id": "other", "at_utc": runner.now()})
        with self.assertRaisesRegex(runner.RunnerError, "REVISION_NOT_RESUMABLE"):
            runner.run(name)
        with self.assertRaisesRegex(runner.RunnerError, "DRIVER_STILL_RUNNING"):
            runner.reconcile(name)
        self.assertEqual(self.db_rows(root), [])

    def test_path_traversal_and_unknown_suite_are_rejected(self):
        for bad in ("../R047-03", "a/b", "", "x" * 81):
            with self.assertRaises(runner.RunnerError):
                runner.revision_root(bad)
        with self.assertRaisesRegex(runner.RunnerError, "UNKNOWN_SUITE"):
            runner.load_suite("invented", "deepseek-v4-flash", "deepseek-v4-pro")
        with self.assertRaisesRegex(runner.RunnerError, "DISTINCT_SUPPORTED_MODELS_REQUIRED"):
            runner.load_suite("heldout", "deepseek-v4-flash", "deepseek-v4-flash")

    def test_target_preparation_requires_current_pricing_without_network(self):
        name = self.name()
        with self.assertRaisesRegex(runner.RunnerError, "CURRENT_OFFICIAL_PRICING_RECORD_REQUIRED"):
            runner.prepare(name)
        self.assertFalse(runner.revision_root(name).exists())

    def test_full_heldout_cli_real_process_restart_model_switch_and_orderly_resume(self):
        name = self.name()
        result, prepared = self.cli("prepare", "--revision", name, "--offline")
        self.assertEqual(result.returncode, 0, prepared)
        result, first = self.cli("run", "--revision", name, "--max-turns", "3")
        self.assertEqual(result.returncode, 0, first)
        self.assertEqual(first["completed_slots"], 3)
        root = runner.revision_root(name)
        first_display = root / "displays/H01_T01.txt"
        stamp = first_display.stat().st_mtime_ns
        result, final = self.cli("run", "--revision", name, timeout=240)
        self.assertEqual(result.returncode, 0, final)
        self.assertEqual((final["completed_slots"], final["generated_target_captures"], final["unknown_count"]), (113, 0, 0))
        self.assertEqual(first_display.stat().st_mtime_ns, stamp)
        captures = runner.read(root / "CAPTURES.json")
        self.assertEqual(len(captures["turns"]), 113)
        rows = {r["slot_id"]: r for r in captures["turns"]}
        for a, b in (("H05_T03", "H05_T04"), ("H13_T04", "H13_T05")):
            before = runner.read(root / "receipts" / (a + ".json"))
            after = runner.read(root / "receipts" / (b + ".json"))
            self.assertNotEqual(before["pid"], after["pid"])
            self.assertEqual(before["session_id"], after["session_id"])
            self.assertEqual(before["entity_id"], after["entity_id"])
        for a, b in (("H05_T03", "H05_T04"), ("H14_T03", "H14_T04")):
            self.assertNotEqual(rows[a]["model"], rows[b]["model"])
            self.assertEqual(rows[a]["session_id"], rows[b]["session_id"])
        result, again = self.cli("run", "--revision", name)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(again["recorded_calls"], 113)
        self.assertEqual(first_display.stat().st_mtime_ns, stamp)
        self.assertIsNone(again["semantic_acceptance"])


if __name__ == "__main__":
    unittest.main()
