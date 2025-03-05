from app.extensions import db
from sqlalchemy import inspect
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


# ✅ Technician Model
class Technician(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(15), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(10), nullable=True)  # Free/Busy
    dob = db.Column(db.Date, nullable=True)

    # Relationship: A technician can have multiple tickets
    tickets = db.relationship("Ticket", backref="technician", lazy=True)


# ✅ Ticket Model
class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference_no = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
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




# ✅ User Model for Login System
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        """ Hash and set password """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """ Check password against stored hash """
        return check_password_hash(self.password_hash, password)

class spare_req(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    serial_number = db.Column(db.String, nullable=False)
    asset_Description = db.Column(db.String, nullable=False)
    code = db.Column(db.String, nullable=False)
    technician_id = db.Column(db.Integer, db.ForeignKey('technician.id'), nullable=False)
    technician_name = db.Column(db.String, nullable=False)
    reading = db.Column(db.Integer, nullable=False)
    date = db.Column(db.String, nullable=False)
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



class spares(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    material_nr = db.Column(db.String, nullable=False)
    brand = db.Column(db.String, nullable=False)
    material_desc = db.Column(db.String, nullable=False)
    currency = db.Column(db.String, nullable=False)
    price = db.Column(db.Float, nullable=False)


# ✅ Ensure Tables Exist and Create Them If Missing
def create_tables_if_not_exist():
    """Check if tables exist, and create them if missing"""
    with db.engine.connect() as connection:
        inspector = inspect(db.engine)

        tables = inspector.get_table_names()

        if "technician" not in tables or "ticket" not in tables or "assets" not in tables or "user" not in tables:
            print("📌 Creating missing tables...")
            db.create_all()
            print("✅ Tables created successfully!")
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
