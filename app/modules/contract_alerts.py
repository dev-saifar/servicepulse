from datetime import datetime
import os
from flask import current_app
from app import db, mail
from app.models import Contract, ContractNotificationLog
from flask_mail import Message
from flask import Blueprint

contract_alerts_bp = Blueprint('contract_alerts', __name__)

@contract_alerts_bp.route('/trigger-contract-alerts')
def trigger_alerts():
    send_contract_expiry_alerts()
    return "✅ Contract alerts processed."


def send_contract_email(contract, stage):
    subject = f"Contract Alert: {contract.contract_code} - {stage.replace('_', ' ').title()}"
    recipient = contract.email
    if not recipient:
        print(f"No email for contract {contract.contract_code}")
        return
    cc_emails = current_app.config.get("CONTRACT_ALERT_CC", [])
    body = f"""
    Dear {contract.sales_person or 'Team'},

    This is a reminder that the following contract is {stage.replace('_', ' ')}:

    • Contract Code: {contract.contract_code}
    • Customer: {contract.cust_name}
    • Billing Company: {contract.billing_company}
    • Start Date: {contract.contract_start_date}
    • End Date: {contract.contract_end_date}

    Please take the necessary action.

    Regards,
    Contract Management System
    """

    msg = Message(
        subject,
        recipients=[recipient],
        cc=cc_emails,
        body=body
    )

    # Attach document if exists
    if contract.document_path:
        try:
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], contract.document_path)
            with open(file_path, 'rb') as f:
                msg.attach(contract.document_path, 'application/octet-stream', f.read())
        except Exception as e:
            print(f"[Attachment Error] {contract.contract_code}: {e}")

    try:
        mail.send(msg)
        print(f"✅ Email sent to {recipient} for contract {contract.contract_code} ({stage})")
    except Exception as e:
        print(f"❌ Email failed for {contract.contract_code}: {e}")

def send_contract_expiry_alerts():
    today = datetime.today().date()
    contracts = Contract.query.all()

    for contract in contracts:
        if not contract.contract_end_date:
            continue

        try:
            end_date = datetime.strptime(contract.contract_end_date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Invalid date for contract {contract.contract_code}")
            continue

        days_remaining = (end_date - today).days
        stage = None

        if days_remaining == 60:
            stage = '60_day'
        elif days_remaining == 30:
            stage = '30_day'
        elif days_remaining < 0:
            stage = 'expired'

        if stage:
            already_sent = ContractNotificationLog.query.filter_by(
                contract_code=contract.contract_code,
                stage=stage
            ).first()

            if not already_sent:
                send_contract_email(contract, stage)
                db.session.add(ContractNotificationLog(cc=current_app.config.get("CONTRACT_ALERT_CC", []),
                    contract_code=contract.contract_code,
                    stage=stage
                ))

    db.session.commit()
@contract_alerts_bp.route('/send-test-alert/<contract_code>')
def send_test_alert(contract_code):
    contract = Contract.query.filter_by(contract_code=contract_code).first()
    if not contract:
        return f"❌ Contract {contract_code} not found."

    # 👇 Override email for testing
    contract.email = "a.saifar@groupmfi.com"  # 🔁 Replace with your email

    send_contract_email(contract, stage="TEST")
    return f"✅ Test alert sent for contract {contract_code}"
def generate_contract_expiry_excel():
    from app.models import Contract
    import pandas as pd
    from io import BytesIO
    from datetime import datetime, timedelta

    today = datetime.today().date()
    cutoff = today + timedelta(days=60)
    active, expiring, expired = [], [], []

    for c in Contract.query.all():
        try:
            end_date = datetime.strptime(c.contract_end_date, "%Y-%m-%d").date()
        except:
            continue

        row = {
            "Contract Code": c.contract_code,
            "Customer": c.cust_name,
            "Billing Company": c.billing_company,
            "Start": c.contract_start_date,
            "End": c.contract_end_date,
            "Salesperson": c.sales_person,
            "Email": c.email,
            "Billing Cycle": c.billing_cycle
        }

        if end_date < today:
            expired.append(row)
        elif today <= end_date <= cutoff:
            expiring.append(row)
        else:
            active.append(row)

    df1 = pd.DataFrame(active)
    df2 = pd.DataFrame(expiring)
    df3 = pd.DataFrame(expired)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df1.to_excel(writer, sheet_name="Active Contracts", index=False)
        df2.to_excel(writer, sheet_name="Expiring Soon", index=False)
        df3.to_excel(writer, sheet_name="Expired Contracts", index=False)
    output.seek(0)

    filename = f"contract_expiry_{today.strftime('%Y%m%d')}.xlsx"
    return output, filename
