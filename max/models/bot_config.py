import uuid
from dataclasses import dataclass
from max.db.connection import get_db


@dataclass
class BotConfig:
    id: str = ''
    project_id: str = ''
    platform: str = ''
    token: str = ''
    channel_id: str = ''
    enabled: int = 0
    webhook_url: str = ''
    created_at: str = ''

    @staticmethod
    def create(project_id, platform, token, channel_id=''):
        db = get_db()
        config_id = str(uuid.uuid4())
        db.execute(
            '''INSERT INTO bot_configs (id, project_id, platform, token, channel_id)
               VALUES (?, ?, ?, ?, ?)''',
            (config_id, project_id, platform, token, channel_id),
        )
        db.commit()
        return BotConfig.get_by_id(config_id)

    @staticmethod
    def get_by_id(config_id):
        db = get_db()
        row = db.execute('SELECT * FROM bot_configs WHERE id = ?', (config_id,)).fetchone()
        if row is None:
            return None
        return BotConfig(**dict(row))

    @staticmethod
    def get_by_project(project_id):
        db = get_db()
        rows = db.execute('SELECT * FROM bot_configs WHERE project_id = ?', (project_id,)).fetchall()
        return [BotConfig(**dict(row)) for row in rows]

    @staticmethod
    def get_by_project_platform(project_id, platform):
        db = get_db()
        row = db.execute(
            'SELECT * FROM bot_configs WHERE project_id = ? AND platform = ?',
            (project_id, platform),
        ).fetchone()
        if row is None:
            return None
        return BotConfig(**dict(row))

    def update(self, **kwargs):
        db = get_db()
        allowed = {'token', 'channel_id', 'webhook_url'}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ', '.join(f'{k} = ?' for k in updates)
        values = list(updates.values()) + [self.id]
        db.execute(f'UPDATE bot_configs SET {set_clause} WHERE id = ?', values)
        db.commit()
        for k, v in updates.items():
            setattr(self, k, v)

    def set_enabled(self, enabled):
        db = get_db()
        db.execute('UPDATE bot_configs SET enabled = ? WHERE id = ?', (int(enabled), self.id))
        db.commit()
        self.enabled = int(enabled)
