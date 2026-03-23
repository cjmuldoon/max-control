"""Task Executor — launches Claude agents to work on assigned feedback items.

"86, you have your orders. Report when complete."

Runs tasks sequentially per project (no conflicts). No timeout — agents
run to completion. Progressive updates posted to inbox and Discord.
"""
import os
import json
import subprocess
import threading
import sqlite3
import time
from datetime import datetime
from collections import defaultdict
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class TaskExecutor:
    """Executes assigned feedback items via Claude agents."""

    def __init__(self):
        self._app = None
        self._queues = defaultdict(list)  # project_id -> [item_ids]
        self._running = {}  # project_id -> True if a worker is active
        self._lock = threading.Lock()

    def init_app(self, app):
        self._app = app

    def execute_item(self, item_id):
        """Queue an item for execution. Runs sequentially per project."""
        if not self._app:
            return {'success': False, 'error': 'Not initialized'}

        with self._app.app_context():
            db_path = self._app.config['DB_PATH']
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            item = conn.execute(
                '''SELECT fr.*, p.name as project_name, p.slug as project_slug, p.path as project_path
                   FROM feedback_register fr
                   LEFT JOIN projects p ON fr.project_id = p.id
                   WHERE fr.id = ?''',
                (item_id,),
            ).fetchone()
            conn.close()

            if not item:
                return {'success': False, 'error': 'Item not found'}

            item = dict(item)
            project_id = item.get('project_id', 'general')

        with self._lock:
            self._queues[project_id].append(item_id)

            # Start worker for this project if not already running
            if not self._running.get(project_id):
                self._running[project_id] = True
                thread = threading.Thread(
                    target=self._project_worker,
                    args=(project_id,),
                    daemon=True,
                    name=f'executor-{project_id[:8]}',
                )
                thread.start()

        return {
            'success': True,
            'message': f'Queued for execution: {item.get("title", "")}',
            'queue_position': len(self._queues[project_id]),
        }

    def _project_worker(self, project_id):
        """Process items sequentially for a project."""
        while True:
            with self._lock:
                if not self._queues[project_id]:
                    self._running[project_id] = False
                    return
                item_id = self._queues[project_id].pop(0)

            try:
                self._execute_single(item_id)
            except Exception as e:
                print(f'[TaskExecutor] ERROR on {item_id[:8]}: {e}')
                import traceback
                traceback.print_exc()

    def _execute_single(self, item_id):
        """Execute a single item — no timeout, progressive updates."""
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        item = conn.execute(
            '''SELECT fr.*, p.name as project_name, p.slug as project_slug, p.path as project_path
               FROM feedback_register fr
               LEFT JOIN projects p ON fr.project_id = p.id
               WHERE fr.id = ?''',
            (item_id,),
        ).fetchone()

        if not item:
            conn.close()
            return

        item = dict(item)

        # Update status
        conn.execute(
            "UPDATE feedback_register SET status = 'in_progress', updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), item_id),
        )
        conn.commit()
        conn.close()

        # Determine model
        assigned = item.get('assigned_to', '')
        model = 'opus' if 'opus' in assigned.lower() else 'haiku' if 'haiku' in assigned.lower() else 'sonnet'

        # Post start update
        self._post_update(item_id, item,
            f'Starting work on this, Chief. Using {model} model.',
            item.get('assigned_to', '86'))

        # Build prompt
        prompt = self._build_prompt(item)

        # Get project path
        project_path = item.get('project_path', '')
        if not project_path or not os.path.isdir(project_path):
            project_path = os.path.dirname(self._app.config['DB_PATH'])

        cli_path = self._app.config['CLAUDE_CLI_PATH']
        results_dir = os.path.join(os.path.dirname(self._app.config['DB_PATH']), 'task_results')
        os.makedirs(results_dir, exist_ok=True)
        result_file = os.path.join(results_dir, f'feedback-{item_id[:8]}.md')

        cmd = [
            cli_path, '--print',
            '--model', model,
            '--dangerously-skip-permissions',
            '-p', prompt,
        ]

        # Unset ANTHROPIC_API_KEY so CLI uses subscription, not API credits
        env = os.environ.copy()
        env.pop('ANTHROPIC_API_KEY', None)

        try:
            # Stream output for progressive updates
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=project_path,
                env=env,
                start_new_session=True,  # Survives parent death
            )

            output_chunks = []
            last_update = time.time()

            # Read output progressively
            for line in iter(proc.stdout.readline, ''):
                output_chunks.append(line)

                # Post progress every 60 seconds
                if time.time() - last_update > 120:
                    progress = ''.join(output_chunks[-20:])  # Last 20 lines
                    self._post_update(item_id, item,
                        f'Still working, Chief. Progress:\n\n{progress[:500]}...',
                        item.get('assigned_to', '86'))
                    last_update = time.time()

            proc.wait()
            output = ''.join(output_chunks).strip() or 'No output'

            # Save full result
            with open(result_file, 'w') as f:
                f.write(f'# Task Result: {item.get("title", "")}\n\n')
                f.write(f'**Model:** {model}\n')
                f.write(f'**Project:** {item.get("project_name", "General")}\n')
                f.write(f'**Completed:** {datetime.now().isoformat()}\n\n')
                f.write(f'## Result\n\n{output}\n')

            # Git: commit changes to branch and push
            deploy_info = self._git_commit_and_push(item, project_path)

            # Update register
            db_path = self._app.config['DB_PATH']
            conn = sqlite3.connect(db_path)
            now = datetime.now().isoformat()

            if deploy_info.get('committed'):
                branch = deploy_info.get('branch', '')
                commit = deploy_info.get('commit', '')
                files = deploy_info.get('files_changed', 0)
                conn.execute(
                    '''UPDATE feedback_register SET status = 'under_review',
                       deploy_status = 'awaiting_review', deploy_branch = ?, deploy_commit = ?,
                       admin_response = ?, updated_at = ? WHERE id = ?''',
                    (branch, commit,
                     f'Ready for review. Branch: {branch} ({files} files). Result: {result_file}',
                     now, item_id),
                )
                summary = output[:600] if len(output) > 600 else output
                self._post_update(item_id, item,
                    f'Work complete, Chief. Committed to `{branch}` ({files} files changed).\n\n'
                    f'**Approve to deploy** or reply with adjustments.\n\nSummary:\n{summary}',
                    item.get('assigned_to', '86'))
            else:
                conn.execute(
                    "UPDATE feedback_register SET status = 'completed', admin_response = ?, updated_at = ? WHERE id = ?",
                    (f'Completed (no file changes). Result: {result_file}', now, item_id),
                )
                summary = output[:800] if len(output) > 800 else output
                self._post_update(item_id, item,
                    f'Task complete, Chief. No code changes needed.\n\nSummary:\n{summary}',
                    item.get('assigned_to', '86'))

            conn.commit()
            conn.close()

            socketio.emit('task_execution_complete', {
                'item_id': item_id,
                'title': item.get('title', ''),
                'success': True,
            })

            # Notify
            try:
                from max.services.notification import notify
                notify('Max — Task Complete', item.get('title', '')[:50], subtitle=f'{model} agent')
            except Exception:
                pass

        except Exception as e:
            self._post_update(item_id, item,
                f'Sorry about that, Chief. Hit an error: {e}',
                item.get('assigned_to', '86'))

            socketio.emit('task_execution_complete', {
                'item_id': item_id,
                'success': False,
                'message': str(e),
            })

    def _post_update(self, item_id, item, content, author):
        """Post to inbox, Discord, and audit trail — non-blocking."""
        def _post():
            try:
                from max.services.inbox import inbox_service
                inbox_service.add_comment(item_id, content, author=author)
            except Exception:
                pass
            try:
                from max.services.audit import audit_service
                audit_service.log(author, 'task_update', 'task', item_id,
                    project_id=item.get('project_id', ''), detail=content[:200])
            except Exception:
                pass
            try:
                from max.services.analytics import analytics_service
                analytics_service.track('task_update', project_id=item.get('project_id', ''),
                    model=item.get('assigned_to', ''))
            except Exception:
                pass
        threading.Thread(target=_post, daemon=True).start()

    def _build_prompt(self, item):
        parts = [
            f'You are Agent 86, working on a task assigned by the Chief via CONTROL.',
            f'',
            f'TASK: {item.get("title", "")}',
            f'CATEGORY: {item.get("category", "")}',
            f'PRIORITY: {item.get("priority", "")}',
        ]
        if item.get('description'):
            parts.append(f'DESCRIPTION: {item["description"]}')
        if item.get('admin_response') and 'Timed out' not in item.get('admin_response', ''):
            parts.append(f'CHIEF\'S NOTES: {item["admin_response"]}')
        parts.extend([
            f'',
            f'PROJECT: {item.get("project_name", "General")}',
            f'',
            f'INSTRUCTIONS:',
            f'1. Read the project\'s CLAUDE.md and understand the codebase',
            f'2. Investigate what needs to be done for this task',
            f'3. Implement the changes',
            f'4. Verify your changes work (run tests if available)',
            f'5. Provide a clear summary of what you did',
            f'',
            f'Work carefully and thoroughly. The Chief is counting on you.',
        ])
        return '\n'.join(parts)

    def _git_commit_and_push(self, item, project_path):
        """Commit changes to an agent branch and push."""
        import re
        slug = re.sub(r'[^a-z0-9-]', '-', item.get('title', 'task')[:40].lower()).strip('-')
        branch = f'agent/{slug}'

        try:
            # Check if there are any changes
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True, text=True, cwd=project_path, timeout=10,
            )
            if not result.stdout.strip():
                return {'committed': False, 'reason': 'No changes'}

            files_changed = len(result.stdout.strip().split('\n'))

            # Get current branch to return to later
            current = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True, text=True, cwd=project_path, timeout=5,
            ).stdout.strip()

            # Create and switch to agent branch
            subprocess.run(
                ['git', 'checkout', '-b', branch],
                capture_output=True, text=True, cwd=project_path, timeout=10,
            )

            # Stage and commit
            subprocess.run(
                ['git', 'add', '-A'],
                capture_output=True, text=True, cwd=project_path, timeout=10,
            )

            commit_msg = f'[Agent 86] {item.get("title", "Task")}\n\n{item.get("description", "")[:200]}'
            result = subprocess.run(
                ['git', 'commit', '-m', commit_msg],
                capture_output=True, text=True, cwd=project_path, timeout=15,
            )

            # Get commit hash
            commit_hash = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                capture_output=True, text=True, cwd=project_path, timeout=5,
            ).stdout.strip()

            # Push
            subprocess.run(
                ['git', 'push', '-u', 'origin', branch],
                capture_output=True, text=True, cwd=project_path, timeout=30,
            )

            # Switch back to original branch
            subprocess.run(
                ['git', 'checkout', current],
                capture_output=True, text=True, cwd=project_path, timeout=10,
            )

            return {
                'committed': True,
                'branch': branch,
                'commit': commit_hash,
                'files_changed': files_changed,
            }

        except Exception as e:
            # If git fails, still mark as done — changes are in the working dir
            return {'committed': False, 'reason': str(e)}

    @staticmethod
    def deploy_to_production(item_id, app):
        """Merge agent branch to main and deploy to server."""
        with app.app_context():
            db_path = app.config['DB_PATH']
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            item = conn.execute(
                '''SELECT fr.*, p.path as project_path, p.slug as project_slug
                   FROM feedback_register fr
                   LEFT JOIN projects p ON fr.project_id = p.id
                   WHERE fr.id = ?''',
                (item_id,),
            ).fetchone()

            if not item or not item['deploy_branch']:
                conn.close()
                return {'success': False, 'error': 'No branch to deploy'}

            item = dict(item)
            project_path = item['project_path']
            branch = item['deploy_branch']

            try:
                # Merge to main
                main_branch = 'main'
                subprocess.run(['git', 'checkout', main_branch],
                    capture_output=True, text=True, cwd=project_path, timeout=10)
                result = subprocess.run(
                    ['git', 'merge', branch, '--no-ff', '-m', f'Merge {branch} — approved by Chief'],
                    capture_output=True, text=True, cwd=project_path, timeout=30,
                )
                if result.returncode != 0:
                    conn.execute(
                        "UPDATE feedback_register SET deploy_status = 'merge_conflict', updated_at = ? WHERE id = ?",
                        (datetime.now().isoformat(), item_id),
                    )
                    conn.commit()
                    conn.close()
                    return {'success': False, 'error': f'Merge conflict: {result.stderr[:200]}'}

                # Push main
                subprocess.run(['git', 'push'],
                    capture_output=True, text=True, cwd=project_path, timeout=30)

                # Update register
                conn.execute(
                    "UPDATE feedback_register SET status = 'completed', deploy_status = 'deployed', updated_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), item_id),
                )
                conn.commit()
                conn.close()

                # Post to inbox
                try:
                    from max.services.inbox import inbox_service
                    inbox_service.add_comment(item_id,
                        f'Deployed to production, Chief. Branch `{branch}` merged to main and pushed.',
                        author='86')
                except Exception:
                    pass

                return {'success': True, 'message': f'Deployed. {branch} merged to main.'}

            except Exception as e:
                conn.close()
                return {'success': False, 'error': str(e)}

    @staticmethod
    def get_diff(item_id, app):
        """Get the git diff for an item's agent branch."""
        with app.app_context():
            db_path = app.config['DB_PATH']
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            item = conn.execute(
                '''SELECT fr.deploy_branch, p.path as project_path
                   FROM feedback_register fr
                   LEFT JOIN projects p ON fr.project_id = p.id
                   WHERE fr.id = ?''',
                (item_id,),
            ).fetchone()
            conn.close()

            if not item or not item['deploy_branch']:
                return None

            try:
                # Get diff between main and the agent branch
                result = subprocess.run(
                    ['git', 'diff', 'main...' + item['deploy_branch']],
                    capture_output=True, text=True, cwd=item['project_path'], timeout=15,
                )

                stat = subprocess.run(
                    ['git', 'diff', '--stat', 'main...' + item['deploy_branch']],
                    capture_output=True, text=True, cwd=item['project_path'], timeout=10,
                )

                return {
                    'diff': result.stdout,
                    'stat': stat.stdout,
                    'branch': item['deploy_branch'],
                }
            except Exception as e:
                return {'error': str(e)}

    def execute_due_items(self):
        """Check for items that are scheduled and due. Queue them sequentially."""
        if not self._app:
            return 0

        with self._app.app_context():
            db_path = self._app.config['DB_PATH']
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            now = datetime.now().isoformat()

            due_items = conn.execute(
                '''SELECT id FROM feedback_register
                   WHERE assigned_to != '' AND assigned_to IS NOT NULL
                   AND scheduled_at != '' AND scheduled_at IS NOT NULL
                   AND scheduled_at <= ?
                   AND status IN ('open', 'planned')''',
                (now,),
            ).fetchall()
            conn.close()

            for item in due_items:
                self.execute_item(item['id'])

            return len(due_items)


# Singleton
task_executor = TaskExecutor()
