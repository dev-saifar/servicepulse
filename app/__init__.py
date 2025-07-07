from flask import Flask, redirect, url_for
from config import Config
from flask import render_template
from flask_migrate import Migrate  # ✅ Ensure Flask-Migrate is imported
from flask_login import LoginManager, current_user, login_required
from app.extensions import db, mail
from app.celery import make_celery
from app.models import create_tables_if_not_exist  # ✅ Ensure correct import
from app.models import User
from flask_login import current_user
from flask import request
from app.modules.db_logger import Log
from app import db
# ✅ Define global extensions
celery = None
migrate = Migrate()
login_manager = LoginManager()
from celery import Celery

celery = Celery(__name__, broker='redis://localhost:6379/0')
from flask_mail import Mail
from config import Config



def create_app():
    global celery
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['CONTRACT_ALERT_CC'] = ['a.saifar@groupmfi.com']

    app.config["DEBUG"] = True
    app.config["ENV"] = "development"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///techtrack.db"
    mail.init_app(app)

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html', user=current_user), 403

    @app.after_request
    def log_request(response):
        try:
            message = f'{request.remote_addr} - [{request.method}] "{request.path}" {response.status_code}'
            new_log = Log(level="INFO", message=message)
            db.session.add(new_log)
            db.session.commit()
        except Exception as e:
            # Avoid circular errors
            print("Logging failed:", e)
        return response

    @app.errorhandler(Exception)
    def handle_exception(e):
        try:
            message = f'❌ Error on {request.method} {request.path}: {str(e)}'
            error_log = Log(level="ERROR", message=message)
            db.session.add(error_log)
            db.session.commit()
        except:
            pass  # Avoid logging loop
        import traceback
        return f"<pre>{traceback.format_exc()}</pre>", 500

    # Register custom datetimeformat filter


    from datetime import datetime

    def datetimeformat(value):
        try:
            return datetime.strptime(value, '%Y/%d/%m %H:%M:%S').strftime('%Y-%m-%d')
        except Exception:
            try:
                return datetime.strptime(value, '%Y-%m-%d').strftime('%Y-%m-%d')
            except:
                return ''

    app.jinja_env.filters['datetimeformat'] = datetimeformat


    # Init Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    login_manager.init_app(app)
    celery = make_celery(app)

    # Flask-Login config
    login_manager.login_view = "auth.login"

    print(f"📌 Database URL: {app.config['SQLALCHEMY_DATABASE_URI']}")

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.route("/")
    def home():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        return redirect(url_for("dashboard.index"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        return redirect(url_for("dashboard.index"))

    # Table creation
    with app.app_context():
        from app.models import spare_req, Assets, spares, Technician
        create_tables_if_not_exist()

    # Register Blueprints
    from app.modules.dashboard import dashboard_bp
    from app.modules.technicians import technicians_bp
    from app.modules.assets import assets_bp
    from app.modules.about import about_bp
    from app.modules.auth import auth_bp
    from app.modules.users import users_bp
    from app.modules.tickets import tickets_bp
    from app.modules.ticket1 import ticket1_bp
    from app.modules.report import report_bp
    from app.modules.hourly import hourly_bp
    from app.modules.material import material_bp
    from app.modules.advance_report import advance_report_bp
    from app.modules.financial import financial_bp
    from app.modules.technician_performance import technician_performance_bp
    from app.tasks import generate_and_email_report
    from app.modules.contracts import contracts_bp
    from app.modules.assets_add import assets_add_bp
    from app.modules.toner import toner_bp
    from app.modules import financial
    financial.cache.init_app(app)
    from app.modules.delivery_report import delivery_report_bp
    from app.modules.dashboard_rotator import dashboard_rotator_bp
    app.register_blueprint(dashboard_rotator_bp)
    from app.modules.contract_alerts import contract_alerts_bp
    app.register_blueprint(contract_alerts_bp, url_prefix='/contract_alert')
    from app.modules.gate_pass import gate_pass_bp
    app.register_blueprint(gate_pass_bp, url_prefix='/gatepass')

    app.register_blueprint(delivery_report_bp, url_prefix='/delivery_report')
    app.register_blueprint(financial_bp, url_prefix='/financial')
    app.register_blueprint(toner_bp, url_prefix='/toner')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(technicians_bp, url_prefix='/technicians')
    app.register_blueprint(tickets_bp, url_prefix='/tickets')
    app.register_blueprint(assets_bp, url_prefix='/assets')
    app.register_blueprint(about_bp, url_prefix='/about')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(ticket1_bp, url_prefix='/ticket1')
    app.register_blueprint(report_bp, url_prefix='/report')
    app.register_blueprint(hourly_bp, url_prefix='/hourly')
    app.register_blueprint(material_bp, url_prefix='/material')
    app.register_blueprint(advance_report_bp, url_prefix='/advance_report')
    app.register_blueprint(technician_performance_bp, url_prefix='/technician_performance')
    app.register_blueprint(contracts_bp, url_prefix='/contracts')
    app.register_blueprint(assets_add_bp, url_prefix='/assets_add')
    from app.modules.logs_dashboard import logs_bp
    app.register_blueprint(logs_bp)
    from app.modules import db_logger  # Ensure Log model is registered
    from app.modules.license_utils import is_license_valid
    from app.modules.license import license_bp
    app.register_blueprint(license_bp)
    from app.modules.license_status import license_status_bp
    app.register_blueprint(license_status_bp)
    from flask import request

    valid, reason = is_license_valid()

    if not valid:
        print("❌ License check failed:", reason)

        @app.before_request
        def enforce_license_check():
            allowed_endpoints = [
                'license.license_page',
                'about.about',
                'about.download_license_info',
                'static'
            ]

            if not request.endpoint or request.endpoint not in allowed_endpoints:
                print(f"🔒 Blocking access to {request.endpoint} due to invalid license.")
                return redirect(url_for("license.license_page"))

    return app

