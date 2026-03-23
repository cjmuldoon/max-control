"""SocketIO events for real-time agent communication."""
from max.extensions import socketio
from flask_socketio import emit


@socketio.on('connect')
def handle_connect():
    emit('connected', {'message': 'CONTROL headquarters online. Welcome, Agent.'})


@socketio.on('disconnect')
def handle_disconnect():
    pass


@socketio.on('subscribe_agent')
def handle_subscribe(data):
    """Subscribe to a specific agent's output stream."""
    agent_id = data.get('agent_id')
    if agent_id:
        from flask_socketio import join_room
        join_room(f'agent_{agent_id}')
        emit('subscribed', {'agent_id': agent_id})


@socketio.on('unsubscribe_agent')
def handle_unsubscribe(data):
    agent_id = data.get('agent_id')
    if agent_id:
        from flask_socketio import leave_room
        leave_room(f'agent_{agent_id}')
