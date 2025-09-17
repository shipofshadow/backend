from storage import get_connection


def fetch_student_info(user_id: int):
    db = get_connection()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM students WHERE user_id = %s", (user_id,))
    application = cursor.fetchone()
    return application