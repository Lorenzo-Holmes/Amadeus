"""Offline observations only. Never writes inputs, grants authority or replays calls.

Use a quiescent checkout and PYTHONDONTWRITEBYTECODE=1. This is not a hostile
filesystem sandbox or a verifier of snapshot authenticity/semantic correctness.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from itertools import combinations
import json
from pathlib import Path, PurePosixPath
import re

PLAN = "persona_core/operational_build_v1"
PROGRESS = "PERSONA_CORE_PROGRESS.md"
CONTROL = ".autonomous/AUTONOMOUS_TASK_STATE.json"
MAX_TEXT_BYTES = 2 * 1024 * 1024
EXIT = {"OBSERVATIONS_ONLY": 0, "UNKNOWN": 4, "BLOCKED": 3, "CONFLICT": 2}
PRIORITY = {name: i for i, name in enumerate(EXIT)}
ACTIVE = {"CLAIMED", "RUNNING"}
STATUSES = ACTIVE | {"READY", "REVIEW", "BLOCKED", "DONE", "COMPLETED", "CANCELLED", "IDLE"}


def stable(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False) + "\n"


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("non-finite JSON number")

    def finite(value):
        number = float(value)
        if not -float("inf") < number < float("inf"):
            raise ValueError("non-finite JSON number")
        return number

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant, parse_float=finite)


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value):
    return isinstance(value, list) and all(text(item) for item in value)


def digest(value, length):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{%d}" % length, value) is not None


def relative_name(value, base=""):
    """Normalize internal ../ evidence references, but reject escape and ambiguity."""
    if not text(value) or "\\" in value or ":" in value or any(ord(c) < 32 for c in value):
        raise ValueError("unsafe path")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise ValueError("absolute path")
    parts = list(PurePosixPath(base).parts)
    for part in path.parts:
        if part == "..":
            if not parts:
                raise ValueError("path escape")
            parts.pop()
        elif part != ".":
            parts.append(part)
    if not parts:
        raise ValueError("empty path")
    return "/".join(parts)


def pattern(value):
    if not text(value):
        raise ValueError("write pattern required")
    subtree = value.endswith("/**")
    prefix = value[:-3] if subtree else value
    if any(c in prefix for c in "*?[]") or ".." in PurePosixPath(prefix).parts:
        raise ValueError("unsupported pattern")
    return relative_name(prefix), subtree


def overlaps(a, b):
    left, left_tree = pattern(a)
    right, right_tree = pattern(b)
    return (left == right or (left_tree and right.startswith(left + "/"))
            or (right_tree and left.startswith(right + "/")))


class Auditor:
    def __init__(self, root, as_of=None):
        self.root = Path(root).resolve()
        self.findings = []
        self.sources = {}
        self.observations = {}
        self.as_of = None
        try:
            self.as_of = timestamp(as_of)
        except (ValueError, TypeError, OverflowError):
            self.add("UNKNOWN", "AS_OF_REQUIRED_OR_INVALID", "as_of")
        if not self.root.is_dir():
            self.add("BLOCKED", "ROOT_UNAVAILABLE", "root")

    def add(self, status, code, source, **details):
        self.findings.append(dict(status=status, code=code, source=source, **details))

    def safe(self, name, base=""):
        relative = relative_name(name, base)
        current = self.root
        for part in relative.split("/"):
            current = current / part
            if current.is_symlink():
                raise ValueError("symlink")
        return current, relative

    def availability(self, name, base="", directory=False):
        try:
            path, relative = self.safe(name, base)
            present = path.is_dir() if directory else path.is_file()
            return ("AVAILABLE_UNVERIFIED" if present else "MISSING_OR_UNREADABLE"), relative
        except (ValueError, OSError, RuntimeError):
            return "UNSAFE_OR_UNREADABLE", "rejected_reference"

    def read(self, name, external=None):
        try:
            path = Path(external) if external is not None else self.safe(name)[0]
            if path.is_symlink() or not path.is_file():
                raise ValueError("not a regular file")
            with path.open("rb") as stream:
                data = stream.read(MAX_TEXT_BYTES + 1)
            if len(data) > MAX_TEXT_BYTES:
                raise ValueError("too large")
            self.sources[name] = hashlib.sha256(data).hexdigest()
            return data.decode("utf-8")
        except (OSError, ValueError, RuntimeError):
            self.add("UNKNOWN", "INPUT_UNAVAILABLE_OR_INVALID", name)
            return None

    def load(self, name, schema, external=None):
        raw = self.read(name, external)
        if raw is None:
            return None
        try:
            result = strict_json(raw)
            if not isinstance(result, dict) or result.get("schema_version") != schema:
                raise ValueError("schema")
            return result
        except (ValueError, RecursionError):
            self.add("UNKNOWN", "JSON_OR_SCHEMA_INVALID", name)
            return None

    def progress(self, raw, operations):
        start, end = "<!-- G6_ACTIVE_START -->", "<!-- G6_ACTIVE_END -->"
        if raw is None:
            return
        if raw.count(start) != 1 or raw.count(end) != 1 or raw.index(start) >= raw.index(end):
            self.add("UNKNOWN", "ACTIVE_PROGRESS_AMBIGUOUS", PROGRESS)
            return
        block = raw.split(start, 1)[1].split(end, 1)[0]
        headings = re.findall(r"^# (APCORE-[A-Z0-9-]+)(?:\s|$)", block, re.M)
        if len(headings) != 1:
            self.add("UNKNOWN", "ACTIVE_PLAN_AMBIGUOUS", PROGRESS)
            return
        fields = {}
        for key in ("CURRENT_STATE", "LAST_COMPLETED", "RECOVERY_POINT", "IN_FLIGHT", "SPEND"):
            values = re.findall(r"^" + key + r":[ \t]*([^\n]*)$", block, re.M)
            if len(values) != 1 or not values[0].strip():
                self.add("UNKNOWN", "ACTIVE_FIELD_AMBIGUOUS", PROGRESS, field=key)
            else:
                fields[key] = values[0].strip()
        self.observations["active_progress"] = {"plan_id": headings[0], **{
            key: fields.get(key) for key in ("CURRENT_STATE", "LAST_COMPLETED")}}
        if operations and operations.get("plan_id") != headings[0]:
            self.add("UNKNOWN", "SCOPE_RECONCILIATION_REQUIRED", PROGRESS,
                     operations_plan=operations.get("plan_id"), active_plan=headings[0])
        if headings[0] == "APCORE-GPT6-OPTIMIZATION-V2":
            status, name = self.availability("persona_core/gpt6_optimization_v2", directory=True)
            if status != "AVAILABLE_UNVERIFIED":
                self.add("BLOCKED", "CURRENT_CANONICAL_UNAVAILABLE", name)
        if "RECOVERY_POINT" in fields:
            status, name = self.availability(fields["RECOVERY_POINT"])
            if status != "AVAILABLE_UNVERIFIED":
                self.add("BLOCKED", "CURRENT_CURSOR_UNAVAILABLE", name)
        decoded = {}
        for key in ("IN_FLIGHT", "SPEND"):
            try:
                value = strict_json(fields[key])
                if not isinstance(value, dict):
                    raise ValueError("object required")
                decoded[key] = value
            except (KeyError, ValueError, RecursionError):
                self.add("UNKNOWN", "ACTIVE_JSON_INVALID", PROGRESS, field=key)
        flight, spend = decoded.get("IN_FLIGHT", {}), decoded.get("SPEND", {})
        requests = flight.get("unresolved_requests")
        if not isinstance(requests, list) or not all(isinstance(r, dict) and
                text(r.get("call_id")) and text(r.get("slot_id")) for r in requests):
            self.add("UNKNOWN", "UNRESOLVED_INVENTORY_INVALID", PROGRESS)
        else:
            identifiers = [{k: r[k] for k in ("call_id", "slot_id")} for r in requests]
            self.observations["reported_unresolved_requests"] = sorted(identifiers, key=stable)
            if requests:
                self.add("BLOCKED", "REPORTED_UNRESOLVED_REQUESTS", PROGRESS,
                         requests=self.observations["reported_unresolved_requests"])
            count = spend.get("unknown_count")
            if type(count) is not int or count < 0:
                self.add("UNKNOWN", "UNKNOWN_COUNT_INVALID", PROGRESS)
            elif count != len(requests):
                self.add("CONFLICT", "UNRESOLVED_COUNT_MISMATCH", PROGRESS)
        status, name = self.availability(spend.get("journal"))
        self.observations["current_journal_availability"] = status
        if status != "AVAILABLE_UNVERIFIED":
            self.add("BLOCKED", "CURRENT_JOURNAL_UNAVAILABLE", name)
        self.observations["current_journal_contents_verified"] = False

    def matrix(self, matrix, operations):
        if matrix is None:
            return
        if operations and matrix.get("plan_id") != operations.get("plan_id"):
            self.add("CONFLICT", "MATRIX_TASK_PLAN_MISMATCH", PLAN)
        gates = matrix.get("gates")
        if not isinstance(gates, list) or not gates:
            self.add("UNKNOWN", "GATE_INVENTORY_INVALID", PLAN)
            return
        rows, seen = [], set()
        for gate in gates:
            if not isinstance(gate, dict) or not text(gate.get("id")) or not text(gate.get("status")):
                self.add("UNKNOWN", "GATE_INVALID", PLAN)
                continue
            name = gate["id"]
            if name in seen:
                self.add("CONFLICT", "DUPLICATE_GATE_ID", name)
            seen.add(name)
            refs = gate.get("evidence")
            if not strings(refs) or not refs:
                self.add("UNKNOWN", "GATE_EVIDENCE_UNSPECIFIED", name)
                continue
            for ref in refs:
                status, normalized = self.availability(ref, PLAN)
                rows.append(dict(gate=name, declared_status=gate["status"], path=normalized,
                                 availability=status, semantic_verdict=None))
                if status != "AVAILABLE_UNVERIFIED":
                    self.add("BLOCKED" if gate["status"] == "PASS" else "UNKNOWN",
                             "GATE_EVIDENCE_UNAVAILABLE", name, path=normalized)
        self.observations["gate_evidence"] = sorted(rows, key=stable)

    def control(self, control):
        if control is None:
            return []
        tasks = control.get("tasks")
        if not isinstance(tasks, list):
            self.add("UNKNOWN", "TASK_INVENTORY_INVALID", CONTROL)
            return []
        valid, seen = [], set()
        for task in tasks:
            if not isinstance(task, dict) or not all(text(task.get(k)) for k in ("TASK_ID", "OWNER", "STATUS")):
                self.add("UNKNOWN", "TASK_INVALID", CONTROL)
                continue
            name = task["TASK_ID"]
            if name in seen:
                self.add("CONFLICT", "DUPLICATE_TASK_ID", name)
            seen.add(name)
            valid.append(task)
            if task["STATUS"] not in STATUSES:
                self.add("UNKNOWN", "TASK_STATUS_UNSUPPORTED", name)
        active = [task for task in valid if task["STATUS"] in ACTIVE]
        self.observations["declared_active_tasks"] = sorted(t["TASK_ID"] for t in active)
        target = control.get("TARGET_CONCURRENCY")
        if type(target) is not int or target < 1 or len(valid) != len(tasks):
            self.add("UNKNOWN", "COUNTER_INPUT_INVALID", CONTROL)
        else:
            if len(active) > target:
                self.add("CONFLICT", "CONCURRENCY_LIMIT_EXCEEDED", CONTROL)
            for key, expected in (("ACTIVE_WORKERS", len(active)),
                                  ("AVAILABLE_SLOTS", max(0, target - len(active)))):
                if type(control.get(key)) is not int or control[key] != expected:
                    self.add("CONFLICT", "CONTROL_COUNTER_MISMATCH", CONTROL, field=key, expected=expected)
        index = {t["TASK_ID"]: t for t in valid}
        for task in active:
            name = task["TASK_ID"]
            if not digest(task.get("BASE_SHA"), 40):
                self.add("UNKNOWN", "TASK_BASE_SHA_INVALID", name)
            if not text(task.get("BRANCH")):
                self.add("UNKNOWN", "ACTIVE_BRANCH_UNSPECIFIED", name)
            try:
                start, end = (timestamp(task.get(k)) for k in ("LEASE_STARTED_AT", "LEASE_EXPIRES_AT"))
                if end <= start:
                    raise ValueError("lease interval")
                if self.as_of and (self.as_of < start or self.as_of >= end):
                    self.add("UNKNOWN", "LEASE_RECONCILIATION_REQUIRED", name)
            except (ValueError, TypeError, OverflowError):
                self.add("UNKNOWN", "LEASE_INVALID", name)
            deps = task.get("DEPENDENCIES")
            if not strings(deps):
                self.add("UNKNOWN", "DEPENDENCIES_INVALID", name)
            else:
                for dependency in deps:
                    if index.get(dependency, {}).get("STATUS") not in {"DONE", "COMPLETED"}:
                        self.add("BLOCKED", "DEPENDENCY_NOT_VERIFIED_COMPLETE", name, dependency=dependency)
            writes = task.get("WRITE_SET")
            if not strings(writes):
                self.add("UNKNOWN", "WRITE_SET_INVALID", name)
            else:
                for item in writes:
                    try:
                        pattern(item)
                    except ValueError:
                        self.add("UNKNOWN", "WRITE_PATTERN_UNSUPPORTED", name, pattern=item)
        for left, right in combinations(active, 2):
            names = sorted([left["TASK_ID"], right["TASK_ID"]])
            if left["OWNER"] == right["OWNER"]:
                self.add("CONFLICT", "MULTIPLE_ACTIVE_TASKS_FOR_OWNER", CONTROL, tasks=names)
            if not strings(left.get("WRITE_SET")) or not strings(right.get("WRITE_SET")):
                continue
            for a in left["WRITE_SET"]:
                for b in right["WRITE_SET"]:
                    try:
                        if overlaps(a, b):
                            self.add("CONFLICT", "ACTIVE_WRITE_OVERLAP", CONTROL, tasks=names,
                                     patterns=sorted([a, b]))
                    except ValueError:
                        pass  # Already reported UNKNOWN above, never declared disjoint.
        return valid

    def github(self, snapshot, tasks):
        if snapshot is None:
            return
        if snapshot.get("repository") != "Lorenzo-Holmes/Amadeus" or not digest(snapshot.get("source_sha"), 40):
            self.add("UNKNOWN", "GITHUB_SCOPE_INVALID", "github_snapshot")
            return
        try:
            observed = timestamp(snapshot.get("observed_at"))
            if self.as_of and not 0 <= (self.as_of - observed).total_seconds() <= 3600:
                self.add("UNKNOWN", "GITHUB_OBSERVATION_NOT_FRESH", "github_snapshot")
                return
        except (ValueError, TypeError, OverflowError):
            self.add("UNKNOWN", "GITHUB_TIMESTAMP_INVALID", "github_snapshot")
            return
        branches, prs = snapshot.get("branches"), snapshot.get("pull_requests")
        if not isinstance(branches, dict) or not all(text(k) and digest(v, 40) for k, v in branches.items()):
            self.add("UNKNOWN", "BRANCH_OBSERVATIONS_INVALID", "github_snapshot")
            return
        if not isinstance(prs, list) or not all(isinstance(p, dict) and all(text(p.get(k)) for k in
                ("url", "head_ref", "state")) and digest(p.get("head_sha"), 40) for p in prs):
            self.add("UNKNOWN", "PR_OBSERVATIONS_INVALID", "github_snapshot")
            return
        if len({p["url"] for p in prs}) != len(prs):
            self.add("UNKNOWN", "DUPLICATE_PR_OBSERVATION", "github_snapshot")
            return
        by_url = {p["url"]: p for p in prs}
        for task in tasks:
            branch, name = task.get("BRANCH"), task["TASK_ID"]
            if not text(branch):
                continue
            head = branches.get(branch)
            if head is None:
                self.add("UNKNOWN", "BRANCH_NOT_OBSERVED", name)
                continue
            evidence = task.get("EVIDENCE")
            expected = evidence.get("head_sha") if isinstance(evidence, dict) else None
            if expected is not None and (not digest(expected, 40) or expected != head):
                self.add("CONFLICT", "DECLARED_HEAD_MISMATCH", name)
            if task["STATUS"] in ACTIVE and task.get("BASE_SHA") != snapshot["source_sha"]:
                self.add("UNKNOWN", "DECLARED_BASE_RECONCILIATION_REQUIRED", name)
            if task.get("PR"):
                pr = by_url.get(task["PR"]) if isinstance(task["PR"], str) else None
                if pr is None:
                    self.add("UNKNOWN", "PR_NOT_OBSERVED", name)
                elif pr["head_ref"] != branch or pr["head_sha"] != head:
                    self.add("CONFLICT", "PR_BRANCH_HEAD_MISMATCH", name)
                elif task["STATUS"] in ACTIVE | {"REVIEW"} and pr["state"] != "open":
                    self.add("UNKNOWN", "PR_STATE_RECONCILIATION_REQUIRED", name)
        self.observations["github_observations_authenticated"] = False

    def protected(self, manifest):
        if manifest is None:
            return
        entries = manifest.get("files")
        if not isinstance(entries, list) or not entries:
            self.add("UNKNOWN", "PROTECTED_BASELINE_EMPTY_OR_INVALID", "protected_baseline")
            return
        checked, seen = [], set()
        for entry in entries:
            try:
                if not isinstance(entry, dict) or not digest(entry.get("sha256"), 64):
                    raise ValueError("digest")
                path, name = self.safe(entry.get("path"))
                if name in seen:
                    raise ValueError("duplicate")
                seen.add(name)
                if not path.is_file():
                    raise ValueError("not file")
                with path.open("rb") as stream:
                    actual = hashlib.file_digest(stream, "sha256").hexdigest()
                equal = actual == entry["sha256"]
                checked.append(dict(path=name, observed_sha256=actual, expected_sha256=entry["sha256"], equal=equal))
                if not equal:
                    self.add("CONFLICT", "PROTECTED_BYTES_MISMATCH", name)
            except (OSError, ValueError, RuntimeError):
                self.add("UNKNOWN", "PROTECTED_ENTRY_UNVERIFIABLE", "protected_baseline")
        self.observations["protected_bytes_checked"] = sorted(checked, key=stable)
        self.observations["protected_baseline_provenance_verified"] = False
        self.observations["protected_tree_coverage_verified"] = False

    def run(self, control_state=None, github_snapshot=None, protected_baseline=None):
        for policy in ("AMADEUS_PERSONA_CORE_MASTER_GOAL.md", "PERSONA_CORE_CONTINUATION_PROTOCOL.md"):
            self.read(policy)
        decision = self.read("PERSONA_CORE_DECISION_LOG.md")
        if decision is not None:
            ids = re.findall(r"^## (DEC-G6-\d+)\b", decision, re.M)
            self.observations["last_listed_g6_decision"] = ids[-1] if ids else None
        self.observations["policy_and_decision_interpretation"] = "MANUAL_REVIEW_REQUIRED"
        operations = self.load(PLAN + "/TASK_STATE.json", "amadeus-operational-task-state-1")
        if operations is not None:
            if not all(text(operations.get(k)) for k in ("plan_id", "phase_status")):
                self.add("UNKNOWN", "OPERATIONS_STATE_INVALID", PLAN)
                operations = None
            else:
                self.observations["operations_declaration"] = {k: operations[k] for k in ("plan_id", "phase_status")}
        self.progress(self.read(PROGRESS), operations)
        self.matrix(self.load(PLAN + "/ACCEPTANCE_MATRIX.json", "amadeus-operational-acceptance-1"), operations)
        tasks = self.control(self.load(CONTROL, "amadeus-autonomous-task-state-1", control_state))
        for label, source, schema, check in (
                ("github_snapshot", github_snapshot, "amadeus-github-observation-1", lambda s: self.github(s, tasks)),
                ("protected_baseline", protected_baseline, "amadeus-protected-baseline-1", self.protected)):
            if source is None:
                self.add("UNKNOWN", "OPTIONAL_EVIDENCE_NOT_SUPPLIED", label)
            else:
                check(self.load(label, schema, source))
        unique = {stable(f): f for f in self.findings}
        findings = sorted(unique.values(), key=stable)
        status = max((f["status"] for f in findings), key=PRIORITY.get, default="OBSERVATIONS_ONLY")
        return dict(schema_version="amadeus-state-drift-audit-1", status=status,
                    as_of=self.as_of.isoformat() if self.as_of else None,
                    semantic_acceptance=False, product_acceptance=False, replay_authorized=False,
                    source_sha256=self.sources, observations=self.observations, findings=findings,
                    limitations=["Immutable checkout required; no atomic live-snapshot proof.",
                                 "Availability and byte equality are not semantic evidence validation.",
                                 "No provider journal contents, process liveness or external snapshot authenticity verified.",
                                 "Narrow marked-progress parser; policies and decisions require manual interpretation."])


def audit(root, **kwargs):
    return Auditor(root, kwargs.pop("as_of", None)).run(**kwargs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--as-of")
    parser.add_argument("--control-state")
    parser.add_argument("--github-snapshot")
    parser.add_argument("--protected-baseline")
    args = vars(parser.parse_args(argv))
    root = args.pop("root")
    result = audit(root, **args)
    print(stable(result), end="")
    return EXIT[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
