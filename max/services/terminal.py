"""Terminal Manager — Persistent multi-terminal management.

"CONTROL Mainframe — multiple secure lines, all monitored."

Terminal sessions persist server-side. Navigate away, come back,
reconnect to the same session. Multiple terminals open simultaneously.
Each labelled by project or custom name.
"""
import os
import pty
import select
import subprocess
import struct
import fcntl
import termios
import signal
import threading
import uuid
from datetime import datetime
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class TerminalSession:
    """A persistent PTY terminal session."""

    def __init__(self, session_id, cwd=None, label=None):
        self.session_id = session_id
        self.cwd = cwd or os.path.expanduser('~')
        self.label = label or os.path.basename(self.cwd)
        self.master_fd = None
        self.slave_fd = None
        self.process = None
        self.alive = False
        self.created_at = datetime.utcnow().isoformat()
        self.scrollback = []  # Keep last N lines for reconnection
        self.max_scrollback = 500
        self._subscribers = set()  # SIDs currently watching this terminal

    def start(self):
        """Spawn a shell with a PTY."""
        shell = os.environ.get('SHELL', '/bin/zsh')
        env = os.environ.copy()
        env['TERM'] = 'xterm-256color'

        self.master_fd, self.slave_fd = pty.openpty()
        self._set_size(24, 120)

        self.process = subprocess.Popen(
            [shell, '-l'],
            stdin=self.slave_fd,
            stdout=self.slave_fd,
            stderr=self.slave_fd,
            cwd=self.cwd,
            env=env,
            preexec_fn=os.setsid,
            close_fds=True,
        )

        os.close(self.slave_fd)
        self.slave_fd = None
        self.alive = True

        reader = threading.Thread(
            target=self._read_loop,
            daemon=True,
            name=f'pty-{self.session_id[:8]}',
        )
        reader.start()

    def subscribe(self, sid):
        """Add a SocketIO client as a subscriber."""
        self._subscribers.add(sid)
        # Send scrollback to new subscriber
        if self.scrollback:
            try:
                socketio.emit('terminal_output', {
                    'session_id': self.session_id,
                    'data': ''.join(self.scrollback),
                }, to=sid, namespace='/')
            except Exception:
                pass

    def unsubscribe(self, sid):
        self._subscribers.discard(sid)

    def write(self, data):
        if self.master_fd is not None and self.alive:
            try:
                os.write(self.master_fd, data.encode('utf-8') if isinstance(data, str) else data)
            except OSError:
                self.alive = False

    def resize(self, rows, cols):
        if self.master_fd is not None and self.alive:
            self._set_size(rows, cols)

    def stop(self):
        self.alive = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None

    def _set_size(self, rows, cols):
        try:
            fd = self.master_fd if self.master_fd is not None else self.slave_fd
            if fd is not None:
                winsize = struct.pack('HHHH', rows, cols, 0, 0)
                fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
        except Exception:
            pass

    def _read_loop(self):
        """Read from PTY. Uses eventlet-safe emit."""
        try:
            while self.alive:
                try:
                    ready, _, _ = select.select([self.master_fd], [], [], 0.1)
                    if ready:
                        data = os.read(self.master_fd, 4096)
                        if data:
                            decoded = data.decode('utf-8', errors='replace')
                            self.scrollback.append(decoded)
                            if len(self.scrollback) > self.max_scrollback:
                                self.scrollback = self.scrollback[-self.max_scrollback:]
                            # Use server.emit directly — works from any thread
                            try:
                                socketio.emit('terminal_output', {
                                    'session_id': self.session_id,
                                    'data': decoded,
                                })
                            except Exception:
                                pass
                        else:
                            break
                except (OSError, ValueError):
                    break
        except Exception:
            pass
        finally:
            self.alive = False
            try:
                socketio.emit('terminal_closed', {
                    'session_id': self.session_id,
                    'message': get_quote('agent_stop'),
                })
            except Exception:
                pass

    def to_dict(self):
        return {
            'session_id': self.session_id,
            'label': self.label,
            'cwd': self.cwd,
            'alive': self.alive,
            'created_at': self.created_at,
            'pid': self.process.pid if self.process else None,
            'subscribers': len(self._subscribers),
        }


class TerminalManager:
    """Manages multiple persistent terminal sessions.

    Sessions survive page navigation. Clients reconnect on return.
    """

    def __init__(self):
        self._sessions = {}
        self._lock = threading.Lock()

    def create_session(self, project_path=None, label=None):
        session_id = str(uuid.uuid4())
        cwd = project_path if project_path and os.path.isdir(project_path) else os.path.expanduser('~')
        if not label:
            label = os.path.basename(cwd) if cwd != os.path.expanduser('~') else 'Home'
        session = TerminalSession(session_id, cwd=cwd, label=label)
        session.start()
        with self._lock:
            self._sessions[session_id] = session
        return session_id

    def get_session(self, session_id):
        with self._lock:
            return self._sessions.get(session_id)

    def subscribe(self, session_id, sid):
        """Subscribe a SocketIO client to a terminal's output."""
        session = self.get_session(session_id)
        if session and session.alive:
            session.subscribe(sid)
            return True
        return False

    def unsubscribe(self, session_id, sid):
        session = self.get_session(session_id)
        if session:
            session.unsubscribe(sid)

    def write(self, session_id, data):
        session = self.get_session(session_id)
        if session:
            session.write(data)

    def resize(self, session_id, rows, cols):
        session = self.get_session(session_id)
        if session:
            session.resize(rows, cols)

    def close_session(self, session_id):
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            session.stop()

    def list_sessions(self):
        """List all active sessions."""
        with self._lock:
            return [s.to_dict() for s in self._sessions.values() if s.alive]

    def get_active_count(self):
        with self._lock:
            return sum(1 for s in self._sessions.values() if s.alive)

    def close_all(self):
        with self._lock:
            for session in self._sessions.values():
                session.stop()
            self._sessions.clear()


terminal_manager = TerminalManager()
