import os
import json
import uuid
import socket
from datetime import datetime
from cryptography.fernet import Fernet

# ========= CONFIG ===============
SECRET_KEY = b'iu-E4F56GRDaK2DU5wh_lU0aXuVhEXtn2FS9H_H_Dqs='  # ← Replace this after step 3
LICENSE_FILE = 'license.lic'  # Stored in root folder (C:\servicepulse)
# ================================

def get_hardware_id():
    return hex(uuid.getnode())

def get_domain():
    return socket.gethostname()

def encrypt_license(data: dict) -> str:
    fernet = Fernet(SECRET_KEY)
    json_data = json.dumps(data).encode()
    return fernet.encrypt(json_data).decode()

def decrypt_license(encrypted_data: str) -> dict:
    fernet = Fernet(SECRET_KEY)
    decrypted = fernet.decrypt(encrypted_data.encode())
    return json.loads(decrypted.decode())

def save_license_file(license_text: str):
    with open(LICENSE_FILE, 'w') as f:
        f.write(license_text)

def load_license_file() -> str:
    if os.path.exists(LICENSE_FILE):
        with open(LICENSE_FILE, 'r') as f:
            return f.read()
    return None

def is_license_valid():
    try:
        raw = load_license_file()
        if not raw:
            return False, "License file not found"

        lic = decrypt_license(raw)
        if lic['hardware_id'] != get_hardware_id():
            return False, "Hardware mismatch"
        if lic['domain'] != get_domain():
            return False, "Domain mismatch"

        if lic['license_type'] != 'lifetime':
            expiry = datetime.strptime(lic['expiry_date'], "%Y-%m-%d")
            if expiry < datetime.today():
                return False, "License expired"

        return True, lic
    except Exception as e:
        return False, f"Invalid license: {e}"
from datetime import timedelta

def create_trial_license(client_name, address, email):
    data = {
        "client_name": client_name,
        "address": address,
        "email": email,
        "domain": get_domain(),
        "hardware_id": get_hardware_id(),
        "license_type": "trial",
        "expiry_date": (datetime.today() + timedelta(days=90)).strftime("%Y-%m-%d")
    }

    encrypted = encrypt_license(data)
    save_license_file(encrypted)
    return data
