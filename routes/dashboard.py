from flask import jsonify, request, Blueprint
from storage import get_connection

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')

@dashboard_bp.route("/active-applicants", methods=["GET"])
def active_applicants():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM applications
        LEFT JOIN semesters ON semesters.id = applications.semester_id
        WHERE semesters.is_active = 1 AND applications.deleted_at IS NULL
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
            WHERE applications.status = 'approved' AND semesters.is_active = 1 AND applications.deleted_at IS NULL;
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
            WHERE applications.status = 'pending' AND semesters.is_active = 1 AND applications.deleted_at IS NULL;
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
            WHERE applications.status = 'denied' AND semesters.is_active = 1 AND applications.deleted_at IS NULL;
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
        SELECT COUNT(*) AS total FROM students WHERE deleted_at IS NULL 
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
                INNER JOIN education_info 
                            ON education_info.student_id = students.user_id
                            AND education_info.semester_id = applications.semester_id
                 JOIN courses ON courses.course_id = education_info.course_id 
                 JOIN departments ON departments.department_id = courses.department_id 
                 JOIN campuses ON campuses.campus_id = departments.campus_id 
                 LEFT JOIN semesters ON semesters.id = applications.semester_id
        WHERE  applications.deleted_at IS NULL AND semesters.is_active = 1 
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
    academic_year_id = request.args.get('academic_year_id', type=int)
    semester_id = request.args.get('semester_id', type=int)
    campus_id = request.args.get('campus_id', type=int)
    department_id = request.args.get('department_id', type=int)
    course_id = request.args.get('course_id', type=int)

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            CONCAT(ay.year_start, '-', ay.year_end) AS academic_year,
            s.name AS semester,
            SUM(CASE WHEN a.status = 'pending' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN a.status = 'approved' THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN a.status = 'denied' THEN 1 ELSE 0 END) AS denied,
            COUNT(*) AS total
        FROM applications a
        JOIN semesters s ON s.id = a.semester_id
        JOIN academic_years ay ON ay.id = s.academic_year_id
        INNER JOIN education_info 
                    ON education_info.student_id = a.student_id
                    AND education_info.semester_id = s.id      
        WHERE a.deleted_at IS NULL
    """

    params = []

    if academic_year_id:
        query += " AND ay.id = %s"
        params.append(academic_year_id)

    if semester_id:
        query += " AND s.id = %s"
        params.append(semester_id)

    if campus_id:
        query += " AND education_info.campus_id = %s"
        params.append(campus_id)

    if department_id:
        query += " AND education_info.department_id = %s"
        params.append(department_id)

    if course_id:
        query += " AND education_info.course_id = %s"
        params.append(course_id)

    query += """
        GROUP BY ay.id, s.id
        ORDER BY ay.year_start ASC, s.name ASC;
    """

    cursor.execute(query, tuple(params))
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(result), 200
