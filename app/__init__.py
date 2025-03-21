from flask import Flask, redirect, url_for
from config import Config

from flask_migrate import Migrate  # ✅ Ensure Flask-Migrate is imported
from flask_login import LoginManager, current_user, login_required
from app.extensions import db, mail
from app.celery import make_celery
from app.models import create_tables_if_not_exist  # ✅ Ensure correct import
from app.models import User

# ✅ Define global extensions
celery = None
migrate = Migrate()
login_manager = LoginManager()
from celery import Celery

celery = Celery(__name__, broker='redis://localhost:6379/0')
from flask_mail import Mail
from config import Config

mail = Mail()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ✅ Initialize Flask-Mail
    mail.init_app(app)

    return app


def create_app():
    global celery
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["DEBUG"] = True  # Enable Debug Mode
    app.config["ENV"] = "development"

    # ✅ Set the database URL before initializing SQLAlchemy
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///techtrack.db"

    # Initialize Flask Extensions
    db.init_app(app)
    migrate.init_app(app, db)  # ✅ Ensure Flask-Migrate is initialized properly
    mail.init_app(app)
    login_manager.init_app(app)  # ✅ Initialize Flask-Login

    # ✅ Redirect to Login Page if Unauthorized
    login_manager.login_view = "auth.login"

    # Initialize Celery
    celery = make_celery(app)

    # ✅ Print Database URL at Startup (For Debugging)
    print(f"📌 Database URL: {app.config['SQLALCHEMY_DATABASE_URI']}")

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ✅ Redirect to Login Page if Not Authenticated
    @app.route("/")
    def home():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))  # Redirect to login page if not logged in
        return redirect(url_for("dashboard.index"))  # Redirect to dashboard if logged in

    # ✅ Protect Dashboard Route
    @app.route("/dashboard")
    @login_required
    def dashboard():
        return redirect(url_for("dashboard.index"))

    # ✅ Run table creation inside app context
    with app.app_context():
        from app.models import spare_req, Assets, spares, Technician
        create_tables_if_not_exist()

    # ✅ Import and Register Blueprints
    from app.modules.dashboard import dashboard_bp
    from app.modules.technicians import technicians_bp
    from app.modules.assets import assets_bp
    from app.modules.about import about_bp
    from app.modules.auth import auth_bp  # ✅ Import Authentication Blueprint
    from app.modules.users import users_bp
    from app.modules.tickets import tickets_bp
    from app.modules.ticket1 import ticket1_bp
    from app.modules.report import report_bp
    from app.modules.hourly import hourly_bp
    from app.modules.material import material_bp
    from app.modules.advance_report import advance_report_bp
    from app.modules.technician_performance import technician_performance_bp
    from app.tasks import generate_and_email_report
    from app.modules.contracts import contracts_bp

    # ✅ Register Blueprints with correct URL prefixes
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(technicians_bp, url_prefix='/technicians')
    app.register_blueprint(tickets_bp, url_prefix='/tickets')
    app.register_blueprint(assets_bp, url_prefix='/assets')
    app.register_blueprint(about_bp, url_prefix='/about')
    app.register_blueprint(auth_bp, url_prefix='/auth')  # ✅ Register Authentication Blueprint
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(ticket1_bp, url_prefix='/ticket1')
    app.register_blueprint(report_bp, url_prefix='/report')
    app.register_blueprint(hourly_bp, url_prefix='/hourly')
    app.register_blueprint(material_bp, url_prefix='/material')
    app.register_blueprint(advance_report_bp, url_prefix='/advance_report')
    app.register_blueprint(technician_performance_bp, url_prefix='/technician_performance')
    app.register_blueprint(contracts_bp, url_prefix='/contracts')



    return app
