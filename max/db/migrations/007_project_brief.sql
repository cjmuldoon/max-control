-- 007_project_brief.sql — Extended project brief for CLAUDE.md generation
-- "The full dossier, Chief."

ALTER TABLE projects ADD COLUMN brief TEXT DEFAULT '';
ALTER TABLE projects ADD COLUMN tech_stack TEXT DEFAULT '';
ALTER TABLE projects ADD COLUMN environments_info TEXT DEFAULT '';
ALTER TABLE projects ADD COLUMN conventions TEXT DEFAULT '';
