"""Health Checker — CONTROL Medical Division.

"The old 'routine checkup' trick."

Runs health checks on projects by analysing their structure, dependencies,
and recent git activity. Results become tasks in the approval queue.
"""
import os
import json
import uuid
import sqlite3
import subprocess
from datetime import datetime
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class HealthChecker:
    """Project health assessment — CONTROL Medical."""

    def run_check(self, project_id):
        """Run a full health check on a project."""
        from flask import current_app
        db_path = current_app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
        if not project:
            conn.close()
            return

        project = dict(project)
        path = project['path']
        findings = []

        # Check 1: Directory exists
        if not os.path.isdir(path):
            findings.append({
                'severity': 'error',
                'title': 'Safe house missing',
                'detail': f'Project directory does not exist: {path}',
            })
            self._save_findings(conn, project_id, findings)
            conn.close()
            return

        # Check 2: Git status
        findings.extend(self._check_git(path))

        # Check 3: Dependency files
        findings.extend(self._check_dependencies(path))

        # Check 4: Common issues
        findings.extend(self._check_common_issues(path))

        # Check 5: File count / size
        findings.extend(self._check_project_size(path))

        self._save_findings(conn, project_id, findings)
        conn.close()

        # Notify
        socketio.emit('health_check_complete', {
            'project_id': project_id,
            'project_name': project['name'],
            'finding_count': len(findings),
            'message': get_quote('health_check'),
        })

        # macOS notification
        from max.services.notification import notify_health_check
        status = f'{len(findings)} findings' if findings else 'All clear'
        notify_health_check(project['name'], status)

    def _check_git(self, path):
        findings = []
        git_dir = os.path.join(path, '.git')

        if not os.path.isdir(git_dir):
            findings.append({
                'severity': 'warning',
                'title': 'No version control',
                'detail': 'Project is not a git repository. CONTROL recommends tracking all operations.',
            })
            return findings

        try:
            # Check for uncommitted changes
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=path, capture_output=True, text=True, timeout=10,
            )
            if result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                findings.append({
                    'severity': 'info',
                    'title': f'Uncommitted changes ({len(lines)} files)',
                    'detail': f'There are {len(lines)} uncommitted changes in the working directory.',
                })

            # Check for unpushed commits
            result = subprocess.run(
                ['git', 'log', '--oneline', '@{u}..HEAD'],
                cwd=path, capture_output=True, text=True, timeout=10,
            )
            if result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                findings.append({
                    'severity': 'warning',
                    'title': f'Unpushed commits ({len(lines)})',
                    'detail': f'{len(lines)} commits not yet pushed to remote.',
                })

        except Exception:
            pass

        return findings

    def _check_dependencies(self, path):
        findings = []

        # Python
        req_file = os.path.join(path, 'requirements.txt')
        if os.path.exists(req_file):
            findings.append({
                'severity': 'info',
                'title': 'Python project detected',
                'detail': 'requirements.txt found. Consider running pip-audit for vulnerability scan.',
            })

        # Node
        pkg_file = os.path.join(path, 'package.json')
        if os.path.exists(pkg_file):
            findings.append({
                'severity': 'info',
                'title': 'Node.js project detected',
                'detail': 'package.json found. Consider running npm audit for vulnerability scan.',
            })

            # Check for outdated lockfile
            lock_file = os.path.join(path, 'package-lock.json')
            if os.path.exists(pkg_file) and not os.path.exists(lock_file):
                findings.append({
                    'severity': 'warning',
                    'title': 'No lockfile',
                    'detail': 'package.json exists but no package-lock.json. Run npm install to generate one.',
                })

        return findings

    def _check_common_issues(self, path):
        findings = []

        # Check for .env file (shouldn't be committed)
        env_file = os.path.join(path, '.env')
        gitignore = os.path.join(path, '.gitignore')

        if os.path.exists(env_file):
            ignored = False
            if os.path.exists(gitignore):
                with open(gitignore) as f:
                    ignored = '.env' in f.read()

            if not ignored:
                findings.append({
                    'severity': 'error',
                    'title': 'Exposed secrets risk',
                    'detail': '.env file exists but is not in .gitignore. Classified intel may be exposed!',
                })

        # Check for TODO/FIXME in recent files
        # (lightweight — just check top-level files)
        todo_count = 0
        for f in os.listdir(path):
            fp = os.path.join(path, f)
            if os.path.isfile(fp) and f.endswith(('.py', '.js', '.ts', '.html')):
                try:
                    with open(fp) as fh:
                        content = fh.read()
                        todo_count += content.upper().count('TODO')
                        todo_count += content.upper().count('FIXME')
                except Exception:
                    pass

        if todo_count > 0:
            findings.append({
                'severity': 'info',
                'title': f'{todo_count} TODOs/FIXMEs found',
                'detail': f'Found {todo_count} TODO/FIXME markers in top-level source files.',
            })

        return findings

    def _check_project_size(self, path):
        findings = []
        try:
            file_count = 0
            total_size = 0
            for root, dirs, files in os.walk(path):
                # Skip common large dirs
                dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', 'venv', '__pycache__', '.venv'}]
                for f in files:
                    file_count += 1
                    total_size += os.path.getsize(os.path.join(root, f))

            size_mb = total_size / (1024 * 1024)
            findings.append({
                'severity': 'info',
                'title': f'Project size: {file_count} files, {size_mb:.1f} MB',
                'detail': f'Excluding .git, node_modules, venv, __pycache__.',
            })
        except Exception:
            pass

        return findings

    def _save_findings(self, conn, project_id, findings):
        """Save health check findings as tasks."""
        now = datetime.utcnow().isoformat()
        for finding in findings:
            task_id = str(uuid.uuid4())
            conn.execute(
                '''INSERT INTO tasks (id, project_id, title, description, type, status, source, priority, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'health_check', 'proposed', 'health_check', ?, ?, ?)''',
                (
                    task_id, project_id, finding['title'], finding['detail'],
                    {'error': 2, 'warning': 1, 'info': 0}.get(finding['severity'], 0),
                    now, now,
                ),
            )
        conn.commit()


# Singleton
health_checker = HealthChecker()
