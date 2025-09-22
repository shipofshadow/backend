import json

from flask import Blueprint, jsonify, send_from_directory, request
from flask_jwt_extended import jwt_required, get_jwt_identity

import storage
from config import UPLOAD_FOLDER
from routes.scholarship_summary import get_scholarship_summary
from storage import get_connection
from services.application_service import base_applicant_query
from utils.response import error

profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")

@profile_bp.route("/scholarship/summary", methods=["GET"])
@jwt_required()
def scholarship_summary():
    student_id = get_jwt_identity()
    return get_scholarship_summary(student_id, active_only=True)


@profile_bp.route("/applications", methods=["GET"])
@jwt_required()
def get_applications():
    user_id = get_jwt_identity()

    connection = get_connection()
    cursor = connection.cursor()

    # SQL: join with semesters and filter active semester
    query = f"""
        {base_applicant_query()}
        WHERE applications.student_id = %s
          AND semesters.is_active = 1
    """

    cursor.execute(query, [user_id])
    applications = cursor.fetchall()
    cursor.close()
    return jsonify(applications), 200


@profile_bp.route('/me', methods=['GET'])
@jwt_required()
def get_user_data():
    user_id = get_jwt_identity()

    connection = get_connection()
    cursor = connection.cursor()

    # Get user base info
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        return jsonify({"message": "User not found"}), 404

    if user['role'] == 'student':
        cursor.execute("""
           SELECT * FROM users 
                             INNER JOIN students ON students.user_id = users.id 
                             LEFT JOIN education_info ON education_info.student_id = students.user_id 
                             LEFT JOIN family_background ON family_background.student_id = students.user_id 
                             LEFT JOIN addresses ON addresses.student_id = students.user_id
            WHERE students.user_id = %s
        """, (user_id,))
        student_profile = cursor.fetchone()
        if student_profile and "password" in student_profile:
            student_profile.pop("password")
        user['profile'] = student_profile

    elif user['role'] == 'admin':
        cursor.execute("""
                   SELECT * FROM users 
                             INNER JOIN user_details ON user_details.user_id = users.id 
            WHERE users.id = %s
        """, (user_id,))
        admin_profile = cursor.fetchone()
        if admin_profile and "password" in admin_profile:
            admin_profile.pop("password")
        user['profile'] = admin_profile

    cursor.close()
    connection.close()

    return jsonify(user), 200

@profile_bp.route('/avatar/<path:filename>', methods=['GET'])
def get_avatar(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@profile_bp.route("/complete", methods=["POST"])
@jwt_required()
def complete_profile():
    user_id = str(get_jwt_identity())
    data = request.get_json()

    student_id = data.get("student_id")
    first_name = data.get("first_name")
    last_name = data.get("last_name")
    middle_name = data.get("middle_name")
    name_extension = data.get("name_extension")
    gender = data.get("gender")
    birth_date = data.get("birth_date")
    citizenship = data.get("citizenship")
    civil_status = data.get("civil_status")
    contact_number = data.get("contact_number")
    email = data.get("email")
    avatar = data.get("avatar")

    if not student_id or not first_name or not last_name or not email:
        return jsonify({"error": "student_id, first_name, last_name, and email are required"}), 400

    connection = get_connection()
    cursor = connection.cursor()

    # Check if this user already has a student profile
    cursor.execute("SELECT * FROM students WHERE user_id = %s", (user_id,))
    existing = cursor.fetchone()
    if existing:
        return jsonify({"error": "Profile already exists"}), 400

    # Insert new student profile
    cursor.execute("""
        INSERT INTO students (
            user_id, student_id, last_name, first_name, middle_name, name_extension,
            gender, birth_date, citizenship, civil_status, contact_number,
            email, avatar, created_at, updated_at
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
    """, (
        user_id, student_id, last_name, first_name, middle_name, name_extension,
        gender, birth_date, citizenship, civil_status, contact_number,
        email, avatar
    ))
    connection.commit()

    cursor.close()
    connection.close()

    return jsonify({"message": "Profile completed successfully"}), 201


@profile_bp.route('/scholarship-status/<int:application_id>', methods=['GET'])
@jwt_required()
def get_scholarship_status(application_id):
    """
    Get scholarship status for a specific application
    Returns different response structure based on current status
    """
    try:
        current_user_id = get_jwt_identity()
        conn = get_connection()
        cursor = conn.cursor()

        # First, verify the application belongs to the current user
        cursor.execute("""
                       SELECT a.id
                       FROM applications a
                       WHERE a.id = %s
                         AND a.student_id = %s
                         AND a.deleted_at IS NULL
                       """, (application_id, current_user_id))

        if not cursor.fetchone():
            return jsonify({"error": "Application not found or access denied"}), 404

        # Get comprehensive application data
        query = """
                SELECT a.id                                                                      as application_id, \
                       a.status                                                                  as app_status, \
                       a.submitted_at, \
                       a.remarks, \
                       s.id                                                                      as scholarship_id, \
                       s.name                                                                    as scholarship_name, \
                       s.description                                                             as scholarship_description, \
                       s.grant_amount, \
                       ss.status                                                                 as selection_status, \
                       ss.selection_reason, \
                       ss.awarded_amount, \
                       ss.created_at                                                             as selected_date, \
                       e.gwa, \
                       e.classification, \
                       e.score, \
                       e.total_units, \
                       st.student_id, \
                       CONCAT(st.first_name, ' ', IFNULL(st.middle_name, ''), ' ', st.last_name) as student_name, \
                       st.email                                                                  as student_email, \
                       c.name                                                                    as course_name, \
                       ei.year_level, \
                       camp.name                                                                 as campus_name, \
                       sem.name                                                                  as semester_name, \
                       fb.father_income + fb.mother_income                                       as total_income, \
                       sr.config                                                                 as scholarship_rules
                FROM applications a
                         LEFT JOIN scholarship_selections ss ON a.id = ss.application_id
                         LEFT JOIN scholarships s ON ss.scholarship_id = s.id
                         LEFT JOIN evaluations e ON a.id = e.application_id
                         LEFT JOIN students st ON a.student_id = st.user_id
                         LEFT JOIN education_info ei ON st.id = ei.student_id
                         LEFT JOIN courses c ON ei.course_id = c.course_id
                         LEFT JOIN campuses camp ON ei.campus_id = camp.campus_id
                         LEFT JOIN semesters sem ON a.semester_id = sem.id
                         LEFT JOIN family_background fb ON st.id = fb.student_id
                         LEFT JOIN scholarship_rules sr ON s.id = sr.scholarship_id
                WHERE a.id = %s \
                  AND a.deleted_at IS NULL \
                """

        cursor.execute(query, (application_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"error": "Application data not found"}), 404

        # Get application files
        cursor.execute("""
                       SELECT file_type, file_path, created_at
                       FROM application_files
                       WHERE application_id = %s
                         AND deleted_at IS NULL
                       """, (application_id,))
        files = cursor.fetchall()

        # Build common data structure
        common_data = {
            "selected_by_admin": {
                "name": "Dr. Maria Santos",  # This would typically come from users table
                "title": "Scholarship Committee Chair",
                "email": "m.santos@university.edu",
                "phone": "+63 912 345 6789"
            },
            "application": {
                "id": result['application_id'],
                "submitted_at": result['submitted_at'].isoformat() if result['submitted_at'] else None,
                "student": {
                    "name": result['student_name'],
                    "student_id": result['student_id'],
                    "course": result['course_name'],
                    "year_level": result['year_level'],
                    "campus": result['campus_name'],
                    "email": result['student_email']
                }
            },
            "evaluation": {
                "gwa": float(result['gwa']) if result['gwa'] else None,
                "classification": result['classification'],
                "score": float(result['score']) if result['score'] else None,
                "total_units": result['total_units']
            },
            "requirements": [
                {
                    "type": file['file_type'],
                    "file_name": file['file_path'].split('/')[-1] if file['file_path'] else None,
                    "uploaded_at": file['created_at'].isoformat() if file['created_at'] else None,
                    "status": "verified"  # You might want to add a status field to application_files table
                }
                for file in files
            ],
            "scholarship_rules": json.loads(result['scholarship_rules']) if result['scholarship_rules'] else {}
        }

        # Determine status and build appropriate response
        app_status = result['app_status']
        selection_status = result['selection_status']

        # If no scholarship selection exists, it's pending
        if not result['scholarship_id']:
            response_data = {
                "status": "pending",
                "message": "Your application is currently under review by the scholarship committee. Please wait for further updates.",
                "common": common_data
            }

        # If scholarship is selected but not yet awarded
        elif selection_status == 'selected':
            response_data = {
                "status": "selected",
                "scholarship": {
                    "id": result['scholarship_id'],
                    "name": result['scholarship_name'],
                    "description": result['scholarship_description'],
                    "grant_amount": float(result['grant_amount']),
                    "selection_reason": result['selection_reason'],
                    "selected_date": result['selected_date'].isoformat() if result['selected_date'] else None,
                    "submitted_date": result['submitted_at'].isoformat() if result['submitted_at'] else None
                },
                "common": common_data
            }

        # If scholarship is awarded
        elif selection_status == 'awarded':
            response_data = {
                "status": "awarded",
                "scholarship": {
                    "id": result['scholarship_id'],
                    "name": result['scholarship_name'],
                    "description": result['scholarship_description'],
                    "grant_amount": float(result['grant_amount']),
                    "awarded_amount": float(result['awarded_amount']) if result['awarded_amount'] else float(
                        result['grant_amount']),
                    "selection_reason": result['selection_reason'],
                    "selected_date": result['selected_date'].isoformat() if result['selected_date'] else None,
                    "awarded_date": result['selected_date'].isoformat() if result['selected_date'] else None,
                    # You might want a separate awarded_date field
                    "submitted_date": result['submitted_at'].isoformat() if result['submitted_at'] else None
                },
                "common": common_data
            }

        # If application is denied or cancelled
        elif app_status == 'denied' or selection_status == 'cancelled':
            response_data = {
                "status": "denied",
                "scholarship": {
                    "id": result['scholarship_id'] if result['scholarship_id'] else 1,
                    "name": result['scholarship_name'] if result['scholarship_name'] else "General Scholarship",
                    "description": result['scholarship_description'] if result[
                        'scholarship_description'] else "Scholarship application",
                    "grant_amount": float(result['grant_amount']) if result['grant_amount'] else 0.0,
                    "denial_reason": result['remarks'] or result[
                        'selection_reason'] or "Your application did not meet the minimum requirements.",
                    "reviewed_date": result['selected_date'].isoformat() if result['selected_date'] else None,
                    "submitted_date": result['submitted_at'].isoformat() if result['submitted_at'] else None
                },
                "common": common_data
            }

        else:
            # Default to pending if status is unclear
            response_data = {
                "status": "pending",
                "message": "Your application is currently under review by the scholarship committee. Please wait for further updates.",
                "common": common_data
            }

        return jsonify(response_data), 200

    except Exception as e:
        return jsonify(error("Internal server error")), 500

