"""Analytics — CONTROL Intelligence Metrics.

"Would you believe... actionable intelligence with charts?"

Tracks agent usage, task completion rates, model usage, and trends.
"""
import uuid
import json
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict


class AnalyticsService:
    def __init__(self):
        self._app = None

    def init_app(self, app):
        self._app = app

    def track(self, event_type, project_id=None, agent_id=None, model=None,
              tokens_in=0, tokens_out=0, duration_ms=0, metadata=None):
        """Track an analytics event."""
        if not self._app:
            return
        try:
            db_path = self._app.config['DB_PATH']
            conn = sqlite3.connect(db_path)
            conn.execute(
                '''INSERT INTO analytics_events
                   (id, timestamp, event_type, project_id, agent_id, model, tokens_in, tokens_out, duration_ms, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (str(uuid.uuid4()), datetime.now().isoformat(), event_type,
                 project_id, agent_id, model, tokens_in, tokens_out, duration_ms,
                 json.dumps(metadata) if metadata else None),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_dashboard_data(self):
        """Get all data needed for the analytics dashboard."""
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        data = {}

        # Overall stats
        data['total_events'] = conn.execute('SELECT COUNT(*) FROM analytics_events').fetchone()[0]
        data['total_tasks'] = conn.execute('SELECT COUNT(*) FROM feedback_register').fetchone()[0]
        data['completed_tasks'] = conn.execute("SELECT COUNT(*) FROM feedback_register WHERE status = 'completed'").fetchone()[0]
        data['open_tasks'] = conn.execute("SELECT COUNT(*) FROM feedback_register WHERE status IN ('open', 'planned')").fetchone()[0]
        data['total_projects'] = conn.execute('SELECT COUNT(*) FROM projects').fetchone()[0]
        data['total_comments'] = conn.execute('SELECT COUNT(*) FROM feedback_comments').fetchone()[0]

        # Tasks by status
        rows = conn.execute('SELECT status, COUNT(*) as cnt FROM feedback_register GROUP BY status').fetchall()
        data['tasks_by_status'] = {r['status']: r['cnt'] for r in rows}

        # Tasks by project
        rows = conn.execute(
            '''SELECT COALESCE(p.name, 'General') as name, COUNT(*) as cnt
               FROM feedback_register fr LEFT JOIN projects p ON fr.project_id = p.id
               GROUP BY name ORDER BY cnt DESC'''
        ).fetchall()
        data['tasks_by_project'] = {r['name']: r['cnt'] for r in rows}

        # Tasks by category
        rows = conn.execute('SELECT category, COUNT(*) as cnt FROM feedback_register GROUP BY category ORDER BY cnt DESC').fetchall()
        data['tasks_by_category'] = {r['category']: r['cnt'] for r in rows}

        # Events by type
        rows = conn.execute('SELECT event_type, COUNT(*) as cnt FROM analytics_events GROUP BY event_type ORDER BY cnt DESC').fetchall()
        data['events_by_type'] = {r['event_type']: r['cnt'] for r in rows}

        # Model usage
        rows = conn.execute('SELECT model, COUNT(*) as cnt FROM analytics_events WHERE model IS NOT NULL GROUP BY model ORDER BY cnt DESC').fetchall()
        data['model_usage'] = {r['model']: r['cnt'] for r in rows}

        # Activity over last 7 days
        data['daily_activity'] = []
        for i in range(6, -1, -1):
            day = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            count = conn.execute(
                "SELECT COUNT(*) FROM analytics_events WHERE timestamp LIKE ?", (f'{day}%',)
            ).fetchone()[0]
            tasks = conn.execute(
                "SELECT COUNT(*) FROM feedback_register WHERE updated_at LIKE ? AND status = 'completed'", (f'{day}%',)
            ).fetchone()[0]
            comments = conn.execute(
                "SELECT COUNT(*) FROM feedback_comments WHERE created_at LIKE ?", (f'{day}%',)
            ).fetchone()[0]
            data['daily_activity'].append({
                'date': day,
                'label': (datetime.now() - timedelta(days=i)).strftime('%a'),
                'events': count,
                'tasks_completed': tasks,
                'comments': comments,
            })

        # Recent audit entries
        rows = conn.execute('SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 20').fetchall()
        data['recent_audit'] = [dict(r) for r in rows]

        # Agent activity
        rows = conn.execute(
            '''SELECT COALESCE(p.name, 'General') as project, a.model, a.status, a.state,
                      a.total_tasks, a.session_id
               FROM agents a LEFT JOIN projects p ON a.project_id = p.id
               ORDER BY a.started_at DESC'''
        ).fetchall()
        data['agents'] = [dict(r) for r in rows]

        conn.close()
        return data


analytics_service = AnalyticsService()
