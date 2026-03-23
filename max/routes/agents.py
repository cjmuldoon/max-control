from flask import Blueprint, request, jsonify, redirect, url_for, flash
from max.models.project import Project
from max.models.agent import Agent
from max.services.agent_runner import agent_runner
from max.utils.smart_quotes import get_quote

agents_bp = Blueprint('agents', __name__)


@agents_bp.route('/start/<project_id>', methods=['POST'])
def start(project_id):
    """Deploy Agent 86 to the field."""
    project = Project.get_by_id(project_id)
    if not project:
        flash("Project not found. KAOS interference suspected.", 'error')
        return redirect(url_for('main.launchpad'))

    model = request.form.get('model', 'sonnet')
    permission_mode = request.form.get('permission_mode', 'plan')

    try:
        agent = agent_runner.start_agent(project, model=model, permission_mode=permission_mode)
        flash(f'{get_quote("agent_start")}', 'success')
    except Exception as e:
        flash(f'Sorry about that, Chief. Could not start agent: {e}', 'error')

    return redirect(url_for('projects.detail', slug=project.slug))


@agents_bp.route('/resume/<project_id>', methods=['POST'])
def resume(project_id):
    """Resume Agent 86 from a previous session — 'Would you believe, I remembered exactly where I left off?'"""
    project = Project.get_by_id(project_id)
    if not project:
        flash("Project not found. KAOS interference suspected.", 'error')
        return redirect(url_for('main.launchpad'))

    session_id = request.form.get('session_id', '').strip()
    if not session_id:
        flash("Sorry about that, Chief. No session ID provided.", 'error')
        return redirect(url_for('projects.detail', slug=project.slug))

    model = request.form.get('model', 'opus')
    permission_mode = request.form.get('permission_mode', 'plan')

    try:
        agent = agent_runner.start_agent(project, model=model, permission_mode=permission_mode, resume_session_id=session_id)
        flash(f'Agent resumed from session {session_id[:8]}…', 'success')
    except Exception as e:
        flash(f'Sorry about that, Chief. Could not resume agent: {e}', 'error')

    return redirect(url_for('projects.detail', slug=project.slug))


@agents_bp.route('/update-session/<project_id>', methods=['POST'])
def update_session(project_id):
    """Update the resume session ID for a project."""
    project = Project.get_by_id(project_id)
    if not project:
        flash("Project not found.", 'error')
        return redirect(url_for('main.launchpad'))

    session_id = request.form.get('session_id', '').strip()
    agent = Agent.get_by_project(project_id)

    if agent:
        from max.db.connection import get_db
        db = get_db()
        db.execute('UPDATE agents SET session_id = ? WHERE id = ?', (session_id, agent.id))
        db.commit()
    else:
        Agent.create(project_id=project_id, session_id=session_id)

    flash(f'Session ID updated: {session_id[:20]}...', 'success')
    return redirect(url_for('projects.detail', slug=project.slug))


@agents_bp.route('/stop/<agent_id>', methods=['POST'])
def stop(agent_id):
    """Recall Agent 86 to headquarters."""
    agent = Agent.get_by_id(agent_id)
    if not agent:
        flash("Agent not found.", 'error')
        return redirect(url_for('main.launchpad'))

    project = Project.get_by_id(agent.project_id)

    try:
        agent_runner.stop_agent(agent_id)
        flash(f'{get_quote("agent_stop")}', 'success')
    except Exception as e:
        flash(f'Sorry about that, Chief. {e}', 'error')

    if project:
        return redirect(url_for('projects.detail', slug=project.slug))
    return redirect(url_for('main.launchpad'))


@agents_bp.route('/status/<agent_id>')
def status(agent_id):
    """Get agent status as JSON — for HTMX polling."""
    agent = Agent.get_by_id(agent_id)
    if not agent:
        return jsonify({'error': 'Agent not found'}), 404
    return jsonify(agent.to_dict())


@agents_bp.route('/send/<agent_id>', methods=['POST'])
def send_message(agent_id):
    """Send a message to a running agent."""
    message = request.form.get('message', '').strip()
    if not message:
        return jsonify({'error': 'No message provided'}), 400

    try:
        agent_runner.send_to_agent(agent_id, message)
        return jsonify({'status': 'sent'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
