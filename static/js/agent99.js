/**
 * Agent 99 — The Competent One
 * Persistent chat panel available on every page.
 * "Even 86 knows that 99 is the smart one."
 */

const Agent99 = {
    isOpen: false,
    isThinking: false,
    pendingAttachment: null, // {filename, path}

    toggle() {
        const panel = document.getElementById('agent99-panel');
        this.isOpen = !this.isOpen;
        panel.classList.toggle('open', this.isOpen);

        if (this.isOpen) {
            document.getElementById('agent99-input').focus();
            // Load history on first open
            MaxSocket.socket.emit('agent99_history');
        }
    },

    send() {
        const input = document.getElementById('agent99-input');
        const message = input.value.trim();
        if (!message || this.isThinking) return;

        // Show user message
        this.addMessage('user', message);
        input.value = '';

        // Show thinking indicator
        this.isThinking = true;
        this.showThinking();

        // Include attachment path if present
        let fullMessage = message;
        if (this.pendingAttachment) {
            fullMessage = `[Attached file: ${this.pendingAttachment.filename} at ${this.pendingAttachment.path}]\n\n${message}`;
            this.clearAttachment();
        }

        // Send to server with page context
        MaxSocket.socket.emit('agent99_message', {
            message: fullMessage,
            page_context: (document.querySelector('.topbar-title')?.textContent || document.title) + ' — ' + window.location.pathname,
        });
    },

    addMessage(role, content) {
        const feed = document.getElementById('agent99-feed');
        const msg = document.createElement('div');
        msg.className = `agent99-msg agent99-msg-${role}`;

        const label = role === 'user'
            ? '<img src="/static/img/maxwell-smart.svg" style="width:14px;height:14px;border-radius:50%;vertical-align:middle;margin-right:3px;">Chief'
            : '<img src="/static/img/agent99.svg" style="width:14px;height:14px;border-radius:50%;vertical-align:middle;margin-right:3px;">99';
        // Clean ACTION: blocks from display
        let displayContent = content.replace(/ACTION:\s*\{[^}]+\}/g, '').trim();

        msg.innerHTML = `
            <div class="agent99-msg-header">${label}</div>
            <div class="agent99-msg-body">${this.escapeHtml(displayContent)}</div>
        `;
        feed.appendChild(msg);
        feed.scrollTop = feed.scrollHeight;
    },

    showThinking() {
        const feed = document.getElementById('agent99-feed');
        let thinking = document.getElementById('agent99-thinking');
        if (!thinking) {
            thinking = document.createElement('div');
            thinking.id = 'agent99-thinking';
            thinking.className = 'agent99-msg agent99-msg-assistant';
            thinking.innerHTML = `
                <div class="agent99-msg-header">👩 99</div>
                <div class="agent99-msg-body" style="color: var(--text-muted); font-style: italic;">
                    <span class="spinner" style="width:14px;height:14px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:6px;"></span>
                    Reviewing the intelligence...
                </div>
            `;
        }
        feed.appendChild(thinking);
        feed.scrollTop = feed.scrollHeight;
    },

    hideThinking() {
        const thinking = document.getElementById('agent99-thinking');
        if (thinking) thinking.remove();
        const toolIndicator = document.getElementById('agent99-tool-indicator');
        if (toolIndicator) toolIndicator.remove();
        this.isThinking = false;
    },

    clear() {
        MaxSocket.socket.emit('agent99_clear');
        document.getElementById('agent99-feed').innerHTML = `
            <div class="agent99-msg agent99-msg-assistant">
                <div class="agent99-msg-header">👩 99</div>
                <div class="agent99-msg-body">Conversation cleared. What do you need, Chief?</div>
            </div>
        `;
    },

    showActionResult(data) {
        const feed = document.getElementById('agent99-feed');
        const msg = document.createElement('div');
        msg.className = 'agent99-msg agent99-msg-system';
        msg.innerHTML = `
            <div class="agent99-msg-body" style="color: ${data.success ? 'var(--success)' : 'var(--error)'}; font-size: 12px;">
                ${data.success ? '✅' : '❌'} ${this.escapeHtml(data.message)}
            </div>
        `;
        feed.appendChild(msg);
        feed.scrollTop = feed.scrollHeight;
    },

    async handleFile(input) {
        const file = input.files[0];
        if (!file) return;
        await this.uploadFile(file);
        input.value = '';
    },

    async uploadFile(file) {
        const form = new FormData();
        form.append('file', file);

        try {
            const resp = await fetch('/upload/file', { method: 'POST', body: form });
            const data = await resp.json();
            if (data.path) {
                this.pendingAttachment = { filename: data.filename, path: data.path };
                document.getElementById('agent99-attachments').style.display = 'block';
                document.getElementById('agent99-attachment-name').textContent = `📎 ${data.filename}`;
            }
        } catch (err) {
            console.error('Upload failed:', err);
        }
    },

    clearAttachment() {
        this.pendingAttachment = null;
        document.getElementById('agent99-attachments').style.display = 'none';
        document.getElementById('agent99-attachment-name').textContent = '';
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML.replace(/\n/g, '<br>');
    },

    init() {
        // Listen for 99's responses
        MaxSocket.socket.on('agent99_response', (data) => {
            this.hideThinking();
            this.addMessage('assistant', data.response);
        });

        // Streaming chunks — show tool usage in real time
        MaxSocket.socket.on('agent99_chunk', (data) => {
            if (data.type === 'tool') {
                // Show tool use as a subtle indicator
                const feed = document.getElementById('agent99-feed');
                let toolIndicator = document.getElementById('agent99-tool-indicator');
                if (!toolIndicator) {
                    toolIndicator = document.createElement('div');
                    toolIndicator.id = 'agent99-tool-indicator';
                    toolIndicator.className = 'agent99-msg agent99-msg-system';
                    feed.appendChild(toolIndicator);
                }
                toolIndicator.innerHTML = `<div class="agent99-msg-body" style="font-size:11px; color: var(--text-muted); font-style: italic;">${this.escapeHtml(data.text)}</div>`;
                feed.scrollTop = feed.scrollHeight;
            }
        });

        MaxSocket.socket.on('agent99_thinking', () => {
            // Already showing thinking
        });

        MaxSocket.socket.on('agent99_action_complete', (data) => {
            this.showActionResult(data);
        });

        MaxSocket.socket.on('agent99_history', (data) => {
            const feed = document.getElementById('agent99-feed');
            if (data.conversation && data.conversation.length > 0) {
                // Clear default welcome
                feed.innerHTML = '';
                data.conversation.forEach(msg => {
                    this.addMessage(msg.role, msg.content);
                });
            }
        });

        MaxSocket.socket.on('agent99_cleared', () => {
            // Already handled in clear()
        });

        // Keyboard shortcut: Ctrl+9 to toggle
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === '9') {
                e.preventDefault();
                this.toggle();
            }
        });

        // Enter to send
        document.getElementById('agent99-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.send();
            }
        });

        // Paste screenshots/files (Cmd+V)
        document.getElementById('agent99-panel').addEventListener('paste', async (e) => {
            const items = e.clipboardData?.items;
            if (!items) return;
            for (const item of items) {
                if (item.type.startsWith('image/')) {
                    e.preventDefault();
                    const file = item.getAsFile();
                    if (file) await this.uploadFile(file);
                    break;
                }
            }
        });

        // Drag and drop
        const panel = document.getElementById('agent99-panel');
        panel.addEventListener('dragover', (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; });
        panel.addEventListener('drop', async (e) => {
            e.preventDefault();
            const file = e.dataTransfer.files[0];
            if (file) await this.uploadFile(file);
        });
    }
};

document.addEventListener('DOMContentLoaded', () => {
    Agent99.init();
});
