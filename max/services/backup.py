"""Backup & Restore — Emergency Protocols.

"Would you believe... a perfectly preserved snapshot of CONTROL's database?"

Backs up the Max database and project configurations.
"""
import os
import shutil
import sqlite3
import json
from datetime import datetime
from max.utils.smart_quotes import get_quote


class BackupService:
    """Backup and restore — CONTROL Emergency Protocols."""

    def __init__(self):
        self.backup_dir = None

    def init_app(self, app):
        self.backup_dir = os.path.join(os.path.dirname(app.config['DB_PATH']), 'backups')
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, label=None):
        """Create a backup of the Max database.

        "Activating emergency protocols, Chief."
        """
        from flask import current_app
        db_path = current_app.config['DB_PATH']

        if not self.backup_dir:
            self.backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
            os.makedirs(self.backup_dir, exist_ok=True)

        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        label_slug = f'_{label}' if label else ''
        backup_name = f'max_backup_{timestamp}{label_slug}.db'
        backup_path = os.path.join(self.backup_dir, backup_name)

        # Use SQLite backup API for consistency
        source = sqlite3.connect(db_path)
        dest = sqlite3.connect(backup_path)
        source.backup(dest)
        source.close()
        dest.close()

        size_kb = os.path.getsize(backup_path) / 1024

        return {
            'path': backup_path,
            'name': backup_name,
            'size_kb': round(size_kb, 1),
            'timestamp': timestamp,
            'message': f'Backup created: {backup_name} ({size_kb:.1f} KB). {get_quote("success")}',
        }

    def restore_backup(self, backup_name):
        """Restore from a backup.

        "Careful, Chief. This replaces the current database."
        """
        from flask import current_app
        db_path = current_app.config['DB_PATH']

        if not self.backup_dir:
            self.backup_dir = os.path.join(os.path.dirname(db_path), 'backups')

        backup_path = os.path.join(self.backup_dir, backup_name)
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup not found: {backup_name}. {get_quote('not_found')}")

        # Create a safety backup before restore
        safety = self.create_backup(label='pre_restore')

        # Replace current DB
        shutil.copy2(backup_path, db_path)

        return {
            'restored': backup_name,
            'safety_backup': safety['name'],
            'message': f'Restored from {backup_name}. Safety backup: {safety["name"]}. {get_quote("success")}',
        }

    def list_backups(self):
        """List all available backups."""
        from flask import current_app
        db_path = current_app.config['DB_PATH']

        if not self.backup_dir:
            self.backup_dir = os.path.join(os.path.dirname(db_path), 'backups')

        if not os.path.isdir(self.backup_dir):
            return []

        backups = []
        for f in sorted(os.listdir(self.backup_dir), reverse=True):
            if f.endswith('.db'):
                path = os.path.join(self.backup_dir, f)
                backups.append({
                    'name': f,
                    'size_kb': round(os.path.getsize(path) / 1024, 1),
                    'modified': datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
                })

        return backups

    def delete_backup(self, backup_name):
        """Delete a backup."""
        if not self.backup_dir:
            raise RuntimeError('Backup directory not initialized')

        path = os.path.join(self.backup_dir, backup_name)
        if os.path.exists(path):
            os.remove(path)
            return {'deleted': backup_name, 'message': f'Backup {backup_name} destroyed.'}
        raise FileNotFoundError(f"Backup not found: {backup_name}")

    def cleanup_old_backups(self, keep=10):
        """Keep only the most recent N backups."""
        backups = self.list_backups()
        if len(backups) <= keep:
            return 0

        removed = 0
        for backup in backups[keep:]:
            try:
                os.remove(os.path.join(self.backup_dir, backup['name']))
                removed += 1
            except Exception:
                pass
        return removed


# Singleton
backup_service = BackupService()
