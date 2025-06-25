from app.extensions import db
from sqlalchemy import inspect
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# ✅ Technician Model
from app.extensions import db

class Technician(db.Model):
    __tablename__ = 'technician'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(15))
    email = db.Column(db.String(100))
    status = db.Column(db.String(10))
    dob = db.Column(db.Date)
    next_of_kin = db.Column(db.String(100))
    kin_relation = db.Column(db.String(100))

    # 🆕 New fields for files
    photo_url = db.Column(db.Text)       # /static/uploads/technicians/abc.jpg
    id_card_url = db.Column(db.Text)     # /static/uploads/technicians/id_abc.pdf
    cv_url = db.Column(db.Text)          # /static/uploads/technicians/cv_abc.pdf

    # relationship with tickets if needed
    tickets = db.relationship('Ticket', backref='technician', lazy=True)



# ✅ Ticket Model
class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference_no = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    customer = db.Column(db.String(200), nullable=False)
    call_type = db.Column(db.String(100), nullable=False)
    technician_id = db.Column(db.Integer, db.ForeignKey("technician.id"), nullable=True)
    service_location = db.Column(db.String(100), nullable=True)
    asset_Description = db.Column(db.String(500), nullable=True)
    called_by = db.Column(db.String(500), nullable=True)


    estimated_time = db.Column(db.Integer, nullable=False, default=60)
    travel_time = db.Column(db.Integer, nullable=False, default=0)
    expected_completion_time = db.Column(db.DateTime, nullable=False)

    status = db.Column(db.String(20), default="Open")  # Open, First Completed, Spare, In Process
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    closed_at = db.Column(db.DateTime, nullable=True)

    serial_number = db.Column(db.String(200), nullable=True)
    email_id = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(200), nullable=True)
    action_taken = db.Column(db.String(1000), nullable=True)
    tat = db.Column(db.Integer, nullable=True)
    region = db.Column(db.String(100), nullable=True)

    complete = db.Column(db.String(1000), nullable=True)  # Completed/Pending
    mr_mono = db.Column(db.Integer, nullable=True)
    mr_color = db.Column(db.Integer, nullable=True)
    tat = db.Column(db.Integer, nullable=True)
    remaining_time = db.Column(db.String(1000), nullable=True)


# ✅ Assets Model
class Assets(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account_code = db.Column(db.String(100), nullable=False)
    customer_name = db.Column(db.String(255), nullable=False)
    serial_number = db.Column(db.String(100), unique=True, nullable=False)
    service_location = db.Column(db.String(255), nullable=True)
    region = db.Column(db.String(100), nullable=True)
    technician_name = db.Column(db.String(255), nullable=True)
    technician_email = db.Column(db.String(255), nullable=True)
    contract = db.Column(db.String(100), nullable=True)
    asset_Description = db.Column(db.Text, nullable=True)
    contract_expiry_date = db.Column(db.String(100), nullable=True)
    last_pm_date= db.Column(db.String(100), nullable=True)
    pm_freq = db.Column(db.String(100), nullable=True)
    install_date = db.Column(db.String(100), nullable=True)
    asset_code = db.Column(db.String(50), nullable=True)
    asset_status = db.Column(db.String(50), nullable=True)
    part_no = db.Column(db.String(50), nullable=True)
    department = db.Column(db.String(100), nullable=True)






# ✅ User Model for Login System
from flask_login import UserMixin
from app.extensions import db

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default="viewer")

    # ✅ User & Admin Management
    can_add_user = db.Column(db.Boolean, default=False)
    can_edit_user = db.Column(db.Boolean, default=False)
    can_delete_user = db.Column(db.Boolean, default=False)
    can_assign_roles = db.Column(db.Boolean, default=False)

    # 🛠 Ticketing System
    can_view_tickets = db.Column(db.Boolean, default=False)
    can_create_tickets = db.Column(db.Boolean, default=False)
    can_edit_tickets = db.Column(db.Boolean, default=False)
    can_close_tickets = db.Column(db.Boolean, default=False)
    can_assign_tickets = db.Column(db.Boolean, default=False)

    # 👷 Technician Management
    can_view_technicians = db.Column(db.Boolean, default=False)
    can_add_technicians = db.Column(db.Boolean, default=False)
    can_edit_technicians = db.Column(db.Boolean, default=False)

    # 🖨 Asset Management
    can_view_assets = db.Column(db.Boolean, default=False)
    can_add_assets = db.Column(db.Boolean, default=False)
    can_edit_assets = db.Column(db.Boolean, default=False)
    can_delete_assets = db.Column(db.Boolean, default=False)

    # 📄 Contracts Module


    can_view_contracts = db.Column(db.Boolean, default=False)
    can_add_contracts = db.Column(db.Boolean, default=False)
    can_edit_contracts = db.Column(db.Boolean, default=False)
    can_delete_contracts = db.Column(db.Boolean, default=False)

    # 🧾 Toner Requests
    can_request_toner = db.Column(db.Boolean, default=False)
    can_edit_toner_requests = db.Column(db.Boolean, default=False)
    can_view_toner_dashboard = db.Column(db.Boolean, default=False)
    can_delete_toner_request = db.Column(db.Boolean, default=False)

    # 🔧 Spare Parts
    can_request_spares = db.Column(db.Boolean, default=False)
    can_view_spare_dashboard = db.Column(db.Boolean, default=False)
    can_delete_spare_request = db.Column(db.Boolean, default=False)

    # 📊 Reports & Dashboards
    can_view_reports = db.Column(db.Boolean, default=False)
    can_export_data = db.Column(db.Boolean, default=False)

    # 👤 Customer Management
    can_view_customers = db.Column(db.Boolean, default=False)
    can_manage_customers = db.Column(db.Boolean, default=False)
    can_delete_customers = db.Column(db.Boolean, default=False)

    # 💰 Financial Dashboard
    can_view_financials = db.Column(db.Boolean, default=False)
    can_export_financials = db.Column(db.Boolean, default=False)
    can_view_pm = db.Column(db.Boolean, default=False)
    can_edit_pm = db.Column(db.Boolean, default=False)

    # 🛠 Preventive Maintenance (PM)
    can_schedule_pm = db.Column(db.Boolean, default=False)
    can_view_pm_dashboard = db.Column(db.Boolean, default=False)

    # ⚙ System / Misc
    can_access_settings = db.Column(db.Boolean, default=False)
    can_upload_documents = db.Column(db.Boolean, default=False)
    can_view_audit_logs = db.Column(db.Boolean, default=False)


class spare_req(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    serial_number = db.Column(db.String, nullable=False)
    asset_Description = db.Column(db.String, nullable=False)
    code = db.Column(db.String, nullable=False)
    technician_id = db.Column(db.Integer, db.ForeignKey('technician.id'), nullable=False)
    technician_name = db.Column(db.String, nullable=False)
    reading = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    foc_no = db.Column(db.String, nullable=True)
    customer_name = db.Column(db.String, nullable=False)
    service_location = db.Column(db.String, nullable=False)
    region = db.Column(db.String, nullable=False)
    contract = db.Column(db.String, nullable=False)
    contract_expiry_date = db.Column(db.String, nullable=False)
    product_code = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    yield_achvd = db.Column(db.String, nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    spare_type = db.Column(db.String, nullable=False)
    warehouse = db.Column(db.String, nullable=False)
    any_remarks = db.Column(db.String, nullable=True)
    warranty_status = db.Column(db.String, nullable=False)
    warranty_remarks = db.Column(db.String, nullable=True)
    request_id = db.Column(db.String(50), nullable=False)



class spares(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    material_nr = db.Column(db.String, nullable=False)
    brand = db.Column(db.String, nullable=False)
    material_desc = db.Column(db.String, nullable=False)
    currency = db.Column(db.String, nullable=False)
    price = db.Column(db.Float, nullable=False)

from app import db
from datetime import datetime
class ScheduledReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    period = db.Column(db.String(50), nullable=True)
    technician_id = db.Column(db.Integer, nullable=True)
    region = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), nullable=True)
    call_type = db.Column(db.String(50), nullable=True)
    customer = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), nullable=False)
    schedule = db.Column(db.String(50), nullable=False)  # Daily, Weekly, Monthly
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    next_run = db.Column(db.DateTime)  # << ADD THIS COLUMN


from app.extensions import db
from datetime import datetime


# ✅ Customer Model (Matches "cust" table in SQLite)
class Customer(db.Model):
    __tablename__ = "cust"  # Ensure the model matches the actual table name in the DB

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cust_code = db.Column(db.String, nullable=False)  # No global uniqueness, but handled per billing_company
    cust_name = db.Column(db.String, nullable=False, unique=True)  # Must be globally unique
    billing_company = db.Column(db.String, nullable=False)

    # Relationship: A customer can have multiple contracts
    contracts = db.relationship("Contract", backref="customer", lazy=True)

    def __repr__(self):
        return f"<Customer {self.cust_code} - {self.cust_name}>"


# ✅ Contract Model (Matches "contract" table in SQLite)
class Contract(db.Model):
    __tablename__ = "contract"  # Ensure the model matches the actual table name in the DB

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cust_code = db.Column(db.String, db.ForeignKey("cust.cust_code"), nullable=False)  # Linked to Customer
    cust_name = db.Column(db.String, nullable=False)
    contract_code = db.Column(db.String, nullable=False, unique=True)  # Unique contract identifier
    cont_discription = db.Column(db.Text, nullable=True)
    durations = db.Column(db.Integer, nullable=False)

    # SQLite stores date as TEXT; parse it properly
    contract_start_date = db.Column(db.String, nullable=False)
    contract_end_date = db.Column(db.String, nullable=False)

    mono_commitment = db.Column(db.String, nullable=True)
    mono_charge = db.Column(db.String, nullable=True)
    mono_excess_charge = db.Column(db.Float, nullable=True)
    color_commitment = db.Column(db.String, nullable=True)
    color_charge = db.Column(db.String, nullable=True)
    color_excess_charge = db.Column(db.String, nullable=True)
    rental_charges = db.Column(db.String, nullable=True)
    software_rental = db.Column(db.String, nullable=True)
    billing_cycle = db.Column(db.String, nullable=True)
    contract_currency = db.Column(db.String, nullable=True)

    # Fix column name case mismatch in the DB: "Billing currency"
    billing_currency = db.Column(db.String, nullable=True, name="Billing currency")

    billing_company = db.Column(db.String, nullable=True)
    sales_person = db.Column(db.String, nullable=True)
    email = db.Column(db.String, nullable=True)
    document_path = db.Column(db.String(255))

    def __repr__(self):
        return f"<Contract {self.contract_code} - {self.cust_code}>"
class toner_request(db.Model):
    __tablename__ = 'toner_request'

    id = db.Column(db.Integer, primary_key=True)
    date_issued = db.Column(db.DateTime, default=datetime.utcnow)

    # Asset & Customer Info (auto-fetched)
    serial_number = db.Column(db.String(100), nullable=False)
    asset_code = db.Column(db.String(50), nullable=True)
    asset_description = db.Column(db.String(255), nullable=True)
    cust_code = db.Column(db.String(100), nullable=True)
    customer_name = db.Column(db.String(255), nullable=True)
    billing_company = db.Column(db.String(100), nullable=True)
    contract_code = db.Column(db.String(100), nullable=True)
    service_location = db.Column(db.String(255), nullable=True)
    region = db.Column(db.String(100), nullable=True)


    # Toner Details
    toner_type = db.Column(db.String(10), nullable=False)  # K / C / M / Y
    toner_model = db.Column(db.String(50), nullable=False)
    toner_source = db.Column(db.String(50), nullable=True)  # Kyocera / HK / Refilled
    toner_life = db.Column(db.Integer, nullable=True)  # Yield
    issued_qty = db.Column(db.Integer, default=1)
    unit_cost = db.Column(db.Float, nullable=True)
    total_cost = db.Column(db.Float, nullable=True)

    # Meter & Delivery Info
    meter_reading = db.Column(db.Integer, nullable=True)
    actual_coverage = db.Column(db.Float, nullable=True)
    previous_reading = db.Column(db.Integer)

    delivery_boy = db.Column(db.String(100), nullable=True)
    delivery_date = db.Column(db.DateTime, nullable=True)
    receiver_name = db.Column(db.String(100), nullable=True)
    delivery_status = db.Column(db.String(50), default='Pending')  # Pending / Delivered / Cancelled

    # System Fields
    requested_by = db.Column(db.String(100), nullable=True)
    issued_by = db.Column(db.String(100), nullable=True)
    comments = db.Column(db.Text, nullable=True)
    request_type = db.Column(db.String(50), nullable=True)
    foc = db.Column(db.String(50), nullable=True)
    request_group= db.Column(db.String(50), nullable=True)
    dispatch_time = db.Column(db.DateTime, nullable=True)

    # TAT is a calculated field (date_issued to delivery_date), not stored in DB but can be exposed in a property
    @property
    def tat(self):
        if self.delivery_date:
            return (self.delivery_date - self.date_issued).days
        return None

class ContractNotificationLog(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        contract_code = db.Column(db.String(100))
        stage = db.Column(db.String(50))  # "60_day", "30_day", "expired"
        sent_at = db.Column(db.DateTime, default=datetime.utcnow)


class TonerModel(db.Model):
    __tablename__ = 'toner_models'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    asset_model = db.Column(db.String(255), nullable=False)
    part_number = db.Column(db.String(255), nullable=False)
    machine_type = db.Column(db.String(50), nullable=False)  # MONO / COLOR / SCANNER

    # Black
    tk_k = db.Column(db.String(50), nullable=True)
    k_life = db.Column(db.Integer, nullable=True)

    # Cyan
    tk_c = db.Column(db.String(50), nullable=True)
    c_life = db.Column(db.Integer, nullable=True)

    # Magenta
    tk_m = db.Column(db.String(50), nullable=True)
    m_life = db.Column(db.Integer, nullable=True)

    # Yellow
    tk_y = db.Column(db.String(50), nullable=True)
    y_life = db.Column(db.Integer, nullable=True)

    def __repr__(self):
        return f"<TonerModel {self.asset_description}>"

class TonerCosting(db.Model):
    __tablename__ = 'toner_costing'

    id = db.Column(db.Integer, primary_key=True)
    toner_model = db.Column(db.String(50), nullable=False)
    toner_type = db.Column(db.String(10), nullable=False)  # K / C / M / Y
    source = db.Column(db.String(50), nullable=False)  # Kyocera / HK / Refilled
    unit_cost = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<TonerCosting {self.toner_model} - {self.source}>"

def create_tables_if_not_exist():
    """Check if tables exist, and create them if missing"""
    with db.engine.connect() as connection:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        required_tables = [
            "technician", "ticket", "assets", "user",
            "toner_request", "toner_models", "toner_costing"
        ]

        missing_tables = [table for table in required_tables if table not in tables]

        if missing_tables:
            print("📌 Creating missing tables...")
            db.create_all()
            print(f"✅ Created tables: {', '.join(missing_tables)}")
        else:
            print("✅ All required tables already exist.")


class DeliveryTeam(db.Model):
    __tablename__ = 'Delivery_Team'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f'<DeliveryTeam {self.name}>'

class McModel(db.Model):
    __tablename__ = "mc_model"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    asset_description = db.Column(db.Text, nullable=True)
    part_no = db.Column(db.Text, nullable=True)
    type = db.Column(db.Text, nullable=True)
    price = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<McModel {self.asset_description}>"



class PreventiveMaintenance(db.Model):
    __tablename__ = 'preventive_maintenance'

    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(100), db.ForeignKey('assets.serial_number'), nullable=False)
    scheduled_date = db.Column(db.Date, nullable=False)
    performed_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(50), default='Pending')  # Pending, Completed
    remarks = db.Column(db.Text, nullable=True)
    technician_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)



from app import db



from datetime import datetime

class ScheduledReportLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('scheduled_report.id'))
    status = db.Column(db.String(50))
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

from datetime import datetime
from app import db



