-- 002_undercover.sql — Hidden targets
-- "Some agents prefer to stay in the shadows."

CREATE TABLE undercover_paths (
    id          TEXT PRIMARY KEY,
    path        TEXT NOT NULL UNIQUE,
    hidden_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
