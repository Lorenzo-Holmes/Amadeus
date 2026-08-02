CREATE TABLE IF NOT EXISTS authority_records (
    record_id TEXT PRIMARY KEY,
    record_type TEXT NOT NULL,
    schema_version TEXT NOT NULL CHECK (schema_version = '0.1'),
    identity_id TEXT NOT NULL,
    lineage_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    content_json TEXT NOT NULL CHECK (json_valid(content_json)),
    content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS command_receipts (
    actor_capability_id TEXT NOT NULL,
    idempotency_scope_hash TEXT NOT NULL CHECK (length(idempotency_scope_hash) = 64),
    idempotency_key TEXT NOT NULL,
    command_id TEXT NOT NULL,
    command_hash TEXT NOT NULL CHECK (length(command_hash) = 64),
    result_json TEXT NOT NULL CHECK (json_valid(result_json)),
    result_hash TEXT NOT NULL CHECK (length(result_hash) = 64),
    semantic_event_ids_json TEXT NOT NULL CHECK (json_valid(semantic_event_ids_json)),
    committed_at TEXT NOT NULL,
    PRIMARY KEY (
        actor_capability_id,
        idempotency_scope_hash,
        idempotency_key
    )
);

CREATE TRIGGER IF NOT EXISTS command_receipts_reject_update
BEFORE UPDATE ON command_receipts
BEGIN
    SELECT RAISE(ABORT, 'command receipt is immutable');
END;

CREATE TRIGGER IF NOT EXISTS command_receipts_reject_delete
BEFORE DELETE ON command_receipts
BEGIN
    SELECT RAISE(ABORT, 'command receipt is immutable');
END;

CREATE TABLE IF NOT EXISTS ledger_events (
    event_id TEXT PRIMARY KEY
        REFERENCES authority_records(record_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    branch_id TEXT NOT NULL
        REFERENCES branches(branch_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    ledger_seq INTEGER NOT NULL CHECK (ledger_seq >= 1),
    previous_event_hash TEXT CHECK (
        previous_event_hash IS NULL OR length(previous_event_hash) = 64
    ),
    event_hash TEXT NOT NULL CHECK (length(event_hash) = 64),
    payload_ref TEXT NOT NULL,
    payload_mode TEXT NOT NULL CHECK (payload_mode IN ('inline', 'reference')),
    payload_inline_json TEXT,
    payload_external_ref TEXT,
    payload_hash TEXT NOT NULL CHECK (length(payload_hash) = 64),
    media_type TEXT NOT NULL,
    UNIQUE (branch_id, ledger_seq),
    CHECK (
        (
            payload_mode = 'inline'
            AND payload_ref = 'inline:' || payload_hash
            AND payload_inline_json IS NOT NULL
            AND json_valid(payload_inline_json)
            AND payload_external_ref IS NULL
        )
        OR
        (
            payload_mode = 'reference'
            AND payload_ref = 'reference:' || payload_external_ref
            AND payload_inline_json IS NULL
            AND payload_external_ref IS NOT NULL
            AND instr(payload_external_ref, ':') > 1
        )
    )
);

CREATE INDEX IF NOT EXISTS ledger_events_inline_session
ON ledger_events (json_extract(payload_inline_json, '$.session_id'))
WHERE payload_mode = 'inline';

CREATE INDEX IF NOT EXISTS authority_records_ledger_session_correlation
ON authority_records (json_extract(content_json, '$.correlation_id'))
WHERE json_extract(content_json, '$.record_header.record_type') = 'LedgerEvent'
  AND json_extract(content_json, '$.event_type') IN (
      'session_started',
      'conversation_message_recorded',
      'session_ended'
  );

CREATE UNIQUE INDEX IF NOT EXISTS authority_records_session_started_correlation
ON authority_records (json_extract(content_json, '$.correlation_id'))
WHERE json_extract(content_json, '$.record_header.record_type') = 'LedgerEvent'
  AND json_extract(content_json, '$.event_type') = 'session_started';

CREATE TABLE IF NOT EXISTS branches (
    branch_id TEXT PRIMARY KEY
        REFERENCES authority_records(record_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    identity_id TEXT NOT NULL
        REFERENCES identities(identity_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    lineage_id TEXT NOT NULL
        REFERENCES lineages(lineage_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    status TEXT NOT NULL CHECK (
        status IN ('active', 'candidate', 'inactive', 'quarantined', 'terminated')
    ),
    version INTEGER NOT NULL CHECK (version >= 1)
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_branch_per_identity
ON branches (identity_id)
WHERE status = 'active';

CREATE TABLE IF NOT EXISTS identities (
    identity_id TEXT PRIMARY KEY
        REFERENCES authority_records(record_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    lifecycle_state TEXT NOT NULL CHECK (
        lifecycle_state IN (
            'active',
            'maintenance_paused',
            'termination_pending',
            'emergency_unresponsive',
            'terminated'
        )
    ),
    active_branch_id TEXT NOT NULL
        REFERENCES branches(branch_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    version INTEGER NOT NULL CHECK (version >= 1)
);

CREATE TABLE IF NOT EXISTS lineages (
    lineage_id TEXT PRIMARY KEY
        REFERENCES authority_records(record_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    root_identity_id TEXT NOT NULL
        REFERENCES identities(identity_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    root_branch_id TEXT NOT NULL
        REFERENCES branches(branch_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    root_snapshot_id TEXT
        REFERENCES authority_records(record_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    version INTEGER NOT NULL CHECK (version >= 1)
);

CREATE TABLE IF NOT EXISTS relationship_vaults (
    vault_id TEXT PRIMARY KEY
        REFERENCES authority_records(record_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    identity_id TEXT NOT NULL
        REFERENCES identities(identity_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    branch_id TEXT NOT NULL
        REFERENCES branches(branch_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    status TEXT NOT NULL CHECK (status IN ('active', 'contact_paused', 'sealed')),
    version INTEGER NOT NULL CHECK (version >= 1)
);

CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY
        REFERENCES authority_records(record_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    identity_id TEXT NOT NULL
        REFERENCES identities(identity_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    branch_id TEXT NOT NULL
        REFERENCES branches(branch_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'committed', 'rejected', 'deferred', 'expired')
    ),
    expires_at TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1)
);

CREATE TABLE IF NOT EXISTS governor_decisions (
    decision_id TEXT PRIMARY KEY
        REFERENCES authority_records(record_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    proposal_id TEXT NOT NULL
        REFERENCES proposals(proposal_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    result TEXT NOT NULL CHECK (result IN ('commit', 'reject', 'defer')),
    version INTEGER NOT NULL CHECK (version >= 1)
);

CREATE TABLE IF NOT EXISTS capabilities (
    capability_id TEXT PRIMARY KEY
        REFERENCES authority_records(record_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    capability_type TEXT NOT NULL CHECK (
        capability_type IN (
            'vault_read',
            'maintenance',
            'termination_execution',
            'break_glass'
        )
    ),
    identity_id TEXT NOT NULL
        REFERENCES identities(identity_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    branch_id TEXT NOT NULL
        REFERENCES branches(branch_id)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED,
    status TEXT NOT NULL,
    expires_at TEXT,
    remaining_uses INTEGER CHECK (remaining_uses IS NULL OR remaining_uses >= 0),
    version INTEGER NOT NULL CHECK (version >= 1)
);

CREATE TRIGGER IF NOT EXISTS ledger_events_reject_update
BEFORE UPDATE ON ledger_events
BEGIN
    SELECT RAISE(ABORT, 'ledger is append-only');
END;

CREATE TRIGGER IF NOT EXISTS ledger_events_reject_delete
BEFORE DELETE ON ledger_events
BEGIN
    SELECT RAISE(ABORT, 'ledger is append-only');
END;

CREATE TRIGGER IF NOT EXISTS authority_ledger_reject_update
BEFORE UPDATE ON authority_records
WHEN OLD.record_type = 'LedgerEvent' OR NEW.record_type = 'LedgerEvent'
BEGIN
    SELECT RAISE(ABORT, 'ledger is append-only');
END;

CREATE TRIGGER IF NOT EXISTS authority_ledger_reject_delete
BEFORE DELETE ON authority_records
WHEN OLD.record_type = 'LedgerEvent'
BEGIN
    SELECT RAISE(ABORT, 'ledger is append-only');
END;
