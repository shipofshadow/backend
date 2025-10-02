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

