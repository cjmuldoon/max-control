"""Test Runner — CONTROL Quality Assurance.

"The old 'run the tests' trick."

Detects project type and runs the appropriate test suite.
Results are saved as tasks for the approval queue.
"""
import os
import subprocess
import uuid
import sqlite3
from datetime import datetime
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class TestRunner:
    """Runs test suites against projects — CONTROL QA Division."""

    def run_tests(self, project_id):
        """Detect and run the test suite for a project."""
        from flask import current_app
        db_path = current_app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
        if not project:
            conn.close()
            return {'success': False, 'error': 'Project not found'}

        project = dict(project)
        path = project['path']

        if not os.path.isdir(path):
            conn.close()
            return {'success': False, 'error': f'Directory not found: {path}'}

        # Detect test framework
        test_cmd, framework = self._detect_test_command(path)
        if not test_cmd:
            result = {
                'success': False,
                'framework': None,
                'error': 'No test framework detected. Would you believe... no tests?',
            }
            self._save_result(conn, project_id, result)
            conn.close()
            return result

        # Run tests
        socketio.emit('test_started', {
            'project_id': project_id,
            'framework': framework,
            'message': f'Running {framework} tests... {get_quote("loading")}',
        })

        try:
            proc = subprocess.run(
                test_cmd,
                cwd=path,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min max
                shell=isinstance(test_cmd, str),
            )

            result = {
                'success': proc.returncode == 0,
                'framework': framework,
                'exit_code': proc.returncode,
                'stdout': proc.stdout[-3000:] if proc.stdout else '',  # Last 3000 chars
                'stderr': proc.stderr[-1000:] if proc.stderr else '',
                'duration': None,
            }

        except subprocess.TimeoutExpired:
            result = {
                'success': False,
                'framework': framework,
                'error': 'Tests timed out after 5 minutes. "Missed it by that much!"',
            }
        except Exception as e:
            result = {
                'success': False,
                'framework': framework,
                'error': f'Sorry about that, Chief. {e}',
            }

        self._save_result(conn, project_id, result)
        conn.close()

        socketio.emit('test_completed', {
            'project_id': project_id,
            'success': result['success'],
            'framework': framework,
            'message': get_quote('success') if result['success'] else get_quote('error'),
        })

        # macOS notification
        from max.services.notification import notify
        status = 'PASSED' if result['success'] else 'FAILED'
        notify(
            f'Max — QA Division',
            f'{project["name"]} tests {status}',
            subtitle=framework,
        )

        return result

    def _detect_test_command(self, path):
        """Detect which test framework to use."""
        # Python — pytest
        if os.path.exists(os.path.join(path, 'pytest.ini')) or \
           os.path.exists(os.path.join(path, 'setup.cfg')) or \
           os.path.exists(os.path.join(path, 'pyproject.toml')) or \
           os.path.isdir(os.path.join(path, 'tests')):
            # Check if pytest is available
            if os.path.exists(os.path.join(path, 'venv', 'bin', 'pytest')):
                return [os.path.join(path, 'venv', 'bin', 'pytest'), '-v', '--tb=short'], 'pytest'
            return ['python', '-m', 'pytest', '-v', '--tb=short'], 'pytest'

        # Python — unittest
        if os.path.exists(os.path.join(path, 'test.py')):
            return ['python', '-m', 'unittest', 'discover', '-v'], 'unittest'

        # Node.js — npm test
        pkg_json = os.path.join(path, 'package.json')
        if os.path.exists(pkg_json):
            try:
                import json
                with open(pkg_json) as f:
                    pkg = json.load(f)
                if 'test' in pkg.get('scripts', {}):
                    return ['npm', 'test'], 'npm test'
            except Exception:
                pass

        # Flask — look for test files
        for name in ('test_app.py', 'tests.py'):
            if os.path.exists(os.path.join(path, name)):
                return ['python', '-m', 'pytest', name, '-v'], 'pytest'

        return None, None

    def _save_result(self, conn, project_id, result):
        """Save test result as a task."""
        now = datetime.utcnow().isoformat()
        task_id = str(uuid.uuid4())

        if result['success']:
            title = f'Tests PASSED ({result.get("framework", "unknown")})'
            description = f'All tests passed. {get_quote("success")}'
            if result.get('stdout'):
                # Extract summary line
                lines = result['stdout'].strip().split('\n')
                summary = lines[-1] if lines else ''
                description += f'\n\nSummary: {summary}'
            priority = 0
        else:
            title = f'Tests FAILED ({result.get("framework", "unknown")})'
            error = result.get('error', '')
            stderr = result.get('stderr', '')
            stdout_tail = result.get('stdout', '')[-500:]
            description = f'{error}\n\n{stderr}\n\n{stdout_tail}'.strip()
            priority = 2

        conn.execute(
            '''INSERT INTO tasks (id, project_id, title, description, type, status, source, priority, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'health_check', 'proposed', 'test_runner', ?, ?, ?)''',
            (task_id, project_id, title, description, priority, now, now),
        )
        conn.commit()


# Singleton
test_runner = TestRunner()
