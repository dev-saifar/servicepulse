import smtplib
from email.mime.text import MIMEText
from config import Config  # Import SMTP settings from config.py


def test_smtp():
    """Function to test SMTP configuration."""
    sender_email = "emailprint.ug@groupmfi.com"
    receiver_email = "a.saifar@groupmfi.com"  # Change this to your test email
    subject = "SMTP Test Email"
    body = "This is a test email to confirm SMTP settings."

    # Create the email message
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = receiver_email

    try:
        # Connect to SMTP server
        server = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT)
        server.set_debuglevel(1)
        server.starttls()  # Secure connection
        server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
        print()

        # Send email
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()

        print("✅ Email sent successfully!")
        return True
    except Exception as e:
        print("❌ Error:", e)
        return False
