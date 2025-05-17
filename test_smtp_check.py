import smtplib
from email.message import EmailMessage

# SMTP Configurations
SMTP_SERVER = 'secure.emailsrvr.com'
SMTP_PORT = 587
SMTP_USERNAME = "emailprint.ug@groupmfi.com"
SMTP_PASSWORD = "mfiug$987@"

# Test Email Details
sender_email = "emailprint.ug@groupmfi.com"
receiver_email = "a.saifar@groupmfi.com"  # 👉 Replace with your own to check
subject = "SMTP Test Email"
body = "This is a test email to verify SMTP settings."

# Prepare Email
msg = EmailMessage()
msg['From'] = sender_email
msg['To'] = receiver_email
msg['Subject'] = subject
msg.set_content(body)

try:
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
    print("✅ SMTP Test Email sent successfully!")
except Exception as e:
    print(f"❌ SMTP Test Email failed. Error: {e}")
