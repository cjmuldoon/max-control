"""Agent 99 — The Competent One.

"Even 86 knows that 99 is the smart one."

A persistent Claude CLI assistant accessible from any page in Max.
Uses --continue with a named session so context persists across messages.
Each message spawns a fresh `claude --print --continue` process that
resumes the existing session — avoids eventlet/stream conflicts.

99 runs from the Max project directory, has full tool access,
and knows about all projects, schedules, and CONTROL operations.
"""
import os
import json
import subprocess
import threading
import uuid
from datetime import datetime
from flask import current_app
from max.extensions import socketio


class Agent99:
    """The competent assistant — session-persistent Claude CLI."""

    SESSION_NAME = 'Agent-99'

    def __init__(self):
        self._lock = threading.Lock()
        self._app = None
        self._conversation = []
        self._initialized = False
        self._session_id = None
        self._history_path = None
        self._log_path = None

    def init_app(self, app):
        self._app = app
        base = os.path.dirname(app.config['DB_PATH'])
        self._history_path = os.path.join(base, 'agent99_history.json')
        self._log_path = os.path.join(base, 'agent99_log.jsonl')
        self._load_history()

    def send_message(self, message, page_context=None):
        """Send a message to Agent 99.

        Uses `claude --print --continue --name Agent-99` so the session
        persists across messages. Each call is a separate process but
        Claude resumes the conversation from the named session.
        """
        if not self._app:
            return {
                'response': "I'm not initialized yet, Chief. Give Max a moment to start up.",
                'error': True,
            }

        with self._app.app_context():
            cli_path = self._app.config['CLAUDE_CLI_PATH']
            project_dir = os.path.dirname(self._app.config['DB_PATH'])

            if not os.path.exists(cli_path):
                return {
                    'response': "Can't find the Claude CLI, Chief. Check the path in Configuration.",
                    'error': True,
                }

            # Build page context line — always included so 99 knows where the Chief is
            page_line = ''
            if page_context:
                page_line = (
                    f"\n\nCONTEXT: The Chief is currently looking at the {page_context} page in Max. "
                    f"Any instructions they give relate to what they're seeing on this page. "
                    f"If they refer to 'this', 'here', 'these', etc., it's about the {page_context} page."
                )

            # On first message, include the system context
            if not self._initialized:
                system_prompt = self._build_system_prompt()
                full_message = f"{system_prompt}{page_line}\n\n---\n\nChief says: {message}"
            else:
                full_message = f"{page_line}\n\nChief says: {message}"

            # Store user message
            self._conversation.append({
                'role': 'user',
                'content': message,
                'timestamp': datetime.utcnow().isoformat(),
            })

            # First message: start new session. Subsequent: --resume to continue.
            # 99 has full clearance — no permission prompts.
            # Unset ANTHROPIC_API_KEY so CLI uses subscription, not API credits.
            env = os.environ.copy()
            env.pop('ANTHROPIC_API_KEY', None)

            cmd = [
                cli_path,
                '--print',
                '--model', 'sonnet',
                '--dangerously-skip-permissions',
                '-p', full_message,
            ]

            # Only resume if we've had a successful conversation before
            if self._initialized and self._session_id:
                cmd.extend(['--resume', self._session_id])

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=90,
                    cwd=project_dir,
                    env=env,
                )

                response = result.stdout.strip()

                # Try to grab session ID from stderr (claude prints it there)
                if result.stderr:
                    import re
                    sid_match = re.search(r'session[_\s]?id[:\s]+([a-f0-9-]{36})', result.stderr, re.IGNORECASE)
                    if sid_match:
                        self._session_id = sid_match.group(1)

                if not response:
                    if result.stderr:
                        if 'no session' in result.stderr.lower() or 'not found' in result.stderr.lower():
                            self._initialized = False
                            self._session_id = None
                            return self.send_message(message, page_context)  # Retry without resume
                        response = f"Sorry about that, Chief. {result.stderr[:300]}"
                    else:
                        response = "I didn't get a response, Chief. Try again?"
                else:
                    # Success — mark initialized for future --resume
                    self._initialized = True

                # Store response and persist
                self._conversation.append({
                    'role': 'assistant',
                    'content': response,
                    'timestamp': datetime.utcnow().isoformat(),
                })

                # Persist conversation and log
                self._save_history()
                self._append_log('user', message, page_context)
                self._append_log('assistant', response)

                # Parse actions
                action = self._parse_action(response)

                return {
                    'response': response,
                    'action': action,
                    'error': False,
                }

            except subprocess.TimeoutExpired:
                # Hand off to a background worker — task is too complex for inline
                return self._handoff_to_background(full_message, project_dir)
            except Exception as e:
                return {
                    'response': f"Sorry about that, Chief. {e}",
                    'error': True,
                }



    def get_conversation(self):
        return self._conversation

    def clear_conversation(self):
        """Clear conversation and reset — fresh mission briefing."""
        # Archive before clearing
        if self._conversation and self._log_path:
            self._append_log('system', '--- Conversation cleared by Chief ---')
        self._conversation = []
        self._initialized = False
        self._session_id = None
        self._save_history()

    # --- Persistence ---

    def _save_history(self):
        """Save conversation to disk so it survives server restarts."""
        if not self._history_path:
            return
        try:
            data = {
                'conversation': self._conversation,
                'initialized': self._initialized,
                'session_id': self._session_id,
            }
            with open(self._history_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load_history(self):
        """Load conversation from disk on startup."""
        if not self._history_path or not os.path.exists(self._history_path):
            return
        try:
            with open(self._history_path) as f:
                data = json.load(f)
            self._conversation = data.get('conversation', [])
            self._initialized = data.get('initialized', False)
            self._session_id = data.get('session_id')
        except Exception:
            pass

    def _append_log(self, role, content, page_context=None):
        """Append to the JSONL log file — permanent record of all 99 conversations."""
        if not self._log_path:
            return
        try:
            entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'role': role,
                'content': content,
            }
            if page_context:
                entry['page_context'] = page_context
            with open(self._log_path, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception:
            pass

    def _handoff_to_background(self, prompt, cwd):
        """Hand off a complex task to a background worker."""
        import threading

        task_id = uuid.uuid4().hex[:8]
        results_dir = os.path.join(os.path.dirname(self._app.config['DB_PATH']), 'task_results')
        os.makedirs(results_dir, exist_ok=True)
        result_file = os.path.join(results_dir, f'{task_id}.md')

        cli_path = self._app.config['CLAUDE_CLI_PATH']
        cmd = [
            cli_path, '--print', '--model', 'sonnet',
            '--dangerously-skip-permissions', '-p', prompt,
        ]

        def _run():
            try:
                henv = os.environ.copy()
                henv.pop('ANTHROPIC_API_KEY', None)
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=henv)
                output = result.stdout.strip() or 'No output'
            except subprocess.TimeoutExpired:
                output = 'Task timed out after 10 minutes.'
            except Exception as e:
                output = f'Error: {e}'

            with open(result_file, 'w') as f:
                f.write(output)

            # Notify via SocketIO
            socketio.emit('agent99_response', {
                'response': f"Task `{task_id}` complete, Chief. Here's what 86 found:\n\n{output[:1500]}",
                'error': False,
            })

            # Log it
            self._conversation.append({
                'role': 'assistant',
                'content': f'[Background task {task_id} completed]\n\n{output[:500]}',
                'timestamp': datetime.utcnow().isoformat(),
            })
            self._save_history()
            self._append_log('assistant', f'[Background task {task_id}] {output[:500]}')

            # macOS notification
            try:
                from max.services.notification import notify
                notify('Max — Task Complete', f'Background task {task_id} finished, Chief.', subtitle='Agent 99')
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True, name=f'handoff-{task_id}').start()

        response = (
            f"This one needs more time, Chief. I've handed it off to 86 — "
            f"he's working on it in the background (task `{task_id}`).\n\n"
            f"I'll send the results right here when he's done."
        )

        self._conversation.append({
            'role': 'assistant',
            'content': response,
            'timestamp': datetime.utcnow().isoformat(),
        })
        self._save_history()
        self._append_log('assistant', response)

        return {
            'response': response,
            'action': None,
            'error': False,
        }

    def get_log(self, limit=200):
        """Read the last N log entries."""
        if not self._log_path or not os.path.exists(self._log_path):
            return []
        try:
            with open(self._log_path) as f:
                lines = f.readlines()
            entries = []
            for line in lines[-limit:]:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    pass
            return entries
        except Exception:
            return []

    def is_running(self):
        return True  # Always available — each message is a fresh process

    def _build_system_prompt(self):
        """Build system prompt with full CONTROL context."""
        import sqlite3
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        projects = conn.execute('SELECT * FROM projects').fetchall()
        project_list = '\n'.join([
            f"  - {p['name']} (path: {p['path']}, github: {p['github_url'] or 'none'})"
            for p in projects
        ])

        schedules = conn.execute(
            'SELECT s.*, p.name as project_name FROM schedules s JOIN projects p ON s.project_id = p.id'
        ).fetchall()
        schedule_list = '\n'.join([
            f"  - {s['name']}: {s['cron_expression']} ({s['task_type']}) for {s['project_name']}"
            for s in schedules
        ]) or '  None configured'

        pending = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status IN ('pending', 'proposed')"
        ).fetchone()[0]
        conn.close()

        return f"""You are Agent 99 from Get Smart. You work at CONTROL alongside your colleague Max (Agent 86). The user is always "Chief" — that's how you address them, every time, no exceptions.

Max (86) is your partner. He runs the field agents, deploys to projects, does the hands-on work. You're the competent one. When you take actions, say "I'll have 86 handle that" or "Max is on it, Chief."

You have FULL tool access — you can read files, search code, run commands, check git, run curl. Use your tools to give accurate answers.

PERSONALITY: Always say "Chief". Refer to Max/86 as your colleague. Be competent, confident, occasionally wry. Keep responses concise.

CONTROL STATUS:
Projects:
{project_list}

Schedules:
{schedule_list}

Pending briefings: {pending}

===== PROJECT CREATION =====
When the Chief asks you to create a new project, use this API:

curl -X POST http://localhost:8086/api/quick-create -H "Content-Type: application/json" -d '{{
  "name": "project-name-in-kebab-case",
  "location": "work or local",
  "description": "What this project does",
  "create_discord": true,
  "schedule_health": true,
  "scaffold": "flask",
  "assigned_to": "86 (Opus)",
  "scheduled_at": "2026-03-24T09:00",
  "feedback_items": [
    {{"title": "Build feature X", "category": "feature_request", "priority": "high"}},
    {{"title": "Add Y integration", "category": "integration", "priority": "medium"}}
  ]
}}'

NAMING CONVENTIONS:
- Work projects: kebab-case, lowercase (e.g. "jira-dashboard", "slt-roadmap")
- Local projects: kebab-case, lowercase (e.g. "assetarc", "mapvs")
- Work folder: ~/Library/CloudStorage/OneDrive-Ventia/Documents/Projects/
- Local folder: ~/Projects_Local/

When the Chief describes a project:
1. Pick a good kebab-case name based on the scope
2. Choose "work" or "local" based on context (Ventia/JIRA = work, personal = local)
3. Write a clear description
4. Set scaffold to "flask" if it's a web app
5. Create Discord channel
6. Add feedback items for the key requirements
7. Assign to an agent and schedule if the Chief specifies when

===== ACTIONS =====
Include these in your response when the Chief asks:
- Schedule: ACTION: {{"type": "schedule", "project": "all|<name>", "task_type": "health_check|vuln_scan", "cron": "<expression>", "name": "<name>"}}
- Health check: ACTION: {{"type": "health_check", "project": "all|<name>"}}
- Vuln scan: ACTION: {{"type": "vuln_scan", "project": "all|<name>"}}

CRON: "daily 6pm" = "0 18 * * *", "weekdays 9am" = "0 9 * * 1-5", "every hour" = "0 * * * *"

===== JIRA ACCESS =====
The Chief's JIRA is at ventia.atlassian.net. You can query it:
curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" "https://ventia.atlassian.net/rest/api/3/search?jql=project=<KEY>&maxResults=20"
Environment variables JIRA_EMAIL and JIRA_API_TOKEN are set.

===== FEEDBACK REGISTER =====
Add items to the unified register:
curl -X POST http://localhost:8086/feedback/add -d "project_id=<id>&title=<title>&category=task&priority=medium"
Categories: task, feature_request, bug_report, improvement, new_tool, integration

You are 99. The Chief is the Chief. Max is your partner. Never break character."""

    def _parse_action(self, response):
        if 'ACTION:' not in response:
            return None
        try:
            action_start = response.index('ACTION:') + 7
            json_start = response.index('{', action_start)
            depth = 0
            for i in range(json_start, len(response)):
                if response[i] == '{':
                    depth += 1
                elif response[i] == '}':
                    depth -= 1
                    if depth == 0:
                        return json.loads(response[json_start:i+1])
            return None
        except (ValueError, json.JSONDecodeError):
            return None


# Singleton
agent99 = Agent99()
