"""Audit Trail — CONTROL knows everything.

"Every action, every agent, every timestamp. The Chief sees all."
"""
import uuid
import json
import sqlite3
from datetime import datetime


class AuditService:
    def __init__(self):
        self._app = None

    def init_app(self, app):
        self._app = app

    def log(self, actor, action, target_type=None, target_id=None, project_id=None, detail=None, metadata=None):
        """Log an action to the audit trail."""
        if not self._app:
            return
        try:
            db_path = self._app.config['DB_PATH']
            conn = sqlite3.connect(db_path)
            conn.execute(
                '''INSERT INTO audit_log (id, timestamp, actor, action, target_type, target_id, project_id, detail, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (str(uuid.uuid4()), datetime.now().isoformat(), actor, action,
                 target_type, target_id, project_id, detail,
                 json.dumps(metadata) if metadata else None),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_log(self, actor=None, action=None, project_id=None, limit=100, offset=0):
        """Query the audit trail."""
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        query = 'SELECT * FROM audit_log WHERE 1=1'
        params = []
        if actor:
            query += ' AND actor = ?'
            params.append(actor)
        if action:
            query += ' AND action = ?'
            params.append(action)
        if project_id:
            query += ' AND project_id = ?'
            params.append(project_id)

        query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_stats(self, hours=24):
        """Get audit stats for the last N hours."""
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)

        cutoff = datetime.now().isoformat()[:10]  # Today

        stats = {}
        stats['total'] = conn.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0]
        stats['today'] = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE timestamp >= ?", (cutoff,)
        ).fetchone()[0]

        # By action type
        rows = conn.execute(
            'SELECT action, COUNT(*) as cnt FROM audit_log GROUP BY action ORDER BY cnt DESC LIMIT 10'
        ).fetchall()
        stats['by_action'] = {r[0]: r[1] for r in rows}

        # By actor
        rows = conn.execute(
            'SELECT actor, COUNT(*) as cnt FROM audit_log GROUP BY actor ORDER BY cnt DESC LIMIT 10'
        ).fetchall()
        stats['by_actor'] = {r[0]: r[1] for r in rows}

        conn.close()
        return stats


audit_service = AuditService()
