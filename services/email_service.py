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

def send_eligibility_notification_email(to_email, context):
    """
    Send eligibility notification email to a student.
    
    Args:
        to_email: Student's email address
        context: Dictionary containing:
            - student_name: Student's name
            - student_id: Student ID
            - eligibility_score: Eligibility score (0-100)
            - classification: Classification (Eligible, Conditionally Eligible, etc.)
            - recommended_scholarships: List of recommended scholarships
    """
    msg = Message(
        subject="🎓 iScholar - You're Eligible for Scholarships!",
        recipients=[to_email]
    )
    msg.html = render_template("eligibility_notification_email.html", **context)
    mail.send(msg)
    return True
