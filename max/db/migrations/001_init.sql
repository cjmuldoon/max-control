-- 001_init.sql — CONTROL database schema
-- "Would you believe... a perfectly normalized database?"

CREATE TABLE projects (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    slug            TEXT NOT NULL UNIQUE,
    path            TEXT NOT NULL,
    location_type   TEXT NOT NULL DEFAULT 'local',
    github_url      TEXT,
    notion_page_id  TEXT,
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'inactive',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE project_environments (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    connection_type TEXT,
    host            TEXT,
    port            INTEGER,
    credentials_ref TEXT,
    is_default      INTEGER NOT NULL DEFAULT 0,
    config_json     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE agents (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    session_id      TEXT,
    pid             INTEGER,
    status          TEXT NOT NULL DEFAULT 'stopped',
    run_location    TEXT NOT NULL DEFAULT 'local',
    model           TEXT DEFAULT 'sonnet',
    permission_mode TEXT DEFAULT 'plan',
    system_prompt   TEXT,
    started_at      TEXT,
    stopped_at      TEXT,
    last_heartbeat  TEXT,
    error_message   TEXT
);

CREATE TABLE agent_logs (
    id              TEXT PRIMARY KEY,
    agent_id        TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    level           TEXT NOT NULL DEFAULT 'info',
    message         TEXT NOT NULL,
    source          TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE tasks (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT,
    type            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    priority        INTEGER DEFAULT 0,
    source          TEXT,
    proposal        TEXT,
    user_notes      TEXT,
    resolution      TEXT,
    assigned_agent  TEXT REFERENCES agents(id),
    external_ref    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE schedules (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    cron_expression TEXT NOT NULL,
    task_type       TEXT NOT NULL,
    config_json     TEXT,
    enabled         INTEGER NOT NULL DEFAULT 1,
    last_run_at     TEXT,
    next_run_at     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE bot_configs (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL,
    token           TEXT NOT NULL,
    channel_id      TEXT,
    enabled         INTEGER NOT NULL DEFAULT 0,
    webhook_url     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE message_queue (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL,
    direction       TEXT NOT NULL,
    sender          TEXT,
    content         TEXT NOT NULL,
    metadata_json   TEXT,
    status          TEXT NOT NULL DEFAULT 'queued',
    queued_at       TEXT NOT NULL DEFAULT (datetime('now')),
    delivered_at    TEXT
);

CREATE TABLE vps_config (
    id              TEXT PRIMARY KEY,
    host            TEXT NOT NULL,
    port            INTEGER DEFAULT 22,
    user            TEXT NOT NULL,
    key_path        TEXT,
    postgres_dsn    TEXT,
    sync_enabled    INTEGER NOT NULL DEFAULT 0,
    last_sync_at    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE sync_log (
    id              TEXT PRIMARY KEY,
    direction       TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    status          TEXT NOT NULL,
    synced_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes — CONTROL needs fast lookups
CREATE INDEX idx_agents_project ON agents(project_id);
CREATE INDEX idx_agent_logs_agent ON agent_logs(agent_id);
CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_schedules_project ON schedules(project_id);
CREATE INDEX idx_message_queue_status ON message_queue(status);
CREATE INDEX idx_message_queue_project ON message_queue(project_id);
