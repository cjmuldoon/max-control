"""Consolidated Feedback Register — all project intelligence in one place.

"99 has compiled all field reports into a single dossier, Chief."

Pulls feedback from all projects' APIs (or SSH+DB), consolidates into
a unified register. Supports adding new items that get pushed back
to the respective project's feedback board.
"""
import os
import json
import uuid
import sqlite3
import urllib.request
from datetime import datetime
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class FeedbackRegisterService:
    """Consolidated feedback across all projects."""

    # Known project feedback API URLs
    # Map project slugs to their feedback API URLs
    # Configure via the project detail page or add here
    FEEDBACK_URLS = {}

    def __init__(self):
        self._app = None

    def init_app(self, app):
        self._app = app

    def sync_all(self):
        """Pull feedback from all projects into the register."""
        if not self._app:
            return {'success': False, 'error': 'Not initialized'}

        with self._app.app_context():
            db_path = self._app.config['DB_PATH']
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row

            projects = conn.execute('SELECT * FROM projects').fetchall()
            total_new = 0

            for project in projects:
                project = dict(project)
                slug = project['slug']

                # Try API first
                api_url = self.FEEDBACK_URLS.get(slug)
                items = []
                if api_url:
                    items = self._fetch_api(api_url)

                # Fallback: try local feedback_posts via SSH or direct DB
                if not items:
                    items = self._fetch_local_db(project)

                # Upsert into register
                new_count = self._upsert_items(conn, project['id'], items)
                total_new += new_count

            conn.close()

            return {
                'success': True,
                'new_items': total_new,
                'message': f'{total_new} new items synced to the register. {get_quote("success")}',
            }

    def sync_project(self, project_id):
        """Sync feedback for a single project."""
        if not self._app:
            return {'success': False, 'error': 'Not initialized'}

        with self._app.app_context():
            db_path = self._app.config['DB_PATH']
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row

            project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
            if not project:
                conn.close()
                return {'success': False, 'error': 'Project not found'}

            project = dict(project)
            slug = project['slug']

            api_url = self.FEEDBACK_URLS.get(slug)
            items = []
            if api_url:
                items = self._fetch_api(api_url)
            if not items:
                items = self._fetch_local_db(project)

            new_count = self._upsert_items(conn, project['id'], items)
            conn.close()

            return {
                'success': True,
                'new_items': new_count,
                'message': f'{new_count} items synced for {project["name"]}.',
            }

    def get_all(self, status=None, statuses=None, category=None, project_id=None, limit=200):
        """Get all feedback items with optional filters. Supports multi-status."""
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        query = '''
            SELECT fr.*, COALESCE(p.name, 'General') as project_name, COALESCE(p.slug, '') as project_slug
            FROM feedback_register fr
            LEFT JOIN projects p ON fr.project_id = p.id
            WHERE 1=1
        '''
        params = []

        if statuses:
            placeholders = ','.join('?' * len(statuses))
            query += f' AND fr.status IN ({placeholders})'
            params.extend(statuses)
        elif status:
            query += ' AND fr.status = ?'
            params.append(status)
        if category:
            query += ' AND fr.category = ?'
            params.append(category)
        if project_id:
            query += ' AND fr.project_id = ?'
            params.append(project_id)

        query += ' ORDER BY fr.updated_at DESC LIMIT ?'
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_stats(self):
        """Get aggregate stats for the register."""
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)

        stats = {}
        for status in ('open', 'planned', 'in_progress', 'completed', 'declined', 'under_review'):
            count = conn.execute(
                'SELECT COUNT(*) FROM feedback_register WHERE status = ?', (status,)
            ).fetchone()[0]
            if count > 0:
                stats[status] = count

        stats['total'] = conn.execute('SELECT COUNT(*) FROM feedback_register').fetchone()[0]

        # By project
        rows = conn.execute('''
            SELECT COALESCE(p.name, 'General'), COUNT(*) as cnt
            FROM feedback_register fr LEFT JOIN projects p ON fr.project_id = p.id
            GROUP BY COALESCE(p.name, 'General')
        ''').fetchall()
        stats['by_project'] = {row[0]: row[1] for row in rows}

        # By category
        rows = conn.execute('''
            SELECT category, COUNT(*) as cnt FROM feedback_register GROUP BY category
        ''').fetchall()
        stats['by_category'] = {row[0]: row[1] for row in rows}

        conn.close()
        return stats

    def add_item(self, project_id, title, description='', category='feature_request', priority='medium'):
        """Add a new item. project_id can be None for general tasks."""
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)

        item_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        # Use empty string for no project (FK allows it since it won't match any project)
        pid = project_id or ''

        conn.execute(
            '''INSERT INTO feedback_register
               (id, project_id, title, description, category, status, priority, source, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'open', ?, 'manual', ?, ?)''',
            (item_id, pid, title, description, category, priority, now, now),
        )
        conn.commit()
        conn.close()

        return item_id

    def update_item(self, item_id, status=None, admin_response=None, assigned_to=None, scheduled_at=None):
        """Update an item — status, assignment, schedule. Pushes to source if possible."""
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        now = datetime.utcnow().isoformat()

        updates = ['updated_at = ?']
        params = [now]

        if status:
            updates.append('status = ?')
            params.append(status)
        if admin_response is not None:
            updates.append('admin_response = ?')
            params.append(admin_response)
        if assigned_to is not None:
            updates.append('assigned_to = ?')
            params.append(assigned_to)
        if scheduled_at is not None:
            updates.append('scheduled_at = ?')
            params.append(scheduled_at)

        params.append(item_id)
        conn.execute(f'UPDATE feedback_register SET {", ".join(updates)} WHERE id = ?', params)
        conn.commit()

        # Push status change back to source API
        if status:
            item = conn.execute(
                '''SELECT fr.*, p.slug as project_slug FROM feedback_register fr
                   JOIN projects p ON fr.project_id = p.id WHERE fr.id = ?''',
                (item_id,),
            ).fetchone()
            if item:
                self._push_status_to_source(dict(item), status, admin_response)

        conn.close()

    def _push_status_to_source(self, item, status, admin_response=None):
        """Push a status update back to the project's production feedback board."""
        slug = item.get('project_slug', '')
        remote_id = item.get('remote_id')
        if not remote_id or not slug:
            return

        # Use the project's feedback status endpoint
        api_base = self.FEEDBACK_URLS.get(slug, '')
        if not api_base:
            return

        # POST to /feedback/<id>/status on the project
        status_url = api_base.replace('/api/v1/feedback', f'/feedback/{remote_id}/status')
        try:
            import urllib.parse
            data = urllib.parse.urlencode({
                'status': status,
                'admin_response': admin_response or '',
            }).encode()
            req = urllib.request.Request(status_url, data=data, method='POST')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass  # Best effort — don't fail if source is unreachable

    def _fetch_api(self, api_url):
        """Fetch from project's /api/v1/feedback endpoint."""
        items = []
        try:
            # Fetch ALL statuses
            url = f'{api_url}?limit=200'
            req = urllib.request.Request(url, headers={'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            posts = data.get('data', data.get('posts', []))
            if isinstance(posts, list):
                for p in posts:
                    items.append({
                        'remote_id': p.get('id'),
                        'title': p.get('title', ''),
                        'description': p.get('description', ''),
                        'category': p.get('category', 'feature_request'),
                        'status': p.get('status', 'open'),
                        'priority': p.get('priority', 'medium'),
                        'vote_count': p.get('vote_count', 0),
                        'comment_count': p.get('comment_count', 0),
                        'admin_response': p.get('admin_response', ''),
                        'author_name': p.get('author_name', ''),
                        'created_at': p.get('created_at', ''),
                        'updated_at': p.get('updated_at', ''),
                    })
        except Exception:
            pass
        return items

    def _fetch_local_db(self, project):
        """Try to read feedback directly from the project's local SQLite."""
        items = []
        path = project.get('path', '')
        if not path:
            return items

        # Common SQLite database locations
        db_candidates = [
            os.path.join(path, 'instance', f'{project["slug"]}.db'),
            os.path.join(path, f'{project["slug"]}.db'),
            os.path.join(path, 'instance', 'app.db'),
        ]

        for db_file in db_candidates:
            if not os.path.exists(db_file):
                continue
            try:
                conn = sqlite3.connect(db_file)
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    'SELECT * FROM feedback_posts ORDER BY created_at DESC LIMIT 200'
                ).fetchall()
                for r in rows:
                    r = dict(r)
                    items.append({
                        'remote_id': r.get('id'),
                        'title': r.get('title', ''),
                        'description': r.get('description', ''),
                        'category': r.get('category', 'feature_request'),
                        'status': r.get('status', 'open'),
                        'priority': r.get('priority', 'medium') if isinstance(r.get('priority'), str) else 'medium',
                        'vote_count': r.get('vote_count', 0),
                        'comment_count': r.get('comment_count', 0),
                        'admin_response': r.get('admin_response', ''),
                        'author_name': r.get('author_name', ''),
                        'created_at': r.get('created_at', ''),
                        'updated_at': r.get('updated_at', ''),
                    })
                conn.close()
                break  # Found it
            except Exception:
                continue
        return items

    def _upsert_items(self, conn, project_id, items):
        """Upsert items into the register. Returns count of new items."""
        now = datetime.utcnow().isoformat()
        new_count = 0

        for item in items:
            remote_id = item.get('remote_id')

            # Check if already exists
            if remote_id:
                existing = conn.execute(
                    'SELECT id FROM feedback_register WHERE project_id = ? AND remote_id = ?',
                    (project_id, remote_id),
                ).fetchone()

                if existing:
                    # Update existing
                    conn.execute(
                        '''UPDATE feedback_register SET
                           title = ?, description = ?, status = ?, priority = ?,
                           vote_count = ?, comment_count = ?, admin_response = ?,
                           synced_at = ?, updated_at = ?
                           WHERE id = ?''',
                        (item['title'], item.get('description', ''), item['status'],
                         item.get('priority', 'medium'), item.get('vote_count', 0),
                         item.get('comment_count', 0), item.get('admin_response', ''),
                         now, item.get('updated_at', now), existing['id']),
                    )
                    continue

            # Insert new
            item_id = str(uuid.uuid4())
            conn.execute(
                '''INSERT INTO feedback_register
                   (id, project_id, remote_id, title, description, category, status, priority,
                    vote_count, comment_count, admin_response, author_name, source, synced_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'sync', ?, ?, ?)''',
                (item_id, project_id, remote_id, item['title'], item.get('description', ''),
                 item.get('category', 'feature_request'), item['status'],
                 item.get('priority', 'medium'), item.get('vote_count', 0),
                 item.get('comment_count', 0), item.get('admin_response', ''),
                 item.get('author_name', ''), now,
                 item.get('created_at', now), item.get('updated_at', now)),
            )
            new_count += 1

        conn.commit()
        return new_count


# Singleton
feedback_register = FeedbackRegisterService()
