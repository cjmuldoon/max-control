"""Bot Manager — CONTROL Communications Division.

"Larrabee, patch me through!"

Manages Discord and Telegram bot lifecycles per project.
Routes messages to agents or queues them for later.
"""
import threading
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class BotManager:
    """Manages all bot instances across projects.

    "CONTROL Communications Division — all channels monitored."
    """

    def __init__(self):
        self._bots = {}  # (project_id, platform) -> bot instance
        self._lock = threading.Lock()

    def start_bot(self, project_id, platform, token, channel_id=None):
        """Activate a communications channel."""
        key = (project_id, platform)

        with self._lock:
            if key in self._bots:
                raise RuntimeError(f'{platform} bot already running for this project')

        if platform == 'discord':
            from max.services.discord_bot import DiscordBotInstance
            bot = DiscordBotInstance(project_id, token, channel_id)
        elif platform == 'telegram':
            from max.services.telegram_bot import TelegramBotInstance
            bot = TelegramBotInstance(project_id, token, channel_id)
        else:
            raise ValueError(f'Unknown platform: {platform}. KAOS doesn\'t use that.')

        bot.start()

        with self._lock:
            self._bots[key] = bot

        socketio.emit('bot_started', {
            'project_id': project_id,
            'platform': platform,
            'message': get_quote('comms'),
        })

        return bot

    def stop_bot(self, project_id, platform):
        """Close the communications channel."""
        key = (project_id, platform)

        with self._lock:
            bot = self._bots.pop(key, None)

        if bot:
            bot.stop()
            socketio.emit('bot_stopped', {
                'project_id': project_id,
                'platform': platform,
            })

    def send_message(self, project_id, platform, message):
        """Send a message through the shoe phone network."""
        key = (project_id, platform)

        with self._lock:
            bot = self._bots.get(key)

        if not bot:
            raise RuntimeError(f'No {platform} bot running. The shoe phone is off the hook.')

        bot.send_message(message)

    def is_running(self, project_id, platform):
        key = (project_id, platform)
        with self._lock:
            return key in self._bots

    def get_status(self, project_id=None):
        """Get status of all bots, or bots for a specific project."""
        with self._lock:
            statuses = []
            for (pid, platform), bot in self._bots.items():
                if project_id is None or pid == project_id:
                    statuses.append({
                        'project_id': pid,
                        'platform': platform,
                        'running': True,
                    })
            return statuses

    def get_running_count(self):
        with self._lock:
            return len(self._bots)

    def stop_all(self):
        """Emergency shutdown — all channels."""
        with self._lock:
            bots = list(self._bots.values())
            self._bots.clear()

        for bot in bots:
            try:
                bot.stop()
            except Exception:
                pass


# Singleton
bot_manager = BotManager()
