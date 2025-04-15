from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
import pandas as pd
import os
import io
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import Assets
from app.models import PreventiveMaintenance

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.extensions import db
from app.models import Customer, Contract, Assets
from datetime import datetime

assets_bp = Blueprint('assets', __name__, template_folder='../templates/assets')

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'xls', 'xlsx', 'csv'}


# ✅ Utility function to check allowed file types
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ✅ Download template route (Fix for missing template error)
@assets_bp.route('/download-template')
def download_template():
    """Generates and provides an asset import template file."""
    template_file = os.path.join(UPLOAD_FOLDER, "assets_template.csv")

    df = pd.DataFrame(columns=[
        "account_code", "customer_name", "serial_number", "service_location",
        "region", "technician_name", "technician_email", "contract", "asset_Description"
    ])

    df.to_csv(template_file, index=False)

    return send_file(template_file, as_attachment=True)


# ✅ Display paginated assets with filters
@assets_bp.route('/')
def index():
    query = Assets.query

    # Capture filter values from URL parameters
    filters = {
        "customer_name": request.args.get("customer_name"),
        "serial_number": request.args.get("serial_number"),
        "service_location": request.args.get("service_location"),
        "region": request.args.get("region"),
        "technician_name": request.args.get("technician_name"),
        "asset_Description": request.args.get("asset_Description"),
    }

    # Apply filters dynamically
    for field, value in filters.items():
        if value:
            query = query.filter(getattr(Assets, field).ilike(f"%{value}%"))

    # Pagination setup
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 100, type=int)  # Default to 100 per page
    paginated_assets = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template("assets/index.html", assets=paginated_assets, filters=filters, per_page=per_page)


# ✅ Export assets to Excel
@assets_bp.route('/export-to-excel')
def export_to_excel():
    """Exports asset data to an Excel file."""
    assets = Assets.query.all()

    # Convert database records to a list of dictionaries safely
    assets_data = []
    for asset in assets:
        if asset is None:
            continue
        assets_data.append({
            'Customer Name': asset.customer_name,
            'Serial Number': asset.serial_number,
            'Location': asset.service_location,
            'Region': asset.region,
            'Technician': asset.technician_name,
            'Asset Description': asset.asset_Description
        })

    # Convert data to Pandas DataFrame
    df = pd.DataFrame(assets_data)

    # Create an Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Assets')

    output.seek(0)

    return send_file(output,
                     download_name="assets.xlsx",
                     as_attachment=True,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ✅ Import assets from an Excel/CSV file
@assets_bp.route('/import', methods=['GET', 'POST'])
def import_assets():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file part", "error")
            return redirect(url_for('assets.import_assets'))

        file = request.files['file']
        if file.filename == '':
            flash("No selected file", "error")
            return redirect(url_for('assets.import_assets'))

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            try:
                df = pd.read_csv(filepath) if filename.endswith('.csv') else pd.read_excel(filepath)
                required_columns = {"account_code", "customer_name", "serial_number", "service_location",
                                    "region", "technician_name", "technician_email", "contract", "asset_Description"}

                if not required_columns.issubset(df.columns):
                    flash("Invalid file format. Please use the correct template.", "error")
                    return redirect(url_for('assets.import_assets'))

                imported_count = 0
                for _, row in df.iterrows():
                    if not row.get('serial_number'):
                        flash(f"Skipping row due to missing serial number.", "warning")
                        continue

                    existing_asset = Assets.query.filter_by(serial_number=row.get('serial_number')).first()
                    if existing_asset:
                        flash(f"Duplicate serial number {row.get('serial_number')} skipped.", "warning")
                        continue

                    asset = Assets(
                        account_code=row.get('account_code'),
                        customer_name=row.get('customer_name'),
                        serial_number=row.get('serial_number'),
                        service_location=row.get('service_location'),
                        region=row.get('region'),
                        technician_name=row.get('technician_name'),
                        technician_email=row.get('technician_email'),
                        contract=row.get('contract'),
                        asset_Description=row.get('asset_Description')
                    )
                    db.session.add(asset)
                    imported_count += 1

                db.session.commit()
                flash(f"{imported_count} assets imported successfully!", "success")

            except Exception as e:
                flash(f"Error processing file: {str(e)}", "error")

            return redirect(url_for('assets.index'))

    return render_template('assets/import.html')


# ✅ Edit an asset
@assets_bp.route('/edit/<int:asset_id>', methods=['GET', 'POST'])
def edit_asset(asset_id):
    asset = Assets.query.get(asset_id)
    if not asset:
        flash("Asset not found!", "error")
        return redirect(url_for('assets.index'))

    if request.method == 'POST':
        try:
            for field in request.form:
                setattr(asset, field, request.form[field])

            db.session.commit()
            flash("Asset updated successfully!", "success")
            return redirect(url_for('assets.index'))
        except Exception as e:
            flash(f"Error updating asset: {str(e)}", "error")

    return render_template('assets/edit.html', asset=asset)


# ✅ Delete an asset
@assets_bp.route('/delete/<int:asset_id>', methods=['POST'])
def delete_asset(asset_id):
    asset = Assets.query.get(asset_id)
    if not asset:
        flash("Asset not found!", "error")
        return redirect(url_for('assets.index'))

    try:
        db.session.delete(asset)
        db.session.commit()
        flash("Asset deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting asset: {str(e)}", "error")

    return redirect(url_for('assets.index'))

@assets_bp.route('/customers', methods=['GET', 'POST'])
def manage_customers():
    if request.method == 'POST':
        billing_company = request.form['billing_company']
        cust_name = request.form['cust_name'].strip()
        cust_code = request.form['cust_code'].strip()

        # Check if customer already exists
        existing_customer = Customer.query.filter_by(cust_name=cust_name, billing_company=billing_company).first()
        if existing_customer:
            flash(f"Customer '{cust_name}' found. Redirecting to contracts...", "success")
            return redirect(url_for('assets.manage_contracts', cust_code=existing_customer.cust_code))

        # New customer scenario: Ensure `cust_code` is provided
        if not cust_code:
            flash("Customer Code is required for new customers!", "error")
            return redirect(url_for('assets.manage_customers'))

        # Ensure `cust_code` is unique within the billing company
        existing_cust_code = Customer.query.filter_by(cust_code=cust_code, billing_company=billing_company).first()
        if existing_cust_code:
            flash(f"Customer Code '{cust_code}' already exists for {billing_company}.", "error")
            return redirect(url_for('assets.manage_customers'))

        # Add new customer
        new_customer = Customer(cust_code=cust_code, cust_name=cust_name, billing_company=billing_company)
        db.session.add(new_customer)
        db.session.commit()
        flash(f"New Customer '{cust_name}' added successfully! Redirecting to contracts...", "success")
        return redirect(url_for('assets.manage_contracts', cust_code=cust_code))

    return render_template('customers.html')

@assets_bp.route('/assets', methods=['GET', 'POST'])
def manage_assets():
    # Your asset management logic here
    return render_template("assets_add/assets_Add.html")

@assets_bp.route('/customer/search', methods=['GET'])
def search_customer():
    billing_company = request.args.get('billing_company', '').strip()
    query = request.args.get('query', '').strip()

    if not billing_company or not query:
        return jsonify([])  # Return an empty list if no input

    # Fetch matching customers from the database
    customers = Customer.query.filter(
        Customer.billing_company == billing_company,
        Customer.cust_name.ilike(f"%{query}%")  # Case-insensitive search
    ).all()

    return jsonify([
        {"cust_code": c.cust_code, "cust_name": c.cust_name, "billing_company": c.billing_company}
        for c in customers
    ])

@assets_bp.route('/contracts', methods=['GET'])
def manage_contracts():
    """Display contract management page"""
    contracts = Contract.query.all()  # Fetch all contracts
    return render_template("contracts/contracts.html")  # Correct path to the contract management template


# ✅ Route to display asset creation form
@assets_bp.route('/add_asset/<contract_code>', methods=['GET'])
def add_asset():
    """Render asset creation form for a specific contract"""
    return render_template('contracts/asset_creation.html', contract_code=contract_code)


# ✅ Route to handle asset creation
@assets_bp.route('/create_asset', methods=['POST'])
def create_asset():
    """Create a new asset"""
    required_fields = ['contract', 'account_code', 'customer_name', 'serial_number', 'service_location',
                       'region', 'technician_name', 'technician_email', 'asset_Description', 'contract_expiry_date',
                       'last_pm_date', 'pm_freq', 'install_date']

    for field in required_fields:
        if not request.form.get(field):
            print(f"❌ Missing required field: {field}")  # Debugging
            return jsonify({"error": f"Missing required field: {field}"}), 400

    # Convert dates correctly
    try:
        contract_expiry_date = datetime.strptime(request.form.get('contract_expiry_date'), '%Y-%m-%d')
        last_pm_date = datetime.strptime(request.form.get('last_pm_date'), '%Y-%m-%d')
        install_date = datetime.strptime(request.form.get('install_date'), '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    # Save to DB
    new_asset = Assets(
        account_code=request.form.get('account_code'),
        customer_name=request.form.get('customer_name'),
        serial_number=request.form.get('serial_number'),
        service_location=request.form.get('service_location'),
        region=request.form.get('region'),
        technician_name=request.form.get('technician_name'),
        technician_email=request.form.get('technician_email'),
        contract=request.form.get('contract'),
        asset_Description=request.form.get('asset_Description'),
        contract_expiry_date=contract_expiry_date,
        last_pm_date=last_pm_date,
        pm_freq=request.form.get('pm_freq'),
        install_date=install_date
    )

    db.session.add(new_asset)
    db.session.commit()

    return jsonify({"success": True, "message": "Asset created successfully"})

@assets_bp.route('/customers/list', methods=['GET'])
def customer_list():
    from sqlalchemy import func, distinct

    customers = db.session.query(
        Customer,
        func.count(distinct(Contract.id)).label("contract_count"),
        func.count(distinct(Assets.id)).label("asset_count")
    ).outerjoin(Contract,
                (Customer.cust_code == Contract.cust_code) & (Customer.billing_company == Contract.billing_company)) \
        .outerjoin(Assets, Customer.cust_name == Assets.customer_name) \
        .group_by(Customer.id).all()

    return render_template("assets/customer_list.html", customers=customers)


@assets_bp.route('/customers/edit/<int:customer_id>', methods=['GET', 'POST'])
def edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    if request.method == 'POST':
        customer.cust_name = request.form['cust_name'].strip()
        customer.cust_code = request.form['cust_code'].strip()
        customer.billing_company = request.form['billing_company'].strip()

        db.session.commit()
        flash("✅ Customer updated successfully!", "success")
        return redirect(url_for('assets.customer_list'))

    return render_template('assets/edit_customer.html', customer=customer)

@assets_bp.route('/customers/delete/<int:customer_id>', methods=['POST'])
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    try:
        db.session.delete(customer)
        db.session.commit()
        flash("🗑️ Customer deleted successfully!", "success")
    except Exception as e:
        flash(f"❌ Error deleting customer: {str(e)}", "error")
    return redirect(url_for('assets.customer_list'))
@assets_bp.route('/customers/export')
def export_customers():
    from sqlalchemy import func, distinct

    # Join and count contracts and assets
    data = db.session.query(
        Customer.cust_code,
        Customer.cust_name,
        Customer.billing_company,
        func.count(distinct(Contract.id)).label("contract_count"),
        func.count(distinct(Assets.id)).label("asset_count")
    ).outerjoin(
        Contract,
        (Customer.cust_code == Contract.cust_code) & (Customer.billing_company == Contract.billing_company)
    ).outerjoin(
        Assets, Customer.cust_name == Assets.customer_name
    ).group_by(
        Customer.cust_code, Customer.cust_name, Customer.billing_company
    ).all()

    # Prepare data for export
    export_data = []
    for row in data:
        export_data.append({
            "Customer Code": row.cust_code,
            "Customer Name": row.cust_name,
            "Billing Company": row.billing_company,
            "No. of Contracts": row.contract_count,
            "No. of Assets": row.asset_count,
        })

    # Convert to Excel using pandas
    import pandas as pd
    import io

    df = pd.DataFrame(export_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Customers')

    output.seek(0)

    return send_file(
        output,
        download_name="customers.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Convert to Excel using pandas
    import pandas as pd
    import io

    df = pd.DataFrame(export_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Customers')

    output.seek(0)

    return send_file(
        output,
        download_name="customers.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
from datetime import datetime, timedelta
from flask import render_template


@assets_bp.route('/pm_dashboard')
def pm_dashboard():
    from app.models import Assets, Ticket
    from sqlalchemy import func
    today = datetime.today().date()

    # Filters from request
    filters = {
        "customer_name": request.args.get("customer_name"),
        "service_location": request.args.get("service_location"),
        "region": request.args.get("region"),
        "technician_name": request.args.get("technician_name")
    }

    # Subquery to get serials with active PM tickets
    active_pm_subq = db.session.query(Ticket.serial_number).filter(
        Ticket.call_type == 'PM',
        Ticket.status.in_(['Open', 'In Process'])
    ).distinct().subquery()

    # Base query with filters and excluding active PMs
    query = Assets.query.filter(~Assets.serial_number.in_(active_pm_subq))

    for field, value in filters.items():
        if value:
            query = query.filter(getattr(Assets, field).ilike(f"%{value}%"))

    # Only fetch assets with both last_pm_date and pm_freq
    query = query.filter(Assets.last_pm_date.isnot(None), Assets.pm_freq.isnot(None))

    due_assets = []
    for asset in query.all():
        try:
            last_pm = datetime.strptime(asset.last_pm_date, '%Y-%m-%d').date()
            freq_days = int(asset.pm_freq.split()[0])
            next_due = last_pm + timedelta(days=freq_days)
            if next_due <= today:
                due_assets.append({
                    "serial_number": asset.serial_number,
                    "customer_name": asset.customer_name,
                    "next_due": next_due.strftime('%Y-%m-%d'),
                    "technician_name": asset.technician_name,
                    "service_location": asset.service_location,
                    "region": asset.region,
                    "asset_description": asset.asset_Description,
                    "contract": asset.contract
                })
        except Exception as e:
            print(f"Error processing asset {asset.serial_number}: {e}")
            continue

    return render_template("assets/pm_dashboard.html", due_assets=due_assets)

@assets_bp.route('/pm_complete/<serial_number>', methods=['GET', 'POST'])
def complete_pm(serial_number):
    from app.models import PreventiveMaintenance, Assets
    asset = Assets.query.filter_by(serial_number=serial_number).first_or_404()

    if request.method == 'POST':
        scheduled_date = request.form.get('scheduled_date') or datetime.utcnow().date()
        performed_date = request.form.get('performed_date') or datetime.utcnow().date()
        technician_name = request.form.get('technician_name')
        remarks = request.form.get('remarks')

        # Save record
        pm = PreventiveMaintenance(
            serial_number=serial_number,
            scheduled_date=scheduled_date,
            performed_date=performed_date,
            technician_name=technician_name,
            remarks=remarks,
            status="Completed"
        )
        db.session.add(pm)

        # ✅ Update asset last_pm_date
        asset.last_pm_date = performed_date.strftime('%Y-%m-%d')
        db.session.commit()

        flash("✅ PM record saved and asset updated.", "success")
        return redirect(url_for('assets.pm_dashboard'))

    return render_template('assets/pm_complete.html', asset=asset)

@assets_bp.route('/pm_history')
def pm_history():
    history = PreventiveMaintenance.query.order_by(
        PreventiveMaintenance.performed_date.desc()
    ).all()

    # Enhance each record with asset details
    enriched = []
    for r in history:
        asset = Assets.query.filter_by(serial_number=r.serial_number).first()
        enriched.append({
            "serial_number": r.serial_number,
            "scheduled_date": r.scheduled_date,
            "performed_date": r.performed_date,
            "technician_name": r.technician_name,
            "remarks": r.remarks,
            "customer_name": asset.customer_name if asset else '',
            "service_location": asset.service_location if asset else '',
            "region": asset.region if asset else ''
        })

    return render_template("assets/pm_history.html", records=enriched)


@assets_bp.route('/export_pm_filtered')
def export_pm_filtered():
    from app.models import Ticket, Assets
    import pandas as pd
    from io import BytesIO

    filters = {
        "customer_name": request.args.get("customer_name"),
        "service_location": request.args.get("service_location"),
        "region": request.args.get("region"),
        "technician_name": request.args.get("technician_name")
    }

    query = Assets.query
    for field, value in filters.items():
        if value:
            query = query.filter(getattr(Assets, field).ilike(f"%{value}%"))

    today = datetime.today().date()
    rows = []

    for asset in query.all():
        try:
            if asset.last_pm_date and asset.pm_freq:
                last_pm = datetime.strptime(asset.last_pm_date, '%Y-%m-%d').date()
                freq_days = int(asset.pm_freq.split()[0])
                next_due = last_pm + timedelta(days=freq_days)

                existing_pm = Ticket.query.filter_by(serial_number=asset.serial_number, call_type='PM')\
                    .filter(Ticket.status.in_(['Open', 'In Process'])).first()

                if next_due <= today and not existing_pm:
                    rows.append({
                        "Serial Number": asset.serial_number,
                        "Customer": asset.customer_name,
                        "Next Due": next_due,
                        "Technician": asset.technician_name,
                        "Location": asset.service_location,
                        "Region": asset.region,
                        "Asset Description": asset.asset_Description
                    })
        except:
            continue

    df = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name="Pending PM")

    output.seek(0)
    return send_file(output, as_attachment=True, download_name="pending_pm_filtered.xlsx")
