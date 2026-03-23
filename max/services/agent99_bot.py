"""Agent 99 Bot Bridge — Talk to 99 via Discord or Telegram.

"The shoe phone connects directly to 99, Chief."

A dedicated Discord/Telegram bot that routes messages to Agent 99's
persistent session and sends responses back. Unlike project bots
(which route to project agents), this connects to 99 herself.
"""
import asyncio
import threading
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class Agent99BotBridge:
    """Bridges Discord/Telegram to Agent 99."""

    def __init__(self):
        self._discord_bot = None
        self._telegram_bot = None
        self._discord_thread = None
        self._telegram_thread = None
        self._app = None

    def init_app(self, app):
        self._app = app

    def start_discord(self, token, channel_id=None):
        """Start Discord bot connected to 99."""
        if self._discord_bot:
            raise RuntimeError('Discord bot for 99 is already running, Chief.')

        self._discord_thread = threading.Thread(
            target=self._run_discord,
            args=(token, channel_id),
            daemon=True,
            name='agent99-discord',
        )
        self._discord_thread.start()

        socketio.emit('agent99_bot_started', {
            'platform': 'discord',
            'message': '99 is now on Discord. The shoe phone is active, Chief.',
        })

    def start_telegram(self, token, chat_id=None):
        """Start Telegram bot connected to 99."""
        if self._telegram_bot:
            raise RuntimeError('Telegram bot for 99 is already running, Chief.')

        self._telegram_thread = threading.Thread(
            target=self._run_telegram,
            args=(token, chat_id),
            daemon=True,
            name='agent99-telegram',
        )
        self._telegram_thread.start()

        socketio.emit('agent99_bot_started', {
            'platform': 'telegram',
            'message': '99 is now on Telegram. Secure channel active, Chief.',
        })

    def stop_discord(self):
        if self._discord_bot:
            try:
                if self._discord_loop:
                    asyncio.run_coroutine_threadsafe(
                        self._discord_bot.close(), self._discord_loop
                    )
            except Exception:
                pass
            self._discord_bot = None

    def stop_telegram(self):
        if self._telegram_bot:
            try:
                if self._telegram_loop:
                    asyncio.run_coroutine_threadsafe(
                        self._telegram_shutdown(), self._telegram_loop
                    )
            except Exception:
                pass
            self._telegram_bot = None

    async def _telegram_shutdown(self):
        if self._telegram_bot:
            try:
                await self._telegram_bot.stop()
                await self._telegram_bot.shutdown()
            except Exception:
                pass

    def is_discord_running(self):
        return self._discord_bot is not None

    def is_telegram_running(self):
        return self._telegram_bot is not None

    def _send_to_99(self, message, sender, platform):
        """Route a message to Agent 99 and return her response."""
        from max.services.agent99 import agent99

        prefixed = f"[Message from {sender} on {platform}]: {message}"
        result = agent99.send_message(prefixed, page_context=f'{platform} bot')

        response = result.get('response', "Sorry, Chief — I couldn't process that.")

        # Clean ACTION blocks from bot responses
        import re
        response = re.sub(r'ACTION:\s*\{[^}]+\}', '', response).strip()

        # Execute any actions
        action = result.get('action')
        if action:
            try:
                from max.sockets.agent99_events import execute_action
                execute_action(action)
            except Exception:
                pass

        return response

    def _run_discord(self, token, channel_id):
        """Run Discord bot in its own event loop."""
        import discord
        from discord import Intents

        self._discord_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._discord_loop)

        intents = Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)
        self._discord_bot = client

        @client.event
        async def on_ready():
            socketio.emit('agent99_bot_event', {
                'platform': 'discord',
                'message': f'99 online on Discord as {client.user.name}',
            })

        @client.event
        async def on_message(message):
            if message.author == client.user:
                return
            if channel_id and str(message.channel.id) != str(channel_id):
                return

            # Allowlist — disabled temporarily for debugging
            # from max.services.discord_bot import _is_allowed
            # if not _is_allowed(message.author):
            #     return

            sender = str(message.author)
            content = message.content

            # Show typing while 99 thinks
            async with message.channel.typing():
                # Run 99's response in a thread to not block
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, self._send_to_99, content, sender, 'Discord'
                )

            # Split long responses (Discord 2000 char limit)
            for i in range(0, len(response), 1900):
                await message.channel.send(response[i:i+1900])

        try:
            self._discord_loop.run_until_complete(client.start(token))
        except Exception as e:
            socketio.emit('agent99_bot_event', {
                'platform': 'discord',
                'type': 'error',
                'message': f'Discord bot error: {e}',
            })
        finally:
            self._discord_bot = None
            self._discord_loop.close()

    def _run_telegram(self, token, chat_id):
        """Run Telegram bot in its own event loop."""
        self._telegram_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._telegram_loop)

        try:
            from telegram import Update
            from telegram.ext import Application, MessageHandler, CommandHandler, filters

            app = Application.builder().token(token).build()
            self._telegram_bot = app

            async def handle_start(update: Update, context):
                await update.message.reply_text(
                    f"🕵️ Agent 99 reporting, Chief.\n\n"
                    f"This is my secure Telegram line. Send me messages "
                    f"and I'll respond — I have full access to CONTROL operations.\n\n"
                    f"Your Chat ID: {update.message.chat_id}"
                )

            async def handle_message(update: Update, context):
                if not update.message or not update.message.text:
                    return
                if chat_id and str(update.message.chat_id) != str(chat_id):
                    return

                sender = update.message.from_user.username or update.message.from_user.first_name
                content = update.message.text

                # Send typing action
                await update.message.chat.send_action('typing')

                # Get 99's response in a thread
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, self._send_to_99, content, sender, 'Telegram'
                )

                # Split long responses (Telegram 4096 char limit)
                for i in range(0, len(response), 4000):
                    await update.message.reply_text(response[i:i+4000])

            app.add_handler(CommandHandler('start', handle_start))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

            socketio.emit('agent99_bot_event', {
                'platform': 'telegram',
                'message': '99 is monitoring Telegram.',
            })

            self._telegram_loop.run_until_complete(app.run_polling(drop_pending_updates=True))

        except Exception as e:
            socketio.emit('agent99_bot_event', {
                'platform': 'telegram',
                'type': 'error',
                'message': f'Telegram bot error: {e}',
            })
        finally:
            self._telegram_bot = None
            self._telegram_loop.close()


# Singleton
agent99_bot = Agent99BotBridge()
