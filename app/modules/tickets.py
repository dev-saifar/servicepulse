from flask import Blueprint, render_template, request, jsonify, send_file
import sqlite3
import uuid
from datetime import datetime, timedelta
import pandas as pd
from app.models import Ticket, Technician, Assets  # Correct import
from app.extensions import db  # Ensure db extension is used

tickets_bp = Blueprint('tickets', __name__, template_folder='../../templates/tickets')

# Database connection function
def get_db_connection():
    conn = sqlite3.connect('techtrack.db')  # Ensure correct DB name
    conn.row_factory = sqlite3.Row
    return conn

# Load Ticket Registration Page (Previously `register_ticket.html`, now `dashboard.html`)
@tickets_bp.route("/dashboard")
def dashboard():
    return render_template("tickets/dashboard.html")  # Renamed for clarity

# Fetch asset details based on Serial Number
@tickets_bp.route("/fetch_asset/<serial>")
def fetch_asset(serial):
    conn = get_db_connection()
    asset = conn.execute("SELECT * FROM Assets WHERE serial_number = ?", (serial,)).fetchone()
    conn.close()

    if asset:
        return jsonify(dict(asset))
    else:
        return jsonify({"error": "Asset not found. Enter details manually."})  # Allow manual input

# Fetch available technicians
@tickets_bp.route("/fetch_technicians")
def fetch_technicians():
    conn = get_db_connection()
    technicians = conn.execute("SELECT id, name, status FROM technician").fetchall()
    conn.close()
    return jsonify([dict(tech) for tech in technicians])

@tickets_bp.route("/create_ticket", methods=["GET", "POST"])
def create_ticket():
    if request.method == "POST":
        serial_number = request.form.get("serial_number", None)
        customer = request.form.get("customer_name")
        title = request.form.get("title")
        call_type = request.form.get("call_type")
        description = request.form.get("description")
        technician_id = request.form.get("technician_id")  # Nullable
        status = "Open"
        reference_no = str(uuid.uuid4())[:8]  # Generate Unique Reference No
        created_at = datetime.utcnow()

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO ticket (reference_no, serial_number, customer, title, call_type, description, technician_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (reference_no, serial_number, customer, title, call_type, description, technician_id, status, created_at))
        conn.commit()
        conn.close()

        flash("Ticket Created Successfully!", "success")
        return redirect(url_for("tickets.index"))

    return render_template("tickets/register_ticket.html")


@tickets_bp.route("/fetch_tickets")
def fetch_tickets():
    conn = get_db_connection()
    tickets = conn.execute("""
           SELECT id, reference_no, title, customer, call_type, technician_id, 
                  estimated_time, travel_time, status, created_at 
           FROM ticket ORDER BY created_at DESC
       """).fetchall()
    conn.close()

    # Convert SQLite Row Objects to Dictionaries
    tickets_list = []
    for ticket in tickets:
        tickets_list.append({
            "id": ticket["id"],
            "reference_no": ticket["reference_no"],
            "title": ticket["title"],
            "customer": ticket["customer"],
            "call_type": ticket["call_type"],
            "technician_id": ticket["technician_id"],
            "estimated_time": ticket["estimated_time"] if ticket["estimated_time"] else "None",
            "travel_time": ticket["travel_time"] if ticket["travel_time"] else "None",
            "status": ticket["status"],
            "created_at": ticket["created_at"].strftime('%Y-%m-%d %H:%M')
        })

    return jsonify(tickets_list)


# Update ticket details
@tickets_bp.route("/update_ticket", methods=["POST"])
def update_ticket():
    data = request.form
    conn = get_db_connection()
    conn.execute("""
        UPDATE ticket SET title = ?, status = ? WHERE reference_no = ?
    """, (data["title"], data["status"], data["reference_no"]))
    conn.commit()
    conn.close()
    return jsonify({"message": "Ticket updated successfully!"})

# Export tickets to Excel
@tickets_bp.route("/export_tickets")
def export_tickets():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM ticket", conn)
    conn.close()
    df.to_excel("tickets.xlsx", index=False)
    return send_file("tickets.xlsx", as_attachment=True)
@tickets_bp.route("/edit_ticket/<int:ticket_id>", methods=["GET", "POST"])
def edit_ticket(ticket_id):
    conn = get_db_connection()
    ticket = conn.execute("SELECT * FROM ticket WHERE id = ?", (ticket_id,)).fetchone()

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        status = request.form["status"]
        action_taken = request.form["action_taken"]

        conn.execute("""
            UPDATE ticket 
            SET title = ?, description = ?, status = ?, action_taken = ?
            WHERE id = ?
        """, (title, description, status, action_taken, ticket_id))
        conn.commit()
        conn.close()
        return redirect(url_for("tickets.index"))

    conn.close()
    return render_template("tickets/edit_ticket.html", ticket=ticket)

@tickets_bp.route('/register_ticket1', methods=['GET', 'POST'])
def register_ticket():
    """Handles ticket creation"""
    technicians = Technician.query.all()  # ✅ Fetch technicians

    if request.method == 'POST':
        try:
            # ✅ Collect form data
            title = request.form.get('title')
            description = request.form.get('description')
            serial_number = request.form.get('serial_number')
            customer_name = request.form.get('customer_name')
            email_id = request.form.get('email_id')
            phone = request.form.get('phone')
            call_type = request.form.get('call_type')
            technician_id = request.form.get('technician_id') or None
            estimated_time = request.form.get('estimated_time') or 60
            travel_time = request.form.get('travel_time') or 15

            # ✅ Convert to integer
            estimated_time = int(estimated_time)
            travel_time = int(travel_time)

            # ✅ Generate Unique Reference Number
            reference_no = str(uuid.uuid4())[:8]

            # ✅ Calculate expected completion time
            expected_completion_time = datetime.utcnow() + timedelta(minutes=estimated_time + travel_time)

            # ✅ Create new ticket instance
            new_ticket = Ticket(
                reference_no=reference_no,
                title=title,
                description=description,
                serial_number=serial_number,
                customer=customer_name,
                call_type=call_type,
                technician_id=technician_id,
                email_id=email_id,
                phone=phone,
                estimated_time=estimated_time,
                travel_time=travel_time,
                status="Open",
                created_at=datetime.utcnow(),
                expected_completion_time=expected_completion_time
            )

            # ✅ Add to DB & commit
            db.session.add(new_ticket)
            db.session.commit()

            flash("Ticket created successfully!", "success")
            return redirect(url_for('tickets.index'))  # Redirect to ticket dashboard

        except Exception as e:
            db.session.rollback()  # ✅ Rollback on error
            flash(f"Error: {str(e)}", "danger")
            print("Error saving ticket:", str(e))  # ✅ Debugging log

    return render_template('tickets/make_ticket.html', technicians=technicians)

@tickets_bp.route("/")
def index():
    conn = get_db_connection()
    tickets = conn.execute("SELECT * FROM ticket").fetchall()
    conn.close()

    # Convert `created_at` safely
    formatted_tickets = []
    for ticket in tickets:
        ticket_dict = dict(ticket)
        try:
            # Correctly parse microseconds if present
            ticket_dict["created_at"] = datetime.strptime(ticket["created_at"], "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            # Fallback for timestamps without microseconds
            ticket_dict["created_at"] = datetime.strptime(ticket["created_at"], "%Y-%m-%d %H:%M:%S")

        formatted_tickets.append(ticket_dict)

    return render_template("tickets/index.html", tickets=formatted_tickets)

@tickets_bp.route("/dashboard-data")
def dashboard_data():
    conn = get_db_connection()
    tickets = conn.execute("SELECT * FROM ticket").fetchall()
    conn.close()
    return jsonify([dict(ticket) for ticket in tickets])  # Ensure it returns valid data
@tickets_bp.route("/update_status/<int:ticket_id>", methods=["POST"])
def update_status(ticket_id):
    new_status = request.form.get("status")

    conn = get_db_connection()
    conn.execute("UPDATE ticket SET status = ? WHERE id = ?", (new_status, ticket_id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Ticket status updated successfully!"})
@tickets_bp.route("/make_ticket", methods=["GET"])
def make_ticket():
    """Render the make_ticket.html form with pre-filled data from query parameters."""
    serial_number = request.args.get("serial_number", "")
    customer_name = request.args.get("customer_name", "")
    service_location = request.args.get("service_location", "")
    region = request.args.get("region", "")
    asset_description = request.args.get("asset_description", "")

    # ✅ Fetch all available technicians
    technicians = Technician.query.all()

    return render_template("tickets/make_ticket.html",
                           serial_number=serial_number,
                           customer_name=customer_name,
                           service_location=service_location,
                           region=region,
                           asset_description=asset_description,
                           technicians=technicians)  # ✅ Pass the technicians list

@tickets_bp.route('/search_assets', methods=['GET', 'POST'])
def search_assets():
    """ Fetch assets from the database based on search filters """
    try:
        if request.method == "GET":
            return render_template("tickets/search_assets.html")  # Ensure this template exists

        data = request.get_json()
        print("Received search filters:", data)  # Debugging log

        query = Assets.query

        if data.get('serial_number'):
            query = query.filter(Assets.serial_number.ilike(f"%{data['serial_number']}%"))
        if data.get('customer_name'):
            query = query.filter(Assets.customer_name.ilike(f"%{data['customer_name']}%"))
        if data.get('service_location'):
            query = query.filter(Assets.service_location.ilike(f"%{data['service_location']}%"))
        if data.get('region'):
            query = query.filter(Assets.region.ilike(f"%{data['region']}%"))

        results = query.all()

        if not results:
            return jsonify({"message": "No assets found"}), 404  # Return 404 if no assets found

        print("Found assets:", results)  # Debugging log

        return jsonify([{
            "serial_number": asset.serial_number,
            "customer_name": asset.customer_name,
            "service_location": asset.service_location,
            "region": asset.region,
            "asset_description": getattr(asset, "asset_Description", "N/A")  # Handle missing field
        } for asset in results])

    except Exception as e:
        print("Error in /search_assets:", str(e))  # Log the error in Flask console
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


