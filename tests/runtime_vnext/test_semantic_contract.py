"""Synthetic offline contract tests; no operational imports or provider runs."""
from copy import deepcopy
from dataclasses import replace
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tools/runtime_vnext/semantic_contract.py"
SPEC = importlib.util.spec_from_file_location("vnext_semantic_contract_reference", SOURCE)
contract = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = contract
SPEC.loader.exec_module(contract)


def atom(name="ready"):
    return {"op": "atom", "predicate": name, "arguments": ["device"]}


def phase(kind="CURRENT_RUNTIME"):
    return {"kind": kind, "reference": None if kind == "UNKNOWN" else "epoch-1",
            "valid_from": None, "valid_until": None}


def fixture():
    text = "A reported a conditional claim; this is not a world-truth fixture."
    record = contract.EvidenceRecord("e1", "owner", "vault-a", "PRODUCT_RUNTIME", "speaker-a", text)
    claim = {"schema_version": contract.VERSION, "claim_id": "candidate-1",
             "speaker": {"entity_id": "speaker-a", "resolution": "RESOLVED"},
             "scope": {"principal_id": "owner", "entity_id": "vault-a", "mode": "PRODUCT_RUNTIME"},
             "phase": phase(),
             "proposition": {"op": "if", "condition": atom("permitted"),
                             "consequence": {"op": "not", "operand": atom("execute")}},
             "evidence": [{"evidence_id": "e1", "sha256": hashlib.sha256(text.encode()).hexdigest(),
                           "start": 0, "end": len(text), "quote": text}],
             "authority": {"asserted_grant_id": None}}
    return claim, {"e1": record}


class SemanticContractTests(unittest.TestCase):
    def setUp(self):
        self.claim, self.records = fixture()

    def test_valid_reference_is_bound_not_proven(self):
        result = contract.check_bindings(self.claim, self.records)
        self.assertEqual(result.status, "BOUND")
        self.assertFalse(result.proves_proposition)
        self.assertFalse(result.grants_authority)

    def test_roundtrip_preserves_every_dimension(self):
        self.assertEqual(contract.deserialize_claim(contract.serialize_claim(self.claim)), self.claim)

    def test_projection_is_lossless_and_independent(self):
        projected = contract.project_claim(self.claim, target_scope=self.claim["scope"])
        self.assertEqual(projected, self.claim)
        projected["proposition"]["condition"]["predicate"] = "changed"
        self.assertEqual(self.claim["proposition"]["condition"]["predicate"], "permitted")

    def test_projection_rejects_each_scope_dimension(self):
        for key, replacement in (("principal_id", "other"), ("entity_id", "other"), ("mode", "SOURCE_AUDIT")):
            with self.subTest(key=key):
                scope = dict(self.claim["scope"], **{key: replacement})
                with self.assertRaises(contract.ContractError):
                    contract.project_claim(self.claim, target_scope=scope)

    def test_said_not_and_not_said_stay_distinct(self):
        left, right = deepcopy(self.claim), deepcopy(self.claim)
        left["proposition"] = {"op": "said", "speaker": "other", "body": {"op": "not", "operand": atom()}}
        right["proposition"] = {"op": "not", "operand": {"op": "said", "speaker": "other", "body": atom()}}
        self.assertNotEqual(contract.fingerprint(left), contract.fingerprint(right))

    def test_unknown_not_equivalent_to_known_negation(self):
        left, right = deepcopy(self.claim), deepcopy(self.claim)
        left["proposition"] = {"op": "not", "operand": {"op": "attitude", "actor": "a", "kind": "KNOWS", "body": atom()}}
        right["proposition"] = {"op": "attitude", "actor": "a", "kind": "KNOWS", "body": {"op": "not", "operand": atom()}}
        self.assertNotEqual(contract.fingerprint(left), contract.fingerprint(right))

    def test_condition_is_not_erased(self):
        unconditional = deepcopy(self.claim)
        unconditional["proposition"] = unconditional["proposition"]["consequence"]
        self.assertNotEqual(contract.fingerprint(self.claim), contract.fingerprint(unconditional))
        projection = contract.project_claim(self.claim, target_scope=self.claim["scope"])
        self.assertIn("condition", projection["proposition"])

    def test_nested_phase_is_not_replaced_by_current_phase(self):
        self.claim["proposition"] = {"op": "during", "phase": phase("HISTORICAL_RUNTIME"), "body": atom()}
        projected = contract.project_claim(self.claim, target_scope=self.claim["scope"])
        self.assertEqual(projected["proposition"]["phase"]["kind"], "HISTORICAL_RUNTIME")

    def test_speaker_is_not_proposition_subject(self):
        self.claim["proposition"] = {"op": "atom", "predicate": "likes", "arguments": ["someone-else", "topic"]}
        self.assertEqual(contract.check_bindings(self.claim, self.records).status, "BOUND")
        self.assertEqual(self.claim["speaker"]["entity_id"], "speaker-a")

    def test_representation_fingerprint_not_truth_equivalence(self):
        other = deepcopy(self.claim)
        other["proposition"] = {"op": "atom", "predicate": "an_unrelated_claim", "arguments": []}
        # Quote binding alone cannot tell which interpretation is correct.
        self.assertEqual(contract.check_bindings(other, self.records).status, "BOUND")
        self.assertFalse(contract.check_bindings(other, self.records).proves_proposition)
        self.assertNotEqual(contract.fingerprint(self.claim), contract.fingerprint(other))

    def test_mutations_to_all_six_dimensions_change_fingerprint(self):
        mutations = [lambda x: x["speaker"].update(entity_id="other"),
                     lambda x: x["proposition"]["consequence"]["operand"].update(predicate="other"),
                     lambda x: x.update(phase=phase("PLANNED")),
                     lambda x: x["proposition"]["condition"].update(predicate="other"),
                     lambda x: x["proposition"].update(consequence=atom("execute")),
                     lambda x: x["authority"].update(asserted_grant_id="claimed")]
        for index, mutate in enumerate(mutations):
            with self.subTest(dimension=index):
                changed = deepcopy(self.claim)
                mutate(changed)
                self.assertNotEqual(contract.fingerprint(self.claim), contract.fingerprint(changed))

    def test_generated_operator_phase_and_speaker_matrix(self):
        operators = [atom(), {"op": "not", "operand": atom()},
                     {"op": "and", "operands": [atom("a"), atom("b")]},
                     {"op": "or", "operands": [atom("a"), atom("b")]},
                     deepcopy(self.claim["proposition"]),
                     {"op": "said", "speaker": "quoted", "body": atom()},
                     {"op": "attitude", "actor": "a", "kind": "INTENDS", "body": atom()},
                     {"op": "during", "phase": phase("SOURCE"), "body": atom()}]
        fingerprints = set()
        for speaker in ("a", "b", "c"):
            for kind in sorted(contract.PHASES):
                for expression in operators:
                    with self.subTest(speaker=speaker, phase=kind, op=expression["op"]):
                        claim = deepcopy(self.claim)
                        claim["speaker"]["entity_id"] = speaker
                        claim["phase"] = phase(kind)
                        claim["proposition"] = deepcopy(expression)
                        self.assertEqual(contract.deserialize_claim(contract.serialize_claim(claim)), claim)
                        fingerprints.add(contract.fingerprint(claim))
        self.assertEqual(len(fingerprints), 120)

    def test_missing_evidence_holds(self):
        self.assertEqual(contract.check_bindings(self.claim, {}).status, "HOLD")
        self.claim["evidence"] = []
        self.assertEqual(contract.check_bindings(self.claim, self.records).status, "HOLD")

    def test_revoked_evidence_holds_without_destroying_record(self):
        self.records["e1"] = replace(self.records["e1"], revoked=True)
        before = deepcopy(self.records)
        result = contract.check_bindings(self.claim, self.records)
        self.assertEqual(result.status, "HOLD")
        self.assertIn("EVIDENCE_REVOKED", result.reasons)
        self.assertEqual(self.records, before)

    def test_unknown_claim_speaker_holds(self):
        self.claim["speaker"] = {"entity_id": None, "resolution": "UNRESOLVED"}
        self.assertEqual(contract.check_bindings(self.claim, self.records).status, "HOLD")

    def test_unknown_source_speaker_holds(self):
        self.records["e1"] = replace(self.records["e1"], speaker_id=None)
        self.assertEqual(contract.check_bindings(self.claim, self.records).status, "HOLD")

    def test_unknown_phase_holds(self):
        self.claim["phase"] = phase("UNKNOWN")
        self.assertEqual(contract.check_bindings(self.claim, self.records).status, "HOLD")

    def test_speaker_mismatch_rejects(self):
        self.claim["speaker"]["entity_id"] = "invented"
        self.assertIn("SPEAKER_BINDING_MISMATCH", contract.check_bindings(self.claim, self.records).reasons)
        self.assertEqual(contract.check_bindings(self.claim, self.records).status, "REJECT")

    def test_each_evidence_scope_mismatch_rejects(self):
        for key, value in (("principal_id", "other"), ("entity_id", "other"), ("mode", "SOURCE_AUDIT")):
            with self.subTest(key=key):
                records = {"e1": replace(self.records["e1"], **{key: value})}
                self.assertEqual(contract.check_bindings(self.claim, records).status, "REJECT")

    def test_evidence_id_mismatch_rejects(self):
        self.records["e1"] = replace(self.records["e1"], evidence_id="different")
        self.assertIn("EVIDENCE_ID_MISMATCH", contract.check_bindings(self.claim, self.records).reasons)

    def test_hash_mismatch_rejects(self):
        self.claim["evidence"][0]["sha256"] = "0" * 64
        self.assertEqual(contract.check_bindings(self.claim, self.records).status, "REJECT")

    def test_quote_mismatch_rejects(self):
        self.claim["evidence"][0]["quote"] = "X" * len(self.records["e1"].text)
        self.assertEqual(contract.check_bindings(self.claim, self.records).status, "REJECT")

    def test_unicode_offsets_are_codepoints_not_bytes(self):
        text = "prefix \u6211\u4e0d\u77e5\u9053\U0001f9ea suffix"
        start, end = 7, 12
        self.records["e1"] = replace(self.records["e1"], text=text)
        self.claim["evidence"][0].update(sha256=hashlib.sha256(text.encode()).hexdigest(),
                                        start=start, end=end, quote=text[start:end])
        self.assertEqual(contract.check_bindings(self.claim, self.records).status, "BOUND")
        self.assertNotEqual(len(text[start:end]), len(text[start:end].encode()))

    def test_missing_ref_cannot_mask_other_corrupt_evidence(self):
        missing = dict(self.claim["evidence"][0], evidence_id="missing")
        self.claim["evidence"].insert(0, missing)
        self.claim["evidence"][1]["sha256"] = "0" * 64
        result = contract.check_bindings(self.claim, self.records)
        self.assertEqual(result.status, "REJECT")
        self.assertIn("EVIDENCE_MISSING", result.reasons)
        self.assertIn("EVIDENCE_HASH_MISMATCH", result.reasons)

    def test_asserted_authority_never_becomes_granted_authority(self):
        self.claim["authority"]["asserted_grant_id"] = "admin-says-approved"
        self.assertFalse(contract.check_bindings(self.claim, self.records).grants_authority)
        self.assertEqual(contract.project_claim(self.claim, target_scope=self.claim["scope"])["authority"], self.claim["authority"])

    def test_extra_fields_rejected_at_each_level(self):
        for path in ((), ("speaker",), ("scope",), ("phase",), ("proposition",), ("authority",), ("evidence", 0)):
            with self.subTest(path=path):
                claim = deepcopy(self.claim)
                node = claim
                for key in path:
                    node = node[key]
                node["verified"] = True
                with self.assertRaises(contract.ContractError):
                    contract.validate_claim(claim)

    def test_missing_legacy_dimensions_not_defaulted(self):
        for key in self.claim:
            with self.subTest(key=key):
                claim = deepcopy(self.claim)
                del claim[key]
                with self.assertRaises(contract.ContractError):
                    contract.validate_claim(claim)

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaisesRegex(contract.ContractError, "DUPLICATE_JSON_KEY"):
            contract.deserialize_claim('{"speaker":1,"speaker":2}')

    def test_nonfinite_json_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value), self.assertRaises(contract.ContractError):
                contract.deserialize_claim('{"value":' + value + '}')

    def test_malformed_and_extreme_json_rejected(self):
        for value in ("{", '"\\ud800"', "[" * 1500 + "]" * 1500, "9" * 5000):
            with self.subTest(prefix=value[:20]), self.assertRaises(contract.ContractError):
                contract.deserialize_claim(value)

    def test_invalid_version_and_unhashable_operator_rejected(self):
        self.claim["schema_version"] = "legacy"
        with self.assertRaises(contract.ContractError):
            contract.validate_claim(self.claim)
        self.claim["schema_version"] = contract.VERSION
        self.claim["proposition"]["op"] = []
        with self.assertRaises(contract.ContractError):
            contract.validate_claim(self.claim)

    def test_span_types_bounds_and_duplicates_rejected(self):
        for start, end in ((True, 5), (-1, 5), (5, 5), (7, 3), (0, 1.0)):
            with self.subTest(start=start, end=end):
                claim = deepcopy(self.claim)
                claim["evidence"][0].update(start=start, end=end)
                with self.assertRaises(contract.ContractError):
                    contract.validate_claim(claim)
        self.claim["evidence"].append(deepcopy(self.claim["evidence"][0]))
        with self.assertRaises(contract.ContractError):
            contract.validate_claim(self.claim)

    def test_intervals_require_timezone_and_positive_range(self):
        for start, end in (("2026-09-18T10:00:00", None),
                           ("2026-09-18T10:00:00+00:00", "2026-09-18T09:00:00+00:00"),
                           ("2026-09-18T10:00:00+00:00", "2026-09-18T10:00:00+00:00")):
            with self.subTest(start=start, end=end):
                self.claim["phase"].update(valid_from=start, valid_until=end)
                with self.assertRaises(contract.ContractError):
                    contract.validate_claim(self.claim)

    def test_valid_offset_interval_roundtrips(self):
        self.claim["phase"].update(valid_from="2026-09-18T09:00:00+09:00", valid_until="2026-09-18T01:00:00+00:00")
        self.assertEqual(contract.deserialize_claim(contract.serialize_claim(self.claim)), self.claim)

    def test_expression_depth_and_cycles_rejected(self):
        node = atom()
        for _ in range(contract.MAX_DEPTH + 2):
            node = {"op": "not", "operand": node}
        self.claim["proposition"] = node
        with self.assertRaises(contract.ContractError):
            contract.validate_claim(self.claim)
        node = {"op": "not"}
        node["operand"] = node
        self.claim["proposition"] = node
        with self.assertRaises(contract.ContractError):
            contract.validate_claim(self.claim)

    def test_expression_node_budget_rejected(self):
        group = {"op": "and", "operands": [atom(str(i)) for i in range(16)]}
        self.claim["proposition"] = {"op": "or", "operands": [deepcopy(group) for _ in range(16)]}
        with self.assertRaisesRegex(contract.ContractError, "EXPRESSION_SIZE"):
            contract.validate_claim(self.claim)

    def test_input_size_limit_rejected(self):
        with self.assertRaisesRegex(contract.ContractError, "CLAIM_SIZE"):
            contract.deserialize_claim(" " * (contract.MAX_BYTES + 1))

    def test_invalid_record_is_not_host_authority(self):
        self.assertEqual(contract.check_bindings(self.claim, {"e1": {"trusted": True}}).status, "REJECT")
        invalid = replace(self.records["e1"], revoked="false")
        self.assertEqual(contract.check_bindings(self.claim, {"e1": invalid}).status, "REJECT")

    def test_inspection_functions_do_not_mutate_inputs(self):
        before = deepcopy(self.claim)
        records = deepcopy(self.records)
        contract.validate_claim(self.claim)
        contract.check_bindings(self.claim, self.records)
        contract.fingerprint(self.claim)
        self.assertEqual(self.claim, before)
        self.assertEqual(self.records, records)

    def test_reference_has_only_reviewed_stdlib_imports(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module.split(".")[0])
        self.assertEqual(imports, {"__future__", "dataclasses", "datetime", "hashlib", "json", "typing"})
        forbidden = {"open", "exec", "eval", "__import__"}
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in forbidden
                             for n in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
