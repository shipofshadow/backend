from db import get_connection

def get_academic_year():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT id FROM academic_years WHERE is_active = 1 LIMIT 1")
    row = cursor.fetchone()
    return row['id'] if row else None
