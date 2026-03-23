"""SocketIO events for Agent 99 — the persistent assistant.

"99, I need your help."

Now backed by a persistent Claude CLI session with full tool access.
"""
from max.extensions import socketio
from max.services.agent99 import agent99
from flask_socketio import emit


@socketio.on('agent99_message')
def handle_message(data):
    """Send a message to Agent 99 — runs in a background thread."""
    import threading

    message = data.get('message', '').strip()
    if not message:
        return

    page_context = data.get('page_context', '')

    emit('agent99_thinking', {'message': '99 is on it, Chief...'})

    def _run():
        result = agent99.send_message(message, page_context=page_context)
        socketio.emit('agent99_response', {
            'response': result.get('response', ''),
            'action': result.get('action'),
            'error': result.get('error', False),
        })
        action = result.get('action')
        if action:
            execute_action(action)

    threading.Thread(target=_run, daemon=True).start()


@socketio.on('agent99_clear')
def handle_clear(data=None):
    """Clear 99's session and start fresh."""
    agent99.clear_conversation()
    emit('agent99_cleared', {'message': 'Fresh briefing, Chief. What do you need?'})


@socketio.on('agent99_history')
def handle_history(data=None):
    """Get 99's conversation history."""
    conversation = agent99.get_conversation()
    emit('agent99_history', {'conversation': conversation})


@socketio.on('agent99_status')
def handle_status(data=None):
    """Check if 99's session is running."""
    emit('agent99_status', {
        'running': agent99.is_running(),
        'session_id': agent99._session_id,
    })


def execute_action(action):
    """Execute an action parsed from 99's response."""
    action_type = action.get('type')

    try:
        if action_type == 'schedule':
            _execute_schedule(action)
        elif action_type == 'health_check':
            _execute_health_check(action)
        elif action_type == 'vuln_scan':
            _execute_vuln_scan(action)

        socketio.emit('agent99_action_complete', {
            'action': action,
            'success': True,
            'message': 'Done, Chief. 86 handled it.',
        })
    except Exception as e:
        socketio.emit('agent99_action_complete', {
            'action': action,
            'success': False,
            'message': f'Sorry about that, Chief. {e}',
        })


def _execute_schedule(action):
    from flask import current_app
    import sqlite3, uuid

    app = current_app._get_current_object()
    db_path = app.config['DB_PATH']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    project_filter = action.get('project', 'all')
    task_type = action.get('task_type', 'health_check')
    cron = action.get('cron', '0 18 * * *')
    name = action.get('name', f'{task_type} schedule')

    if project_filter == 'all':
        projects = conn.execute('SELECT * FROM projects').fetchall()
    else:
        projects = conn.execute(
            'SELECT * FROM projects WHERE name LIKE ?', (f'%{project_filter}%',),
        ).fetchall()

    for project in projects:
        sched_id = str(uuid.uuid4())
        conn.execute(
            '''INSERT INTO schedules (id, project_id, name, cron_expression, task_type, enabled)
               VALUES (?, ?, ?, ?, ?, 1)''',
            (sched_id, project['id'], f"{name} — {project['name']}", cron, task_type),
        )

    conn.commit()
    conn.close()


def _execute_health_check(action):
    from flask import current_app
    import sqlite3

    app = current_app._get_current_object()
    db_path = app.config['DB_PATH']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    project_filter = action.get('project', 'all')
    if project_filter == 'all':
        projects = conn.execute('SELECT * FROM projects').fetchall()
    else:
        projects = conn.execute(
            'SELECT * FROM projects WHERE name LIKE ?', (f'%{project_filter}%',),
        ).fetchall()
    conn.close()

    from max.services.health_checker import health_checker
    for project in projects:
        health_checker.run_check(project['id'])


def _execute_vuln_scan(action):
    from flask import current_app
    import sqlite3

    app = current_app._get_current_object()
    db_path = app.config['DB_PATH']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    project_filter = action.get('project', 'all')
    if project_filter == 'all':
        projects = conn.execute('SELECT * FROM projects').fetchall()
    else:
        projects = conn.execute(
            'SELECT * FROM projects WHERE name LIKE ?', (f'%{project_filter}%',),
        ).fetchall()
    conn.close()

    from max.services.vuln_scanner import vuln_scanner
    for project in projects:
        vuln_scanner.run_scan(project['id'])
