# Max — Agent Management Platform

Flask web app that orchestrates Claude Code CLI agents across multiple projects.
Named after Maxwell Smart (Agent 86) from *Get Smart*.

## Quick Start
```bash
source venv/bin/activate
python run.py  # → http://localhost:8086
```

## Tech Stack
- Flask + Flask-SocketIO (threading mode)
- SQLite (auto-migrating schema)
- Vanilla JS + CSS custom properties (3 themes)
- Claude CLI spawned via subprocess

## Project Structure
- `app.py` — Flask factory
- `config.py` — Config with project locations (via .env)
- `max/` — Package: models, services, routes, sockets, db, utils
- `static/` — CSS (themes/), JS, images
- `templates/` — Jinja2 templates with partials

## Conventions
- Maxwell Smart references in UI copy (errors, loading, success)
- Accent colour always #E8734A (Claude orange)
- Themes: dark, light, soft — toggled via `data-theme` on `<html>`
- DB migrations in `max/db/migrations/` (numbered .sql files)
- Agent processes spawned via `subprocess.Popen`
