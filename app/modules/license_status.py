from flask import Blueprint, render_template
from app.modules.license_utils import is_license_valid, get_domain, get_hardware_id, load_license_file, decrypt_license

license_status_bp = Blueprint('license_status', __name__)

@license_status_bp.route('/license-info')
def license_info():
    license_data = {}
    valid, result = is_license_valid()

    if valid:
        license_data = result
        license_data['status'] = "Valid ✅"
    else:
        license_data = {
            "client_name": "Unknown",
            "domain": get_domain(),
            "hardware_id": get_hardware_id(),
            "license_type": "N/A",
            "expiry_date": "N/A",
            "status": f"Invalid ❌: {result}"
        }

    return render_template('license_info.html', license=license_data)
