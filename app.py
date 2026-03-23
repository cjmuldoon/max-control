import os
import sys
from flask import Flask
from config import Config, DevelopmentConfig
from max.extensions import socketio
from max.db.connection import init_db, get_db
from max.db.migrate import run_migrations


def create_app(config_class=None):
    """Application factory — CONTROL headquarters online."""
    if config_class is None:
        config_class = DevelopmentConfig

    app = Flask(
        __name__,
        static_folder='static',
        template_folder='templates',
    )
    app.config.from_object(config_class)

    # Initialize extensions
    socketio.init_app(app, async_mode=app.config.get('SOCKETIO_ASYNC_MODE', 'eventlet'))

    # Initialize database
    with app.app_context():
        init_db(app)
        run_migrations(app)

    # Register blueprints — CONTROL divisions
    from max.routes.main import main_bp
    from max.routes.projects import projects_bp
    from max.routes.agents import agents_bp
    from max.routes.terminal import terminal_bp
    from max.routes.bots import bots_bp
    from max.routes.tasks import tasks_bp
    from max.routes.schedules import schedules_bp
    from max.routes.analytics import analytics_bp
    from max.routes.environments import environments_bp
    from max.routes.vps import vps_bp
    from max.routes.upload import upload_bp
    from max.routes.agent99_config import agent99_config_bp
    from max.routes.task_handoff import handoff_bp
    from max.routes.feedback import feedback_bp
    from max.routes.api import api_bp
    from max.routes.inbox import inbox_bp
    from max.routes.audit import audit_bp
    from max.routes.backup import backup_bp
    from max.routes.settings import settings_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(agents_bp, url_prefix='/agents')
    app.register_blueprint(terminal_bp, url_prefix='/terminal')
    app.register_blueprint(bots_bp, url_prefix='/bots')
    app.register_blueprint(tasks_bp, url_prefix='/tasks')
    app.register_blueprint(schedules_bp, url_prefix='/schedules')
    app.register_blueprint(analytics_bp, url_prefix='/analytics')
    app.register_blueprint(environments_bp, url_prefix='/environments')
    app.register_blueprint(vps_bp, url_prefix='/vps')
    app.register_blueprint(upload_bp, url_prefix='/upload')
    app.register_blueprint(agent99_config_bp, url_prefix='/agent99')
    app.register_blueprint(handoff_bp, url_prefix='/handoff')
    app.register_blueprint(feedback_bp, url_prefix='/feedback')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(inbox_bp, url_prefix='/inbox')
    app.register_blueprint(audit_bp, url_prefix='/audit')
    app.register_blueprint(backup_bp, url_prefix='/backup')
    app.register_blueprint(settings_bp, url_prefix='/settings')

    # Initialize services
    from max.services.backup import backup_service
    backup_service.init_app(app)

    from max.services.vps import vps_service
    vps_service.init_app(app)

    from max.services.vps_sync import vps_sync_service
    vps_sync_service.init_app(app)

    from max.services.learning import learning_service
    learning_service.init_app(app)

    from max.services.notion_sync import notion_sync_service
    notion_sync_service.init_app(app)

    from max.services.agent99_bot import agent99_bot
    agent99_bot.init_app(app)

    from max.services.task_handoff import task_handoff
    task_handoff.init_app(app)

    from max.services.feedback_register import feedback_register
    feedback_register.init_app(app)

    from max.services.task_executor import task_executor
    task_executor.init_app(app)

    from max.services.inbox import inbox_service
    inbox_service.init_app(app)

    from max.services.audit import audit_service
    audit_service.init_app(app)

    from max.services.analytics import analytics_service
    analytics_service.init_app(app)

    # Register SocketIO events — CONTROL communications
    from max.sockets import agent_events  # noqa: F401
    from max.sockets import terminal_events  # noqa: F401
    from max.sockets import bot_events  # noqa: F401
    from max.sockets import agent99_events  # noqa: F401

    # Initialize Agent 99
    from max.services.agent99 import agent99
    agent99.init_app(app)

    # Context processor — inject Smart theming globally
    @app.context_processor
    def inject_smart_context():
        from max.utils.smart_quotes import get_quote, get_status_label, get_section_name
        from max.services.agent_runner import agent_runner
        from max.services.bot_manager import bot_manager
        from max.models.task import Task
        return {
            'smart_quote': get_quote,
            'get_status_label': get_status_label,
            'get_section_name': get_section_name,
            'running_count': agent_runner.get_running_count(),
            'bot_count': bot_manager.get_running_count(),
            'pending_tasks': Task.get_pending_count(),
            'inbox_unread': inbox_service.get_unread_count(),
            'awaiting_deploy': _get_deploy_count(app.config['DB_PATH']),
        }

    # Clean up orphaned agents on startup
    with app.app_context():
        from max.services.agent_runner import agent_runner
        agent_runner.cleanup_orphans()

    # Teardown
    @app.teardown_appcontext
    def close_db(exception):
        db = get_db()
        if db is not None:
            db.close()

    # Auto-start Discord bot as a SEPARATE PROCESS (avoids eventlet conflicts)
    # Only in the reloader child (WERKZEUG_RUN_MAIN=true) or non-debug mode
    # Discord worker is started from run.py (not here — Flask reloader causes duplicates)

    return app


def _get_deploy_count(db_path):
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM feedback_register WHERE deploy_status = 'awaiting_review'").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def _start_discord_worker(app):
    """Spawn Discord bot as a separate process — outside eventlet."""
    import json as _json
    import subprocess as _sp

    base = os.path.dirname(app.config['DB_PATH'])
    _bot_config_path = os.path.join(base, 'discord_bot_config.json')
    _a99_path = os.path.join(base, 'agent99_bots.json')

    if not os.path.exists(_bot_config_path):
        return

    try:
        with open(_bot_config_path) as _f:
            _bot_config = _json.load(_f)

        _token = _bot_config.get('discord_token', '')
        _channel_map = {v: k for k, v in _bot_config.get('channels', {}).items()}
        _a99_channel = ''

        if os.path.exists(_a99_path):
            with open(_a99_path) as _f:
                _a99 = _json.load(_f)
            _a99_channel = _a99.get('discord', {}).get('channel_id', '')

        if _token:
            _worker = os.path.join(base, 'max', 'services', 'discord_worker.py')
            _proc = _sp.Popen(
                [sys.executable, _worker, _token, _json.dumps(_channel_map), _a99_channel],
                stdout=_sp.PIPE, stderr=_sp.STDOUT,
                cwd=base,
            )
            app._discord_worker = _proc
            print(f'  🤖 Discord bot worker started (PID: {_proc.pid})')
    except Exception as _e:
        print(f'  ⚠️ Discord bot startup failed: {_e}')
