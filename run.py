#!/usr/bin/env python3
"""
Max — Agent Management Platform
"Would you believe... a fully autonomous multi-agent orchestration platform?"

Named after Maxwell Smart, Agent 86.
"""
import os
import sys
import json
import subprocess
import atexit

from app import create_app, _start_discord_worker
from max.extensions import socketio

app = create_app()

# Track the Discord worker process
_discord_proc = None


def _start_discord():
    """Start the Discord bot worker as a subprocess."""
    global _discord_proc
    base = os.path.dirname(os.path.abspath(__file__))
    bot_config_path = os.path.join(base, 'discord_bot_config.json')
    a99_path = os.path.join(base, 'agent99_bots.json')

    if not os.path.exists(bot_config_path):
        return

    try:
        with open(bot_config_path) as f:
            bot_config = json.load(f)

        token = bot_config.get('discord_token', '')
        channel_map = {v: k for k, v in bot_config.get('channels', {}).items()}
        a99_channel = ''

        if os.path.exists(a99_path):
            with open(a99_path) as f:
                a99 = json.load(f)
            a99_channel = a99.get('discord', {}).get('channel_id', '')

        if token:
            worker = os.path.join(base, 'max', 'services', 'discord_worker.py')
            _discord_proc = subprocess.Popen(
                [sys.executable, worker, token, json.dumps(channel_map), a99_channel],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                cwd=base,
            )
            print(f'  🤖 Discord bot started (PID: {_discord_proc.pid})')
    except Exception as e:
        print(f'  ⚠️ Discord bot failed: {e}')


def _cleanup():
    """Kill Discord worker on exit."""
    global _discord_proc
    if _discord_proc:
        _discord_proc.terminate()
        try:
            _discord_proc.wait(timeout=3)
        except Exception:
            _discord_proc.kill()


if __name__ == '__main__':
    # Kill any leftover workers
    subprocess.run(['pkill', '-f', 'discord_worker.py'], capture_output=True)

    print('\n  🕵️  Max is online. CONTROL headquarters operational.')
    print('  "Would you believe... the world\'s smartest agent manager?"')
    print('  → http://localhost:8086\n')

    _start_discord()
    atexit.register(_cleanup)

    # Task checker disabled — use "Run Due Tasks" button or 🏃 button on dossier
    # to manually trigger tasks. Auto-scheduling was causing rogue agents.
    print('  📋 Task checker: MANUAL mode (use Run Due Tasks button)')

    socketio.run(app, host='0.0.0.0', port=8086, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
