"""Host-bound sandbox sessions and utterance storage (R045-01).

Trust boundary: the local host/OS owns this API. Untrusted text is never parsed
as a principal, session handle, role, or event. Not an OS-user security sandbox.
"""
from __future__ import annotations
import hashlib
import json
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

WORKSPACE = Path(__file__).resolve().parents[2]
LEGACY = WORKSPACE / "persona_core/runtime"
SANDBOX_PARENTS = (WORKSPACE / "persona_core/operational_runtime_v1/sandboxes",
                   WORKSPACE / "persona_core/operational_build_v1/evidence",
                   WORKSPACE / "work/openai_formal_binding")
MODES = {"PRODUCT_RUNTIME", "CHARACTER_SIMULATION", "SOURCE_AUDIT"}

class StoreGuard(ValueError):
    pass

def ensure(condition: bool, reason: str) -> None:
    if not condition:
        raise StoreGuard(reason)

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def safe_root(root: Path | str) -> Path:
    path = Path(root).resolve()
    ensure(any(path.is_relative_to(p.resolve()) and path != p.resolve() for p in SANDBOX_PARENTS), "Only isolated candidate/evidence roots allowed")
    ensure(not path.is_relative_to(LEGACY.resolve()), "Production runtime is read-only")
    return path

def create_sandbox(destination: Path | str) -> Path:
    """Host-only clone; does not call or reinstall Genesis."""
    root = safe_root(destination)
    root.mkdir(parents=True, exist_ok=False)
    source = LEGACY / "genesis/GENESIS_SNAPSHOT_R035.json"
    before = file_sha(source)
    shutil.copytree(LEGACY, root / "legacy_runtime", ignore=shutil.ignore_patterns("__pycache__"))
    ensure(file_sha(root / "legacy_runtime/genesis/GENESIS_SNAPSHOT_R035.json") == before, "Genesis clone mismatch")
    marker = {"sandbox": True, "created_at_utc": utc_now(), "source_genesis_sha256": before,
              "source_runtime": "persona_core/runtime", "genesis_reinstalled": False,
              "test_history_is_production": False, "schema": "transcript-45-1"}
    with (root / "SANDBOX.json").open("x", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(marker, ensure_ascii=False, indent=2) + "\n")
    return root

@dataclass(frozen=True)
class SessionHandle:
    session_id: str
    principal_id: str
    entity_id: str
    mode: str
    _seal: object = field(repr=False, compare=False)

class TranscriptStore:
    def __init__(self, root: Path | str):
        self.root = safe_root(root)
        self.marker = json.loads((self.root / "SANDBOX.json").read_text(encoding="utf-8"))
        ensure(self.marker["sandbox"] is True, "Not an approved sandbox")
        genesis = self.root / "legacy_runtime/genesis/GENESIS_SNAPSHOT_R035.json"
        ensure(file_sha(genesis) == self.marker["source_genesis_sha256"], "Genesis changed")
        self._seal = object()
        database = self.root / "runtime.sqlite3"
        if database.exists():
            # Reject unsupported/corrupt layouts BEFORE changing journal mode or
            # running CREATE IF NOT EXISTS. Missing state is not auto-repaired.
            probe = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                version = probe.execute("PRAGMA user_version").fetchone()[0]
                tables = {r[0] for r in probe.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
                ensure(version in (0, 45, 46), "Unsupported transcript schema; migrate explicitly")
                ensure((version == 0 and not tables) or (version != 0 and {"metadata", "entities", "sessions", "turns"}.issubset(tables)),
                       "Incomplete or unversioned transcript database; explicit recovery required")
                if version:
                    identity = probe.execute("SELECT value FROM metadata WHERE key='genesis_sha256'").fetchone()
                    ensure(identity is not None and identity[0] == self.marker["source_genesis_sha256"], "Database/Genesis identity mismatch")
            finally:
                probe.close()
        self.db = sqlite3.connect(self.root / "runtime.sqlite3", timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        ensure(version in (0, 45, 46), "Unsupported transcript schema; migrate explicitly")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS entities(
          entity_id TEXT PRIMARY KEY, principal_id TEXT NOT NULL, label TEXT NOT NULL,
          created_at_utc TEXT NOT NULL, UNIQUE(principal_id,label));
        CREATE TABLE IF NOT EXISTS sessions(
          session_id TEXT PRIMARY KEY, principal_id TEXT NOT NULL,
          entity_id TEXT NOT NULL REFERENCES entities(entity_id), mode TEXT NOT NULL,
          created_at_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS turns(
          seq INTEGER PRIMARY KEY AUTOINCREMENT, turn_id TEXT UNIQUE NOT NULL,
          session_id TEXT NOT NULL REFERENCES sessions(session_id), idempotency_key TEXT NOT NULL,
          user_text TEXT NOT NULL, assistant_text TEXT, created_at_utc TEXT NOT NULL,
          response_at_utc TEXT, display_at_utc TEXT, status TEXT NOT NULL,
          input_provenance TEXT NOT NULL, response_provenance TEXT,
          request_id TEXT, UNIQUE(session_id,idempotency_key));
        CREATE INDEX IF NOT EXISTS turns_by_session ON turns(session_id,seq);
        """)
        with self.transaction():
            if version == 0:
                self.db.execute("PRAGMA user_version=45")
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES(?,?)", ("genesis_sha256", self.marker["source_genesis_sha256"]))
            ensure(self.db.execute("SELECT value FROM metadata WHERE key='genesis_sha256'").fetchone()[0] == self.marker["source_genesis_sha256"], "Database/Genesis identity mismatch")

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def close(self) -> None:
        self.db.close()

    def _authenticate(self, handle: SessionHandle) -> sqlite3.Row:
        ensure(type(handle) is SessionHandle and handle._seal is self._seal, "Host-issued session handle required")
        row = self.db.execute("SELECT s.* FROM sessions s JOIN entities e ON s.entity_id=e.entity_id WHERE s.session_id=? AND s.principal_id=? AND e.principal_id=?",
                              (handle.session_id, handle.principal_id, handle.principal_id)).fetchone()
        ensure(row is not None and row["entity_id"] == handle.entity_id and row["mode"] == handle.mode, "Session identity mismatch")
        return row

    def open_session(self, principal_id: str, label: str, mode: str = "PRODUCT_RUNTIME") -> SessionHandle:
        """Host configuration API; principal is not extracted from conversation."""
        ensure(isinstance(principal_id, str) and 0 < len(principal_id) <= 160, "Invalid principal")
        ensure(isinstance(label, str) and 0 < len(label) <= 160 and mode in MODES, "Invalid label/mode")
        with self.transaction():
            entity = self.db.execute("SELECT entity_id FROM entities WHERE principal_id=? AND label=?", (principal_id, label)).fetchone()
            eid = entity[0] if entity else "entity_" + uuid.uuid4().hex
            if not entity:
                self.db.execute("INSERT INTO entities VALUES(?,?,?,?)", (eid, principal_id, label, utc_now()))
            sid = "session_" + uuid.uuid4().hex
            self.db.execute("INSERT INTO sessions VALUES(?,?,?,?,?)", (sid, principal_id, eid, mode, utc_now()))
        return SessionHandle(sid, principal_id, eid, mode, self._seal)

    def resume(self, principal_id: str, session_id: str) -> SessionHandle:
        row = self.db.execute("SELECT * FROM sessions WHERE session_id=? AND principal_id=?", (session_id, principal_id)).fetchone()
        ensure(row is not None, "Session unavailable for this host principal")
        handle = SessionHandle(row["session_id"], row["principal_id"], row["entity_id"], row["mode"], self._seal)
        self._authenticate(handle)
        return handle

    def list_sessions(self, principal_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute("SELECT s.session_id,s.entity_id,s.mode,s.created_at_utc,e.label FROM sessions s JOIN entities e USING(entity_id) WHERE s.principal_id=? AND e.principal_id=? ORDER BY s.created_at_utc", (principal_id, principal_id))]

    def begin_turn(self, handle: SessionHandle, text: str, idempotency_key: str) -> dict[str, Any]:
        self._authenticate(handle)
        ensure(isinstance(text, str) and text.strip() and len(text) <= 12000, "Input must be nonempty text within 12000 characters")
        ensure(isinstance(idempotency_key, str) and 0 < len(idempotency_key) <= 200, "Stable input idempotency key required")
        with self.transaction():
            row = self.db.execute("SELECT * FROM turns WHERE session_id=? AND idempotency_key=?", (handle.session_id, idempotency_key)).fetchone()
            if row:
                ensure(row["user_text"] == text, "Idempotency key reused for different input")
                return dict(row)
            tid = "turn_" + uuid.uuid4().hex
            self.db.execute("INSERT INTO turns(turn_id,session_id,idempotency_key,user_text,created_at_utc,status,input_provenance) VALUES(?,?,?,?,?,?,?)",
                            (tid, handle.session_id, idempotency_key, text, utc_now(), "RECEIVED", "RAW_USER_UTTERANCE_NOT_EVENT_PROOF"))
        return self.get_turn(handle, tid)

    def get_turn(self, handle: SessionHandle, turn_id: str) -> dict[str, Any]:
        self._authenticate(handle)
        row = self.db.execute("SELECT * FROM turns WHERE turn_id=? AND session_id=?", (turn_id, handle.session_id)).fetchone()
        ensure(row is not None, "Turn unavailable for this session")
        return dict(row)

    def capture_reply(self, handle: SessionHandle, turn_id: str, text: str, request_id: str,
                      origin: str = "AUTHORED_TEST_STUB") -> dict[str, Any]:
        """Trusted host observation of output, never proof of its described events."""
        ensure(origin in {"AUTHORED_TEST_STUB", "TARGET_PROVIDER_CAPTURE"}, "Unknown capture origin")
        ensure(isinstance(text, str) and text.strip() and len(text) <= 100000, "Invalid raw reply")
        with self.transaction():
            row = self.get_turn(handle, turn_id)
            if row["assistant_text"] is not None:
                ensure(row["assistant_text"] == text and row["request_id"] == request_id and row["response_provenance"] == origin, "Raw response is immutable")
                return row
            ensure(row["status"] in {"RECEIVED", "SUBMITTED_STATUS_UNKNOWN"}, "Turn cannot accept a response")
            self.db.execute("UPDATE turns SET assistant_text=?,request_id=?,response_provenance=?,response_at_utc=?,status='RESPONSE_CAPTURED' WHERE turn_id=?",
                            (text, request_id, origin, utc_now(), turn_id))
        return self.get_turn(handle, turn_id)

    def mark_displayed(self, handle: SessionHandle, turn_id: str) -> dict[str, Any]:
        with self.transaction():
            row = self.get_turn(handle, turn_id)
            from accepted_output import project_turn
            project_turn(self.db, row, 'display')
            ensure(row["status"] in {"RESPONSE_CAPTURED", "DISPLAYED"}, "No displayable captured response")
            if row["status"] != "DISPLAYED":
                self.db.execute("UPDATE turns SET status='DISPLAYED',display_at_utc=? WHERE turn_id=?", (utc_now(), turn_id))
        return self.get_turn(handle, turn_id)

    def recent(self, handle: SessionHandle, limit: int = 8) -> list[dict[str, Any]]:
        self._authenticate(handle)
        ensure(type(limit) is int and 1 <= limit <= 100, "Invalid recent-window limit")
        rows = self.db.execute("SELECT * FROM turns WHERE session_id=? ORDER BY seq DESC LIMIT ?", (handle.session_id, limit)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def conversation_turn(self, handle: SessionHandle, turn_id: str, *, purpose: str) -> dict[str, Any]:
        from accepted_output import project_turn
        return project_turn(self.db, self.get_turn(handle, turn_id), purpose)

    def conversation_recent(self, handle: SessionHandle, limit: int = 8, *, purpose: str) -> list[dict[str, Any]]:
        from accepted_output import project_turn
        return [project_turn(self.db, r, purpose) for r in self.recent(handle, limit)]
