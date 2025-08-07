from flask import jsonify, request, Blueprint
from db import get_connection
from services.admin.manage_periods import get_active_period

meta_bp = Blueprint('meta', __name__, url_prefix='/api')

@meta_bp.route('/semesters', methods=['GET'])
def get_semesters():
    semester_id = request.args.get('semester_id', type=int)
    academic_year_id = request.args.get('academic_year_id', type=int)

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            s.id AS semester_id,
            s.name AS semester_name,
            s.is_active,
            ay.id AS academic_year_id,
            ay.year_start,
            ay.year_end
        FROM semesters s
        JOIN academic_years ay ON ay.id = s.academic_year_id
        WHERE s.deleted_at IS NULL
    """

    params = []
    if semester_id:
        query += " AND s.id = %s"
        params.append(semester_id)

    if academic_year_id:
        query += " AND ay.id = %s"
        params.append(academic_year_id)

    query += " ORDER BY ay.year_start ASC, s.name ASC"

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    semesters = []
    for row in rows:
        semesters.append({
            "id": row["semester_id"],
            "name": row["semester_name"],
            "is_active": row["is_active"],
            "academic_year": {
                "id": row["academic_year_id"],
                "year_start": row["year_start"],
                "year_end": row["year_end"]
            }
        })

    cursor.close()
    conn.close()

    if semester_id and len(semesters) == 1:
        return jsonify(semesters[0]), 200

    return jsonify(semesters), 200

@meta_bp.route('/active-academic-term', methods=['GET'])
def current_academic_year():
    data = get_active_period()
    if data:
        formatted = f"AY {data['year_start']}-{data['year_end']} - {data['semester_name']}"
        return jsonify({
            "academic_year": f"{data['year_start']}-{data['year_end']}",
            "semester": data['semester_name'],
            "academic_year_id": data['academic_year_id'],
            "semester_id": data['semester_id'],
            "formatted": formatted
        })
    else:
        return jsonify({"error": "No active academic year or semester found"}), 404


@meta_bp.route('/campuses', methods=['GET'])
def get_campuses():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT campus_id, name FROM campuses")
    rows = cursor.fetchall()
    data = [{'id': row['campus_id'], 'name': row['name']} for row in rows]
    cursor.close()
    conn.close()
    return jsonify(data), 200


@meta_bp.route('/departments', methods=['GET'])
def get_departments():
    campus_id = request.args.get('campus_id')
    conn = get_connection()
    cursor = conn.cursor()
    if campus_id:
        cursor.execute("SELECT department_id, name, campus_id FROM departments WHERE campus_id = %s", (campus_id,))
    else:
        cursor.execute("SELECT department_id, name, campus_id FROM departments")
    rows = cursor.fetchall()
    data = [{'id': row['department_id'], 'name': row['name'], 'campus_id': row['campus_id']} for row in rows]
    cursor.close()
    conn.close()
    return jsonify(data), 200


@meta_bp.route('/courses', methods=['GET'])
def get_courses():
    department_id = request.args.get('department_id')
    conn = get_connection()
    cursor = conn.cursor()
    if department_id:
        cursor.execute("SELECT course_id, name, major, department_id FROM courses WHERE department_id = %s",
                       (department_id,))
    else:
        cursor.execute("SELECT course_id, name, major, department_id FROM courses")
    rows = cursor.fetchall()
    data = [{'id': row['course_id'], 'name': row['name'], 'major': row['major'], 'department_id': row['department_id']}
            for row in rows]
    cursor.close()
    conn.close()
    return jsonify(data), 200
