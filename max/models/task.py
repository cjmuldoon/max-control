import uuid
from dataclasses import dataclass
from datetime import datetime
from max.db.connection import get_db


@dataclass
class Task:
    id: str = ''
    project_id: str = ''
    title: str = ''
    description: str = ''
    type: str = ''
    status: str = 'pending'
    priority: int = 0
    source: str = ''
    proposal: str = ''
    user_notes: str = ''
    resolution: str = ''
    assigned_agent: str = ''
    external_ref: str = ''
    created_at: str = ''
    updated_at: str = ''

    @staticmethod
    def create(project_id, title, type='feature', description='', source='manual', priority=0):
        db = get_db()
        task_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        db.execute(
            '''INSERT INTO tasks (id, project_id, title, description, type, status, source, priority, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)''',
            (task_id, project_id, title, description, type, source, priority, now, now),
        )
        db.commit()
        return Task.get_by_id(task_id)

    @staticmethod
    def get_by_id(task_id):
        db = get_db()
        row = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if row is None:
            return None
        return Task(**dict(row))

    @staticmethod
    def get_by_project(project_id, status=None):
        db = get_db()
        if status:
            rows = db.execute(
                'SELECT * FROM tasks WHERE project_id = ? AND status = ? ORDER BY priority DESC, created_at DESC',
                (project_id, status),
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT * FROM tasks WHERE project_id = ? ORDER BY priority DESC, created_at DESC',
                (project_id,),
            ).fetchall()
        return [Task(**dict(row)) for row in rows]

    @staticmethod
    def get_all(status=None, type_filter=None, limit=100):
        db = get_db()
        query = 'SELECT * FROM tasks WHERE 1=1'
        params = []
        if status:
            query += ' AND status = ?'
            params.append(status)
        if type_filter:
            query += ' AND type = ?'
            params.append(type_filter)
        query += ' ORDER BY priority DESC, created_at DESC LIMIT ?'
        params.append(limit)
        rows = db.execute(query, params).fetchall()
        return [Task(**dict(row)) for row in rows]

    @staticmethod
    def get_pending_count():
        db = get_db()
        return db.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('pending', 'proposed')").fetchone()[0]

    @staticmethod
    def get_stats():
        """Get task statistics for analytics."""
        db = get_db()
        stats = {}
        for status in ('pending', 'proposed', 'approved', 'rejected', 'completed', 'in_progress'):
            count = db.execute('SELECT COUNT(*) FROM tasks WHERE status = ?', (status,)).fetchone()[0]
            stats[status] = count
        stats['total'] = sum(stats.values())

        # By type
        type_stats = {}
        rows = db.execute('SELECT type, COUNT(*) as cnt FROM tasks GROUP BY type').fetchall()
        for row in rows:
            type_stats[row['type']] = row['cnt']
        stats['by_type'] = type_stats

        # By project
        project_stats = {}
        rows = db.execute(
            '''SELECT p.name, COUNT(t.id) as cnt
               FROM tasks t JOIN projects p ON t.project_id = p.id
               GROUP BY p.name ORDER BY cnt DESC'''
        ).fetchall()
        for row in rows:
            project_stats[row['name']] = row['cnt']
        stats['by_project'] = project_stats

        return stats

    def approve(self, notes=''):
        db = get_db()
        now = datetime.utcnow().isoformat()
        db.execute(
            "UPDATE tasks SET status = 'approved', user_notes = ?, updated_at = ? WHERE id = ?",
            (notes, now, self.id),
        )
        db.commit()
        self.status = 'approved'
        self.user_notes = notes

    def reject(self, notes=''):
        db = get_db()
        now = datetime.utcnow().isoformat()
        db.execute(
            "UPDATE tasks SET status = 'rejected', user_notes = ?, updated_at = ? WHERE id = ?",
            (notes, now, self.id),
        )
        db.commit()
        self.status = 'rejected'

    def complete(self, resolution=''):
        db = get_db()
        now = datetime.utcnow().isoformat()
        db.execute(
            "UPDATE tasks SET status = 'completed', resolution = ?, updated_at = ? WHERE id = ?",
            (resolution, now, self.id),
        )
        db.commit()
        self.status = 'completed'

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__}
