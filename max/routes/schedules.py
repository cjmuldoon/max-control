"""Schedules — Mission Schedule.

"The old 'run it on a timer' trick."
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from max.models.schedule import Schedule
from max.models.project import Project
from max.services.scheduler import scheduler_service
from max.utils.smart_quotes import get_quote

schedules_bp = Blueprint('schedules', __name__)


@schedules_bp.route('/')
def index():
    """Mission Schedule — all cron jobs."""
    schedules = Schedule.get_all()
    projects = Project.get_all()
    project_map = {p.id: p for p in projects}

    for sched in schedules:
        sched.project = project_map.get(sched.project_id)

    active_jobs = scheduler_service.get_jobs()

    return render_template(
        'schedules.html',
        schedules=schedules,
        projects=projects,
        active_jobs=active_jobs,
        quote=get_quote('loading'),
    )


@schedules_bp.route('/create', methods=['POST'])
def create():
    """Schedule a new recurring mission."""
    project_id = request.form.get('project_id', '')
    name = request.form.get('name', '').strip()
    cron_expression = request.form.get('cron_expression', '').strip()
    task_type = request.form.get('task_type', 'health_check')

    if not project_id or not name or not cron_expression:
        flash("Sorry about that, Chief. Need all mission parameters.", 'error')
        return redirect(url_for('schedules.index'))

    try:
        schedule = Schedule.create(project_id, name, cron_expression, task_type)
        scheduler_service.add_schedule(schedule.to_dict())
        flash(f'Mission "{name}" scheduled. {get_quote("success")}', 'success')
    except Exception as e:
        flash(f'Sorry about that, Chief. {e}', 'error')

    return redirect(url_for('schedules.index'))


@schedules_bp.route('/toggle/<schedule_id>', methods=['POST'])
def toggle(schedule_id):
    """Enable/disable a scheduled mission."""
    schedule = Schedule.get_by_id(schedule_id)
    if not schedule:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('schedules.index'))

    schedule.toggle()

    if schedule.enabled:
        scheduler_service.add_schedule(schedule.to_dict())
        flash(f'Schedule "{schedule.name}" activated. {get_quote("success")}', 'success')
    else:
        scheduler_service.remove_schedule(schedule_id)
        flash(f'Schedule "{schedule.name}" deactivated.', 'success')

    return redirect(url_for('schedules.index'))


@schedules_bp.route('/delete/<schedule_id>', methods=['POST'])
def delete(schedule_id):
    """Delete a scheduled mission."""
    schedule = Schedule.get_by_id(schedule_id)
    if not schedule:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('schedules.index'))

    scheduler_service.remove_schedule(schedule_id)
    schedule.delete()
    flash(f'Schedule removed. {get_quote("agent_stop")}', 'success')
    return redirect(url_for('schedules.index'))
