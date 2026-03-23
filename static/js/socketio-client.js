/**
 * Max — SocketIO Client
 * Real-time connection to CONTROL headquarters.
 */

const MaxSocket = {
    socket: null,

    init() {
        this.socket = io();

        this.socket.on('connect', () => {
            this.updateStatus('connected');
        });

        this.socket.on('disconnect', () => {
            this.updateStatus('disconnected');
        });

        this.socket.on('connected', (data) => {
            console.log('Max:', data.message);
        });

        // Agent output events
        this.socket.on('agent_output', (data) => {
            this.handleAgentOutput(data);
        });

        this.socket.on('agent_stopped', (data) => {
            this.handleAgentStopped(data);
        });

        this.socket.on('agent_error', (data) => {
            this.handleAgentError(data);
        });
    },

    updateStatus(status) {
        const el = document.getElementById('connection-status');
        if (!el) return;

        if (status === 'connected') {
            el.className = 'status-badge running';
            el.innerHTML = '<span class="status-dot"></span><span>CONTROL Online</span>';
        } else {
            el.className = 'status-badge error';
            el.innerHTML = '<span class="status-dot"></span><span>Disconnected</span>';
        }
    },

    subscribeAgent(agentId) {
        if (this.socket) {
            this.socket.emit('subscribe_agent', { agent_id: agentId });
        }
    },

    handleAgentOutput(data) {
        const log = document.getElementById('agent-log');
        if (!log) return;

        const entry = document.createElement('div');
        entry.className = 'agent-log-entry';

        const time = new Date(data.timestamp).toLocaleTimeString();
        const content = data.content || data.raw || '';

        entry.innerHTML = `<span class="timestamp">[${time}]</span>${escapeHtml(content)}`;
        log.appendChild(entry);

        // Auto-scroll to bottom
        log.scrollTop = log.scrollHeight;
    },

    handleAgentStopped(data) {
        const log = document.getElementById('agent-log');
        if (!log) return;

        const entry = document.createElement('div');
        entry.className = 'agent-log-entry';
        entry.style.color = 'var(--warning)';
        entry.textContent = `Agent recalled to headquarters. (exit code: ${data.exit_code || 'unknown'})`;
        log.appendChild(entry);
    },

    handleAgentError(data) {
        const log = document.getElementById('agent-log');
        if (!log) return;

        const entry = document.createElement('div');
        entry.className = 'agent-log-entry';
        entry.style.color = 'var(--error)';
        entry.textContent = `Sorry about that, Chief. ${data.error}`;
        log.appendChild(entry);
    }
};

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Smart polling — pause when tab inactive
const SmartPoll = {
    active: true,

    init() {
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.active = false;
                if (MaxSocket.socket) MaxSocket.socket.disconnect();
            } else {
                this.active = true;
                if (MaxSocket.socket) MaxSocket.socket.connect();
            }
        });
    }
};

document.addEventListener('DOMContentLoaded', () => {
    MaxSocket.init();
    SmartPoll.init();
});
