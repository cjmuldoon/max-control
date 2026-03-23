-- 006_deploy_approval.sql — Deploy approval tracking
-- "Ready for your review, Chief."

ALTER TABLE feedback_register ADD COLUMN deploy_status TEXT DEFAULT '';
ALTER TABLE feedback_register ADD COLUMN deploy_branch TEXT DEFAULT '';
ALTER TABLE feedback_register ADD COLUMN deploy_commit TEXT DEFAULT '';

ALTER TABLE feedback_comments ADD COLUMN deploy_action TEXT DEFAULT '';
