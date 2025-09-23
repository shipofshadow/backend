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
    try:
        current_user_id = get_jwt_identity()
        conn = get_connection()
        cursor = conn.cursor()

        # Verify ownership
        cursor.execute("""
            SELECT id FROM applications
            WHERE id = %s AND student_id = %s AND deleted_at IS NULL
        """, (application_id, current_user_id))
        if not cursor.fetchone():
            return jsonify({"error": "Application not found or access denied"}), 404

        # Load core application data
        cursor.execute("""
            SELECT 
                applications.id AS application_id,
                applications.status,
                applications.submitted_at,
                applications.remarks,
                applications.reference_number,
                scholarship_selections.status AS selection_status,
                scholarship_selections.selection_reason,
                scholarship_selections.awarded_amount,
                scholarship_selections.created_at AS selection_date,
                scholarships.id AS scholarship_id,
                scholarships.name AS scholarship_name,
                scholarships.description AS scholarship_description,
                scholarships.grant_amount,
                evaluations.gwa,
                evaluations.score,
                evaluations.total_units,
                evaluations.classification,
                evaluations.income,
                students.student_id,
                CONCAT(students.first_name,' ',students.last_name) AS student_name,
                students.email AS student_email,
                students.contact_number,
                courses.name AS course_name,
                education_info.year_level,
                campuses.name AS campus_name,
                scholarship_rules.config AS scholarship_rules
            FROM applications
            LEFT JOIN scholarship_selections ON applications.id = scholarship_selections.application_id
            LEFT JOIN scholarships ON scholarship_selections.scholarship_id = scholarships.id
            LEFT JOIN evaluations ON applications.id = evaluations.application_id
            LEFT JOIN students ON applications.student_id = students.user_id
            LEFT JOIN education_info 
                ON education_info.student_id = students.user_id
                AND education_info.semester_id = applications.semester_id
            LEFT JOIN campuses ON education_info.campus_id = campuses.campus_id
            LEFT JOIN departments ON education_info.department_id = departments.department_id
            LEFT JOIN courses ON education_info.course_id = courses.course_id
            LEFT JOIN scholarship_rules ON scholarships.id = scholarship_rules.scholarship_id
            WHERE applications.id = %s 
              AND applications.deleted_at IS NULL
        """, (application_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({"error": "Application data not found"}), 404

        # Files
        cursor.execute("""
            SELECT file_type, file_path, created_at
            FROM application_files
            WHERE application_id = %s AND deleted_at IS NULL
        """, (application_id,))
        files = cursor.fetchall()

        requirements = [
            {
                "file_name": f["file_path"].split("/")[-1],
                "type": f["file_type"],
                "uploaded_at": f["created_at"].isoformat(),
                "status": "verified"
            } for f in files
        ]

        common = {
            "application": {
                "id": result["application_id"],
                "reference_number": result["reference_number"],
                "status": result['status'],
                "submitted_at": result["submitted_at"].isoformat() if result["submitted_at"] else None,
                "student": {
                    "name": result["student_name"],
                    "student_id": result["student_id"],
                    "course": result["course_name"],
                    "year_level": result["year_level"],
                    "campus": result["campus_name"],
                    "email": result["student_email"],
                    "phone": result["contact_number"]
                }
            },
            "evaluation": {
                "gwa": result["gwa"],
                "score": result["score"],
                "total_units": result["total_units"],
                "classification": result["classification"],
                "income": result["income"]
            },
            "requirements": requirements,
            "scholarship_rules": json.loads(result["scholarship_rules"]) if result["scholarship_rules"] else {}
        }

        # -------------------------
        # Build response by status
        # -------------------------
        app_status = result["status"]
        sel_status = result["selection_status"]

        if app_status == "pending":
            return jsonify({
                "status": "pending",
                "common": common
            })

        elif app_status == "evaluated" and not sel_status:
            return jsonify({
                "status": "evaluated",
                "message": "Your application has been evaluated by the committee. Awaiting scholarship selection.",
                "common": common
            })

        elif sel_status in ("awarded", "selected"):
            return jsonify({
                "status": "approved",
                "name": result["scholarship_name"],
                "description": result["scholarship_description"],
                "grant_amount": float(result["grant_amount"]),
                "submitted_at": result["submitted_at"].isoformat(),
                "approved_at": result["selection_date"].isoformat(),
                "common": common,
                "selection_reason": result["selection_reason"],
                "requirements": requirements,
                "admin_contact": {
                    "name": "Ms. Maria Santos",
                    "title": "Scholarship Coordinator",
                    "email": "maria.santos@university.edu.ph",
                    "phone": "+63 2 8123 4567"
                }
            })

        elif app_status == "denied" or sel_status == "cancelled":
            rules = json.loads(result["scholarship_rules"]) if result["scholarship_rules"] else {}
            return jsonify({
                "status": "denied",
                "name": result["scholarship_name"],
                "description": result["scholarship_description"],
                "grant_amount": float(result["grant_amount"]) if result["grant_amount"] else 0,
                "submitted_at": result["submitted_at"].isoformat(),
                "denied_at": result["selection_date"].isoformat() if result["selection_date"] else None,
                "application": common["application"],
                "evaluation": common["evaluation"],
                "denial_reason": result["remarks"] or "Application did not meet requirements.",
                "scholarship_requirements": {
                    "min_gwa": rules.get("min_gwa"),
                    "min_units": rules.get("min_units_enrolled"),
                    "max_income": rules.get("max_income")
                }
            })

        else:
            return jsonify({
                "status": "pending",
                "common": common
            })

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500
