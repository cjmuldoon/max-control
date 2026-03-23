"""SocketIO events for persistent multi-terminal management."""
from max.extensions import socketio
from max.services.terminal import terminal_manager
from flask_socketio import emit
from flask import request


@socketio.on('terminal_create')
def handle_create(data):
    """Create a new terminal session."""
    project_path = data.get('project_path')
    label = data.get('label')
    mode = data.get('mode', 'main')
    auto_cmd = data.get('auto_cmd', '')
    session_id = terminal_manager.create_session(project_path, label)
    terminal_manager.subscribe(session_id, request.sid)
    session = terminal_manager.get_session(session_id)
    emit('terminal_created', {
        'session_id': session_id,
        'label': session.label if session else label or 'Terminal',
        'mode': mode,
        'auto_cmd': auto_cmd,
    })


@socketio.on('terminal_subscribe')
def handle_subscribe(data):
    """Reconnect to an existing terminal session."""
    session_id = data.get('session_id')
    if session_id:
        success = terminal_manager.subscribe(session_id, request.sid)
        if success:
            session = terminal_manager.get_session(session_id)
            emit('terminal_subscribed', {
                'session_id': session_id,
                'label': session.label if session else '',
                'message': 'Reconnected to terminal.',
            })
        else:
            emit('terminal_error', {
                'session_id': session_id,
                'message': 'Session not found or dead.',
            })


@socketio.on('terminal_input')
def handle_input(data):
    session_id = data.get('session_id')
    input_data = data.get('data', '')
    if session_id:
        terminal_manager.write(session_id, input_data)


@socketio.on('terminal_resize')
def handle_resize(data):
    session_id = data.get('session_id')
    rows = data.get('rows', 24)
    cols = data.get('cols', 120)
    if session_id:
        terminal_manager.resize(session_id, rows, cols)


@socketio.on('terminal_close')
def handle_close(data):
    session_id = data.get('session_id')
    if session_id:
        terminal_manager.close_session(session_id)
        socketio.emit('terminal_sessions_updated', terminal_manager.list_sessions())


@socketio.on('terminal_list')
def handle_list(data=None):
    """List all active terminal sessions."""
    emit('terminal_sessions_updated', terminal_manager.list_sessions())


@socketio.on('terminal_unsubscribe')
def handle_unsubscribe(data):
    session_id = data.get('session_id')
    if session_id:
        terminal_manager.unsubscribe(session_id, request.sid)


@socketio.on('disconnect')
def handle_disconnect_terminals():
    """Unsubscribe from all terminals on disconnect (but don't kill them)."""
    pass  # Sessions stay alive — they just lose this subscriber
