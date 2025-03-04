import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key")
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", f"sqlite:///{os.path.join(BASE_DIR, 'techtrack.db')}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Celery Configuration
    CELERY_BROKER_URL = 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

    # Flask-Mail Configuration
    MAIL_SERVER = 'secure.emailsrvr.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = "emailprint.ug@groupmfi.com"
    MAIL_PASSWORD = "mfiug$987@"
    MAIL_DEFAULT_SENDER = "emailprint.ug@groupmfi.com"
