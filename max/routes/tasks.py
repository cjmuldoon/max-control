"""Tasks — Mission Briefings.

"Don't tell me, let me guess — another impossible mission?"
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from max.models.task import Task
from max.models.project import Project
from max.utils.smart_quotes import get_quote

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('/')
def index():
    """Mission Briefings — the approval queue."""
    status_filter = request.args.get('status', '')
    type_filter = request.args.get('type', '')
    project_filter = request.args.get('project', '')

    # Build query
    tasks = Task.get_all(
        status=status_filter or None,
        type_filter=type_filter or None,
        limit=200,
    )

    # Filter by project if specified
    if project_filter:
        tasks = [t for t in tasks if t.project_id == project_filter]

    # Build project name lookup
    projects = Project.get_all()
    project_map = {p.id: p for p in projects}

    # Attach project info to tasks
    for task in tasks:
        task.project = project_map.get(task.project_id)

    stats = Task.get_stats()

    return render_template(
        'tasks.html',
        tasks=tasks,
        projects=projects,
        project_map=project_map,
        stats=stats,
        status_filter=status_filter,
        type_filter=type_filter,
        project_filter=project_filter,
        quote=get_quote('loading'),
    )


@tasks_bp.route('/approve/<task_id>', methods=['POST'])
def approve(task_id):
    """Approve a mission proposal — 'Good work, 86.'"""
    task = Task.get_by_id(task_id)
    if not task:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('tasks.index'))

    notes = request.form.get('notes', '').strip()
    task.approve(notes=notes)
    flash(f'Mission approved. {get_quote("success")}', 'success')
    return redirect(url_for('tasks.index'))


@tasks_bp.route('/reject/<task_id>', methods=['POST'])
def reject(task_id):
    """Reject a mission proposal — 'Not this time, 86.'"""
    task = Task.get_by_id(task_id)
    if not task:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('tasks.index'))

    notes = request.form.get('notes', '').strip()
    task.reject(notes=notes)
    flash(f'Mission rejected. {get_quote("agent_stop")}', 'success')
    return redirect(url_for('tasks.index'))


@tasks_bp.route('/complete/<task_id>', methods=['POST'])
def complete(task_id):
    """Mark mission as complete."""
    task = Task.get_by_id(task_id)
    if not task:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('tasks.index'))

    resolution = request.form.get('resolution', '').strip()
    task.complete(resolution=resolution)
    flash(f'Mission complete! {get_quote("success")}', 'success')
    return redirect(url_for('tasks.index'))


@tasks_bp.route('/run-health/<project_id>', methods=['POST'])
def run_health(project_id):
    """Run CONTROL Medical health check on a project."""
    project = Project.get_by_id(project_id)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('tasks.index'))

    from max.services.health_checker import health_checker
    health_checker.run_check(project_id)
    flash(f'CONTROL Medical has examined {project.name}. {get_quote("health_check")}', 'success')
    return redirect(url_for('tasks.index'))


@tasks_bp.route('/run-vuln/<project_id>', methods=['POST'])
def run_vuln(project_id):
    """Run Counter-KAOS vulnerability scan on a project."""
    project = Project.get_by_id(project_id)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('tasks.index'))

    from max.services.vuln_scanner import vuln_scanner
    vuln_scanner.run_scan(project_id)
    flash(f'Counter-KAOS sweep complete on {project.name}. {get_quote("health_check")}', 'success')
    return redirect(url_for('tasks.index'))
