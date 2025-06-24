from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from app.extensions import db
from app.models import Ticket, Technician
from datetime import datetime, timedelta
import pandas as pd
from app.models import Assets, Ticket
from sqlalchemy.orm import aliased

from app.utils.permission_required import permission_required
from flask_login import login_required
from sqlalchemy import func
ticket1_bp = Blueprint("ticket1", __name__, template_folder="../templates/ticket1")


def generate_reference_number():
    """Generate a reference number in the format SR-YYMM-XXX."""
    current_year = datetime.utcnow().strftime('%y')  # '25' for 2025
    current_month = datetime.utcnow().strftime('%m')  # '02' for February

    prefix = f"SR-{current_year}{current_month}-"  # SR-2502-

    # Get the last ticket for the current month
    last_ticket = Ticket.query.filter(Ticket.reference_no.like(f"{prefix}%")).order_by(Ticket.id.desc()).first()

    if last_ticket:
        last_number = int(last_ticket.reference_no.split('-')[-1])  # Extract last number
        new_number = last_number + 1  # Increment
    else:
        new_number = 1  # Start series from 001

    return f"{prefix}{str(new_number).zfill(3)}"  # SR-2502-001


@ticket1_bp.route('/edit/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
@permission_required('can_edit_tickets')
def edit_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)

    if request.method == 'POST':
        try:
            ticket.title = request.form['title']
            ticket.description = request.form['description']
            ticket.customer = request.form['customer']
            ticket.call_type = request.form['call_type']
            ticket.technician_id = int(request.form['technician_id']) if request.form['technician_id'] else None
            ticket.estimated_time = int(request.form['estimated_time']) if request.form['estimated_time'] else None
            ticket.travel_time = int(request.form['travel_time']) if request.form['travel_time'] else None
            ticket.serial_number = request.form['serial_number']
            ticket.called_by = request.form['called_by']
            ticket.email_id = request.form['email_id']
            ticket.phone = request.form['phone']
            ticket.service_location = request.form['service_location']
            ticket.region = request.form['region']
            ticket.asset_Description = request.form['asset_description']  # Note: Fix naming mismatch
            ticket.action_taken = request.form['action_taken']
            ticket.complete = request.form['complete']
            ticket.mr_mono = request.form['mr_mono']
            ticket.mr_color = request.form['mr_color']

            new_status = request.form['status']
            previous_status = ticket.status  # Save old status first

            ticket.status = new_status  # ✅ Update first before condition

            if new_status == "Closed" and previous_status != "Closed":
                ticket.closed_at = datetime.utcnow()

                if ticket.call_type == "PM":
                    from app.models import Assets, PreventiveMaintenance
                    asset = Assets.query.filter_by(serial_number=ticket.serial_number).first()
                    if asset:
                        asset.last_pm_date = datetime.utcnow().strftime('%Y-%m-%d')

                        pm_entry = PreventiveMaintenance(
                            serial_number=ticket.serial_number,
                            scheduled_date=ticket.created_at.date(),
                            performed_date=ticket.closed_at.date(),
                            status="Completed",
                            remarks=ticket.action_taken or "PM done",
                            technician_name=ticket.technician.name if ticket.technician else "Unassigned"
                        )
                        db.session.add(pm_entry)

            ticket.status = new_status

            # ✅ Free up the technician only if they have no other pending tickets
            if ticket.status == "Closed" and ticket.technician_id:
                assigned_technician = Technician.query.get(ticket.technician_id)
                if assigned_technician:
                    # Check if the technician has other pending tickets
                    open_tickets = Ticket.query.filter_by(technician_id=ticket.technician_id).filter(
                        Ticket.status != "Closed").count()

                    if open_tickets == 0:  # Only mark as "Free" if no open tickets remain
                        assigned_technician.status = "Free"

            db.session.commit()
            flash("Ticket updated successfully!", "success")
            return redirect(url_for('ticket1.ticket_dashboard'))

        except Exception as e:
            flash(f"Error updating ticket: {str(e)}", "danger")

    technicians = Technician.query.all()
    return render_template('ticket1/edit_ticket.html', ticket=ticket, technicians=technicians)



@ticket1_bp.route('/new', methods=['GET', 'POST'])
@login_required
@permission_required('can_create_tickets')
def new_ticket():
    """Register a new ticket and mark technician as Busy"""
    if request.method == 'POST':
        serial_number = request.form.get('serial_number')
        customer_name = request.form.get('customer_name')
        service_location = request.form.get('service_location')
        region = request.form.get('region')
        asset_Description = request.form.get('asset_Description')
        title = request.form.get('title')
        description = request.form.get('description')
        called_by = request.form.get('called_by')
        email_id = request.form.get('email_id')
        phone = request.form.get('phone')
        call_type = request.form.get('call_type')
        technician_id = request.form.get('technician_id')
        estimated_time = int(request.form.get('estimated_time') or 60)
        travel_time = int(request.form.get('travel_time') or 15)

        expected_completion_time = datetime.utcnow() + timedelta(minutes=(estimated_time + travel_time))

        new_ticket = Ticket(
            reference_no=generate_reference_number(),
            serial_number=serial_number,
            customer=customer_name,
            service_location=service_location,
            region=region,
            asset_Description=asset_Description,
            title=title,
            description=description,
            called_by=called_by,
            email_id=email_id,
            phone=phone,
            call_type=call_type,
            technician_id=technician_id,
            estimated_time=estimated_time,
            travel_time=travel_time,
            status="Open",
            created_at=datetime.utcnow(),
            expected_completion_time=expected_completion_time
        )

        db.session.add(new_ticket)

        # ✅ Mark technician as "Busy" when assigned a ticket
        if technician_id:
            assigned_technician = Technician.query.get(technician_id)
            if assigned_technician:
                assigned_technician.status = "Busy"
                db.session.commit()

        flash("Ticket created successfully!", "success")
        return redirect(url_for('ticket1.ticket_dashboard'))

    technicians = Technician.query.all()
    return render_template('ticket1/new_ticket.html', technicians=technicians)

from datetime import date

@ticket1_bp.route('/dashboard', methods=['GET'])
@login_required
@permission_required('can_view_tickets')
def ticket_dashboard():
    """Render the ticket dashboard with extended filters and additional fields."""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status')
    customer = request.args.get('customer')
    serial_number = request.args.get('serial')  # Added filter for Serial Number
    technician = request.args.get('technician')  # Added filter for Technician Name
    region = request.args.get('region')  # Added filter for Region
    call_type = request.args.get('callType')  # Added filter for Call Type

    # Aliased Technician table to fetch technician name
    tech_alias = aliased(Technician)

    query = db.session.query(
        Ticket.reference_no, Ticket.title, Ticket.customer, Ticket.call_type,
        tech_alias.name.label("technician_name"), Ticket.expected_completion_time,
        Ticket.status, Ticket.created_at, Ticket.closed_at, Ticket.serial_number,
        Ticket.tat, Ticket.complete, Ticket.service_location, Ticket.region,
        Ticket.asset_Description, Ticket.called_by, Ticket.id
    ).outerjoin(tech_alias, tech_alias.id == Ticket.technician_id)

    # Apply filters
    if start_date:
        query = query.filter(Ticket.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Ticket.created_at <= datetime.strptime(end_date, '%Y-%m-%d'))
    if status:
        query = query.filter(Ticket.status == status)
    if customer:
        query = query.filter(Ticket.customer.ilike(f"%{customer}%"))
    if serial_number:
        query = query.filter(Ticket.serial_number.ilike(f"%{serial_number}%"))
    if technician:
        query = query.filter(tech_alias.name.ilike(f"%{technician}%"))
    if region:
        query = query.filter(Ticket.region.ilike(f"%{region}%"))
    if call_type:
        query = query.filter(Ticket.call_type.ilike(f"%{call_type}%"))

    tickets = query.order_by(Ticket.created_at.desc()).all()

    return render_template(
        'ticket1/dashboard.html',
        tickets=tickets,
        today=date.today(),
        total_open=sum(1 for t in tickets if t.status == 'Open'),
        total_in_progress=sum(1 for t in tickets if t.status == 'In Progress'),
        total_closed=sum(1 for t in tickets if t.status == 'Closed'),
        avg_resolution_time=round(
            sum((t.closed_at - t.created_at).total_seconds() for t in tickets if t.closed_at) / 3600 / max(1,
                                                                                                           len([t for t
                                                                                                                in
                                                                                                                tickets
                                                                                                                if
                                                                                                                t.closed_at])),
            1
        ),
        overdue_tickets=sum(1 for t in tickets if t.status == 'Open' and (date.today() - t.created_at.date()).days > 3)
    )


import pandas as pd
from flask import send_file, request
from io import BytesIO
from datetime import datetime



@ticket1_bp.route('/export', methods=['GET'])
@login_required
@permission_required('can_export_data')
def export_tickets():
    """Export only the filtered tickets to an Excel file."""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status')
    customer = request.args.get('customer')
    serial_number = request.args.get('serial')
    technician_name = request.args.get('technician')
    region = request.args.get('region')
    call_type = request.args.get('callType')

    tech_alias = aliased(Technician)
    query = db.session.query(
        Ticket.reference_no, Ticket.title, Ticket.customer, Ticket.call_type,
        tech_alias.name.label("technician_name"), Ticket.expected_completion_time,
        Ticket.status, Ticket.created_at, Ticket.closed_at, Ticket.serial_number,
        Ticket.tat, Ticket.complete, Ticket.service_location, Ticket.region,
        Ticket.asset_Description, Ticket.called_by
    ).outerjoin(tech_alias, tech_alias.id == Ticket.technician_id)

    # Apply filters
    if start_date:
        query = query.filter(Ticket.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Ticket.created_at <= datetime.strptime(end_date, '%Y-%m-%d'))
    if status:
        query = query.filter(Ticket.status == status)
    if customer:
        query = query.filter(Ticket.customer.ilike(f"%{customer}%"))
    if serial_number:
        query = query.filter(Ticket.serial_number.ilike(f"%{serial_number}%"))
    if technician_name:
        query = query.filter(tech_alias.name.ilike(f"%{technician_name}%"))
    if region:
        query = query.filter(Ticket.region.ilike(f"%{region}%"))
    if call_type:
        query = query.filter(Ticket.call_type.ilike(f"%{call_type}%"))

    tickets = query.order_by(Ticket.created_at.desc()).all()

    # Create formatted data
    data = []
    for ticket in tickets:
        ticket_data = {
            "Reference No": ticket.reference_no,
            "Title": ticket.title,
            "Customer": ticket.customer,
            "Call Type": ticket.call_type,
            "Technician": getattr(ticket, 'technician_name', "Unassigned"),
            "Expected Completion": ticket.expected_completion_time.strftime('%Y-%m-%d %H:%M:%S') if ticket.expected_completion_time else "",
            "Status": ticket.status,
            "Created At": ticket.created_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.created_at else "",
            "Closed At": ticket.closed_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.closed_at else "",
            "Serial No": ticket.serial_number,
            "TAT": ticket.tat,
            "Complete": ticket.complete,
            "Service Location": ticket.service_location,
            "Region": ticket.region,
            "Asset Description": ticket.asset_Description,
            "Called By": ticket.called_by
        }
        data.append(ticket_data)

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Filtered Tickets")

    output.seek(0)

    return send_file(output, as_attachment=True, download_name="filtered_tickets.xlsx")


@ticket1_bp.route('/search_asset', methods=['GET'])
def search_asset():
    """Render the Search Asset Page."""
    return render_template('ticket1/search_asset.html')
@ticket1_bp.route('/search_assets', methods=['GET'])
def search_assets():
    """Render the Search Asset Page."""
    return render_template('tickets/search_assets.html')

@ticket1_bp.route('/new_auto_populated_ticket', methods=['GET', 'POST'])
@login_required
@permission_required('can_create_tickets')
def new_auto_populated_ticket():
    """Render the ticket form with technician list and handle ticket creation"""
    if request.method == 'POST':
        serial_number = request.form.get('serial_number')
        customer_name = request.form.get('customer_name')
        service_location = request.form.get('service_location')
        region = request.form.get('region')
        asset_Description = request.form.get('asset_Description')
        title = request.form.get('title')
        description = request.form.get('description')
        called_by = request.form.get('called_by')
        email_id = request.form.get('email_id')
        phone = request.form.get('phone')
        call_type = request.form.get('call_type')
        technician_id = request.form.get('technician_id')
        estimated_time = int(request.form.get('estimated_time') or 60)
        travel_time = int(request.form.get('travel_time') or 15)

        # Calculate expected completion time
        from datetime import datetime, timedelta
        expected_completion_time = datetime.utcnow() + timedelta(minutes=estimated_time + travel_time)

        new_ticket = Ticket(
            reference_no=generate_reference_number(),
            serial_number=serial_number,
            customer=customer_name,
            service_location=service_location,
            region=region,
            asset_Description=asset_Description,
            title=title,
            description=description,
            called_by=called_by,
            email_id=email_id,
            phone=phone,
            call_type=call_type,
            technician_id=technician_id,
            estimated_time=estimated_time,
            travel_time=travel_time,
            expected_completion_time=expected_completion_time,
            status="Open",
            created_at=datetime.utcnow(),
        )
        db.session.add(new_ticket)
        if technician_id:
            assigned_technician = Technician.query.get(technician_id)
            if assigned_technician:
                assigned_technician.status = "Busy"

                db.session.commit()
        flash("Ticket created successfully!", "success")
        return redirect(url_for('ticket1.ticket_dashboard'))

    # ✅ Ensure it returns the correct template with available technicians
    technicians = Technician.query.all()
    return render_template('ticket1/new_auto_populated_ticket.html', technicians=technicians)


@ticket1_bp.route('/import_tickets', methods=['POST'])
def import_tickets():
    """Import tickets from a CSV file with BOM removal and correct datetime formatting."""
    if 'file' not in request.files:
        flash("No file uploaded", "danger")
        return redirect(url_for('ticket1.ticket_dashboard'))

    file = request.files['file']
    if file.filename == '':
        flash("No selected file", "danger")
        return redirect(url_for('ticket1.ticket_dashboard'))

    try:
        # ✅ Read CSV with proper encoding and remove BOM if it exists
        df = pd.read_csv(file, encoding='utf-8-sig')  # Removes BOM automatically

        # ✅ Debugging: Print CSV Columns to ensure correct header names
        print("CSV Columns:", df.columns.tolist())

        # ✅ Rename incorrect headers if needed
        if 'ï»¿id' in df.columns:
            df.rename(columns={'ï»¿id': 'id'}, inplace=True)

        # ✅ Ensure Date Fields are Properly Converted
        date_fields = ['created_at', 'closed_at', 'expected_completion_time']
        for field in date_fields:
            if field in df.columns:
                df[field] = pd.to_datetime(df[field], errors='coerce')  # Convert to datetime

        for _, row in df.iterrows():
            # ✅ Ensure correct datetime format
            created_at = row.get('created_at', datetime.utcnow())
            if pd.notna(created_at) and isinstance(created_at, pd.Timestamp):
                created_at = created_at.to_pydatetime()  # Convert to Python datetime

            closed_at = row.get('closed_at')
            if pd.notna(closed_at) and isinstance(closed_at, pd.Timestamp):
                closed_at = closed_at.to_pydatetime()

            expected_completion_time = row.get('expected_completion_time')
            if pd.isna(expected_completion_time):
                expected_completion_time = datetime.utcnow() + timedelta(minutes=60)  # Default 1 hour
            elif isinstance(expected_completion_time, pd.Timestamp):
                expected_completion_time = expected_completion_time.to_pydatetime()

            new_ticket = Ticket(
                id=row.get('id', None),  # If the ID is auto-generated, remove this line.
                reference_no=row.get('reference_no', generate_reference_number()),
                title=row.get('title', 'No title'),
                description=row.get('description', 'No description provided'),
                customer=row.get('customer', 'Unknown Customer'),
                call_type=row.get('call_type', 'Unknown'),
                technician_id=row.get('technician_id', None),
                estimated_time=int(row.get('estimated_time', 60)),
                travel_time=int(row.get('travel_time', 0)),
                expected_completion_time=expected_completion_time,
                status=row.get('status', 'Open'),
                created_at=created_at,
                closed_at=closed_at,
                serial_number=row.get('serial_number', 'N/A'),
                email_id=row.get('email_id', 'N/A'),
                phone=row.get('phone', 'N/A'),
                action_taken=row.get('action_taken', 'N/A'),
                tat=row.get('tat', None),
                complete=row.get('complete', ""),
                mr_mono=row.get('mr_mono', ""),
                mr_color=row.get('mr_color', ""),
                technician_email=row.get('technecian_email', 'N/A'),  # Assuming rename was done earlier
                service_location=row.get('service_location', 'N/A'),
                remaining_time=row.get('remaining_time', None),
                region=row.get('region', 'N/A'),
                asset_Description=row.get('asset_Description', 'N/A'),
                called_by=row.get('called_by', 'N/A')
            )

            print(f"Inserting Ticket: {new_ticket}")  # Debugging Step

            db.session.add(new_ticket)

        db.session.commit()
        flash("Tickets imported successfully!", "success")

    except Exception as e:
        print(f"Error importing tickets: {str(e)}")
        flash(f"Error importing tickets: {str(e)}", "danger")

    return redirect(url_for('ticket1.ticket_dashboard'))
@ticket1_bp.route('/check_serial/<serial_number>', methods=['GET'])
def check_serial(serial_number):
    """Fetch asset details based on serial number and return as JSON."""
    asset = Assets.query.filter_by(serial_number=serial_number).first()

    if asset:
        return jsonify({
            "customer_name": asset.customer_name,
            "service_location": asset.service_location,
            "region": asset.region,
            "asset_Description": asset.asset_Description
        })
    else:
        return jsonify({"error": "Serial Number not found"}), 404
@ticket1_bp.route('/load_tickets')
@login_required
@permission_required('can_view_tickets')
def load_tickets():
    page = request.args.get('page', 1, type=int)
    per_page = 100

    # Apply filters
    query = Ticket.query

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status')
    customer = request.args.get('customer')
    serial = request.args.get('serial')
    technician = request.args.get('technician')
    region = request.args.get('region')
    call_type = request.args.get('callType')

    if start_date:
        query = query.filter(Ticket.created_at >= start_date)
    if end_date:
        query = query.filter(Ticket.created_at <= end_date)
    if status:
        query = query.filter_by(status=status)
    if customer:
        query = query.filter(Ticket.customer.ilike(f'%{customer}%'))
    if serial:
        query = query.filter(Ticket.serial_number.ilike(f'%{serial}%'))
    if technician:
        query = query.filter(Ticket.technician_name.ilike(f'%{technician}%'))
    if region:
        query = query.filter(Ticket.region.ilike(f'%{region}%'))
    if call_type:
        query = query.filter(Ticket.call_type.ilike(f'%{call_type}%'))

    # Paginate and render ticket rows only
    tickets = query.order_by(Ticket.created_at.desc()).paginate(page=page, per_page=per_page)
    return render_template('ticket1/ticket_rows.html', tickets=tickets.items)

from flask import jsonify
from datetime import datetime, timedelta
from collections import defaultdict
from app.models import Ticket  # or however you import it

@ticket1_bp.route('/ticket_dashboard_summary_page')
@login_required
@permission_required('can_view_tickets')
def ticket_dashboard_summary_page():
    from datetime import datetime, timedelta

    now = datetime.now()
    from_str = request.args.get('from_date')
    to_str = request.args.get('to_date')

    from_date = datetime.strptime(from_str, "%Y-%m-%d") if from_str else now - timedelta(days=90)
    to_date = datetime.strptime(to_str, "%Y-%m-%d") + timedelta(days=1) if to_str else now

    technician = request.args.get('technician')

    query = Ticket.query.join(Technician, isouter=True)

    if from_date:
        query = query.filter(Ticket.created_at >= from_date)
    if to_date:
        query = query.filter(Ticket.created_at >= from_date, Ticket.created_at <= to_date)
    if technician:
        query = query.filter(Technician.name.ilike(f"%{technician}%"))

    tickets = query.all()
    now = datetime.utcnow()

    summary = {
        'open': sum(1 for t in tickets if t.status == 'Open'),
        'in_process': sum(1 for t in tickets if t.status == 'In Progress'),
        'closed': sum(1 for t in tickets if t.status == 'Closed'),
        'overdue': sum(1 for t in tickets if t.status == 'Open' and (now - t.created_at).days > 3),
        'avg_resolution': round(
            sum((t.closed_at - t.created_at).total_seconds() for t in tickets if t.closed_at) / 3600 / max(1, len([t for t in tickets if t.closed_at])),
            1
        )
    }

    # 🔸 Trends
    trend = defaultdict(lambda: {'opened': 0, 'closed': 0})
    for t in tickets:
        created_day = t.created_at.strftime('%Y-%m-%d')
        trend[created_day]['opened'] += 1
        if t.closed_at:
            closed_day = t.closed_at.strftime('%Y-%m-%d')
            trend[closed_day]['closed'] += 1

    sorted_days = sorted(trend.keys())
    trend_data = {
        'labels': sorted_days,
        'opened': [trend[day]['opened'] for day in sorted_days],
        'closed': [trend[day]['closed'] for day in sorted_days]
    }

    # 🔸 Alarming serials (≥3 in last 90 days)
    recent_cutoff = now - timedelta(days=90)
    recent_tickets = Ticket.query.filter(
        Ticket.created_at >= recent_cutoff,
        Ticket.call_type.ilike("CM"),
        Ticket.serial_number.isnot(None),
        func.length(func.trim(Ticket.serial_number)) > 0
    ).all()

    counter = defaultdict(list)
    for t in recent_tickets:
        if t.serial_number:
            counter[t.serial_number].append(t)

    alarming = []
    for serial, t_list in counter.items():
        if len(t_list) >= 3:
            last = sorted(t_list, key=lambda x: x.created_at, reverse=True)[0]
            alarming.append({
                'serial_number': serial,
                'customer_name': last.customer,
                'location': last.service_location,
                'region': last.region,
                'count': len(t_list),
                'last_date': last.created_at.strftime('%Y-%m-%d')
            })

    return render_template(
        'ticket1/ticket_dashboard.html',
        summary=summary,
        trend=trend_data,
        alarming=alarming
    )
@ticket1_bp.route('/technician_analytics')
@login_required
@permission_required('can_view_tickets')
def technician_analytics():
    from datetime import datetime, timedelta
    from collections import defaultdict
    from app.models import Technician, Ticket, spare_req

    today = datetime.today()
    default_from = today - timedelta(days=90)

    from_date_str = request.args.get('from_date') or default_from.strftime("%Y-%m-%d")
    to_date_str = request.args.get('to_date') or today.strftime("%Y-%m-%d")
    technician_name = request.args.get("technician")

    from_date = datetime.strptime(from_date_str, "%Y-%m-%d")
    to_date = datetime.strptime(to_date_str, "%Y-%m-%d")

    # 🔍 Resolve technician name
    technician_id = None
    if technician_name:
        tech = Technician.query.filter(Technician.name.ilike(f"%{technician_name}%")).first()
        if tech:
            technician_id = tech.id

    # 📊 Trends
    ticket_type_trend = defaultdict(lambda: defaultdict(int))
    resolution_trend = defaultdict(list)

    ticket_query = Ticket.query.filter(Ticket.created_at.between(from_date, to_date))
    if technician_id:
        ticket_query = ticket_query.filter(Ticket.technician_id == technician_id)

    all_tickets = ticket_query.all()
    closed_tickets = []

    for t in all_tickets:
        day = t.created_at.strftime('%Y-%m-%d')
        call_type = t.call_type.strip().upper() if t.call_type else "UNKNOWN"
        ticket_type_trend[day][call_type] += 1

        if t.closed_at:
            hrs = (t.closed_at - t.created_at).total_seconds() / 3600
            resolution_trend[day].append(hrs)
            closed_tickets.append(t)

    avg_resolution_by_day = {
        day: round(sum(times) / len(times), 1)
        for day, times in resolution_trend.items()
    }

    # 🧮 Working Days
    def working_days(start, end):
        return sum(1 for d in (start + timedelta(n) for n in range((end - start).days + 1)) if d.weekday() < 5)

    wd_total = working_days(from_date, to_date)
    total_closed = len(closed_tickets)
    avg_resolution = round(
        sum((t.closed_at - t.created_at).total_seconds() / 3600 for t in closed_tickets) / total_closed, 1
    ) if total_closed else 0
    overall_productivity = round(total_closed / max(wd_total, 1), 1)

    # 🛠 Warranty & FOC
    spare_q = spare_req.query.filter(spare_req.date.between(from_date, to_date))
    if technician_id:
        spare_q = spare_q.filter(spare_req.technician_id == technician_id)

    warranty_pending_total = spare_q.filter(spare_req.warranty_status == "Pending").count()
    foc_pending_total = spare_q.filter(
        (spare_req.foc_no == None) | (spare_req.foc_no == "") | (spare_req.foc_no == "Pending")
    ).count()

    # 👨 Per-Technician Analysis
    tech_filter = Technician.query.filter_by(id=technician_id) if technician_id else Technician.query.all()
    technicians = tech_filter if technician_id else tech_filter

    data = []
    for tech in technicians:
        t_q = Ticket.query.filter(
            Ticket.technician_id == tech.id,
            Ticket.created_at.between(from_date, to_date)
        )
        tickets = t_q.all()

        closed = [t for t in tickets if t.status and t.status.strip().lower() == "closed"]
        open_count = len([t for t in tickets if t.status and t.status.strip().lower() != "closed"])

        def count_type(call_type):
            return sum(1 for t in tickets if t.call_type and t.call_type.strip().lower() == call_type)

        call_types = ["pm", "cm", "myq", "installation", "mfi-central"]
        pm = count_type("pm")
        cm = count_type("cm")
        myq = count_type("myq")
        inst = count_type("installation")
        mfi_central = count_type("mfi-central")

        other = sum(1 for t in tickets if t.call_type and t.call_type.strip().lower() not in call_types)

        avg_res_time = round(
            sum((t.closed_at - t.created_at).total_seconds() / 3600 for t in closed) / len(closed), 1
        ) if closed else 0

        spare_q = spare_req.query.filter(
            spare_req.technician_id == tech.id,
            spare_req.date.between(from_date, to_date)
        )
        warranty_pending = spare_q.filter(spare_req.warranty_status == "Pending").count()
        foc_pending = spare_q.filter(
            (spare_req.foc_no == None) | (spare_req.foc_no == "") | (spare_req.foc_no == "Pending")
        ).count()

        productivity = round(len(closed) / max(wd_total, 1), 1)

        data.append({
            "name": tech.name,
            "open": open_count,
            "closed": len(closed),
            "pm": pm,
            "cm": cm,
            "myq": myq,
            "install": inst,
            "mfi_central": mfi_central,
            "other": other,
            "avg_resolution": avg_res_time,
            "warranty_pending": warranty_pending,
            "foc_pending": foc_pending,
            "productivity": productivity
        })

    totals = {
        "open": sum(t["open"] for t in data),
        "closed": sum(t["closed"] for t in data),
        "pm": sum(t["pm"] for t in data),
        "cm": sum(t["cm"] for t in data),
        "myq": sum(t["myq"] for t in data),
        "install": sum(t["install"] for t in data),
        "mfi_central": sum(t["mfi_central"] for t in data),
        "other": sum(t["other"] for t in data),
        "warranty_pending": sum(t["warranty_pending"] for t in data),
        "foc_pending": sum(t["foc_pending"] for t in data),
    }

    all_techs = Technician.query.order_by(Technician.name).all()

    return render_template("ticket1/technician_analytics.html",
                           ticket_type_trend=dict(ticket_type_trend),
                           avg_resolution_by_day=avg_resolution_by_day,
                           data=data,
                           filters={
                               "from_date": from_date_str,
                               "to_date": to_date_str,
                               "technician": technician_name
                           },
                           summary={
                               "total": len(all_tickets),
                               "closed": total_closed,
                               "avg_resolution": avg_resolution,
                               "warranty_pending": warranty_pending_total,
                               "foc_pending": foc_pending_total,
                               "productivity": overall_productivity
                           },
                           all_technicians=all_techs,
                           totals=totals)

@ticket1_bp.route('/export_technician_excel')
@login_required
@permission_required('can_export_data')
def export_technician_excel():
    import pandas as pd
    from flask import send_file
    from io import BytesIO

    # Reuse your analytics logic to rebuild `data` list
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    technician = request.args.get('technician')

    # 👇 Reuse the logic from technician_analytics to get `data`
    # You can refactor data generation to a shared function if preferred

    # Placeholder - replace this with real technician summary logic
    data = [
        {"Technician": "John", "Open": 2, "Closed": 5, "PM": 2, "CM": 1, "MYQ": 1, "Install": 0, "Other": 1,
         "Avg Resolution": 2.5, "Warranty Pending": 1, "FOC Pending": 0, "Productivity": 1.2}
    ]

    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False, sheet_name='Technician Performance')
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='technician_performance.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@ticket1_bp.route('/export_technician_pdf')
@login_required
@permission_required('can_export_data')
def export_technician_pdf():
    from flask import render_template, make_response
    from xhtml2pdf import pisa
    from io import BytesIO
    from datetime import datetime

    from_date = request.args.get('from_date') or '2025-01-01'
    to_date = request.args.get('to_date') or datetime.today().strftime("%Y-%m-%d")
    technician = request.args.get('technician')

    # 👇 Replace this with your real data generation logic
    data = [
        {"name": "John Doe", "open": 3, "closed": 5, "pm": 2, "cm": 1, "myq": 1, "install": 0, "other": 1,
         "avg_resolution": 2.5, "warranty_pending": 1, "foc_pending": 0, "productivity": 1.2}
    ]
    summary = {
        "total": 8, "closed": 5, "avg_resolution": 2.5,
        "warranty_pending": 1, "foc_pending": 0, "productivity": 1.2
    }
    filters = {"from_date": from_date, "to_date": to_date, "technician": technician}

    html = render_template("ticket1/technician_export_pdf.html", data=data, summary=summary, filters=filters)

    result = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=result)

    if pisa_status.err:
        return f"PDF generation failed: {pisa_status.err}"

    result.seek(0)
    response = make_response(result.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=technician_dashboard.pdf"
    return response
@ticket1_bp.route('/export_alarming_cases')
@login_required
@permission_required('can_export_data')
def export_alarming_cases():
    from io import BytesIO
    import pandas as pd

    now = datetime.utcnow()
    recent_cutoff = now - timedelta(days=90)
    recent_tickets = Ticket.query.filter(
        Ticket.created_at >= recent_cutoff,
        Ticket.call_type.ilike("CM"),
        Ticket.serial_number.isnot(None),
        func.length(func.trim(Ticket.serial_number)) > 0
    ).all()

    from collections import defaultdict
    counter = defaultdict(list)
    for t in recent_tickets:
        if t.serial_number:
            counter[t.serial_number].append(t)

    alarming = []
    for serial, t_list in counter.items():
        if len(t_list) >= 3:
            last = sorted(t_list, key=lambda x: x.created_at, reverse=True)[0]
            alarming.append({
                "Serial Number": serial,
                "Customer Name": last.customer,
                "Location": last.service_location,
                "Region": last.region,
                "Ticket Count": len(t_list),
                "Last Ticket Date": last.created_at.strftime('%Y-%m-%d')
            })

    df = pd.DataFrame(alarming)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(output, as_attachment=True, download_name="alarming_cases.xlsx")

@ticket1_bp.route('/create_pm_ticket')
@login_required
@permission_required('can_create_tickets')
def create_pm_ticket():
    from app.models import Assets, Ticket, Technician

    serial = request.args.get('serial_number')
    asset = Assets.query.filter_by(serial_number=serial).first()

    if not asset:
        flash(f"No asset found for Serial No: {serial}", "danger")
        return redirect(url_for('assets.pm_dashboard'))

    # ✅ Match technician using email (recommended and reliable)
    technician_id = None
    assigned_name = "Unassigned"

    if asset.technician_email:
        tech = Technician.query.filter(
            Technician.email.ilike(asset.technician_email.strip())
        ).first()

        if tech:
            technician_id = tech.id
            assigned_name = tech.name
            tech.status = "Busy"
            db.session.commit()  # Update tech status

    # ✅ Create the PM ticket
    ticket = Ticket(
        reference_no=generate_reference_number(),
        serial_number=asset.serial_number,
        customer=asset.customer_name,
        service_location=asset.service_location,
        region=asset.region,
        asset_Description=asset.asset_Description,
        title="Preventive Maintenance",
        description="Auto-generated PM ticket",
        called_by="System",
        call_type="PM",
        technician_id=technician_id,
        estimated_time=60,
        travel_time=15,
        expected_completion_time=datetime.utcnow() + timedelta(minutes=75),
        status="Open",
        created_at=datetime.utcnow()
    )

    db.session.add(ticket)
    db.session.commit()

    flash(f"✅ PM Ticket created for {serial} and assigned to: {assigned_name}", "success")
    return redirect(url_for('assets.pm_dashboard'))

# ✅ New route: Create PM tickets in bulk with optional filters
# ✅ Bulk PM Ticket Creation with Technician Email Matching
@ticket1_bp.route('/create_pm_bulk', methods=['POST', 'GET'])
@login_required
@permission_required('can_create_tickets')
def create_pm_bulk():
    from app.models import Assets, Ticket, Technician

    filters = {
        "customer_name": request.args.get("customer_name"),
        "service_location": request.args.get("service_location"),
        "region": request.args.get("region"),
        "technician_name": request.args.get("technician_name")
    }

    today = datetime.today().date()
    created = 0

    query = Assets.query
    for field, value in filters.items():
        if value:
            query = query.filter(getattr(Assets, field).ilike(f"%{value}%"))

    assets = query.all()
    for asset in assets:
        try:
            if asset.last_pm_date and asset.pm_freq:
                last_pm = datetime.strptime(asset.last_pm_date, '%Y-%m-%d').date()
                freq_days = int(asset.pm_freq.split()[0])
                next_due = last_pm + timedelta(days=freq_days)

                existing_pm = Ticket.query.filter_by(
                    serial_number=asset.serial_number,
                    call_type='PM'
                ).filter(Ticket.status.in_(["Open", "In Progress"])).first()

                if next_due <= today and not existing_pm:
                    technician_id = None
                    if asset.technician_email:
                        tech = Technician.query.filter(Technician.email.ilike(asset.technician_email.strip())).first()
                        if tech:
                            technician_id = tech.id
                            tech.status = "Busy"

                    ticket = Ticket(
                        reference_no=generate_reference_number(),
                        serial_number=asset.serial_number,
                        customer=asset.customer_name,
                        service_location=asset.service_location,
                        region=asset.region,
                        asset_Description=asset.asset_Description,
                        title="Preventive Maintenance",
                        description="Auto-generated bulk PM ticket",
                        called_by="System",
                        call_type="PM",
                        technician_id=technician_id,
                        estimated_time=60,
                        travel_time=15,
                        expected_completion_time=datetime.utcnow() + timedelta(minutes=75),
                        status="Open",
                        created_at=datetime.utcnow()
                    )

                    db.session.add(ticket)
                    created += 1
        except Exception as e:
            print(f"Error creating ticket for {asset.serial_number}: {e}")
            continue

    db.session.commit()
    flash(f"✅ {created} PM tickets created in bulk.", "success")
    return redirect(url_for('assets.pm_dashboard'))
