import uuid
import os
import signal
from dataclasses import dataclass
from datetime import datetime
from max.db.connection import get_db


@dataclass
class Agent:
    id: str = ''
    project_id: str = ''
    session_id: str = ''
    pid: int = None
    status: str = 'stopped'
    run_location: str = 'local'
    model: str = 'sonnet'
    permission_mode: str = 'plan'
    system_prompt: str = ''
    started_at: str = ''
    stopped_at: str = ''
    last_heartbeat: str = ''
    error_message: str = ''

    @staticmethod
    def create(project_id, model='sonnet', permission_mode='plan', session_id=None):
        db = get_db()
        agent_id = str(uuid.uuid4())
        session_id = session_id or str(uuid.uuid4())

        db.execute(
            '''INSERT INTO agents (id, project_id, session_id, status, model, permission_mode)
               VALUES (?, ?, ?, 'stopped', ?, ?)''',
            (agent_id, project_id, session_id, model, permission_mode),
        )
        db.commit()
        return Agent.get_by_id(agent_id)

    @staticmethod
    def get_by_id(agent_id):
        db = get_db()
        row = db.execute('SELECT * FROM agents WHERE id = ?', (agent_id,)).fetchone()
        if row is None:
            return None
        return Agent(**dict(row))

    @staticmethod
    def get_by_project(project_id):
        db = get_db()
        row = db.execute(
            'SELECT * FROM agents WHERE project_id = ? ORDER BY started_at DESC LIMIT 1',
            (project_id,),
        ).fetchone()
        if row is None:
            return None
        return Agent(**dict(row))

    @staticmethod
    def get_all_running():
        db = get_db()
        rows = db.execute("SELECT * FROM agents WHERE status = 'running'").fetchall()
        return [Agent(**dict(row)) for row in rows]

    def set_running(self, pid):
        db = get_db()
        now = datetime.utcnow().isoformat()
        db.execute(
            "UPDATE agents SET status = 'running', pid = ?, started_at = ?, last_heartbeat = ? WHERE id = ?",
            (pid, now, now, self.id),
        )
        db.commit()
        self.status = 'running'
        self.pid = pid
        self.started_at = now

    def set_stopped(self):
        db = get_db()
        now = datetime.utcnow().isoformat()
        db.execute(
            "UPDATE agents SET status = 'stopped', stopped_at = ?, pid = NULL WHERE id = ?",
            (now, self.id),
        )
        db.commit()
        self.status = 'stopped'
        self.stopped_at = now
        self.pid = None

    def set_error(self, message):
        db = get_db()
        db.execute(
            "UPDATE agents SET status = 'error', error_message = ? WHERE id = ?",
            (message, self.id),
        )
        db.commit()
        self.status = 'error'
        self.error_message = message

    def update_heartbeat(self):
        db = get_db()
        now = datetime.utcnow().isoformat()
        db.execute(
            'UPDATE agents SET last_heartbeat = ? WHERE id = ?',
            (now, self.id),
        )
        db.commit()
        self.last_heartbeat = now

    def is_process_alive(self):
        """Check if the agent's process is still running."""
        if self.pid is None:
            return False
        try:
            os.kill(self.pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'session_id': self.session_id,
            'pid': self.pid,
            'status': self.status,
            'run_location': self.run_location,
            'model': self.model,
            'permission_mode': self.permission_mode,
            'started_at': self.started_at,
            'stopped_at': self.stopped_at,
            'last_heartbeat': self.last_heartbeat,
            'error_message': self.error_message,
        }
