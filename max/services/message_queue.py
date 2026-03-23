"""Message Queue — The Dead Drop.

"Even when Agent 86 is sleeping, CONTROL never misses a message."

SQLite-backed queue for bot messages received while agents are offline.
Messages are drained when the agent starts up.
"""
import uuid
import sqlite3
from datetime import datetime
from flask import current_app


class MessageQueueService:
    """Persistent message queue — CONTROL's dead drop system."""

    def enqueue(self, project_id, platform, sender, content, direction='inbound', metadata=None):
        """Drop a message in the dead drop."""
        db_path = current_app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        msg_id = str(uuid.uuid4())
        conn.execute(
            '''INSERT INTO message_queue (id, project_id, platform, direction, sender, content, metadata_json, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'queued')''',
            (msg_id, project_id, platform, direction, sender, content, metadata),
        )
        conn.commit()
        conn.close()
        return msg_id

    def drain(self, project_id):
        """Pick up all queued messages for a project. The dead drop is cleared."""
        db_path = current_app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            '''SELECT * FROM message_queue
               WHERE project_id = ? AND status = 'queued'
               ORDER BY queued_at ASC''',
            (project_id,),
        ).fetchall()

        if rows:
            now = datetime.utcnow().isoformat()
            conn.execute(
                '''UPDATE message_queue SET status = 'delivered', delivered_at = ?
                   WHERE project_id = ? AND status = 'queued' ''',
                (now, project_id),
            )
            conn.commit()

        conn.close()
        return [dict(row) for row in rows]

    def peek(self, project_id):
        """Look at queued messages without draining."""
        db_path = current_app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            '''SELECT * FROM message_queue
               WHERE project_id = ? AND status = 'queued'
               ORDER BY queued_at ASC''',
            (project_id,),
        ).fetchall()

        conn.close()
        return [dict(row) for row in rows]

    def get_undelivered_count(self, project_id):
        """How many messages are waiting in the dead drop?"""
        db_path = current_app.config['DB_PATH']
        conn = sqlite3.connect(db_path)

        count = conn.execute(
            "SELECT COUNT(*) FROM message_queue WHERE project_id = ? AND status = 'queued'",
            (project_id,),
        ).fetchone()[0]

        conn.close()
        return count

    def get_recent(self, project_id, limit=50):
        """Get recent messages (all statuses) for the feed."""
        db_path = current_app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            '''SELECT * FROM message_queue
               WHERE project_id = ?
               ORDER BY queued_at DESC LIMIT ?''',
            (project_id, limit),
        ).fetchall()

        conn.close()
        return [dict(row) for row in rows]


# Singleton
message_queue = MessageQueueService()
