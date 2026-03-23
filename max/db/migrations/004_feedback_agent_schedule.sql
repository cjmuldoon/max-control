-- 004_feedback_agent_schedule.sql — Agent assignment and scheduling for feedback items
-- "86, you have a new assignment. Report at 0600."

ALTER TABLE feedback_register ADD COLUMN assigned_to TEXT DEFAULT '';
ALTER TABLE feedback_register ADD COLUMN scheduled_at TEXT DEFAULT '';
