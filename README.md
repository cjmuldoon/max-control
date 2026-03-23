# Max — Agent Management Platform

### *"Would you believe... a fully autonomous multi-agent orchestration platform?"*

<p align="center">
  <img src="static/img/maxwell-smart.svg" width="80" alt="Agent 86">
  <img src="static/img/agent99.svg" width="80" alt="Agent 99">
</p>

**Max** (named after Maxwell Smart, Agent 86) is a self-hosted agent management platform that orchestrates [Claude Code](https://claude.ai/claude-code) CLI agents across multiple projects. Built with Flask, it provides a web-based mission control centre for deploying, monitoring, and coordinating AI agents.

> *"Sorry about that, Chief."* — Max, after every minor setback

---

## ✨ Features

### 🕵️ CONTROL Headquarters
- **Operations Centre** — Dashboard showing all registered projects with status, health, and quick actions
- **Persistent Multi-Terminal Hub** — Multiple xterm.js terminals with tab and mini-panel management. Sessions survive page navigation. Pop-out windows. Fullscreen mode.
- **Agent 99** — Persistent Claude CLI assistant accessible from every page (Cmd+9). She knows all your projects, can schedule tasks, run health checks, and create new projects from natural language.

### 📋 Mission Dossier
- **Consolidated task register** across all projects — bugs, features, improvements, tasks
- **Syncs with production** — pulls from your apps' feedback APIs, pushes status updates back
- **Agent assignment** — assign tasks to 86 (Sonnet/Opus) or 99
- **Scheduling** — set date/time for agent work, friendly cron builder with presets
- **Multi-select bulk actions** — run, deploy, or run & deploy selected items
- **Quality gates** — review states, rejection loops with feedback

### 🚀 Agent Deployment & Execution
- **Sequential task execution** per project — no conflicts, no timeouts
- **Git workflow** — agents commit to `agent/<task>` branches, push for review
- **Diff viewer** — color-coded code review in the browser
- **Deploy approval** — review diff, approve, merge to main with one click
- **Progressive updates** — agents report progress every 2 minutes
- **Auto-handoff** — if a task times out inline, it spawns a background worker

### 📞 Shoe Phone Network (Discord & Telegram)
- **One bot, multiple channels** — each project gets a Discord channel
- **Agent 99's Direct Line** — dedicated channel for 99
- **Project agents respond in character** — Max talks like Maxwell Smart
- **File attachments** — send screenshots and files via Discord
- **Background task handoff** — complex requests auto-delegate to background workers
- **Results delivered** back to the channel when complete
- **Allowlist** — only authorised users can talk to the bots

### 📬 Inbox
- **Central notification hub** — all agent updates, task completions, questions
- **Reply inline** — responses go to the ticket thread
- **Deploy approval from inbox** — review diffs and approve without leaving
- **Discord push** — agent updates post to project channels automatically
- **macOS notifications** — native alerts for agent activity

### 🌍 Satellite Office (VPS)
- **Remote agent deployment** — SSH into VPS, spawn research agents
- **Remote terminal** — execute commands on VPS from the browser
- **PostgreSQL sync** — bidirectional sync between local SQLite and VPS Postgres
- **Agent coordination** — remote researches, local executes

### 📊 Intelligence Division
- **Analytics dashboard** — 7-day activity trends, task distribution, model usage, project breakdown
- **Audit trail** — every agent action logged with timestamp, actor, detail
- **Health checks** — git status, dependencies, common issues, project size
- **Vulnerability scanning** — npm audit, pip-audit integration
- **Log analysis** — error pattern detection in project logs

### 🏋️ Training Ground (Regression)
- **Regression branches** — isolated git branches for testing changes
- **Promote to production** — merge to main with one click
- **Test runner** — auto-detect and run pytest, npm test, unittest

### 💾 Emergency Protocols
- **Backup & restore** — snapshot the database, restore with safety backup
- **CLAUDE.md management** — edit project briefs, generate CLAUDE.md, intelligent merge

### 🎨 Themes
Three themes with Claude orange (`#E8734A`) as the accent:
- 🌙 **Dark** — Night Operations
- ☀️ **Light** — Daylight Operations
- 🌊 **Soft** — CONTROL Headquarters (light blues & greys)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- [Claude Code CLI](https://claude.ai/claude-code) installed and authenticated
- Git

### Install

```bash
git clone https://github.com/yourusername/max.git
cd max
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your settings
python run.py
```

Open `http://localhost:8086` — CONTROL headquarters is operational.

### Docker

```bash
cp .env.example .env
# Edit .env
docker-compose up -d
```

### macOS Auto-Start

```bash
python setup_startup.py        # Install launchd agent
python setup_startup.py uninstall  # Remove it
```

---

## 📱 Discord Setup

1. Create a bot at [discord.com/developers](https://discord.com/developers/applications)
2. Enable **Message Content Intent** under Bot → Privileged Gateway Intents
3. Invite the bot to your server
4. Configure in Max: **Shoe Phone** page → enter token + channel IDs
5. Or let 99 create channels: she can do it programmatically

---

## 🏗️ Architecture

```
Max (Flask + SocketIO)
├── Routes (Blueprints) ← HTTP → Browser UI
├── SocketIO Events ← WebSocket → Real-time updates
├── Services
│   ├── AgentRunner → spawns claude CLI processes
│   ├── Agent99 → persistent Claude assistant
│   ├── TaskExecutor → sequential task queue per project
│   ├── BotManager → Discord/Telegram lifecycle
│   ├── TerminalManager → persistent PTY sessions
│   ├── HealthChecker → project health analysis
│   ├── FeedbackRegister → consolidated task management
│   ├── InboxService → agent notifications
│   ├── AuditService → activity logging
│   └── AnalyticsService → usage tracking
├── DB (SQLite)
└── Discord Worker (subprocess)
```

---

## ⚙️ Configuration

All configuration via `.env` or environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_SECRET_KEY` | `agent-86-would-you-believe` | Flask session secret |
| `MAX_PORT` | `8086` | Server port (Agent 86's number) |
| `CLAUDE_CLI_PATH` | `~/.local/bin/claude` | Path to Claude CLI |
| `MAX_PROJECT_LOCATIONS` | `local:~/Projects` | Project directories (name:path pairs) |
| `DISCORD_BOT_TOKEN` | — | Discord bot token |
| `VPS_HOST` | — | VPS IP for remote operations |

---

## 🕵️ Maxwell Smart References

Max is packed with Get Smart references:

- **Agent 86 (Max)** — your project agents, confident and occasionally bumbling
- **Agent 99** — the competent persistent assistant who always calls you "Chief"
- **The Chief** — that's you
- **CONTROL** — the good guys (your infrastructure)
- **KAOS** — the bad guys (production errors, vulnerabilities)
- **The Shoe Phone** — Discord/Telegram bot connectivity
- **The Cone of Silence** — secure operations (token entry, credentials)
- **KAOS Mode** — `--dangerously-skip-permissions` (☠️ button)
- **Training Ground** — regression environments
- **Emergency Protocols** — backup & restore
- **Mission Dossier** — consolidated task register
- **Satellite Office** — VPS remote operations
- **"Would you believe..."** — loading messages
- **"Sorry about that, Chief"** — error messages
- **"And loving it!"** — success messages
- **"Missed it by that much!"** — timeouts and near-misses

---

## 📁 Project Structure

```
max/
├── app.py                  # Flask factory
├── config.py               # Configuration
├── run.py                  # Entry point + Discord worker
├── max/
│   ├── models/             # Data models (Project, Agent, Task, etc.)
│   ├── services/           # Business logic (agent runner, bots, health, etc.)
│   ├── routes/             # Flask blueprints
│   ├── sockets/            # SocketIO event handlers
│   ├── db/migrations/      # SQL migrations
│   └── utils/              # Smart quotes, helpers
├── static/                 # CSS themes, JS, images
├── templates/              # Jinja2 templates
├── menubar/                # macOS menu bar app (rumps)
└── scripts/                # Setup scripts, launchd plists
```

---

## 🤝 Contributing

1. Fork the repo
2. Create a branch (`git checkout -b feature/shoe-phone-upgrade`)
3. Make your changes
4. Submit a PR

*"Would you believe... we accept pull requests?"*

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <em>"Would you believe... the world's smartest agent manager?"</em><br>
  <strong>Built with Claude Code. And loving it.</strong>
</p>
