import json

from flask import Blueprint, jsonify, send_from_directory, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from services.notification_service import create_notification
from utils.hashing import hash_password, verify_password
from config import UPLOAD_FOLDER
from routes.scholarship_summary import get_scholarship_summary
from storage import get_connection
from services.application_service import base_applicant_query, fetch_grades_by_application_id
from utils.response import error
from utils.utils import save_avatar

profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")


@profile_bp.route('/upload-avatar', methods=['POST'])
@jwt_required()
def upload_avatar():
    """
    Upload avatar image for the current user.
    Works for both students and admins.
    """
    user_id = get_jwt_identity()

    if 'avatar' not in request.files:
        return jsonify({"error": "No avatar file provided"}), 400

    avatar_file = request.files['avatar']

    if avatar_file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Validate file type
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    if not ('.' in avatar_file.filename and
            avatar_file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        return jsonify({"error": "Invalid file type. Allowed: png, jpg, jpeg, gif"}), 400

    # Save avatar using existing utility (handles S3/local storage)
    result = save_avatar(avatar_file, str(user_id))

    if not result:
        return jsonify({"error": "Failed to save avatar"}), 500

    # Update database based on user role
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            cursor.close()
            connection.close()
            return jsonify({"error": "User not found"}), 404

        if user['role'] == 'student':
            cursor.execute(
                "UPDATE students SET avatar = %s WHERE user_id = %s",
                (result, user_id)
            )
        else:  # admin, super_admin, faculty, bitress
            cursor.execute(
                "UPDATE user_details SET avatar = %s WHERE user_id = %s",
                (result, user_id)
            )

        connection.commit()
    except Exception as e:
        connection.rollback()
        cursor.close()
        connection.close()
        return jsonify({"error": "Failed to update avatar in database"}), 500

    cursor.close()
    connection.close()

    return jsonify({
        "success": True,
        "avatar": result,
        "message": "Avatar uploaded successfully"
    }), 200


@profile_bp.route("/scholarship/summary", methods=["GET"])
@jwt_required()
def scholarship_summary():
    student_id = get_jwt_identity()
    active_only_param = request.args.get("active_only", "false").lower()
    active_only = active_only_param in ["true", "1", "yes"]
    return get_scholarship_summary(student_id, active_only=active_only)


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


@profile_bp.route("/applications/<int:application_id>", methods=["GET"])
@jwt_required()
def get_application_by_id(application_id):
    user_id = get_jwt_identity()

    connection = get_connection()
    cursor = connection.cursor()

    query = f"""
        {base_applicant_query()}
        WHERE applications.student_id = %s AND applications.id = %s
          AND semesters.is_active = 1
    """

    cursor.execute(query, [user_id, application_id])
    application = cursor.fetchone()
    if not application:
        cursor.close()
        return jsonify({"error": "Application not found"}), 404

    grades = fetch_grades_by_application_id(cursor, application_id)

    application['grades'] = grades

    cursor.close()
    return jsonify(application), 200
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
    # Remove any leading 'uploads/' or 'uploads\' to be safe
    if filename.startswith("uploads/"):
        filename = filename[len("uploads/"):]
    elif filename.startswith("uploads\\"):
        filename = filename[len("uploads\\"):]

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
            return jsonify({
                "common": common,
                "status": "denied",
                "denied_at": result["selection_date"].isoformat() if result["selection_date"] else None,
                "denial_reason": result["remarks"] or "Application did not meet requirements.",
            })

        else:
            return jsonify({
                "status": "pending",
                "common": common
            })

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@profile_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    old_password = data.get('old_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')

    # Validate required fields
    if not old_password or not new_password or not confirm_password:
        return jsonify({"error": "All password fields are required"}), 400

    if new_password != confirm_password:
        return jsonify({"error": "New password and confirmation do not match"}), 400

    # Enforce password policy (example: min length, must include digits/letters)
    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters long"}), 400
    if new_password.isdigit() or new_password.isalpha():
        return jsonify({"error": "New password must include both letters and numbers"}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT password, is_active FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({"error": "User not found"}), 404
        if not result["is_active"]:
            return jsonify({"error": "Account is inactive"}), 403

        current_hashed_password = result["password"]
        if not verify_password(old_password, current_hashed_password):
            return jsonify({"error": "Old password is incorrect"}), 400

        new_hashed_password = hash_password(new_password)

        cursor.execute("""
            UPDATE users 
            SET password = %s, updated_at = NOW() 
            WHERE id = %s
        """, (new_hashed_password, user_id))
        conn.commit()
        
        create_notification(
            user_id, 
            'password_changed', 
            'Password changed.', 
            'Your account password was changed successfully.')


        return jsonify({"message": "Password changed successfully"}), 200

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({f"error: {e}" }), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
