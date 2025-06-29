from flask import Blueprint, render_template, request, jsonify, send_file, abort
from sqlalchemy import func, case
from app import db
from app.models import Ticket, Technician
from app.utils.permission_required import permission_required
from flask_login import login_required
import pandas as pd
import io

# Create Blueprint for Reports
report_bp = Blueprint('report', __name__, url_prefix='/report')

@report_bp.route('/')
@login_required
@permission_required('can_view_reports')
def report_dashboard():
    try:
        technicians = Technician.query.all()
        technician_names = [tech.name for tech in technicians]

        ticket_types_query = db.session.query(
            Ticket.call_type, func.count(Ticket.call_type)
        ).group_by(Ticket.call_type).all()
        ticket_types_data = {t[0]: t[1] for t in ticket_types_query}

        ticket_status_query = db.session.query(
            Ticket.status, func.count(Ticket.status)
        ).group_by(Ticket.status).all()
        ticket_status_data = {t[0]: t[1] for t in ticket_status_query}

        tickets_handled_query = db.session.query(
            Technician.name, func.count(Ticket.id).label("ticket_count")
        ).join(Ticket, Ticket.technician_id == Technician.id, isouter=True)\
        .group_by(Technician.name).order_by(func.count(Ticket.id).desc()).all()
        tickets_handled_data = {row[0]: row[1] for row in tickets_handled_query}

        hourly_ticket_query = db.session.query(
            func.strftime('%H', Ticket.created_at).label('hour'), func.count(Ticket.id)
        ).group_by('hour').all()
        hourly_ticket_data = {row[0]: row[1] for row in hourly_ticket_query}

        sla_breach_query = db.session.query(
            case((Ticket.status == "Breached", "Breached"), (Ticket.status != "Breached", "Within SLA")),
            func.count(Ticket.id)
        ).group_by(Ticket.status).all()
        sla_breach_data = {row[0]: row[1] for row in sla_breach_query}

        return render_template(
            'report/report.html',
            technician_names=technician_names,
            ticket_types=ticket_types_data,
            tickets_handled=tickets_handled_data,
            hourly_ticket_data=hourly_ticket_data,
            sla_breach_data=sla_breach_data,
            ticket_status_data=ticket_status_data
        )

    except Exception as e:
        print(f"Error in report_dashboard: {e}")
        return "An error occurred while generating the report.", 500

@report_bp.route('/data', methods=['GET'])
@login_required
@permission_required('can_view_reports')
def get_report_data():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    tickets_handled_query = db.session.query(
        Technician.name, func.count(Ticket.id).label("ticket_count")
    ).join(Ticket, Ticket.technician_id == Technician.id, isouter=True)\
    .group_by(Technician.name).order_by(func.count(Ticket.id).desc()).all()
    tickets_handled_data = {row[0]: row[1] for row in tickets_handled_query}

    ticket_types_query = db.session.query(
        Ticket.call_type, func.count(Ticket.call_type)
    ).group_by(Ticket.call_type).all()
    ticket_types_data = {t[0]: t[1] for t in ticket_types_query}

    ticket_status_query = db.session.query(
        Ticket.status, func.count(Ticket.status)
    ).group_by(Ticket.status).all()
    ticket_status_data = {t[0]: t[1] for t in ticket_status_query}

    hourly_ticket_query = db.session.query(
        func.strftime('%H', Ticket.created_at).label('hour'), func.count(Ticket.id)
    ).group_by('hour').all()
    hourly_ticket_data = {row[0]: row[1] for row in hourly_ticket_query}

    return jsonify({
        "tickets_handled": tickets_handled_data,
        "ticket_types": ticket_types_data,
        "ticket_status": ticket_status_data,
        "hourly_ticket_data": hourly_ticket_data
    })

@report_bp.route('/export', methods=['GET'])
@login_required
@permission_required('can_export_data')
def export_report():
    report_data = get_report_data().json
    df = pd.DataFrame(report_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Technician Productivity')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name="technician_productivity_report.xlsx")
from flask import send_file
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
from app.models import Contract
from app.utils.permission_required import permission_required
from flask_login import login_required

@report_bp.route('/export/contract-report')
@login_required
@permission_required('can_view_contracts')
def export_contract_report():
    today = datetime.today().date()
    expiring_cutoff = today + timedelta(days=60)

    # Load all contracts
    contracts = Contract.query.all()

    # Prepare data
    active_data = []
    expiring_data = []
    expired_data = []

    for c in contracts:
        try:
            end_date = datetime.strptime(c.contract_end_date, "%Y-%m-%d").date()
        except:
            continue  # Skip if invalid date

        row = {
            "Contract Code": c.contract_code,
            "Customer": c.cust_name,
            "Billing Company": c.billing_company,
            "Start Date": c.contract_start_date,
            "End Date": c.contract_end_date,
            "Salesperson": c.sales_person,
            "Email": c.email,
            "Billing Cycle": c.billing_cycle,
            "Currency": c.contract_currency
        }

        if end_date < today:
            expired_data.append(row)
        elif today <= end_date <= expiring_cutoff:
            expiring_data.append(row)
        else:
            active_data.append(row)

    # Create DataFrames
    df_active = pd.DataFrame(active_data)
    df_expiring = pd.DataFrame(expiring_data)
    df_expired = pd.DataFrame(expired_data)

    # Write to Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_active.to_excel(writer, sheet_name='Active Contracts', index=False)
        df_expiring.to_excel(writer, sheet_name='Expiring Soon', index=False)
        df_expired.to_excel(writer, sheet_name='Expired Contracts', index=False)

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f"Contract_Report_{today.strftime('%Y%m%d')}.xlsx"
    )
