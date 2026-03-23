"""Agent Runner — spawns and manages Claude CLI processes.

"Would you believe... the world's most sophisticated agent deployment system?"
"""
import os
import json
import signal
import subprocess
import threading
import uuid
from datetime import datetime
from flask import current_app
from max.extensions import socketio
from max.db.connection import get_db


class AgentRunner:
    """Manages Claude CLI agent processes across all projects."""

    def __init__(self):
        # agent_id -> process info
        self._processes = {}
        self._lock = threading.Lock()

    def start_agent(self, project, model='sonnet', permission_mode='plan', resume_session_id=None):
        """Start a Claude agent for a project.

        Spawns `claude --print --output-format stream-json` as a subprocess
        and streams output to SocketIO.
        """
        from max.models.agent import Agent

        # Check if agent already running for this project
        existing = Agent.get_by_project(project.id)
        if existing and existing.status == 'running' and existing.is_process_alive():
            raise RuntimeError(f'Agent already running for {project.name}')

        # Create or reuse agent record
        agent = Agent.create(
            project_id=project.id,
            model=model,
            permission_mode=permission_mode,
            session_id=resume_session_id,
        )

        cli_path = current_app.config['CLAUDE_CLI_PATH']
        if not os.path.exists(cli_path):
            agent.set_error(f'Claude CLI not found at {cli_path}')
            raise FileNotFoundError(f'Claude CLI not found at {cli_path}')

        # Build command — launch from project directory so Claude picks up
        # .claude/ memory, CLAUDE.md, and project-specific settings.
        # Just like opening a terminal in the project folder and typing `claude`.
        cmd = [
            cli_path,
            '--print',
            '--output-format', 'stream-json',
            '--model', model,
            '--permission-mode', permission_mode,
            '--name', f'Max-{project.slug}',
        ]
        if resume_session_id:
            cmd.extend(['--resume', resume_session_id])
        else:
            cmd.extend(['--session-id', agent.session_id])

        # System prompt with project context (supplements CLAUDE.md, doesn't replace it)
        system_prompt = self._build_system_prompt(project)
        if system_prompt:
            cmd.extend(['--system-prompt', system_prompt])

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=project.path if os.path.isdir(project.path) else None,
                text=True,
                bufsize=1,
            )

            agent.set_running(proc.pid)

            # Update project status
            db = get_db()
            db.execute("UPDATE projects SET status = 'active' WHERE id = ?", (project.id,))
            db.commit()

            # Store process reference
            with self._lock:
                self._processes[agent.id] = {
                    'process': proc,
                    'project_id': project.id,
                    'agent_id': agent.id,
                }

            # Start output reader thread
            reader = threading.Thread(
                target=self._read_output,
                args=(agent.id, proc),
                daemon=True,
            )
            reader.start()

            return agent

        except Exception as e:
            agent.set_error(str(e))
            raise

    def stop_agent(self, agent_id):
        """Stop a running agent. The old 'graceful shutdown' trick."""
        from max.models.agent import Agent

        with self._lock:
            proc_info = self._processes.get(agent_id)

        if proc_info:
            proc = proc_info['process']
            try:
                # Try graceful shutdown first
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
            except Exception:
                pass

            with self._lock:
                self._processes.pop(agent_id, None)

        # Update DB
        agent = Agent.get_by_id(agent_id)
        if agent:
            agent.set_stopped()
            db = get_db()
            db.execute("UPDATE projects SET status = 'inactive' WHERE id = ?", (agent.project_id,))
            db.commit()

        socketio.emit('agent_stopped', {'agent_id': agent_id})

    def send_to_agent(self, agent_id, message):
        """Send a message to a running agent's stdin."""
        with self._lock:
            proc_info = self._processes.get(agent_id)

        if not proc_info:
            raise RuntimeError('Agent not running')

        proc = proc_info['process']
        if proc.stdin and not proc.stdin.closed:
            try:
                proc.stdin.write(message + '\n')
                proc.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                raise RuntimeError(f'Failed to send: {e}')
        else:
            raise RuntimeError('Agent stdin not available')

    def get_running_count(self):
        with self._lock:
            return len(self._processes)

    def cleanup_orphans(self):
        """Clean up any orphaned agent records on startup."""
        from max.models.agent import Agent
        running_agents = Agent.get_all_running()
        for agent in running_agents:
            if not agent.is_process_alive():
                agent.set_stopped()

    def _read_output(self, agent_id, proc):
        """Read agent output in a background thread and emit via SocketIO."""
        try:
            for line in iter(proc.stdout.readline, ''):
                line = line.strip()
                if not line:
                    continue

                # Try to parse as JSON (stream-json format)
                try:
                    data = json.loads(line)
                    msg_type = data.get('type', 'unknown')
                    content = ''

                    if msg_type == 'assistant' and 'message' in data:
                        # Extract text content from assistant messages
                        message = data['message']
                        if 'content' in message:
                            for block in message['content']:
                                if block.get('type') == 'text':
                                    content = block.get('text', '')
                    elif msg_type == 'result':
                        content = data.get('result', '')
                    else:
                        content = line

                    socketio.emit('agent_output', {
                        'agent_id': agent_id,
                        'type': msg_type,
                        'content': content,
                        'raw': line,
                        'timestamp': datetime.utcnow().isoformat(),
                    })

                except json.JSONDecodeError:
                    # Plain text output
                    socketio.emit('agent_output', {
                        'agent_id': agent_id,
                        'type': 'text',
                        'content': line,
                        'timestamp': datetime.utcnow().isoformat(),
                    })

                # Also log to DB via a separate emit (handled by socket event)
                self._log_output(agent_id, line)

        except Exception as e:
            socketio.emit('agent_error', {
                'agent_id': agent_id,
                'error': str(e),
            })
        finally:
            # Process ended
            proc.wait()
            exit_code = proc.returncode

            with self._lock:
                self._processes.pop(agent_id, None)

            socketio.emit('agent_stopped', {
                'agent_id': agent_id,
                'exit_code': exit_code,
            })

    def _log_output(self, agent_id, message):
        """Store agent output in the log table."""
        # This runs in a background thread, so we need a fresh connection
        try:
            from flask import current_app
            import sqlite3
            db_path = current_app.config['DB_PATH']
            conn = sqlite3.connect(db_path)
            conn.execute(
                'INSERT INTO agent_logs (id, agent_id, level, message, source) VALUES (?, ?, ?, ?, ?)',
                (str(uuid.uuid4()), agent_id, 'info', message[:2000], 'stdout'),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # Don't crash the reader thread over logging failures

    def _build_system_prompt(self, project):
        """Build a system prompt with project context."""
        parts = [
            f'You are Agent 86, managing the "{project.name}" project.',
            f'Project path: {project.path}',
        ]
        if project.description:
            parts.append(f'Description: {project.description}')
        if project.github_url:
            parts.append(f'GitHub: {project.github_url}')

        return ' '.join(parts)


# Singleton instance
agent_runner = AgentRunner()
