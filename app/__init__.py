# app/__init__.py
import os
from pathlib import Path
from datetime import datetime

from flask import Flask, redirect, url_for, render_template, request
from flask_migrate import Migrate
from flask_login import LoginManager, current_user, login_required
from dotenv import load_dotenv

from config import Config
from app.extensions import db, mail
from app.celery import make_celery
from app.modules.db_logger import Log
from app.models import create_tables_if_not_exist, User
# add near top with other imports
from sqlalchemy import event
from sqlalchemy.engine import Engine

# ensure SQLite FKs are enforced
@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    try:
        if dbapi_connection.__class__.__module__.startswith("sqlite3"):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    except Exception:
        pass

# Globals
celery = None
migrate = Migrate()
login_manager = LoginManager()


# -------------------------
# SMTP reloader helpers
# -------------------------
def _clean(v):
    return None if v is None else str(v).strip().strip("'\"")


def _to_bool(v, default=False):
    if v is None:
        return default
    return _clean(v).lower() in ("1", "true", "yes", "on")


def _to_int(v, default):
    try:
        return int(_clean(v))
    except Exception:
        return default


def _env_path() -> str:
    # Adjust if your .env lives elsewhere
    return str(Path(os.getcwd()) / ".env")


def apply_smtp_from_env(app):
    """
    Read SMTP keys from env/.env, clean types, set app.config,
    and re-init Flask-Mail so changes take effect immediately.
    """
    load_dotenv(dotenv_path=_env_path(), override=True)

    server = _clean(os.getenv("MAIL_SERVER", "smtp.gmail.com"))
    port = _to_int(os.getenv("MAIL_PORT", 587), 587)
    username = _clean(os.getenv("MAIL_USERNAME"))
    password = _clean(os.getenv("MAIL_PASSWORD"))
    if password:
        # Guard against pasted Gmail App Passwords that include spaces
        password = password.replace(" ", "")
    default_sender = _clean(os.getenv("MAIL_DEFAULT_SENDER")) or username

    # TLS/SSL logic: infer from port if flags missing
    use_tls_raw = os.getenv("MAIL_USE_TLS")
    use_ssl_raw = os.getenv("MAIL_USE_SSL")
    if use_tls_raw is None and use_ssl_raw is None:
        use_tls = (port == 587)
        use_ssl = (port == 465)
    else:
        use_tls = _to_bool(use_tls_raw, True)
        use_ssl = _to_bool(use_ssl_raw, False)
        if use_tls and use_ssl:  # never both; prefer SSL if both set
            use_tls, use_ssl = False, True

    app.config.update(
        MAIL_SERVER=server,
        MAIL_PORT=port,
        MAIL_USERNAME=username,
        MAIL_PASSWORD=password,
        MAIL_DEFAULT_SENDER=default_sender,
        MAIL_USE_TLS=use_tls,
        MAIL_USE_SSL=use_ssl,
        MAIL_SUPPRESS_SEND=False,
    )
    mail.init_app(app)  # rebind with latest config

    # Optional: log effective values
    app.logger.info(
        "SMTP loaded: %s",
        {
            "server": app.config.get("MAIL_SERVER"),
            "port": app.config.get("MAIL_PORT"),
            "tls": app.config.get("MAIL_USE_TLS"),
            "ssl": app.config.get("MAIL_USE_SSL"),
            "user": app.config.get("MAIL_USERNAME"),
            "from": app.config.get("MAIL_DEFAULT_SENDER"),
        },
    )


# ---------------
# App Factory
# ---------------
def create_app():
    global celery

    # Load .env before anything else
    load_dotenv(dotenv_path=_env_path(), override=True)

    app = Flask(__name__)
    app.config.from_object(Config)

    # Your app-specific config
    app.config['CONTRACT_ALERT_CC'] = ['a.saifar@groupmfi.com']
    app.config["DEBUG"] = True
    app.config["ENV"] = "development"

    # If Config didn’t provide a DB URL, fall back to local sqlite
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///techtrack.db"

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)  # initial; will be refreshed by apply_smtp_from_env
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id: str):
        # SA 1.4/2.x friendly loader with fallback
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            try:
                return User.query.get(int(user_id))
            except Exception:
                return None

    # 🔄 Apply SMTP from .env on startup
    apply_smtp_from_env(app)

    # Jinja filters
    def datetimeformat(value):
        try:
            return datetime.strptime(value, "%Y/%d/%m %H:%M:%S").strftime("%Y-%m-%d")
        except Exception:
            try:
                return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
            except Exception:
                return ""
    app.jinja_env.filters["datetimeformat"] = datetimeformat

    # Handy template helper to avoid BuildError when optional modules aren’t mounted
    @app.context_processor
    def _endpoint_tools():
        def endpoint_exists(name):
            try:
                url_for(name)
                return True
            except Exception:
                return False
        return {"current_user": current_user, "endpoint_exists": endpoint_exists}

    # Request logging
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

    # Error pages
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html", user=current_user), 403

    @app.errorhandler(Exception)
    def handle_exception(e):
        try:
            message = f"❌ Error on {request.method} {request.path}: {str(e)}"
            error_log = Log(level="ERROR", message=message)
            db.session.add(error_log)
            db.session.commit()
        except Exception:
            pass  # Avoid logging loop
        import traceback
        return f"<pre>{traceback.format_exc()}</pre>", 500

    # Celery
    celery = make_celery(app)

    # Routes
    @app.route("/")
    def home():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        return redirect(url_for("dashboard.index"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        return redirect(url_for("dashboard.index"))

    # Create tables if missing
    with app.app_context():
        from app.models import spare_req, Assets, spares, Technician  # noqa: F401
        from app.modules.inventory import models as _inv_models  # noqa: F401
        create_tables_if_not_exist()


    # -------------------
    # Register Blueprints
    # -------------------
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
    from app.modules.contracts import contracts_bp
    from app.modules.assets_add import assets_add_bp
    from app.modules.toner import toner_bp
    from app.modules import financial
    financial.cache.init_app(app)
    from app.modules.delivery_report import delivery_report_bp
    from app.modules.dashboard_rotator import dashboard_rotator_bp
    from app.modules.contract_alerts import contract_alerts_bp
    from app.modules.gate_pass import gate_pass_bp
    from app.modules.settings import settings_bp  # SMTP UI & Test endpoint

    app.register_blueprint(dashboard_rotator_bp)
    app.register_blueprint(contract_alerts_bp, url_prefix='/contract_alert')
    app.register_blueprint(gate_pass_bp, url_prefix='/gatepass')       # <-- ensure gate_pass endpoints resolve
    app.register_blueprint(settings_bp)                                 # <-- /settings + /settings/test-email

    from app.models import PendingDelivery  # noqa: F401

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
    from app.modules.license import license_bp
    app.register_blueprint(license_bp)
    from app.modules.license_status import license_status_bp
    app.register_blueprint(license_status_bp)
    # after other blueprints
    from app.modules.inventory import inventory_bp
    app.register_blueprint(inventory_bp, url_prefix="/inventory")

    # CLI command
    from app.modules.inventory.cli import register_inventory_cli
    register_inventory_cli(app)

    # -------------------------
    # License enforcement guard
    # -------------------------
    from app.modules.license_utils import is_license_valid

    ALLOWED_ENDPOINTS = {
        "license.license_page",           # activation page
        "license_status.license_info",    # license info page
        "about.about",                    # allowed
        "about.download_license_info",    # helper for generating info
        "auth.login",                     # allow login
        "auth.logout",                    # allow logout
        "static",                         # static files
    }

    @app.before_request
    def enforce_license_check():
        endpoint = (request.endpoint or "")
        if not endpoint or endpoint in ALLOWED_ENDPOINTS or endpoint.startswith("static"):
            return None

        ok, _ = is_license_valid()
        if ok:
            return None

        # Block and send user to activation page, preserve "next"
        return redirect(url_for("license.license_page", next=request.url))

    # Debug DB URL
    print(f"📌 Database URL: {app.config['SQLALCHEMY_DATABASE_URI']}")

    return app
