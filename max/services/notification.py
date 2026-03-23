"""macOS Notifications — The Shoe Phone.

"The shoe phone is ringing!"
"""
import subprocess
import platform
from max.utils.smart_quotes import get_quote


def notify(title, message, subtitle=None, sound=True):
    """Send a macOS notification. The shoe phone rings!"""
    if platform.system() != 'Darwin':
        return

    script_parts = [f'display notification "{_escape(message)}"']
    script_parts.append(f'with title "{_escape(title)}"')

    if subtitle:
        script_parts.append(f'subtitle "{_escape(subtitle)}"')

    if sound:
        script_parts.append('sound name "Ping"')

    script = ' '.join(script_parts)

    try:
        subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass


def notify_agent_started(project_name):
    notify(
        'Max — CONTROL',
        get_quote('agent_start'),
        subtitle=f'Project: {project_name}',
    )


def notify_agent_stopped(project_name):
    notify(
        'Max — CONTROL',
        get_quote('agent_stop'),
        subtitle=f'Project: {project_name}',
    )


def notify_bot_message(project_name, platform_name, sender):
    notify(
        f'Max — {get_quote("notification")}',
        f'{sender} sent a message on {platform_name}',
        subtitle=f'Project: {project_name}',
    )


def notify_task_proposed(project_name, task_title):
    notify(
        'Max — Mission Briefing',
        f'Agent 86 proposes: {task_title}',
        subtitle=f'Project: {project_name}',
    )


def notify_health_check(project_name, status):
    notify(
        'Max — CONTROL Medical',
        f'{project_name}: {status}',
    )


def _escape(text):
    """Escape special characters for osascript."""
    return text.replace('"', '\\"').replace('\\', '\\\\')
