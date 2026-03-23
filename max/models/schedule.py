import uuid
from dataclasses import dataclass
from datetime import datetime
from max.db.connection import get_db


@dataclass
class Schedule:
    id: str = ''
    project_id: str = ''
    name: str = ''
    cron_expression: str = ''
    task_type: str = ''
    config_json: str = ''
    enabled: int = 1
    last_run_at: str = ''
    next_run_at: str = ''
    created_at: str = ''

    @staticmethod
    def create(project_id, name, cron_expression, task_type, config_json=''):
        db = get_db()
        sched_id = str(uuid.uuid4())
        db.execute(
            '''INSERT INTO schedules (id, project_id, name, cron_expression, task_type, config_json)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (sched_id, project_id, name, cron_expression, task_type, config_json),
        )
        db.commit()
        return Schedule.get_by_id(sched_id)

    @staticmethod
    def get_by_id(sched_id):
        db = get_db()
        row = db.execute('SELECT * FROM schedules WHERE id = ?', (sched_id,)).fetchone()
        if row is None:
            return None
        return Schedule(**dict(row))

    @staticmethod
    def get_by_project(project_id):
        db = get_db()
        rows = db.execute('SELECT * FROM schedules WHERE project_id = ? ORDER BY name', (project_id,)).fetchall()
        return [Schedule(**dict(row)) for row in rows]

    @staticmethod
    def get_all():
        db = get_db()
        rows = db.execute('SELECT * FROM schedules ORDER BY name').fetchall()
        return [Schedule(**dict(row)) for row in rows]

    def toggle(self):
        db = get_db()
        new_val = 0 if self.enabled else 1
        db.execute('UPDATE schedules SET enabled = ? WHERE id = ?', (new_val, self.id))
        db.commit()
        self.enabled = new_val

    def delete(self):
        db = get_db()
        db.execute('DELETE FROM schedules WHERE id = ?', (self.id,))
        db.commit()

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__}
