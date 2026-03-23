"""
Standardized Feedback API endpoint — drop this into each project's api_v1.py
Works with both AssetArc and MapVS feedback models.

Add to the existing api blueprint in each project:
  from models.feedback import FeedbackPost
  # Then add the routes below
"""

# --- Add these routes to your existing api_v1.py blueprint ---

@api.route('/feedback', methods=['GET'])
def api_feedback_list():
    """Read-only API for feedback posts — used by Max agents.

    Query params:
      ?status=open,planned,in_progress  (comma-separated, default: all)
      ?category=bug_report,feature_request  (comma-separated, default: all)
      ?limit=50  (default: 50, max: 200)
      ?since=2026-01-01  (ISO date, only posts updated after this date)
    """
    from models.feedback import FeedbackPost
    from infrastructure.database import get_session

    status_filter = request.args.get('status', '')
    category_filter = request.args.get('category', '')
    limit = min(int(request.args.get('limit', 50)), 200)
    since = request.args.get('since', '')

    with get_session() as session:
        query = session.query(FeedbackPost)

        if status_filter:
            statuses = [s.strip() for s in status_filter.split(',')]
            query = query.filter(FeedbackPost.status.in_(statuses))

        if category_filter:
            categories = [c.strip() for c in category_filter.split(',')]
            query = query.filter(FeedbackPost.category.in_(categories))

        if since:
            from datetime import datetime
            try:
                since_dt = datetime.fromisoformat(since)
                query = query.filter(FeedbackPost.updated_at >= since_dt)
            except ValueError:
                pass

        posts = query.order_by(FeedbackPost.created_at.desc()).limit(limit).all()

        return jsonify({
            'posts': [
                {
                    'id': p.id,
                    'title': p.title,
                    'description': p.description,
                    'category': p.category,
                    'status': p.status,
                    'priority': p.priority,
                    'vote_count': p.vote_count,
                    'comment_count': p.comment_count,
                    'admin_response': p.admin_response,
                    'author_name': p.author_name,
                    'created_at': p.created_at.isoformat() if p.created_at else None,
                    'updated_at': p.updated_at.isoformat() if p.updated_at else None,
                }
                for p in posts
            ],
            'total': len(posts),
        })


@api.route('/feedback/stats', methods=['GET'])
def api_feedback_stats():
    """Aggregate feedback stats — used by Max analytics."""
    from services.feedback_service import get_board_stats
    stats = get_board_stats()
    return jsonify(stats)
