"""Authored offline host fixtures; no real TTY, candidate or paid provider call."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid

import candidate_day_v2 as g
import candidate_host_v2 as h


class Tests(unittest.TestCase):
    def setUp(self):
        parent = g.ROOT / "persona_core/operational_build_v1/evidence/G6_V2_candidate_host_offline_tests"
        parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="AUTHOR_TEST_", dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assertTrue(self.root.resolve().is_relative_to(parent.resolve()))

    def fixture(self):
        scope = g.load(g.ROOT / "persona_core/operational_build_v1/evidence/R047-04/NATURAL_DAY_OBSERVATION_SCOPE.json")
        scope["batch_id"] = "OFFLINE_HOST_" + uuid.uuid4().hex
        scope["principal_id"] = "AUTHOR_TEST_OPERATOR"
        for slot in scope["slots"]:
            slot["entity_label"] = "AUTHOR_TEST_ENTITY"
        runtime, handle, _, _, _ = g.initialize_clean_runtime(self.root, scope,
            principal=scope["principal_id"], entity_label="AUTHOR_TEST_ENTITY")
        transcript, _, _, provider = g.runtime_modules(g.ROOT)
        from operations import open_chat
        store = transcript.TranscriptStore(runtime)
        self.addCleanup(store.close)
        resumed = store.resume(scope["principal_id"], handle.session_id)
        service = open_chat(store, resumed, scope)
        candidate = {"candidate_id": "AUTHOR_TEST_NOT_A_CANDIDATE", "created_at_utc": datetime.now(timezone.utc).isoformat(),
                     "principal_id": scope["principal_id"], "entity_id": resumed.entity_id, "session_id": resumed.session_id,
                     "host_tool_bindings": g.host_tool_bindings()}
        return candidate, store, service, provider

    def test_file_pipe_and_fake_tty_object_cannot_produce_genuine_receipt(self):
        class PretendTTY(io.StringIO):
            def isatty(self):
                return True
        for stream in (io.StringIO("authored"), PretendTTY("authored")):
            with self.assertRaisesRegex(g.GateError, "REAL_LOCAL_TTY"):
                h.read_tty_line(stream, PretendTTY())

    def test_live_console_rejects_non_tty_before_any_candidate_mutation(self):
        with self.assertRaisesRegex(g.GateError, "REAL_LOCAL_TTY"):
            h.run_console(self.root / "NOT_A_CANDIDATE.json", self.root / "NO_PRICE.json")
        self.assertFalse((self.root / "ACTIVE_HOST.json").exists())

    def test_self_authored_genuine_label_without_tty_token_refused(self):
        candidate = {"host_tool_bindings": {h.HOST_NAME: "test"}}
        origin = h.HostInput("authored", datetime.now(timezone.utc).isoformat(),
                             "GENUINE_LOCAL_INTERACTIVE_USER", True, False, object())
        with self.assertRaisesRegex(g.GateError, "UNTRUSTED_HUMAN"):
            h.sign_ingress(origin, candidate, "t", b"x" * 32)

    def test_author_test_journal_display_receipt_stays_ineligible_for_real_day(self):
        candidate, store, service, provider = self.fixture()
        sent, displayed, checks = [], [], []
        key = b"x" * 32
        def transport(payload, credential):
            # Receipt and journal both exist before transport executes.
            sent.append(json.loads(payload))
            self.assertEqual(len(list((self.root / "HOST_INGRESS").glob("*.json"))), 1)
            self.assertEqual(store.db.execute("SELECT status FROM provider_calls").fetchone()[0], "SUBMITTED_STATUS_UNKNOWN")
            return 200, provider.canonical({"model": sent[-1]["model"], "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "收到，先讨论当前问题。"}}],
                                            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}})
        result = h.send_once(service, h.authored_test_input("这是明确的离线输入。"), candidate, self.root / "HOST_INGRESS", key,
            preflight=lambda: checks.append(True), display=displayed.append, transport=transport, credential_reader=lambda: "OFFLINE_KEY")
        self.assertEqual(result["status"], "DISPLAYED")
        self.assertEqual((len(sent), len(displayed), len(checks)), (1, 1, 2))
        row = dict(store.db.execute("SELECT p.*,t.user_text,t.assistant_text FROM provider_calls p JOIN turns t USING(turn_id)").fetchone())
        self.assertEqual(row["capture_origin"], "AUTHORED_PROVIDER_TEST_FIXTURE")
        receipt = g.load(self.root / "HOST_INGRESS" / (row["turn_id"] + ".json"))
        self.assertEqual(receipt["source_kind"], "AUTHOR_TEST")
        self.assertTrue(receipt["is_test"])
        with self.assertRaisesRegex(g.GateError, "NON_GENUINE_OR_TEST"):
            g.verify_ingress(receipt, key, candidate, row)
        self.assertFalse((self.root / "CHECKPOINT.json").exists())

    def test_unknown_stops_next_slot_without_second_transport(self):
        candidate, _, service, _ = self.fixture()
        sent = []
        def transport(payload, credential):
            sent.append(payload)
            raise TimeoutError("OFFLINE simulated unknown")
        args = dict(preflight=lambda: None, display=lambda _: None, transport=transport,
                    credential_reader=lambda: "OFFLINE_KEY")
        first = h.send_once(service, h.authored_test_input("离线第一句"), candidate, self.root / "HOST_INGRESS", b"x" * 32, **args)
        self.assertEqual(first["status"], "SUBMITTED_STATUS_UNKNOWN")
        with self.assertRaises(g.GateError):
            h.send_once(service, h.authored_test_input("离线第二句"), candidate, self.root / "HOST_INGRESS", b"x" * 32, **args)
        self.assertEqual(len(sent), 1)

    def test_second_preflight_failure_never_reaches_transport_or_credentials(self):
        candidate, store, service, _ = self.fixture()
        checks, sent, credentials = [], [], []
        def preflight():
            checks.append(True)
            if len(checks) == 2:
                raise g.GateError("SOURCE_CHANGED_AT_LAST_HOOK")
        with self.assertRaisesRegex(g.GateError, "SOURCE_CHANGED_AT_LAST_HOOK"):
            h.send_once(service, h.authored_test_input("离线输入"), candidate, self.root / "HOST_INGRESS", b"x" * 32,
                preflight=preflight, display=lambda _: None,
                transport=lambda *args: sent.append(args), credential_reader=lambda: credentials.append(True))
        self.assertEqual((len(sent), len(credentials)), (0, 0))
        self.assertEqual(store.db.execute("SELECT count(*) FROM provider_calls").fetchone()[0], 0)
        with self.assertRaisesRegex(g.GateError, "UNFINISHED_UNBOUND"):
            h.assert_no_unfinished_or_unbound_turns(service)

    def test_test_origin_cannot_select_real_official_transport(self):
        candidate, _, service, provider = self.fixture()
        with self.assertRaisesRegex(g.GateError, "AUTHOR_TEST_REQUIRES_OFFLINE_TRANSPORT"):
            h.send_once(service, h.authored_test_input("离线输入"), candidate, self.root / "HOST_INGRESS", b"x" * 32,
                preflight=lambda: None, display=lambda _: None, transport=provider.official_transport,
                credential_reader=lambda: "OFFLINE_KEY")

    def price(self):
        scope = g.load(g.ROOT / "persona_core/operational_build_v1/evidence/R047-04/NATURAL_DAY_OBSERVATION_SCOPE.json")
        _, _, _, provider = g.runtime_modules(g.ROOT)
        stamp = datetime(2026, 9, 17, 0, 0, tzinfo=timezone.utc)
        value = {"observation_date_local": "2026-09-17", "timezone": "Asia/Tokyo", "offline_only": False,
                 "models_confirmed": sorted({s["model"] for s in scope["slots"]}),
                 "peak_rates_cny_per_million_tokens": json.loads(json.dumps(scope["peak_rates_cny_per_million_tokens"])),
                 "thinking_types_confirmed": ["enabled"], "reasoning_efforts_confirmed": ["max"],
                 "reasoning_is_included_in_completion_usage": True,
                 "sources": ["https://api-docs.deepseek.com/OFFLINE_SCHEMA_TEST_NOT_AN_OBSERVATION"]}
        path = self.root / "AUTHOR_TEST_PRICE.json"
        g.write_new(path, value)
        return path, value, scope, provider, stamp

    def test_date_rollover_and_price_drift_reject_before_call(self):
        path, value, scope, provider, stamp = self.price()
        result = h.validate_pricing(path, g.sha(path), scope, provider, now=stamp)
        self.assertEqual(result["observed_local_date"], "2026-09-17")
        with self.assertRaisesRegex(g.GateError, "CURRENT_OFFICIAL"):
            h.validate_pricing(path, g.sha(path), scope, provider, now=datetime(2026, 9, 17, 15, 0, tzinfo=timezone.utc))
        changed = json.loads(json.dumps(value)); changed["peak_rates_cny_per_million_tokens"]["deepseek-v4-pro"]["output"] += 1
        path.write_bytes(g.canonical(changed))
        with self.assertRaisesRegex(g.GateError, "PRICE_DIFFERS"):
            h.validate_pricing(path, g.sha(path), scope, provider, now=stamp)

    def test_changed_price_file_and_missing_model_confirmation_rejected(self):
        path, value, scope, provider, stamp = self.price()
        previous = g.sha(path)
        value["models_confirmed"] = []
        path.write_bytes(g.canonical(value))
        with self.assertRaisesRegex(g.GateError, "PRICING_RECORD_CHANGED"):
            h.validate_pricing(path, previous, scope, provider, now=stamp)
        with self.assertRaisesRegex(g.GateError, "CURRENT_MODEL"):
            h.validate_pricing(path, g.sha(path), scope, provider, now=stamp)

    def test_official_flash_price_drop_preserves_frozen_conservative_ceiling(self):
        path, value, scope, provider, stamp = self.price()
        value["peak_rates_cny_per_million_tokens"]["deepseek-v4-flash"] = {
            "input_hit": 0.04, "input_miss": 2, "output": 8}
        path.write_bytes(g.canonical(value))
        result = h.validate_pricing(path, g.sha(path), scope, provider, now=stamp)
        self.assertEqual(result["official_rates_cny_per_million_tokens"]["deepseek-v4-flash"]["input_hit"], 0.04)
        self.assertEqual(result["conservative_ceiling_rates_cny_per_million_tokens"]["deepseek-v4-flash"]["input_hit"], 0.1)
        self.assertTrue(result["ceiling_rates_are_not_actual_billing"])
        for rate in ("input_hit", "input_miss", "output"):
            changed = json.loads(json.dumps(value))
            changed["peak_rates_cny_per_million_tokens"]["deepseek-v4-flash"][rate] = scope["peak_rates_cny_per_million_tokens"]["deepseek-v4-flash"][rate] + 0.01
            path.write_bytes(g.canonical(changed))
            with self.subTest(rate=rate), self.assertRaisesRegex(g.GateError, "PRICE_DIFFERS"):
                h.validate_pricing(path, g.sha(path), scope, provider, now=stamp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
