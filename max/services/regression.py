"""Regression Environment — The Training Ground.

"Would you believe... a perfectly isolated test environment?"

Each project can have a regression environment — a separate git branch
where changes are applied and tested before promotion to production.

Supports the "check prod but fix in regression" workflow:
1. Agent inspects production (main branch)
2. Creates/switches to regression branch
3. Applies fix in regression
4. Runs test suite
5. If tests pass, user confirms promotion (merge to main)
"""
import os
import subprocess
import uuid
import sqlite3
from datetime import datetime
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class RegressionService:
    """Regression environment management — CONTROL's Training Ground."""

    REGRESSION_BRANCH_PREFIX = 'regression/'

    def get_status(self, project_path):
        """Get the regression status for a project."""
        if not self._is_git_repo(project_path):
            return {'available': False, 'reason': 'Not a git repository'}

        current_branch = self._get_current_branch(project_path)
        is_regression = current_branch.startswith(self.REGRESSION_BRANCH_PREFIX) if current_branch else False
        regression_branches = self._list_regression_branches(project_path)
        main_branch = self._get_main_branch(project_path)

        return {
            'available': True,
            'current_branch': current_branch,
            'main_branch': main_branch,
            'is_on_regression': is_regression,
            'regression_branches': regression_branches,
            'has_uncommitted': self._has_uncommitted_changes(project_path),
        }

    def create_regression_branch(self, project_path, name=None):
        """Create a new regression branch from main.

        "Entering the Training Ground, Chief."
        """
        if not self._is_git_repo(project_path):
            raise RuntimeError("Not a git repository. Can't create a training ground without version control.")

        main_branch = self._get_main_branch(project_path)
        branch_name = f"{self.REGRESSION_BRANCH_PREFIX}{name or datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        # Ensure we're on main and up to date
        result = subprocess.run(
            ['git', 'checkout', main_branch],
            cwd=project_path, capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Couldn't switch to {main_branch}: {result.stderr.strip()}")

        # Create and switch to regression branch
        result = subprocess.run(
            ['git', 'checkout', '-b', branch_name],
            cwd=project_path, capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Couldn't create branch: {result.stderr.strip()}")

        return {
            'branch': branch_name,
            'from': main_branch,
            'message': f'Training ground "{branch_name}" created from {main_branch}. {get_quote("success")}',
        }

    def switch_to_regression(self, project_path, branch_name):
        """Switch to an existing regression branch."""
        result = subprocess.run(
            ['git', 'checkout', branch_name],
            cwd=project_path, capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Couldn't switch to {branch_name}: {result.stderr.strip()}")

        return {'branch': branch_name, 'message': f'Switched to training ground: {branch_name}'}

    def switch_to_production(self, project_path):
        """Switch back to the main (production) branch."""
        main_branch = self._get_main_branch(project_path)
        result = subprocess.run(
            ['git', 'checkout', main_branch],
            cwd=project_path, capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Couldn't return to production: {result.stderr.strip()}")

        return {'branch': main_branch, 'message': f'Back in production ({main_branch}). Careful out there, 86.'}

    def promote_to_production(self, project_path, regression_branch):
        """Merge regression branch into main — promote to production.

        "Mission accomplished, Chief. Promoting to production."
        """
        main_branch = self._get_main_branch(project_path)

        # Switch to main
        result = subprocess.run(
            ['git', 'checkout', main_branch],
            cwd=project_path, capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Couldn't switch to {main_branch}: {result.stderr.strip()}")

        # Merge regression branch
        result = subprocess.run(
            ['git', 'merge', regression_branch, '--no-ff', '-m',
             f'Promote {regression_branch} to production — approved by CONTROL'],
            cwd=project_path, capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Merge failed: {result.stderr.strip()}. KAOS interference suspected.")

        return {
            'merged': regression_branch,
            'into': main_branch,
            'message': f'{get_quote("success")} Changes promoted from {regression_branch} to {main_branch}.',
        }

    def get_diff_from_main(self, project_path, regression_branch=None):
        """Get the diff between regression and main."""
        main_branch = self._get_main_branch(project_path)
        branch = regression_branch or self._get_current_branch(project_path)

        result = subprocess.run(
            ['git', 'diff', '--stat', f'{main_branch}...{branch}'],
            cwd=project_path, capture_output=True, text=True, timeout=15,
        )
        return result.stdout.strip()

    def delete_regression_branch(self, project_path, branch_name):
        """Delete a regression branch — mission scrubbed."""
        main_branch = self._get_main_branch(project_path)

        # Switch to main first
        subprocess.run(
            ['git', 'checkout', main_branch],
            cwd=project_path, capture_output=True, text=True, timeout=15,
        )

        result = subprocess.run(
            ['git', 'branch', '-D', branch_name],
            cwd=project_path, capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Couldn't delete branch: {result.stderr.strip()}")

        return {'deleted': branch_name, 'message': f'Training ground "{branch_name}" demolished.'}

    # --- Private helpers ---

    def _is_git_repo(self, path):
        return os.path.isdir(os.path.join(path, '.git'))

    def _get_current_branch(self, path):
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=path, capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def _get_main_branch(self, path):
        """Detect whether the project uses 'main' or 'master'."""
        result = subprocess.run(
            ['git', 'branch', '--list', 'main'],
            cwd=path, capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip():
            return 'main'

        result = subprocess.run(
            ['git', 'branch', '--list', 'master'],
            cwd=path, capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip():
            return 'master'

        return 'main'  # Default

    def _list_regression_branches(self, path):
        result = subprocess.run(
            ['git', 'branch', '--list', f'{self.REGRESSION_BRANCH_PREFIX}*'],
            cwd=path, capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return []
        return [b.strip().lstrip('* ') for b in result.stdout.strip().split('\n') if b.strip()]

    def _has_uncommitted_changes(self, path):
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=path, capture_output=True, text=True, timeout=10,
        )
        return bool(result.stdout.strip())


# Singleton
regression_service = RegressionService()
