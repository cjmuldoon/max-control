from flask import Blueprint, render_template, request, jsonify
from max.models.project import Project
from max.services.terminal import terminal_manager
from max.utils.smart_quotes import get_quote

terminal_bp = Blueprint('terminal', __name__)


@terminal_bp.route('/')
def index():
    """CONTROL Mainframe — multi-terminal management hub."""
    projects = Project.get_all()
    sessions = terminal_manager.list_sessions()

    # Get last session ID per project for resume
    from max.models.agent import Agent
    project_sessions = {}
    for p in projects:
        agent = Agent.get_by_project(p.id)
        if agent and agent.session_id:
            project_sessions[p.slug] = agent.session_id

    return render_template(
        'terminal.html',
        projects=projects,
        sessions=sessions,
        project_sessions=project_sessions,
        quote=get_quote('terminal'),
    )


@terminal_bp.route('/popout')
def popout():
    """Pop-out terminal in a dedicated window."""
    project_path = request.args.get('path', '')
    project_name = request.args.get('name', 'Terminal')
    session_id = request.args.get('session', '')

    return render_template(
        'terminal_popout.html',
        project_path=project_path,
        project_name=project_name,
        session_id=session_id,
    )


@terminal_bp.route('/sessions')
def sessions():
    """API: list active terminal sessions."""
    return jsonify(terminal_manager.list_sessions())
