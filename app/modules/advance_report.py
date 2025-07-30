from flask import Blueprint, render_template, request, jsonify, send_file, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy import func
from app import db
from app.models import Ticket, Technician, ScheduledReport
from flask import render_template
from collections import defaultdict
from app.models import ScheduledReport, ScheduledReportLog
from flask_login import login_required
from flask import current_app
from app.utils.permission_required import permission_required
from sqlalchemy import func, case, and_, or_, cast, Float
import pandas as pd
from app.models import toner_request, spare_req, spares, Ticket  # add Customer, Assets if needed

import io
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import schedule
import time
from app.modules.delivery_report import (
    generate_toner_delivery_excel,
    generate_spare_delivery_excel,
    generate_ticket_cost_excel,
    generate_total_service_summary_excel
)

import threading
from config import Config  # Import SMTP settings from config.py
from dotenv import load_dotenv
load_dotenv(override=True)

# Create Blueprint for Advanced Reports
advance_report_bp = Blueprint('advance_report', __name__, url_prefix='/advance_report')


def send_email_report(report, file_path):
    """Send scheduled report via email using SMTP settings from config.py"""
    from email.mime.base import MIMEBase
    from email import encoders

    sender_email = Config.MAIL_USERNAME
    receiver_email = report.email
    subject = f"📊 Scheduled Report: {report.report_type}"

    # Extract and personalize values
    recipient_name = receiver_email.split('@')[0].replace('.', ' ').title()
    report_type = report.report_type
    start_date = report.start_date.strftime('%Y-%m-%d') if report.start_date else None
    end_date = report.end_date.strftime('%Y-%m-%d') if report.end_date else None

    # Compose body text
    body = (
        f"Dear {recipient_name},\n\n"
        f"Please find attached your scheduled report: *{report_type}*.\n"
        f"{f"The data covers the period from {start_date} to {end_date}.\n" if start_date and end_date else ''}"
        f"\nIf you have any questions or need further insights, feel free to contact our support team.\n\n"
        f"\n\n"
        f"Warm regards,\n"
        f"\n"
        f"ServPulse Automated Reporting System"
    )

    # Create email message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    # Attach report
    with open(file_path, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={file_path}")
        msg.attach(part)

    # Send email
    with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
        server.starttls()
        server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
        server.sendmail(sender_email, receiver_email, msg.as_string())

from datetime import datetime, timedelta
from flask_mail import Message
from app import mail, db
from app.models import ScheduledReport, Ticket
import pandas as pd
import io
import traceback

def generate_scheduled_reports():
    now = datetime.utcnow()
    reports = ScheduledReport.query.all()

    for report in reports:
        try:
            # === Determine if report should run now ===
            run_now = (
                (report.schedule == "daily" and now.hour == 17) or
                (report.schedule == "weekly" and now.weekday() == 4 and now.hour == 17) or
                (report.schedule == "monthly" and now.day == 1 and now.hour == 5)
            )
            if not run_now:
                continue

            # === Resolve Date Range ===
            start_date, end_date = report.start_date, report.end_date
            today = now.date()

            if report.period and report.period.lower() != "custom":
                if report.period == "This Week":
                    start_date = today - timedelta(days=today.weekday())
                    end_date = today
                elif report.period == "Last Week":
                    end_date = today - timedelta(days=today.weekday() + 1)
                    start_date = end_date - timedelta(days=6)
                elif report.period == "This Month":
                    start_date = today.replace(day=1)
                    end_date = today
                elif report.period == "Last Month":
                    first_this_month = today.replace(day=1)
                    end_date = first_this_month - timedelta(days=1)
                    start_date = end_date.replace(day=1)
                elif report.period == "This Year":
                    start_date = today.replace(month=1, day=1)
                    end_date = today
                elif report.period == "Last Year":
                    start_date = today.replace(year=today.year - 1, month=1, day=1)
                    end_date = start_date.replace(month=12, day=31)

            s_date = start_date.strftime('%Y-%m-%d') if start_date else ''
            e_date = end_date.strftime('%Y-%m-%d') if end_date else ''

            # === Generate Report File Based on Type ===
            if report.report_type == "Ticket Report":
                output, filename = generate_ticket_cost_excel(s_date, e_date)

            elif report.report_type == "Entity Cost Summary":
                from app.modules.advance_report import generate_entity_cost_summary_excel
                output, filename = generate_entity_cost_summary_excel(s_date, e_date)

            elif report.report_type == "Total Summary":
                output, filename = generate_total_service_summary_excel(s_date, e_date)

            elif report.report_type == "Toner Delivery":
                output, filename = generate_toner_delivery_excel(s_date, e_date)

            elif report.report_type == "Spare Delivery":
                output, filename = generate_spare_delivery_excel(s_date, e_date)

            else:
                print(f"Unknown report type: {report.report_type}")
                continue

            # === Save File ===
            import os

            # Ensure folder exists
            os.makedirs("scheduled_reports", exist_ok=True)

            file_path = os.path.join("scheduled_reports", filename)
            with open(file_path, "wb") as f:
                f.write(output.getvalue())

            # === Send Email Using Working SMTP Method ===
            send_email_report(report, file_path)
            print(f"✅ Report sent: {filename} → {report.email}")

        except Exception as e:
            print(f"❌ Failed to generate/send report: {report.report_type}")
            import traceback
            traceback.print_exc()
            continue


# Run the scheduler in a separate thread
def run_scheduler():
    schedule.every().hour.do(run_report_job_with_context)
    while True:
        schedule.run_pending()
        time.sleep(60)

def run_report_job_with_context():
    from app import create_app
    app = create_app()
    with app.app_context():
        generate_scheduled_reports()

threading.Thread(target=run_scheduler, daemon=True).start()


@advance_report_bp.route('/')
@login_required
@permission_required('can_view_reports')
def advance_report_dashboard():
    """Renders the Advanced Reports Dashboard"""
    scheduled_reports = ScheduledReport.query.all()

    # Fetch recent logs per report (e.g. last 3 logs per report)
    logs = ScheduledReportLog.query.order_by(ScheduledReportLog.created_at.desc()).limit(100).all()

    # Group logs by report_id
    logs_by_report = defaultdict(list)
    for log in logs:
        logs_by_report[log.report_id].append(log)

    # ⬇️ Move the next_run calculation here
    def calculate_next_run(report):
        now = datetime.utcnow()
        if report.schedule == "daily":
            return (now + timedelta(days=18)).replace(hour=1, minute=0, second=0, microsecond=0)
        elif report.schedule == "weekly":
            next_friday = now + timedelta(days=(4 - now.weekday() + 7) % 7)
            return next_friday.replace(hour=18, minute=0, second=0, microsecond=0)
        elif report.schedule == "monthly":
            next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
            return next_month.replace(hour=5, minute=0, second=0, microsecond=0)
        return None

    # Inject next_run dynamically
    for report in scheduled_reports:
        report.next_run = calculate_next_run(report)

    # ✅ Return after everything is ready
    return render_template(
        'advance_report/dashboard.html',
        scheduled_reports=scheduled_reports,
        logs_by_report=logs_by_report
    )



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

        # === Resolve Date Range ===
        start_date, end_date = report.start_date, report.end_date
        today = datetime.utcnow().date()
        if report.period and report.period.lower() != "custom":
            if report.period == "This Week":
                start_date = today - timedelta(days=today.weekday())
                end_date = today
            elif report.period == "Last Week":
                end_date = today - timedelta(days=today.weekday() + 1)
                start_date = end_date - timedelta(days=6)
            elif report.period == "This Month":
                start_date = today.replace(day=1)
                end_date = today
            elif report.period == "Last Month":
                first_this_month = today.replace(day=1)
                end_date = first_this_month - timedelta(days=1)
                start_date = end_date.replace(day=1)
            elif report.period == "This Year":
                start_date = today.replace(month=1, day=1)
                end_date = today
            elif report.period == "Last Year":
                start_date = today.replace(year=today.year - 1, month=1, day=1)
                end_date = start_date.replace(month=12, day=31),
            elif report.report_type == "Contract Report":
                from app.modules.contract_alerts import generate_contract_expiry_excel
                output, filename = generate_contract_expiry_excel()

        s_date = start_date.strftime('%Y-%m-%d') if start_date else ''
        e_date = end_date.strftime('%Y-%m-%d') if end_date else ''

        # === Generate appropriate report ===
        if report.report_type == "Ticket Report":
            from app.modules.delivery_report import generate_ticket_cost_excel
            output, filename = generate_ticket_cost_excel(s_date, e_date)

        elif report.report_type == "Toner Delivery":
            from app.modules.delivery_report import generate_toner_delivery_excel
            output, filename = generate_toner_delivery_excel(s_date, e_date)

        elif report.report_type == "Spare Delivery":
            from app.modules.delivery_report import generate_spare_delivery_excel
            output, filename = generate_spare_delivery_excel(s_date, e_date)

        elif report.report_type == "Total Summary":
            from app.modules.delivery_report import generate_total_service_summary_excel
            output, filename = generate_total_service_summary_excel(s_date, e_date)

        elif report.report_type == "Contract Report":
            from app.modules.contract_alerts import generate_contract_expiry_excel
            output, filename = generate_contract_expiry_excel()


        else:
            flash("Unsupported report type.", "danger")
            return redirect(url_for('advance_report.advance_report_dashboard'))

        import os

        # Ensure folder exists
        os.makedirs("scheduled_reports", exist_ok=True)

        file_path = os.path.join("scheduled_reports", filename)
        with open(file_path, "wb") as f:
            f.write(output.getvalue())

        # Send report via email
        send_email_report(report, f"scheduled_reports/{filename}")
        with open(f"scheduled_reports/{filename}", 'wb') as f:
            f.write(output.getvalue())

        flash(f"Report '{report.report_type}' sent successfully to {report.email}!", "success")

    except Exception as e:
        flash(f"Error running scheduled report: {str(e)}", "danger")
        print(f"Exception occurred: {str(e)}")

    return redirect(url_for('advance_report.advance_report_dashboard'))


@advance_report_bp.route('/schedule_unified_report', methods=['POST'])
@login_required
def schedule_unified_report():
    from app.models import ScheduledReport
    from datetime import datetime
    from flask import flash

    report_type = request.form.get('report_type')
    email = request.form.get('email')
    schedule = request.form.get('frequency')  # form still sends "frequency", we map it to schedule
    period = request.form.get('period')
    start_date_str = request.form.get('start_date') or None
    end_date_str = request.form.get('end_date') or None

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else None
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else None

    if period != 'Custom':
        start_date = None
        end_date = None

    report = ScheduledReport(
        report_type=report_type,
        email=email,
        schedule=schedule,
        period=period,
        start_date=start_date,
        end_date=end_date,
        #next_run=datetime.utcnow()
    )
    db.session.add(report)
    db.session.commit()

    flash("Report has been scheduled successfully!", "success")
    return redirect(url_for('advance_report.advance_report_dashboard'))


@advance_report_bp.route('/unified_scheduler')
@login_required
def unified_scheduler():
    return render_template('advance_report/unified_scheduler.html')

# Existing imports

# Helper: Toner Delivery Report
    # Existing imports

    from app.models import toner_request, TonerCosting, spare_req, spares, Ticket

    from flask_login import login_required
    from app import db
    import pandas as pd
    import io
    from datetime import datetime

    # Helper: Toner Delivery Report

    def generate_toner_delivery_excel(start_date=None, end_date=None):
        query = db.session.query(toner_request).filter(toner_request.delivery_status == 'Delivered')
        if start_date:
            query = query.filter(toner_request.date_issued >= start_date)
        if end_date:
            query = query.filter(toner_request.date_issued <= end_date)

        results = query.all()
        data = []

        for t in results:
            cost_entry = TonerCosting.query.filter_by(toner_model=t.toner_model, source=t.toner_source).first()
            unit_cost = cost_entry.unit_cost if cost_entry else 0.0
            total_cost = unit_cost * t.issued_qty if t.issued_qty else 0.0

            data.append({
                "Date Issued": t.date_issued.strftime('%Y-%m-%d') if t.date_issued else '',
                "Serial Number": t.serial_number,
                "Customer Name": t.customer_name,
                "Toner Model": t.toner_model,
                "Source": t.toner_source,
                "Qty": t.issued_qty,
                "Unit Cost": round(unit_cost, 2),
                "Total Cost": round(total_cost, 2),
            })

        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Toner")
        output.seek(0)
        return output, "toner_delivery_report.xlsx"

    # Helper: Spare Delivery Report

    def generate_spare_delivery_excel(start_date=None, end_date=None):
        query = db.session.query(spare_req)
        if start_date:
            query = query.filter(spare_req.date >= start_date)
        if end_date:
            query = query.filter(spare_req.date <= end_date)

        results = query.all()
        data = []

        for s in results:
            spare_info = spares.query.filter_by(material_nr=s.product_code).first()
            unit_cost = 0.0 if s.warehouse.upper() == 'WORKSHOP' else (spare_info.price if spare_info else 0.0)
            total_cost = unit_cost * s.qty

            data.append({
                "Date": s.date.strftime('%Y-%m-%d') if s.date else '',
                "Serial Number": s.serial_number,
                "Product Code": s.product_code,
                "Description": s.description,
                "Qty": s.qty,
                "Warehouse": s.warehouse,
                "Customer Name": s.customer_name,
                "Unit Cost": round(unit_cost, 2),
                "Total Cost": round(total_cost, 2),
            })

        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Spare")
        output.seek(0)
        return output, "spare_delivery_report.xlsx"

    # Helper: Ticket Cost Report

    def generate_ticket_cost_excel(start_date=None, end_date=None):
        query = db.session.query(Ticket)
        if start_date:
            query = query.filter(Ticket.created_at >= start_date)
        if end_date:
            query = query.filter(Ticket.created_at <= end_date)

        results = query.all()
        data = []

        for t in results:
            data.append({
                "Reference No": t.reference_no,
                "Customer": t.customer,
                "Created At": t.created_at.strftime('%Y-%m-%d') if t.created_at else '',
                "Service Cost": 10
            })

        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Ticket Cost")
        output.seek(0)
        return output, "ticket_cost_report.xlsx"

    # Helper: Total Service Summary

    def generate_total_service_summary_excel(start_date=None, end_date=None):
        from collections import defaultdict

        if start_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            end_date = datetime.strptime(end_date, "%Y-%m-%d")

        toner_query = db.session.query(toner_request)
        spare_query = db.session.query(spare_req)
        ticket_query = db.session.query(Ticket)

        if start_date:
            toner_query = toner_query.filter(toner_request.date_issued >= start_date)
            spare_query = spare_query.filter(spare_req.date >= start_date)
            ticket_query = ticket_query.filter(Ticket.created_at >= start_date)
        if end_date:
            toner_query = toner_query.filter(toner_request.date_issued <= end_date)
            spare_query = spare_query.filter(spare_req.date <= end_date)
            ticket_query = ticket_query.filter(Ticket.created_at <= end_date)

        toner_data, toner_costs = [], defaultdict(float)
        for t in toner_query.all():
            cost_entry = TonerCosting.query.filter_by(toner_model=t.toner_model, source=t.toner_source).first()
            unit_cost = cost_entry.unit_cost if cost_entry else 0.0
            total_cost = unit_cost * t.issued_qty if t.issued_qty else 0.0
            toner_costs[t.customer_name] += total_cost
            toner_data.append({
                "Date Issued": t.date_issued.strftime('%Y-%m-%d') if t.date_issued else '',
                "Serial Number": t.serial_number,
                "Customer Name": t.customer_name,
                "Toner Model": t.toner_model,
                "Toner Source": t.toner_source,
                "Issued Qty": t.issued_qty,
                "Unit Cost": round(unit_cost, 2),
                "Total Cost": round(total_cost, 2),
            })

        spare_data, spare_costs = [], defaultdict(float)
        for s in spare_query.all():
            spare_info = spares.query.filter_by(material_nr=s.product_code).first()
            unit_cost = 0.0 if s.warehouse.upper() == 'WORKSHOP' else (spare_info.price if spare_info else 0.0)
            total_cost = unit_cost * s.qty
            spare_costs[s.customer_name] += total_cost
            spare_data.append({
                "Date": s.date.strftime('%Y-%m-%d') if s.date else '',
                "Serial Number": s.serial_number,
                "Product Code": s.product_code,
                "Description": s.description,
                "Qty": s.qty,
                "Warehouse": s.warehouse,
                "Customer Name": s.customer_name,
                "Unit Cost": round(unit_cost, 2),
                "Total Cost": round(total_cost, 2),
            })

        ticket_data, service_costs = [], defaultdict(float)
        for t in ticket_query.all():
            service_costs[t.customer] += 10
            ticket_data.append({
                "Reference No": t.reference_no,
                "Customer": t.customer,
                "Created At": t.created_at.strftime('%Y-%m-%d') if t.created_at else '',
                "Service Cost": 10
            })

        all_customers = set(toner_costs) | set(spare_costs) | set(service_costs)
        summary_data = []
        for cust in all_customers:
            toner = toner_costs.get(cust, 0)
            spare = spare_costs.get(cust, 0)
            service = service_costs.get(cust, 0)
            total = toner + spare + service
            summary_data.append({
                "Customer": cust,
                "Toner Cost": round(toner, 2),
                "Spare Cost": round(spare, 2),
                "Service Cost": round(service, 2),
                "Total Cost": round(total, 2)
            })

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Write primary data
            pd.DataFrame(toner_data).to_excel(writer, index=False, sheet_name="Toner")
            pd.DataFrame(spare_data).to_excel(writer, index=False, sheet_name="Spare")
            pd.DataFrame(ticket_data).to_excel(writer, index=False, sheet_name="Ticket Cost")

            # Create and write summary
            df_summary['Total Cost'] = pd.to_numeric(df_summary['Total Cost'], errors='coerce').fillna(0)
            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, index=False, sheet_name="Summary")

            # Create chart from full summary
            df_summary = pd.DataFrame(summary_data)
            df_summary = df_summary.sort_values(by='Total Cost', ascending=False)
            df_summary.to_excel(writer, index=False, sheet_name="Summary")

            workbook = writer.book
            worksheet_summary = writer.sheets["Summary"]
            num_rows = len(df_summary)



        # Prepare the output
        output.seek(0)
        return output, "total_service_summary.xlsx"

# In advance_report.py
# ... (existing imports and code) ...

@advance_report_bp.route("/entity-cost-summary", methods=["GET"])
@login_required
@permission_required('can_export_financials')
def generate_entity_cost_summary_excel():
    try:
        # ⏳ Filters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        customer = request.args.get('customer')
        contract = request.args.get('contract')
        serial_number = request.args.get('serial_number')

        today = datetime.today()
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d") if start_date_str else today.replace(day=1)
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d") if end_date_str else today

        # ✅ Toner Cost
        toner_query = db.session.query(
            toner_request.serial_number.label("serial_number"),
            toner_request.customer_name,
            toner_request.contract_code,
            func.sum(toner_request.issued_qty * toner_request.unit_cost).label("toner_cost")
        ).filter(
            toner_request.date_issued.between(start_date, end_date)
        )

        if customer:
            toner_query = toner_query.filter(toner_request.customer_name == customer)
        if contract:
            toner_query = toner_query.filter(toner_request.contract_code == contract)
        if serial_number:
            toner_query = toner_query.filter(toner_request.serial_number == serial_number)

        toner_query = toner_query.group_by(
            toner_request.serial_number,
            toner_request.customer_name,
            toner_request.contract_code
        ).subquery()

        # ✅ Spare Cost
        spare_query = db.session.query(
            spare_req.serial_number.label("serial_number"),
            spare_req.customer_name,
            spare_req.contract,
            func.sum(spare_req.qty * spares.price).label("spare_cost")
        ).join(spares, spares.material_nr == spare_req.product_code
        ).filter(
            spare_req.date.between(start_date, end_date)
        )

        if customer:
            spare_query = spare_query.filter(spare_req.customer_name == customer)
        if contract:
            spare_query = spare_query.filter(spare_req.contract == contract)
        if serial_number:
            spare_query = spare_query.filter(spare_req.serial_number == serial_number)

        spare_query = spare_query.group_by(
            spare_req.serial_number,
            spare_req.customer_name,
            spare_req.contract
        ).subquery()

        # ✅ Service Cost
        ticket_query = db.session.query(
            Ticket.serial_number.label("serial_number"),
            Ticket.customer,
            Ticket.contract,
            func.count(Ticket.id).label("ticket_count"),
            (func.count(Ticket.id) * 10).label("service_cost")
        ).filter(
            Ticket.created_at.between(start_date, end_date)
        )

        if customer:
            ticket_query = ticket_query.filter(Ticket.customer == customer)
        if contract:
            ticket_query = ticket_query.filter(Ticket.contract == contract)
        if serial_number:
            ticket_query = ticket_query.filter(Ticket.serial_number == serial_number)

        ticket_query = ticket_query.group_by(
            Ticket.serial_number,
            Ticket.customer,
            Ticket.contract
        ).subquery()

        # 🧩 Merge all
        merged = db.session.query(
            toner_query.c.serial_number,
            toner_query.c.customer_name,
            toner_query.c.contract_code,
            toner_query.c.toner_cost,
            spare_query.c.spare_cost,
            ticket_query.c.service_cost
        ).outerjoin(
            spare_query, toner_query.c.serial_number == spare_query.c.serial_number
        ).outerjoin(
            ticket_query, toner_query.c.serial_number == ticket_query.c.serial_number
        ).all()

        # 🧾 Create Excel
        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')

        data = [{
            "Serial Number": row.serial_number,
            "Customer Name": row.customer_name,
            "Contract Code": row.contract_code,
            "Toner Cost": round(row.toner_cost or 0, 2),
            "Spare Cost": round(row.spare_cost or 0, 2),
            "Service Cost": round(row.service_cost or 0, 2),
            "Total Cost": round((row.toner_cost or 0) + (row.spare_cost or 0) + (row.service_cost or 0), 2)
        } for row in merged]

        df = pd.DataFrame(data)
        df.to_excel(writer, index=False, sheet_name='EntityCostSummary')
        writer.close()
        output.seek(0)

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            download_name='Entity_Cost_Summary.xlsx',
            as_attachment=True
        )

    except Exception as e:
        print(f"[ERROR] Report generation failed: {e}")
        flash("Something went wrong while generating the entity cost summary.", "danger")
        return redirect(url_for("advance_report.advance_report_home"))

@advance_report_bp.route("/entity-cost-summary", methods=["GET"]) # Changed advance_report to advance_report_bp
@login_required
@permission_required("can_view_reports")
def entity_cost_summary():
    try:
        # Extract filters from URL query parameters
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        customer_name = request.args.get("customer_name")

        output, filename = generate_entity_cost_summary_excel(
            start_date=start_date,
            end_date=end_date,
            customer_name=customer_name
        )

        if not output:
            flash("Failed to generate the report.", "danger")
            return redirect(request.referrer or url_for("advance_report.entity_cost_summary"))

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        print(f"[ERROR] Report generation failed: {e}")
        flash("An unexpected error occurred while generating the report.", "danger")
        return redirect(request.referrer or url_for("advance_report.entity_cost_summary"))
