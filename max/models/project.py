import uuid
import re
from dataclasses import dataclass, field
from datetime import datetime
from max.db.connection import get_db


@dataclass
class Project:
    id: str = ''
    name: str = ''
    slug: str = ''
    path: str = ''
    location_type: str = 'local'
    github_url: str = ''
    notion_page_id: str = ''
    description: str = ''
    brief: str = ''
    tech_stack: str = ''
    environments_info: str = ''
    conventions: str = ''
    status: str = 'inactive'
    created_at: str = ''
    updated_at: str = ''

    @staticmethod
    def slugify(name):
        """Convert name to URL-safe slug."""
        slug = name.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_-]+', '-', slug)
        return slug.strip('-')

    @staticmethod
    def create(name, path, location_type='local', description='', github_url='', notion_page_id=''):
        """Create a new project in CONTROL's database."""
        db = get_db()
        project_id = str(uuid.uuid4())
        slug = Project.slugify(name)

        db.execute(
            '''INSERT INTO projects (id, name, slug, path, location_type, description, github_url, notion_page_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (project_id, name, slug, path, location_type, description, github_url, notion_page_id),
        )
        db.commit()
        return Project.get_by_id(project_id)

    @staticmethod
    def get_by_id(project_id):
        db = get_db()
        row = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
        if row is None:
            return None
        return Project(**dict(row))

    @staticmethod
    def get_all():
        db = get_db()
        rows = db.execute('SELECT * FROM projects ORDER BY name').fetchall()
        return [Project(**dict(row)) for row in rows]

    @staticmethod
    def get_by_slug(slug):
        db = get_db()
        row = db.execute('SELECT * FROM projects WHERE slug = ?', (slug,)).fetchone()
        if row is None:
            return None
        return Project(**dict(row))

    def update(self, **kwargs):
        db = get_db()
        allowed = {'name', 'description', 'github_url', 'notion_page_id', 'status',
                   'brief', 'tech_stack', 'environments_info', 'conventions'}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return

        updates['updated_at'] = datetime.utcnow().isoformat()
        set_clause = ', '.join(f'{k} = ?' for k in updates)
        values = list(updates.values()) + [self.id]

        db.execute(f'UPDATE projects SET {set_clause} WHERE id = ?', values)
        db.commit()

        for k, v in updates.items():
            setattr(self, k, v)

    def delete(self):
        db = get_db()
        db.execute('DELETE FROM projects WHERE id = ?', (self.id,))
        db.commit()

    def get_agent(self):
        """Get the current agent for this project."""
        from max.models.agent import Agent
        return Agent.get_by_project(self.id)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'path': self.path,
            'location_type': self.location_type,
            'github_url': self.github_url,
            'notion_page_id': self.notion_page_id,
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }
