-- 005_inbox_comments.sql — Agent updates, comments, and inbox
-- "86 has filed his report, Chief."

CREATE TABLE feedback_comments (
    id          TEXT PRIMARY KEY,
    item_id     TEXT NOT NULL,
    author      TEXT NOT NULL DEFAULT '86',
    content     TEXT NOT NULL,
    is_agent    INTEGER NOT NULL DEFAULT 1,
    read        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_comments_item ON feedback_comments(item_id);
CREATE INDEX idx_comments_unread ON feedback_comments(read) WHERE read = 0;
