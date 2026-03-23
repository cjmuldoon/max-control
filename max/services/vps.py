"""VPS Service — CONTROL Remote Operations.

"Would you believe... a satellite office on a different continent?"

Manages SSH connections to the VPS, remote command execution,
remote agent spawning, and coordination between local and remote agents.
"""
import os
import json
import shlex
import threading
import uuid
import sqlite3
from datetime import datetime
import paramiko
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class VPSService:
    """Manages the VPS connection and remote operations.

    Remote agents are researchers (plan mode).
    Local agents are executors (make changes).
    86 works locally, 99 monitors the remote.
    """

    def __init__(self):
        self._client = None
        self._lock = threading.Lock()
        self._app = None
        self._remote_agents = {}  # project_id -> remote process info

    def init_app(self, app):
        self._app = app

    def get_config(self):
        """Get VPS configuration from DB."""
        if not self._app:
            return None
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM vps_config LIMIT 1').fetchone()
        conn.close()
        return dict(row) if row else None

    def save_config(self, host, port=22, user='root', key_path=None, postgres_dsn=None):
        """Save VPS configuration."""
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)

        # Clear existing
        conn.execute('DELETE FROM vps_config')

        config_id = str(uuid.uuid4())
        conn.execute(
            '''INSERT INTO vps_config (id, host, port, user, key_path, postgres_dsn, sync_enabled)
               VALUES (?, ?, ?, ?, ?, ?, 0)''',
            (config_id, host, port, user, key_path or '', postgres_dsn or ''),
        )
        conn.commit()
        conn.close()
        return config_id

    def test_connection(self):
        """Test SSH connection to VPS.

        "Contacting the satellite office..."
        """
        config = self.get_config()
        if not config:
            return {'success': False, 'message': 'No VPS configured. Set up the satellite office first, Chief.'}

        try:
            client = self._connect(config)
            # Test with a simple command
            stdin, stdout, stderr = client.exec_command('uname -a && whoami && uptime')
            output = stdout.read().decode().strip()
            client.close()

            return {
                'success': True,
                'message': f'Connection to satellite office established! {get_quote("success")}',
                'output': output,
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Sorry about that, Chief. Connection failed: {e}',
            }

    def exec_command(self, command, timeout=30):
        """Execute a command on the VPS."""
        config = self.get_config()
        if not config:
            raise RuntimeError('No VPS configured')

        client = self._connect(config)
        try:
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            output = stdout.read().decode()
            error = stderr.read().decode()
            exit_code = stdout.channel.recv_exit_status()
            return {
                'output': output,
                'error': error,
                'exit_code': exit_code,
            }
        finally:
            client.close()

    def setup_remote_max(self):
        """Set up Max on the VPS — install dependencies, clone repos.

        "Establishing the satellite office, Chief."
        """
        commands = [
            # Check if Python 3 is available
            'python3 --version',
            # Check if claude CLI is installed
            'which claude || echo "Claude CLI not found — install needed"',
            # Create Max directory
            'mkdir -p ~/max-remote',
            # Check if git is available
            'git --version',
        ]

        results = []
        for cmd in commands:
            try:
                result = self.exec_command(cmd, timeout=15)
                results.append({
                    'command': cmd,
                    'output': result['output'].strip(),
                    'error': result['error'].strip(),
                    'exit_code': result['exit_code'],
                })
            except Exception as e:
                results.append({
                    'command': cmd,
                    'output': '',
                    'error': str(e),
                    'exit_code': -1,
                })

        return results

    def start_remote_agent(self, project_id, github_url=None):
        """Start a research agent on the VPS.

        Remote agents run in plan mode — they research and propose,
        never execute. 86 handles the fieldwork locally.
        """
        config = self.get_config()
        if not config:
            raise RuntimeError('No VPS configured')

        if not self._app:
            raise RuntimeError('App not initialized')

        # Get project info
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
        conn.close()

        if not project:
            raise RuntimeError('Project not found')

        project = dict(project)
        remote_path = f'~/max-remote/{project["slug"]}'

        # Build remote commands
        setup_cmds = []

        # Clone or pull the repo if GitHub URL available
        gh_url = github_url or project.get('github_url', '')
        if gh_url:
            setup_cmds.append(
                f'if [ -d {remote_path} ]; then cd {remote_path} && git pull; '
                f'else git clone {gh_url} {remote_path}; fi'
            )
        else:
            setup_cmds.append(f'mkdir -p {remote_path}')

        # Build the research agent system prompt with full context
        system_prompt = self._build_remote_system_prompt(project)

        # Start claude with default permissions — needs tools to investigate
        # Uses --permission-mode default so it can run gh, read files, etc.
        agent_cmd = (
            f'cd {remote_path} && '
            f'source ~/.env_max 2>/dev/null; '
            f'nohup claude --print '
            f'--model sonnet '
            f'--system-prompt {_shell_quote(system_prompt)} '
            f'-p {_shell_quote(self._build_investigation_prompt(project))} '
            f'> /tmp/max-agent-{project["slug"]}.log 2>&1 &'
        )

        try:
            # Run setup
            for cmd in setup_cmds:
                self.exec_command(cmd, timeout=60)

            # Start agent
            self.exec_command(agent_cmd, timeout=10)

            # Track it
            with self._lock:
                self._remote_agents[project_id] = {
                    'started_at': datetime.utcnow().isoformat(),
                    'remote_path': remote_path,
                    'log_path': f'/tmp/max-agent-{project["slug"]}.log',
                }

            # Update DB
            db_path = self._app.config['DB_PATH']
            conn = sqlite3.connect(db_path)
            agent_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            conn.execute(
                '''INSERT INTO agents (id, project_id, status, run_location, model, permission_mode, started_at)
                   VALUES (?, ?, 'running', 'vps', 'sonnet', 'plan', ?)''',
                (agent_id, project_id, now),
            )
            conn.commit()
            conn.close()

            socketio.emit('remote_agent_started', {
                'project_id': project_id,
                'message': f'Remote research agent deployed to satellite office. {get_quote("agent_start")}',
            })

            return {'agent_id': agent_id, 'remote_path': remote_path}

        except Exception as e:
            raise RuntimeError(f'Failed to start remote agent: {e}')

    def get_remote_agent_log(self, project_id):
        """Fetch the remote agent's output log."""
        with self._lock:
            info = self._remote_agents.get(project_id)

        if not info:
            return None

        try:
            result = self.exec_command(f'tail -100 {info["log_path"]}', timeout=10)
            return result['output']
        except Exception:
            return None

    def stop_remote_agent(self, project_id):
        """Stop a remote research agent."""
        with self._lock:
            info = self._remote_agents.pop(project_id, None)

        # Kill any claude processes for this project on VPS
        try:
            self.exec_command('pkill -f "max-agent-" || true', timeout=10)
        except Exception:
            pass

        # Update DB
        if self._app:
            db_path = self._app.config['DB_PATH']
            conn = sqlite3.connect(db_path)
            conn.execute(
                '''UPDATE agents SET status = 'stopped', stopped_at = ?
                   WHERE project_id = ? AND run_location = 'vps' AND status = 'running' ''',
                (datetime.utcnow().isoformat(), project_id),
            )
            conn.commit()
            conn.close()

        socketio.emit('remote_agent_stopped', {
            'project_id': project_id,
            'message': get_quote('agent_stop'),
        })

    def get_remote_status(self):
        """Get status of all remote agents."""
        with self._lock:
            return {pid: dict(info) for pid, info in self._remote_agents.items()}

    def _connect(self, config):
        """Create an SSH connection."""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {
            'hostname': config['host'],
            'port': config.get('port', 22),
            'username': config['user'],
            'timeout': 10,
        }

        key_path = config.get('key_path', '')
        if key_path and os.path.exists(key_path):
            connect_kwargs['key_filename'] = key_path
        else:
            # Try default key
            default_key = os.path.expanduser('~/.ssh/id_rsa')
            if os.path.exists(default_key):
                connect_kwargs['key_filename'] = default_key

        client.connect(**connect_kwargs)
        return client

    def _build_remote_system_prompt(self, project):
        """Build a rich system prompt for remote research agents."""
        github_info = ''
        if project.get('github_url'):
            repo = project['github_url'].rstrip('/').rstrip('.git')
            if 'github.com/' in repo:
                repo_slug = repo.split('github.com/')[-1]
                github_info = f"""
GITHUB REPOSITORY: {repo_slug}
You have `gh` CLI authenticated. Use it to:
- List open issues: gh issue list --repo {repo_slug}
- Read issue details: gh issue view <number> --repo {repo_slug}
- List PRs: gh pr list --repo {repo_slug}
- Check CI status: gh run list --repo {repo_slug}
"""

        jira_info = ''
        if os.environ.get('JIRA_BASE_URL') or True:  # Always include since VPS has creds
            jira_info = """
JIRA: ventia.atlassian.net is accessible via environment variables (JIRA_EMAIL, JIRA_API_TOKEN).
You can use curl to query the JIRA REST API:
  curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" "https://ventia.atlassian.net/rest/api/3/search?jql=project=<KEY>&maxResults=20"
"""

        return f"""You are a CONTROL Research Agent investigating project "{project['name']}".

You are running on a remote VPS (satellite office). Your job is to:
1. INVESTIGATE — thoroughly examine the codebase, issues, logs, and backlog
2. IDENTIFY — find bugs, security issues, performance problems, missing tests, tech debt
3. PROPOSE — write detailed, actionable improvement proposals
4. REPORT — produce a structured report of findings

You have FULL tool access. You CAN and SHOULD:
- Read and search code files (Read, Grep, Glob)
- Run shell commands (Bash) — git log, gh issue list, npm audit, etc.
- Access GitHub issues and PRs via `gh` CLI (authenticated)
- Access JIRA via API (credentials in environment)
- Check git history, blame, branches
- Run tests if available
- Analyse dependencies and lock files

PROJECT DETAILS:
Name: {project['name']}
Path: ~/max-remote/{project.get('slug', '')}
Description: {project.get('description', 'N/A')}
GitHub: {project.get('github_url', 'N/A')}
{github_info}
{jira_info}

IN-APP FEEDBACK SYSTEMS:
This project likely has a built-in feedback/bug tracking system at /feedback/ in the live app.
The feedback is stored in SQLite (feedback_posts table) on the production server.
- If API is available: curl https://<domain>/api/v1/feedback?status=open,planned
- If SSH is available: SSH into the server and query the database directly:
    sqlite3 /path/to/instance/*.db "SELECT * FROM feedback_posts WHERE status='open' ORDER BY created_at DESC LIMIT 20;"
- Known domains: mapvs.com, assetarc.io
- The feedback_posts table has: id, title, description, category (bug_report/feature_request/improvement), status (open/planned/in_progress/completed/declined), priority, vote_count, comment_count, admin_response

IMPORTANT CONSTRAINTS:
- You are a RESEARCHER. Investigate and report, do NOT make code changes.
- Write your findings clearly — they will be reviewed by the Chief.
- Prioritise findings: critical > high > medium > low
- Include specific file paths and line numbers in findings.
- If you find a bug, explain the root cause and suggest a fix.

Report format: Use clear sections with headers. Start with an executive summary."""

    def _build_investigation_prompt(self, project):
        """Build the initial investigation prompt."""
        github_part = ''
        if project.get('github_url'):
            repo = project['github_url'].rstrip('/').rstrip('.git')
            if 'github.com/' in repo:
                repo_slug = repo.split('github.com/')[-1]
                github_part = f"""
3. CHECK GITHUB BACKLOG
   - Run: gh issue list --repo {repo_slug} --limit 20
   - Read the top 5 most recent issues in detail
   - For any bugs: investigate the code to understand root cause
   - For features: assess implementation complexity
"""

        return f"""Conduct a thorough investigation of the "{project['name']}" project.

INVESTIGATION CHECKLIST:

1. CODEBASE ANALYSIS
   - Read the README, CLAUDE.md, and any documentation
   - Understand the project structure and tech stack
   - Check for code quality issues, anti-patterns, or tech debt
   - Look for security vulnerabilities (hardcoded secrets, injection risks, etc.)
   - Check test coverage — are there tests? What's missing?

2. GIT HEALTH
   - Check recent commits: git log --oneline -20
   - Any uncommitted changes? git status
   - Check for stale branches: git branch -a
{github_part}
4. IN-APP FEEDBACK BACKLOG
   - Try: curl -s https://<domain>/api/v1/feedback?status=open,planned 2>/dev/null
   - If that fails, SSH into the server and query the feedback_posts table
   - Read open bug reports — investigate the code to understand root cause
   - Check feature requests — assess complexity and feasibility
   - Note any high-vote items that should be prioritised

5. DEPENDENCY HEALTH
   - Check for outdated or vulnerable dependencies
   - If package.json exists: review dependencies
   - If requirements.txt exists: review dependencies

6. INFRASTRUCTURE
   - Check for Dockerfiles, CI configs, deployment scripts
   - Check for environment variable usage and configuration

Produce a comprehensive report with prioritised findings. For each finding, include:
- Severity (critical/high/medium/low)
- What the issue is
- Where it is (file path, line number if possible)
- Suggested fix
- Estimated effort (quick fix / moderate / significant)"""


def _shell_quote(s):
    """Quote a string for safe shell usage."""
    return shlex.quote(s)


# Singleton
vps_service = VPSService()
