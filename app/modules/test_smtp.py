# test_smtp.py
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from flask import current_app

def send_email(to_email, subject, text=None, html=None):  # ✅ Fixed: added text and html parameters
    try:
        smtp_server = current_app.config['MAIL_SERVER']
        smtp_port = current_app.config['MAIL_PORT']
        smtp_username = current_app.config['MAIL_USERNAME']
        smtp_password = current_app.config['MAIL_PASSWORD']

        message = MIMEMultipart("alternative")
        message['From'] = smtp_username
        message['To'] = to_email
        message['Subject'] = subject

        if text:
            message.attach(MIMEText(text, 'plain', 'utf-8'))
        if html:
            message.attach(MIMEText(html, 'html', 'utf-8'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(smtp_username, to_email, message.as_bytes())
        server.quit()

        print(f"✅ Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send email to {to_email}. Error: {e}")
