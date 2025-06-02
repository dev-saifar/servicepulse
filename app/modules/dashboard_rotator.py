# C:\servicepulse\app\modules\dashboard_rotator.py

from flask import Blueprint, render_template
from datetime import datetime
from app.extensions import db
from app.models import Technician, Ticket
from sqlalchemy.sql import func, case

dashboard_rotator_bp = Blueprint(
    'dashboard_rotator',
    __name__,
    template_folder='../templates/dashboard_rotator'
)

@dashboard_rotator_bp.route('/tv/dashboard')
def tv_dashboard():
    today = datetime.utcnow().strftime('%Y-%m-%d')
    current_month = datetime.utcnow().strftime('%Y-%m')

    # 👨‍🔧 Technician + tickets handled today
    technicians = db.session.query(
        Technician.id,
        Technician.name,
        Technician.status,
        func.count(case((func.strftime('%Y-%m-%d', Ticket.created_at) == today, 1), else_=None)).label('tickets_handled_today')
    ).outerjoin(Ticket, Technician.id == Ticket.technician_id).group_by(Technician.id).all()

    # 🎯 Performer of the day
    performer_of_day = db.session.query(
        Technician.name,
        func.count(Ticket.id).label('daily_tickets')
    ).join(Ticket).filter(
        func.strftime('%Y-%m-%d', Ticket.created_at) == today
    ).group_by(Technician.id).order_by(func.count(Ticket.id).desc()).first()

    # 🏆 Performer of the month
    performer_of_month = db.session.query(
        Technician.name,
        func.count(Ticket.id).label('total_tickets')
    ).join(Ticket).filter(
        func.strftime('%Y-%m', Ticket.created_at) == current_month
    ).group_by(Technician.id).order_by(func.count(Ticket.id).desc()).first()

    # 📊 Total ticket stats
    completed_tickets = Ticket.query.filter_by(status="Closed").count()
    pending_tickets = Ticket.query.filter(Ticket.status != "Closed").count()

    # 🔴 Overdue techs
    exceeded_time_techs = []
    busy_techs = Technician.query.filter_by(status="Busy").all()
    for tech in busy_techs:
        overdue = Ticket.query.filter(
            Ticket.technician_id == tech.id,
            Ticket.status != "Closed",
            Ticket.expected_completion_time < datetime.utcnow()
        ).count()
        if overdue > 0:
            exceeded_time_techs.append(tech.name)

    # 🟢🟠 Tech status counts
    total_free = Technician.query.filter_by(status="Free").count()
    total_busy = Technician.query.filter_by(status="Busy").count()

    # ⚙️ Workload (top 5)
    workload = db.session.query(
        Technician.name,
        func.count(Ticket.id).label("count")
    ).join(Ticket).group_by(Technician.id).order_by(func.count(Ticket.id).desc()).limit(5).all()

    return render_template(
        "dashboard_rotator/dashboard_tv.html",
        technicians=technicians,
        performer_of_day={
            "name": performer_of_day.name if performer_of_day else "No Data",
            "count": performer_of_day.daily_tickets if performer_of_day else 0
        },
        performer_of_month={
            "name": performer_of_month.name if performer_of_month else "No Data",
            "count": performer_of_month.total_tickets if performer_of_month else 0
        },

        total_free=total_free,
        total_busy=total_busy,
        completed_tickets=completed_tickets,
        pending_tickets=pending_tickets,
        exceeded_time_techs=exceeded_time_techs,
        workload=workload
    )
