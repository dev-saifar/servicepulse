Repository Overview

This project is a Flask application that tracks service tickets, technicians, assets, toner/spare requests and financial reports. It integrates Celery for background tasks, Flask‑Login for authentication and SQLAlchemy for ORM.

/
├── app/                 → core Flask package
│   ├── __init__.py      → creates the Flask app and registers blueprints
│   ├── celery.py        → Celery configuration
│   ├── extensions.py    → initializes db, migrate and mail instances
│   ├── models.py        → SQLAlchemy models (Technician, Ticket, Assets, etc.)
│   ├── modules/         → feature blueprints (auth, assets, tickets, reports…)
│   ├── static/          → CSS/JS/images
│   └── templates/       → Jinja2 HTML templates
├── config.py            → configuration (DB URI, mail settings, Celery broker)
├── run.py               → simple entry point calling `create_app()`
├── migrations/          → Alembic database migrations
└── tests/               → placeholder for unit tests
Key Components
App Factory & Blueprints
create_app() configures the app, initializes extensions and registers a large set of blueprints (dashboard, technicians, tickets, assets, etc.). A license check is enforced before each request if a license file is missing or invalid.

Configuration
config.py sets default values, including Celery/Redis and Flask‑Mail connection details.

Database Models
app/models.py defines tables such as Technician, Ticket, Assets, and User. The User model contains many Boolean permission flags which determine access to various features.

Background Tasks
app/tasks.py defines a Celery task generate_and_email_report to produce scheduled reports and email them to recipients. Celery is initialized via make_celery() in app/celery.py.

License Utilities
The application uses encrypted license files; helper functions in license_utils.py load, save and validate the license at startup.

Modules/Blueprints
The modules package contains separate files for each feature set, e.g. tickets.py, assets.py, technicians.py, toner.py, financial.py and an advanced reporting system in advance_report.py.

Templates and Static Assets
app/templates/ and app/static/ contain HTML templates, CSS/JS, and images used across the blueprints.

Things to Know When Working With the Codebase
App factory pattern – create_app() must be used by tests, Celery workers and the run.py script.

Permissions – The User model has many permission columns; blueprints check them using the permission_required decorator in app/utils/permission_required.py.

Celery – Scheduled jobs or long‑running tasks should be added to tasks.py. Workers rely on Redis as the message broker.

Database – SQLite is used by default (see .env or config.py). Alembic migrations under migrations/ track schema changes.

Email & Reporting – Many modules send email via Flask-Mail or direct SMTP (e.g., advanced reports). Check config.py for mail credentials.

License Enforcement – The application blocks most routes if the license file is missing or invalid. See license_utils.py and license.py for details.

Suggested Next Steps
Become comfortable with Flask blueprints and Jinja templates to understand how pages are rendered and how new routes are added.

Review the SQLAlchemy models in app/models.py to see the database schema and relationships.

Explore Celery usage for scheduled reports. Running a Celery worker alongside the Flask app is necessary for background tasks.

Examine the financial.py and advance_report.py modules if you need complex reporting or exports—they showcase SQLAlchemy queries and Excel generation.

Consider adding tests under tests/ (currently mostly empty) to validate key features such as authentication and CRUD operations.

Overall, this codebase provides a fairly full-featured service management dashboard. Understanding Flask, SQLAlchemy, and Celery will help you extend or maintain it effectively.


