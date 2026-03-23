"""CONTROL Inbox — Agent updates, comments, and notifications.

"86 has filed his report, Chief."

Central notification system. Agents post comments on feedback items.
Comments appear in the ticket thread, the inbox, and Discord.
"""
import os
import json
import uuid
import sqlite3
from datetime import datetime
from max.extensions import socketio


class InboxService:
    """Manages agent comments and the Chief's inbox."""

    def __init__(self):
        self._app = None

    def init_app(self, app):
        self._app = app

    def add_comment(self, item_id, content, author='86', is_agent=True, push_discord=True):
        """Add a comment to a feedback item. Shows in inbox + ticket + Discord."""
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        comment_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        conn.execute(
            '''INSERT INTO feedback_comments (id, item_id, author, content, is_agent, read, created_at)
               VALUES (?, ?, ?, ?, ?, 0, ?)''',
            (comment_id, item_id, author, content, int(is_agent), now),
        )
        conn.commit()

        # Get item details for context
        item = conn.execute(
            '''SELECT fr.*, COALESCE(p.name, 'General') as project_name, COALESCE(p.slug, '') as project_slug
               FROM feedback_register fr
               LEFT JOIN projects p ON fr.project_id = p.id
               WHERE fr.id = ?''',
            (item_id,),
        ).fetchone()
        conn.close()

        item_dict = dict(item) if item else {}

        # Emit to UI
        socketio.emit('inbox_new', {
            'comment_id': comment_id,
            'item_id': item_id,
            'item_title': item_dict.get('title', ''),
            'project': item_dict.get('project_name', ''),
            'author': author,
            'content': content,
            'is_agent': is_agent,
            'created_at': now,
        })

        # Push to Discord
        if push_discord and is_agent:
            self._push_to_discord(item_dict, author, content)

        # macOS notification for agent comments
        if is_agent:
            try:
                from max.services.notification import notify
                notify(
                    f'Max — {author}',
                    content[:100],
                    subtitle=item_dict.get('title', '')[:50],
                )
            except Exception:
                pass

        return comment_id

    def get_comments(self, item_id):
        """Get all comments for a feedback item."""
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            'SELECT * FROM feedback_comments WHERE item_id = ? ORDER BY created_at ASC',
            (item_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_inbox(self, unread_only=False, limit=50):
        """Get inbox — recent agent comments across all items."""
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        query = '''
            SELECT fc.*, fr.title as item_title,
                   COALESCE(p.name, 'General') as project_name,
                   fr.deploy_status, fr.deploy_branch
            FROM feedback_comments fc
            JOIN feedback_register fr ON fc.item_id = fr.id
            LEFT JOIN projects p ON fr.project_id = p.id
        '''
        params = []
        if unread_only:
            query += ' WHERE fc.read = 0'
        query += ' ORDER BY fc.created_at DESC LIMIT ?'
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_unread_count(self):
        """Count unread inbox items."""
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        count = conn.execute('SELECT COUNT(*) FROM feedback_comments WHERE read = 0').fetchone()[0]
        conn.close()
        return count

    def mark_read(self, comment_id=None, item_id=None, mark_all=False):
        """Mark comments as read."""
        db_path = self._app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        now = datetime.utcnow().isoformat()

        if mark_all:
            conn.execute('UPDATE feedback_comments SET read = 1')
        elif item_id:
            conn.execute('UPDATE feedback_comments SET read = 1 WHERE item_id = ?', (item_id,))
        elif comment_id:
            conn.execute('UPDATE feedback_comments SET read = 1 WHERE id = ?', (comment_id,))

        conn.commit()
        conn.close()

    def _push_to_discord(self, item, author, content):
        """Push an agent comment to the project's Discord channel."""
        slug = item.get('project_slug', '')
        if not slug:
            return

        try:
            config_path = os.path.join(os.path.dirname(self._app.config['DB_PATH']), 'discord_bot_config.json')
            if not os.path.exists(config_path):
                return

            with open(config_path) as f:
                config = json.load(f)

            channel_id = config.get('channels', {}).get(slug)
            token = config.get('discord_token', '')
            if not channel_id or not token:
                return

            import urllib.request
            msg = f"**{author}** on _{item.get('title', '')}_ ({item.get('project_name', '')}):\n{content[:1800]}"
            payload = json.dumps({'content': msg}).encode()
            req = urllib.request.Request(
                f'https://discord.com/api/v10/channels/{channel_id}/messages',
                data=payload,
                headers={
                    'Authorization': f'Bot {token}',
                    'Content-Type': 'application/json',
                },
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass


# Singleton
inbox_service = InboxService()
