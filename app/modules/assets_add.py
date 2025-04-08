# app/modules/assets_Add.py
from flask import Blueprint, render_template, request, jsonify
from app.models import Assets, Technician
from app.extensions import db
from app.models import McModel  # Make sure the spelling matches your models.py exactly


assets_add_bp = Blueprint(
    'assets_add', __name__,
    template_folder='../templates/assets_add'
)

@assets_add_bp.route('/add_asset_form')
def add_asset_form():
    return render_template('assets_Add.html')

@assets_add_bp.route('/check_serial_number')
def check_serial_number():
    serial = request.args.get("serial")
    asset = Assets.query.filter_by(serial_number=serial).first()
    if asset:
        return jsonify({"exists": True, "customer_name": asset.customer_name})
    return jsonify({"exists": False})

@assets_add_bp.route('/get_technicians')
def get_technicians():
    techs = Technician.query.with_entities(Technician.name).all()
    return jsonify([t.name for t in techs])

@assets_add_bp.route('/get_technician_email')
def get_technician_email():
    name = request.args.get("name")
    tech = Technician.query.filter_by(name=name).first()
    return jsonify({"email": tech.email if tech else ""})

@assets_add_bp.route('/generate_asset_code')
def generate_asset_code():
    location = request.args.get("location")
    prefix = {"kampala": "B", "upcountry": "C", "used": "INV"}.get(location.lower(), "B")
    count = Assets.query.filter(Assets.asset_code.like(f"{prefix}%")).count() + 1
    return jsonify({"asset_code": f"{prefix}{str(count).zfill(5)}"})

@assets_add_bp.route('/create', methods=['POST'])
def create_asset():
    try:
        serial_number = request.form.get("serial_number")
        if Assets.query.filter_by(serial_number=serial_number).first():
            return jsonify({"success": False, "error": "Serial number already exists!"})

        asset = Assets(
            account_code=request.form.get("account_code") or request.form.get("customer_name"),
            customer_name=request.form.get("customer_name"),
            serial_number=serial_number,
            service_location=request.form.get("service_location"),
            region=request.form.get("region"),
            technician_name=request.form.get("technician_name"),
            technician_email=request.form.get("technician_email"),
            contract=request.form.get("contract"),
            asset_Description=request.form.get("asset_Description"),
            contract_expiry_date=request.form.get("contract_expiry_date"),
            last_pm_date=request.form.get("last_pm_date"),
            pm_freq=request.form.get("pm_freq") or "Quarterly",
            install_date=request.form.get("install_date"),
            asset_code=request.form.get("asset_code"),
            asset_status=request.form.get("asset_status") or "Active",
            part_no=request.form.get("partnumber"),  # ✅ CORRECT FIELD NAME in model
            department=request.form.get("department")
        )
        db.session.add(asset)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)})
@assets_add_bp.route('/search_customer')
def search_customer():
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify([])

    from app.models import Customer  # Import if not already
    customers = Customer.query.filter(Customer.cust_name.ilike(f"%{query}%")).all()
    return jsonify([
        {"cust_code": c.cust_code, "cust_name": c.cust_name, "billing_company": c.billing_company}
        for c in customers
    ])
@assets_add_bp.route('/get_contracts_by_customer')
def get_contracts_by_customer():
    cust_name = request.args.get("cust_name")
    if not cust_name:
        return jsonify([])

    from app.models import Contract
    contracts = Contract.query.filter_by(cust_name=cust_name).all()

    return jsonify([
        {"contract_code": c.contract_code, "contract_expiry_date": c.contract_end_date}
        for c in contracts
    ])
@assets_add_bp.route('/search_asset_description')
def search_asset_description():
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify([])

    descriptions = (
        db.session.query(Assets.asset_Description)
        .filter(Assets.asset_Description.ilike(f"%{query}%"))
        .distinct()
        .limit(10)
        .all()
    )

    return jsonify([desc[0] for desc in descriptions])
@assets_add_bp.route('/get_partnumber', methods=['GET'])
def get_partnumber():
      # Make sure MC_Model is imported
    model_name = request.args.get('model')
    model = McModel.query.filter_by(asset_description=model_name).first()

    if model:
        return jsonify({"part_no": model.part_no})
    return jsonify({"part_no": ""})
