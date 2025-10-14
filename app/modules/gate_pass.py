from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from datetime import datetime, timedelta
from flask_login import login_required
from app.utils.permission_required import permission_required
from flask_login import current_user
from app.models import Contract, Customer,PendingDelivery
from flask import request, jsonify


import os
import uuid
import qrcode
from app.models import GatePassRequest, Assets, Ticket, Technician, Contract, WorkshopAsset

gate_pass_bp = Blueprint('gate_pass', __name__, url_prefix='/gatepass')


@gate_pass_bp.route('/delivery', methods=['GET', 'POST'])
@login_required
@permission_required('can_create_gatepass')
def create_delivery():
    if request.method == 'POST':
        data = request.form

        # Check if serial exists
        existing = Assets.query.filter_by(serial_number=data.get('serial_number')).first()
        if existing:
            flash("🚫 Serial Number already exists in Assets. Please make a collection note first.", "danger")
            return redirect(url_for('gate_pass.create_delivery'))

        serial_number = data.get('serial_number')
        # Check in workshop table
        workshop_asset = WorkshopAsset.query.filter_by(serial_number=serial_number).first()
        if workshop_asset:
            workshop_asset.asset_status = 'Send Out'
            db.session.commit()

        try:
            asset_code = generate_asset_code(data.get('asset_type'))
            qr_path = generate_qr_code(f"{data.get('customer_name')} | {data.get('serial_number')} | {asset_code}")
            gp_number = generate_gp_number()
            accessories = data.get('accessories')

            gp = GatePassRequest(
                gp_number=gp_number,
                type='delivery',
                customer_name=data.get('customer_name'),
                contract_code=data.get('contract_code'),
                department=data.get('department'),
                serial_number=data.get('serial_number'),
                asset_code=asset_code,
                asset_type=data.get('asset_type'),
                technician_name=data.get('technician_name'),
                technician_email=data.get('technician_email'),
                service_location=data.get('service_location'),
                region=data.get('region'),
                delivery_datetime=data.get('delivery_datetime'),
                asset_description=data.get('asset_description'),
                accessories=accessories,
                part_number=data.get('part_number'),
                mono_reading=data.get('mono_reading'),
                color_reading=data.get('color_reading'),
                contact_number=data.get('contact_number'),
                remarks=data.get('remarks'),
                qr_code_path=qr_path,
                status='Pending'
            )
            db.session.add(gp)

            asset = Assets(
                account_code="",
                customer_name=data.get('customer_name'),
                serial_number=data.get('serial_number'),
                service_location=data.get('service_location'),
                region=data.get('region'),
                technician_name=data.get('technician_name'),
                technician_email=data.get('technician_email'),
                contract=data.get('contract_code'),
                asset_Description=data.get('asset_description'),
                asset_code=asset_code,
                part_no=data.get('part_number'),
                pm_freq='60',
                install_date=datetime.now().strftime("%Y-%m-%d"),
                asset_status='Active',
                department=data.get('department')
            )
            db.session.add(asset)

            ticket = Ticket(
                reference_no=generate_reference_number(),
                serial_number=data.get('serial_number'),
                customer=data.get('customer_name'),
                service_location=data.get('service_location'),
                region=data.get('region'),
                asset_Description=data.get('asset_description'),
                title="Installation Ticket",
                description="Auto-generated from Delivery Gate Pass",
                called_by="System",
                email_id=data.get('technician_email'),
                phone=data.get('contact_number'),
                call_type="Installation",
                technician_id=data.get('technician_id'),
                estimated_time=60,
                travel_time=15,
                expected_completion_time=datetime.utcnow() + timedelta(minutes=75),
                status="Open",
                created_at=datetime.utcnow()

            )
            db.session.add(ticket)

            tech_id = data.get('technician_id')
            if tech_id:
                technician = Technician.query.get(tech_id)
                if technician:
                    technician.status = "Busy"

            db.session.commit()
            flash("✅ Gate Pass created and asset delivered.", "success")
            return redirect(url_for('gate_pass.delivery_task_list'))

        except Exception as e:
            db.session.rollback()
            flash(f"❌ An error occurred: {str(e)}", "danger")
            return redirect(url_for('gate_pass.create_delivery'))

    # Final fallback: handle GET or invalid POST
    return render_template('gatepass/delivery_form.html')


@gate_pass_bp.route('/collection', methods=['GET', 'POST'])
@login_required
@permission_required('can_create_gatepass')
def create_collection():
    if request.method == 'POST':
        data = request.form
        asset_code = data.get('asset_code')

        qr_path = generate_qr_code(f"{data.get('customer_name')} | {data.get('serial_number')} | {asset_code}")
        gp_number = generate_gp_number()

        gp = GatePassRequest(
            gp_number=gp_number,
            type='collection',
            customer_name=data.get('customer_name'),
            contract_code=data.get('contract_code'),
            department=data.get('department'),
            serial_number=data.get('serial_number'),
            asset_code=asset_code,
            technician_name=data.get('technician_name'),
            technician_email=data.get('technician_email'),
            service_location=data.get('service_location'),
            region=data.get('region'),
            delivery_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            asset_description=data.get('asset_description'),
            part_number=data.get('part_number'),
            mono_reading=data.get('mono_reading'),
            color_reading=data.get('color_reading'),
            accessories=data.get('accessories'),
            contact_number='',
            remarks=data.get('remarks'),
            qr_code_path=qr_path,
            status='Pending'
        )
        db.session.add(gp)
        db.session.commit()
        flash("Collection Gate Pass Created", "success")
        return redirect(url_for('gate_pass.task_list'))


    return render_template('gatepass/collection_form.html')




@gate_pass_bp.route('/delivery/tasks')
@login_required
@permission_required('can_view_gatepass')
def delivery_task_list():
    pending = GatePassRequest.query.filter_by(type='delivery', status='Pending').all()
    return render_template('gatepass/task_list.html', tasks=pending, title="Delivery Tasks")


@gate_pass_bp.route('/autocomplete/customers')
def autocomplete_customers():
    term = request.args.get('term', '')
    customers = Contract.query.with_entities(Contract.cust_name)\
        .filter(Contract.cust_name.ilike(f"%{term}%"))\
        .distinct().limit(10).all()
    return jsonify([c[0] for c in customers])


@gate_pass_bp.route('/contracts/by_customer')
def contracts_by_customer():
    customer = request.args.get('customer_name', '')
    contracts = Contract.query.with_entities(Contract.contract_code)\
        .filter_by(cust_name=customer).limit(10).all()
    return jsonify([c[0] for c in contracts])


@gate_pass_bp.route('/autocomplete/technicians')
def autocomplete_technicians():
    term = request.args.get('term', '')
    techs = Technician.query.with_entities(Technician.name, Technician.email)\
        .filter(Technician.name.ilike(f"%{term}%")).limit(10).all()
    return jsonify([{'name': t[0], 'email': t[1]} for t in techs])


@gate_pass_bp.route('/print/<int:gp_id>')
@login_required
@permission_required('can_view_gatepass')
def print_gate_pass(gp_id):
    gate_pass = GatePassRequest.query.get_or_404(gp_id)
    contract = Contract.query.filter_by(contract_code=gate_pass.contract_code).first()
    billing_company = contract.billing_company if contract else 'N/A'
    return render_template('gatepass/gatepass_print.html', gate_pass=gate_pass, now=datetime.now(), billing_company=billing_company)


@gate_pass_bp.route('/mark-completed/<int:gp_id>')
@login_required
@permission_required('can_edit_gatepass')
def mark_completed(gp_id):
    gp = GatePassRequest.query.get_or_404(gp_id)
    gp.status = 'completed'

    if gp.type == 'collection':
        # ✅ Pull full asset record
        asset = Assets.query.filter_by(serial_number=gp.serial_number).first()

        if asset:
            workshop = WorkshopAsset(
                account_code=asset.account_code,
                customer_name=asset.customer_name,
                serial_number=asset.serial_number,
                service_location=asset.service_location,
                region=asset.region,
                technician_name=asset.technician_name,
                technician_email=asset.technician_email,
                contract=asset.contract,
                asset_Description=asset.asset_Description,
                contract_expiry_date=asset.contract_expiry_date,
                last_pm_date=datetime.now().strftime("%Y-%m-%d"),
                pm_freq=asset.pm_freq,
                install_date=asset.install_date,
                asset_code=asset.asset_code,
                asset_status="in workshop",
                part_no=asset.part_no,
                department=asset.department
            )
            db.session.add(workshop)
            db.session.delete(asset)

    db.session.commit()
    flash("Marked as completed.", "success")
    return redirect(url_for('gate_pass.task_list'))


# -------------------------
# Utility functions
# -------------------------

def generate_gp_number():
    current_year = datetime.now().year
    count = GatePassRequest.query.filter(GatePassRequest.gp_number.like(f"GP-{current_year}-%")).count()
    next_seq = str(count + 1).zfill(3)
    return f"GP-{current_year}-{next_seq}"

def generate_reference_number():
    today = datetime.now().strftime('%Y%m%d')
    count = Ticket.query.filter(Ticket.reference_no.like(f"REF-{today}-%")).count()
    return f"REF-{today}-{count + 1:03d}"


@gate_pass_bp.route('/generate_asset_code')
def generate_asset_code(asset_type):
    prefix = {'Kampala': 'B', 'Upcountry': 'C', 'Used': 'INV'}.get(asset_type, 'X')
    last = Assets.query.filter(Assets.asset_code.like(f"{prefix}%"))\
               .order_by(Assets.asset_code.desc()).first()
    if last:
        num = int(last.asset_code.replace(prefix, '').lstrip("0") or 0) + 1
    else:
        num = 1
    return f"{prefix}{str(num).zfill(5)}"


    location = request.args.get('location', '').lower()
    prefix = {'kampala': 'B', 'upcountry': 'C', 'used': 'INV'}.get(location, 'X')
    last = Assets.query.filter(Assets.asset_code.like(f"{prefix}%"))\
              .order_by(Assets.asset_code.desc()).first()
    if last:
        num = int(last.asset_code.replace(prefix, '').lstrip("0") or 0) + 1
    else:
        num = 1
    return jsonify({'asset_code': f"{prefix}{str(num).zfill(5)}"})


import os
import uuid
import qrcode


def generate_qr_code(content):
    from flask import current_app

    folder = os.path.join(current_app.root_path, 'static', 'qr')
    os.makedirs(folder, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.png"
    full_path = os.path.join(folder, filename)

    img = qrcode.make(content)
    img.save(full_path)

    return f"qr/{filename}"  # relative for use in <img src="{{ url_for('static', filename=...) }}">



@gate_pass_bp.route('/collection/<serial_number>', methods=['GET'])
@permission_required('can_create_gatepass')
def load_collection_form(serial_number):
    asset = Assets.query.filter_by(serial_number=serial_number).first()
    if not asset:
        flash("Asset not found", "danger")
        return redirect(url_for("gate_pass.search_assets_for_collection"))

    contract = Contract.query.filter_by(contract_code=asset.contract).first()
    contract_code = contract.contract_code if contract else ""

    return render_template('gatepass/collection_form.html', asset=asset, contract_code=contract_code)
@gate_pass_bp.route('/collection/search', methods=['GET', 'POST'])
def search_assets_for_collection():
    if request.method == 'POST':
        data = request.get_json()
        query = Assets.query

        if data.get("serial_number"):
            query = query.filter(Assets.serial_number.ilike(f"%{data['serial_number']}%"))
        if data.get("customer_name"):
            query = query.filter(Assets.customer_name.ilike(f"%{data['customer_name']}%"))
        if data.get("service_location"):
            query = query.filter(Assets.service_location.ilike(f"%{data['service_location']}%"))
        if data.get("region"):
            query = query.filter(Assets.region.ilike(f"%{data['region']}%"))

        results = query.limit(100).all()

        return jsonify([{
            "serial_number": a.serial_number,
            "customer_name": a.customer_name,
            "service_location": a.service_location,
            "region": a.region,
            "asset_description": a.asset_Description
        } for a in results])

    return render_template('gatepass/collection_search.html')

from datetime import datetime, timedelta

@gate_pass_bp.route('/workshop-assets')
@login_required
@permission_required('can_create_gatepass')
def workshop_assets():
    assets = WorkshopAsset.query.order_by(WorkshopAsset.collected_date.desc()).all()
    return render_template('gatepass/workshop_assets.html', assets=assets, now=datetime.now(), timedelta=timedelta)


@gate_pass_bp.route('/check_serial_exists')
def check_serial_exists():
    serial = request.args.get('serial_number')
    if not serial:
        return jsonify({"exists": False})

    exists = db.session.execute(
        text("SELECT 1 FROM assets WHERE serial_number = :s LIMIT 1"),
        {"s": serial}
    ).first() is not None

    return jsonify({"exists": exists})

@gate_pass_bp.route('/tasks')
@login_required
@permission_required('can_view_gatepass')
def task_list():
    status_filter = request.args.get('status_filter')
    q = GatePassRequest.query
    if status_filter:
        q = q.filter_by(status=status_filter)

    tasks = q.order_by(
        GatePassRequest.created_at.desc(),
        GatePassRequest.delivery_datetime.desc(),
        GatePassRequest.id.desc()
    ).all()

    return render_template('gatepass/task_list.html',
                           tasks=tasks,
                           status_filter=status_filter)



@gate_pass_bp.route('/export')
@login_required
@permission_required('can_export_gatepass')
def export_tasks_excel():
    import pandas as pd
    from flask import make_response, request
    from io import BytesIO

    # ✅ read filter from query string
    status_filter = request.args.get('status_filter')
    if status_filter:
        tasks = GatePassRequest.query.filter_by(status=status_filter).all()
    else:
        tasks = GatePassRequest.query.all()

    # Convert to Excel
    data = [{
        "GP No.": gp.gp_number,
        "Type": gp.type,
        "Customer": gp.customer_name,
        "Serial": gp.serial_number,
        "Location": gp.service_location,
        "Technician": gp.technician_name,
        "Date": gp.delivery_datetime,
        "Status": gp.status
    } for gp in tasks]

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='GatePassTasks')

    output.seek(0)
    response = make_response(output.read())
    response.headers['Content-Disposition'] = f'attachment; filename=GatePassTasks_{status_filter or "all"}.xlsx'
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return response

# ------------------- Decommissioning Flow ----------------------

@gate_pass_bp.route('/decommission/<serial_number>', methods=['GET'])
@login_required
@permission_required('can_create_gatepass')
def view_decommission_form(serial_number):
    asset = WorkshopAsset.query.filter_by(serial_number=serial_number).first_or_404()
    return render_template('gatepass/decommission_form.html', asset=asset)


@gate_pass_bp.route('/decommission/confirm', methods=['POST'])
@login_required
@permission_required('can_create_gatepass')
def confirm_decommission():
    serial_number = request.form.get('serial_number')
    asset = WorkshopAsset.query.filter_by(serial_number=serial_number).first_or_404()

    remarks = request.form.get('remarks')
    mono = request.form.get('mono_reading')
    color = request.form.get('color_reading')

    gp_number = generate_gp_number()

    # ✅ NEW: create QR code and keep relative static path (e.g., "qr/abcd.png")
    qr_path = generate_qr_code(f"DECOMMISSION | {asset.customer_name} | {asset.serial_number} | {gp_number}")

    gp = GatePassRequest(
        gp_number=gp_number,
        type='decommission',
        customer_name=asset.customer_name,
        contract_code=asset.contract,
        department=asset.department,
        serial_number=asset.serial_number,
        asset_code=asset.asset_code,
        technician_name=asset.technician_name,
        technician_email=asset.technician_email,
        service_location=asset.service_location,
        region=asset.region,
        delivery_datetime=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        asset_description=asset.asset_Description,
        part_number=asset.part_no,
        mono_reading=mono,
        color_reading=color,
        remarks=remarks,
        qr_code_path=qr_path,          # ✅ NEW
        status='Pending'
    )
    db.session.add(gp)
    asset.asset_status = 'decommissioned'
    db.session.commit()

    flash(f"Decommissioning note created for {asset.serial_number}.", "success")
    return redirect(url_for('gate_pass.workshop_assets'))

@gate_pass_bp.route('/decommission/print/<int:gp_id>', methods=['GET'])
@login_required
@permission_required('can_view_gatepass')
def print_decommission(gp_id):
    gp = GatePassRequest.query.get_or_404(gp_id)
    if gp.type != 'decommission':
        flash("Invalid print type.", "danger")
        return redirect(url_for('gate_pass.task_list'))

    contract = Contract.query.filter_by(contract_code=gp.contract_code).first()
    billing_company = contract.billing_company if contract else "DS"
    return render_template('gatepass/decommission_print.html', gate_pass=gp, billing_company=billing_company, now=datetime.utcnow())


@gate_pass_bp.route('/decommission/complete/<int:gp_id>', methods=['GET'])
@login_required
@permission_required('can_edit_gatepass')
def complete_decommission(gp_id):
    gp = GatePassRequest.query.get_or_404(gp_id)
    if gp.type != 'decommission':
        flash("Invalid task type.", "danger")
        return redirect(url_for('gate_pass.task_list'))

    gp.status = 'completed'
    db.session.commit()
    flash(f"Decommission GP {gp.gp_number} marked as completed.", "success")
    return redirect(url_for('gate_pass.task_list'))

@gate_pass_bp.route('/workshop/edit/<int:asset_id>', methods=['GET', 'POST'])
@login_required
@permission_required('can_edit_gatepass')
def edit_workshop_asset(asset_id):
    asset = WorkshopAsset.query.get_or_404(asset_id)
    if request.method == 'POST':
        # update fields...
        db.session.commit()
        flash('Asset updated successfully.', 'success')
        return redirect(url_for('gate_pass.workshop_assets'))
    return render_template('gatepass/edit_workshop_asset.html', asset=asset)




@gate_pass_bp.route('/validate_qr/<int:asset_id>', methods=['POST'])
@login_required
@permission_required('gatepass')
def validate_qr(asset_id):
    asset = db.session.get(WorkshopAsset, asset_id)
    if not asset:
        flash("Asset not found.", "danger")
        return redirect(url_for('gate_pass.workshop_assets'))

    asset.decommissioned_date = datetime.now()
    task = TaskList.query.filter_by(serial_number=asset.serial_number, task_type="Collection", status="Pending").first()
    if task:
        task.status = "Done"
        task.completed_time = datetime.now()

    db.session.commit()
    flash(f"Asset {asset.serial_number} marked as collected.", "success")
    return redirect(request.referrer or url_for('gate_pass.workshop_assets'))

@gate_pass_bp.route('/get_assets_by_customer')
def get_assets_by_customer():
    customer_name = request.args.get('customer_name', '')
    assets = Assets.query.filter_by(customer_name=customer_name).all()
    result = []
    for a in assets:
        result.append({
            "serial_number": a.serial_number,
            "asset_code": a.asset_code,
            "asset_description": a.asset_Description,
            "service_location": a.service_location,
            "region": a.region,
            "technician_name": a.technician_name,
            "department": a.department
        })
    return jsonify(result)

@gate_pass_bp.route('/bulk_collection', methods=['GET', 'POST'])
@login_required
@permission_required('can_create_gatepass')
def bulk_collection():
    if request.method == 'POST':
        try:
            customer_name = request.form.get('customer_name')

            # Step 1: Generate a unique GP Number
            gp_number = f"GP-COLLECT-{uuid.uuid4().hex[:6].upper()}"

            # Step 2: Generate QR Code and save path
            qr_filename = f"{gp_number}.png"
            qr_folder = os.path.join('static', 'qr_codes')
            os.makedirs(qr_folder, exist_ok=True)
            qr_path = os.path.join(qr_folder, qr_filename)

            img = qrcode.make(gp_number)
            img.save(qr_path)

            # Step 3: Loop over machines
            machines_added = 0
            i = 0
            while True:
                if f"serial_number_{i}" not in request.form:
                    break
                if request.form.get(f"select_{i}") != "on":
                    i += 1
                    continue

                serial = request.form.get(f'serial_number_{i}')
                asset = Assets.query.filter_by(serial_number=serial).first()
                if not asset:
                    i += 1
                    continue

                # Move asset to workshop
                workshop_asset = WorkshopAsset(
                    account_code=asset.account_code,
                    customer_name=asset.customer_name,
                    serial_number=asset.serial_number,
                    service_location=asset.service_location,
                    region=asset.region,
                    technician_name=asset.technician_name,
                    technician_email=asset.technician_email,
                    contract=asset.contract,
                    asset_Description=asset.asset_Description,
                    contract_expiry_date=asset.contract_expiry_date,
                    last_pm_date=datetime.now().strftime("%Y-%m-%d"),
                    pm_freq=asset.pm_freq,
                    install_date=asset.install_date,
                    asset_code=asset.asset_code,
                    asset_status="in workshop",
                    part_no=asset.part_no,
                    department=asset.department,
                    mono_reading=int(request.form.get(f'mono_reading_{i}') or 0),
                    color_reading=int(request.form.get(f'color_reading_{i}') or 0),
                    remarks=request.form.get(f'accessories_{i}'),
                    collected_date=datetime.now(),
                    decommission_gp_number=gp_number
                )
                #db.session.add(workshop_asset)
                #db.session.delete(asset)

                # Create gate pass entry
                gp_request = GatePassRequest(
                    gp_number=gp_number,
                    type='collection',
                    customer_name=asset.customer_name,
                    contract_code=asset.contract,
                    department=asset.department,
                    serial_number=asset.serial_number,
                    asset_code=asset.asset_code,
                    asset_type=getattr(asset, "asset_type", "Unknown"),
                    technician_name=asset.technician_name,
                    technician_email=asset.technician_email,
                    service_location=asset.service_location,
                    region=asset.region,
                    delivery_datetime=datetime.now(),
                    asset_description=asset.asset_Description,
                    part_number=asset.part_no,
                    mono_reading=int(request.form.get(f'mono_reading_{i}') or 0),
                    color_reading=int(request.form.get(f'color_reading_{i}') or 0),
                    contact_number="",
                    accessories=request.form.get(f'accessories_{i}'),
                    remarks="",
                    qr_code_path=qr_path,
                    status='Pending',
                    created_at=datetime.now()
                )
                db.session.add(gp_request)

                machines_added += 1
                i += 1

            if machines_added == 0:
                flash("❌ No machines selected.", "danger")
                return redirect(request.url)

            db.session.commit()
            flash(f"✅ Collection submitted for {machines_added} machine(s). GP No: {gp_number}", "success")
            return redirect(url_for('gate_pass.task_list'))

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error: {str(e)}", "danger")

    return render_template("gatepass/bulk_collection_form.html")
@gate_pass_bp.route('/print_bulk_collection/<gp_number>')
@login_required
def print_bulk_collection(gp_number):
    # Fetch all gate pass records under this GP number
    gate_passes = GatePassRequest.query.filter_by(gp_number=gp_number).all()
    if not gate_passes:
        flash("❌ Invalid GP Number or no records found.", "danger")
        return redirect(url_for('gate_pass.bulk_collection'))

    customer_name = gate_passes[0].customer_name
    billing_company = "MDS" if "MDS" in gate_passes[0].contract_code.upper() else "DS"

    return render_template(
        'gatepass/bulk_collection_print.html',
        gate_passes=gate_passes,
        gp_number=gp_number,
        customer_name=customer_name,
        billing_company=billing_company,
        now=datetime.now()
    )

@gate_pass_bp.route('/complete_bulk_collection/<gp_number>')
@login_required
@permission_required('can_edit_gatepass')
def complete_bulk_collection(gp_number):
    try:
        pending_entries = GatePass.query.filter_by(gp_number=gp_number, type='collection', status='Pending').all()
        if not pending_entries:
            flash('No pending collection found with this GP number.', 'warning')
            return redirect(url_for('gate_pass.task_list'))

        for entry in pending_entries:
            # Create new WorkshopAsset entry
            workshop_asset = WorkshopAsset(
                customer_name=entry.customer_name,
                contract_code=entry.contract_code,
                serial_number=entry.serial_number,
                asset_code=entry.asset_code,
                asset_description=entry.asset_description,
                mono_reading=entry.mono_reading,
                color_reading=entry.color_reading,
                technician_name=entry.technician_name,
                service_location=entry.service_location,
                region=entry.region,
                remarks=entry.remarks,
                created_by=current_user.name,
                created_on=datetime.now()
            )
            db.session.add(workshop_asset)

            # Mark gate pass as completed
            entry.status = 'completed'
            entry.completed_on = datetime.now()

        db.session.commit()
        flash('Bulk collection marked as completed and moved to workshop.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error completing bulk collection: {str(e)}', 'danger')

    return redirect(url_for('gate_pass.task_list'))
@gate_pass_bp.route('/complete_bulk_single/<int:gp_id>')
@login_required
@permission_required('gate_pass')
def complete_bulk_single(gp_id):
    gp = GatePass.query.get_or_404(gp_id)
    if gp.status != 'completed':
        # Move to workshop_assets
        asset = WorkshopAsset(
            serial_number=gp.serial_number,
            customer_name=gp.customer_name,
            service_location=gp.service_location,
            region=gp.region,
            technician_name=gp.technician_name,
            asset_description=gp.asset_description,
            # Add any other required fields
        )
        db.session.add(asset)

        gp.status = 'completed'
        gp.completed_on = datetime.now()
        db.session.commit()

    flash(f'Bulk collection for {gp.serial_number} marked as completed.', 'success')
    return redirect(url_for('gate_pass.task_list'))
@gate_pass_bp.route('/complete_bulk_delivery/<gp_number>', methods=['POST'], endpoint='complete_bulk_delivery')
@login_required
@permission_required('can_edit_gatepass')
def complete_bulk_delivery(gp_number):

    try:
        gatepasses = GatePassRequest.query.filter_by(gp_number=gp_number, type='delivery', status='Pending').all()

        if not gatepasses:
            flash("⚠️ No pending delivery entries found for this GP.", "warning")
            return redirect(url_for('gate_pass.task_list'))

        for entry in gatepasses:
            # Add to PendingDelivery
            pending = PendingDelivery(
                account_code="",  # optional
                customer_name=entry.customer_name,
                serial_number=entry.serial_number,
                service_location=entry.service_location,
                region=entry.region,
                technician_name=entry.technician_name,
                technician_email=entry.technician_email,
                contract=entry.contract_code,
                asset_Description=entry.asset_description,
                contract_expiry_date="",  # optional
                last_pm_date="",
                pm_freq="60",  # default
                install_date=str(datetime.utcnow().date()),
                asset_code=None,
                asset_status="Active",
                part_no="",
                department=entry.department,
                created_by=current_user.username,
                status="Pending"
            )
            db.session.add(pending)

            # Update gate pass status
            entry.status = 'Completed'
            db.session.add(entry)

        db.session.commit()
        flash(f"✅ Bulk delivery completed and moved to Pending Delivery table.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error completing bulk delivery: {str(e)}", "danger")

    return redirect(url_for('gate_pass.task_list'))

from itertools import zip_longest

@gate_pass_bp.route('/bulk_delivery', methods=['GET', 'POST'])
@login_required
@permission_required('can_create_gatepass')
def bulk_delivery():
    if request.method == 'GET':
        return render_template('gatepass/bulk_delivery_form.html')

    try:
        data = request.form

        customer_name  = data.get('customer_name')
        contract_code  = data.get('contract_code')
        contact_number = data.get('contact_number')

        # Pull lists; some may be missing (e.g., accessories[] after UI change)
        serial_numbers     = [s.strip() for s in data.getlist('serial_number[]') if s.strip()]
        asset_descriptions = data.getlist('asset_description[]') or []
        departments        = data.getlist('department[]') or []
        remarks_list       = data.getlist('remarks[]') or []
        mono_readings      = data.getlist('mono_reading[]') or []
        color_readings     = data.getlist('color_reading[]') or []
        part_numbers       = data.getlist('part_number[]') or []
        # accessories were removed in UI; keep empty list for compatibility
        accessories        = data.getlist('accessories[]') or []

        gp_number  = generate_gp_number()
        added_count = 0

        # Iterate with zip_longest to avoid index errors; fill missing with ""
        for serial, desc, dept, mono, color, remark, acc, part_no in zip_longest(
            serial_numbers, asset_descriptions, departments,
            mono_readings, color_readings, remarks_list, accessories, part_numbers,
            fillvalue=""
        ):
            if not serial:   # skip rows without a serial
                continue

            # Avoid duplicate pending entries for same serial
            if GatePassRequest.query.filter_by(serial_number=serial, status='Pending', type='delivery').first():
                flash(f"⚠️ {serial} already exists as pending delivery. Skipped.", "warning")
                continue

            qr_path = generate_qr_code(f"{customer_name} | {serial} | {gp_number}")

            gp = GatePassRequest(
                gp_number=gp_number,
                type='delivery',
                customer_name=customer_name,
                contract_code=contract_code,
                department=dept or "",
                serial_number=serial,
                asset_code=None,
                asset_type="",
                technician_name="",
                technician_email="",
                service_location="",  # location removed from form
                region="",
                delivery_datetime=datetime.now(),
                asset_description=desc or "",
                part_number=part_no or "",
                mono_reading=int(mono or 0),
                color_reading=int(color or 0),
                contact_number=contact_number,
                accessories=acc or "",        # safe even when not posted
                remarks=remark or "",
                qr_code_path=qr_path,
                status='Pending'
            )
            db.session.add(gp)
            added_count += 1

        db.session.commit()
        flash(f"✅ Bulk delivery created with GP #{gp_number}. {added_count} machine(s) added.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error creating bulk delivery: {str(e)}", "danger")

    return redirect(url_for('gate_pass.task_list'))


@gate_pass_bp.route('/pending_deliveries')
@login_required
@permission_required('can_view_assets')
def pending_deliveries():
    deliveries = PendingDelivery.query.order_by(PendingDelivery.created_at.desc()).all()
    return render_template('gatepass/pending_delivery_dashboard.html', deliveries=deliveries)

@gate_pass_bp.route('/review_pending_delivery/<serial>', methods=['GET', 'POST'])
@login_required
@permission_required('can_create_gatepass')
def review_pending_delivery(serial):
    delivery = PendingDelivery.query.filter_by(serial_number=serial).first_or_404()

    # Pull techs for dropdown
    technicians = Technician.query.with_entities(Technician.name, Technician.email).all()

    if request.method == 'POST':
        serial_number = delivery.serial_number

        # 1) Duplicate guard
        if Assets.query.filter_by(serial_number=serial_number).first():
            flash(f"Asset with serial {serial_number} already exists.", 'danger')
            return redirect(request.url)

        # 2) Contract → cust_code, billing_company
        contract = Contract.query.filter_by(contract_code=delivery.contract).first()
        cust_code = getattr(contract, 'cust_code', '') if contract else ''
        billing_company = getattr(contract, 'billing_company', '') if contract else ''

        # 3) Build asset from form + pending record
        new_asset = Assets(
            account_code = cust_code,
            customer_name = delivery.customer_name,
            serial_number = serial_number,
            service_location = delivery.service_location,
            region = delivery.region,
            technician_name = request.form.get('technician_name') or delivery.technician_name,
            technician_email = request.form.get('technician_email') or delivery.technician_email,
            contract = delivery.contract,  # field name in Assets is 'contract'
            asset_Description = request.form.get('asset_description') or delivery.asset_Description,
            contract_expiry_date = getattr(contract, 'contract_expiry_date', None),
            last_pm_date = request.form.get('install_date') or datetime.utcnow().strftime("%Y-%m-%d"),
            pm_freq = request.form.get('pm_freq') or '60',
            install_date = request.form.get('install_date') or datetime.utcnow().strftime("%Y-%m-%d"),
            asset_code = request.form.get('asset_code'),
            asset_status = request.form.get('asset_status') or 'Active',
            part_no = request.form.get('part_number') or delivery.part_no or "",
            department = request.form.get('department') or delivery.department,



        )
        db.session.add(new_asset)

        # 4) Remove from pending
        db.session.delete(delivery)
        db.session.commit()

        flash("✅ Asset added and removed from Pending Delivery.", "success")
        return redirect(url_for('gate_pass.task_list'))

    # GET → render with technicians & now (for default date)
    return render_template(
        'gatepass/review_pending_delivery.html',
        delivery=delivery,
        technicians=[type('T', (), {'name': n, 'email': e}) for n, e in technicians],
        now=datetime.utcnow()
    )

from sqlalchemy import inspect

from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError, ProgrammingError
from flask import current_app

@gate_pass_bp.route('/search_customers_bulk', methods=['GET'])
def search_customers_bulk():
    try:
        term = request.args.get('term', '').lower()
        # Verify table existence
        inspector = inspect(db.engine)
        if 'cust' not in inspector.get_table_names():
            current_app.logger.error("Table 'cust' not found")
            return jsonify({'error': "Table 'cust' not found"}), 500
        if 'cust_name' not in [col['name'] for col in inspector.get_columns('cust')]:
            current_app.logger.error("Column 'cust_name' not found")
            return jsonify({'error': "Column 'cust_name' not found"}), 500
        results = (
            db.session.query(Customer.cust_name)
            .filter(db.func.lower(Customer.cust_name).like(f'%{term}%'))
            .distinct()
            .limit(10)
            .all()
        )
        current_app.logger.info(f"Query returned {len(results)} results")
        return jsonify([{'label': r[0], 'value': r[0]} for r in results])
    except OperationalError as e:
        current_app.logger.error(f"Database error: {str(e)}")
        return jsonify({'error': f"Database error: {str(e)}"}), 500
    except ProgrammingError as e:
        current_app.logger.error(f"Query error: {str(e)}")
        return jsonify({'error': f"Query error: {str(e)}"}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': f"Unexpected error: {str(e)}"}), 500

@gate_pass_bp.route("/get_contract_by_customer_bulk", methods=["GET"])
def get_contract_by_customer_bulk():
    customer_name = request.args.get("customer_name", "")
    current_app.logger.info(f"Fetching contract for customer: {customer_name}")
    contract = Contract.query.filter_by(cust_name=customer_name).first()
    if contract is None:
        current_app.logger.warning(f"No contract found for {customer_name}")
    return jsonify({"contract_code": contract.contract_code if contract else ""})

@gate_pass_bp.route('/print_bulk_delivery/<gp_number>')
@login_required
def print_bulk_delivery(gp_number):
    gate_passes = GatePassRequest.query.filter_by(gp_number=gp_number, type='delivery').all()
    if not gate_passes:
        flash("❌ Invalid GP Number or no records found.", "danger")
        return redirect(url_for('gate_pass.task_list'))
    first = gate_passes[0]
    # If you have Contract.billing_company, reuse it; else default:
    billing_company = "MDS" if "MDS" in (first.contract_code or "").upper() else "DS"
    return render_template(
        'gatepass/bulk_collection_print.html',  # same template
        gate_passes=gate_passes,
        gp_number=gp_number,
        customer_name=first.customer_name,
        billing_company=billing_company,
        now=datetime.now()
    )
@gate_pass_bp.route('/delete/<int:gp_id>', methods=['POST'])
@login_required
@permission_required('can_edit_gatepass')
def delete_gate_pass(gp_id):
    # Allow only Admins (matches how Settings visibility works)
    if getattr(current_user, 'role', '') != 'Admin':
        flash("You are not authorized to delete gate passes.", "danger")
        return redirect(url_for('gate_pass.task_list'))

    gp = GatePassRequest.query.get_or_404(gp_id)

    # Do not allow deleting completed entries
    if (gp.status or '').lower() == 'completed':
        flash("Cannot delete a completed gate pass.", "warning")
        return redirect(url_for('gate_pass.task_list'))

    # Try to remove QR image on disk (if any)
    try:
        if gp.qr_code_path:
            from flask import current_app
            qr_abs = os.path.join(current_app.root_path, 'static', gp.qr_code_path)
            if os.path.exists(qr_abs):
                os.remove(qr_abs)
    except Exception:
        pass  # ignore file errors

    db.session.delete(gp)
    db.session.commit()
    flash(f"🗑️ Deleted Gate Pass {gp.gp_number} ({gp.type}).", "success")
    return redirect(url_for('gate_pass.task_list'))


@gate_pass_bp.route('/delete-group/<gp_number>', methods=['POST'])
@login_required
@permission_required('can_edit_gatepass')
def delete_group(gp_number):
    # Admin check
    if getattr(current_user, 'role', '') != 'Admin':
        flash("You are not authorized to delete gate passes.", "danger")
        return redirect(url_for('gate_pass.task_list'))

    items = GatePassRequest.query.filter_by(gp_number=gp_number).all()
    if not items:
        flash("No gate passes found for this GP number.", "warning")
        return redirect(url_for('gate_pass.task_list'))

    # Block deletion if any are completed
    completed = [gp for gp in items if (gp.status or '').lower() == 'completed']
    if completed:
        flash("Cannot delete group: one or more entries are completed.", "warning")
        return redirect(url_for('gate_pass.task_list'))

    # Remove unique QR files (avoid double-delete)
    try:
        from flask import current_app
        for qr_rel in {gp.qr_code_path for gp in items if gp.qr_code_path}:
            qr_abs = os.path.join(current_app.root_path, 'static', qr_rel)
            if os.path.exists(qr_abs):
                os.remove(qr_abs)
    except Exception:
        pass

    # Delete all in one go
    for gp in items:
        db.session.delete(gp)
    db.session.commit()

    flash(f"🗑️ Deleted {len(items)} record(s) under GP {gp_number}.", "success")
    return redirect(url_for('gate_pass.task_list'))
