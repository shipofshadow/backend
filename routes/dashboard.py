from flask import jsonify, request, Blueprint
from flask_jwt_extended import jwt_required
from storage import get_connection
from utils.decorator import admin_or_faculty_required

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')

@dashboard_bp.route("/active-applicants", methods=["GET"])
@jwt_required()
@admin_or_faculty_required
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

@dashboard_bp.route("/public-stats", methods=["GET"])
def public_stats():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                COUNT(*) AS total_applications,
                SUM(CASE WHEN applications.status = 'approved' THEN 1 ELSE 0 END) AS approved_students
            FROM applications
            LEFT JOIN semesters ON semesters.id = applications.semester_id
            WHERE semesters.is_active = 1 AND applications.deleted_at IS NULL
        """)
        result = cursor.fetchone() or {}
        return jsonify({
            'success': True,
            'total_applications': result.get('total_applications') or 0,
            'approved_students': int(result.get('approved_students') or 0),
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'total_applications': 0,
            'approved_students': 0,
            'error': str(e)
        }), 200
    finally:
        cursor.close()
        conn.close()

@dashboard_bp.route("/approved-applicants", methods=["GET"])
@jwt_required()
@admin_or_faculty_required
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
@jwt_required()
@admin_or_faculty_required
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
@jwt_required()
@admin_or_faculty_required
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
@jwt_required()
@admin_or_faculty_required
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
@jwt_required()
@admin_or_faculty_required
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
@jwt_required()
@admin_or_faculty_required
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


# ─────────────────────────────────────────────────────────────────
# Activity Logs – recent application events across the system
# ─────────────────────────────────────────────────────────────────
@dashboard_bp.route('/activity-logs', methods=['GET'])
@jwt_required()
@admin_or_faculty_required
def activity_logs():
    """
    Returns a paginated list of recent application activity events
    (created, status changes) ordered newest-first.
    Query params:
      - limit  (int, default 50)
      - offset (int, default 0)
    """
    limit  = request.args.get('limit',  default=50,  type=int)
    offset = request.args.get('offset', default=0,   type=int)
    limit  = min(limit, 200)  # cap at 200 rows

    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            a.id            AS application_id,
            a.status,
            a.created_at,
            a.updated_at,
            a.remarks,
            CONCAT(sd.first_name, ' ', sd.last_name) AS student_name,
            s.student_id,
            c.name          AS course_name,
            camp.name       AS campus_name,
            sem.name        AS semester_name,
            CONCAT(ay.year_start, '-', ay.year_end)  AS academic_year
        FROM applications a
        JOIN students      s    ON s.user_id        = a.student_id
        JOIN student_details sd ON sd.student_id    = s.user_id
        LEFT JOIN education_info ei
            ON ei.student_id  = a.student_id
           AND ei.semester_id = a.semester_id
        LEFT JOIN courses   c    ON c.course_id      = ei.course_id
        LEFT JOIN campuses  camp ON camp.campus_id   = ei.campus_id
        LEFT JOIN semesters sem  ON sem.id           = a.semester_id
        LEFT JOIN academic_years ay ON ay.id         = sem.academic_year_id
        WHERE a.deleted_at IS NULL
        ORDER BY a.updated_at DESC
        LIMIT %s OFFSET %s
    """, (limit, offset))

    rows = cursor.fetchall()

    # Total count for pagination
    cursor.execute("SELECT COUNT(*) AS total FROM applications WHERE deleted_at IS NULL")
    total = cursor.fetchone()['total']

    cursor.close()
    conn.close()

    return jsonify({
        'logs':   rows,
        'total':  total,
        'limit':  limit,
        'offset': offset,
    }), 200


# ─────────────────────────────────────────────────────────────────
# Metrics – aggregate scholarship statistics
# ─────────────────────────────────────────────────────────────────
@dashboard_bp.route('/metrics', methods=['GET'])
@jwt_required()
@admin_or_faculty_required
def metrics():
    """
    Returns aggregate metrics:
      - overall_total       : total applications (all time)
      - approved_total      : total approved (all time)
      - pending_total       : total pending
      - denied_total        : total denied
      - approval_rate_pct   : approved / total * 100
      - per_semester        : breakdown per academic year + semester
      - per_campus          : total applicants per campus
      - top_courses         : top 10 courses by applicant count
    """
    conn   = get_connection()
    cursor = conn.cursor()

    # ── Overall counts ──────────────────────────────────────────
    cursor.execute("""
        SELECT
            COUNT(*)                                                          AS overall_total,
            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END)             AS approved_total,
            SUM(CASE WHEN status = 'pending'  THEN 1 ELSE 0 END)             AS pending_total,
            SUM(CASE WHEN status = 'denied'   THEN 1 ELSE 0 END)             AS denied_total,
            ROUND(
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0) * 100, 1
            )                                                                 AS approval_rate_pct
        FROM applications
        WHERE deleted_at IS NULL
    """)
    overall = cursor.fetchone()

    # ── Per semester ────────────────────────────────────────────
    cursor.execute("""
        SELECT
            CONCAT(ay.year_start, '-', ay.year_end) AS academic_year,
            sem.name                                 AS semester,
            COUNT(*)                                 AS total,
            SUM(CASE WHEN a.status = 'approved' THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN a.status = 'pending'  THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN a.status = 'denied'   THEN 1 ELSE 0 END) AS denied
        FROM applications a
        JOIN semesters     sem ON sem.id   = a.semester_id
        JOIN academic_years ay ON ay.id    = sem.academic_year_id
        WHERE a.deleted_at IS NULL
        GROUP BY ay.year_start, ay.year_end, sem.name
        ORDER BY ay.year_start DESC, sem.name
    """)
    per_semester = cursor.fetchall()

    # ── Per campus ──────────────────────────────────────────────
    cursor.execute("""
        SELECT
            camp.name AS campus,
            COUNT(a.id) AS total,
            SUM(CASE WHEN a.status = 'approved' THEN 1 ELSE 0 END) AS approved
        FROM applications a
        JOIN students s ON s.user_id = a.student_id
        LEFT JOIN education_info ei
            ON ei.student_id  = a.student_id
           AND ei.semester_id = a.semester_id
        LEFT JOIN campuses camp ON camp.campus_id = ei.campus_id
        WHERE a.deleted_at IS NULL
        GROUP BY camp.campus_id, camp.name
        ORDER BY total DESC
    """)
    per_campus = cursor.fetchall()

    # ── Top courses ─────────────────────────────────────────────
    cursor.execute("""
        SELECT
            c.name  AS course,
            d.name  AS department,
            camp.name AS campus,
            COUNT(a.id) AS total
        FROM applications a
        JOIN students s ON s.user_id = a.student_id
        LEFT JOIN education_info ei
            ON ei.student_id  = a.student_id
           AND ei.semester_id = a.semester_id
        LEFT JOIN courses     c    ON c.course_id      = ei.course_id
        LEFT JOIN departments d    ON d.department_id  = c.department_id
        LEFT JOIN campuses    camp ON camp.campus_id   = d.campus_id
        WHERE a.deleted_at IS NULL
        GROUP BY c.course_id, c.name, d.name, camp.name
        ORDER BY total DESC
        LIMIT 10
    """)
    top_courses = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({
        'overall':      overall,
        'per_semester': per_semester,
        'per_campus':   per_campus,
        'top_courses':  top_courses,
    }), 200
