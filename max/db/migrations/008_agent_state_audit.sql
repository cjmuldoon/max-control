-- 008_agent_state_audit.sql — Agent state machine, heartbeat, audit trail, analytics
-- "CONTROL needs to know everything, Chief."

-- Agent state machine
ALTER TABLE agents ADD COLUMN state TEXT DEFAULT 'offline';
ALTER TABLE agents ADD COLUMN last_task TEXT DEFAULT '';
ALTER TABLE agents ADD COLUMN total_tasks INTEGER DEFAULT 0;
ALTER TABLE agents ADD COLUMN total_tokens INTEGER DEFAULT 0;

-- Audit trail
CREATE TABLE audit_log (
    id          TEXT PRIMARY KEY,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    target_type TEXT,
    target_id   TEXT,
    project_id  TEXT,
    detail      TEXT,
    metadata    TEXT
);

CREATE INDEX idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX idx_audit_actor ON audit_log(actor);
CREATE INDEX idx_audit_project ON audit_log(project_id);
CREATE INDEX idx_audit_action ON audit_log(action);

-- Analytics events
CREATE TABLE analytics_events (
    id          TEXT PRIMARY KEY,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    event_type  TEXT NOT NULL,
    project_id  TEXT,
    agent_id    TEXT,
    model       TEXT,
    tokens_in   INTEGER DEFAULT 0,
    tokens_out  INTEGER DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    metadata    TEXT
);

CREATE INDEX idx_analytics_timestamp ON analytics_events(timestamp);
CREATE INDEX idx_analytics_type ON analytics_events(event_type);
CREATE INDEX idx_analytics_project ON analytics_events(project_id);

-- Task quality gates
ALTER TABLE feedback_register ADD COLUMN review_count INTEGER DEFAULT 0;
ALTER TABLE feedback_register ADD COLUMN max_retries INTEGER DEFAULT 3;
ALTER TABLE feedback_register ADD COLUMN rejection_feedback TEXT DEFAULT '';

-- Working memory (ephemeral per task)
ALTER TABLE feedback_register ADD COLUMN working_notes TEXT DEFAULT '';
