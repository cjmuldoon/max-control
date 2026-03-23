"""SocketIO events for bot communications.

"CONTROL Communications Division — all channels monitored."
"""
from max.extensions import socketio
from flask_socketio import emit


@socketio.on('subscribe_bot')
def handle_subscribe(data):
    """Subscribe to a project's bot messages."""
    project_id = data.get('project_id')
    if project_id:
        from flask_socketio import join_room
        join_room(f'bot_{project_id}')
        emit('bot_subscribed', {'project_id': project_id})
