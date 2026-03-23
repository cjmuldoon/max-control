"""Notion Sync — CONTROL Intelligence Database.

"99 has the latest intelligence from the Notion dossiers, Chief."

Syncs linked Notion pages with projects — pulls updates, creates tasks
from action items, and pushes status updates back.

Uses the Notion MCP server configured in the user's Claude settings.
Falls back to direct API calls if available.
"""
import os
import json
import uuid
import sqlite3
import subprocess
from datetime import datetime
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class NotionSyncService:
    """Sync with Notion intelligence dossiers."""

    def __init__(self):
        self._app = None

    def init_app(self, app):
        self._app = app

    def sync_project(self, project_id):
        """Sync a project's linked Notion page.

        Pulls content from the Notion page, looks for:
        - Action items / todos
        - Status updates
        - Notes and decisions

        Creates tasks from findings.
        """
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
            notion_page_id = project.get('notion_page_id', '')

            if not notion_page_id:
                conn.close()
                return {
                    'success': False,
                    'error': f'No Notion page linked to {project["name"]}. Set it in the project dossier.',
                }

            # Try to fetch Notion page content using Claude CLI with Notion MCP
            items = self._fetch_via_claude(project, notion_page_id)

            if items is None:
                # Fallback: create a note that Notion sync was attempted
                items = [{
                    'title': f'Notion sync attempted for {project["name"]}',
                    'description': f'Notion page ID: {notion_page_id}. '
                                   f'Ensure the Notion MCP server is configured to access this page.',
                    'type': 'info',
                }]

            # Save items as tasks
            new_count = 0
            now = datetime.utcnow().isoformat()
            for item in items:
                external_ref = f'notion:{notion_page_id}:{item.get("title", "")[:50]}'

                existing = conn.execute(
                    'SELECT id FROM tasks WHERE project_id = ? AND external_ref = ?',
                    (project_id, external_ref),
                ).fetchone()
                if existing:
                    continue

                task_id = str(uuid.uuid4())
                conn.execute(
                    '''INSERT INTO tasks (id, project_id, title, description, type, status, source, external_ref, priority, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, 'pending', 'notion', ?, ?, ?, ?)''',
                    (task_id, project_id, item['title'], item.get('description', ''),
                     item.get('type', 'feature'), external_ref,
                     item.get('priority', 0), now, now),
                )
                new_count += 1

            conn.commit()
            conn.close()

            socketio.emit('notion_synced', {
                'project_id': project_id,
                'project_name': project['name'],
                'new_items': new_count,
            })

            return {
                'success': True,
                'new_items': new_count,
                'message': f'{new_count} new intel items from Notion dossier. {get_quote("success")}',
            }

    def sync_all_projects(self):
        """Sync Notion for all projects that have a linked page."""
        if not self._app:
            return []

        with self._app.app_context():
            db_path = self._app.config['DB_PATH']
            conn = sqlite3.connect(db_path)
            projects = conn.execute(
                "SELECT id, name FROM projects WHERE notion_page_id IS NOT NULL AND notion_page_id != ''"
            ).fetchall()
            conn.close()

            results = []
            for p in projects:
                result = self.sync_project(p['id'])
                results.append({'project': p['name'], **result})

            return results

    def _fetch_via_claude(self, project, notion_page_id):
        """Use Claude CLI to fetch Notion page content via MCP."""
        cli_path = self._app.config['CLAUDE_CLI_PATH']
        if not os.path.exists(cli_path):
            return None

        prompt = f"""Use the Notion MCP tools to fetch the page with ID "{notion_page_id}".
Look for any action items, todos, decisions, or status updates.
Return them as a JSON array: [{{"title": "...", "description": "...", "type": "feature|bug|improvement", "priority": 0}}]
Only output the JSON array."""

        try:
            result = subprocess.run(
                [cli_path, '--print', '--model', 'haiku', '-p', prompt],
                capture_output=True, text=True, timeout=30,
                cwd=project['path'] if os.path.isdir(project['path']) else None,
            )

            output = result.stdout.strip()
            if '[' in output:
                json_start = output.index('[')
                json_end = output.rindex(']') + 1
                return json.loads(output[json_start:json_end])

        except Exception:
            pass

        return None


# Singleton
notion_sync_service = NotionSyncService()
