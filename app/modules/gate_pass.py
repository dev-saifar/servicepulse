from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from datetime import datetime, timedelta

import os
import uuid
import qrcode
from app.models import GatePassRequest, Assets, Ticket, Technician, Contract, WorkshopAsset

gate_pass_bp = Blueprint('gate_pass', __name__, url_prefix='/gatepass')


@gate_pass_bp.route('/delivery', methods=['GET', 'POST'])
def create_delivery():
    if request.method == 'POST':
        data = request.form
        # Check if serial number already exists in assets table
        existing = Assets.query.filter_by(serial_number=data.get('serial_number')).first()
        if existing:
            flash("🚫 Serial Number already exists in Assets. Please make a collection note first.", "danger")
            return redirect(url_for('gate_pass.create_delivery'))

        asset_code = generate_asset_code(data.get('asset_type'))

        qr_path = generate_qr_code(f"{data.get('customer_name')} | {data.get('serial_number')} | {asset_code}")
        gp_number = generate_gp_number()

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
            part_number=data.get('part_number'),
            mono_reading=data.get('mono_reading'),
            color_reading=data.get('color_reading'),
            contact_number=data.get('contact_number'),
            remarks=data.get('remarks'),
            qr_code_path=qr_path,
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
        flash("Gate Pass created and asset delivered.", "success")
        return redirect(url_for('gate_pass.delivery_task_list'))

    return render_template('gatepass/delivery_form.html')

@gate_pass_bp.route('/collection', methods=['GET', 'POST'])
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
            status='pending'
        )
        db.session.add(gp)
        db.session.commit()
        flash("Collection Gate Pass Created", "success")
        return redirect(url_for('gate_pass.gate_pass_tasks'))

    return render_template('gatepass/collection_form.html')


@gate_pass_bp.route('/tasks')
def gate_pass_tasks():
    all_tasks = GatePassRequest.query.order_by(GatePassRequest.created_at.desc()).all()
    return render_template('gatepass/task_list.html', tasks=all_tasks)


@gate_pass_bp.route('/delivery/tasks')
def delivery_task_list():
    pending = GatePassRequest.query.filter_by(type='delivery', status='pending').all()
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
def print_gate_pass(gp_id):
    gate_pass = GatePassRequest.query.get_or_404(gp_id)
    contract = Contract.query.filter_by(contract_code=gate_pass.contract_code).first()
    billing_company = contract.billing_company if contract else 'N/A'
    return render_template('gatepass/gatepass_print.html', gate_pass=gate_pass, now=datetime.now(), billing_company=billing_company)


@gate_pass_bp.route('/mark-completed/<int:gp_id>')
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
                asset_status=asset.asset_status,
                part_no=asset.part_no,
                department=asset.department
            )
            db.session.add(workshop)
            db.session.delete(asset)

    db.session.commit()
    flash("Marked as completed.", "success")
    return redirect(url_for('gate_pass.gate_pass_tasks'))

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
