# app/utils/backup_utils.py
import os, zipfile
from datetime import datetime, timedelta
from flask import current_app

def create_internal_backup():
    BACKUP_DIR = os.path.join(current_app.root_path, 'backups')
    SOURCE_DIRS = [
        os.path.join(current_app.root_path, 'database', 'servicepulse.db'),
        os.path.join(current_app.root_path, 'uploads'),
        os.path.join(current_app.root_path, 'reports'),
    ]
    EXCLUDE = ['__pycache__', 'venv', 'logs']
    DAYS_TO_KEEP = 7

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_zip = os.path.join(BACKUP_DIR, f'backup_{timestamp}.zip')

    with zipfile.ZipFile(backup_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for source in SOURCE_DIRS:
            if os.path.isfile(source):
                zipf.write(source, os.path.basename(source))
            else:
                for root, dirs, files in os.walk(source):
                    dirs[:] = [d for d in dirs if d not in EXCLUDE]
                    for file in files:
                        full_path = os.path.join(root, file)
                        arcname = os.path.relpath(full_path, start=current_app.root_path)
                        zipf.write(full_path, arcname)

    # Auto delete old backups
    now = datetime.now()
    for f in os.listdir(BACKUP_DIR):
        fpath = os.path.join(BACKUP_DIR, f)
        if f.endswith('.zip') and os.path.isfile(fpath):
            created = datetime.fromtimestamp(os.path.getctime(fpath))
            if now - created > timedelta(days=DAYS_TO_KEEP):
                os.remove(fpath)

    print(f"✅ Backup created at: {backup_zip}")
