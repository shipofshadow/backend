from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

import db
from db import get_connection
from services.application_service import base_applicant_query

profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")

@profile_bp.route("/applications", methods=["GET"])
@jwt_required()
def get_applications():
    user_id = get_jwt_identity()

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(base_applicant_query() + 'WHERE applications.student_id = %s', [user_id])
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
    cursor.execute("SELECT id, username, role FROM users WHERE id = %s", (user_id,))
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
        user['profile'] = student_profile

    cursor.close()
    connection.close()

    return jsonify(user), 200
