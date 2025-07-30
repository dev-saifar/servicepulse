# app/modules/settings.py
from flask import Blueprint, render_template, request, redirect, flash, url_for, current_app, send_file
from werkzeug.utils import secure_filename
from dotenv import set_key, dotenv_values
from flask_mail import Message
from app.extensions import db, mail
from app.models import Assets, spares, TonerModel, TonerCosting, Customer, Contract
import os, pandas as pd
from io import BytesIO

settings_bp = Blueprint('settings', __name__, template_folder='../templates/settings')

ENV_PATH = os.path.abspath('.env')
UPLOAD_FOLDER = os.path.join('app', 'uploads', 'imports')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@settings_bp.route('/settings', methods=['GET', 'POST'])
def settings_page():
    smtp = dotenv_values(ENV_PATH)

    if request.method == 'POST' and 'smtp_save' in request.form:
        set_key(ENV_PATH, "MAIL_SERVER", request.form.get("MAIL_SERVER", ""))
        set_key(ENV_PATH, "MAIL_PORT", request.form.get("MAIL_PORT", "587"))
        set_key(ENV_PATH, "MAIL_USERNAME", request.form.get("MAIL_USERNAME", ""))
        set_key(ENV_PATH, "MAIL_PASSWORD", request.form.get("MAIL_PASSWORD", ""))
        set_key(ENV_PATH, "MAIL_DEFAULT_SENDER", request.form.get("MAIL_DEFAULT_SENDER", ""))
        set_key(ENV_PATH, "MAIL_USE_TLS", "True" if request.form.get("MAIL_USE_TLS") else "False")
        flash("✅ SMTP settings updated!", "success")
        return redirect(url_for('settings.settings_page'))

    return render_template("settings.html", smtp=smtp)


@settings_bp.route('/settings/upload/<table>', methods=['POST'])
def upload_excel(table):
    file = request.files.get('file')
    if not file or not file.filename.endswith('.xlsx'):
        flash("Invalid file format. Only .xlsx allowed.", "danger")
        return redirect(url_for('settings.settings_page'))

    path = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
    file.save(path)

    df = pd.read_excel(path)

    try:
        for _, row in df.iterrows():
            row_data = row.dropna().to_dict()
            if table == 'assets': db.session.add(Assets(**row_data))
            elif table == 'spares': db.session.add(spares(**row_data))
            elif table == 'tonermodel': db.session.add(TonerModel(**row_data))
            elif table == 'tonercosting': db.session.add(TonerCosting(**row_data))
            elif table == 'customer': db.session.add(Customer(**row_data))
            elif table == 'contract': db.session.add(Contract(**row_data))

        db.session.commit()
        flash(f"✅ Imported into {table} successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Import failed: {str(e)}", "danger")

    return redirect(url_for('settings.settings_page'))

@settings_bp.route('/settings/download-template/<model>', methods=['GET'])
def download_template(model):
    templates = {
        'assets': ['account_code','customer_name','serial_number','service_location','region','technician_name','technician_email','contract','asset_Description','contract_expiry_date','last_pm_date','pm_freq','install_date','asset_code','asset_status','part_no','department'],
        'spares': ['material_nr','brand','material_desc','currency','price'],
        'tonermodel': ['asset_model','part_number','machine_type','tk_k','k_life','tk_c','c_life','tk_m','m_life','tk_y','y_life'],
        'tonercosting': ['toner_model','toner_type','source','unit_cost'],
        'customer': ['cust_code','cust_name','billing_company'],
        'contract': ['cust_code','cust_name','contract_code','cont_discription','durations','contract_start_date','contract_end_date','mono_commitment','mono_charge','mono_excess_charge','color_commitment','color_charge','color_excess_charge','rental_charges','software_rental','billing_cycle','contract_currency','billing_currency','billing_company','sales_person','email','document_path']
    }

    if model not in templates:
        flash("Invalid template request.", "danger")
        return redirect(url_for('settings.settings_page'))

    df = pd.DataFrame(columns=templates[model])
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, download_name=f"{model}_template.xlsx", as_attachment=True)

@settings_bp.route('/test-email', methods=['POST'])
def test_email():
    from flask import current_app
    test_email_address = request.form.get('test_email')
    if not test_email_address:
        flash("❌ No email provided for test!", "danger")
        return redirect(url_for('settings.settings_page'))

    try:
        msg = Message(
            subject="✅ SMTP Test Email",
            recipients=[test_email_address],
            body="This is a test email from SERVICE PULSE ERP SMTP settings.",
        )
        mail.send(msg)
        flash(f"✅ Test email sent successfully to {test_email_address}.", "success")
    except Exception as e:
        print("SMTP Test Error:", e)
        flash("❌ Failed to send test email. Check SMTP settings and logs.", "danger")

    return redirect(url_for('settings.settings_page'))
