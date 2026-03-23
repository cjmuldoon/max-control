"""Scheduler Service — CONTROL Mission Schedule.

"The old 'run it on a timer' trick. Works every time."

Wraps APScheduler to run cron jobs loaded from the schedules DB table.
"""
import uuid
import sqlite3
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from max.extensions import socketio


class SchedulerService:
    """Manages scheduled tasks — CONTROL's mission planner."""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self._app = None

    def init_app(self, app):
        """Initialize with Flask app context."""
        self._app = app
        self.scheduler.start()
        self._load_schedules()

    def _load_schedules(self):
        """Load all enabled schedules from DB on startup."""
        if not self._app:
            return

        with self._app.app_context():
            db_path = self._app.config['DB_PATH']
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM schedules WHERE enabled = 1"
            ).fetchall()
            conn.close()

            for row in rows:
                self._register_job(dict(row))

    def _register_job(self, schedule):
        """Register a single cron job."""
        job_id = f"schedule_{schedule['id']}"

        # Remove existing if any
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        try:
            trigger = CronTrigger.from_crontab(schedule['cron_expression'])
            self.scheduler.add_job(
                self._execute_task,
                trigger=trigger,
                id=job_id,
                args=[schedule],
                replace_existing=True,
            )
        except Exception as e:
            print(f'  ✗ Failed to register schedule {schedule["name"]}: {e}')

    def _execute_task(self, schedule):
        """Execute a scheduled task — the mission begins."""
        if not self._app:
            return

        with self._app.app_context():
            task_type = schedule['task_type']
            project_id = schedule['project_id']

            # Update last_run_at
            db_path = self._app.config['DB_PATH']
            conn = sqlite3.connect(db_path)
            now = datetime.utcnow().isoformat()
            conn.execute(
                'UPDATE schedules SET last_run_at = ? WHERE id = ?',
                (now, schedule['id']),
            )
            conn.commit()
            conn.close()

            # Dispatch based on task type
            if task_type == 'health_check':
                from max.services.health_checker import health_checker
                health_checker.run_check(project_id)
            elif task_type == 'vuln_scan':
                from max.services.vuln_scanner import vuln_scanner
                vuln_scanner.run_scan(project_id)
            else:
                # Custom task — emit event for handling
                socketio.emit('schedule_fired', {
                    'schedule_id': schedule['id'],
                    'project_id': project_id,
                    'task_type': task_type,
                    'timestamp': now,
                })

    def add_schedule(self, schedule_dict):
        """Add a new schedule and register the cron job."""
        self._register_job(schedule_dict)

    def remove_schedule(self, schedule_id):
        """Remove a schedule's cron job."""
        job_id = f"schedule_{schedule_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

    def get_jobs(self):
        """List all active jobs."""
        return [
            {
                'id': job.id,
                'next_run': str(job.next_run_time) if job.next_run_time else None,
                'trigger': str(job.trigger),
            }
            for job in self.scheduler.get_jobs()
        ]

    def shutdown(self):
        self.scheduler.shutdown(wait=False)


# Singleton
scheduler_service = SchedulerService()
