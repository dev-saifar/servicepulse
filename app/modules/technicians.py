from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime, timedelta
from app.extensions import db
from app.models import Technician, Ticket
from sqlalchemy import func
from flask_login import login_required
from app.utils.permission_required import permission_required

technicians_bp = Blueprint('technicians', __name__, template_folder='../templates/technicians')

@technicians_bp.route('/')
@login_required
@permission_required('can_view_technicians')
def index():
    technicians = db.session.query(
        Technician.id,
        Technician.name,
        Technician.status,
        func.concat(
            func.coalesce(Ticket.region, ' '),
            ' - ',
            func.coalesce(Ticket.service_location, ' '),
            ' - ',
            func.coalesce(Ticket.customer, ' ')
        ).label('last_location'),
        db.func.count(Ticket.id).filter(Ticket.created_at >= datetime.utcnow().date()).label('calls_today'),
        db.func.coalesce(Ticket.expected_completion_time, datetime.utcnow()).label('expected_free_time')
    ).outerjoin(Ticket, Technician.id == Ticket.technician_id) \
        .group_by(Technician.id).all()

    technician_list = []
    for tech in technicians:
        minutes_left = max((tech.expected_free_time - datetime.utcnow()).total_seconds() / 60, 0)
        progress_percentage = min(100, (minutes_left / 60) * 100)

        technician_list.append({
            "id": tech.id,
            "name": tech.name,
            "status": tech.status,
            "last_location": tech.last_location,
            "calls_today": tech.calls_today,
            "minutes_left": int(minutes_left),
            "progress_percentage": int(progress_percentage),
        })

    return render_template('technicians/index.html', technicians=technician_list)


@technicians_bp.route('/add', methods=['GET', 'POST'])
@login_required
@permission_required('can_add_technicians')
def add_technician():
    if request.method == 'POST':
        name = request.form['name']
        mobile = request.form['mobile']
        email = request.form['email']

        if not name or not mobile or not email:
            flash("All fields are required!", "error")
            return redirect(url_for('technicians.add_technician'))

        new_technician = Technician(name=name, mobile=mobile, email=email, status="Free")
        db.session.add(new_technician)
        db.session.commit()
        flash("Technician added successfully!", "success")
        return redirect(url_for('technicians.index'))

    return render_template('technicians/add_technician.html')


@technicians_bp.route('/import', methods=['GET', 'POST'])
@login_required
@permission_required('can_add_technicians')
def import_technicians():
    if request.method == 'POST':
        file = request.files['file']
        if not file:
            flash("No file selected!", "error")
            return redirect(url_for('technicians.import_technicians'))

        import csv
        from io import TextIOWrapper

        file_stream = TextIOWrapper(file.stream, encoding='utf-8')
        csv_reader = csv.reader(file_stream)
        next(csv_reader)  # Skip header row

        for row in csv_reader:
            if len(row) < 3:
                continue
            name, mobile, email = row[:3]
            technician = Technician(name=name, mobile=mobile, email=email, status="Free")
            db.session.add(technician)

        db.session.commit()
        flash("Technicians imported successfully!", "success")
        return redirect(url_for('technicians.index'))

    return render_template('technicians/import_technicians.html')


@technicians_bp.route('/edit/<int:tech_id>', methods=['GET', 'POST'])
@login_required
@permission_required('can_edit_technicians')
def edit_technician(tech_id):
    technician = Technician.query.get_or_404(tech_id)
    if request.method == 'POST':
        technician.name = request.form['name']
        db.session.commit()
        return redirect(url_for('technicians.index'))
    return render_template('technicians/edit.html', technician=technician)


@technicians_bp.route('/delete/<int:tech_id>', methods=['POST'])
@login_required
@permission_required('can_edit_technicians')
def delete_technician(tech_id):
    technician = Technician.query.get_or_404(tech_id)
    db.session.delete(technician)
    db.session.commit()
    flash('Technician deleted successfully!', 'success')
    return redirect(url_for('technicians.index'))
