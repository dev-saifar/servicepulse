from celery import Celery
from app import db, mail
from app.models import ScheduledReport
from flask_mail import Message
import pandas as pd
import os
from datetime import datetime

celery = Celery('tasks', broker='redis://localhost:6379/0')
from app.modules.contract_alerts import send_contract_expiry_alerts
from app import celery

@celery.task
def run_contract_alerts():
    send_contract_expiry_alerts()

@celery.task
def generate_and_email_report(report_id):
    """Generate and send scheduled reports via email."""
    report = ScheduledReport.query.get(report_id)

    if not report:
        return "Report not found"

    # Generate report data
    file_path = f"temp_reports/scheduled_report_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
    df = pd.DataFrame([])  # Replace this with actual report generation logic
    df.to_excel(file_path, index=False)

    # Send email
    msg = Message(
        subject="Scheduled Report",
        sender="your_email@example.com",
        recipients=[report.email]
    )
    msg.body = "Attached is your scheduled technician performance report."
    with open(file_path, "rb") as f:
        msg.attach("Technician_Report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   f.read())

    mail.send(msg)

    return "Report emailed successfully"
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'daily-contract-reports': {
        'task': 'tasks.run_all_scheduled_reports',
        'schedule': crontab(hour=6, minute=0),  # every day at 06:00
    },
}