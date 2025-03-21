from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from app.extensions import db
from app.models import Customer, Contract
from datetime import datetime
from sqlalchemy import extract  # Add this import

contracts_bp = Blueprint('contracts', __name__, template_folder='../templates/contracts')

@contracts_bp.route('/search_customer', methods=['GET'])
def search_customer():
    """Search for customers"""
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify([])

    customers = Customer.query.filter(Customer.cust_name.ilike(f"%{query}%")).all()
    return jsonify([{"cust_code": c.cust_code, "cust_name": c.cust_name, "billing_company": c.billing_company} for c in customers])

@contracts_bp.route('/fetch_contracts', methods=['GET'])
def fetch_contracts():
    """Fetch contracts for a selected customer"""
    cust_code = request.args.get("cust_code", "").strip()
    billing_company = request.args.get("billing_company", "").strip()

    contracts = Contract.query.filter_by(cust_code=cust_code, billing_company=billing_company).all()
    return jsonify([{"contract_code": c.contract_code, "cont_discription": c.cont_discription} for c in contracts])

@contracts_bp.route('/get_contract_details', methods=['GET'])
def get_contract_details():
    """Fetch full contract details"""
    contract_code = request.args.get("contract_code", "").strip()
    billing_company = request.args.get("billing_company", "").strip()

    contract = Contract.query.filter_by(contract_code=contract_code, billing_company=billing_company).first()
    return jsonify({
        "success": True,
        "contract": {
            "cont_discription": contract.cont_discription,
            "contract_start_date": contract.contract_start_date,
            "contract_end_date": contract.contract_end_date,
            "sales_person": contract.sales_person,
            "durations": contract.durations
        }
    })

@contracts_bp.route('/create_contract', methods=['POST'])
def create_contract():
    """Create a new contract"""
    # Validate required fields
    required_fields = ['cust_code', 'billing_company', 'cont_discription', 'contract_start_date', 'contract_end_date', 'sales_person']
    for field in required_fields:
        if not request.form.get(field):
            print(f"❌ Missing required field: {field}")  # Debugging
            return jsonify({"error": f"Missing required field: {field}"}), 400

    cust_code = request.form.get('cust_code')
    billing_company = request.form.get('billing_company')
    cont_discription = request.form.get('cont_discription')
    contract_start_date = datetime.strptime(request.form.get('contract_start_date'), '%Y-%m-%d')
    contract_end_date = datetime.strptime(request.form.get('contract_end_date'), '%Y-%m-%d')
    sales_person = request.form.get('sales_person')
    durations = (contract_end_date - contract_start_date).days // 30  # Duration in months

    customer = Customer.query.filter_by(cust_code=cust_code, billing_company=billing_company).first()
    cust_name = customer.cust_name if customer else None  # Default to None if not found
    # Generate contract code
    contract_code = generate_contract_code(cust_code, billing_company, contract_start_date, contract_end_date)
    if not contract_code:
        return jsonify({"error": "Failed to generate contract code"}), 400

    # Check if contract code already exists
    existing_contract = Contract.query.filter_by(contract_code=contract_code, billing_company=billing_company).first()
    if existing_contract:
        return jsonify({"error": "Contract code already exists"}), 400

    # Save to DB
    def convert_empty_to_none(value):
        return None if value.strip() == "" else value

    new_contract = Contract(
        cust_code=cust_code,
        cust_name=cust_name,
        billing_company=billing_company,
        cont_discription=cont_discription,
        contract_start_date=contract_start_date,
        contract_end_date=contract_end_date,
        sales_person=sales_person,
        durations=durations,
        contract_code=contract_code,
        mono_commitment=convert_empty_to_none(request.form.get('mono_commitment', "")),
        mono_charge=convert_empty_to_none(request.form.get('mono_charge', "")),
        mono_excess_charge=convert_empty_to_none(request.form.get('mono_excess_charge', "")),
        color_commitment=convert_empty_to_none(request.form.get('color_commitment', "")),
        color_charge=convert_empty_to_none(request.form.get('color_charge', "")),
        color_excess_charge=convert_empty_to_none(request.form.get('color_excess_charge', "")),
        rental_charges=convert_empty_to_none(request.form.get('rental_charges', "")),
        software_rental=convert_empty_to_none(request.form.get('software_rental', "")),
        billing_cycle=convert_empty_to_none(request.form.get('billing_cycle', "")),
        contract_currency=convert_empty_to_none(request.form.get('contract_currency', ""))
    )

    db.session.add(new_contract)
    db.session.commit()

    return jsonify({"success": True, "message": "Contract created successfully", "contract_code": contract_code})

def generate_contract_code(cust_code, billing_company, start_date, end_date):
    """Generate contract code in the format: DS_YY_YY_XXX"""
    if not billing_company:
        return None

    year_signed = start_date.year
    year_expiry = end_date.year

    # Use SQLAlchemy's extract function to filter by year
    contracts_in_year = Contract.query.filter(
        Contract.billing_company == billing_company,
        extract('year', Contract.contract_start_date) == year_signed
    ).count() + 1  # Increment contract count for that year

    return f"{billing_company[:2]}{str(year_signed)[2:]}{str(year_expiry)[2:]}{str(contracts_in_year).zfill(3)}"