import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key")
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", f"sqlite:///{os.path.join(BASE_DIR, 'techtrack.db')}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Celery Configuration
    CELERY_BROKER_URL = 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

    # Flask-Mail Configuration (NOW FROM .env)
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.example.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True") == "True"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", MAIL_USERNAME)

