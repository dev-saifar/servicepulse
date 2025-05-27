from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from app.modules.license_utils import (
    is_license_valid, get_domain, get_hardware_id,
    create_trial_license
)
from datetime import datetime

about_bp = Blueprint('about', __name__, template_folder='../templates')

@about_bp.route('/about', methods=['GET', 'POST'])
def about():
    license_info = {
        "client_name": "",
        "address": "",
        "email": "",
        "domain": get_domain(),
        "hardware_id": get_hardware_id(),
        "license_type": "N/A",
        "expiry_date": "N/A",
        "status": "❌ Not Activated"
    }

    valid, result = is_license_valid()
    if valid and isinstance(result, dict):
        license_info.update(result)
        license_info["status"] = "✅ Valid"
    elif isinstance(result, str):
        license_info["status"] = f"❌ {result}"

    if request.method == 'POST':
        if request.form.get("action") == "activate_trial":
            client_name = request.form.get("client_name")
            address = request.form.get("address")
            email = request.form.get("email")
            trial = create_trial_license(client_name, address, email)
            license_info.update(trial)
            license_info["status"] = "✅ Trial Activated"
            flash(f"✅ Trial license activated for 90 days (until {trial['expiry_date']}).", "success")
            return redirect(url_for('about.about'))

    return render_template('about/about.html', license=license_info)


@about_bp.route('/download-license-info', methods=['POST'])
def download_license_info():
    client_name = request.form.get("client_name")
    address = request.form.get("address")
    email = request.form.get("email")

    info = {
        "client_name": client_name,
        "address": address,
        "email": email,
        "domain": get_domain(),
        "hardware_id": get_hardware_id(),
        "requested_on": datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    }

    response = make_response(jsonify(info))
    response.headers['Content-Disposition'] = 'attachment; filename=client_info.json'
    response.mimetype = 'application/json'
    flash("✅ License info generated. Kindly share the downloaded file with the ServPulse Team.", "info")
    return response
