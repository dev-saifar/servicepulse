from celery import Celery
from celery.schedules import crontab
from config import Config

celery = None  # Define Celery globally

def make_celery(app):
    global celery
    celery = Celery(
        app.import_name,
        backend=Config.CELERY_RESULT_BACKEND,
        broker=Config.CELERY_BROKER_URL
    )
    celery.conf.update(app.config)

    # ✅ Add periodic task schedule
    celery.conf.beat_schedule = {
        'send_contract_alerts_daily': {
            'task': 'app.tasks.run_contract_alerts',
            'schedule': crontab(hour=8, minute=0),  # Every day at 8:00 AM
        }
    }

    celery.conf.timezone = 'Africa/Kampala'  # ⏰ Set your timezone if needed
    return celery
