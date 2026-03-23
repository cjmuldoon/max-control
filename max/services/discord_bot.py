"""Discord Bot — Agent 86's Shoe Phone (Discord Edition).

"Would you believe... a secure Discord channel?"
"""
import asyncio
import json
import os
import threading
import discord
from discord import Intents
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class DiscordBotInstance:
    """A Discord bot instance for a single project.

    Runs in its own thread with its own event loop.
    """

    def __init__(self, project_id, token, channel_id=None):
        self.project_id = project_id
        self.token = token
        self.channel_id = channel_id
        self.client = None
        self.thread = None
        self.loop = None
        self._running = False

    def start(self):
        self._running = True
        self.thread = threading.Thread(
            target=self._run_bot,
            daemon=True,
            name=f'discord-{self.project_id[:8]}',
        )
        self.thread.start()

    def stop(self):
        self._running = False
        if self.loop and self.client:
            asyncio.run_coroutine_threadsafe(self.client.close(), self.loop)

    def send_message(self, content):
        """Send a message through the shoe phone."""
        if not self.client or not self.channel_id:
            return

        async def _send():
            channel = self.client.get_channel(int(self.channel_id))
            if channel:
                await channel.send(content)

        if self.loop:
            asyncio.run_coroutine_threadsafe(_send(), self.loop)

    def _run_bot(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        intents = Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)

        @self.client.event
        async def on_ready():
            socketio.emit('bot_event', {
                'project_id': self.project_id,
                'platform': 'discord',
                'type': 'connected',
                'message': f'Agent 86 is online in Discord as {self.client.user.name}. {get_quote("comms")}',
            })

        @self.client.event
        async def on_message(message):
            # Don't respond to our own messages
            if message.author == self.client.user:
                return

            # Only listen in the configured channel
            if self.channel_id and str(message.channel.id) != str(self.channel_id):
                return

            # Allowlist check — disabled temporarily for debugging
            # if not _is_allowed(message.author):
            #     return

            # Emit to SocketIO for real-time UI
            socketio.emit('bot_message', {
                'project_id': self.project_id,
                'platform': 'discord',
                'sender': str(message.author),
                'content': message.content,
                'channel': str(message.channel),
            })

            # Queue the message for the agent
            try:
                from flask import current_app
                from max.services.message_queue import message_queue
                # Need app context for DB access
                # This is handled by the bot route / agent runner
            except Exception:
                pass

            # Route to agent if running
            self._route_to_agent(message.content, str(message.author))

        try:
            self.loop.run_until_complete(self.client.start(self.token))
        except Exception as e:
            socketio.emit('bot_event', {
                'project_id': self.project_id,
                'platform': 'discord',
                'type': 'error',
                'message': f'Sorry about that, Chief. Discord error: {e}',
            })
        finally:
            self.loop.close()

    def _route_to_agent(self, content, sender):
        """Route message to the project's agent, or queue it."""
        from max.services.agent_runner import agent_runner

        socketio.emit('bot_message_received', {
            'project_id': self.project_id,
            'platform': 'discord',
            'sender': sender,
            'content': content,
        })


def _is_allowed(author):
    """Check if a Discord user is on the Chief's allowlist."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'discord_bot_config.json')
    try:
        with open(config_path) as f:
            config = json.load(f)
        allowlist = config.get('allowlist', {})
        usernames = [u.lower() for u in allowlist.get('usernames', [])]
        user_ids = [str(uid) for uid in allowlist.get('user_ids', [])]

        # Check username (case-insensitive)
        if str(author.name).lower() in usernames:
            return True
        if hasattr(author, 'global_name') and author.global_name and author.global_name.lower() in usernames:
            return True
        # Check numeric user ID
        if str(author.id) in user_ids:
            return True

        return False
    except Exception:
        return True  # If config fails, allow (fail open)
