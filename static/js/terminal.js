/**
 * Max — CONTROL Mainframe Terminal
 * xterm.js + SocketIO PTY bridge.
 * "You are now connected to the CONTROL mainframe. Speak clearly."
 */

let terminal = null;
let fitAddon = null;
let terminalSessionId = null;
let isFullscreen = false;
let resizeObserver = null;

function launchTerminal() {
    const select = document.getElementById('terminal-project');
    const projectPath = select.value;

    const banner = document.getElementById('terminal-banner');
    const container = document.getElementById('terminal-container');

    // Close existing if any
    if (terminal) {
        closeTerminal();
    }

    banner.style.display = 'none';
    container.style.display = 'block';

    // Show extra buttons
    document.getElementById('fullscreen-btn').style.display = '';
    document.getElementById('popout-btn').style.display = '';

    // Get theme colors
    const style = getComputedStyle(document.documentElement);

    terminal = new Terminal({
        cursorBlink: true,
        fontSize: 14,
        fontFamily: "'SF Mono', Monaco, 'Cascadia Code', monospace",
        theme: {
            background: style.getPropertyValue('--terminal-bg').trim(),
            foreground: style.getPropertyValue('--terminal-fg').trim(),
            cursor: '#E8734A',
            cursorAccent: style.getPropertyValue('--terminal-bg').trim(),
            selectionBackground: 'rgba(232, 115, 74, 0.3)',
        },
        allowProposedApi: true,
    });

    fitAddon = new FitAddon.FitAddon();
    terminal.loadAddon(fitAddon);

    terminal.open(container);

    // Small delay to let the DOM settle before fitting
    setTimeout(() => {
        fitAddon.fit();
    }, 100);

    // Request terminal session from server
    MaxSocket.socket.emit('terminal_create', {
        project_path: projectPath || null,
    });

    // Handle terminal output from server
    const outputHandler = (data) => {
        if (data.session_id === terminalSessionId && terminal) {
            terminal.write(data.data);
        }
    };

    const createdHandler = (data) => {
        terminalSessionId = data.session_id;
    };

    const closedHandler = (data) => {
        if (data.session_id === terminalSessionId && terminal) {
            terminal.writeln(`\r\n  \x1b[33m${data.message}\x1b[0m`);
            terminal.writeln('  \x1b[2mSession ended. Click Connect to open a new line.\x1b[0m');
        }
    };

    // Remove old listeners first, then add new ones
    MaxSocket.socket.off('terminal_output');
    MaxSocket.socket.off('terminal_created');
    MaxSocket.socket.off('terminal_closed');
    MaxSocket.socket.on('terminal_output', outputHandler);
    MaxSocket.socket.on('terminal_created', createdHandler);
    MaxSocket.socket.on('terminal_closed', closedHandler);

    // Send input to server
    terminal.onData((data) => {
        if (terminalSessionId) {
            MaxSocket.socket.emit('terminal_input', {
                session_id: terminalSessionId,
                data: data,
            });
        }
    });

    // Handle resize
    if (resizeObserver) resizeObserver.disconnect();
    resizeObserver = new ResizeObserver(() => {
        if (fitAddon && terminal) {
            fitAddon.fit();
            if (terminalSessionId) {
                MaxSocket.socket.emit('terminal_resize', {
                    session_id: terminalSessionId,
                    rows: terminal.rows,
                    cols: terminal.cols,
                });
            }
        }
    });
    resizeObserver.observe(container);

    terminal.focus();
}

function closeTerminal() {
    if (terminalSessionId) {
        MaxSocket.socket.emit('terminal_close', {
            session_id: terminalSessionId,
        });
    }

    if (resizeObserver) {
        resizeObserver.disconnect();
        resizeObserver = null;
    }

    if (terminal) {
        terminal.dispose();
        terminal = null;
    }

    terminalSessionId = null;

    // Exit fullscreen if active
    if (isFullscreen) toggleFullscreen();

    const banner = document.getElementById('terminal-banner');
    const container = document.getElementById('terminal-container');
    banner.style.display = 'block';
    container.style.display = 'none';
    container.innerHTML = '';

    // Hide extra buttons
    document.getElementById('fullscreen-btn').style.display = 'none';
    document.getElementById('popout-btn').style.display = 'none';
}

function toggleFullscreen() {
    const wrapper = document.getElementById('terminal-wrapper');
    isFullscreen = !isFullscreen;
    wrapper.classList.toggle('terminal-fullscreen', isFullscreen);

    const btn = document.getElementById('fullscreen-btn');
    btn.innerHTML = isFullscreen ? '&#x2716; Exit Fullscreen' : '&#x26F6; Fullscreen';

    // Hide/show page elements
    const desc = document.getElementById('terminal-desc');
    const footer = document.getElementById('terminal-footer');
    if (desc) desc.style.display = isFullscreen ? 'none' : '';
    if (footer) footer.style.display = isFullscreen ? 'none' : '';

    // Re-fit after layout change
    setTimeout(() => {
        if (fitAddon && terminal) {
            fitAddon.fit();
            if (terminalSessionId) {
                MaxSocket.socket.emit('terminal_resize', {
                    session_id: terminalSessionId,
                    rows: terminal.rows,
                    cols: terminal.cols,
                });
            }
        }
        if (terminal) terminal.focus();
    }, 200);
}

function popOutTerminal() {
    const select = document.getElementById('terminal-project');
    const projectPath = select.value || '';
    const projectName = select.options[select.selectedIndex]?.text || 'Terminal';

    const params = new URLSearchParams();
    if (projectPath) params.set('path', projectPath);
    params.set('name', projectName);

    const popout = window.open(
        `/terminal/popout?${params.toString()}`,
        'max-terminal',
        'width=900,height=600,menubar=no,toolbar=no,location=no,status=no'
    );

    if (popout) {
        // Close the embedded terminal since we popped out
        closeTerminal();
    }
}

// Escape key exits fullscreen
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isFullscreen) {
        toggleFullscreen();
    }
});
