"""Log Analyzer — CONTROL Intelligence Analysis.

"Hymie is scanning all systems, Chief."

Analyzes project logs for anomalies, error patterns, and trends.
Surfaces findings as tasks.
"""
import os
import re
import uuid
import sqlite3
from datetime import datetime
from collections import Counter
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class LogAnalyzer:
    """Analyzes logs for anomalies — CONTROL Intelligence."""

    # Common error patterns to look for
    ERROR_PATTERNS = [
        (r'(?i)error[:\s]', 'error', 'Error detected'),
        (r'(?i)exception[:\s]', 'error', 'Exception detected'),
        (r'(?i)traceback', 'error', 'Traceback detected'),
        (r'(?i)fatal[:\s]', 'error', 'Fatal error detected'),
        (r'(?i)warning[:\s]', 'warning', 'Warning detected'),
        (r'(?i)deprecat', 'warning', 'Deprecation warning'),
        (r'(?i)timeout', 'warning', 'Timeout detected'),
        (r'(?i)connection refused', 'error', 'Connection refused'),
        (r'(?i)out of memory', 'error', 'Out of memory'),
        (r'(?i)disk full', 'error', 'Disk full'),
        (r'(?i)permission denied', 'error', 'Permission denied'),
        (r'(?i)segmentation fault', 'error', 'Segfault detected'),
    ]

    def analyze_project(self, project_id):
        """Analyze logs for a project."""
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
        findings = []

        # Scan common log locations
        log_dirs = [
            os.path.join(path, 'logs'),
            os.path.join(path, 'log'),
            path,  # Top-level log files
        ]

        log_files = []
        for log_dir in log_dirs:
            if not os.path.isdir(log_dir):
                continue
            for f in os.listdir(log_dir):
                if f.endswith(('.log', '.err', '.out')):
                    log_files.append(os.path.join(log_dir, f))

        if not log_files:
            findings.append({
                'severity': 'info',
                'title': 'No log files found',
                'detail': 'No .log, .err, or .out files found in the project. '
                          'Hymie has nothing to analyse.',
            })
        else:
            for log_file in log_files[:10]:  # Max 10 files
                file_findings = self._analyze_file(log_file)
                findings.extend(file_findings)

        # Also analyze agent logs from DB
        agent_findings = self._analyze_agent_logs(conn, project_id)
        findings.extend(agent_findings)

        # Save findings as tasks
        self._save_findings(conn, project_id, findings)
        conn.close()

        socketio.emit('log_analysis_complete', {
            'project_id': project_id,
            'project_name': project['name'],
            'finding_count': len(findings),
            'message': get_quote('health_check'),
        })

        return {
            'success': True,
            'findings': len(findings),
            'message': f'Hymie found {len(findings)} items in the intelligence. {get_quote("success")}',
        }

    def _analyze_file(self, filepath):
        """Analyze a single log file for patterns."""
        findings = []
        filename = os.path.basename(filepath)

        try:
            # Read last 1000 lines
            with open(filepath, 'r', errors='replace') as f:
                lines = f.readlines()[-1000:]
        except Exception:
            return findings

        error_counts = Counter()
        error_examples = {}

        for line in lines:
            for pattern, severity, label in self.ERROR_PATTERNS:
                if re.search(pattern, line):
                    error_counts[label] += 1
                    if label not in error_examples:
                        error_examples[label] = line.strip()[:200]

        for label, count in error_counts.most_common(5):
            severity = 'error' if count > 10 else 'warning' if count > 3 else 'info'
            findings.append({
                'severity': severity,
                'title': f'{filename}: {label} ({count}x)',
                'detail': f'Found {count} occurrences in {filename}.\nExample: {error_examples.get(label, "")}',
            })

        return findings

    def _analyze_agent_logs(self, conn, project_id):
        """Analyze stored agent logs for the project."""
        findings = []

        # Get recent agent logs
        rows = conn.execute(
            '''SELECT al.* FROM agent_logs al
               JOIN agents a ON al.agent_id = a.id
               WHERE a.project_id = ? AND al.level = 'error'
               ORDER BY al.created_at DESC LIMIT 50''',
            (project_id,),
        ).fetchall()

        if rows:
            findings.append({
                'severity': 'warning',
                'title': f'Agent errors: {len(rows)} recent error logs',
                'detail': f'Agent 86 encountered {len(rows)} errors in recent sessions. '
                          f'Latest: {rows[0]["message"][:200] if rows else "N/A"}',
            })

        return findings

    def _save_findings(self, conn, project_id, findings):
        """Save analysis findings as tasks."""
        now = datetime.utcnow().isoformat()
        for finding in findings:
            task_id = str(uuid.uuid4())
            conn.execute(
                '''INSERT INTO tasks (id, project_id, title, description, type, status, source, priority, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'improvement', 'proposed', 'log_analyzer', ?, ?, ?)''',
                (task_id, project_id, finding['title'], finding['detail'],
                 {'error': 2, 'warning': 1, 'info': 0}.get(finding['severity'], 0),
                 now, now),
            )
        conn.commit()


# Singleton
log_analyzer = LogAnalyzer()
