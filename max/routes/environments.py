"""Environments — Safe Houses & Training Grounds.

"Would you believe... a perfectly isolated regression environment?"
"""
from flask import Blueprint, request, redirect, url_for, flash, jsonify
from max.models.project import Project
from max.services.regression import regression_service
from max.services.test_runner import test_runner
from max.utils.smart_quotes import get_quote

environments_bp = Blueprint('environments', __name__)


@environments_bp.route('/status/<project_id>')
def status(project_id):
    """Get regression status for a project."""
    project = Project.get_by_id(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    status = regression_service.get_status(project.path)
    return jsonify(status)


@environments_bp.route('/create-regression/<project_id>', methods=['POST'])
def create_regression(project_id):
    """Create a new regression branch — enter the Training Ground."""
    project = Project.get_by_id(project_id)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('main.launchpad'))

    name = request.form.get('branch_name', '').strip() or None

    try:
        result = regression_service.create_regression_branch(project.path, name)
        flash(result['message'], 'success')
    except Exception as e:
        flash(f'Sorry about that, Chief. {e}', 'error')

    return redirect(url_for('projects.detail', slug=project.slug))


@environments_bp.route('/switch-regression/<project_id>', methods=['POST'])
def switch_regression(project_id):
    """Switch to a regression branch."""
    project = Project.get_by_id(project_id)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('main.launchpad'))

    branch = request.form.get('branch', '')
    try:
        result = regression_service.switch_to_regression(project.path, branch)
        flash(result['message'], 'success')
    except Exception as e:
        flash(f'Sorry about that, Chief. {e}', 'error')

    return redirect(url_for('projects.detail', slug=project.slug))


@environments_bp.route('/switch-production/<project_id>', methods=['POST'])
def switch_production(project_id):
    """Switch back to production."""
    project = Project.get_by_id(project_id)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('main.launchpad'))

    try:
        result = regression_service.switch_to_production(project.path)
        flash(result['message'], 'success')
    except Exception as e:
        flash(f'Sorry about that, Chief. {e}', 'error')

    return redirect(url_for('projects.detail', slug=project.slug))


@environments_bp.route('/promote/<project_id>', methods=['POST'])
def promote(project_id):
    """Promote regression to production — merge to main."""
    project = Project.get_by_id(project_id)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('main.launchpad'))

    branch = request.form.get('branch', '')
    try:
        result = regression_service.promote_to_production(project.path, branch)
        flash(result['message'], 'success')
    except Exception as e:
        flash(f'Sorry about that, Chief. {e}', 'error')

    return redirect(url_for('projects.detail', slug=project.slug))


@environments_bp.route('/delete-regression/<project_id>', methods=['POST'])
def delete_regression(project_id):
    """Delete a regression branch — scrub the mission."""
    project = Project.get_by_id(project_id)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('main.launchpad'))

    branch = request.form.get('branch', '')
    try:
        result = regression_service.delete_regression_branch(project.path, branch)
        flash(result['message'], 'success')
    except Exception as e:
        flash(f'Sorry about that, Chief. {e}', 'error')

    return redirect(url_for('projects.detail', slug=project.slug))


@environments_bp.route('/run-tests/<project_id>', methods=['POST'])
def run_tests(project_id):
    """Run test suite — CONTROL QA Division."""
    project = Project.get_by_id(project_id)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('main.launchpad'))

    result = test_runner.run_tests(project_id)
    if result['success']:
        flash(f'Tests PASSED! {get_quote("success")}', 'success')
    else:
        flash(f'Tests FAILED. {result.get("error", get_quote("error"))}', 'error')

    return redirect(url_for('projects.detail', slug=project.slug))


@environments_bp.route('/diff/<project_id>')
def diff(project_id):
    """Get diff between regression and main."""
    project = Project.get_by_id(project_id)
    if not project:
        return jsonify({'error': 'Not found'}), 404

    branch = request.args.get('branch')
    diff_text = regression_service.get_diff_from_main(project.path, branch)
    return jsonify({'diff': diff_text})
