"""Task Handoff — 99 delegates complex work to background agents.

"I'll hand this off to 86, Chief. He'll work on it in the background."

When 99 detects a task is too complex for a single --print call,
she spawns a background Claude CLI process that runs autonomously.
The process runs with full permissions, reports results to a file,
and Max notifies the Chief when it's done.
"""
import os
import json
import uuid
import subprocess
import threading
from datetime import datetime
from max.extensions import socketio


class TaskHandoff:
    """Manages background task workers — 86 in the field."""

    def __init__(self):
        self._tasks = {}  # task_id -> task info
        self._app = None

    def init_app(self, app):
        self._app = app

    def create_task(self, prompt, cwd=None, model='sonnet', requested_by='99'):
        """Spawn a background Claude process for a complex task.

        Returns a task_id that can be checked for status/results.
        """
        task_id = str(uuid.uuid4())[:8]
        base = os.path.dirname(self._app.config['DB_PATH']) if self._app else '.'
        results_dir = os.path.join(base, 'task_results')
        os.makedirs(results_dir, exist_ok=True)

        result_file = os.path.join(results_dir, f'{task_id}.md')
        log_file = os.path.join(results_dir, f'{task_id}.log')
        work_dir = cwd or base

        cli_path = os.path.expanduser('~/.local/bin/claude')

        cmd = [
            cli_path, '--print',
            '--model', model,
            '--dangerously-skip-permissions',
            '-p', prompt,
        ]

        task_info = {
            'id': task_id,
            'prompt': prompt[:200],
            'model': model,
            'cwd': work_dir,
            'status': 'running',
            'requested_by': requested_by,
            'started_at': datetime.utcnow().isoformat(),
            'result_file': result_file,
            'log_file': log_file,
            'pid': None,
        }

        self._tasks[task_id] = task_info

        # Spawn in a real thread
        thread = threading.Thread(
            target=self._run_task,
            args=(task_id, cmd, work_dir, result_file, log_file),
            daemon=True,
            name=f'task-{task_id}',
        )
        thread.start()

        socketio.emit('task_handoff_started', {
            'task_id': task_id,
            'prompt': prompt[:200],
            'model': model,
            'message': f'86 is on it, Chief. Task {task_id} running in the background.',
        })

        return task_info

    def _run_task(self, task_id, cmd, work_dir, result_file, log_file):
        """Run the background task and capture results."""
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=work_dir,
            )

            self._tasks[task_id]['pid'] = proc.pid

            stdout, stderr = proc.communicate()  # No timeout — run to completion

            # Save results
            with open(result_file, 'w') as f:
                f.write(f'# Task {task_id} Results\n\n')
                f.write(f'**Model:** {self._tasks[task_id]["model"]}\n')
                f.write(f'**Started:** {self._tasks[task_id]["started_at"]}\n')
                f.write(f'**Completed:** {datetime.utcnow().isoformat()}\n')
                f.write(f'**Working Directory:** {work_dir}\n\n')
                f.write(f'## Prompt\n\n{self._tasks[task_id]["prompt"]}\n\n')
                f.write(f'## Result\n\n{stdout}\n')
                if stderr:
                    f.write(f'\n## Errors\n\n{stderr}\n')

            with open(log_file, 'w') as f:
                f.write(stdout)
                if stderr:
                    f.write(f'\n---STDERR---\n{stderr}')

            self._tasks[task_id]['status'] = 'completed'
            self._tasks[task_id]['completed_at'] = datetime.utcnow().isoformat()
            self._tasks[task_id]['exit_code'] = proc.returncode

            socketio.emit('task_handoff_complete', {
                'task_id': task_id,
                'success': proc.returncode == 0,
                'message': f'Task {task_id} complete, Chief. Results ready.',
            })

            # macOS notification
            try:
                from max.services.notification import notify
                notify('Max — Task Complete',
                       f'Background task {task_id} finished.',
                       subtitle=self._tasks[task_id]['prompt'][:50])
            except Exception:
                pass

        except subprocess.TimeoutExpired:
            proc.kill()
            self._tasks[task_id]['status'] = 'timeout'
            socketio.emit('task_handoff_complete', {
                'task_id': task_id,
                'success': False,
                'message': f'Task {task_id} timed out after 10 minutes.',
            })

        except Exception as e:
            self._tasks[task_id]['status'] = 'error'
            self._tasks[task_id]['error'] = str(e)
            socketio.emit('task_handoff_complete', {
                'task_id': task_id,
                'success': False,
                'message': f'Task {task_id} failed: {e}',
            })

    def get_task(self, task_id):
        return self._tasks.get(task_id)

    def get_all_tasks(self):
        return list(self._tasks.values())

    def get_result(self, task_id):
        task = self._tasks.get(task_id)
        if not task:
            return None
        result_file = task.get('result_file')
        if result_file and os.path.exists(result_file):
            with open(result_file) as f:
                return f.read()
        return None


# Singleton
task_handoff = TaskHandoff()
