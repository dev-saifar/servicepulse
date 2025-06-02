from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.modules.license_utils import is_license_valid, save_license_file, create_trial_license, get_domain, get_hardware_id

license_bp = Blueprint('license', __name__)

@license_bp.route('/license', methods=['GET', 'POST'])
def license_page():
    if request.method == 'POST':
        if 'license_key' in request.form:
            key = request.form.get('license_key', '').strip()
            if key:
                save_license_file(key)
                valid, msg = is_license_valid()
                if valid:
                    flash("✅ License activated successfully.", "success")
                    return redirect(url_for('about.about'))
                else:
                    flash(f"❌ Invalid license: {msg}", "danger")
            else:
                flash("⚠️ Please enter a license key.", "warning")

        elif 'trial' in request.form:
            valid, existing = is_license_valid()
            if valid and existing.get("license_type") == "trial":
                flash(f"⚠️ Trial already activated. Valid until {existing['expiry_date']}", "warning")
            else:
                client_name = request.form.get("client_name")
                address = request.form.get("address")
                email = request.form.get("email")
                trial_info = create_trial_license(client_name, address, email)
                flash(f"✅ Trial license activated! Valid until {trial_info['expiry_date']}", "success")
            return redirect(url_for('about.about'))

    # ✅ ALWAYS return the license.html on GET with license data for download info
    valid, existing = is_license_valid()
    license_info = existing if valid else {}
    return render_template(
        "license.html",
        domain=get_domain(),
        hardware_id=get_hardware_id(),
        license=license_info
    )
