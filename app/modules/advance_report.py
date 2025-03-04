from flask import Blueprint, render_template, request, jsonify, send_file, redirect, url_for, flash
from sqlalchemy import func
from app import db
from app.models import Ticket, Technician, ScheduledReport
import pandas as pd
import io
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import schedule
import time
import threading
from config import Config  # Import SMTP settings from config.py

# Create Blueprint for Advanced Reports
advance_report_bp = Blueprint('advance_report', __name__, url_prefix='/advance_report')


def send_email_report(report, file_path):
    """Send scheduled report via email using SMTP settings from config.py"""
    sender_email = Config.MAIL_USERNAME
    receiver_email = report.email
    subject = f"Scheduled Report: {report.report_type}"
    body = "Please find the scheduled report attached."

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    with open(file_path, "rb") as attachment:
        from email.mime.base import MIMEBase
        from email import encoders
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition", f"attachment; filename={file_path}"
        )
        msg.attach(part)

    with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
        server.starttls()
        server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
        server.sendmail(sender_email, receiver_email, msg.as_string())


def generate_scheduled_reports():
    """Check scheduled reports and send them via email"""
    now = datetime.utcnow()
    reports = ScheduledReport.query.all()
    for report in reports:
        if (report.schedule == "daily" and now.hour == 17) or \
                (report.schedule == "weekly" and now.weekday() == 4 and now.hour == 17) or \
                (report.schedule == "monthly" and now.day == 1 and now.hour == 5):

            query = Ticket.query
            if report.start_date:
                query = query.filter(Ticket.created_at >= report.start_date)
            if report.end_date:
                query = query.filter(Ticket.created_at <= report.end_date)
            if report.technician_id:
                query = query.filter(Ticket.technician_id == report.technician_id)
            if report.region:
                query = query.filter(Ticket.region.ilike(f"%{report.region}%"))
            if report.status:
                query = query.filter(Ticket.status == report.status)
            if report.call_type:
                query = query.filter(Ticket.call_type == report.call_type)
            if report.customer:
                query = query.filter(Ticket.customer.ilike(f"%{report.customer}%"))

            tickets = query.all()
            file_path = f"scheduled_reports/{report.report_type}_{now.strftime('%Y%m%d')}.xlsx"
            df = pd.DataFrame(
                [{column.name: getattr(ticket, column.name) for column in Ticket.__table__.columns} for ticket in
                 tickets])
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Scheduled Report')

            send_email_report(report, file_path)


# Run the scheduler in a separate thread
def run_scheduler():
    schedule.every().hour.do(generate_scheduled_reports)
    while True:
        schedule.run_pending()
        time.sleep(60)


threading.Thread(target=run_scheduler, daemon=True).start()


@advance_report_bp.route('/')
def advance_report_dashboard():
    """Renders the Advanced Reports Dashboard"""
    scheduled_reports = ScheduledReport.query.all()
    return render_template('advance_report/dashboard.html', scheduled_reports=scheduled_reports)


@advance_report_bp.route('/ticket_report', methods=['GET', 'POST'])
def ticket_report():
    """Ticket Report Generation Page with Scheduling Option"""
    technicians = Technician.query.all()

    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        period = request.form.get('period')
        technician_id = request.form.get('technician_id')
        region = request.form.get('region')
        status = request.form.get('status')
        call_type = request.form.get('call_type')
        customer = request.form.get('customer')
        schedule = request.form.get('schedule')
        email = request.form.get('email')

        # Convert empty strings to None
        start_date = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        end_date = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

        if schedule and email:
            new_schedule = ScheduledReport(
                report_type='Ticket Report',
                start_date=start_date,
                end_date=end_date,
                period=period,
                technician_id=technician_id,
                region=region,
                status=status,
                call_type=call_type,
                customer=customer,
                email=email,
                schedule=schedule,
                created_at=datetime.utcnow()
            )
            db.session.add(new_schedule)
            db.session.commit()
            flash("Report scheduled successfully!", "success")
            return redirect(url_for('advance_report.advance_report_dashboard'))

    # Ensure the function always returns a response
    return render_template('advance_report/ticket_report.html', technicians=technicians)


@advance_report_bp.route('/delete_schedule/<int:schedule_id>', methods=['POST'])
def delete_schedule(schedule_id):
    """Deletes a scheduled report"""
    scheduled_report = ScheduledReport.query.get_or_404(schedule_id)
    db.session.delete(scheduled_report)
    db.session.commit()
    flash("Scheduled report deleted successfully!", "success")
    return redirect(url_for('advance_report.advance_report_dashboard'))