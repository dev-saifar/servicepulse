from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.modules.license_utils import (
    is_license_valid, save_license_file, create_trial_license,
    get_domain, get_hardware_id, trial_already_used
)

license_bp = Blueprint('license', __name__)

@license_bp.route('/license', methods=['GET', 'POST'])
def license_page():
    if request.method == 'POST':
        # Full license paste
        if 'license_key' in request.form:
            key = request.form.get('license_key', '').strip()
            if not key:
                flash("⚠️ Please enter a license key.", "warning")
            else:
                save_license_file(key)
                valid, msg = is_license_valid(force_reload=True)  # ensure fresh read
                if valid:
                    flash("✅ License activated successfully.", "success")
                    next_url = request.args.get('next') or request.form.get('next')
                    return redirect(next_url or url_for('about.about'))
                else:
                    flash(f"❌ Invalid license: {msg}", "danger")

        # Trial activation (once only)
        elif 'trial' in request.form:
            # If already fully licensed, no need to create a trial
            ok, lic = is_license_valid()
            if ok and lic.get("license_type") != "trial":
                flash("✅ A valid license is already installed.", "success")
                return redirect(url_for('about.about'))

            if trial_already_used():
                flash("❌ Trial already activated on this machine. Please request a full license.", "danger")
                return redirect(url_for('license.license_page'))

            try:
                client_name = request.form.get("client_name")
                address = request.form.get("address")
                email = request.form.get("email")
                trial_info = create_trial_license(client_name, address, email)
                is_license_valid(force_reload=True)
                flash(f"✅ Trial license activated! Valid until {trial_info['expiry_date']}", "success")
                next_url = request.args.get('next') or request.form.get('next')
                return redirect(next_url or url_for('about.about'))
            except Exception as e:
                flash(f"❌ Unable to activate trial: {e}", "danger")

    valid, existing = is_license_valid()
    license_info = existing if valid else {}
    return render_template(
        "license.html",
        domain=get_domain(),
        hardware_id=get_hardware_id(),
        license=license_info,
        trial_used=trial_already_used()
    )
