import os
import json
import uuid
import socket
import hashlib
from datetime import datetime, timedelta, date
from cryptography.fernet import Fernet
from functools import lru_cache

# ========= CONFIG ===============
SECRET_KEY = b'iu-E4F56GRDaK2DU5wh_lU0aXuVhEXtn2FS9H_H_Dqs='  # keep in sync
# ================================

def _app_home() -> str:
    """
    Stable base dir for license storage.
    SERVICEPULSE_HOME can override (e.g., C:\servicepulse).
    """
    env_home = os.getenv("SERVICEPULSE_HOME")
    if env_home:
        return os.path.abspath(env_home)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def _license_file_path() -> str:
    """
    Absolute path for license file.
    SERVICEPULSE_LICENSE_FILE can override explicit file.
    """
    override = os.getenv("SERVICEPULSE_LICENSE_FILE")
    if override:
        return os.path.abspath(override)
    return os.path.join(_app_home(), "license.lic")

def get_hardware_id():
    return hex(uuid.getnode())

def get_domain():
    return socket.gethostname()

def _trial_marker_path() -> str:
    """
    A per-machine+domain 'trial used' marker so the trial button works once only.
    """
    fingerprint = f"{get_hardware_id()}|{get_domain()}"
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    return os.path.join(_app_home(), f".trial_{digest}.used")

def trial_already_used() -> bool:
    return os.path.exists(_trial_marker_path())

def _mark_trial_used():
    p = _trial_marker_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    # atomic create
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(datetime.utcnow().isoformat())
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)
    # best-effort make hidden on Windows (optional)
    try:
        if os.name == "nt":
            import ctypes
            FILE_ATTRIBUTE_HIDDEN = 0x02
            ctypes.windll.kernel32.SetFileAttributesW(p, FILE_ATTRIBUTE_HIDDEN)
    except Exception:
        pass

def encrypt_license(data: dict) -> str:
    fernet = Fernet(SECRET_KEY)
    json_data = json.dumps(data).encode()
    return fernet.encrypt(json_data).decode()

def decrypt_license(encrypted_data: str) -> dict:
    fernet = Fernet(SECRET_KEY)
    decrypted = fernet.decrypt(encrypted_data.encode())
    return json.loads(decrypted.decode())

def save_license_file(license_text: str):
    """
    Atomic write + cache bust so newly-activated licenses are visible immediately.
    """
    path = _license_file_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write((license_text or "").strip())
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    _read_and_validate.cache_clear()

def load_license_file() -> str | None:
    path = _license_file_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None

@lru_cache(maxsize=1)
def _read_and_validate():
    raw = load_license_file()
    if not raw:
        return False, "License file not found"

    lic = decrypt_license(raw)

    # bind to this machine + hostname
    if lic.get('hardware_id') != get_hardware_id():
        return False, "Hardware mismatch"
    if lic.get('domain') != get_domain():
        return False, "Domain mismatch"

    # expiry: treat expiry date as inclusive (valid through that day)
    if lic.get('license_type') != 'lifetime':
        try:
            exp = datetime.strptime(lic['expiry_date'], "%Y-%m-%d").date()
        except Exception:
            return False, "Invalid expiry format"
        if exp < date.today():
            return False, "License expired"

    return True, lic

def is_license_valid(force_reload: bool = False):
    if force_reload:
        _read_and_validate.cache_clear()
    try:
        return _read_and_validate()
    except Exception as e:
        return False, f"Invalid license: {e}"

def create_trial_license(client_name, address, email):
    """
    Create a 90-day trial exactly once per machine+domain.
    If trial already used, raise a clear error.
    """
    if trial_already_used():
        raise RuntimeError("Trial already activated on this machine. Please contact support for a full license.")

    data = {
        "client_name": client_name,
        "address": address,
        "email": email,
        "domain": get_domain(),
        "hardware_id": get_hardware_id(),
        "license_type": "trial",
        "expiry_date": (date.today() + timedelta(days=90)).strftime("%Y-%m-%d"),
    }
    encrypted = encrypt_license(data)
    save_license_file(encrypted)   # atomic + cache clear
    _mark_trial_used()             # burn the trial
    return data
