"""Telegram Bot — Agent 99's Secure Channel.

"Even Siegfried can't crack this channel."
"""
import asyncio
import threading
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class TelegramBotInstance:
    """A Telegram bot instance for a single project.

    Agent 99's preferred communications method.
    Runs in its own thread with its own event loop.
    """

    def __init__(self, project_id, token, chat_id=None):
        self.project_id = project_id
        self.token = token
        self.chat_id = chat_id
        self.app = None
        self.thread = None
        self.loop = None
        self._running = False

    def start(self):
        self._running = True
        self.thread = threading.Thread(
            target=self._run_bot,
            daemon=True,
            name=f'telegram-{self.project_id[:8]}',
        )
        self.thread.start()

    def stop(self):
        self._running = False
        if self.loop and self.app:
            asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop)

    async def _shutdown(self):
        if self.app:
            try:
                await self.app.stop()
                await self.app.shutdown()
            except Exception:
                pass

    def send_message(self, content):
        """Send a message through Agent 99's channel."""
        if not self.chat_id or not self.app:
            return

        async def _send():
            try:
                await self.app.bot.send_message(chat_id=self.chat_id, text=content)
            except Exception:
                pass

        if self.loop:
            asyncio.run_coroutine_threadsafe(_send(), self.loop)

    def _run_bot(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            from telegram import Update
            from telegram.ext import Application, MessageHandler, CommandHandler, filters

            self.app = Application.builder().token(self.token).build()

            async def handle_message(update: Update, context):
                if not update.message or not update.message.text:
                    return

                # Filter by chat_id if configured
                if self.chat_id and str(update.message.chat_id) != str(self.chat_id):
                    return

                sender = update.message.from_user.username or update.message.from_user.first_name
                content = update.message.text

                # Emit to SocketIO
                socketio.emit('bot_message', {
                    'project_id': self.project_id,
                    'platform': 'telegram',
                    'sender': sender,
                    'content': content,
                })

                # Route to agent
                self._route_to_agent(content, sender)

            async def handle_start(update: Update, context):
                await update.message.reply_text(
                    f"🕵️ {get_quote('comms')}\n\n"
                    f"This is CONTROL's secure Telegram channel.\n"
                    f"Messages sent here will be relayed to Agent 86.\n\n"
                    f"Chat ID: {update.message.chat_id}"
                )

            self.app.add_handler(CommandHandler('start', handle_start))
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

            socketio.emit('bot_event', {
                'project_id': self.project_id,
                'platform': 'telegram',
                'type': 'connected',
                'message': f'Agent 99 is monitoring Telegram. {get_quote("comms")}',
            })

            self.loop.run_until_complete(self.app.run_polling(drop_pending_updates=True))

        except Exception as e:
            socketio.emit('bot_event', {
                'project_id': self.project_id,
                'platform': 'telegram',
                'type': 'error',
                'message': f'Sorry about that, Chief. Telegram error: {e}',
            })
        finally:
            self.loop.close()

    def _route_to_agent(self, content, sender):
        """Route message to the project's agent, or queue it."""
        socketio.emit('bot_message_received', {
            'project_id': self.project_id,
            'platform': 'telegram',
            'sender': sender,
            'content': content,
        })
