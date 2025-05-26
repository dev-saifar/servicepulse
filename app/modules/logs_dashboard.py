# logs_dashboard.py
from flask import Blueprint, render_template, request, send_file
from app.modules.db_logger import Log
from datetime import datetime
from io import BytesIO
import pandas as pd

logs_bp = Blueprint('logs', __name__, url_prefix='/logs')

@logs_bp.route("/", methods=["GET"])
def view_logs():
    level = request.args.get("level", default=None)
    start = request.args.get("start", default=None)
    end = request.args.get("end", default=None)
    page = request.args.get("page", 1, type=int)

    query = Log.query

    if level:
        query = query.filter_by(level=level)

    if start and end:
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.strptime(end, "%Y-%m-%d")
            query = query.filter(Log.timestamp.between(start_date, end_date))
        except ValueError as e:
            print(f"⚠️ Date parsing error: {e}")  # Optional

    try:
        logs = query.order_by(Log.timestamp.desc()).paginate(page=page, per_page=50)
    except Exception as e:
        print(f"🔥 Pagination error: {e}")
        logs = None

    return render_template("logs.html", logs=logs, level=level, start=start, end=end)

@logs_bp.route("/export")
def export_logs():
    logs = Log.query.order_by(Log.timestamp.desc()).all()
    df = pd.DataFrame([(l.id, l.timestamp.strftime("%Y-%m-%d %H:%M:%S"), l.level, l.message) for l in logs],
                      columns=["ID", "Timestamp", "Level", "Message"])

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name="Logs")

    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="logs.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
