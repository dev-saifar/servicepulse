from flask import Blueprint, render_template, jsonify, request
from sqlalchemy import func, case
from datetime import datetime
from app.models import db, Ticket, Technician

hourly_bp = Blueprint('hourly', __name__, url_prefix='/hourly')


# ✅ Technician Productivity Report
@hourly_bp.route('/productivity', methods=['GET'])
def get_technician_productivity():
    start_date = request.args.get('start_date', datetime.today().strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.today().strftime('%Y-%m-%d'))

    productivity_query = db.session.query(
        Technician.name.label("technician"),
        func.count(case((Ticket.call_type == "PM", 1))).label("pm_done"),
        func.count(case((Ticket.call_type == "CM", 1))).label("cm_done"),
        func.count(case((Ticket.call_type == "Installation", 1))).label("installations"),
        func.count(case((Ticket.call_type == "MyQ Installation", 1))).label("myq_installations"),
        func.count(case((Ticket.call_type.notin_(["PM", "CM", "Installation", "MyQ Installation"]), 1))).label(
            "other_tickets")
    ).join(Ticket, Ticket.technician_id == Technician.id, isouter=True) \
        .filter(Ticket.created_at >= start_date, Ticket.created_at <= end_date) \
        .group_by(Technician.name) \
        .order_by(func.count(Ticket.id).desc()).all()

    return jsonify([
        {"technician": row.technician, "pm_done": row.pm_done, "cm_done": row.cm_done,
         "installations": row.installations, "myq_installations": row.myq_installations,
         "other_tickets": row.other_tickets}
        for row in productivity_query
    ])


# ✅ Technician Daily Hourly Report (Location & Tickets)
@hourly_bp.route('/daily_hourly_report', methods=['GET'])
def get_daily_hourly_report():
    selected_date = request.args.get('date', datetime.today().strftime('%Y-%m-%d'))

    # Define time slots
    hours = [f"{h}-00 - {h+1}-00" for h in range(8, 17)]

    # Fetch tickets per hour per technician
    query = db.session.query(
        Technician.name.label("technician"),
        func.strftime('%H', Ticket.created_at).label("hour"),
        Ticket.service_location,
        func.count(Ticket.id).label("tickets_handled")
    ).join(Technician, Ticket.technician_id == Technician.id)\
     .filter(func.date(Ticket.created_at) == selected_date)\
     .group_by(Technician.name, "hour", Ticket.service_location)\
     .order_by(Technician.name, "hour")

    hourly_query = query.all()

    print("🔍 RAW QUERY RESULT:", hourly_query)  # Debugging step

    report_data = {}
    for tech, hour, location, tickets_handled in hourly_query:
        formatted_hour = f"{int(hour)}-00 - {int(hour)+1}-00"
        if tech not in report_data:
            report_data[tech] = {h: "No Activity" for h in hours}
            report_data[tech]["total_tickets"] = 0

        report_data[tech][formatted_hour] = location
        report_data[tech]["total_tickets"] += tickets_handled

    print("📊 PROCESSED REPORT DATA:", report_data)  # Debugging step
    return jsonify(report_data)

# API to Fetch List of Technicians for Dropdown
@hourly_bp.route('/hourly/get_technicians', methods=['GET'])
def get_technicians():
    technicians = db.session.query(Technician.name).all()
    return jsonify([tech[0] for tech in technicians])

# ✅ Ticket Breakdown (by Status & Type)
@hourly_bp.route('/ticket_breakdown', methods=['GET'])
def get_ticket_breakdown():
    breakdown_query = db.session.query(
        Ticket.status,
        Ticket.call_type,
        func.count(Ticket.id).label("count")
    ).group_by(Ticket.status, Ticket.call_type).all()

    result = []
    for row in breakdown_query:
        result.append({"status": row.status, "call_type": row.call_type, "count": row.count})

    return jsonify(result)


# ✅ Export to Excel (Technician Hourly Report)
@hourly_bp.route('/export_hourly_report', methods=['GET'])
def export_hourly_report():
    selected_date = request.args.get('date', datetime.today().strftime('%Y-%m-%d'))
    hourly_query = db.session.query(
        Technician.name.label("technician"),
        func.strftime('%H', Ticket.created_at).label("hour"),
        Ticket.customer,
        Ticket.service_location,
        func.count(Ticket.id).label("tickets_handled")
    ).join(Technician, Ticket.technician_id == Technician.id) \
        .filter(func.date(Ticket.created_at) == selected_date) \
        .group_by(Technician.name, "hour", Ticket.customer, Ticket.service_location) \
        .order_by(Technician.name, "hour").all()

    import pandas as pd
    data = []
    for tech, hour, customer, location, tickets_handled in hourly_query:
        data.append({"Technician": tech, "Time Slot": f"{int(hour)}:00 - {int(hour) + 1}:00",
                     "Customer": customer, "Location": location, "Tickets Handled": tickets_handled})

    df = pd.DataFrame(data)
    file_path = "exports/hourly_report.xlsx"
    df.to_excel(file_path, index=False)

    return jsonify({"message": "Export successful", "file_path": file_path})
@hourly_bp.route('/hourly_report', methods=['GET'])
def hourly_report():
    return render_template('report/hourly_report.html')
