from flask import jsonify, request, Blueprint
from db import get_connection

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')

@dashboard_bp.route("/active-applicants", methods=["GET"])
def active_applicants():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM applications
        LEFT JOIN semesters ON semesters.id = applications.semester_id
        WHERE semesters.is_active = 1
    """)

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    return jsonify({
        'active_applicants': result['total'],
    }), 200

@dashboard_bp.route("/approved-applicants", methods=["GET"])
def approved_applicants():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
       """
            SELECT COUNT(*) AS total 
            FROM applications 
            LEFT JOIN semesters ON semesters.id = applications.semester_id 
            WHERE applications.status = 'approved' AND semesters.is_active = 1;
       """)

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    return jsonify({
        'approved_applicants': result['total'],
    }), 200

@dashboard_bp.route("/pending-applicants", methods=["GET"])
def pending_applicants():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
       """
            SELECT COUNT(*) AS total 
            FROM applications 
            LEFT JOIN semesters ON semesters.id = applications.semester_id 
            WHERE applications.status = 'pending' AND semesters.is_active = 1;
       """)

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    return jsonify({
        'pending_applicants': result['total'],
    }), 200

@dashboard_bp.route("/rejected-applicants", methods=["GET"])
def rejected_applicants():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
       """
            SELECT COUNT(*) AS total 
            FROM applications 
            LEFT JOIN semesters ON semesters.id = applications.semester_id 
            WHERE applications.status = 'denied' AND semesters.is_active = 1;
       """)

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    return jsonify({
        'rejected_applicants': result['total'],
    }), 200

@dashboard_bp.route("/registered-students", methods=["GET"])
def registered_students():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) AS total FROM students
        """
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    return jsonify({
        'registered_students': result['total'],
    })

@dashboard_bp.route("/applicants-breakdown", methods=["GET"])
def applicants_per_course():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT campuses.name AS campus, departments.name AS department, courses.name AS course, COUNT(applications.id) AS total_applicants 
        FROM applications 
                 JOIN students ON students.user_id = applications.student_id 
                 JOIN education_info ON education_info.student_id = students.user_id 
                 JOIN courses ON courses.course_id = education_info.course_id 
                 JOIN departments ON departments.department_id = courses.department_id 
                 JOIN campuses ON campuses.campus_id = departments.campus_id 
                 LEFT JOIN semesters ON semesters.id = applications.semester_id
        WHERE  semesters.is_active = 1
        GROUP BY campuses.name, departments.name, courses.name 
        ORDER BY campuses.name, departments.name, courses.name;
    """
        )
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(result), 200

@dashboard_bp.route('/applications-trend', methods=['GET'])
def applications_trend():
    year = request.args.get('year', default=2025, type=int)

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            MONTHNAME(applications.submitted_at) AS month,
            COUNT(*) AS total_applications
        FROM applications
        JOIN semesters ON semesters.id = applications.semester_id
        WHERE semesters.is_active = 1 AND YEAR(applications.submitted_at) = %s
        GROUP BY MONTH(applications.submitted_at)
        ORDER BY MONTH(applications.submitted_at);
    """
    cursor.execute(query, (year,))
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(result), 200