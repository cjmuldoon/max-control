"""Learning Functions — CONTROL Adaptive Intelligence.

"Would you believe... an agent that learns from its mistakes?"

Analyses past exceptions, error patterns, and task feedback across projects.
Proposes code or config changes based on recurring issues.
Uses Claude CLI to generate actionable improvement proposals.
"""
import os
import json
import uuid
import sqlite3
import subprocess
from datetime import datetime
from collections import Counter
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class LearningService:
    """Adaptive intelligence — learns from past operations.

    "99 always said I should learn from my mistakes. So I do. Eventually."
    """

    def __init__(self):
        self._app = None

    def init_app(self, app):
        self._app = app

    def analyze_and_propose(self, project_id):
        """Analyse past issues for a project and propose improvements.

        Examines:
        1. Recurring error patterns from agent logs
        2. Rejected/completed tasks for patterns
        3. Health check history
        4. Vulnerability scan history

        Then uses Claude to propose actionable fixes.
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

            # Gather intelligence
            intel = self._gather_intelligence(conn, project_id)
            conn.close()

            if not intel['has_data']:
                return {
                    'success': True,
                    'proposals': 0,
                    'message': 'Not enough historical data for analysis yet, Chief. Run some health checks first.',
                }

            # Use Claude to analyse and propose
            proposals = self._generate_proposals(project, intel)

            # Save proposals as tasks
            self._save_proposals(project_id, proposals)

            socketio.emit('learning_complete', {
                'project_id': project_id,
                'project_name': project['name'],
                'proposals': len(proposals),
                'message': f'86 learned {len(proposals)} things. {get_quote("success")}',
            })

            return {
                'success': True,
                'proposals': len(proposals),
                'message': f'{len(proposals)} improvement proposals generated. {get_quote("success")}',
            }

    def analyze_all_projects(self):
        """Run learning analysis across all projects."""
        if not self._app:
            return

        with self._app.app_context():
            db_path = self._app.config['DB_PATH']
            conn = sqlite3.connect(db_path)
            projects = conn.execute('SELECT id FROM projects').fetchall()
            conn.close()

            results = []
            for p in projects:
                result = self.analyze_and_propose(p['id'])
                results.append(result)

            return results

    def _gather_intelligence(self, conn, project_id):
        """Gather historical data for analysis."""
        intel = {'has_data': False}

        # Recent error logs
        error_logs = conn.execute(
            '''SELECT al.message, al.created_at FROM agent_logs al
               JOIN agents a ON al.agent_id = a.id
               WHERE a.project_id = ? AND al.level = 'error'
               ORDER BY al.created_at DESC LIMIT 50''',
            (project_id,),
        ).fetchall()
        intel['error_logs'] = [dict(r) for r in error_logs]

        # Completed tasks (what's been fixed before)
        completed = conn.execute(
            '''SELECT title, description, resolution, type FROM tasks
               WHERE project_id = ? AND status = 'completed'
               ORDER BY updated_at DESC LIMIT 30''',
            (project_id,),
        ).fetchall()
        intel['completed_tasks'] = [dict(r) for r in completed]

        # Rejected tasks (what was deemed not worth doing)
        rejected = conn.execute(
            '''SELECT title, description, user_notes, type FROM tasks
               WHERE project_id = ? AND status = 'rejected'
               ORDER BY updated_at DESC LIMIT 20''',
            (project_id,),
        ).fetchall()
        intel['rejected_tasks'] = [dict(r) for r in rejected]

        # Recurring health check findings
        health_tasks = conn.execute(
            '''SELECT title, description, COUNT(*) as occurrences FROM tasks
               WHERE project_id = ? AND source = 'health_check'
               GROUP BY title ORDER BY occurrences DESC LIMIT 10''',
            (project_id,),
        ).fetchall()
        intel['recurring_health'] = [dict(r) for r in health_tasks]

        # Vulnerability findings
        vuln_tasks = conn.execute(
            '''SELECT title, description FROM tasks
               WHERE project_id = ? AND source = 'vuln_scan'
               ORDER BY created_at DESC LIMIT 10''',
            (project_id,),
        ).fetchall()
        intel['vuln_findings'] = [dict(r) for r in vuln_tasks]

        intel['has_data'] = bool(
            error_logs or completed or health_tasks or vuln_tasks
        )

        return intel

    def _generate_proposals(self, project, intel):
        """Use Claude to generate improvement proposals from intelligence."""
        cli_path = self._app.config['CLAUDE_CLI_PATH']
        if not os.path.exists(cli_path):
            return self._fallback_proposals(intel)

        # Build analysis prompt
        prompt = f"""Analyse the following operational intelligence for the project "{project['name']}" and propose specific, actionable improvements.

PROJECT: {project['name']}
PATH: {project['path']}
DESCRIPTION: {project.get('description', 'N/A')}

RECURRING HEALTH CHECK FINDINGS:
{json.dumps(intel['recurring_health'], indent=2)}

ERROR LOG PATTERNS:
{json.dumps(intel['error_logs'][:10], indent=2)}

PREVIOUSLY COMPLETED FIXES:
{json.dumps(intel['completed_tasks'][:10], indent=2)}

VULNERABILITY FINDINGS:
{json.dumps(intel['vuln_findings'][:5], indent=2)}

Based on this data, provide 3-5 specific improvement proposals. For each, provide:
1. A concise title
2. What the issue is
3. The proposed fix (specific code changes or config updates)
4. Priority (high/medium/low)

Format as JSON array: [{{"title": "...", "description": "...", "priority": "high|medium|low"}}]
Only output the JSON array, nothing else."""

        try:
            result = subprocess.run(
                [cli_path, '--print', '--model', 'haiku', '-p', prompt],
                capture_output=True, text=True, timeout=60,
                cwd=project['path'] if os.path.isdir(project['path']) else None,
            )

            output = result.stdout.strip()
            # Extract JSON from output
            if '[' in output:
                json_start = output.index('[')
                json_end = output.rindex(']') + 1
                proposals = json.loads(output[json_start:json_end])
                return proposals

        except Exception:
            pass

        return self._fallback_proposals(intel)

    def _fallback_proposals(self, intel):
        """Generate proposals without Claude (pattern-based fallback)."""
        proposals = []

        # Check recurring health issues
        for item in intel.get('recurring_health', []):
            if item.get('occurrences', 0) >= 2:
                proposals.append({
                    'title': f'Recurring: {item["title"]}',
                    'description': f'This finding has occurred {item["occurrences"]} times. '
                                   f'{item.get("description", "")} Consider a permanent fix.',
                    'priority': 'medium',
                })

        # Check error patterns
        if intel.get('error_logs'):
            error_msgs = [e['message'] for e in intel['error_logs']]
            common = Counter(error_msgs).most_common(3)
            for msg, count in common:
                if count >= 3:
                    proposals.append({
                        'title': f'Recurring error ({count}x)',
                        'description': f'Error seen {count} times: {msg[:200]}',
                        'priority': 'high' if count >= 5 else 'medium',
                    })

        # Check unresolved vulns
        for vuln in intel.get('vuln_findings', []):
            if 'vulnerabilities' in vuln.get('title', '').lower():
                proposals.append({
                    'title': f'Unresolved: {vuln["title"]}',
                    'description': vuln.get('description', ''),
                    'priority': 'high',
                })

        return proposals[:5]

    def _save_proposals(self, project_id, proposals):
        """Save learning proposals as tasks."""
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        now = datetime.utcnow().isoformat()

        for proposal in proposals:
            task_id = str(uuid.uuid4())
            priority_map = {'high': 2, 'medium': 1, 'low': 0}
            priority = priority_map.get(proposal.get('priority', 'low'), 0)

            conn.execute(
                '''INSERT INTO tasks (id, project_id, title, description, type, status, source, priority, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'improvement', 'proposed', 'learning', ?, ?, ?)''',
                (task_id, project_id,
                 proposal.get('title', 'Improvement proposal'),
                 proposal.get('description', ''),
                 priority, now, now),
            )

        conn.commit()
        conn.close()


# Singleton
learning_service = LearningService()
