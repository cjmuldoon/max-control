"""Roadmap Integration — Mission Intelligence.

"99 always has the latest intelligence, Chief."

Pulls GitHub issues via `gh` CLI or reads a local ROADMAP.md.
Surfaces items as tasks in the Mission Briefings queue.
"""
import os
import json
import uuid
import sqlite3
import subprocess
from datetime import datetime
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class RoadmapService:
    """Integrates project roadmaps — GitHub issues or local files."""

    def sync_roadmap(self, project_id):
        """Sync roadmap items for a project."""
        from flask import current_app
        db_path = current_app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
        if not project:
            conn.close()
            return {'success': False, 'error': 'Project not found'}

        project = dict(project)
        items = []

        # Try in-app feedback API first (the real backlog)
        env_configs = self._get_feedback_configs()
        project_name_lower = project['name'].lower()
        for config in env_configs:
            if config['project'].lower() in project_name_lower or project_name_lower in config['project'].lower():
                items = self._fetch_feedback_api(config['url'])
                if items:
                    break

        # Try SSH + DB if no API available and we have environment info
        if not items:
            items = self._fetch_feedback_ssh(project)

        # Try GitHub issues
        if not items and project.get('github_url'):
            items = self._fetch_github_issues(project['github_url'], project['path'])

        # Fallback to local ROADMAP.md
        if not items:
            items = self._read_local_roadmap(project['path'])

        # Create a local ROADMAP.md if nothing exists
        if not items:
            self._create_default_roadmap(project['path'], project['name'])
            items = [{'title': 'Roadmap created', 'type': 'info',
                      'description': f'A default ROADMAP.md has been created for {project["name"]}.'}]

        # Save as tasks (avoid duplicates by checking external_ref)
        new_count = 0
        for item in items:
            external_ref = item.get('external_ref', '')
            if external_ref:
                existing = conn.execute(
                    'SELECT id FROM tasks WHERE project_id = ? AND external_ref = ?',
                    (project_id, external_ref),
                ).fetchone()
                if existing:
                    continue

            task_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            conn.execute(
                '''INSERT INTO tasks (id, project_id, title, description, type, status, source, external_ref, priority, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 'pending', 'roadmap', ?, ?, ?, ?)''',
                (task_id, project_id, item['title'], item.get('description', ''),
                 item.get('type', 'feature'), external_ref,
                 item.get('priority', 0), now, now),
            )
            new_count += 1

        conn.commit()
        conn.close()

        socketio.emit('roadmap_synced', {
            'project_id': project_id,
            'project_name': project['name'],
            'new_items': new_count,
            'total_items': len(items),
        })

        return {
            'success': True,
            'new_items': new_count,
            'total_items': len(items),
            'message': f'{new_count} new intel items from roadmap. {get_quote("success")}',
        }

    def _fetch_github_issues(self, github_url, project_path):
        """Fetch open issues from GitHub using `gh` CLI."""
        items = []

        # Extract owner/repo from URL
        # https://github.com/user/repo.git -> user/repo
        repo = github_url.rstrip('/').rstrip('.git')
        if 'github.com/' in repo:
            repo = repo.split('github.com/')[-1]
        else:
            return items

        try:
            result = subprocess.run(
                ['gh', 'issue', 'list', '--repo', repo, '--json',
                 'number,title,body,labels,state,url', '--limit', '50'],
                capture_output=True, text=True, timeout=30,
                cwd=project_path if os.path.isdir(project_path) else None,
            )

            if result.returncode == 0 and result.stdout.strip():
                issues = json.loads(result.stdout)
                for issue in issues:
                    # Determine type from labels
                    labels = [l.get('name', '').lower() for l in issue.get('labels', [])]
                    if any('bug' in l for l in labels):
                        issue_type = 'bug'
                        priority = 2
                    elif any('feature' in l or 'enhancement' in l for l in labels):
                        issue_type = 'feature'
                        priority = 1
                    else:
                        issue_type = 'feature'
                        priority = 0

                    items.append({
                        'title': f'#{issue["number"]}: {issue["title"]}',
                        'description': (issue.get('body', '') or '')[:500],
                        'type': issue_type,
                        'priority': priority,
                        'external_ref': issue.get('url', f'gh:{repo}#{issue["number"]}'),
                    })

        except FileNotFoundError:
            pass  # gh CLI not installed
        except Exception:
            pass

        return items

    def _read_local_roadmap(self, project_path):
        """Read a local ROADMAP.md file."""
        items = []
        roadmap_path = os.path.join(project_path, 'ROADMAP.md')

        if not os.path.exists(roadmap_path):
            return items

        try:
            with open(roadmap_path) as f:
                content = f.read()

            # Parse markdown checklist items: - [ ] Item or - [x] Item
            import re
            for match in re.finditer(r'- \[([ x])\] (.+)', content):
                checked = match.group(1) == 'x'
                title = match.group(2).strip()

                if not checked:  # Only unchecked items
                    # Detect type from keywords
                    title_lower = title.lower()
                    if any(w in title_lower for w in ['bug', 'fix', 'broken', 'error']):
                        item_type = 'bug'
                        priority = 2
                    elif any(w in title_lower for w in ['improve', 'refactor', 'optimize']):
                        item_type = 'improvement'
                        priority = 1
                    else:
                        item_type = 'feature'
                        priority = 0

                    items.append({
                        'title': title,
                        'type': item_type,
                        'priority': priority,
                        'external_ref': f'roadmap:{title[:50]}',
                    })

        except Exception:
            pass

        return items

    def _create_default_roadmap(self, project_path, project_name):
        """Create a default ROADMAP.md for a project."""
        roadmap_path = os.path.join(project_path, 'ROADMAP.md')
        if os.path.exists(roadmap_path):
            return

        try:
            content = f"""# {project_name} — Roadmap

## Backlog

- [ ] Initial project health check
- [ ] Set up automated testing
- [ ] Configure CI/CD pipeline
- [ ] Documentation review

## In Progress

## Done

"""
            with open(roadmap_path, 'w') as f:
                f.write(content)
        except Exception:
            pass


    def _get_feedback_configs(self):
        """Known feedback system URLs for each project."""
        return [
            {'project': 'MapVS', 'url': 'https://mapvs.com/api/v1/feedback'},
            {'project': 'AssetArc', 'url': 'https://assetarc.io/api/v1/feedback'},
            # Add more as projects get the API endpoint:
            # {'project': 'WOTCE', 'url': 'https://wotce.com/api/v1/feedback'},
            # {'project': 'PlanningPortal', 'url': 'https://planningportal.com/api/v1/feedback'},
        ]

    def _fetch_feedback_api(self, api_url):
        """Fetch feedback items from an app's /api/v1/feedback endpoint."""
        import urllib.request
        items = []

        try:
            # Fetch open/planned/in_progress items
            url = f'{api_url}?status=open,planned,in_progress&limit=50'
            req = urllib.request.Request(url, headers={'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())

            for post in data.get('posts', []):
                # Map category to task type
                category = post.get('category', '')
                type_map = {
                    'bug_report': 'bug',
                    'feature_request': 'feature',
                    'improvement': 'improvement',
                    'new_tool': 'feature',
                    'integration': 'feature',
                }
                task_type = type_map.get(category, 'feature')

                # Map priority
                priority_val = post.get('priority', 0)
                if isinstance(priority_val, str):
                    priority_val = {'high': 2, 'medium': 1, 'low': 0}.get(priority_val, 0)

                items.append({
                    'title': f'[{post.get("status", "open")}] {post["title"]}',
                    'description': (
                        f'{post.get("description", "")[:300]}\n\n'
                        f'Votes: {post.get("vote_count", 0)} | '
                        f'Comments: {post.get("comment_count", 0)}'
                        f'{" | Admin: " + post["admin_response"][:100] if post.get("admin_response") else ""}'
                    ),
                    'type': task_type,
                    'priority': priority_val,
                    'external_ref': f'feedback:{post["id"]}',
                })

        except Exception:
            pass

        return items

    def _fetch_feedback_ssh(self, project):
        """Fetch feedback by SSH-ing into the server and querying SQLite.

        Fallback when no API endpoint is available.
        """
        items = []

        # Check if we have environment info for this project
        from flask import current_app
        db_path = current_app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        envs = conn.execute(
            'SELECT * FROM project_environments WHERE project_id = ? AND is_default = 1',
            (project['id'],),
        ).fetchone()
        conn.close()

        if not envs:
            return items

        env = dict(envs)
        if env.get('connection_type') != 'ssh' or not env.get('host'):
            return items

        # SSH in and query the feedback_posts table
        try:
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                'hostname': env['host'],
                'port': env.get('port', 22),
                'username': 'root',
                'timeout': 10,
            }

            key_path = os.path.expanduser('~/.ssh/id_rsa')
            if os.path.exists(key_path):
                connect_kwargs['key_filename'] = key_path

            client.connect(**connect_kwargs)

            # Try to find and query the SQLite database
            # Common locations for Flask apps
            db_paths_to_try = [
                f'/var/www/{project.get("slug", "")}/instance/*.db',
                f'/var/www/{project.get("slug", "")}/*.db',
                f'/home/{project.get("slug", "")}/*.db',
            ]

            cmd = (
                'find /var/www -name "*.db" -path "*/instance/*" 2>/dev/null | head -5; '
                'find /var/www -maxdepth 3 -name "*.db" 2>/dev/null | head -5'
            )
            stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
            db_files = stdout.read().decode().strip().split('\n')
            db_files = [f for f in db_files if f.strip()]

            for db_file in db_files:
                query = (
                    f'sqlite3 -json "{db_file}" '
                    f'"SELECT id, title, description, category, status, priority, vote_count, comment_count, admin_response '
                    f'FROM feedback_posts WHERE status IN (\'open\', \'planned\', \'in_progress\') '
                    f'ORDER BY created_at DESC LIMIT 50;" 2>/dev/null'
                )
                stdin, stdout, stderr = client.exec_command(query, timeout=10)
                output = stdout.read().decode().strip()

                if output and output.startswith('['):
                    try:
                        rows = json.loads(output)
                        for row in rows:
                            category = row.get('category', '')
                            type_map = {
                                'bug_report': 'bug',
                                'feature_request': 'feature',
                                'improvement': 'improvement',
                            }

                            items.append({
                                'title': f'[{row.get("status", "open")}] {row["title"]}',
                                'description': (row.get('description', '') or '')[:300],
                                'type': type_map.get(category, 'feature'),
                                'priority': row.get('priority', 0) if isinstance(row.get('priority'), int) else 0,
                                'external_ref': f'feedback-ssh:{row["id"]}',
                            })
                        break  # Found feedback in this db
                    except json.JSONDecodeError:
                        pass

            client.close()

        except Exception:
            pass

        return items


# Singleton
roadmap_service = RoadmapService()
