"""Offline claim/evidence reference, NOT a parser or an admission authority.

No runtime imports, storage, credentials, provider calls, or state writes.
BOUND means quote/scope binding only, never truth, interpretation correctness,
permission, or G6 acceptance. EvidenceRecord is test input, not a host capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any, Mapping

VERSION = "amadeus.claim-reference.v1"
MODES = {"PRODUCT_RUNTIME", "CHARACTER_SIMULATION", "SOURCE_AUDIT"}
PHASES = {"CURRENT_RUNTIME", "HISTORICAL_RUNTIME", "SOURCE", "PLANNED", "UNKNOWN"}
MAX_BYTES = 65536
MAX_DEPTH = 24
MAX_NODES = 256


class ContractError(ValueError):
    """A malformed or out-of-scope reference, not a judgment of world truth."""


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ContractError(reason)


def _object(value: Any, keys: str) -> None:
    _require(type(value) is dict and set(value) == set(keys.split()), "FIELD_SET")


def _text(value: Any, limit: int = 256, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    _require(type(value) is str and 0 < len(value) <= limit and bool(value.strip()), "TEXT")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ContractError("INVALID_UNICODE") from exc


def _choice(value: Any, choices: set[str]) -> None:
    _require(type(value) is str and value in choices, "CHOICE")


def _scope(value: Any) -> None:
    _object(value, "principal_id entity_id mode")
    _text(value["principal_id"])
    _text(value["entity_id"])
    _choice(value["mode"], MODES)


def _phase(value: Any) -> None:
    _object(value, "kind reference valid_from valid_until")
    _choice(value["kind"], PHASES)
    if value["kind"] == "UNKNOWN":
        _require(value["reference"] is None, "UNKNOWN_PHASE_HAS_REFERENCE")
    else:
        _text(value["reference"])
    times = []
    for key in ("valid_from", "valid_until"):
        raw = value[key]
        if raw is None:
            times.append(None)
            continue
        _text(raw, 64)
        try:
            stamp = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ContractError("TIMESTAMP") from exc
        _require(stamp.tzinfo is not None and stamp.utcoffset() is not None, "TIMEZONE")
        times.append(stamp)
    if all(t is not None for t in times):
        _require(times[0] < times[1], "EMPTY_OR_REVERSED_INTERVAL")


def _node(value: Any, depth: int, budget: list[int]) -> None:
    _require(depth <= MAX_DEPTH, "EXPRESSION_DEPTH")
    budget[0] += 1
    _require(budget[0] <= MAX_NODES, "EXPRESSION_SIZE")
    _require(type(value) is dict, "EXPRESSION_OBJECT")
    op = value.get("op")
    _choice(op, {"atom", "not", "and", "or", "if", "said", "attitude", "during"})
    children = []
    if op == "atom":
        _object(value, "op predicate arguments")
        _text(value["predicate"])
        args = value["arguments"]
        _require(type(args) is list and len(args) <= 16, "ARGUMENTS")
        for arg in args:
            _text(arg)
    elif op == "not":
        _object(value, "op operand")
        children = [value["operand"]]
    elif op in {"and", "or"}:
        _object(value, "op operands")
        children = value["operands"]
        _require(type(children) is list and 2 <= len(children) <= 16, "OPERANDS")
    elif op == "if":
        _object(value, "op condition consequence")
        children = [value["condition"], value["consequence"]]
    elif op == "said":
        _object(value, "op speaker body")
        _text(value["speaker"])
        children = [value["body"]]
    elif op == "attitude":
        _object(value, "op actor kind body")
        _text(value["actor"])
        _choice(value["kind"], {"KNOWS", "BELIEVES", "INTENDS", "WISHES", "QUESTIONS"})
        children = [value["body"]]
    elif op == "during":
        _object(value, "op phase body")
        _phase(value["phase"])
        children = [value["body"]]
    for child in children:
        _node(child, depth + 1, budget)


def validate_claim(claim: Any) -> None:
    """Validate closed syntax only; do not infer facts from well-formed JSON."""
    _object(claim, "schema_version claim_id speaker scope phase proposition evidence authority")
    _require(claim["schema_version"] == VERSION, "SCHEMA_VERSION")
    _text(claim["claim_id"])
    _object(claim["speaker"], "entity_id resolution")
    speaker = claim["speaker"]
    _choice(speaker["resolution"], {"RESOLVED", "UNRESOLVED"})
    if speaker["resolution"] == "UNRESOLVED":
        _require(speaker["entity_id"] is None, "UNRESOLVED_SPEAKER_HAS_ID")
    else:
        _text(speaker["entity_id"])
    _scope(claim["scope"])
    _phase(claim["phase"])
    _node(claim["proposition"], 0, [0])
    _object(claim["authority"], "asserted_grant_id")
    _text(claim["authority"]["asserted_grant_id"], nullable=True)
    refs = claim["evidence"]
    _require(type(refs) is list and len(refs) <= 16, "EVIDENCE_REFS")
    seen = set()
    for ref in refs:
        _object(ref, "evidence_id sha256 start end quote")
        _text(ref["evidence_id"])
        sha = ref["sha256"]
        _require(type(sha) is str and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha), "SHA256")
        start, end = ref["start"], ref["end"]
        _require(type(start) is int and type(end) is int and 0 <= start < end, "SPAN")
        _text(ref["quote"], 8000)
        _require(end - start == len(ref["quote"]), "SPAN_LENGTH")
        key = (ref["evidence_id"], start, end)
        _require(key not in seen, "DUPLICATE_SPAN")
        seen.add(key)


def serialize_claim(claim: Any) -> str:
    validate_claim(claim)
    result = json.dumps(claim, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    _require(len(result.encode("utf-8")) <= MAX_BYTES, "CLAIM_SIZE")
    return result


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ContractError("NONFINITE_JSON_NUMBER")


def deserialize_claim(text: str) -> dict:
    _require(type(text) is str, "JSON_TEXT")
    try:
        _require(len(text.encode("utf-8")) <= MAX_BYTES, "CLAIM_SIZE")
        claim = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except ContractError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ContractError("INVALID_JSON") from exc
    validate_claim(claim)
    return claim


def fingerprint(claim: Any) -> str:
    """Representation identity, NOT semantic equivalence or runtime dedup."""
    return hashlib.sha256(serialize_claim(claim).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceRecord:
    """Synthetic/read-only binding input; NOT an authenticated host receipt."""
    evidence_id: str
    principal_id: str
    entity_id: str
    mode: str
    speaker_id: str | None
    text: str
    revoked: bool = False


@dataclass(frozen=True)
class BindingResult:
    status: str
    reasons: tuple[str, ...]

    @property
    def proves_proposition(self) -> bool:
        return False

    @property
    def grants_authority(self) -> bool:
        return False


def check_bindings(claim: dict, records: Mapping[str, EvidenceRecord]) -> BindingResult:
    """Bind quoted content; REJECT outranks HOLD across all evidence refs.

    Records must be supplied by the caller; no missing evidence is fetched.
    Even BOUND does not check that the AST correctly interprets the quotation.
    """
    serialize_claim(claim)
    errors, holds = [], []
    if not claim["evidence"]:
        holds.append("EVIDENCE_MISSING")
    if claim["speaker"]["resolution"] == "UNRESOLVED":
        holds.append("SPEAKER_UNRESOLVED")
    if claim["phase"]["kind"] == "UNKNOWN":
        holds.append("PHASE_UNRESOLVED")
    for ref in claim["evidence"]:
        record = records.get(ref["evidence_id"])
        if record is None:
            holds.append("EVIDENCE_MISSING")
            continue
        if type(record) is not EvidenceRecord:
            errors.append("INVALID_EVIDENCE_RECORD")
            continue
        try:
            _text(record.evidence_id)
            _scope({"principal_id": record.principal_id, "entity_id": record.entity_id, "mode": record.mode})
            _text(record.speaker_id, nullable=True)
            _text(record.text, 128000)
            _require(type(record.revoked) is bool, "REVOKED_FLAG")
        except ContractError:
            errors.append("INVALID_EVIDENCE_RECORD")
            continue
        if record.evidence_id != ref["evidence_id"]:
            errors.append("EVIDENCE_ID_MISMATCH")
        if any(getattr(record, key) != value for key, value in claim["scope"].items()):
            errors.append("EVIDENCE_SCOPE_MISMATCH")
        if hashlib.sha256(record.text.encode("utf-8")).hexdigest() != ref["sha256"]:
            errors.append("EVIDENCE_HASH_MISMATCH")
        if record.text[ref["start"]:ref["end"]] != ref["quote"]:
            errors.append("EVIDENCE_QUOTE_MISMATCH")
        if record.speaker_id is None:
            holds.append("SOURCE_SPEAKER_UNRESOLVED")
        elif claim["speaker"]["resolution"] == "RESOLVED" and record.speaker_id != claim["speaker"]["entity_id"]:
            errors.append("SPEAKER_BINDING_MISMATCH")
        if record.revoked:
            holds.append("EVIDENCE_REVOKED")
    reasons = tuple(sorted(set(errors + holds)))
    return BindingResult("REJECT" if errors else "HOLD" if holds else "BOUND", reasons)


def project_claim(claim: dict, *, target_scope: dict) -> dict:
    """Lossless, scope-checked copy; never flatten/truncate the proposition."""
    _scope(target_scope)
    serialized = serialize_claim(claim)
    _require(target_scope == claim["scope"], "PROJECTION_SCOPE_MISMATCH")
    return deserialize_claim(serialized)
