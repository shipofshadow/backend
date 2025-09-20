from flask import Blueprint, jsonify, send_from_directory, request
from flask_jwt_extended import jwt_required, get_jwt_identity

import storage
from config import UPLOAD_FOLDER
from routes.scholarship_summary import get_scholarship_summary
from storage import get_connection
from services.application_service import base_applicant_query

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
