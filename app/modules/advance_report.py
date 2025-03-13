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
    body = "Hello , Please find the scheduled report attached."

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


import os

@advance_report_bp.route('/ticket_report', methods=['GET', 'POST'])
def ticket_report():
    """Ticket Report Generation Page with Scheduling Option"""
    technicians = Technician.query.all()

    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        period = request.form.get('period')  # Fixed period selection
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

        # Handle Fixed Period selection
        today = datetime.utcnow()
        if period:
            if period == "current_month":
                start_date = today.replace(day=1)
                end_date = today
            elif period == "last_month":
                first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
                last_day_last_month = today.replace(day=1) - timedelta(days=1)
                start_date = first_day_last_month
                end_date = last_day_last_month
            elif period == "weekly":
                start_date = today - timedelta(days=7)
                end_date = today

        # If scheduling a report
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

        # If exporting report immediately
        else:
            query = db.session.query(
                Ticket.reference_no,
                Ticket.title,
                Ticket.description,
                Ticket.customer,
                Ticket.call_type,
                Ticket.service_location,
                Ticket.asset_Description,
                Ticket.called_by,
                Ticket.status,
                Ticket.created_at,
                Ticket.closed_at,
                Ticket.serial_number,
                Ticket.email_id,
                Ticket.phone,
                Ticket.action_taken,
                Ticket.tat,
                Ticket.region,
                Ticket.complete,
                Ticket.mr_mono,
                Ticket.mr_color,
                Technician.name.label("technician_name")
            ).join(Technician, Ticket.technician_id == Technician.id, isouter=True)

            # Apply Filters (Including Fixed Period)
            if start_date:
                query = query.filter(Ticket.created_at >= start_date)
            if end_date:
                query = query.filter(Ticket.created_at <= end_date)
            if technician_id:
                query = query.filter(Ticket.technician_id == technician_id)
            if region:
                query = query.filter(Ticket.region.ilike(f"%{region}%"))
            if status:
                query = query.filter(Ticket.status == status)
            if call_type:
                query = query.filter(Ticket.call_type == call_type)
            if customer:
                query = query.filter(Ticket.customer.ilike(f"%{customer}%"))

            tickets = query.all()
            if not tickets:
                flash("No records found for the selected filters.", "warning")
                return render_template('advance_report/ticket_report.html', technicians=technicians)

            # Ensure 'reports' directory exists
            report_dir = os.path.join(os.getcwd(), "reports")
            if not os.path.exists(report_dir):
                os.makedirs(report_dir)

            # Generate report file
            file_name = f"ticket_report_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
            file_path = os.path.join(report_dir, file_name)

            # Convert to pandas DataFrame
            df = pd.DataFrame(tickets, columns=[
                'Reference No', 'Title', 'Description', 'Customer', 'Call Type', 'Service Location',
                'Asset Description', 'Called By', 'Status', 'Created At', 'Closed At', 'Serial Number',
                'Email ID', 'Phone', 'Action Taken', 'TAT', 'Region', 'Completion Status',
                'MR Mono', 'MR Color', 'Technician Name'
            ])

            # Save as Excel
            try:
                with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Ticket Report')

                # Verify file creation
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"File was not created: {file_path}")

                print(f"Report successfully saved at: {file_path}")  # Debugging log

            except Exception as e:
                print(f"Error saving report: {str(e)}")
                flash("An error occurred while generating the report.", "danger")
                return render_template('advance_report/ticket_report.html', technicians=technicians)

            return send_file(file_path, as_attachment=True)

    return render_template('advance_report/ticket_report.html', technicians=technicians)

@advance_report_bp.route('/delete_schedule/<int:schedule_id>', methods=['POST'])
def delete_schedule(schedule_id):
    """Deletes a scheduled report"""
    scheduled_report = ScheduledReport.query.get_or_404(schedule_id)
    db.session.delete(scheduled_report)
    db.session.commit()
    flash("Scheduled report deleted successfully!", "success")
    return redirect(url_for('advance_report.advance_report_dashboard'))


@advance_report_bp.route('/run_scheduled_report/<int:report_id>', methods=['POST'])
def run_scheduled_report(report_id):
    """Manually run a specific scheduled report"""
    try:
        report = ScheduledReport.query.get(report_id)
        if not report:
            flash(f"Scheduled report with ID {report_id} not found.", "danger")
            return redirect(url_for('advance_report.advance_report_dashboard'))

        print(f"Running scheduled report: {report.report_type} for email {report.email}")

        # Generate report
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
        if not tickets:
            flash(f"No records found for scheduled report: {report.report_type}", "warning")
            print(f"No tickets found for scheduled report ID {report_id}")
            return redirect(url_for('advance_report.advance_report_dashboard'))

        print(f"Found {len(tickets)} tickets for scheduled report.")

        # Ensure directory exists
        report_dir = os.path.join(os.getcwd(), "scheduled_reports")
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)

        # Generate report file
        file_name = f"{report.report_type}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
        file_path = os.path.join(report_dir, file_name)

        df = pd.DataFrame([{column.name: getattr(ticket, column.name) for column in Ticket.__table__.columns} for ticket in tickets])

        with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Scheduled Report')

        # Check if file exists
        if not os.path.exists(file_path):
            flash(f"Error: Report file was not created.", "danger")
            print("Error: File was not created.")
            return redirect(url_for('advance_report.advance_report_dashboard'))

        print(f"Report successfully saved at: {file_path}")

        # Send report via email
        send_email_report(report, file_path)
        flash(f"Report '{report.report_type}' sent successfully to {report.email}!", "success")
        print(f"Email sent to {report.email} with file {file_path}")

    except Exception as e:
        flash(f"Error running scheduled report: {str(e)}", "danger")
        print(f"Exception occurred: {str(e)}")

    return redirect(url_for('advance_report.advance_report_dashboard'))
