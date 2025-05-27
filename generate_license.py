from app.modules.license_utils import encrypt_license

def generate_license():
    client_name = input("Client Name: ")
    domain = input("Domain (e.g., servpulse): ")
    hardware_id = input("Hardware ID (from client): ")
    license_type = input("Type (yearly/lifetime): ").strip()
    expiry = ""
    if license_type != 'lifetime':
        expiry = input("Expiry date (YYYY-MM-DD): ")

    data = {
        "client_name": client_name,
        "domain": domain,
        "hardware_id": hardware_id,
        "license_type": license_type,
        "expiry_date": expiry
    }

    print("\nEncrypted License Key:\n")
    print(encrypt_license(data))

if __name__ == "__main__":
    generate_license()
