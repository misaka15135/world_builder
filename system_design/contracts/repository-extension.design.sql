-- World Builder repository design illustration, 2026-11-12.
-- Self-contained EMPTY-DATABASE model; NOT a migration for the existing store.
-- Run only in :memory: or a disposable design database. Never apply to wir.sqlite3.
-- SQL syntax floor: SQLite >= 3.37 (STRICT tables); deployment baseline >= 3.45.
-- Application enforces semantic state transitions,
-- DAG/requirement coverage, geometry, source locks, CAS and cancellation ordering.
PRAGMA foreign_keys = ON;

-- Control-plane probes do not create a World or Revision and have their own budget.
CREATE TABLE connection_probes (
    probe_id TEXT PRIMARY KEY,
    connection_id TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    protocol TEXT NOT NULL CHECK (protocol IN ('native_tools','action_json')),
    state TEXT NOT NULL CHECK (state IN ('queued','running','succeeded','failed','cancelled')),
    max_model_calls INTEGER NOT NULL CHECK (max_model_calls > 0),
    model_calls_used INTEGER NOT NULL DEFAULT 0 CHECK (model_calls_used >= 0 AND model_calls_used <= max_model_calls),
    max_total_tokens INTEGER NOT NULL CHECK (max_total_tokens > 0),
    observed_tokens INTEGER CHECK (observed_tokens >= 0),
    usage_state TEXT NOT NULL CHECK (usage_state IN ('exact','estimated','unknown')),
    result_ref TEXT,
    created_at TEXT NOT NULL,
    CHECK (state <> 'succeeded' OR result_ref IS NOT NULL)
) STRICT;
CREATE INDEX probes_by_connection ON connection_probes(connection_id, created_at);

CREATE TABLE worlds (
    world_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    head_revision_id TEXT,
    head_generation INTEGER NOT NULL DEFAULT 0 CHECK (head_generation >= 0),
    lock_generation INTEGER NOT NULL DEFAULT 0 CHECK (lock_generation >= 0),
    created_at TEXT NOT NULL,
    FOREIGN KEY (world_id, head_revision_id)
        REFERENCES revisions (world_id, revision_id) DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE revisions (
    revision_id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds (world_id),
    parent_revision_id TEXT,
    restored_from TEXT,
    snapshot_hash TEXT NOT NULL,
    operation_id TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (world_id, revision_id),
    FOREIGN KEY (world_id, parent_revision_id) REFERENCES revisions (world_id, revision_id),
    FOREIGN KEY (world_id, restored_from) REFERENCES revisions (world_id, revision_id),
    FOREIGN KEY (world_id, operation_id) REFERENCES operations (world_id, operation_id)
        DEFERRABLE INITIALLY DEFERRED,
    CHECK (parent_revision_id IS NULL OR parent_revision_id <> revision_id)
) STRICT;
CREATE INDEX revisions_history ON revisions (world_id, created_at, revision_id);
CREATE TRIGGER revisions_no_update BEFORE UPDATE ON revisions
BEGIN SELECT RAISE(ABORT, 'immutable_revision'); END;
CREATE TRIGGER worlds_head_generation BEFORE UPDATE OF head_revision_id, head_generation ON worlds
WHEN NEW.head_revision_id IS NOT OLD.head_revision_id OR NEW.head_generation <> OLD.head_generation
BEGIN
    SELECT CASE WHEN NEW.head_revision_id IS NULL OR NEW.head_generation <> OLD.head_generation + 1
        THEN RAISE(ABORT, 'invalid_head_generation') END;
END;

CREATE TABLE operations (
    operation_id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds (world_id),
    base_revision_id TEXT NOT NULL,
    expected_head_generation INTEGER NOT NULL CHECK (expected_head_generation >= 0),
    actor_id TEXT NOT NULL,
    command_kind TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN
        ('queued','running','waiting_user','validating','succeeded','failed','cancelled')),
    state_version INTEGER NOT NULL DEFAULT 0 CHECK (state_version >= 0),
    cancel_epoch INTEGER NOT NULL DEFAULT 0 CHECK (cancel_epoch >= 0),
    deadline_at TEXT NOT NULL,
    result_revision_id TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (world_id, operation_id),
    UNIQUE (world_id, actor_id, command_kind, idempotency_key),
    FOREIGN KEY (world_id, base_revision_id) REFERENCES revisions (world_id, revision_id),
    FOREIGN KEY (world_id, result_revision_id) REFERENCES revisions (world_id, revision_id),
    CHECK (state <> 'succeeded' OR result_revision_id IS NOT NULL)
) STRICT;
CREATE INDEX operations_recovery ON operations (state, deadline_at);

CREATE TABLE task_versions (
    task_id TEXT NOT NULL,
    task_version INTEGER NOT NULL CHECK (task_version >= 1),
    operation_id TEXT NOT NULL REFERENCES operations (operation_id),
    graph_version INTEGER NOT NULL CHECK (graph_version >= 1),
    capability TEXT NOT NULL,
    definition_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('waiting_dependencies','ready','running',
        'waiting_tool','waiting_user','validating','accepted','failed','cancelled','invalidated')),
    state_version INTEGER NOT NULL DEFAULT 0 CHECK (state_version >= 0),
    lease_token INTEGER NOT NULL DEFAULT 0 CHECK (lease_token >= 0),
    lease_until TEXT,
    output_ref TEXT,
    PRIMARY KEY (task_id, task_version),
    UNIQUE (operation_id, task_id, task_version)
) STRICT;
CREATE INDEX tasks_ready ON task_versions (operation_id, state, task_id, task_version);
CREATE TRIGGER task_definition_immutable BEFORE UPDATE OF
    operation_id, graph_version, capability, definition_hash, definition_json, scope_json ON task_versions
BEGIN SELECT RAISE(ABORT, 'immutable_task_definition'); END;
CREATE TABLE task_dependencies (
    operation_id TEXT NOT NULL,
    consumer_id TEXT NOT NULL,
    consumer_version INTEGER NOT NULL,
    producer_id TEXT NOT NULL,
    producer_version INTEGER NOT NULL,
    output_contract TEXT NOT NULL,
    PRIMARY KEY (consumer_id, consumer_version, producer_id, producer_version),
    FOREIGN KEY (operation_id, consumer_id, consumer_version)
        REFERENCES task_versions (operation_id, task_id, task_version),
    FOREIGN KEY (operation_id, producer_id, producer_version)
        REFERENCES task_versions (operation_id, task_id, task_version),
    CHECK (consumer_id <> producer_id OR consumer_version <> producer_version)
) STRICT;
CREATE INDEX dependencies_reverse ON task_dependencies (producer_id, producer_version);

CREATE TABLE candidates (
    candidate_id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL,
    world_id TEXT NOT NULL,
    base_revision_id TEXT NOT NULL,
    expected_head_generation INTEGER NOT NULL CHECK (expected_head_generation >= 0),
    cancel_epoch INTEGER NOT NULL CHECK (cancel_epoch >= 0),
    lock_generation INTEGER NOT NULL CHECK (lock_generation >= 0),
    patch_hash TEXT NOT NULL,
    validation_hash TEXT,
    state TEXT NOT NULL CHECK (state IN ('draft','validated','accepted','rejected','stale','abandoned')),
    state_version INTEGER NOT NULL DEFAULT 0 CHECK (state_version >= 0),
    accepted_revision_id TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (operation_id, candidate_id),
    FOREIGN KEY (world_id, operation_id) REFERENCES operations (world_id, operation_id),
    FOREIGN KEY (world_id, base_revision_id) REFERENCES revisions (world_id, revision_id),
    FOREIGN KEY (world_id, accepted_revision_id) REFERENCES revisions (world_id, revision_id),
    CHECK (state NOT IN ('validated','accepted') OR validation_hash IS NOT NULL),
    CHECK (state <> 'accepted' OR accepted_revision_id IS NOT NULL)
) STRICT;
CREATE INDEX candidates_by_operation ON candidates (operation_id, state);
CREATE TABLE candidate_tasks (
    operation_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    task_version INTEGER NOT NULL,
    artifact_ref TEXT NOT NULL,
    PRIMARY KEY (candidate_id, task_id, task_version),
    FOREIGN KEY (operation_id, candidate_id) REFERENCES candidates (operation_id, candidate_id),
    FOREIGN KEY (operation_id, task_id, task_version)
        REFERENCES task_versions (operation_id, task_id, task_version)
) STRICT;

CREATE TABLE tool_calls (
    call_id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    task_version INTEGER NOT NULL,
    idempotency_key TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    tool_version TEXT NOT NULL,
    arguments_hash TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('queued','running','succeeded','failed','unknown','cancelled')),
    attempt INTEGER NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    lease_token INTEGER NOT NULL CHECK (lease_token >= 0),
    cancel_epoch INTEGER NOT NULL CHECK (cancel_epoch >= 0),
    receipt_ref TEXT,
    result_ref TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE (operation_id, idempotency_key),
    FOREIGN KEY (operation_id, task_id, task_version)
        REFERENCES task_versions (operation_id, task_id, task_version),
    CHECK (state <> 'succeeded' OR (receipt_ref IS NOT NULL AND result_ref IS NOT NULL))
) STRICT;
CREATE INDEX calls_recovery ON tool_calls (state, updated_at);
CREATE TRIGGER tool_identity_immutable BEFORE UPDATE OF operation_id, task_id, task_version,
    idempotency_key, tool_name, tool_version, arguments_hash ON tool_calls
BEGIN SELECT RAISE(ABORT, 'immutable_tool_identity'); END;

-- Units are dimension-specific integers: calls, tokens, bytes, milliseconds,
-- or currency micros. Never store money in a floating-point column.
CREATE TABLE budget_accounts (
    operation_id TEXT NOT NULL REFERENCES operations (operation_id),
    dimension TEXT NOT NULL,
    limit_units INTEGER NOT NULL CHECK (limit_units >= 0),
    reserved_units INTEGER NOT NULL DEFAULT 0 CHECK (reserved_units >= 0),
    settled_units INTEGER NOT NULL DEFAULT 0 CHECK (settled_units >= 0),
    overrun_units INTEGER NOT NULL DEFAULT 0 CHECK (overrun_units >= 0),
    PRIMARY KEY (operation_id, dimension),
    CHECK (reserved_units + settled_units <= limit_units)
) STRICT;
CREATE TABLE budget_reservations (
    reservation_id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL,
    dimension TEXT NOT NULL,
    owner_ref TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('held','unknown','settled','released')),
    granted_units INTEGER NOT NULL CHECK (granted_units >= 0),
    held_units INTEGER NOT NULL CHECK (held_units >= 0),
    settled_units INTEGER NOT NULL DEFAULT 0 CHECK (settled_units >= 0),
    observed_units INTEGER CHECK (observed_units IS NULL OR observed_units >= 0),
    overrun_units INTEGER NOT NULL DEFAULT 0 CHECK (overrun_units >= 0),
    UNIQUE (operation_id, dimension, owner_ref),
    FOREIGN KEY (operation_id, dimension) REFERENCES budget_accounts (operation_id, dimension),
    CHECK (held_units + settled_units <= granted_units),
    CHECK ((state IN ('held','unknown') AND held_units = granted_units AND settled_units = 0)
        OR (state = 'released' AND held_units = 0 AND settled_units = 0)
        OR (state = 'settled' AND held_units = 0)),
    CHECK (overrun_units = CASE WHEN observed_units IS NOT NULL AND observed_units > granted_units
        THEN observed_units - granted_units ELSE 0 END)
) STRICT;
CREATE TRIGGER budget_reserve AFTER INSERT ON budget_reservations BEGIN
    UPDATE budget_accounts SET reserved_units = reserved_units + NEW.held_units,
        settled_units = settled_units + NEW.settled_units,
        overrun_units = overrun_units + NEW.overrun_units
    WHERE operation_id = NEW.operation_id AND dimension = NEW.dimension;
END;
CREATE TRIGGER budget_identity_immutable BEFORE UPDATE OF operation_id, dimension, owner_ref,
    granted_units ON budget_reservations
BEGIN SELECT RAISE(ABORT, 'immutable_budget_identity'); END;
CREATE TRIGGER budget_settle AFTER UPDATE ON budget_reservations BEGIN
    UPDATE budget_accounts SET reserved_units = reserved_units + NEW.held_units - OLD.held_units,
        settled_units = settled_units + NEW.settled_units - OLD.settled_units,
        overrun_units = overrun_units + NEW.overrun_units - OLD.overrun_units
    WHERE operation_id = NEW.operation_id AND dimension = NEW.dimension;
END;
CREATE TRIGGER budget_preserve BEFORE DELETE ON budget_reservations
BEGIN SELECT RAISE(ABORT, 'budget_audit_required'); END;

CREATE TABLE objects (
    world_id TEXT NOT NULL REFERENCES worlds (world_id),
    object_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    PRIMARY KEY (world_id, object_id)
) STRICT;
CREATE TABLE object_versions (
    world_id TEXT NOT NULL,
    object_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    payload_ref TEXT NOT NULL,
    PRIMARY KEY (world_id, object_id, content_hash),
    FOREIGN KEY (world_id, object_id) REFERENCES objects (world_id, object_id)
) STRICT;
CREATE TRIGGER object_versions_no_update BEFORE UPDATE ON object_versions
BEGIN SELECT RAISE(ABORT, 'immutable_object_version'); END;
CREATE TABLE revision_objects (
    world_id TEXT NOT NULL,
    revision_id TEXT NOT NULL,
    object_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    PRIMARY KEY (revision_id, object_id),
    FOREIGN KEY (world_id, revision_id) REFERENCES revisions (world_id, revision_id),
    FOREIGN KEY (world_id, object_id, content_hash)
        REFERENCES object_versions (world_id, object_id, content_hash)
) STRICT;

CREATE TABLE locks (
    lock_id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds (world_id),
    owner_id TEXT NOT NULL,
    scope_kind TEXT NOT NULL CHECK (scope_kind IN ('object','field','region')),
    object_id TEXT,
    field_pointer TEXT,
    region_json TEXT,
    lock_version INTEGER NOT NULL CHECK (lock_version >= 1),
    FOREIGN KEY (world_id, object_id) REFERENCES objects (world_id, object_id),
    CHECK ((scope_kind = 'object' AND object_id IS NOT NULL AND field_pointer IS NULL AND region_json IS NULL)
        OR (scope_kind = 'field' AND object_id IS NOT NULL AND field_pointer IS NOT NULL AND region_json IS NULL)
        OR (scope_kind = 'region' AND object_id IS NULL AND field_pointer IS NULL AND region_json IS NOT NULL))
) STRICT;
CREATE INDEX locks_by_object ON locks (world_id, object_id);
CREATE TABLE spatial_reads (
    read_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES candidates (candidate_id),
    predicate_json TEXT NOT NULL,
    min_x REAL NOT NULL, max_x REAL NOT NULL,
    min_y REAL NOT NULL, max_y REAL NOT NULL,
    min_z REAL NOT NULL, max_z REAL NOT NULL,
    result_set_hash TEXT NOT NULL,
    spatial_generation INTEGER NOT NULL CHECK (spatial_generation >= 0),
    CHECK (min_x < max_x AND min_y < max_y AND min_z < max_z)
) STRICT;
CREATE INDEX spatial_reads_candidate ON spatial_reads (candidate_id);

CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL REFERENCES operations (operation_id),
    sequence INTEGER NOT NULL CHECK (sequence >= 1),
    task_id TEXT,
    task_version INTEGER,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    summary TEXT NOT NULL,
    payload_ref TEXT,
    UNIQUE (operation_id, sequence),
    FOREIGN KEY (operation_id, task_id, task_version)
        REFERENCES task_versions (operation_id, task_id, task_version),
    CHECK ((task_id IS NULL AND task_version IS NULL) OR (task_id IS NOT NULL AND task_version IS NOT NULL))
) STRICT;
CREATE TRIGGER events_no_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'immutable_event'); END;
