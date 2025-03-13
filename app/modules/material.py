from flask import Blueprint, render_template, request, jsonify
from app.extensions import db
from app.models import spares, Technician, spare_req, Assets
from datetime import datetime
from flask import send_file
from flask import send_file
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
material_bp = Blueprint('material', __name__, template_folder='../templates/material')

@material_bp.route('/dashboard', methods=['GET'])
def material_dashboard():
    return render_template('material/material_dashboard.html')

@material_bp.route('/fetch_asset/<serial_number>', methods=['GET'])
def fetch_asset(serial_number):
    serial_number = serial_number.strip()

    asset = Assets.query.filter_by(serial_number=serial_number).first()
    if not asset:
        return jsonify({"error": "Asset not found"}), 404

    return jsonify({
        "customer_name": asset.customer_name,
        "service_location": asset.service_location,
        "region": asset.region,
        "contract": asset.contract,
        "contract_expiry_date": asset.contract_expiry_date,
        "asset_Description": asset.asset_Description
    })

# Fetch technician list
@material_bp.route('/fetch_technicians', methods=['GET'])
def fetch_technicians():
    technicians = Technician.query.all()
    tech_list = [{"id": tech.id, "name": tech.name} for tech in technicians]
    return jsonify(tech_list)

# Fetch spare part details
@material_bp.route('/fetch_spare/<part_number>', methods=['GET'])
def fetch_spare(part_number):
    part_number = part_number.strip()
    spare = spares.query.filter_by(material_nr=part_number).first()
    return jsonify({"description": spare.material_desc}) if spare else jsonify({"error": "Not found"}), 404

# Fetch previous reading for a specific serial number and part number
@material_bp.route('/fetch_previous_reading/<serial_number>/<part_number>', methods=['GET'])
def fetch_previous_reading(serial_number, part_number):
    spare_entry = spare_req.query.filter(
        spare_req.serial_number == serial_number,
        spare_req.product_code == part_number
    ).order_by(spare_req.date.desc()).first()

    return jsonify({"previous_reading": spare_entry.reading if spare_entry else 0})

# Fetch warranty pending count and FOC return pending count for a technician
@material_bp.route('/fetch_pending_counts/<int:technician_id>', methods=['GET'])
def fetch_pending_counts(technician_id):
    """ Fetch count of warranty pending and FOC return pending for a technician """
    warranty_pending = spare_req.query.filter(
        spare_req.technician_id == technician_id,
        spare_req.warranty_status == "Pending"
    ).count()

    foc_pending = spare_req.query.filter(
        spare_req.technician_id == technician_id,
        (spare_req.foc_no == None) | (spare_req.foc_no == '')
    ).count()

    return jsonify({
        "warranty_pending": warranty_pending,
        "foc_pending": foc_pending
    })

from math import ceil

@material_bp.route('/fetch_requests', methods=['GET'])
def fetch_requests():
    """ Fetch paginated requests with filtering options """
    page = request.args.get('page', 1, type=int)
    per_page = 500  # ✅ Set pagination to 500 records per page

    from_date = request.args.get('fromDate')
    to_date = request.args.get('toDate')

    # Filters for search
    filters = {
        "id": request.args.get("filterId"),
        "serial_number": request.args.get("filterSerial"),
        "asset_Description": request.args.get("filterAsset"),
        "technician_name": request.args.get("filterTechnician"),
        "warehouse": request.args.get("filterWarehouse"),
        "product_code": request.args.get("filterProduct"),
        "description": request.args.get("filterDescription"),
        "warranty_status": request.args.get("filterStatus")
    }

    query = spare_req.query

    # ✅ Proper Date Filtering
    if from_date:
        from_date = datetime.strptime(from_date, "%Y-%m-%d")
        query = query.filter(spare_req.date >= from_date)
    if to_date:
        to_date = datetime.strptime(to_date, "%Y-%m-%d")
        query = query.filter(spare_req.date <= to_date)

    # ✅ Apply other search filters
    for key, value in filters.items():
        if value:
            query = query.filter(getattr(spare_req, key).ilike(f"%{value}%"))

    # ✅ Get total record count & calculate total pages
    total_records = query.count()
    total_pages = ceil(total_records / per_page)

    # ✅ Paginate the query
    requests = query.order_by(spare_req.date.desc()).paginate(page=page, per_page=per_page, error_out=False)

    request_list = [{
        "id": req.id,
        "date": req.date.strftime('%Y-%m-%d'),  # ✅ Ensure proper date format
        "customer_name": req.customer_name,
        "foc_no": req.foc_no,
        "serial_number": req.serial_number,
        "asset_Description": req.asset_Description,
        "technician_name": req.technician_name,
        "warehouse": req.warehouse,
        "product_code": req.product_code,
        "description": req.description,
        "warranty_status": req.warranty_status
    } for req in requests.items]

    return jsonify({
        "requests": request_list,
        "total_pages": total_pages  # ✅ Send total pages to frontend

    })
import uuid  # ✅ Import UUID to generate unique request IDs

@material_bp.route('/submit_request', methods=['POST'])
def submit_request():
    """Handles spare request submission and saves data to the database."""
    data = request.json  # Get JSON data from frontend
    print("Received Data:", data)  # Debugging output

    if not isinstance(data, list):  # Ensure data is a list
        flash("❌ Invalid data format. Expected a list of requests.", "error")
        return render_template("material/material_dashboard.html")

    try:
        last_inserted_id = None  # To store last request ID
        request_id = str(uuid.uuid4())  # ✅ Generate a unique request_id for this batch

        for item in data:  # Process each item in the list
            spare_request = spare_req(
                serial_number=item['serial_number'],
                asset_Description=item['asset_Description'],
                technician_id=int(item['technician_id']) if item['technician_id'].isdigit() else None,
                technician_name=item['technician_name'],
                reading=int(item['reading']) if item['reading'].isdigit() else 0,
                date=datetime.now(),
                request_id=request_id,  # ✅ Assign same request_id to all items
                customer_name=item['customer_name'],
                service_location=item['service_location'],
                region=item['region'],
                contract=item['contract'],
                contract_expiry_date=item.get('contract_expiry_date', None),
                product_code=item['product_code'],
                description=item['description'],
                yield_achvd=int(item['yield_achvd']) if item['yield_achvd'].isdigit() else 0,
                qty=int(item['qty']) if item['qty'].isdigit() else 1,
                spare_type=item['spare_type'],
                warehouse=item['warehouse'],
                any_remarks=item.get('any_remarks', ""),
                warranty_status=item['warranty_status'],
                foc_no="Pending",  # ✅ Default to "Pending" if empty
            )

            db.session.add(spare_request)
            db.session.flush()  # Get ID before commit
            last_inserted_id = spare_request.id  # Store last inserted request ID

        db.session.commit()
        print(f"✅ All requests saved successfully! Request ID: {request_id}")

        flash("✅ Request submitted successfully!", "success")

        # ✅ Redirect to the Print Request page with correct request_id
        return redirect(url_for('material.print_request', request_id=request_id))

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error saving to DB: {str(e)}", "error")
        print("❌ Error Saving to DB:", str(e))
        return render_template("material/material_dashboard.html")

@material_bp.route('/print_request/<request_id>', methods=['GET'])
def print_request(request_id):
    """ Fetches print request details and loads the print page """
    request_entries = spare_req.query.filter_by(request_id=request_id).all()

    if not request_entries:
        flash(f"❌ Request ID {request_id} not found!", "error")
        return redirect(url_for('material.material_dashboard'))

    # ✅ Fetch details from the first entry (all have the same metadata)
    request_entry = request_entries[0]

    # ✅ Count number of warranty pending requests for this technician
    warranty_pending_count = spare_req.query.filter(
        spare_req.technician_id == request_entry.technician_id,
        spare_req.warranty_status == "Pending"
    ).count()

    # ✅ Count number of FOC pending requests for this technician
    foc_pending_count = spare_req.query.filter(
        spare_req.technician_id == request_entry.technician_id,
        spare_req.foc_no == "Pending"
    ).count()

    # ✅ Gather all spare items for this request_id
    spare_items = [
        {
            "product_code": spare.product_code,
            "description": spare.description,
            "previous_reading": spare_req.query.filter(
                spare_req.serial_number == spare.serial_number,
                spare_req.product_code == spare.product_code,
                spare_req.request_id != request_id  # ✅ Exclude the current request
            ).order_by(spare_req.date.desc()).first().reading if spare_req.query.filter(
                spare_req.serial_number == spare.serial_number,
                spare_req.product_code == spare.product_code,
                spare_req.request_id != request_id
            ).order_by(spare_req.date.desc()).first() else 0,  # ✅ Fetch the correct previous reading
            "current_reading": spare.reading,
            "yield": spare.yield_achvd,
            "qty": spare.qty,
            "spare_type": spare.spare_type,
            "warehouse": spare.warehouse,
            "remarks": spare.any_remarks,
        }
        for spare in request_entries
    ]

    # ✅ Fetch history excluding the current request_id
    history_entries = spare_req.query.filter(
        spare_req.serial_number == request_entry.serial_number,
        spare_req.request_id != request_id  # ✅ Exclude the latest request
    ).order_by(spare_req.date.desc()).all()

    history_data = [
        {
            "date": entry.date.strftime('%Y-%m-%d'),
            "product_code": entry.product_code,
            "description": entry.description,
            "qty": entry.qty,
            "reading": entry.reading,
            "yield_achvd": entry.yield_achvd,
            "warehouse": entry.warehouse,
            "technician_name": entry.technician_name,
            "remarks": entry.any_remarks,
        }
        for entry in history_entries
    ]

    return render_template("material/print_request.html", request_data={
        "customer_name": request_entry.customer_name,
        "service_location": request_entry.service_location,
        "region": request_entry.region,
        "contract": request_entry.contract,
        "contract_expiry_date": request_entry.contract_expiry_date,
        "asset_Description": request_entry.asset_Description,
        "serial_number": request_entry.serial_number,
        "technician_name": request_entry.technician_name,
        "warranty_pending": warranty_pending_count,
        "foc_pending": foc_pending_count,
        "spare_items": spare_items
    }, history=history_data)


@material_bp.route('/movement', methods=['GET'])
def material_movement():
    return render_template('material/material_movement.html')

@material_bp.route('/history', methods=['GET'])
def request_history():
    return render_template('material/request_history.html')



# Route to serve the edit request page
@material_bp.route('/edit_request/<int:id>')
def edit_request_page(id):
    return render_template('material/edit_request.html')
import pandas as pd
import os

import pandas as pd
import os
from flask import send_file  # ✅ Added missing import


@material_bp.route('/export_excel', methods=['GET'])
def export_excel():
    """ Export filtered requests as an Excel file """
    from_date = request.args.get('fromDate')
    to_date = request.args.get('toDate')

    # Filters for search
    filters = {
        "id": request.args.get("filterId"),
        "serial_number": request.args.get("filterSerial"),
        "asset_Description": request.args.get("filterAsset"),
        "technician_name": request.args.get("filterTechnician"),
        "warehouse": request.args.get("filterWarehouse"),
        "product_code": request.args.get("filterProduct"),
        "description": request.args.get("filterDescription"),
        "warranty_status": request.args.get("filterStatus")
    }

    query = spare_req.query

    # ✅ Apply Date Filtering
    if from_date:
        from_date = datetime.strptime(from_date, "%Y-%m-%d")
        query = query.filter(spare_req.date >= from_date)
    if to_date:
        to_date = datetime.strptime(to_date, "%Y-%m-%d")
        query = query.filter(spare_req.date <= to_date)

    # ✅ Apply Search Filters
    for key, value in filters.items():
        if value:
            query = query.filter(getattr(spare_req, key).ilike(f"%{value}%"))

    # ✅ Fetch Filtered Data
    requests = query.all()

    data = [{
        "ID": req.id,
        "Date": req.date.strftime('%Y-%m-%d'),
        "Serial Number": req.serial_number,
        "Asset Description": req.asset_Description,
        "Technician Name": req.technician_name,
        "Warehouse": req.warehouse,
        "Product Code": req.product_code,
        "Description": req.description,
        "Warranty Status": req.warranty_status
    } for req in requests]

    # ✅ Generate Excel File
    df = pd.DataFrame(data)
    file_path = os.path.join(os.getcwd(), "filtered_material_requests.xlsx")
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)


@material_bp.route('/fetch_print_data/<int:request_id>', methods=['GET'])
def fetch_print_data(request_id):
    """ Fetches print request details along with pending counts and spare request history """
    request_entry = spare_req.query.get(request_id)
    if not request_entry:
        app.logger.error(f"❌ Request ID {request_id} not found in spare_req table.")
        return jsonify({"error": f"Request ID {request_id} not found"}), 404

    # Fetch technician details
    technician = Technician.query.get(request_entry.technician_id)

    # Get pending counts
    pending_counts = fetch_pending_counts(request_entry.technician_id).json if request_entry.technician_id else {"warranty_pending": 0, "foc_pending": 0}

    # Fetch spare request history
    history_entries = spare_req.query.filter_by(serial_number=request_entry.serial_number).all()
    history_data = [{
        "date": entry.date,
        "product_code": entry.product_code,
        "description": entry.description,
        "reading": entry.reading,
        "yield_achvd": entry.yield_achvd,
        "qty": entry.qty,
        "warehouse": entry.warehouse,
        "technician_name": entry.technician_name,
        "remarks": entry.any_remarks,
    } for entry in history_entries]

    app.logger.info(f"✅ Data retrieved for Request ID {request_id}: {request_entry}")

    return jsonify({
        "customer_name": request_entry.customer_name,
        "service_location": request_entry.service_location,
        "region": request_entry.region,
        "contract": request_entry.contract,
        "contract_expiry_date": request_entry.contract_expiry_date,
        "asset_Description": request_entry.asset_Description,
        "serial_number": request_entry.serial_number,
        "technician": request_entry.technician_name,
        "warranty_pending": pending_counts.get("warranty_pending", 0),
        "foc_pending": pending_counts.get("foc_pending", 0),
        "spare_items": [{
            "product_code": spare.product_code,
            "description": spare.description,
            "previous_reading": spare.reading,
            "current_reading": spare.reading,
            "yield": spare.yield_achvd,
            "qty": spare.qty,
            "spare_type": spare.spare_type,
            "warehouse": spare.warehouse,
            "remarks": spare.any_remarks,
        } for spare in spare_req.query.filter_by(serial_number=request_entry.serial_number).all()],
        "history": history_data
    })
@material_bp.route('/get_request/<int:id>', methods=['GET'])
def get_request(id):
    """Fetch request details including UUID for reprint."""
    request_data = spare_req.query.get(id)
    if not request_data:
        return jsonify({"error": "Request not found"}), 404

    return jsonify({
        "id": request_data.id,
        "request_id": request_data.request_id,  # ✅ Return UUID for reprinting
        "serial_number": request_data.serial_number,
        "asset_description": request_data.asset_Description,
        "product_code": request_data.product_code,
        "description": request_data.description,
        "code": request_data.code,
        "technician_id": request_data.technician_id,
        "technician_name": request_data.technician_name,
        "customer_name": request_data.customer_name,
        "service_location": request_data.service_location,
        "region": request_data.region,
        "contract": request_data.contract,
        "contract_expiry_date": request_data.contract_expiry_date,
        "reading": request_data.reading if request_data.reading is not None else "",
        "qty": request_data.qty,
        "spare_type": request_data.spare_type,
        "warehouse": request_data.warehouse,
        "foc_no": request_data.foc_no,
        "any_remarks": request_data.any_remarks,
        "warranty_status": request_data.warranty_status,
        "warranty_remarks": request_data.warranty_remarks
    })

@material_bp.route('/update_request/<int:id>', methods=['POST'])
def update_request(id):
    print(f"✏️ Updating request ID: {id}")  # Debugging Output

    data = request.json
    if not data or 'id' not in data:
        print("❌ Invalid request payload")  # Debugging Output
        return jsonify({"error": "Invalid request"}), 400

    request_data = spare_req.query.get(id)
    if not request_data:
        print(f"❌ Request ID {id} NOT found!")  # Debugging Output
        return jsonify({"error": "Request not found"}), 404

    # Update only editable fields
    request_data.code = data.get("code", request_data.code)
    request_data.reading = data.get("reading", request_data.reading)
    request_data.warehouse = data.get("warehouse", request_data.warehouse)
    request_data.foc_no = data.get("foc_no", request_data.foc_no)
    request_data.any_remarks = data.get("any_remarks", request_data.any_remarks)
    request_data.warranty_status = data.get("warranty_status", request_data.warranty_status)
    request_data.warranty_remarks = data.get("warranty_remarks", request_data.warranty_remarks)

    db.session.commit()
    print("✅ Request updated successfully")  # Debugging Output
    return jsonify({"success": True})  # ✅ Ensure JSON response is correct

@material_bp.route('/fetch_history/<serial_number>', methods=['GET'])
def fetch_history(serial_number):
    """ Fetch the spare request history for a given serial number. """
    history_entries = spare_req.query.filter_by(serial_number=serial_number).order_by(spare_req.date.desc()).all()

    if not history_entries:
        return jsonify([])  # Return an empty list if no history is found

    history_data = [{
        "date": entry.date.strftime('%Y-%m-%d'),
        "product_code": entry.product_code,
        "description": entry.description,
        "qty": entry.qty,
        "reading": entry.reading,
        "yield_achvd": entry.yield_achvd,
        "warehouse": entry.warehouse,
        "technician_name": entry.technician_name,
        "foc_no": entry.foc_no,
        "warranty_status": entry.warranty_status,
        "remarks": entry.any_remarks,
    } for entry in history_entries]

    return jsonify(history_data)


@material_bp.route('/delete_request/<int:request_id>', methods=['DELETE'])
def delete_request(request_id):
    """Handles deletion of a material request by ID."""
    try:
        request_entry = spare_req.query.get(request_id)

        if not request_entry:
            return jsonify({"error": "Request not found"}), 404  # If ID doesn't exist

        db.session.delete(request_entry)
        db.session.commit()

        return jsonify({"message": "Request deleted successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500  # Return error response

