from db import get_connection

def get_academic_year():
    connection = get_connection()
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                ay.id AS academic_year_id,
                ay.year_start,
                ay.year_end,
                s.id AS semester_id,
                s.name AS semester_name
            FROM academic_years ay
            LEFT JOIN semesters s ON s.academic_year_id = ay.id AND s.is_active = 1
            WHERE ay.is_active = 1
            LIMIT 1
        """)
        return cursor.fetchone()
