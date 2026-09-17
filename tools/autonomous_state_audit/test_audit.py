"""Synthetic offline oracles only; no historical R044-R047 validation is rerun."""
import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).with_name("audit.py")
SPEC = importlib.util.spec_from_file_location("state_drift_audit", SOURCE)
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)
NOW = "2026-09-17T18:40:00Z"
SHA = "a" * 40
HEAD = "b" * 40
PLAN_ID = "APCORE-GPT6-OPTIMIZATION-V2"


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for path in ("AMADEUS_PERSONA_CORE_MASTER_GOAL.md", "PERSONA_CORE_CONTINUATION_PROTOCOL.md"):
            self.put(path, "synthetic policy fixture\n")
        self.put("PERSONA_CORE_DECISION_LOG.md", "## DEC-G6-001 - synthetic\n## DEC-G6-002 - synthetic\n")
        self.put("protected/frozen.bin", b"synthetic frozen bytes")
        self.put("persona_core/gpt6_optimization_v2/CURSOR.json", "{}")
        self.put("evidence/cursor.json", "{}")
        self.put("evidence/journal.sqlite3", b"NOT A DATABASE: presence fixture only")
        self.put("persona_core/operational_runtime_v1/source.py", "# fixture\n")
        self.operation = {"schema_version": "amadeus-operational-task-state-1", "plan_id": PLAN_ID,
                          "phase_status": "BUILD_SCOPE_COMPLETE_VALIDATION_PENDING"}
        self.matrix = {"schema_version": "amadeus-operational-acceptance-1", "plan_id": PLAN_ID,
                       "gates": [{"id": "synthetic-gate", "status": "PASS",
                                  "evidence": ["../operational_runtime_v1/source.py"]}]}
        self.task = {"TASK_ID": "C01", "OWNER": "WORKER-C", "STATUS": "RUNNING", "BASE_SHA": SHA,
                     "BRANCH": "feature-c", "PR": "https://github.com/Lorenzo-Holmes/Amadeus/pull/99",
                     "EVIDENCE": {"head_sha": HEAD}, "WRITE_SET": ["tools/c/**"], "DEPENDENCIES": [],
                     "LEASE_STARTED_AT": "2026-09-17T18:30:00Z", "LEASE_EXPIRES_AT": "2026-09-17T22:30:00Z"}
        self.control = {"schema_version": "amadeus-autonomous-task-state-1", "tasks": [self.task],
                        "TARGET_CONCURRENCY": 4, "ACTIVE_WORKERS": 1, "AVAILABLE_SLOTS": 3}
        self.github = {"schema_version": "amadeus-github-observation-1", "repository": "Lorenzo-Holmes/Amadeus",
                       "source_sha": SHA, "observed_at": NOW, "branches": {"feature-c": HEAD},
                       "pull_requests": [{"url": self.task["PR"], "head_ref": "feature-c", "head_sha": HEAD, "state": "open"}]}
        self.protected = {"schema_version": "amadeus-protected-baseline-1", "files": [
            {"path": "protected/frozen.bin", "sha256": hashlib.sha256(b"synthetic frozen bytes").hexdigest()}]}
        self.flight = {"unresolved_requests": []}
        self.spend = {"journal": "evidence/journal.sqlite3", "unknown_count": 0}
        self.progress()
        self.sync()

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())

    def sync(self):
        for name, value in ((a.PLAN + "/TASK_STATE.json", self.operation),
                            (a.PLAN + "/ACCEPTANCE_MATRIX.json", self.matrix), (a.CONTROL, self.control),
                            ("snapshot.json", self.github), ("protected.json", self.protected)):
            self.put(name, a.stable(value))

    def progress(self, plan=PLAN_ID):
        self.put(a.PROGRESS, "<!-- G6_ACTIVE_START -->\n# " + plan + " - synthetic fixture\n"
                 "CURRENT_STATE: SYNTHETIC_PENDING\nLAST_COMPLETED: G6-06\n"
                 "RECOVERY_POINT: evidence/cursor.json\nIN_FLIGHT: " + json.dumps(self.flight) +
                 "\nSPEND: " + json.dumps(self.spend) + "\n<!-- G6_ACTIVE_END -->\n"
                 "# Historical section\nCURRENT_STATE: HISTORICAL_PASS\n")

    def run_audit(self, **kwargs):
        options = {"as_of": NOW, "github_snapshot": self.root / "snapshot.json",
                   "protected_baseline": self.root / "protected.json"}
        options.update(kwargs)
        return a.audit(self.root, **options)

    def codes(self, **kwargs):
        return {f["code"] for f in self.run_audit(**kwargs)["findings"]}

    def add_task(self, pattern="tools/d/**", owner="WORKER-D"):
        other = dict(self.task, TASK_ID="D01", OWNER=owner, WRITE_SET=[pattern])
        self.control["tasks"].append(other)
        self.control.update(ACTIVE_WORKERS=2, AVAILABLE_SLOTS=2)
        self.sync()
        return other

    def test_clean_observations_do_not_grant_acceptance_or_authenticity(self):
        report = self.run_audit()
        self.assertEqual(report["status"], "OBSERVATIONS_ONLY")
        for field in ("semantic_acceptance", "product_acceptance", "replay_authorized"):
            self.assertIs(report[field], False)
        self.assertFalse(report["observations"]["current_journal_contents_verified"])
        self.assertFalse(report["observations"]["protected_baseline_provenance_verified"])

    def test_different_phase_is_unknown_not_historical_failure(self):
        self.operation["plan_id"] = self.matrix["plan_id"] = "APCORE-OPERATIONS-V1"
        self.sync()
        report = self.run_audit()
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertIn("SCOPE_RECONCILIATION_REQUIRED", self.codes())
        self.assertEqual(report["observations"]["operations_declaration"]["plan_id"], "APCORE-OPERATIONS-V1")
        self.assertEqual(report["observations"]["active_progress"]["plan_id"], PLAN_ID)

    def test_old_trailing_status_does_not_override_active(self):
        self.assertEqual(self.run_audit()["observations"]["active_progress"]["CURRENT_STATE"], "SYNTHETIC_PENDING")

    def test_missing_duplicate_reversed_markers_are_unknown(self):
        original = (self.root / a.PROGRESS).read_text()
        for replacement in (original.replace("<!-- G6_ACTIVE_START -->", ""),
                            original + "<!-- G6_ACTIVE_START -->", "<!-- G6_ACTIVE_END --><!-- G6_ACTIVE_START -->"):
            with self.subTest(replacement=replacement[:30]):
                self.put(a.PROGRESS, replacement)
                self.assertIn("ACTIVE_PROGRESS_AMBIGUOUS", self.codes())

    def test_blank_active_field_cannot_consume_next_line(self):
        raw = (self.root / a.PROGRESS).read_text().replace("CURRENT_STATE: SYNTHETIC_PENDING", "CURRENT_STATE:")
        self.put(a.PROGRESS, raw)
        self.assertIn("ACTIVE_FIELD_AMBIGUOUS", self.codes())
        self.assertIsNone(self.run_audit()["observations"]["active_progress"]["CURRENT_STATE"])

    def test_duplicate_active_field_is_unknown(self):
        raw = (self.root / a.PROGRESS).read_text().replace("LAST_COMPLETED: G6-06", "LAST_COMPLETED: G6-06\nLAST_COMPLETED: G6-05")
        self.put(a.PROGRESS, raw)
        self.assertIn("ACTIVE_FIELD_AMBIGUOUS", self.codes())

    def test_unresolved_request_survives_missing_journal(self):
        self.flight["unresolved_requests"] = [{"call_id": "synthetic-call", "slot_id": "N06_T4", "raw_sha256": None}]
        self.spend["unknown_count"] = 1
        self.progress()
        (self.root / "evidence/journal.sqlite3").unlink()
        report = self.run_audit()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["observations"]["reported_unresolved_requests"], [{"call_id": "synthetic-call", "slot_id": "N06_T4"}])
        self.assertIn("CURRENT_JOURNAL_UNAVAILABLE", self.codes())
        self.assertIn("REPORTED_UNRESOLVED_REQUESTS", self.codes())
        self.assertFalse(report["replay_authorized"])

    def test_missing_inventory_never_becomes_empty_success(self):
        self.flight = {}
        self.progress()
        report = self.run_audit()
        self.assertIn("UNRESOLVED_INVENTORY_INVALID", self.codes())
        self.assertNotIn("reported_unresolved_requests", report["observations"])

    def test_mismatched_unknown_count_is_conflict(self):
        self.spend["unknown_count"] = 1
        self.progress()
        self.assertEqual(self.run_audit()["status"], "CONFLICT")
        self.assertIn("UNRESOLVED_COUNT_MISMATCH", self.codes())

    def test_missing_canonical_and_cursor_are_blocked(self):
        (self.root / "persona_core/gpt6_optimization_v2/CURSOR.json").unlink()
        (self.root / "persona_core/gpt6_optimization_v2").rmdir()
        (self.root / "evidence/cursor.json").unlink()
        self.assertTrue({"CURRENT_CANONICAL_UNAVAILABLE", "CURRENT_CURSOR_UNAVAILABLE"} <= self.codes())
        self.assertEqual(self.run_audit()["status"], "BLOCKED")

    def test_bad_active_json_is_unknown_not_crash(self):
        self.put(a.PROGRESS, (self.root / a.PROGRESS).read_text().replace('"unknown_count": 0', '"unknown_count": NaN'))
        self.assertIn("ACTIVE_JSON_INVALID", self.codes())

    def test_pass_gate_missing_evidence_is_blocked(self):
        (self.root / "persona_core/operational_runtime_v1/source.py").unlink()
        report = self.run_audit()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("GATE_EVIDENCE_UNAVAILABLE", self.codes())
        self.assertIsNone(report["observations"]["gate_evidence"][0]["semantic_verdict"])

    def test_internal_parent_reference_is_allowed_but_only_available(self):
        row = self.run_audit()["observations"]["gate_evidence"][0]
        self.assertEqual(row["availability"], "AVAILABLE_UNVERIFIED")
        self.assertEqual(row["path"], "persona_core/operational_runtime_v1/source.py")
        self.assertIsNone(row["semantic_verdict"])

    def test_gate_empty_evidence_and_duplicate_ids_not_pass(self):
        self.matrix["gates"] *= 2
        self.matrix["gates"][0]["evidence"] = []
        self.sync()
        self.assertTrue({"DUPLICATE_GATE_ID", "GATE_EVIDENCE_UNSPECIFIED"} <= self.codes())

    def test_missing_invalid_utf8_oversize_and_wrong_json_shape(self):
        path = a.PLAN + "/TASK_STATE.json"
        for content in (b"\xff", b"x" * (a.MAX_TEXT_BYTES + 1), b"[]", b"{"):
            with self.subTest(size=len(content)):
                self.put(path, content)
                self.assertNotEqual(self.run_audit()["status"], "OBSERVATIONS_ONLY")
        (self.root / path).unlink()
        self.assertIn("INPUT_UNAVAILABLE_OR_INVALID", self.codes())

    def test_duplicate_keys_and_nonfinite_numbers_are_rejected(self):
        for raw in ('{"a": 1, "a": 2}', '{"x": NaN}', '{"x": Infinity}', '{"x": 1e9999}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                a.strict_json(raw)

    def test_unsupported_schema_and_bad_nested_shapes(self):
        self.control["schema_version"] = "future-schema"
        self.sync()
        self.assertIn("JSON_OR_SCHEMA_INVALID", self.codes())
        self.control["schema_version"] = "amadeus-autonomous-task-state-1"
        self.control["tasks"] = {}
        self.sync()
        self.assertIn("TASK_INVENTORY_INVALID", self.codes())

    def test_expired_lease_stays_active_until_reconciled(self):
        self.task["LEASE_EXPIRES_AT"] = NOW
        self.sync()
        report = self.run_audit()
        self.assertIn("LEASE_RECONCILIATION_REQUIRED", self.codes())
        self.assertEqual(report["observations"]["declared_active_tasks"], ["C01"])

    def test_naive_or_reversed_lease_unknown(self):
        for expiry in ("2026-09-17T22:30:00", "2026-09-17T17:30:00Z", None):
            with self.subTest(expiry=expiry):
                self.task["LEASE_EXPIRES_AT"] = expiry
                self.sync()
                self.assertIn("LEASE_INVALID", self.codes())

    def test_as_of_not_inferred_from_clock(self):
        report = self.run_audit(as_of=None)
        self.assertIn("AS_OF_REQUIRED_OR_INVALID", self.codes(as_of=None))
        self.assertIsNone(report["as_of"])

    def test_counter_drift_is_conflict(self):
        self.control["ACTIVE_WORKERS"] = 0
        self.sync()
        self.assertIn("CONTROL_COUNTER_MISMATCH", self.codes())

    def test_duplicate_task_ids_and_owner_collision(self):
        other = self.add_task(owner="WORKER-C")
        other["TASK_ID"] = "C01"
        self.sync()
        self.assertTrue({"DUPLICATE_TASK_ID", "MULTIPLE_ACTIVE_TASKS_FOR_OWNER"} <= self.codes())

    def test_dependency_without_done_evidence_blocks(self):
        self.task["DEPENDENCIES"] = ["not-published"]
        self.sync()
        self.assertIn("DEPENDENCY_NOT_VERIFIED_COMPLETE", self.codes())

    def test_overlap_is_detected_and_adjacent_path_is_not(self):
        other = self.add_task("tools/c/nested/file.py")
        self.assertIn("ACTIVE_WRITE_OVERLAP", self.codes())
        other["WRITE_SET"] = ["tools/c2/**"]
        self.sync()
        self.assertNotIn("ACTIVE_WRITE_OVERLAP", self.codes())

    def test_unsupported_glob_is_unknown_not_safely_disjoint(self):
        self.add_task("tools/*/test_?.py")
        self.assertIn("WRITE_PATTERN_UNSUPPORTED", self.codes())

    def test_invalid_tasks_and_bool_counters_do_not_pass(self):
        self.control["tasks"].append(None)
        self.control["TARGET_CONCURRENCY"] = True
        self.sync()
        self.assertTrue({"TASK_INVALID", "COUNTER_INPUT_INVALID"} <= self.codes())

    def test_pr_branch_and_declared_head_mismatch(self):
        self.github["branches"]["feature-c"] = "c" * 40
        self.sync()
        self.assertTrue({"PR_BRANCH_HEAD_MISMATCH", "DECLARED_HEAD_MISMATCH"} <= self.codes())

    def test_missing_branch_row_is_unknown_not_absence(self):
        self.github["branches"] = {}
        self.sync()
        self.assertIn("BRANCH_NOT_OBSERVED", self.codes())
        self.assertEqual(self.run_audit()["status"], "UNKNOWN")

    def test_stale_future_or_invalid_snapshot_not_used_for_conflict(self):
        for time in ("2026-09-17T17:00:00Z", "2026-09-17T19:00:00Z", "not-a-time"):
            with self.subTest(time=time):
                self.github["observed_at"] = time
                self.github["branches"]["feature-c"] = "c" * 40
                self.sync()
                self.assertEqual(self.run_audit()["status"], "UNKNOWN")
                self.assertNotIn("PR_BRANCH_HEAD_MISMATCH", self.codes())

    def test_snapshot_wrong_repo_malformed_sha_and_duplicate_pr(self):
        self.github["repository"] = "other/repo"
        self.sync()
        self.assertIn("GITHUB_SCOPE_INVALID", self.codes())
        self.github["repository"] = "Lorenzo-Holmes/Amadeus"
        self.github["source_sha"] = "bad"
        self.sync()
        self.assertIn("GITHUB_SCOPE_INVALID", self.codes())
        self.github["source_sha"] = SHA
        self.github["pull_requests"] *= 2
        self.sync()
        self.assertIn("DUPLICATE_PR_OBSERVATION", self.codes())

    def test_matching_protected_hash_is_only_byte_observation(self):
        row = self.run_audit()["observations"]["protected_bytes_checked"][0]
        self.assertTrue(row["equal"])
        self.assertFalse(self.run_audit()["observations"]["protected_tree_coverage_verified"])

    def test_protected_mismatch_missing_and_bad_digest(self):
        self.put("protected/frozen.bin", b"changed")
        self.assertIn("PROTECTED_BYTES_MISMATCH", self.codes())
        (self.root / "protected/frozen.bin").unlink()
        self.assertIn("PROTECTED_ENTRY_UNVERIFIABLE", self.codes())
        self.protected["files"][0]["sha256"] = "not-a-hash"
        self.sync()
        self.assertIn("PROTECTED_ENTRY_UNVERIFIABLE", self.codes())

    def test_missing_optional_inputs_are_unknown(self):
        report = self.run_audit(github_snapshot=None, protected_baseline=None)
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(len([f for f in report["findings"] if f["code"] == "OPTIONAL_EVIDENCE_NOT_SUPPLIED"]), 2)

    def test_symlink_and_traversal_are_not_read_as_evidence(self):
        self.put("outside-looking.txt", "synthetic")
        (self.root / "link").symlink_to(self.root / "outside-looking.txt")
        auditor = a.Auditor(self.root, NOW)
        for name in ("link", "../escape", "/absolute", "C:\\private", "../" + self.root.name + "/outside-looking.txt"):
            with self.subTest(name=name):
                status, _ = auditor.availability(name)
                self.assertEqual(status, "UNSAFE_OR_UNREADABLE")
        self.protected["files"][0]["path"] = "link"
        self.sync()
        self.assertIn("PROTECTED_ENTRY_UNVERIFIABLE", self.codes())

    def test_read_only_integration_preserves_all_input_bytes_and_mtimes(self):
        def inventory():
            return {p.relative_to(self.root).as_posix(): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                    for p in self.root.rglob("*") if p.is_file()}
        before = inventory()
        self.run_audit()
        self.assertEqual(inventory(), before)

    def test_output_determinism_independent_of_absolute_root(self):
        first = a.stable(self.run_audit())
        self.assertEqual(a.stable(self.run_audit()), first)
        with tempfile.TemporaryDirectory() as other:
            target = Path(other)
            for path in self.root.rglob("*"):
                if path.is_file():
                    new = target / path.relative_to(self.root)
                    new.parent.mkdir(parents=True, exist_ok=True)
                    new.write_bytes(path.read_bytes())
            second = a.audit(target, as_of=NOW, github_snapshot=target / "snapshot.json", protected_baseline=target / "protected.json")
            self.assertEqual(a.stable(second), first)
        self.assertNotIn(str(self.root), first)

    def test_cli_json_and_status_codes(self):
        base = [sys.executable, str(SOURCE), "--root", str(self.root), "--as-of", NOW,
                "--github-snapshot", str(self.root / "snapshot.json"), "--protected-baseline", str(self.root / "protected.json")]
        env = dict(os.environ, PYTHONDONTWRITECODE="1")
        for expected, mutation in ((0, lambda: None),
                                   (4, lambda: self.task.update(LEASE_EXPIRES_AT=NOW)),
                                   (3, lambda: (self.root / "evidence/journal.sqlite3").unlink()),
                                   (2, lambda: self.control.update(ACTIVE_WORKERS=0))):
            mutation()
            self.sync()
            run = subprocess.run(base, capture_output=True, text=True, env=env, timeout=10)
            self.assertEqual(run.returncode, expected, run.stderr)
            self.assertEqual(run.stderr, "")
            self.assertFalse(json.loads(run.stdout)["semantic_acceptance"])

    def test_auditor_imports_no_runtime_provider_network_or_database(self):
        tree = ast.parse(SOURCE.read_text())
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(n.name.split(".")[0] for n in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module.split(".")[0])
        self.assertEqual(imports, {"__future__", "argparse", "datetime", "hashlib", "itertools", "json", "pathlib", "re"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
