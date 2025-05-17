# logs_dashboard.py
from flask import Blueprint, render_template
from app.modules.db_logger import Log

logs_bp = Blueprint('logs', __name__, url_prefix='/logs')

@logs_bp.route('/')
def view_logs():
    logs = Log.query.order_by(Log.timestamp.desc()).limit(200).all()
    return render_template('logs.html', logs=logs)

