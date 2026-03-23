"""Audit Trail — full activity log."""
from flask import Blueprint, render_template, request, jsonify
from max.services.audit import audit_service

audit_bp = Blueprint('audit', __name__)


@audit_bp.route('/')
def index():
    actor = request.args.get('actor', '')
    action = request.args.get('action', '')
    project_id = request.args.get('project', '')

    entries = audit_service.get_log(
        actor=actor or None,
        action=action or None,
        project_id=project_id or None,
        limit=200,
    )
    stats = audit_service.get_stats()

    from max.models.project import Project
    projects = Project.get_all()

    return render_template('audit.html', entries=entries, stats=stats,
                           projects=projects, actor_filter=actor,
                           action_filter=action, project_filter=project_id)


@audit_bp.route('/api')
def api():
    entries = audit_service.get_log(
        actor=request.args.get('actor'),
        action=request.args.get('action'),
        project_id=request.args.get('project'),
        limit=int(request.args.get('limit', 100)),
    )
    return jsonify(entries)
