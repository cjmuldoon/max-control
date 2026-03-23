"""Backup — Emergency Protocols.

"Would you believe... a perfectly preserved snapshot?"
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from max.services.backup import backup_service
from max.utils.smart_quotes import get_quote

backup_bp = Blueprint('backup', __name__)


@backup_bp.route('/')
def index():
    """Emergency Protocols — backup management."""
    backups = backup_service.list_backups()
    return render_template('backup.html', backups=backups)


@backup_bp.route('/create', methods=['POST'])
def create():
    """Create a new backup."""
    label = request.form.get('label', '').strip() or None
    try:
        result = backup_service.create_backup(label=label)
        flash(result['message'], 'success')
    except Exception as e:
        flash(f'Sorry about that, Chief. Backup failed: {e}', 'error')

    return redirect(url_for('backup.index'))


@backup_bp.route('/restore/<backup_name>', methods=['POST'])
def restore(backup_name):
    """Restore from backup — careful, Chief."""
    try:
        result = backup_service.restore_backup(backup_name)
        flash(result['message'], 'success')
    except Exception as e:
        flash(f'Sorry about that, Chief. {e}', 'error')

    return redirect(url_for('backup.index'))


@backup_bp.route('/delete/<backup_name>', methods=['POST'])
def delete(backup_name):
    """Delete a backup."""
    try:
        result = backup_service.delete_backup(backup_name)
        flash(result['message'], 'success')
    except Exception as e:
        flash(f'Sorry about that, Chief. {e}', 'error')

    return redirect(url_for('backup.index'))
