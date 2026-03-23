#!/usr/bin/env python3
"""Discord Bot Worker — runs as a separate process, outside eventlet.

"The shoe phone operates on its own frequency, Chief."

Handles:
- Agent 99 in #agent-99 (full Claude CLI session)
- Project agents in #assetarc, #mapvs, etc. (Claude CLI per project)
- /help command for available commands
- Slash commands for common operations
"""
import sys
import os
import json
import asyncio
import subprocess
import re
import discord
from discord import Intents

# Config passed as command line args
TOKEN = sys.argv[1] if len(sys.argv) > 1 else ''
CHANNEL_MAP_JSON = sys.argv[2] if len(sys.argv) > 2 else '{}'
AGENT99_CHANNEL = sys.argv[3] if len(sys.argv) > 3 else ''
MAX_URL = sys.argv[4] if len(sys.argv) > 4 else 'http://localhost:8086'

CHANNEL_MAP = json.loads(CHANNEL_MAP_JSON)  # channel_id -> project_slug

# Project paths (loaded from Max DB)
PROJECT_PATHS = {}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_allowed(author):
    """Only the Chief gets through."""
    config_path = os.path.join(os.path.dirname(BASE_DIR), 'discord_bot_config.json')
    try:
        with open(config_path) as f:
            config = json.load(f)
        allowlist = config.get('allowlist', {})
        user_ids = [str(uid) for uid in allowlist.get('user_ids', [])]
        usernames = [u.lower() for u in allowlist.get('usernames', [])]

        if str(author.id) in user_ids:
            return True
        if str(author.name).lower() in usernames:
            return True
        if hasattr(author, 'global_name') and author.global_name and author.global_name.lower() in usernames:
            return True
        return False
    except Exception:
        return True  # Fail open if config missing


def _load_project_paths():
    """Load project paths from Max's database."""
    import sqlite3
    db_path = os.path.join(os.path.dirname(BASE_DIR), 'max.db')
    if not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    for row in conn.execute('SELECT slug, path FROM projects').fetchall():
        PROJECT_PATHS[row['slug']] = row['path']
    conn.close()


# Track pending background tasks so we can deliver results
PENDING_HANDOFFS = {}  # task_id -> channel_id


LOGS_CHANNEL = '1485343011041841213'


def _post_to_logs(message):
    """Post a message to #control-logs."""
    try:
        import urllib.request
        config_path = os.path.join(os.path.dirname(BASE_DIR), 'discord_bot_config.json')
        with open(config_path) as f:
            config = json.load(f)
        token = config.get('discord_token', '')
        if not token:
            return
        payload = json.dumps({'content': message[:1900]}).encode()
        req = urllib.request.Request(
            f'https://discord.com/api/v10/channels/{LOGS_CHANNEL}/messages',
            data=payload,
            headers={'Authorization': f'Bot {token}', 'Content-Type': 'application/json'},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def _run_claude(message, cwd=None, session_name=None, channel_id=None, timeout=120):
    """Run claude CLI. If it times out, hand off to a background worker."""
    cli_path = os.path.expanduser('~/.local/bin/claude')
    project_dir = cwd or os.path.dirname(BASE_DIR)

    # Use subscription, not API credits
    env = os.environ.copy()
    env.pop('ANTHROPIC_API_KEY', None)

    cmd = [
        cli_path, '--print',
        '--model', 'sonnet',
        '--dangerously-skip-permissions',
        '-p', message,
    ]

    if session_name:
        cmd.extend(['--continue', '--name', session_name])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=project_dir, env=env,
        )
        response = result.stdout.strip()
        if not response:
            if result.stderr and 'no session' not in result.stderr.lower():
                return f"Sorry about that, Chief. {result.stderr[:300]}"
            if session_name and '--continue' in cmd:
                cmd.remove('--continue')
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=timeout, cwd=project_dir, env=env,
                )
                response = result.stdout.strip()
            if not response:
                return "I couldn't get a response, Chief. Try again?"

        # Clean ACTION blocks
        response = re.sub(r'ACTION:\s*\{[^}]+\}', '', response).strip()
        return response

    except subprocess.TimeoutExpired:
        # Hand off to background worker — task is too complex for inline
        return _handoff_to_background(message, project_dir, session_name, channel_id)
    except Exception as e:
        return f"Sorry about that, Chief. {e}"


def _handoff_to_background(prompt, cwd, session_name=None, channel_id=None):
    """Spawn a background Claude process for a task that timed out."""
    import uuid
    task_id = uuid.uuid4().hex[:8]
    results_dir = os.path.join(os.path.dirname(BASE_DIR), 'task_results')
    os.makedirs(results_dir, exist_ok=True)
    result_file = os.path.join(results_dir, f'{task_id}.md')

    cli_path = os.path.expanduser('~/.local/bin/claude')
    cmd = [
        cli_path, '--print', '--model', 'sonnet',
        '--dangerously-skip-permissions', '-p', prompt,
    ]

    def _run():
        _post_to_logs(f'📋 Background task `{task_id}` started')
        try:
            henv = os.environ.copy()
            henv.pop('ANTHROPIC_API_KEY', None)
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=henv)
            output = result.stdout or 'No output'
            with open(result_file, 'w') as f:
                f.write(output)
            _post_to_logs(f'✅ Background task `{task_id}` complete ({len(output)} chars)')
        except Exception as e:
            with open(result_file, 'w') as f:
                f.write(f'Error: {e}')

        # Store for delivery
        PENDING_HANDOFFS[task_id] = {
            'result_file': result_file,
            'completed': True,
        }

    import threading
    threading.Thread(target=_run, daemon=True, name=f'handoff-{task_id}').start()

    PENDING_HANDOFFS[task_id] = {'result_file': result_file, 'completed': False, 'channel_id': channel_id}

    return (
        f"This one's going to take a bit, Chief. I've handed it off to 86 — "
        f"he's working on it in the background (task `{task_id}`).\n\n"
        f"I'll send the results here when he's done. "
        f"Or check with `/task {task_id}`."
    )


HELP_TEXT = """🕵️ **CONTROL Command Reference**

**In #agent-99:**
Talk naturally — 99 has full access to all projects, tools, and CONTROL operations.

**In project channels (#assetarc, #mapvs, etc.):**
Messages go to that project's agent with full codebase context.

**Commands (any channel):**
`/help` — This message
`/status` — Current CONTROL status (agents, projects, tasks)
`/health <project>` — Run health check on a project
`/scan <project>` — Run vulnerability scan
`/projects` — List all registered projects

**Examples:**
• "Check the feedback board for open bugs"
• "What's the git status?"
• "Add a margin-top to the header in index.html"
• "Run the tests"
• "Schedule a health check for 6pm daily"

The agents have full CLI access — anything you'd do in a terminal, they can do.
"""


async def handle_command(message, content):
    """Handle /commands."""
    parts = content.strip().split(None, 1)
    cmd = parts[0].lower()

    if cmd == '/help':
        await message.channel.send(HELP_TEXT)
        return True

    if cmd == '/status':
        import sqlite3
        db_path = os.path.join(os.path.dirname(BASE_DIR), 'max.db')
        conn = sqlite3.connect(db_path)
        projects = conn.execute('SELECT COUNT(*) FROM projects').fetchone()[0]
        agents = conn.execute("SELECT COUNT(*) FROM agents WHERE status='running'").fetchone()[0]
        tasks = conn.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('pending','proposed')").fetchone()[0]
        conn.close()
        await message.channel.send(
            f"📊 **CONTROL Status**\n"
            f"• **{projects}** projects registered\n"
            f"• **{agents}** agents in the field\n"
            f"• **{tasks}** pending mission briefings"
        )
        return True

    if cmd == '/task':
        task_id = parts[1] if len(parts) > 1 else ''
        if not task_id:
            await message.channel.send("Usage: `/task <task_id>` — check a background task result.")
            return True
        info = PENDING_HANDOFFS.get(task_id)
        if not info:
            await message.channel.send(f"No task `{task_id}` found, Chief.")
            return True
        if not info.get('completed'):
            await message.channel.send(f"Task `{task_id}` is still running, Chief. 86 is on it.")
            return True
        try:
            with open(info['result_file']) as f:
                result = f.read()
            for i in range(0, len(result), 1900):
                await message.channel.send(result[i:i+1900])
        except Exception as e:
            await message.channel.send(f"Couldn't read result: {e}")
        return True

    if cmd == '/projects':
        import sqlite3
        db_path = os.path.join(os.path.dirname(BASE_DIR), 'max.db')
        conn = sqlite3.connect(db_path)
        rows = conn.execute('SELECT name, slug, status FROM projects ORDER BY name').fetchall()
        conn.close()
        lines = [f"• **{r[0]}** (`{r[1]}`) — {r[2]}" for r in rows]
        await message.channel.send("📋 **Registered Operations**\n" + '\n'.join(lines))
        return True

    return False


async def main():
    _load_project_paths()

    intents = Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f'[Max Discord] Connected as {client.user}')
        print(f'[Max Discord] Channels: {CHANNEL_MAP}')
        if AGENT99_CHANNEL:
            print(f'[Max Discord] Agent 99: {AGENT99_CHANNEL}')

        # Background loop: deliver handoff results back to channels
        async def delivery_loop():
            while True:
                await asyncio.sleep(5)
                for task_id, info in list(PENDING_HANDOFFS.items()):
                    if info.get('completed') and not info.get('delivered') and info.get('channel_id'):
                        try:
                            channel = client.get_channel(int(info['channel_id']))
                            if channel:
                                with open(info['result_file']) as f:
                                    result = f.read()
                                header = f"✅ **Task `{task_id}` complete, Chief.** Here are the results:\n\n"
                                full = header + result
                                for i in range(0, len(full), 1900):
                                    await channel.send(full[i:i+1900])
                                info['delivered'] = True
                        except Exception as e:
                            print(f'[Delivery] Failed for {task_id}: {e}')
                            info['delivered'] = True  # Don't retry forever

        client.loop.create_task(delivery_loop())

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return

        # Allowlist — only the Chief
        if not _is_allowed(message.author):
            return

        channel_id = str(message.channel.id)
        sender = str(message.author)
        content = message.content or ''

        # Handle attachments — download and reference in the message
        attachment_paths = []
        if message.attachments:
            upload_dir = os.path.join(os.path.dirname(BASE_DIR), 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            for att in message.attachments:
                try:
                    ext = os.path.splitext(att.filename)[1] or '.bin'
                    safe_name = f'{att.id}{ext}'
                    local_path = os.path.join(upload_dir, safe_name)
                    await att.save(local_path)
                    attachment_paths.append((att.filename, local_path))
                    print(f'[Attachment] Saved {att.filename} -> {local_path}')
                except Exception as e:
                    print(f'[Attachment] Failed to save {att.filename}: {e}')

        if attachment_paths:
            att_text = '\n'.join([f'[Attached: {name} at {path}]' for name, path in attachment_paths])
            content = f'{att_text}\n\n{content}' if content else att_text

        if not content:
            return

        # Handle /commands in any channel
        if content.startswith('/'):
            handled = await handle_command(message, content)
            if handled:
                return

        # Agent 99 channel
        if channel_id == AGENT99_CHANNEL:
            print(f'[99] {sender}: {content}')
            ninety_nine_prompt = (
                f'You are Agent 99 from Get Smart, messaging via Discord. '
                f'The user is "Chief". Your partner Max (Agent 86) is right next to you — '
                f'you sometimes reference him ("86 is looking into that", "I told Max to handle it"). '
                f'You\'re the competent one. Be confident, wry, professional. '
                f'You can read files, run commands, access all CONTROL operations.\n\n'
                f'Chief says: {content}'
            )
            async with message.channel.typing():
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, _run_claude,
                    ninety_nine_prompt,
                    os.path.dirname(BASE_DIR),
                    'Agent-99',
                    channel_id,
                    180,  # 3 min timeout for 99 — she has a big system prompt
                )
            for i in range(0, len(response), 1900):
                await message.channel.send(response[i:i+1900])
            return

        # Project channels
        if channel_id in CHANNEL_MAP:
            project_slug = CHANNEL_MAP[channel_id]
            project_path = PROJECT_PATHS.get(project_slug)
            print(f'[{project_slug}] {sender}: {content}')

            if project_path and os.path.isdir(project_path):
                # Add project context on first message
                project_prompt = (
                    f'You are Maxwell Smart, Agent 86 from Get Smart. You work for CONTROL. '
                    f'The user is "Chief" — always address them that way. '
                    f'You are confident, enthusiastic, sometimes bumbling but ultimately competent. '
                    f'Use catchphrases naturally: "Would you believe...", "Missed it by that much!", '
                    f'"Sorry about that, Chief", "And loving it!", "The old [X] trick". '
                    f'Your partner Agent 99 is nearby — she\'s the smart one and you know it, '
                    f'but you\'d never admit it. You\'re working on the {project_slug} project.\n\n'
                    f'You have full access to read/write files, run commands, check git, run tests. '
                    f'The project is at {project_path}. '
                    f'This project has a feedback system at /feedback/ for bug/feature tracking. '
                    f'Keep responses concise but in character.\n\n'
                    f'Chief says: {content}'
                )
                async with message.channel.typing():
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None, _run_claude,
                        project_prompt,
                        project_path,
                        f'Max-{project_slug}',
                        channel_id,
                    )
                for i in range(0, len(response), 1900):
                    await message.channel.send(response[i:i+1900])
            else:
                await message.channel.send(
                    f"📁 Can't find project path for **{project_slug}**, Chief. "
                    f"Check the project config in Max."
                )
            return

    await client.start(TOKEN)


if __name__ == '__main__':
    if not TOKEN:
        print('No token provided')
        sys.exit(1)
    asyncio.run(main())
