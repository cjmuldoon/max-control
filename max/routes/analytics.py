"""Analytics — CONTROL Intelligence Division."""
from flask import Blueprint, render_template, jsonify
from max.services.analytics import analytics_service

analytics_bp = Blueprint('analytics', __name__)


@analytics_bp.route('/')
def index():
    data = analytics_service.get_dashboard_data()
    return render_template('analytics.html', data=data)


@analytics_bp.route('/api')
def api():
    return jsonify(analytics_service.get_dashboard_data())
