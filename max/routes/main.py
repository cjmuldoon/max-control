import subprocess
from flask import Blueprint, render_template, jsonify
from max.models.project import Project
from max.utils.smart_quotes import get_quote

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def launchpad():
    """CONTROL headquarters — the launchpad."""
    projects = Project.get_all()

    # Attach agent status to each project
    for project in projects:
        agent = project.get_agent()
        project.agent_status = agent.status if agent else 'no_agent'

    return render_template(
        'launchpad.html',
        projects=projects,
        quote=get_quote('loading'),
        empty_quote=get_quote('empty'),
    )


@main_bp.route('/system/lid-awake/<action>', methods=['POST'])
def lid_awake(action):
    """Toggle lid-awake: on, off, or status."""
    if action not in ('on', 'off', 'status'):
        return jsonify({'success': False, 'error': 'Invalid action'}), 400
    try:
        result = subprocess.run(
            ['sudo', '/usr/local/bin/lid-awake', action],
            capture_output=True, text=True, timeout=5,
        )
        output = (result.stdout + result.stderr).strip()
        return jsonify({'success': result.returncode == 0, 'output': output, 'action': action})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
