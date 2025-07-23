from db import get_connection

# ---------- Campus ----------
def get_campuses():
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT campus_id, name FROM campuses")
        return [{'id': row['campus_id'], 'name': row['name']} for row in cursor.fetchall()]

def add_campus(name):
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("INSERT INTO campuses (name) VALUES (%s)", (name,))
        conn.commit()

def update_campus(campus_id, name):
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("UPDATE campuses SET name = %s WHERE campus_id = %s", (name, campus_id))
        conn.commit()

def delete_campus(campus_id):
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM campuses WHERE campus_id = %s", (campus_id,))
        conn.commit()

# ---------- Department ----------
def get_departments(campus_id=None):
    conn = get_connection()
    with conn.cursor() as cursor:
        if campus_id:
            cursor.execute("SELECT department_id, name, campus_id FROM departments WHERE campus_id = %s", (campus_id,))
        else:
            cursor.execute("SELECT department_id, name, campus_id FROM departments")
        return [{'id': row['department_id'], 'name': row['name'], 'campus_id': row['campus_id']} for row in cursor.fetchall()]

def add_department(name, campus_id):
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("INSERT INTO departments (name, campus_id) VALUES (%s, %s)", (name, campus_id))
        conn.commit()

def update_department(department_id, name, campus_id):
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("UPDATE departments SET name = %s, campus_id = %s WHERE department_id = %s", (name, campus_id, department_id))
        conn.commit()

def delete_department(department_id):
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM departments WHERE department_id = %s", (department_id,))
        conn.commit()

# ---------- Course ----------
def get_courses(department_id=None):
    conn = get_connection()
    with conn.cursor() as cursor:
        if department_id:
            cursor.execute("""
                SELECT c.course_id, c.name AS course_name, c.major,
                       d.department_id, d.name AS department_name, d.campus_id
                FROM courses c
                JOIN departments d ON c.department_id = d.department_id
                WHERE c.department_id = %s
            """, (department_id,))
        else:
            cursor.execute("""
                SELECT c.course_id, c.name AS course_name, c.major,
                       d.department_id, d.name AS department_name, d.campus_id
                FROM courses c
                JOIN departments d ON c.department_id = d.department_id
            """)

        return [{
            'id': row['course_id'],
            'name': row['course_name'],
            'major': row['major'],
            'department_id': row['department_id'],
            'department_name': row['department_name'],
            'campus_id': row['campus_id']
        } for row in cursor.fetchall()]

def add_course(name, major, department_id):
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("INSERT INTO courses (name, major, department_id) VALUES (%s, %s, %s)", (name, major, department_id))
        conn.commit()

def update_course(course_id, name, major, department_id):
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("UPDATE courses SET name = %s, major = %s, department_id = %s WHERE course_id = %s", (name, major, department_id, course_id))
        conn.commit()

def delete_course(course_id):
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM courses WHERE course_id = %s", (course_id,))
        conn.commit()

