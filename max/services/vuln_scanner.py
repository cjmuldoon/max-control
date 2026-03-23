"""Vulnerability Scanner — Counter-KAOS Division.

"KAOS is behind this, I just know it."

Runs npm audit / pip-audit against projects and creates tasks for findings.
"""
import os
import json
import uuid
import sqlite3
import subprocess
from datetime import datetime
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class VulnScanner:
    """Vulnerability scanning — Counter-KAOS operations."""

    def run_scan(self, project_id):
        """Run vulnerability scan on a project."""
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

        # Detect project type and scan accordingly
        if os.path.exists(os.path.join(path, 'package.json')):
            findings.extend(self._scan_npm(path))

        if os.path.exists(os.path.join(path, 'requirements.txt')):
            findings.extend(self._scan_pip(path))

        if not findings:
            findings.append({
                'severity': 'info',
                'title': 'No vulnerabilities detected',
                'detail': 'Counter-KAOS sweep complete. All clear, Chief.',
            })

        self._save_findings(conn, project_id, findings)
        conn.close()

        socketio.emit('vuln_scan_complete', {
            'project_id': project_id,
            'project_name': project['name'],
            'finding_count': len(findings),
            'message': get_quote('health_check'),
        })

    def _scan_npm(self, path):
        """Run npm audit."""
        findings = []
        try:
            result = subprocess.run(
                ['npm', 'audit', '--json'],
                cwd=path, capture_output=True, text=True, timeout=60,
            )
            data = json.loads(result.stdout)

            vuln_count = data.get('metadata', {}).get('vulnerabilities', {})
            total = sum(vuln_count.values()) if isinstance(vuln_count, dict) else 0

            if total > 0:
                severity_summary = ', '.join(f'{k}: {v}' for k, v in vuln_count.items() if v > 0)
                findings.append({
                    'severity': 'warning' if vuln_count.get('critical', 0) == 0 else 'error',
                    'title': f'npm: {total} vulnerabilities found',
                    'detail': f'KAOS infiltration detected! {severity_summary}. Run `npm audit fix` to counter.',
                })
            else:
                findings.append({
                    'severity': 'info',
                    'title': 'npm: No vulnerabilities',
                    'detail': 'npm audit clean. KAOS has not penetrated these dependencies.',
                })

        except FileNotFoundError:
            findings.append({
                'severity': 'info',
                'title': 'npm not available',
                'detail': 'npm is not installed. Cannot scan Node.js dependencies.',
            })
        except json.JSONDecodeError:
            pass
        except subprocess.TimeoutExpired:
            findings.append({
                'severity': 'warning',
                'title': 'npm audit timed out',
                'detail': 'The scan took too long. "Missed it by that much!"',
            })
        except Exception as e:
            findings.append({
                'severity': 'warning',
                'title': 'npm audit failed',
                'detail': f'Sorry about that, Chief. {e}',
            })

        return findings

    def _scan_pip(self, path):
        """Check for known vulnerable Python packages."""
        findings = []
        try:
            # Try pip-audit if available
            result = subprocess.run(
                ['pip-audit', '-r', os.path.join(path, 'requirements.txt'), '--format', 'json'],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if data:
                    findings.append({
                        'severity': 'warning',
                        'title': f'pip-audit: {len(data)} vulnerable packages',
                        'detail': f'KAOS agents found in {len(data)} Python packages.',
                    })
                else:
                    findings.append({
                        'severity': 'info',
                        'title': 'pip-audit: All clear',
                        'detail': 'No known vulnerabilities in Python dependencies.',
                    })
        except FileNotFoundError:
            findings.append({
                'severity': 'info',
                'title': 'pip-audit not available',
                'detail': 'Install pip-audit for Python vulnerability scanning: pip install pip-audit',
            })
        except Exception:
            pass

        return findings

    def _save_findings(self, conn, project_id, findings):
        now = datetime.utcnow().isoformat()
        for finding in findings:
            task_id = str(uuid.uuid4())
            conn.execute(
                '''INSERT INTO tasks (id, project_id, title, description, type, status, source, priority, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'vuln_scan', 'proposed', 'vuln_scan', ?, ?, ?)''',
                (
                    task_id, project_id, finding['title'], finding['detail'],
                    {'error': 2, 'warning': 1, 'info': 0}.get(finding['severity'], 0),
                    now, now,
                ),
            )
        conn.commit()


# Singleton
vuln_scanner = VulnScanner()
