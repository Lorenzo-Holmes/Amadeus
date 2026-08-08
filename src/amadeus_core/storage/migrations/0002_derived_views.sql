CREATE TABLE derived_view_scopes (
    identity_id TEXT NOT NULL,
    lineage_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    generation INTEGER NOT NULL CHECK (generation >= 1),
    semantic_state_hash TEXT NOT NULL CHECK (
        length(semantic_state_hash) = 64
        AND semantic_state_hash NOT GLOB '*[^0-9a-f]*'
    ),
    PRIMARY KEY (identity_id, lineage_id, branch_id, vault_id)
);

CREATE TABLE derived_view_manifests (
    identity_id TEXT NOT NULL,
    lineage_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    view_type TEXT NOT NULL CHECK (
        view_type IN ('summary', 'timeline', 'vector', 'fulltext', 'cue')
    ),
    view_id TEXT NOT NULL UNIQUE,
    manifest_json TEXT NOT NULL CHECK (json_valid(manifest_json)),
    manifest_hash TEXT NOT NULL CHECK (
        length(manifest_hash) = 64
        AND manifest_hash NOT GLOB '*[^0-9a-f]*'
    ),
    content_hash TEXT NOT NULL CHECK (
        length(content_hash) = 64
        AND content_hash NOT GLOB '*[^0-9a-f]*'
    ),
    PRIMARY KEY (
        identity_id,
        lineage_id,
        branch_id,
        vault_id,
        view_type
    ),
    FOREIGN KEY (
        identity_id,
        lineage_id,
        branch_id,
        vault_id
    ) REFERENCES derived_view_scopes (
        identity_id,
        lineage_id,
        branch_id,
        vault_id
    ) ON DELETE CASCADE
);

CREATE TABLE derived_view_contents (
    view_id TEXT PRIMARY KEY,
    content_json TEXT NOT NULL CHECK (json_valid(content_json)),
    content_hash TEXT NOT NULL CHECK (
        length(content_hash) = 64
        AND content_hash NOT GLOB '*[^0-9a-f]*'
    ),
    FOREIGN KEY (view_id)
        REFERENCES derived_view_manifests (view_id)
        ON DELETE CASCADE
);
