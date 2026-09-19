"""Explicit authored offline fixtures; never emit real-day/candidate evidence."""
import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid

import candidate_day_v2 as g
import candidate_longitudinal_v2 as l


class Tests(unittest.TestCase):
    def fixture(self):
        rows = [{"turn_id": f"OFFLINE_t{i}", "call_id": f"OFFLINE_c{i}", "user_text": f"离线输入{i}，不是实际用户。",
                 "assistant_text": f"离线输出{i}，不是目标模型回答。", "display_at_utc": f"2026-01-0{i}T01:00:00Z",
                 "model": "OFFLINE_PRIMARY" if i == 1 else "OFFLINE_SECONDARY"} for i in range(1, 4)]
        bundle = {"classification": "OFFLINE_AUTHOR_FIXTURE", "binding": {"OFFLINE_ONLY": True},
                  "days": [{"observed_local_date": f"2026-01-0{i}", "observed_at_utc": f"2026-01-0{i}T02:00:00Z"} for i in range(1, 4)],
                  "evidence": {"rows": rows}, "retrieval": [{"retrieval_call_id": "OFFLINE_c2", "opening_turn_ids": ["OFFLINE_t1"]}],
                  "primary": "OFFLINE_PRIMARY", "secondary": "OFFLINE_SECONDARY"}
        review = l.blank_review(bundle)
        review["reviewer"].update(actor_type="DEVELOPER_AI", name_or_identifier="OFFLINE STRUCTURAL TEST (NOT AN ACTUAL REVIEW RETURN)",
            role="DEVELOPER", individual_item_adjudication=True, automatic_verdict_prefill=False, read_full_raw_inputs_outputs_context_and_events=True,
            participated_in_implementation=True, conflicts_of_interest=True,
            started_at_utc="2026-01-04T01:00:00Z", completed_at_utc="2026-01-04T02:00:00Z")
        def cite(row):
            return {"turn_id": row["turn_id"], "user_quote": row["user_text"], "assistant_quote": row["assistant_text"]}
        for turn, row in zip(review["turns"], rows):
            for j in turn["judgments"]:
                j.update(verdict="PASS", user_quote=row["user_text"], assistant_quote=row["assistant_text"], rationale="OFFLINE schema fixture only")
        for day, row in zip(review["days"], rows):
            for key, rated in day["quality"].items():
                rated.update(score=4, rationale="OFFLINE", evidence=[cite(row)])
        for item in review["longitudinal"]:
            item.update(verdict="PASS", rationale="OFFLINE", evidence=[cite(rows[0]), cite(rows[1])])
        review["findings_complete"] = True
        return bundle, review

    def test_blank_template_never_prefills_verdict_or_human_authorship(self):
        bundle, _ = self.fixture()
        blank = l.blank_review(bundle)
        self.assertFalse(blank["reviewer"]["individual_item_adjudication"])
        self.assertTrue(all(j["verdict"] is None for t in blank["turns"] for j in t["judgments"]))
        with self.assertRaisesRegex(g.GateError, "EXPLICIT_INDIVIDUAL_REVIEW"):
            l.bind_review(bundle, blank)

    def test_complete_offline_review_cannot_become_real_day_acceptance(self):
        bundle, review = self.fixture()
        report = l.bind_review(bundle, review)
        self.assertEqual(report["verdict_counts"], {"PASS": 12})
        self.assertEqual(report["status"], "OFFLINE_FIXTURE_ONLY")
        self.assertFalse(report["recorded_natural_day_gate_met"])
        self.assertEqual(report["qualified_real_date_count"], 0)
        self.assertFalse(report["product_acceptance_complete"])

    def test_structural_binding_never_substitutes_for_manual_turns(self):
        bundle, review = self.fixture()
        review["turns"].pop()
        with self.assertRaisesRegex(g.GateError, "EVERY_ORIGINAL_TURN"):
            l.bind_review(bundle, review)

    def test_invented_original_input_or_output_quote_is_rejected(self):
        bundle, baseline = self.fixture()
        for key in ("user_quote", "assistant_quote"):
            review = copy.deepcopy(baseline); review["turns"][0]["judgments"][0][key] = "不存在的引文"
            with self.subTest(key=key), self.assertRaisesRegex(g.GateError, "QUOTE_NOT_EXACT"):
                l.bind_review(bundle, review)

    def test_fail_unknown_and_low_quality_are_preserved(self):
        bundle, review = self.fixture()
        review["turns"][0]["judgments"][0]["verdict"] = "FAIL"
        review["turns"][1]["judgments"][0]["verdict"] = "UNKNOWN"
        review["days"][0]["quality"]["naturalness"]["score"] = 3
        report = l.bind_review(bundle, review)
        self.assertEqual(report["verdict_counts"], {"PASS": 10, "FAIL": 1, "UNKNOWN": 1})
        self.assertFalse(report["semantic_judgments_all_pass"])
        self.assertTrue(any(d["score"] == 3 for d in report["quality_diagnostics"]))

    def test_optional_daily_quality_diagnostics_do_not_invent_numeric_gate(self):
        bundle, review = self.fixture()
        review["days"][0]["quality"] = {}
        review["days"][1]["quality"]["naturalness"]["score"] = 1
        report = l.bind_review(bundle, review)
        self.assertTrue(report["semantic_judgments_all_pass"])
        self.assertFalse(report["quality_diagnostics_are_gate_thresholds"])
        self.assertTrue(any(d["score"] == 1 for d in report["quality_diagnostics"]))

    def test_open_major_finding_cannot_hide_behind_all_pass_judgments(self):
        bundle, review = self.fixture()
        review["findings"] = [{"id": "OFFLINE_F1", "severity": "MAJOR", "status": "OPEN", "rationale": "OFFLINE",
                               "evidence": review["longitudinal"][0]["evidence"]}]
        self.assertEqual(l.bind_review(bundle, review)["open_material_findings"], ["OFFLINE_F1"])

    def test_quality_and_longitudinal_quotes_must_cover_their_actual_dates(self):
        bundle, review = self.fixture()
        review["days"][1]["quality"]["naturalness"]["evidence"] = review["days"][0]["quality"]["naturalness"]["evidence"]
        with self.assertRaisesRegex(g.GateError, "WRONG_DAY"):
            l.bind_review(bundle, review)
        bundle, review = self.fixture()
        review["longitudinal"][0]["evidence"].pop()
        with self.assertRaisesRegex(g.GateError, "DISTINCT_DATES"):
            l.bind_review(bundle, review)

    def test_model_and_retrieval_obligations_need_relevant_raw_turns(self):
        bundle, review = self.fixture()
        bundle["retrieval"] = [{"retrieval_call_id": "OFFLINE_c3", "opening_turn_ids": ["OFFLINE_t1"]}]
        with self.assertRaisesRegex(g.GateError, "ACTUAL_RETRIEVAL_AND_OPENING_QUOTES"):
            l.bind_review(bundle, review)
        bundle, review = self.fixture()
        bundle["primary"] = "OTHER_MODEL_NOT_SHOWN"
        with self.assertRaisesRegex(g.GateError, "MODEL_SWITCH_QUOTES"):
            l.bind_review(bundle, review)

    def test_unknown_actor_auto_prefill_or_unread_context_is_not_item_review(self):
        bundle, baseline = self.fixture()
        for field, value in (("actor_type", "UNDECLARED_AUTOMATION"), ("individual_item_adjudication", False),
                             ("automatic_verdict_prefill", True),
                             ("read_full_raw_inputs_outputs_context_and_events", False)):
            review = copy.deepcopy(baseline); review["reviewer"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(g.GateError, "EXPLICIT_INDIVIDUAL_REVIEW"):
                l.bind_review(bundle, review)

    def test_reviewer_actor_is_separate_from_genuine_user_input_actor(self):
        bundle, review = self.fixture()
        report = l.bind_review(bundle, review)
        self.assertEqual(report["reviewer_actor_type"], "DEVELOPER_AI")
        self.assertFalse(report["review_is_independent_external_review"])
        review["reviewer"]["actor_type"] = "HUMAN"
        self.assertEqual(l.bind_review(bundle, review)["reviewer_actor_type"], "HUMAN")
        self.assertFalse(report["recorded_natural_day_gate_met"])

    def test_checkpoint_exclusion_lock_preserves_live_host_and_cleans_only_own_lock(self):
        with tempfile.TemporaryDirectory(prefix="APCORE_OFFLINE_LOCK_ONLY_") as scratch:
            parent = Path(scratch)
            candidate = parent / "NOT_A_CANDIDATE.json"
            active = parent / "ACTIVE_HOST.json"
            g.write_new(active, {"OFFLINE_OTHER_HOST": True})
            with self.assertRaisesRegex(g.GateError, "EXIT_HOST"):
                with l.checkpoint_lock(candidate):
                    self.fail("must not acquire")
            self.assertEqual(g.load(active), {"OFFLINE_OTHER_HOST": True})
            active.unlink()
            with l.checkpoint_lock(candidate):
                self.assertEqual(g.load(active)["purpose"], "CHECKPOINT_NO_PROVIDER")
            self.assertFalse(active.exists())
            self.assertFalse(candidate.exists())

    def test_resolved_major_requires_quote_bound_resolution(self):
        bundle, review = self.fixture()
        review["findings"] = [{"id": "OFFLINE_F1", "severity": "MAJOR", "status": "RESOLVED", "rationale": "OFFLINE",
                               "evidence": review["longitudinal"][0]["evidence"]}]
        with self.assertRaisesRegex(g.GateError, "BOUND_RESOLUTION"):
            l.bind_review(bundle, review)

    def test_content_snapshot_real_runtime_backup_has_no_day_claim(self):
        parent = g.ROOT / "persona_core/operational_build_v1/evidence/G6_V2_candidate_longitudinal_offline_tests"
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="AUTHOR_TEST_", dir=parent) as scratch:
            root = Path(scratch)
            scope = g.load(g.ROOT / "persona_core/operational_build_v1/evidence/R047-04/NATURAL_DAY_OBSERVATION_SCOPE.json")
            scope["batch_id"] = "OFFLINE_SNAPSHOT_" + uuid.uuid4().hex
            runtime, _, _, _, _ = g.initialize_clean_runtime(root, scope, principal="OFFLINE_TEST", entity_label="OFFLINE_TEST")
            before = g.sha(runtime / "runtime.sqlite3")
            backup = l.content_snapshot(runtime, root / "OFFLINE_CONTENT_ONLY")
            self.assertEqual(g.sha(runtime / "runtime.sqlite3"), before)
            self.assertEqual(backup["summary"]["tables"]["provider_calls"]["rows"], 0)
            self.assertEqual(backup["summary"]["tables"]["turns"]["rows"], 0)
            self.assertFalse((root / "OFFLINE_CONTENT_ONLY/CHECKPOINT.json").exists())
            self.assertFalse(list(root.rglob("CANDIDATE_MANIFEST.json")))
            import recovery
            (backup["path"] / "SANDBOX.json").write_text("tampered offline", encoding="utf-8")
            with self.assertRaises(Exception):
                recovery.verify_backup(backup["path"], backup["sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
