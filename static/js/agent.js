/**
 * Max — Agent Controls
 * Real-time agent output streaming and message sending.
 */

document.addEventListener('DOMContentLoaded', () => {
    if (typeof AGENT_ID !== 'undefined' && AGENT_ID) {
        // Subscribe to this agent's output
        MaxSocket.subscribeAgent(AGENT_ID);
    }
});

async function sendAgentMessage(event) {
    event.preventDefault();

    const input = document.getElementById('agent-msg-input');
    const message = input.value.trim();
    if (!message || !AGENT_ID) return;

    // Show sent message in log
    const log = document.getElementById('agent-log');
    const entry = document.createElement('div');
    entry.className = 'agent-log-entry';
    entry.style.color = 'var(--accent)';
    const time = new Date().toLocaleTimeString();
    entry.innerHTML = `<span class="timestamp">[${time}]</span> <strong>You:</strong> ${escapeHtml(message)}`;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;

    input.value = '';

    try {
        const response = await fetch(`/agents/send/${AGENT_ID}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `message=${encodeURIComponent(message)}`
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Failed to send');
        }
    } catch (err) {
        const errEntry = document.createElement('div');
        errEntry.className = 'agent-log-entry';
        errEntry.style.color = 'var(--error)';
        errEntry.textContent = `Missed it by that much! ${err.message}`;
        log.appendChild(errEntry);
    }
}
