from flask import Blueprint, render_template, request, jsonify, send_file
from app.models import Technician, Ticket, ScheduledReport, spare_req
from app.extensions import db
from datetime import datetime, timedelta
import pandas as pd
import os

technician_performance_bp = Blueprint("technician_performance", __name__)


# ✅ Render the UI when accessed normally
@technician_performance_bp.route("/", methods=["GET"])
def technician_performance():
    return render_template("advance_report/technician_performance.html")


# ✅ API to return JSON when requested (Renamed to avoid conflicts)
@technician_performance_bp.route("/fetch_report", methods=["GET"])
def fetch_report_data(preset=None, date_from=None, date_to=None):
    """ Fetches report data based on filters """
    today = datetime.today().date()

    # ✅ Handle missing preset values
    if preset == "today":
        date_from = date_to = today
    elif preset == "this_week":
        date_from = today - timedelta(days=today.weekday())
        date_to = today
    elif preset == "this_month":
        date_from = today.replace(day=1)
        date_to = today
    elif preset == "last_month":
        first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last_day_last_month = today.replace(day=1) - timedelta(days=1)
        date_from, date_to = first_day_last_month, last_day_last_month
    else:
        # ✅ Default to last 30 days if no preset is provided
        date_from = today - timedelta(days=30)
        date_to = today

    # ✅ Convert date strings to datetime (if not already set)
    if isinstance(date_from, str) and date_from:
        date_from = datetime.strptime(date_from, "%Y-%m-%d")
    if isinstance(date_to, str) and date_to:
        date_to = datetime.strptime(date_to, "%Y-%m-%d")

    # ✅ Fetch data
    technicians = Technician.query.all()
    data = []

    for tech in technicians:
        tickets_query = Ticket.query.filter(Ticket.technician_id == tech.id)

        # Apply date filter if provided
        if date_from and date_to:
            tickets_query = tickets_query.filter(Ticket.created_at.between(date_from, date_to))

        tickets = tickets_query.all()

        pm_count = sum(1 for t in tickets if t.call_type == "PM")
        cm_count = sum(1 for t in tickets if t.call_type == "CM")
        myq_count = sum(1 for t in tickets if t.call_type == "MYQ")
        install_count = sum(1 for t in tickets if t.call_type == "Installation")
        mfi_count = sum(1 for t in tickets if t.call_type == "MFI-CENTRAL")
        other_count = sum(1 for t in tickets if t.call_type not in ["PM", "CM", "MYQ", "Installation", "MFI-CENTRAL"])

        avg_resolution_time = (
            sum(t.tat for t in tickets if t.tat is not None) / len(tickets) if tickets else 0
        )

        # ✅ Fix NameError: Ensure correct variable name
        data.append({
            "Technician Name": tech.name,
            "PM Count": pm_count,
            "CM Count": cm_count,
            "MYQ Count": myq_count,
            "Installation Count": install_count,
            "MFI-CENTRAL Count": mfi_count,  # ✅ Fix variable name
            "Other Count": other_count,
            "Average Resolution Time (Hours)": avg_resolution_time
        })

    return data

@technician_performance_bp.route("/download_report", methods=["GET"])
def download_report():
    preset = request.args.get("preset", "")
    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")

    # ✅ Fetch data
    data = fetch_report_data(preset, date_from, date_to)

    if not data:
        return jsonify({"message": "No data available"}), 400

    df = pd.DataFrame(data)

    # ✅ Ensure the reports directory exists
    reports_dir = os.path.join(os.getcwd(), "app", "static", "reports")
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)  # ✅ Creates the folder if it doesn't exist

    filename = "technician_performance_report.xlsx"  # ✅ Excel file
    filepath = os.path.join(reports_dir, filename)

    # ✅ Save as Excel file
    df.to_excel(filepath, index=False, engine="openpyxl")

    # ✅ Send the file as an Excel attachment
    return send_file(filepath, as_attachment=True, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ✅ API to Schedule Report
@technician_performance_bp.route("/schedule_report", methods=["POST"])
def schedule_report():
    try:
        data = request.get_json()
        print("Received Schedule Request:", data)  # ✅ Debugging

        if not data:
            return jsonify({"message": "No data received"}), 400

        schedule = data.get("schedule")
        email = data.get("email")
        report_type = data.get("report_type")

        if not schedule or not email or not report_type:
            print("Invalid data received:", data)  # ✅ Debugging
            return jsonify({"message": "Invalid data provided", "received_data": data}), 400

        valid_reports = ["Technician Performance", "FOC & Warranty Report"]

        if report_type not in valid_reports:
            print("Invalid report type received:", report_type)  # ✅ Debugging
            return jsonify({"message": f"Invalid report type: {report_type}"}), 400

        new_report = ScheduledReport(
            report_type=report_type,
            schedule=schedule,
            email=email,
            created_at=datetime.utcnow()
        )
        db.session.add(new_report)
        db.session.commit()

        print("Report scheduled successfully:", report_type, email, schedule)  # ✅ Debugging
        return jsonify({"message": f"{report_type} scheduled successfully"}), 200

    except Exception as e:
        print("Error scheduling report:", str(e))  # ✅ Catch and log errors
        return jsonify({"message": "Server error"}), 500


# ✅ API to Get Scheduled Reports
@technician_performance_bp.route("/get_scheduled_reports", methods=["GET"])
def get_scheduled_reports():
    reports = ScheduledReport.query.all()
    data = [
        {
            "id": report.id,
            "report_type": report.report_type,
            "schedule": report.schedule,
            "email": report.email
        }
        for report in reports
    ]
    return jsonify(data)


# ✅ API to Delete Scheduled Report
@technician_performance_bp.route("/delete_scheduled_report/<int:report_id>", methods=["DELETE"])
def delete_scheduled_report(report_id):
    report = ScheduledReport.query.get(report_id)
    if not report:
        return jsonify({"message": "Report not found"}), 404

    db.session.delete(report)
    db.session.commit()
    return jsonify({"message": "Scheduled report deleted successfully"}), 200


# ✅ Fetch FOC & Warranty Report Data
def fetch_foc_warranty_report_data(preset=None, date_from=None, date_to=None):
    today = datetime.today().date()

    # ✅ Handle preset date filters
    if preset == "today":
        date_from = date_to = today
    elif preset == "this_week":
        date_from = today - timedelta(days=today.weekday())
        date_to = today
    elif preset == "this_month":
        date_from = today.replace(day=1)
        date_to = today
    elif preset == "last_month":
        first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last_day_last_month = today.replace(day=1) - timedelta(days=1)
        date_from, date_to = first_day_last_month, last_day_last_month
    else:
        date_from = today - timedelta(days=30)
        date_to = today

    # ✅ Convert date strings to datetime
    if isinstance(date_from, str) and date_from:
        date_from = datetime.strptime(date_from, "%Y-%m-%d")
    if isinstance(date_to, str) and date_to:
        date_to = datetime.strptime(date_to, "%Y-%m-%d")

    technicians = Technician.query.all()
    data = []

    for tech in technicians:
        # Fetch Tickets
        tickets_query = Ticket.query.filter(Ticket.technician_id == tech.id)
        if date_from and date_to:
            tickets_query = tickets_query.filter(Ticket.created_at.between(date_from, date_to))

        open_tickets = tickets_query.filter(Ticket.status != "Closed").count()
        closed_tickets = tickets_query.filter(Ticket.status == "Closed").count()

        # Fetch Spare Requests (Warranty & FOC)
        spare_requests_query = spare_req.query.filter(spare_req.technician_id == tech.id)
        if date_from and date_to:
            spare_requests_query = spare_requests_query.filter(spare_req.date.between(date_from, date_to))

        warranty_claimed = spare_requests_query.filter(spare_req.warranty_status == "Claimed").count()
        warranty_pending = spare_requests_query.filter(spare_req.warranty_status == "Pending").count()
        foc_pending = spare_requests_query.filter(spare_req.foc_no == "Pending").count()

        # Append Data
        data.append({
            "Technician Name": tech.name,
            "Open Tickets": open_tickets,
            "Closed Tickets": closed_tickets,
            "Warranty Claimed": warranty_claimed,
            "Warranty Pending": warranty_pending,
            "FOC Pending": foc_pending
        })

    return data

# ✅ API to Get JSON Report
@technician_performance_bp.route("/fetch_foc_warranty_report", methods=["GET"])
def fetch_foc_warranty_report():
    preset = request.args.get("preset", "")
    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")

    data = fetch_foc_warranty_report_data(preset, date_from, date_to)
    return jsonify(data)

# ✅ API to Download Excel Report
@technician_performance_bp.route("/download_foc_warranty_report", methods=["GET"])
def download_foc_warranty_report():
    preset = request.args.get("preset", "")
    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")

    data = fetch_foc_warranty_report_data(preset, date_from, date_to)
    if not data:
        return jsonify({"message": "No data available"}), 400

    df = pd.DataFrame(data)

    reports_dir = os.path.join(os.getcwd(), "app", "static", "reports")
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)

    filename = "technician_foc_warranty_report.xlsx"
    filepath = os.path.join(reports_dir, filename)

    df.to_excel(filepath, index=False, engine="openpyxl")

    return send_file(filepath, as_attachment=True, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
@technician_performance_bp.route("/foc_warranty_report", methods=["GET"])
def technician_foc_war():
    """ ✅ Render the UI for the FOC & Warranty Report """
    return render_template("advance_report/technician_foc_war.html")
from flask_mail import Mail, Message
from flask import jsonify, Blueprint, current_app

# Initialize Flask-Mail
mail = Mail()

@technician_performance_bp.route("/test_email", methods=["GET"])
def test_email():
    try:
        msg = Message(
            "Test Email from Flask",
            sender=current_app.config["MAIL_DEFAULT_SENDER"],
            recipients=["a.saifar@groupmfi.com"],  # ✅ Replace with your email
            body="This is a test email from your Flask app."
        )
        mail.send(msg)
        return jsonify({"message": "Test email sent successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
def get_technician_analytics_data(from_date=None, to_date=None, technician=None):
    if from_date:
        from_date = datetime.strptime(from_date, "%Y-%m-%d")
    if to_date:
        to_date = datetime.strptime(to_date, "%Y-%m-%d")

    query = Ticket.query

    if from_date and to_date:
        query = query.filter(Ticket.created_at.between(from_date, to_date))

    if technician:
        tech_obj = Technician.query.filter_by(name=technician).first()
        if tech_obj:
            query = query.filter(Ticket.technician_id == tech_obj.id)

    tickets = query.all()
    technician_data = {}

    for ticket in tickets:
        tech_name = ticket.technician.name if ticket.technician else "Unknown"
        if tech_name not in technician_data:
            technician_data[tech_name] = {
                "Technician": tech_name,
                "PM": 0,
                "CM": 0,
                "MYQ": 0,
                "Install": 0,
                "MFI-Central": 0,
                "Other": 0,
                "Closed": 0,
                "Open": 0,
                "TATs": [],
            }

        entry = technician_data[tech_name]
        call_type = ticket.call_type or ""
        status = ticket.status or ""
        if call_type == "PM":
            entry["PM"] += 1
        elif call_type == "CM":
            entry["CM"] += 1
        elif call_type == "MYQ":
            entry["MYQ"] += 1
        elif call_type == "Installation":
            entry["Install"] += 1
        elif call_type == "MFI-CENTRAL":
            entry["MFI-Central"] += 1
        else:
            entry["Other"] += 1

        if status == "Closed":
            entry["Closed"] += 1
        else:
            entry["Open"] += 1

        if ticket.tat:
            entry["TATs"].append(ticket.tat)

    # Finalize TATs
    for entry in technician_data.values():
        tats = entry.pop("TATs")
        entry["Avg Resolution Time (Hours)"] = round(sum(tats)/len(tats), 2) if tats else 0

    return list(technician_data.values())

@technician_performance_bp.route("/export_technician_excel", methods=["GET"])
def export_technician_excel():
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    technician = request.args.get("technician")

    data = get_technician_analytics_data(from_date, to_date, technician)
    if not data:
        return jsonify({"message": "No data found"}), 400

    df = pd.DataFrame(data)

    reports_dir = os.path.join(os.getcwd(), "app", "static", "reports")
    os.makedirs(reports_dir, exist_ok=True)

    filename = "technician_analytics_export.xlsx"
    filepath = os.path.join(reports_dir, filename)
    df.to_excel(filepath, index=False, engine="openpyxl")

    return send_file(filepath, as_attachment=True)
