from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from app.extensions import db
from app.models import Ticket, Technician
from datetime import datetime, timedelta
import pandas as pd
from app.models import Assets, Ticket
from sqlalchemy.orm import aliased

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

            new_status = request.form['status']

            # ✅ Log closed timestamp when status changes to "Closed"
            if new_status == "Closed" and ticket.status != "Closed":
                ticket.closed_at = datetime.utcnow()

            ticket.status = new_status

            # ✅ Free up the technician if the ticket is marked "Closed"
            if ticket.status == "Closed" and ticket.technician_id:
                assigned_technician = Technician.query.get(ticket.technician_id)
                if assigned_technician:
                    assigned_technician.status = "Free"

            db.session.commit()
            flash("Ticket updated successfully!", "success")
            return redirect(url_for('ticket1.ticket_dashboard'))

        except Exception as e:
            flash(f"Error updating ticket: {str(e)}", "danger")

    technicians = Technician.query.all()
    return render_template('ticket1/edit_ticket.html', ticket=ticket, technicians=technicians)


@ticket1_bp.route('/new', methods=['GET', 'POST'])
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


@ticket1_bp.route('/dashboard', methods=['GET'])

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

    return render_template('ticket1/dashboard.html', tickets=tickets)


import pandas as pd
from flask import send_file, request
from io import BytesIO
from datetime import datetime


def export_tickets():
    """Export only the filtered tickets to an Excel file."""

    # Get filter parameters from request
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status')
    customer = request.args.get('customer')

    # Start query
    query = Ticket.query

    # Apply filters if present
    if start_date:
        query = query.filter(Ticket.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Ticket.created_at <= datetime.strptime(end_date, '%Y-%m-%d'))
    if status:
        query = query.filter(Ticket.status == status)
    if customer:
        query = query.filter(Ticket.customer.ilike(f"%{customer}%"))

    # Fetch only the filtered records
    tickets = query.order_by(Ticket.created_at.desc()).all()

    # ✅ Ensure correct field names match UI table
    data = [
        {
            "Reference No": ticket.reference_no,
            "Title": ticket.title,
            "Customer": ticket.customer,
            "Call Type": ticket.call_type,
            "Technician": ticket.technician.name if ticket.technician else "Unassigned",
            "Expected Completion": ticket.expected_completion_time.strftime(
                '%Y-%m-%d %H:%M:%S') if ticket.expected_completion_time else "",
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
        for ticket in tickets
    ]

    # Create Excel file
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Filtered Tickets")

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="filtered_tickets.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@ticket1_bp.route('/export', methods=['GET'])
def export_tickets():
    """Export only the filtered tickets to an Excel file."""

    # Get filter parameters from request
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status')
    customer = request.args.get('customer')

    # Start query
    query = Ticket.query

    # Apply filters if present
    if start_date:
        query = query.filter(Ticket.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Ticket.created_at <= datetime.strptime(end_date, '%Y-%m-%d'))
    if status:
        query = query.filter(Ticket.status == status)
    if customer:
        query = query.filter(Ticket.customer.ilike(f"%{customer}%"))

    # Fetch only the filtered records
    tickets = query.order_by(Ticket.created_at.desc()).all()

    # ✅ Ensure correct field names match UI table
    data = [
        {
            "Reference No": ticket.reference_no,
            "Title": ticket.title,
            "Customer": ticket.customer,
            "Call Type": ticket.call_type,
            "Technician": ticket.technician.name if ticket.technician else "Unassigned",
            "Expected Completion": ticket.expected_completion_time.strftime(
                '%Y-%m-%d %H:%M:%S') if ticket.expected_completion_time else "",
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
        for ticket in tickets
    ]

    # Create Excel file
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Filtered Tickets")

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="filtered_tickets.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

@ticket1_bp.route('/search_asset', methods=['GET'])
def search_asset():
    """Render the Search Asset Page."""
    return render_template('ticket1/search_asset.html')
@ticket1_bp.route('/search_assets', methods=['GET'])
def search_assets():
    """Render the Search Asset Page."""
    return render_template('tickets/search_assets.html')

@ticket1_bp.route('/new_auto_populated_ticket', methods=['GET', 'POST'])
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
