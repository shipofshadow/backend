from flask import Flask, jsonify, request, Blueprint, send_from_directory
from flask_jwt_extended import jwt_required

from db import get_connection
from routes.application import UPLOAD_FOLDER
from services.application_service import base_applicant_query
from utils.decorator import admin_required

applicants_bp = Blueprint('applicants', __name__, url_prefix='/api/applicants')

@applicants_bp.route('/files/<path:filename>', methods=['GET'])
def get_uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@applicants_bp.route("/qualified", methods=["GET"])
@jwt_required()
def get_all_qualified_applicants():
    db = get_connection()
    cursor = db.cursor()

    query = base_applicant_query() + """
        WHERE semesters.is_active = 1
        AND applications.status = 'approved'
    """
    cursor.execute(query)

    result = cursor.fetchall()
    cursor.close()
    db.close()

    return jsonify(result), 200

@applicants_bp.route("/", methods=["GET"])
@jwt_required()
def get_all_applicants():
    db = get_connection()
    cursor = db.cursor()
    cursor.execute(base_applicant_query() + " WHERE semesters.is_active = 1")
    result = cursor.fetchall()
    return jsonify(result), 200

@applicants_bp.route("/not-applied", methods=["GET"])
@jwt_required()
def get_not_applied():
    db = get_connection()
    cursor = db.cursor()

    cursor.execute("""
                    SELECT 
                        students.id AS student_id,
                        students.user_id,
                        students.student_id AS student_number,
                        students.first_name,
                        students.middle_name,
                        students.last_name,
                        students.name_extension,
                        students.gender,
                        students.birth_date,
                        students.civil_status,
                        students.citizenship,
                        students.contact_number,
                        students.email,
                        users.is_active,
                        users.id AS user_id,
                        users.username,
                        users.role,
                        users.created_at,
                        users.updated_at
                    FROM users
                    INNER JOIN students ON students.user_id = users.id
                    LEFT JOIN applications ON applications.student_id = students.id
                    INNER JOIN semesters ON semesters.id = applications.semester_id
                    WHERE users.role = 'student'
                      AND semesters.is_active = 1
                    """)
    result = cursor.fetchall()

    return jsonify(result), 200

@applicants_bp.route('/<int:student_id>', methods=['GET'])
@jwt_required()
def get_applicant_by_id(student_id):
    db = get_connection()
    with db.cursor() as cursor:
        cursor.execute(base_applicant_query() + " WHERE semesters.is_active = 1 AND students.user_id = %s", (student_id,))
        row = cursor.fetchone()

    if not row:
        return jsonify({"message": "Applicant not found"}), 404

    return jsonify(row), 200

@applicants_bp.route('/<int:applicant_id>', methods=['PUT'])
@jwt_required()
def update_applicant(applicant_id):
    data = request.json
    return jsonify(data), 200

@applicants_bp.route('/<int:applicant_id>', methods=['DELETE'])
@jwt_required()
def delete_applicant(applicant_id):
    return jsonify({"message": "Applicant deleted"}), 200
