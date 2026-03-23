from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from max.models.project import Project
from max.models.bot_config import BotConfig
from max.services.bot_manager import bot_manager
from max.services.message_queue import message_queue
from max.utils.smart_quotes import get_quote

bots_bp = Blueprint('bots', __name__)


@bots_bp.route('/')
def index():
    """CONTROL Communications Division."""
    projects = Project.get_all()
    bot_statuses = bot_manager.get_status()

    # Build a map of project -> bot configs
    project_bots = {}
    for project in projects:
        configs = BotConfig.get_by_project(project.id)
        queue_count = message_queue.get_undelivered_count(project.id)
        project_bots[project.id] = {
            'project': project,
            'configs': configs,
            'queue_count': queue_count,
            'discord_running': bot_manager.is_running(project.id, 'discord'),
            'telegram_running': bot_manager.is_running(project.id, 'telegram'),
        }

    return render_template(
        'bots.html',
        projects=projects,
        project_bots=project_bots,
        quote=get_quote('comms'),
    )


@bots_bp.route('/configure/<project_id>', methods=['POST'])
def configure(project_id):
    """Configure a bot for a project — enter the Cone of Silence."""
    project = Project.get_by_id(project_id)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('bots.index'))

    platform = request.form.get('platform', '')
    token = request.form.get('token', '').strip()
    channel_id = request.form.get('channel_id', '').strip()

    if not platform or not token:
        flash('Sorry about that, Chief. Need a platform and token.', 'error')
        return redirect(url_for('bots.index'))

    # Create or update config
    existing = BotConfig.get_by_project_platform(project_id, platform)
    if existing:
        existing.update(token=token, channel_id=channel_id)
        flash(f'{platform.title()} configuration updated. {get_quote("success")}', 'success')
    else:
        BotConfig.create(project_id, platform, token, channel_id)
        flash(f'{platform.title()} channel configured. {get_quote("success")}', 'success')

    return redirect(url_for('bots.index'))


@bots_bp.route('/toggle/<project_id>/<platform>', methods=['POST'])
def toggle(project_id, platform):
    """Toggle a bot on or off — flip the shoe phone switch."""
    project = Project.get_by_id(project_id)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('bots.index'))

    config = BotConfig.get_by_project_platform(project_id, platform)
    if not config:
        flash(f'No {platform} configuration found. Configure it first, Chief.', 'error')
        return redirect(url_for('bots.index'))

    if bot_manager.is_running(project_id, platform):
        bot_manager.stop_bot(project_id, platform)
        config.set_enabled(False)
        flash(f'{platform.title()} channel closed. {get_quote("agent_stop")}', 'success')
    else:
        try:
            bot_manager.start_bot(project_id, platform, config.token, config.channel_id)
            config.set_enabled(True)
            flash(f'{platform.title()} channel opened! {get_quote("comms")}', 'success')
        except Exception as e:
            flash(f'Sorry about that, Chief. {e}', 'error')

    return redirect(url_for('bots.index'))


@bots_bp.route('/messages/<project_id>')
def messages(project_id):
    """Get recent messages for a project — the intelligence feed."""
    recent = message_queue.get_recent(project_id, limit=50)
    return jsonify(recent)
