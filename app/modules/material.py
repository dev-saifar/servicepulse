from flask import Blueprint, render_template, request, jsonify
from app.extensions import db
from app.models import spares, Technician, spare_req, Assets
from datetime import datetime
from flask import send_file
from flask import send_file

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
@material_bp.route('/fetch_pending_counts/<technician_id>', methods=['GET'])
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

@material_bp.route('/fetch_history/<serial_number>', methods=['GET'])
def fetch_history(serial_number):
    history = spare_req.query.filter_by(serial_number=serial_number).all()

    if not history:  # ✅ Handle empty results
        return jsonify([])  # Return an empty list to avoid errors

    history_data = []
    for spare in history:
        if spare:  # Ensure spare is not None
            history_data.append({
                "date": spare.date if spare.date else "N/A",
                "product_code": spare.product_code if spare.product_code else "N/A",
                "description": spare.description if spare.description else "N/A",
                "qty": spare.qty if spare.qty else 0,
                "reading": spare.reading if spare.reading else "NA",
                "yield_achvd": spare.yield_achvd if spare.yield_achvd else "N/A",
                "warehouse": spare.warehouse if spare.warehouse else "N/A",
                "technician_name": spare.technician_name if spare.technician_name else "N/A",
                "foc_no": spare.foc_no if spare.foc_no else "N/A",
                "warranty_status": spare.warranty_status if spare.warranty_status else "N/A",
                "remarks": spare.any_remarks if spare.any_remarks else "N/A"
            })

    return jsonify(history_data)
from flask import flash, redirect, url_for, render_template

@material_bp.route('/submit_request', methods=['POST'])
def submit_request():
    data = request.json  # Get JSON data from frontend
    print("Received Data:", data)  # Debugging output in Flask console

    if not isinstance(data, list):  # Ensure data is a list
        flash("❌ Invalid data format. Expected a list of requests.", "error")
        return render_template("material/material_dashboard.html")

    try:
        for item in data:  # Process each item in the list
            spare_request = spare_req(
                serial_number=item['serial_number'],
                asset_Description=item['asset_Description'],
                technician_id=int(item['technician_id']) if item['technician_id'].isdigit() else None,
                technician_name=item['technician_name'],
                reading=int(item['reading']) if item['reading'].isdigit() else 0,
                date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
                warranty_status=item['warranty_status']
            )

            db.session.add(spare_request)

        db.session.commit()
        print("✅ All requests saved successfully in DB!")

        # Redirect to the Print Request page after saving
        return redirect(url_for('material.print_request'))

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error saving to DB: {str(e)}", "error")
        print("❌ Error Saving to DB:", str(e))

    return render_template("material/material_dashboard.html")

@material_bp.route('print_request')
def print_request():
    return render_template("material/print_request.html")

@material_bp.route('/movement', methods=['GET'])
def material_movement():
    return render_template('material/material_movement.html')

@material_bp.route('/history', methods=['GET'])
def request_history():
    return render_template('material/request_history.html')

@material_bp.route('/fetch_requests', methods=['GET'])
def fetch_requests():
    """ Fetch paginated requests with filtering options """
    page = int(request.args.get('page', 1))
    from_date = request.args.get('fromDate')
    to_date = request.args.get('toDate')

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

    if from_date and to_date:
        query = query.filter(spare_req.date >= from_date, spare_req.date <= to_date)

    for key, value in filters.items():
        if value:
            query = query.filter(getattr(spare_req, key).ilike(f"%{value}%"))

    requests = query.order_by(spare_req.date.desc()).paginate(page=page, per_page=100).items  # ✅ Fixed Pagination

    request_list = [{
        "id": req.id,
        "date": req.date,  # ✅ Added Date
        "customer_name": req.customer_name,  # ✅ Added Customer Name
        "foc_no": req.foc_no,  # ✅ Added FOC Number
        "serial_number": req.serial_number,
        "asset_Description": req.asset_Description,
        "technician_name": req.technician_name,
        "warehouse": req.warehouse,
        "product_code": req.product_code,
        "description": req.description,
        "warranty_status": req.warranty_status
    } for req in requests]

    return jsonify(request_list)

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
    """ Export all requests as an Excel file """
    requests = spare_req.query.all()
    data = [{
        "ID": req.id,
        "Date":req.date,
        "Serial Number": req.serial_number,
        "Asset Description": req.asset_Description,
        "Technician Name": req.technician_name,
        "Warehouse": req.warehouse,
        "Product Code": req.product_code,
        "Description": req.description,
        "Warranty Status": req.warranty_status
    } for req in requests]

    df = pd.DataFrame(data)

    # ✅ Fix: Use a valid file path
    file_path = os.path.join(os.getcwd(), "material_requests.xlsx")

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
    print(f"🔍 Fetching request ID: {id}")  # Debugging Output

    request_data = spare_req.query.get(id)
    if not request_data:
        print(f"❌ Request ID {id} NOT found in the database!")  # Debugging Output
        return jsonify({"error": "Request not found"}), 404

    return jsonify({
        # Asset Information (Non-editable)
        "id": request_data.id,
        "serial_number": request_data.serial_number,
        "asset_description": request_data.asset_Description,
        "product_code": request_data.product_code,
        "description": request_data.description,
        "code": request_data.code,  # Editable

        # Technician Details (Non-editable)
        "technician_id": request_data.technician_id,
        "technician_name": request_data.technician_name,

        # Service & Contract Details (Non-editable)
        "customer_name": request_data.customer_name,
        "service_location": request_data.service_location,
        "region": request_data.region,
        "contract": request_data.contract,
        "contract_expiry_date": request_data.contract_expiry_date,

        # Spare Part & Usage Information
        "reading": request_data.reading if request_data.reading is not None else "",

        "qty": request_data.qty,
        "spare_type": request_data.spare_type,
        "warehouse": request_data.warehouse,  # Editable

        # Additional Information
        "foc_no": request_data.foc_no,  # Editable
        "any_remarks": request_data.any_remarks,  # Editable

        # Warranty Details
        "warranty_status": request_data.warranty_status,  # Editable
        "warranty_remarks": request_data.warranty_remarks  # Editable
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

