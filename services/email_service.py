from flask import render_template
from extensions import mail
from flask_mail import Message

def send_activation_email(to_email, context):
    msg = Message(
        subject="Activate Your iScholar Account",
        recipients=[to_email]
    )
    msg.html = render_template("activation_email.html", **context)

    mail.send(msg)
    return True

def send_password_reset_email(to_email, context):
    msg = Message(
        subject="Password Reset Request",
        recipients=[to_email]
    )
    msg.html = render_template("password_reset_email.html", **context)
    mail.send(msg)
    return True

def send_application_reminder_email(to_email, context):
    """Send scholarship application reminder email"""
    msg = Message(
        subject="📚 Apply for Scholarships - iScholar",
        recipients=[to_email]
    )
    msg.html = render_template("application_reminder_email.html", **context)
    mail.send(msg)
    return True
