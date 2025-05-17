# app/modules/db_logger.py
from datetime import datetime
from app import db

class Log(db.Model):
    __tablename__ = 'log'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    level = db.Column(db.String(50))
    message = db.Column(db.Text)

def log_info(message):
    log = Log(level='INFO', message=message)
    db.session.add(log)
    db.session.commit()

def log_error(message):
    log = Log(level='ERROR', message=message)
    db.session.add(log)
    db.session.commit()

