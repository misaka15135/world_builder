PRAGMA foreign_keys = ON;

CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE worlds (
    world_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    head_revision_id TEXT
);

CREATE TABLE revisions (
    revision_id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds(world_id),
    parent_revision_ids_json TEXT NOT NULL,
    author TEXT NOT NULL,
    created_at TEXT NOT NULL,
    change_set_hash TEXT NOT NULL,
    validation_summary_json TEXT NOT NULL,
    committed INTEGER NOT NULL CHECK (committed IN (0, 1))
);

CREATE TABLE records (
    world_id TEXT NOT NULL REFERENCES worlds(world_id),
    revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
    record_id TEXT NOT NULL,
    record_type TEXT NOT NULL,
    parent_id TEXT,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    PRIMARY KEY (revision_id, record_id)
);

CREATE INDEX records_by_world_type ON records(world_id, record_type);
CREATE INDEX records_by_parent ON records(revision_id, parent_id);

CREATE VIRTUAL TABLE record_bounds USING rtree(
    rowid,
    min_x, max_x,
    min_y, max_y,
    min_z, max_z
);

CREATE TABLE resource_blobs (
    sha256 TEXT PRIMARY KEY,
    byte_length INTEGER NOT NULL CHECK (byte_length >= 0),
    media_type TEXT NOT NULL,
    relative_path TEXT NOT NULL UNIQUE,
    published INTEGER NOT NULL CHECK (published IN (0, 1))
);

CREATE TABLE revision_resources (
    revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
    asset_id TEXT NOT NULL,
    sha256 TEXT NOT NULL REFERENCES resource_blobs(sha256),
    PRIMARY KEY (revision_id, asset_id)
);

CREATE TABLE branches (
    world_id TEXT NOT NULL REFERENCES worlds(world_id),
    branch_name TEXT NOT NULL,
    head_revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
    PRIMARY KEY (world_id, branch_name)
);

CREATE TABLE import_events (
    import_id TEXT PRIMARY KEY,
    package_sha256 TEXT NOT NULL,
    source_schema_version TEXT NOT NULL,
    target_schema_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('staged', 'committed', 'failed')),
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
