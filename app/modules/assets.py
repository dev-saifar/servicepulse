from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
import pandas as pd
import os
import io
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import Assets

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

    # Fetch asset data from the database
    assets = Assets.query.all()

    # Convert database records to a list of dictionaries
    assets_data = [
        {
            'Customer Name': asset.customer_name,
            'Serial Number': asset.serial_number,
            'Location': asset.service_location,
            'Region': asset.region,
            'Technician': asset.technician_name,
            'Asset Description': asset.asset_Description
        }
        for asset in assets
    ]

    # Convert data to Pandas DataFrame
    df = pd.DataFrame(assets_data)

    # Create an Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Assets')

    output.seek(0)

    # Send file as a response
    return send_file(output, download_name="assets.xlsx", as_attachment=True,
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
