from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from app.extensions import db
from app.models import Customer, Contract
from datetime import datetime
from sqlalchemy import extract  # Add this import
from app.models import Customer
from flask import jsonify
from sqlalchemy import func
from datetime import date
from flask_login import login_required
from app.utils.permission_required import permission_required
from flask_login import login_required, current_user




contracts_bp = Blueprint('contracts', __name__, template_folder='../templates/contracts')
@contracts_bp.route('/search_customer', methods=['GET'])
def search_customer():
    query = request.args.get('query', '').lower()

    customers = Customer.query.filter(Customer.cust_name.ilike(f'%{query}%')).all()

    results = []
    for c in customers:
        if c:  # skip None
            results.append({
                "cust_code": c.cust_code,
                "cust_name": c.cust_name,
                "billing_company": c.billing_company
            })

    return jsonify(results)


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
@login_required
@permission_required('can_add_contracts')
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


from flask import Blueprint, render_template, request, jsonify, send_file
from app.extensions import db
from app.models import Contract
import csv
import io
from flask import flash

from datetime import datetime


@contracts_bp.route('/list')
@login_required
@permission_required('can_view_contracts')
def list_contracts():

    return render_template('contract_list.html')


from datetime import datetime


@contracts_bp.route('/fetch_contracts1')
@login_required
@permission_required('can_view_contracts')
def fetch_contracts1():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = Contract.query

    if start_date and end_date:
        query = query.filter(Contract.contract_start_date >= start_date, Contract.contract_end_date <= end_date)

    contracts = query.all()

    contracts_data = []
    for contract in contracts:
        if contract is None:  # Ensure contract is not None
            continue

        contracts_data.append({
            "contract_code": contract.contract_code if contract.contract_code else "N/A",
            "customer": contract.cust_name if contract.cust_name else "N/A",
            "billing_company": contract.billing_company if contract.billing_company else "N/A",
            "cont_discription": contract.cont_discription if contract.cont_discription else "N/A",
            "sales_person": contract.sales_person if contract.sales_person else "N/A",
            "start_date": convert_to_date(contract.contract_start_date),
            "end_date": convert_to_date(contract.contract_end_date),
            "billing_cycle": contract.billing_cycle if contract.billing_cycle else "N/A",
        })

    return jsonify(contracts_data)


def convert_to_date(date_value):
    """Converts a string date to 'YYYY-MM-DD' format if needed."""
    if isinstance(date_value, str):  # If already a string, return as is
        return date_value
    elif isinstance(date_value, datetime):  # If it's a datetime object, format it
        return date_value.strftime('%Y-%m-%d')
    return "N/A"  # Return "N/A" if the date is None


@contracts_bp.route('/view')
@login_required
@permission_required('can_view_contracts')
def view_contract():
    contract_code = request.args.get('code')
    contract = Contract.query.filter_by(contract_code=contract_code).first()
    if not contract:
        return jsonify({"error": "Contract not found"}), 404
    return jsonify({
        "contract_code": contract.contract_code,
        "customer": contract.cust_name,
        "billing_company": contract.billing_company,
        "cont_discription": contract.cont_discription,
        "sales_person": contract.sales_person,
        "start_date": contract.contract_start_date.strftime('%Y-%m-%d') if isinstance(contract.contract_start_date, datetime) else contract.contract_start_date,
        "end_date": contract.contract_end_date.strftime('%Y-%m-%d') if isinstance(contract.contract_end_date, datetime) else contract.contract_end_date,
        "billing_cycle": contract.billing_cycle,
        "contract_currency": contract.contract_currency,
        "mono_commitment": contract.mono_commitment,
        "mono_charge": contract.mono_charge,
        "mono_excess_charge": contract.mono_excess_charge,
        "color_commitment": contract.color_commitment,
        "color_charge": contract.color_charge,
        "color_excess_charge": contract.color_excess_charge,
        "rental_charges": contract.rental_charges,
        "software_rental": contract.software_rental,
        "durations": contract.durations,
        "document_path": contract.document_path  # ✅ ADD THIS LINE

    })

@contracts_bp.route('/edit', methods=['GET', 'POST'])
@login_required
@permission_required('can_edit_contracts')
def edit_contract():
    contract_code = request.args.get('code')
    contract = Contract.query.filter_by(contract_code=contract_code).first()

    if not contract:
        flash('Contract not found', 'danger')
        return redirect(url_for('contracts.list_contracts'))

    if request.method == 'POST':
        # Basic fields
        contract.cust_code = request.form['cust_code']
        contract.cust_name = request.form['cust_name']
        contract.billing_company = request.form['billing_company']
        contract.cont_discription = request.form['cont_discription']
        contract.contract_start_date = request.form['contract_start_date']
        contract.contract_end_date = request.form['contract_end_date']
        contract.durations = request.form['durations']
        contract.sales_person = request.form['sales_person']
        contract.billing_cycle = request.form['billing_cycle']
        contract.contract_currency = request.form['contract_currency']

        # Advanced fields
        contract.mono_commitment = request.form.get('mono_commitment')
        contract.mono_charge = request.form.get('mono_charge')
        contract.mono_excess_charge = request.form.get('mono_excess_charge')
        contract.color_commitment = request.form.get('color_commitment')
        contract.color_charge = request.form.get('color_charge')
        contract.color_excess_charge = request.form.get('color_excess_charge')
        contract.rental_charges = request.form.get('rental_charges')
        contract.software_rental = request.form.get('software_rental')
        contract.billing_currency = request.form.get('billing_currency')
        contract.email = request.form.get('email')

        db.session.commit()
        flash('✅ Contract updated successfully', 'success')
        return redirect(url_for('contracts.list_contracts'))

    return render_template('contracts/edit_contract.html', contract=contract)

@contracts_bp.route('/delete', methods=['DELETE'])
@login_required
@permission_required('can_delete_contracts')
def delete_contract():
    contract_code = request.args.get('code')
    contract = Contract.query.filter_by(contract_code=contract_code).first()
    if not contract:
        return jsonify({"success": False, "error": "Contract not found"})

    db.session.delete(contract)
    db.session.commit()
    return jsonify({"success": True})


@contracts_bp.route('/export_excel')
def export_excel():
    import pandas as pd
    from io import BytesIO
    from flask import send_file

    contracts = Contract.query.all()
    data = [{
        "Contract Code": c.contract_code,
        "Customer": c.cust_name,
        "Billing Company": c.billing_company,
        "Description": c.cont_discription,
        "Sales Person": c.sales_person,
        "Start Date": c.contract_start_date.strftime('%Y-%m-%d') if isinstance(c.contract_start_date, datetime) else c.contract_start_date,
        "End Date": c.contract_end_date.strftime('%Y-%m-%d') if isinstance(c.contract_end_date, datetime) else c.contract_end_date,
        "Billing Cycle": c.billing_cycle,
        "Currency": c.contract_currency,
        "Email": c.email,
        "Mono Commitment": c.mono_commitment,
        "Mono Charge": c.mono_charge,
        "Mono Excess Charge": c.mono_excess_charge,
        "Color Commitment": c.color_commitment,
        "Color Charge": c.color_charge,
        "Color Excess Charge": c.color_excess_charge,
        "Rental Charges": c.rental_charges,
        "Software Rental": c.software_rental,
        "Duration (Months)": c.durations
    } for c in contracts]

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Contracts')

    output.seek(0)
    return send_file(output, download_name="contracts.xlsx", as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
from flask import jsonify, request
from collections import defaultdict
from datetime import datetime, date
from sqlalchemy import extract
from app.models import Contract
from app.modules.contracts import contracts_bp
from flask import jsonify, request, render_template
from collections import defaultdict
from datetime import datetime, date
from sqlalchemy import extract, func
from app.models import Contract
from app.modules.contracts import contracts_bp
import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = os.path.join('app', 'static', 'uploads', 'contracts')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@contracts_bp.route('/contracts/dashboard')
@login_required
@permission_required('can_view_contracts')
def contract_dashboard_page():
    billing_companies = [b[0] for b in db.session.query(Contract.billing_company).distinct()]
    years = sorted(set(int(y[0]) for y in db.session.query(extract('year', Contract.contract_start_date)).distinct() if y[0]))
    return render_template("contract_dashboard.html", billing_companies=billing_companies, years=years)


@contracts_bp.route('/contracts/dashboard-data')
@login_required
@permission_required('can_view_contracts')
def contract_dashboard_data():
    today = date.today()
    billing_filter = request.args.get('billing_company', '').strip()
    year_filter = request.args.get('year', '').strip()

    contracts_query = Contract.query
    if billing_filter:
        contracts_query = contracts_query.filter(Contract.billing_company == billing_filter)
    if year_filter and year_filter.isdigit():
        contracts_query = contracts_query.filter(extract('year', Contract.contract_start_date) == int(year_filter))

    contracts = contracts_query.all()

    # Counters and structures
    total, active, expiring, expired = 0, 0, 0, 0
    sales_total = defaultdict(int)
    sales_active = defaultdict(int)
    sales_expiring = defaultdict(int)
    sales_expired = defaultdict(int)
    trends = defaultdict(int)

    active_list, expiring_list, expired_list = [], [], []

    def parse_date(d):
        if isinstance(d, date):
            return d
        if isinstance(d, str) and d.strip():
            try:
                return datetime.strptime(d.strip(), "%Y-%m-%d").date()
            except Exception:
                return None
        return None

    for c in contracts:
        start_date = parse_date(c.contract_start_date)
        end_date = parse_date_safe(c.contract_end_date)
        if not end_date:
            continue  # skip invalid date entries

        if not start_date or not end_date:
            continue  # skip if dates are invalid

        total += 1
        trends[start_date.year] += 1

        salesperson = c.sales_person or "Unassigned"
        sales_total[salesperson] += 1

        row = {
            "contract_code": c.contract_code,
            "cust_name": c.cust_name,
            "end": end_date.strftime('%Y-%m-%d')
        }

        if end_date < today:
            expired += 1
            sales_expired[salesperson] += 1
            expired_list.append(row)
        elif (end_date - today).days <= 60:
            expiring += 1
            sales_expiring[salesperson] += 1
            expiring_list.append(row)
        else:
            active += 1
            sales_active[salesperson] += 1
            active_list.append(row)

    return jsonify({
        "summary": {
            "total": total,
            "active": active,
            "expired": expired,
            "expiring": expiring
        },
        "sales_donut": {
            "total": {"labels": list(sales_total.keys()), "data": list(sales_total.values())},
            "active": {"labels": list(sales_active.keys()), "data": list(sales_active.values())},
            "expiring": {"labels": list(sales_expiring.keys()), "data": list(sales_expiring.values())},
            "expired": {"labels": list(sales_expired.keys()), "data": list(sales_expired.values())}
        },
        "trends": {
            "labels": list(trends.keys()),
            "data": list(trends.values())
        },
        # 🔁 Rename here:
        "contract_lists": {
            "active": active_list,
            "expiring": expiring_list,
            "expired": expired_list
        }
    })


@contracts_bp.route('/contracts/upload/<contract_code>', methods=['POST'])
@login_required
@permission_required('can_edit_contracts')
def upload_contract_file(contract_code):
    file = request.files.get('contract_file')
    if not file:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400

    filename = secure_filename(file.filename)
    saved_filename = f"{contract_code}_{filename}"
    filepath = os.path.join(UPLOAD_FOLDER, saved_filename)
    file.save(filepath)

    contract = Contract.query.filter_by(contract_code=contract_code).first()
    contract.document_path = f"uploads/contracts/{saved_filename}"
    db.session.commit()
    return jsonify({'success': True})

from datetime import datetime

def parse_date_safe(d):
    if not d or not isinstance(d, str) or d.strip() == "":
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%d/%m %H:%M:%S"):  # Add more as needed
        try:
            return datetime.strptime(d.strip(), fmt).date()
        except ValueError:
            continue
    return None  # return None if nothing works
