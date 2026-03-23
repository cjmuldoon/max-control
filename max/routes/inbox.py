"""CONTROL Inbox — Agent updates and notifications."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from max.services.inbox import inbox_service
from max.utils.smart_quotes import get_quote

inbox_bp = Blueprint('inbox', __name__)


@inbox_bp.route('/')
def index():
    """The Chief's inbox — all agent updates."""
    unread_only = request.args.get('unread') == '1'
    messages = inbox_service.get_inbox(unread_only=unread_only, limit=100)
    unread_count = inbox_service.get_unread_count()

    return render_template(
        'inbox.html',
        messages=messages,
        unread_count=unread_count,
        unread_only=unread_only,
    )


@inbox_bp.route('/mark-read', methods=['POST'])
def mark_read():
    comment_id = request.form.get('comment_id')
    item_id = request.form.get('item_id')
    mark_all = request.form.get('all') == '1'

    inbox_service.mark_read(comment_id=comment_id, item_id=item_id, mark_all=mark_all)
    return redirect(url_for('inbox.index'))


@inbox_bp.route('/reply', methods=['POST'])
def reply():
    """Chief replies to an agent comment."""
    item_id = request.form.get('item_id', '')
    content = request.form.get('content', '').strip()

    if item_id and content:
        inbox_service.add_comment(item_id, content, author='Chief', is_agent=False, push_discord=False)
        inbox_service.mark_read(item_id=item_id)
        flash(f'Reply sent. {get_quote("success")}', 'success')

    return redirect(url_for('inbox.index'))


@inbox_bp.route('/comments/<item_id>')
def comments(item_id):
    """Get comments for a specific item (JSON)."""
    comments = inbox_service.get_comments(item_id)
    return jsonify(comments)


@inbox_bp.route('/unread-count')
def unread_count():
    return jsonify({'count': inbox_service.get_unread_count()})
