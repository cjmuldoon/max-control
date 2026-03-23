"""Feedback Register — consolidated intelligence from all projects."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from max.models.project import Project
from max.services.feedback_register import feedback_register
from max.utils.smart_quotes import get_quote

feedback_bp = Blueprint('feedback', __name__)


@feedback_bp.route('/')
def index():
    """Consolidated feedback register — all projects, all statuses."""
    # Multi-select status filter (comma-separated)
    status_filter = request.args.getlist('status') or request.args.get('statuses', '').split(',')
    status_filter = [s for s in status_filter if s]
    category_filter = request.args.get('category', '')
    project_filter = request.args.get('project', '')

    items = feedback_register.get_all(
        statuses=status_filter or None,
        category=category_filter or None,
        project_id=project_filter or None,
    )
    stats = feedback_register.get_stats()
    projects = Project.get_all()

    return render_template(
        'feedback_register.html',
        items=items,
        stats=stats,
        projects=projects,
        status_filter=status_filter,
        category_filter=category_filter,
        project_filter=project_filter,
    )


@feedback_bp.route('/sync', methods=['POST'])
def sync():
    result = feedback_register.sync_all()
    flash(result['message'], 'success' if result['success'] else 'error')
    return redirect(url_for('feedback.index'))


@feedback_bp.route('/sync/<project_id>', methods=['POST'])
def sync_project(project_id):
    result = feedback_register.sync_project(project_id)
    flash(result['message'], 'success' if result['success'] else 'error')
    return redirect(url_for('feedback.index'))


@feedback_bp.route('/add', methods=['POST'])
def add():
    project_id = request.form.get('project_id', '')
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    category = request.form.get('category', 'feature_request')
    priority = request.form.get('priority', 'medium')

    if not title:
        flash("Need a title, Chief.", 'error')
        return redirect(url_for('feedback.index'))

    feedback_register.add_item(project_id or None, title, description, category, priority)
    flash(f'Item added to the register. {get_quote("success")}', 'success')
    return redirect(url_for('feedback.index'))


@feedback_bp.route('/update/<item_id>', methods=['POST'])
def update(item_id):
    """Update an item — status, assignment, schedule."""
    status = request.form.get('status', '') or None
    admin_response = request.form.get('admin_response', '').strip() or None
    assigned_to = request.form.get('assigned_to', '') or None
    scheduled_at = request.form.get('scheduled_at', '') or None

    feedback_register.update_item(
        item_id,
        status=status,
        admin_response=admin_response,
        assigned_to=assigned_to,
        scheduled_at=scheduled_at,
    )
    flash(f'Updated. {get_quote("success")}', 'success')
    return redirect(url_for('feedback.index'))


@feedback_bp.route('/deploy/<item_id>', methods=['POST'])
def deploy(item_id):
    """Approve and deploy — merge agent branch to main, push, deploy."""
    from max.services.task_executor import TaskExecutor
    from flask import current_app
    result = TaskExecutor.deploy_to_production(item_id, current_app._get_current_object())
    flash(result.get('message', result.get('error', '')),
          'success' if result.get('success') else 'error')
    return redirect(url_for('feedback.index'))


@feedback_bp.route('/diff/<item_id>')
def diff(item_id):
    """View the diff for an agent's changes."""
    from max.services.task_executor import TaskExecutor
    from flask import current_app
    diff_data = TaskExecutor.get_diff(item_id, current_app._get_current_object())
    return render_template('diff_viewer.html', diff=diff_data, item_id=item_id)


@feedback_bp.route('/execute/<item_id>', methods=['POST'])
def execute(item_id):
    """Launch an agent to work on this item — from the project directory with full context."""
    from max.services.task_executor import task_executor
    result = task_executor.execute_item(item_id)
    flash(result['message'], 'success' if result['success'] else 'error')
    return redirect(url_for('feedback.index'))


@feedback_bp.route('/execute-due', methods=['POST'])
def execute_due():
    """Run all items that are assigned, scheduled, and due."""
    from max.services.task_executor import task_executor
    count = task_executor.execute_due_items()
    flash(f'{count} due tasks launched. {get_quote("success")}', 'success')
    return redirect(url_for('feedback.index'))


@feedback_bp.route('/bulk', methods=['POST'])
def bulk_action():
    """Bulk actions: run, deploy, or run+deploy selected items."""
    from max.services.task_executor import task_executor, TaskExecutor
    from flask import current_app

    item_ids = request.form.getlist('item_ids')
    action = request.form.get('action', '')

    if not item_ids:
        flash("No items selected, Chief.", 'error')
        return redirect(url_for('feedback.index'))

    results = []
    for item_id in item_ids:
        if action == 'run':
            r = task_executor.execute_item(item_id)
            results.append(r.get('message', ''))
        elif action == 'deploy':
            r = TaskExecutor.deploy_to_production(item_id, current_app._get_current_object())
            results.append(r.get('message', r.get('error', '')))
        elif action == 'run_and_deploy':
            # Queue the run — deploy happens automatically after completion now
            r = task_executor.execute_item(item_id)
            # Mark for auto-deploy after completion
            feedback_register.update_item(item_id, status='open')
            import sqlite3
            conn = sqlite3.connect(current_app.config['DB_PATH'])
            conn.execute("UPDATE feedback_register SET deploy_status = 'auto_deploy' WHERE id = ?", (item_id,))
            conn.commit()
            conn.close()
            results.append(f'Queued for run + auto-deploy')

    flash(f'{len(item_ids)} items: {action}. {get_quote("success")}', 'success')
    return redirect(url_for('feedback.index'))


@feedback_bp.route('/api')
def api():
    items = feedback_register.get_all(
        statuses=request.args.get('status', '').split(',') if request.args.get('status') else None,
        category=request.args.get('category'),
        project_id=request.args.get('project'),
    )
    return jsonify(items)
