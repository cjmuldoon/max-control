"""VPS — Remote Operations / Satellite Office.

"Would you believe... a fully operational satellite office?"
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from max.models.project import Project
from max.services.vps import vps_service
from max.services.vps_sync import vps_sync_service
from max.utils.smart_quotes import get_quote

vps_bp = Blueprint('vps', __name__)


@vps_bp.route('/')
def index():
    """Satellite Office — VPS management."""
    config = vps_service.get_config()
    projects = Project.get_all()
    remote_status = vps_service.get_remote_status()

    return render_template(
        'vps.html',
        config=config,
        projects=projects,
        remote_status=remote_status,
    )


@vps_bp.route('/configure', methods=['POST'])
def configure():
    """Configure the satellite office connection."""
    host = request.form.get('host', '').strip()
    port = int(request.form.get('port', 22))
    user = request.form.get('user', 'root').strip()
    key_path = request.form.get('key_path', '').strip()
    postgres_dsn = request.form.get('postgres_dsn', '').strip()

    if not host:
        flash('Need a host address for the satellite office, Chief.', 'error')
        return redirect(url_for('vps.index'))

    vps_service.save_config(host, port, user, key_path, postgres_dsn)
    flash(f'Satellite office configured at {host}. {get_quote("success")}', 'success')
    return redirect(url_for('vps.index'))


@vps_bp.route('/test', methods=['POST'])
def test_connection():
    """Test SSH connection to VPS."""
    result = vps_service.test_connection()
    if result['success']:
        flash(f'{result["message"]}\n{result.get("output", "")}', 'success')
    else:
        flash(result['message'], 'error')
    return redirect(url_for('vps.index'))


@vps_bp.route('/setup', methods=['POST'])
def setup():
    """Set up Max remote environment on VPS."""
    try:
        results = vps_service.setup_remote_max()
        output = '\n'.join([f'{r["command"]}: {r["output"] or r["error"]}' for r in results])
        flash(f'Satellite office setup complete. {get_quote("success")}', 'success')
    except Exception as e:
        flash(f'Sorry about that, Chief. Setup failed: {e}', 'error')
    return redirect(url_for('vps.index'))


@vps_bp.route('/deploy/<project_id>', methods=['POST'])
def deploy_remote(project_id):
    """Deploy a research agent to the satellite office."""
    project = Project.get_by_id(project_id)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('vps.index'))

    try:
        result = vps_service.start_remote_agent(project_id, project.github_url)
        flash(f'Research agent deployed to satellite office for {project.name}. {get_quote("agent_start")}', 'success')
    except Exception as e:
        flash(f'Sorry about that, Chief. {e}', 'error')
    return redirect(url_for('vps.index'))


@vps_bp.route('/recall/<project_id>', methods=['POST'])
def recall_remote(project_id):
    """Recall a remote research agent."""
    vps_service.stop_remote_agent(project_id)
    flash(f'Remote agent recalled. {get_quote("agent_stop")}', 'success')
    return redirect(url_for('vps.index'))


@vps_bp.route('/log/<project_id>')
def remote_log(project_id):
    """Fetch remote agent log."""
    log = vps_service.get_remote_agent_log(project_id)
    return jsonify({'log': log or 'No log available.'})


@vps_bp.route('/sync', methods=['POST'])
def sync_now():
    """Trigger immediate sync."""
    result = vps_sync_service.sync_now()
    if result.get('success'):
        flash(f'Sync complete. {result.get("synced", {})}', 'success')
    elif result.get('skipped'):
        flash('Sync not configured. Set up Postgres DSN and enable sync.', 'info')
    else:
        flash(f'Sync failed: {result.get("error", "Unknown")}', 'error')
    return redirect(url_for('vps.index'))


@vps_bp.route('/exec', methods=['POST'])
def exec_command():
    """Execute a command on the VPS."""
    command = request.form.get('command', '').strip()
    if not command:
        return jsonify({'error': 'No command provided'}), 400

    try:
        result = vps_service.exec_command(command, timeout=30)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
