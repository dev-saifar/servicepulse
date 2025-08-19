# app/modules/settings.py
from flask import Blueprint, render_template, request, redirect, flash, url_for, current_app, send_file, abort
from werkzeug.utils import secure_filename
from dotenv import set_key, dotenv_values
from flask_mail import Message
from app.extensions import db, mail
from app.models import Assets, spares, TonerModel, TonerCosting, Customer, Contract
from functools import wraps
from flask_login import current_user
import os
import sys
import re
import pandas as pd
from io import BytesIO
import datetime
import shutil
import subprocess
from urllib.parse import urlparse
import string

# ---------- Optional Google Drive ----------
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    _gdrive_available = True
except Exception:
    _gdrive_available = False

# ---------- Optional APScheduler ----------
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    _scheduler = BackgroundScheduler(timezone="Africa/Kampala")
except Exception:
    _scheduler = None

settings_bp = Blueprint('settings', __name__, template_folder='../templates/settings')

# ===================== Auth / Admin guard =====================
def _login_url():
    try:
        return url_for('auth.login', next=request.url)
    except Exception:
        try:
            return url_for('login', next=request.url)
        except Exception:
            return '/login?next=' + request.url

def _is_admin(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_admin", False):
        return True
    role_attr = str(getattr(user, "role", "")).lower()
    if role_attr == "admin":
        return True
    roles = getattr(user, "roles", [])
    try:
        lowered = [r.name.lower() if hasattr(r, "name") else str(r).lower() for r in roles]
    except Exception:
        lowered = [str(roles).lower()]
    return "admin" in lowered

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not getattr(current_user, "is_authenticated", False):
            flash("Please log in to access Settings.", "danger")
            return redirect(_login_url())
        if not _is_admin(current_user):
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

# ===================== .env helpers =====================
def _env_path():
    """Resolve the .env path relative to the app folder (not process CWD)."""
    app_root = current_app.root_path  # .../app
    candidates = [
        os.path.abspath(os.path.join(app_root, '..', '.env')),
        os.path.abspath(os.path.join(app_root, '.env')),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    os.makedirs(os.path.dirname(candidates[0]), exist_ok=True)
    open(candidates[0], 'a', encoding='utf-8').close()
    return candidates[0]

def _env(key, default=None):
    return dotenv_values(_env_path()).get(key, default)

def _set_env(key, value):
    set_key(_env_path(), key, str(value))

# ---- helper: show next scheduled backup time
def _next_run_text():
    """Return 'YYYY-MM-DD HH:MM' for the next scheduled backup, or None."""
    if not _scheduler:
        return None
    try:
        job = _scheduler.get_job("db_backup_job")
        if job and job.next_run_time:
            return job.next_run_time.strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    return None

# ---- helper: show next scheduled log cleanup time
def _next_log_run_text():
    if not _scheduler:
        return None
    try:
        job = _scheduler.get_job("log_cleanup_job")
        if job and job.next_run_time:
            return job.next_run_time.strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    return None

# ===================== Upload/Brand folders =====================
UPLOAD_FOLDER = os.path.join('app', 'uploads', 'imports')
KEYS_FOLDER = os.path.join('app', 'uploads', 'keys')
BRAND_FOLDER = os.path.join('app', 'static', 'uploads', 'branding')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(KEYS_FOLDER, exist_ok=True)
os.makedirs(BRAND_FOLDER, exist_ok=True)

# ===================== General helpers =====================
def _db_uri():
    return current_app.config.get('SQLALCHEMY_DATABASE_URI')

def _timestamp():
    return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

def _default_backup_dir():
    # Default: <project_root>/app/backups
    return os.path.join(current_app.root_path, 'backups')

def _is_unc(path: str) -> bool:
    return path.startswith('\\\\') or path.startswith('//')

def _unc_share_root(path: str) -> str:
    if not _is_unc(path):
        return ''
    p = path.replace('/', '\\')
    parts = [x for x in p.split('\\') if x]
    if len(parts) >= 2:
        return f"\\\\{parts[0]}\\{parts[1]}"
    return ''

def _sanitize_backup_path(p: str, default_dir: str) -> str:
    """
    Sanitize a user/env-provided path for saving backups.
    - strip quotes/control chars
    - normalize absolute
    - force forward slashes
    - drive roots / UNC roots get a '/db_backups' subfolder
    """
    p = (p or "").strip().strip('\'"')
    p = "".join(ch for ch in p if ord(ch) >= 32)
    p = p.replace("\\", "/")

    if not os.path.isabs(p) and not p.startswith("//"):
        p = os.path.abspath(p)
    else:
        p = os.path.normpath(p)

    p = p.replace("\\", "/")

    if re.fullmatch(r"[A-Za-z]:/?", p):
        p = p.rstrip("/").upper() + "/db_backups"

    if p.startswith("//"):
        parts = p.strip("/").split("/")
        if len(parts) == 2:
            p = p + "/db_backups"

    return p

def _sanitize_browse_path(p: str) -> str:
    """Sanitize for browsing (no auto-append)."""
    p = (p or "").strip().strip('\'"')
    p = "".join(ch for ch in p if ord(ch) >= 32)
    p = p.replace("\\", "/")
    if not p:
        return p
    if not os.path.isabs(p) and not p.startswith("//"):
        p = os.path.abspath(p)
    else:
        p = os.path.normpath(p)
    return p.replace("\\", "/")

def _backup_dir():
    default_dir = _default_backup_dir()
    raw = _env("DB_BACKUP_DIR", default_dir)
    path = _sanitize_backup_path(raw, default_dir)
    try:
        _maybe_connect_smb_for_path(path)
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        fallback = default_dir
        os.makedirs(fallback, exist_ok=True)
        current_app.logger.warning(f"Backup dir error ({e}), using fallback: {fallback}")
        path = fallback
    return path

def _list_windows_drives():
    drives = []
    if sys.platform == 'win32':
        for c in string.ascii_uppercase:
            root = f"{c}:/"
            if os.path.exists(root) or os.path.exists(root.replace('/', '\\')):
                drives.append(root)
    return drives

# ===================== DB helpers =====================
def _resolve_sqlite_path_from_uri(uri: str) -> str:
    rel = uri.split("sqlite:///", 1)[-1]
    candidates = []
    if os.path.isabs(rel):
        candidates.append(rel)
    else:
        candidates.append(os.path.join(current_app.root_path, rel))
        try:
            candidates.append(os.path.join(current_app.instance_path, rel))
        except Exception:
            pass
    for p in candidates:
        if os.path.exists(p):
            return os.path.abspath(p)
    return os.path.abspath(candidates[0])

def _maybe_connect_smb_for_path(path: str):
    if sys.platform != 'win32':
        return
    if not _is_unc(path):
        return
    if _env("SMB_ENABLED", "False") != "True":
        return
    share = _env("SMB_SHARE", "") or _unc_share_root(path)
    user = _env("SMB_USER", "")
    password = _env("SMB_PASSWORD", "")
    if not (share and user and password):
        return
    try:
        proc = subprocess.run(["net", "use", share, password, f"/user:{user}"],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            current_app.logger.info(f"SMB session attempt for {share} returned {proc.returncode}: {proc.stderr}")
    except Exception as e:
        current_app.logger.info(f"SMB session error for {share}: {e}")

def _extract_drive_folder_id(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    m = re.search(r'/folders/([a-zA-Z0-9_-]+)', s)
    if m: return m.group(1)
    m = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', s)
    if m: return m.group(1)
    if s.startswith("http"):
        return s.rsplit('/', 1)[-1].split('?', 1)[0]
    return s

# Branding helpers
_ALLOWED_BRAND_KEYS = {
    "BRAND_LOGO_LIGHT": "logo_light",
    "BRAND_LOGO_DARK": "logo_dark",
    "BRAND_LOGO_ICON": "logo_icon",
    "BRAND_WATERMARK": "watermark",
    "BRAND_STAMP": "stamp",
}
def _brand_rel_path(filename: str) -> str:
    return f"/static/uploads/branding/{filename}"

def _save_brand_file(file_storage, var_key: str) -> str:
    if not file_storage or not file_storage.filename:
        return _env(var_key, "")
    fn = secure_filename(file_storage.filename)
    root, ext = os.path.splitext(fn)
    out_name = f"{var_key.lower()}_{_timestamp()}{ext or '.png'}"
    dest = os.path.join(BRAND_FOLDER, out_name)
    file_storage.save(dest)
    return _brand_rel_path(out_name)

def _delete_brand_file(var_key: str):
    path = _env(var_key, "")
    if not path:
        return
    abs_path = os.path.abspath(os.path.join(current_app.root_path, path.lstrip('/')))
    if os.path.commonpath([abs_path, os.path.abspath(BRAND_FOLDER)]) != os.path.abspath(BRAND_FOLDER):
        return
    try:
        if os.path.isfile(abs_path):
            os.remove(abs_path)
    except Exception:
        pass
    _set_env(var_key, "")

def _render_doc_title(company_name: str, doc_type: str, fmt: str, upper: bool) -> str:
    dt = doc_type.upper() if upper else doc_type
    safe_fmt = fmt or "{company_name} ({doc_type})"
    return safe_fmt.replace("{company_name}", company_name or "").replace("{doc_type}", dt)

# ===================== Scheduler =====================
def _schedule_backup_job_from_env():
    if not _scheduler:
        return
    enabled = _env("DB_BACKUP_ENABLED", "False") == "True"
    time_str = _env("DB_BACKUP_TIME", "02:00")
    job_id = "db_backup_job"
    try:
        job = _scheduler.get_job(job_id)
        if job:
            _scheduler.remove_job(job_id)
    except Exception:
        pass
    if not enabled:
        return
    try:
        hour, minute = [int(x) for x in time_str.split(":")]
    except Exception:
        hour, minute = 2, 0
    trigger = CronTrigger(hour=hour, minute=minute)
    _scheduler.add_job(_run_scheduled_backup, trigger, id=job_id, replace_existing=True)

# ---- LOG CLEANUP scheduling
def _schedule_log_cleanup_job_from_env():
    if not _scheduler:
        return
    job_id = "log_cleanup_job"
    try:
        job = _scheduler.get_job(job_id)
        if job:
            _scheduler.remove_job(job_id)
    except Exception:
        pass

    enabled = _env("LOG_RETENTION_ENABLED", "False") == "True"
    if not enabled:
        return

    time_str = _env("LOG_CLEAN_TIME", "03:10")
    try:
        hour, minute = [int(x) for x in time_str.split(":")]
    except Exception:
        hour, minute = 3, 10
    trigger = CronTrigger(hour=hour, minute=minute)
    _scheduler.add_job(_run_log_cleanup, trigger, id=job_id, replace_existing=True)

@settings_bp.before_app_request
def _maybe_start_scheduler():
    if not _scheduler:
        return
    if not current_app.config.get("BACKUP_SCHEDULER_INITIALIZED", False):
        try:
            if not _scheduler.running:
                _scheduler.start()
            _schedule_backup_job_from_env()
            _schedule_log_cleanup_job_from_env()
            current_app.config["BACKUP_SCHEDULER_INITIALIZED"] = True
        except Exception as e:
            current_app.logger.exception("Failed to start scheduler: %s", e)

# ===================== Backups =====================
def _prune_old_backups(folder, keep_days):
    try:
        keep_days = int(keep_days)
    except Exception:
        keep_days = 7
    cutoff = datetime.datetime.now() - datetime.timedelta(days=keep_days)
    for name in os.listdir(folder):
        f = os.path.join(folder, name)
        try:
            if os.path.isfile(f) and datetime.datetime.fromtimestamp(os.path.getmtime(f)) < cutoff:
                os.remove(f)
        except Exception:
            pass

def _backup_sqlite(uri, dest_dir):
    src = _resolve_sqlite_path_from_uri(uri)
    if not os.path.exists(src):
        raise RuntimeError(f"SQLite file not found: {src}")
    _maybe_connect_smb_for_path(dest_dir)
    out = os.path.join(dest_dir, f"sqlite_{_timestamp()}.backup")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    shutil.copy2(src, out)
    return out

def _backup_postgres(uri, dest_dir):
    parsed = urlparse(uri)
    dbname = parsed.path.lstrip('/')
    user = parsed.username or ""
    password = parsed.password or ""
    host = parsed.hostname or "localhost"
    port = str(parsed.port or 5432)
    _maybe_connect_smb_for_path(dest_dir)
    out = os.path.join(dest_dir, f"pg_{dbname}_{_timestamp()}.backup")
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password
    args = ["pg_dump", "-h", host, "-p", port, "-U", user, "-F", "c", "-b", "-f", out, dbname]
    proc = subprocess.run(args, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or "pg_dump failed")
    return out

def _backup_mysql(uri, dest_dir):
    parsed = urlparse(uri)
    dbname = parsed.path.lstrip('/')
    user = parsed.username or ""
    password = parsed.password or ""
    host = parsed.hostname or "localhost"
    port = str(parsed.port or 3306)
    _maybe_connect_smb_for_path(dest_dir)
    out = os.path.join(dest_dir, f"mysql_{dbname}_{_timestamp()}.backup")
    args = ["mysqldump", "-h", host, "-P", port, "-u", user, f"--password={password}", dbname]
    with open(out, "w", encoding="utf-8") as fh:
        proc = subprocess.run(args, stdout=fh, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        err = proc.stderr if isinstance(proc.stderr, str) else (proc.stderr.decode() if proc.stderr else "mysqldump failed")
        raise RuntimeError(err)
    return out

def _gdrive_upload(file_path: str):
    if _env("GDRIVE_ENABLED", "False") != "True":
        return None
    if not _gdrive_available:
        raise RuntimeError("Google Drive libs not installed. pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")

    sa_json_path = _env("GDRIVE_SA_JSON", "")
    folder_id = _extract_drive_folder_id(_env("GDRIVE_FOLDER_ID", ""))

    if not sa_json_path or not os.path.isfile(sa_json_path):
        raise RuntimeError("Service account JSON not found. Upload it in Settings.")

    scopes = ['https://www.googleapis.com/auth/drive.file']
    creds = service_account.Credentials.from_service_account_file(sa_json_path, scopes=scopes)
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)

    metadata = {'name': os.path.basename(file_path)}
    if folder_id:
        metadata['parents'] = [folder_id]

    media = MediaFileUpload(file_path, mimetype='application/octet-stream', resumable=False)
    resp = service.files().create(
        body=metadata,
        media_body=media,
        fields='id,name,parents',
        supportsAllDrives=True
    ).execute()
    return resp

def backup_database():
    """Run a backup; returns (ok: bool, path: str|None, message: str)"""
    dest_dir = _backup_dir()
    uri = _db_uri() or ""
    try:
        uri_low = uri.lower()
        if uri_low.startswith("sqlite"):
            out = _backup_sqlite(uri, dest_dir)
        elif uri_low.startswith("postgresql"):
            out = _backup_postgres(uri, dest_dir)
        elif uri_low.startswith("mysql"):
            out = _backup_mysql(uri, dest_dir)
        else:
            raise RuntimeError(f"Unsupported DB for auto-backup: {uri}")

        keep = _env("DB_BACKUP_KEEP_DAYS", "7")
        _prune_old_backups(dest_dir, keep)

        cloud_note = ""
        try:
            if _env("GDRIVE_ENABLED", "False") == "True":
                _gdrive_upload(out)
                _set_env("DB_BACKUP_LAST_CLOUD", datetime.datetime.now().isoformat(timespec="seconds"))
                _set_env("DB_BACKUP_LAST_CLOUD_STATUS", "SUCCESS")
                cloud_note = " + uploaded to Google Drive"
        except Exception as ce:
            _set_env("DB_BACKUP_LAST_CLOUD", datetime.datetime.now().isoformat(timespec="seconds"))
            _set_env("DB_BACKUP_LAST_CLOUD_STATUS", f"FAIL: {ce}")
            cloud_note = f" (Drive upload failed: {ce})"

        _set_env("DB_BACKUP_LAST", datetime.datetime.now().isoformat(timespec="seconds"))
        _set_env("DB_BACKUP_LAST_STATUS", "SUCCESS")
        return True, out, f"Backup completed to {dest_dir}{cloud_note}"
    except Exception as e:
        _set_env("DB_BACKUP_LAST", datetime.datetime.now().isoformat(timespec="seconds"))
        _set_env("DB_BACKUP_LAST_STATUS", f"FAIL: {e}")
        return False, None, str(e)

def _run_scheduled_backup():
    ok, path, msg = backup_database()
    print(f"[DB BACKUP] ok={ok} path={path} msg={msg}")

def _list_backups():
    folder = _backup_dir()
    items = []
    try:
        for name in os.listdir(folder):
            if not name.lower().endswith('.backup'):
                continue
            p = os.path.join(folder, name)
            if os.path.isfile(p):
                items.append({
                    "name": name,
                    "size": os.path.getsize(p),
                    "mtime": datetime.datetime.fromtimestamp(os.path.getmtime(p)),
                })
        items.sort(key=lambda x: x["mtime"], reverse=True)
    except Exception:
        pass
    return items

def _bytes_fmt(n):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024 or unit == "TB":
            return f"{n:.2f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024.0

def _dir_stats(dir_path: str, backup_files: list, keep_days: int):
    exists = os.path.isdir(dir_path)
    writable = os.access(dir_path, os.W_OK | os.X_OK) if exists else False
    total = used = free = None
    try:
        usage = shutil.disk_usage(dir_path if exists else os.path.abspath(dir_path))
        total, used, free = usage.total, usage.total - usage.free, usage.free
    except Exception:
        pass

    total_size = sum(f["size"] for f in backup_files)
    cutoff = datetime.datetime.now() - datetime.timedelta(days=int(keep_days or 7))
    prune_count = sum(1 for f in backup_files if f["mtime"] < cutoff)
    used_pct = int(used / total * 100) if (total and used is not None) else None
    latest = backup_files[0] if backup_files else None

    return {
        "exists": exists,
        "writable": writable,
        "total": total,
        "used": used,
        "free": free,
        "used_pct": used_pct,
        "file_count": len(backup_files),
        "total_size": total_size,
        "prune_count": prune_count,
        "latest": latest
    }

# ===================== LOG CLEANUP =====================
def _cleanup_old_logs(retention_days: int) -> int:
    """Delete Log rows older than N days. Returns deleted row count."""
    from app.modules.db_logger import Log  # avoid circular import
    cutoff = datetime.datetime.now() - datetime.timedelta(days=int(retention_days or 30))
    try:
        deleted = Log.query.filter(Log.timestamp < cutoff).delete(synchronize_session=False)
        db.session.commit()
        return int(deleted or 0)
    except Exception as e:
        db.session.rollback()
        raise e

def _run_log_cleanup():
    days = int(_env("LOG_RETENTION_DAYS", "30") or 30)
    try:
        deleted = _cleanup_old_logs(days)
        _set_env("LOG_CLEAN_LAST", datetime.datetime.now().isoformat(timespec="seconds"))
        _set_env("LOG_CLEAN_LAST_STATUS", f"SUCCESS: deleted {deleted}")
    except Exception as e:
        _set_env("LOG_CLEAN_LAST", datetime.datetime.now().isoformat(timespec="seconds"))
        _set_env("LOG_CLEAN_LAST_STATUS", f"FAIL: {e}")

# ===================== Settings pages =====================
@settings_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings_page():
    smtp = dotenv_values(_env_path())

    # ----- SAVE SMTP -----
    if request.method == 'POST' and request.form.get('smtp_save'):
        _set_env("MAIL_SERVER", request.form.get("MAIL_SERVER", ""))
        _set_env("MAIL_PORT", request.form.get("MAIL_PORT", "587"))
        _set_env("MAIL_USERNAME", request.form.get("MAIL_USERNAME", ""))
        _set_env("MAIL_PASSWORD", request.form.get("MAIL_PASSWORD", ""))
        _set_env("MAIL_DEFAULT_SENDER", request.form.get("MAIL_DEFAULT_SENDER", ""))
        _set_env("MAIL_USE_TLS", "True" if request.form.get("MAIL_USE_TLS") else "False")
        flash("✅ SMTP settings updated!", "success")
        return redirect(url_for('settings.settings_page'))

    # ----- SAVE BACKUP -----
    if request.method == 'POST' and request.form.get('backup_save'):
        enabled = 'DB_BACKUP_ENABLED' in request.form
        time_str = (request.form.get('DB_BACKUP_TIME', '02:00') or '02:00')[:5]
        keep_days = request.form.get('DB_BACKUP_KEEP_DAYS', '7') or '7'

        raw_dir = (request.form.get('DB_BACKUP_DIR') or '').strip() or _default_backup_dir()
        safe_dir = _sanitize_backup_path(raw_dir, _default_backup_dir())
        try:
            os.makedirs(safe_dir, exist_ok=True)
        except Exception as e:
            flash(f"❌ Backup folder invalid: {safe_dir} ({e})", "danger")
            return redirect(url_for('settings.settings_page', set_db_backup_dir=safe_dir))

        _set_env("DB_BACKUP_ENABLED", "True" if enabled else "False")
        _set_env("DB_BACKUP_TIME", time_str)
        _set_env("DB_BACKUP_KEEP_DAYS", keep_days)
        _set_env("DB_BACKUP_DIR", safe_dir)

        _set_env("SMB_ENABLED", "True" if 'SMB_ENABLED' in request.form else "False")
        _set_env("SMB_SHARE", request.form.get("SMB_SHARE", ""))
        _set_env("SMB_USER", request.form.get("SMB_USER", ""))
        if request.form.get("SMB_PASSWORD", ""):
            _set_env("SMB_PASSWORD", request.form.get("SMB_PASSWORD", ""))

        _set_env("GDRIVE_ENABLED", "True" if 'GDRIVE_ENABLED' in request.form else "False")
        _set_env("GDRIVE_FOLDER_ID", _extract_drive_folder_id(request.form.get("GDRIVE_FOLDER_ID", "")))

        _schedule_backup_job_from_env()
        flash(f"✅ Backup settings saved. Folder: {safe_dir}", "success")
        return redirect(url_for('settings.settings_page'))

    # ----- SAVE BRANDING -----
    if request.method == 'POST' and request.form.get('branding_save'):
        _set_env("BRAND_COMPANY_NAME", request.form.get("BRAND_COMPANY_NAME", "").strip())
        _set_env("BRAND_DOC_TITLE_FORMAT", request.form.get("BRAND_DOC_TITLE_FORMAT", "{company_name} ({doc_type})").strip())
        _set_env("BRAND_DOC_TYPE_UPPER", "True" if request.form.get("BRAND_DOC_TYPE_UPPER") else "False")

        for var_key, field in _ALLOWED_BRAND_KEYS.items():
            file_obj = request.files.get(field)
            clear_flag = request.form.get(f"clear_{field}") == "on"
            if clear_flag:
                _delete_brand_file(var_key)
                continue
            if file_obj and file_obj.filename:
                _delete_brand_file(var_key)
                web_path = _save_brand_file(file_obj, var_key)
                _set_env(var_key, web_path)

        flash("✅ Branding saved.", "success")
        return redirect(url_for('settings.settings_page'))

    # ----- SAVE LOG HOUSEKEEPING -----
    if request.method == 'POST' and request.form.get('log_save'):
        enabled = 'LOG_RETENTION_ENABLED' in request.form
        days = request.form.get('LOG_RETENTION_DAYS', '30') or '30'
        time_str = (request.form.get('LOG_CLEAN_TIME', '03:10') or '03:10')[:5]

        _set_env("LOG_RETENTION_ENABLED", "True" if enabled else "False")
        _set_env("LOG_RETENTION_DAYS", days)
        _set_env("LOG_CLEAN_TIME", time_str)

        _schedule_log_cleanup_job_from_env()
        flash(f"✅ Log housekeeping saved (keep {days} days).", "success")
        return redirect(url_for('settings.settings_page'))

    # ----- VIEW MODEL -----
    uri = _db_uri() or ""
    db_file_resolved = ""
    if uri.lower().startswith("sqlite"):
        try:
            db_file_resolved = _resolve_sqlite_path_from_uri(uri)
        except Exception:
            db_file_resolved = "(could not resolve)"

    chosen_prefill = request.args.get('set_db_backup_dir', '').strip()
    if chosen_prefill:
        dir_norm = _sanitize_browse_path(chosen_prefill)
    else:
        dir_raw = _env("DB_BACKUP_DIR", _default_backup_dir())
        dir_norm = _sanitize_backup_path(dir_raw, _default_backup_dir())

    backup_files = _list_backups()
    keep_days = _env("DB_BACKUP_KEEP_DAYS", "7")
    stats = _dir_stats(dir_norm.replace("\\","/"), backup_files, keep_days)

    backup_cfg = {
        "enabled": _env("DB_BACKUP_ENABLED", "False"),
        "time": _env("DB_BACKUP_TIME", "02:00"),
        "keep": keep_days,
        "dir": dir_norm.replace("\\", "/"),
        "last": _env("DB_BACKUP_LAST", "—"),
        "last_status": _env("DB_BACKUP_LAST_STATUS", "—"),
        "next_run": _next_run_text() or "—",
        "db_path": db_file_resolved,
        "quick_default": _default_backup_dir(),
        "quick_instance": os.path.join(getattr(current_app, "instance_path", current_app.root_path), "backups"),

        "smb_enabled": _env("SMB_ENABLED", "False"),
        "smb_share": _env("SMB_SHARE", ""),
        "smb_user": _env("SMB_USER", ""),

        "gdrive_enabled": _env("GDRIVE_ENABLED", "False"),
        "gdrive_folder": _env("GDRIVE_FOLDER_ID", ""),
        "gdrive_key_path": _env("GDRIVE_SA_JSON", ""),
        "gdrive_libs": "Yes" if _gdrive_available else "No",
        "cloud_last": _env("DB_BACKUP_LAST_CLOUD", "—"),
        "cloud_status": _env("DB_BACKUP_LAST_CLOUD_STATUS", "—"),
    }

    log_cfg = {
        "enabled": _env("LOG_RETENTION_ENABLED", "False"),
        "days": _env("LOG_RETENTION_DAYS", "30"),
        "time": _env("LOG_CLEAN_TIME", "03:10"),
        "last": _env("LOG_CLEAN_LAST", "—"),
        "last_status": _env("LOG_CLEAN_LAST_STATUS", "—"),
        "next_run": _next_log_run_text() or "—",
    }

    brand = {
        "company_name": _env("BRAND_COMPANY_NAME", ""),
        "doc_fmt": _env("BRAND_DOC_TITLE_FORMAT", "{company_name} ({doc_type})"),
        "doc_upper": _env("BRAND_DOC_TYPE_UPPER", "True"),
        "logo_light": _env("BRAND_LOGO_LIGHT", ""),
        "logo_dark": _env("BRAND_LOGO_DARK", ""),
        "logo_icon": _env("BRAND_LOGO_ICON", ""),
        "watermark": _env("BRAND_WATERMARK", ""),
        "stamp": _env("BRAND_STAMP", ""),
    }
    previews = []
    for doc in ["Delivery Note", "Collection Note", "Invoice"]:
        previews.append({
            "name": doc,
            "title": _render_doc_title(brand["company_name"], doc, brand["doc_fmt"], brand["doc_upper"] == "True")
        })

    import_models = ["assets", "spares", "tonermodel", "tonercosting", "customer", "contract"]

    return render_template(
        "settings.html",
        smtp=smtp,
        backup=backup_cfg,
        backup_files=backup_files,
        backup_stats=stats,
        log=log_cfg,
        import_models=import_models,
        brand=brand,
        brand_previews=previews,
        _bytes_fmt=_bytes_fmt,
    )

# ----- Actions (admin only) -----
@settings_bp.route('/settings/backup-now', methods=['POST'])
@admin_required
def backup_now():
    ok, path, msg = backup_database()
    flash(("✅ " if ok else "❌ ") + msg, "success" if ok else "danger")
    return redirect(url_for('settings.settings_page'))

@settings_bp.route('/settings/backup-download/<name>', methods=['GET'])
@admin_required
def backup_download(name):
    folder = _backup_dir()
    safe = secure_filename(name)
    full = os.path.abspath(os.path.join(folder, safe))
    if not full.startswith(os.path.abspath(folder)) or not os.path.isfile(full):
        flash("❌ Invalid backup file.", "danger")
        return redirect(url_for('settings.settings_page'))
    return send_file(full, as_attachment=True)

@settings_bp.post('/settings/backup-delete/<name>')
@admin_required
def backup_delete(name):
    folder = _backup_dir()
    safe = secure_filename(name)
    full = os.path.abspath(os.path.join(folder, safe))
    try:
        if full.startswith(os.path.abspath(folder)) and os.path.isfile(full):
            os.remove(full)
            flash(f"🗑️ Deleted {safe}", "success")
        else:
            flash("❌ Invalid backup file.", "danger")
    except Exception as e:
        flash(f"❌ Delete failed: {e}", "danger")
    return redirect(url_for('settings.settings_page'))

@settings_bp.post('/settings/backup-prune-old')
@admin_required
def backup_prune_now():
    folder = _backup_dir()
    keep_days = int(_env("DB_BACKUP_KEEP_DAYS", "7") or 7)
    before = len([f for f in os.listdir(folder) if f.lower().endswith('.backup')])
    _prune_old_backups(folder, keep_days)
    after = len([f for f in os.listdir(folder) if f.lower().endswith('.backup')])
    removed = before - after if before >= after else 0
    flash(f"🧹 Pruned {removed} old backups (older than {keep_days} days).", "success")
    return redirect(url_for('settings.settings_page'))

@settings_bp.get('/settings/backup-test')
@admin_required
def backup_test_dir():
    path = request.args.get('path', '').strip() or _backup_dir()
    path = _sanitize_browse_path(path)
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, f".__testwrite__{_timestamp()}.tmp")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
        flash(f"✅ Write test passed for: {path}", "success")
    except Exception as e:
        flash(f"❌ Write test failed for {path}: {e}", "danger")
    return redirect(url_for('settings.settings_page', set_db_backup_dir=path))

@settings_bp.route('/settings/upload-gdrive-key', methods=['POST'])
@admin_required
def upload_gdrive_key():
    f = request.files.get('gdrive_key')
    if not f or not f.filename.endswith('.json'):
        flash("❌ Please upload a JSON key file.", "danger")
        return redirect(url_for('settings.settings_page'))
    dest = os.path.join(KEYS_FOLDER, secure_filename(f.filename))
    f.save(dest)
    _set_env("GDRIVE_SA_JSON", os.path.abspath(dest))
    flash("✅ Google Drive service account key uploaded.", "success")
    return redirect(url_for('settings.settings_page'))

@settings_bp.route('/settings/backup-upload-last', methods=['POST'])
@admin_required
def backup_upload_last():
    if _env("GDRIVE_ENABLED", "False") != "True":
        flash("❌ Enable Google Drive in Settings first.", "danger")
        return redirect(url_for('settings.settings_page'))
    files = _list_backups()
    if not files:
        flash("❌ No local backups found to upload.", "danger")
        return redirect(url_for('settings.settings_page'))
    latest = files[0]['name']
    local_path = os.path.join(_backup_dir(), latest)
    try:
        _gdrive_upload(local_path)
        _set_env("DB_BACKUP_LAST_CLOUD", datetime.datetime.now().isoformat(timespec="seconds"))
        _set_env("DB_BACKUP_LAST_CLOUD_STATUS", "SUCCESS")
        flash(f"✅ Uploaded '{latest}' to Google Drive.", "success")
    except Exception as e:
        _set_env("DB_BACKUP_LAST_CLOUD", datetime.datetime.now().isoformat(timespec="seconds"))
        _set_env("DB_BACKUP_LAST_CLOUD_STATUS", f"FAIL: {e}")
        flash(f"❌ Drive upload failed: {e}", "danger")
    return redirect(url_for('settings.settings_page'))

@settings_bp.post('/settings/log-clean-now')
@admin_required
def log_clean_now():
    days = int(_env("LOG_RETENTION_DAYS", "30") or 30)
    try:
        deleted = _cleanup_old_logs(days)
        _set_env("LOG_CLEAN_LAST", datetime.datetime.now().isoformat(timespec="seconds"))
        _set_env("LOG_CLEAN_LAST_STATUS", f"SUCCESS: deleted {deleted}")
        flash(f"🧹 Deleted {deleted} log rows older than {days} days.", "success")
    except Exception as e:
        _set_env("LOG_CLEAN_LAST", datetime.datetime.now().isoformat(timespec="seconds"))
        _set_env("LOG_CLEAN_LAST_STATUS", f"FAIL: {e}")
        flash(f"❌ Log cleanup failed: {e}", "danger")
    return redirect(url_for('settings.settings_page'))

# ===================== Data Import / Templates / SMTP test =====================
@settings_bp.route('/settings/upload/<table>', methods=['POST'])
@admin_required
def upload_excel(table):
    file = request.files.get('file')
    if not file or not file.filename.endswith('.xlsx'):
        flash("Invalid file format. Only .xlsx allowed.", "danger")
        return redirect(url_for('settings.settings_page'))

    path = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
    file.save(path)
    df = pd.read_excel(path)

    try:
        for _, row in df.iterrows():
            row_data = row.dropna().to_dict()
            if table == 'assets': db.session.add(Assets(**row_data))
            elif table == 'spares': db.session.add(spares(**row_data))
            elif table == 'tonermodel': db.session.add(TonerModel(**row_data))
            elif table == 'tonercosting': db.session.add(TonerCosting(**row_data))
            elif table == 'customer': db.session.add(Customer(**row_data))
            elif table == 'contract': db.session.add(Contract(**row_data))
        db.session.commit()
        flash(f"✅ Imported into {table} successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Import failed: {str(e)}", "danger")

    return redirect(url_for('settings.settings_page'))

@settings_bp.route('/settings/download-template/<model>', methods=['GET'])
@admin_required
def download_template(model):
    templates = {
        'assets': ['account_code','customer_name','serial_number','service_location','region','technician_name','technician_email','contract','asset_Description','contract_expiry_date','last_pm_date','pm_freq','install_date','asset_code','asset_status','part_no','department'],
        'spares': ['material_nr','brand','material_desc','currency','price'],
        'tonermodel': ['asset_model','part_number','machine_type','tk_k','k_life','tk_c','c_life','tk_m','m_life','tk_y','y_life'],
        'tonercosting': ['toner_model','toner_type','source','unit_cost'],
        'customer': ['cust_code','cust_name','billing_company'],
        'contract': ['cust_code','cust_name','contract_code','cont_discription','durations','contract_start_date','contract_end_date','mono_commitment','mono_charge','mono_excess_charge','color_commitment','color_charge','color_excess_charge','rental_charges','software_rental','billing_cycle','contract_currency','billing_currency','billing_company','sales_person','email','document_path']
    }
    if model not in templates:
        flash("Invalid template request.", "danger")
        return redirect(url_for('settings.settings_page'))

    df = pd.DataFrame(columns=templates[model])
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, download_name=f"{model}_template.xlsx", as_attachment=True)

@settings_bp.route('/test-email', methods=['POST'])
@admin_required
def test_email():
    test_email_address = request.form.get('test_email')
    if not test_email_address:
        flash("❌ No email provided for test!", "danger")
        return redirect(url_for('settings.settings_page'))
    try:
        msg = Message(
            subject="✅ SMTP Test Email",
            recipients=[test_email_address],
            body="This is a test email from SERVICE PULSE ERP SMTP settings.",
        )
        mail.send(msg)
        flash(f"✅ Test email sent successfully to {test_email_address}.", "success")
    except Exception as e:
        print("SMTP Test Error:", e)
        flash("❌ Failed to send test email. Check SMTP settings and logs.", "danger")
    return redirect(url_for('settings.settings_page'))

# ===================== Simple folder browser (no modal) =====================
@settings_bp.get('/settings/browse')
@admin_required
def browse_dir():
    """
    Simple server-side folder browser page.
    Windows: drives list. Linux: '/'.
    Click into folders; 'Select this folder' returns to Settings with path pre-filled.
    """
    raw = request.args.get('path', '').strip()

    if sys.platform == 'win32' and not raw:
        drives = _list_windows_drives()
        entries = [{"name": d, "path": d.replace("\\", "/")} for d in drives]
        return render_template('browse.html', path='', parent='', entries=entries, is_root=True)

    if not raw and sys.platform != 'win32':
        raw = '/'

    path = _sanitize_browse_path(raw) if raw else ("/" if sys.platform != 'win32' else "")
    if sys.platform == 'win32' and not path:
        drives = _list_windows_drives()
        entries = [{"name": d, "path": d.replace("\\", "/")} for d in drives]
        return render_template('browse.html', path='', parent='', entries=entries, is_root=True)

    entries = []
    parent = ''
    try:
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            if os.path.isdir(full):
                entries.append({"name": name, "path": full.replace("\\", "/")})

        norm = path.replace("\\", "/").rstrip("/")
        parts = norm.split("/")
        if sys.platform == 'win32':
            if (len(parts) == 1 and len(parts[0]) == 2 and parts[0][1] == ':'):
                parent = ''
            else:
                parent = "/".join(parts[:-1]) if len(parts) > 1 else ''
        else:
            parent = "/".join(parts[:-1]) or "/"
    except Exception:
        entries = []
        parent = ''

    return render_template('browse.html', path=path, parent=parent, entries=entries, is_root=False)
