from flask import Blueprint, render_template, jsonify
from datetime import datetime
from app.extensions import db
from app.models import Ticket, Technician
from sqlalchemy.sql import func, case
from flask_login import login_required
from app.utils.permission_required import permission_required

dashboard_bp = Blueprint('dashboard', __name__, template_folder='../templates/dashboard')

@dashboard_bp.route('/')
@login_required
@permission_required('can_view_reports')
def index():
    completed_tickets = Ticket.query.filter_by(status="Closed").count()
    pending_tickets = Ticket.query.filter(Ticket.status != "Closed").count()

    today = datetime.utcnow().strftime('%Y-%m-%d')

    technicians = db.session.query(
        Technician.id,
        Technician.name,
        Technician.status,
        func.count(case((func.strftime('%Y-%m-%d', Ticket.created_at) == today, 1), else_=None)).label('tickets_handled_today')
    ).outerjoin(Ticket, Technician.id == Ticket.technician_id).group_by(Technician.id).all()

    performer_of_month = db.session.query(
        Technician.name, func.count(Ticket.id).label('total_tickets')
    ).join(Ticket).filter(
        func.strftime('%Y-%m', Ticket.created_at) == func.strftime('%Y-%m', func.now())
    ).group_by(Technician.id).order_by(func.count(Ticket.id).desc()).first()

    performer_of_day = db.session.query(
        Technician.name, func.count(Ticket.id).label('daily_tickets')
    ).join(Ticket).filter(
        func.strftime('%Y-%m-%d', Ticket.created_at) == today
    ).group_by(Technician.id).order_by(func.count(Ticket.id).desc()).first()

    exceeded_time_techs = [
        t.name for t in technicians if t.status == "Busy" and Ticket.query.filter(
            Ticket.technician_id == t.id,
            Ticket.status != "Closed",
            Ticket.expected_completion_time < datetime.utcnow()
        ).count() > 0
    ]

    return render_template(
        'dashboard/index.html',
        completed_tickets=completed_tickets,
        pending_tickets=pending_tickets,
        technicians=technicians,
        performer_of_month=performer_of_month or {"name": "No Data", "total_tickets": 0},
        performer_of_day=performer_of_day or {"name": "No Data", "daily_tickets": 0},
        exceeded_time_techs=exceeded_time_techs
    )

@dashboard_bp.route('/dashboard-data')
@login_required
@permission_required('can_view_reports')
def dashboard_data():
    today = datetime.utcnow().strftime('%Y-%m-%d')

    completed_tickets = Ticket.query.filter_by(status="Closed").count()
    pending_tickets = Ticket.query.filter(Ticket.status != "Closed").count()

    technicians = db.session.query(
        Technician.id,
        Technician.name,
        Technician.status,
        func.count(case((func.strftime('%Y-%m-%d', Ticket.created_at) == today, 1), else_=None)).label('tickets_handled_today')
    ).outerjoin(Ticket, Technician.id == Ticket.technician_id).group_by(Technician.id).all()

    performer_of_month = db.session.query(
        Technician.name, func.count(Ticket.id).label('total_tickets')
    ).join(Ticket).filter(
        func.strftime('%Y-%m', Ticket.created_at) == func.strftime('%Y-%m', func.now())
    ).group_by(Technician.id).order_by(func.count(Ticket.id).desc()).first()

    performer_of_day = db.session.query(
        Technician.name, func.count(Ticket.id).label('daily_tickets')
    ).join(Ticket).filter(
        func.strftime('%Y-%m-%d', Ticket.created_at) == today
    ).group_by(Technician.id).order_by(func.count(Ticket.id).desc()).first()

    exceeded_time_techs = [
        t.name for t in technicians if t.status == "Busy" and Ticket.query.filter(
            Ticket.technician_id == t.id,
            Ticket.status != "Closed",
            Ticket.expected_completion_time < datetime.utcnow()
        ).count() > 0
    ]

    return jsonify({
        "completed_tickets": completed_tickets,
        "pending_tickets": pending_tickets,
        "technicians": [
            {
                "name": t.name,
                "status": t.status,
                "tickets_handled_today": t.tickets_handled_today or 0,
                "exceeded": t.name in exceeded_time_techs
            } for t in technicians
        ],
        "performer_of_month": {
            "name": performer_of_month.name if performer_of_month else "No Data",
            "total_tickets": performer_of_month.total_tickets if performer_of_month else 0
        },
        "performer_of_day": {
            "name": performer_of_day.name if performer_of_day else "No Data",
            "daily_tickets": performer_of_day.daily_tickets if performer_of_day else 0
        }
    })

@dashboard_bp.route('/rotate')
@login_required
@permission_required('can_view_reports')
def dashboard_rotator():
    return render_template('dashboard_rotator.html')
