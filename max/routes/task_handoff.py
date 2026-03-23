"""Task Handoff API — background agent management."""
from flask import Blueprint, request, jsonify, render_template
from max.services.task_handoff import task_handoff

handoff_bp = Blueprint('handoff', __name__)


@handoff_bp.route('/create', methods=['POST'])
def create():
    """Create a background task."""
    data = request.get_json() or request.form
    prompt = data.get('prompt', '')
    cwd = data.get('cwd', '')
    model = data.get('model', 'sonnet')

    if not prompt:
        return jsonify({'error': 'Need a prompt, Chief.'}), 400

    task = task_handoff.create_task(prompt, cwd=cwd or None, model=model)
    return jsonify(task)


@handoff_bp.route('/status/<task_id>')
def status(task_id):
    """Check task status."""
    task = task_handoff.get_task(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(task)


@handoff_bp.route('/result/<task_id>')
def result(task_id):
    """Get task result."""
    content = task_handoff.get_result(task_id)
    if content is None:
        return jsonify({'error': 'No result yet'}), 404
    return jsonify({'result': content})


@handoff_bp.route('/list')
def list_tasks():
    """List all background tasks."""
    tasks = task_handoff.get_all_tasks()
    return jsonify(tasks)
