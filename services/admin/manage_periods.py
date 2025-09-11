from storage import get_connection

def get_active_period():
    db = get_connection()
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                ay.id AS academic_year_id,
                ay.year_start,
                ay.year_end,
                s.id AS semester_id,
                s.name AS semester_name
            FROM semesters s
            INNER JOIN academic_years ay ON s.academic_year_id = ay.id
            WHERE s.is_active = 1
            LIMIT 1
        """)
        return cursor.fetchone()


def add_academic_year(year_start):
    year_end = year_start + 1
    db = get_connection()
    with db.cursor() as cursor:
        cursor.execute("""
            INSERT INTO academic_years (year_start, year_end)
            VALUES (%s, %s)
        """, (year_start, year_end))
        db.commit()


def add_semester(academic_year_id, name):
    db = get_connection()
    with db.cursor() as cursor:
        cursor.execute("""
            INSERT INTO semesters (academic_year_id, name, is_active)
            VALUES (%s, %s, 0)
        """, (academic_year_id, name))
        db.commit()


def activate_semester(semester_id):
    db = get_connection()
    with db.cursor() as cursor:
        # Deactivate all semesters first
        cursor.execute("UPDATE semesters SET is_active = 0")
        # Activate the selected semester
        cursor.execute("UPDATE semesters SET is_active = 1 WHERE id = %s", (semester_id,))
        db.commit()


def get_all_periods():
    db = get_connection()
    with db.cursor() as cursor:
        # Get all academic years
        cursor.execute("""
            SELECT id, year_start, year_end
            FROM academic_years
            ORDER BY year_start DESC
        """)
        academic_years = cursor.fetchall()

        # Attach semesters to each year
        for year in academic_years:
            cursor.execute("""
                SELECT id, name, is_active
                FROM semesters
                WHERE academic_year_id = %s
                ORDER BY id ASC
            """, (year['id'],))
            semesters = cursor.fetchall()
            year['semesters'] = semesters

        return academic_years
