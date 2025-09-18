from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

import storage
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
    """
    Get profile information of the logged-in user
    ---
    tags:
      - Profile
    security:
      - Bearer: []
    responses:
      200:
        description: User profile info
        content:
          application/json:
            schema:
              type: object
              properties:
                id:
                  type: integer
                  example: 123
                username:
                  type: string
                  example: "john_doe"
                role:
                  type: string
                  example: "student"
                profile:
                  type: object
                  description: Detailed student profile (if role is student)
                  properties:
                    first_name:
                      type: string
                      example: "John"
                    last_name:
                      type: string
                      example: "Doe"
                    education_info:
                      type: object
                      example: {"school": "ABC University", "year_level": 3}
                    family_background:
                      type: object
                      example: {"father_name": "Mr. Doe", "mother_name": "Mrs. Doe"}
                    addresses:
                      type: object
                      example: {"street": "123 Main St", "city": "Metro City"}
      401:
        description: Unauthorized - JWT token missing or invalid
      404:
        description: User not found
    """

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
