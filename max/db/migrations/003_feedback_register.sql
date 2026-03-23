-- 003_feedback_register.sql — Consolidated feedback register
-- "99 has all the intelligence in one place, Chief."

CREATE TABLE feedback_register (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    remote_id       INTEGER,          -- ID in the project's feedback_posts table
    title           TEXT NOT NULL,
    description     TEXT,
    category        TEXT DEFAULT 'feature_request',
    status          TEXT DEFAULT 'open',
    priority        TEXT DEFAULT 'medium',
    vote_count      INTEGER DEFAULT 0,
    comment_count   INTEGER DEFAULT 0,
    admin_response  TEXT,
    author_name     TEXT,
    source          TEXT DEFAULT 'sync',  -- 'sync' | 'manual' | 'agent'
    synced_at       TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_feedback_project ON feedback_register(project_id);
CREATE INDEX idx_feedback_status ON feedback_register(status);
CREATE INDEX idx_feedback_category ON feedback_register(category);
