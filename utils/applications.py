# utils/applications.py
from typing import Optional
from storage import get_connection
import secrets
import string

def get_application(application_id: int) -> Optional[dict]:
    """
    Check if an application exists and is not deleted.
    Returns the application row as a dict if found, otherwise None.
    """
    db = get_connection()
    cursor = db.cursor()
    try:
        cursor.execute(
            "SELECT id, student_id as user_id, status FROM applications WHERE id = %s AND deleted_at IS NULL",
            (application_id,)
        )
        application = cursor.fetchone()
        return application
    finally:
        cursor.close()
        db.close()

def email_exists(email: str) -> bool:
    db = get_connection()
    cursor = db.cursor()
    try:
        cursor.execute(
            "SELECT user_id FROM students WHERE email = %s", (email,)
        )
        application = cursor.fetchone()
        return application
    finally:
        cursor.close()
        db.close()


def generate_reference_number():
    alphabet = string.ascii_uppercase + string.digits
    ref = ''.join(secrets.choice(alphabet) for _ in range(12))
    return f"REF-{ref}"