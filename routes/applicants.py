from datetime import datetime, timezone

from flask import Flask, jsonify, request, Blueprint, send_from_directory
from flask_jwt_extended import jwt_required

from services.notification_service import create_notification, notify_student_application_status
from storage import get_connection
from routes.application import UPLOAD_FOLDER
from services.application_service import base_applicant_query, fetch_grades_by_application_ids
from utils.applications import get_application
from utils.decorator import admin_required

applicants_bp = Blueprint('applicants', __name__, url_prefix='/api/applicants')

@applicants_bp.route('/files/<path:filename>', methods=['GET'])
def get_uploaded_file(filename):
    """
    Download an uploaded file by filename.
    ---
    tags:
      - Applicants
    parameters:
      - in: path
        name: filename
        type: string
        required: true
    responses:
      200:
        description: File downloaded successfully
    """
    return send_from_directory(UPLOAD_FOLDER, filename)


def fetch_applicants_by_status(status: str):
    db = get_connection()
    cursor = db.cursor()

    query = base_applicant_query() + """
    WHERE applications.deleted_at IS NULL
    AND semesters.is_active = 1 
    AND applications.status = %s
    """
    cursor.execute(query, (status,))
    applicants = cursor.fetchall()

    if not applicants:
        cursor.close()
        db.close()
        return []

    application_ids = [app["id"] for app in applicants]
    grades_map = fetch_grades_by_application_ids(cursor, application_ids)

    for app in applicants:
        app["grades"] = grades_map.get(app["id"], [])

    cursor.close()
    db.close()
    return applicants


@applicants_bp.route("/qualified", methods=["GET"])
@jwt_required()
def get_all_qualified_applicants():
    """
    Get all applicants with status 'approved'.
    ---
    tags:
      - Applicants
    security:
      - jwt: []
    responses:
      200:
        description: List of approved applicants
    """

    return jsonify(fetch_applicants_by_status("approved")), 200


@applicants_bp.route("/pending", methods=["GET"])
def get_pending_applicants():
    """
    Get all applicants with status 'pending'.
    ---
    tags:
      - Applicants
    responses:
      200:
        description: List of pending applicants
    """

    return jsonify(fetch_applicants_by_status("pending")), 200


@applicants_bp.route("/", methods=["GET"])
@jwt_required()
@jwt_required()
def get_all_applicants():
    """
    Get all applicants (active semester).
    ---
    tags:
      - Applicants
    responses:
      200:
        description: List of all applicants
    """

    db = get_connection()
    cursor = db.cursor()
    cursor.execute(base_applicant_query() + " WHERE applications.deleted_at IS NULL AND semesters.is_active = 1")
    applicants = cursor.fetchall()

    if not applicants:
        cursor.close()
        db.close()
        return jsonify([]), 200

    application_ids = [app["id"] for app in applicants]
    grades_map = fetch_grades_by_application_ids(cursor, application_ids)

    for app in applicants:
        app["grades"] = grades_map.get(app["id"], [])

    cursor.close()
    db.close()
    return jsonify(applicants), 200

@applicants_bp.route("/archived", methods=["GET"])
@jwt_required()
def get_archived_applicants():
    """
    Get all archived applicants (deleted applications).
    ---
    tags:
      - Applicants
    security:
      - jwt: []
    responses:
      200:
        description: List of archived applicants
    """

    db = get_connection()
    cursor = db.cursor()

    query = base_applicant_query() + """
        WHERE applications.deleted_at IS NOT NULL
        AND semesters.is_active = 1
    """
    cursor.execute(query)
    applicants = cursor.fetchall()

    if not applicants:
        cursor.close()
        db.close()
        return jsonify([]), 200

    application_ids = [app["id"] for app in applicants]
    grades_map = fetch_grades_by_application_ids(cursor, application_ids)

    for app in applicants:
        app["grades"] = grades_map.get(app["id"], [])

    cursor.close()
    db.close()
    return jsonify(applicants), 200


@applicants_bp.route("/not-applied", methods=["GET"])
@jwt_required()
def get_not_applied():
    """
    Get students who have not submitted applications for the active semester.
    ---
    tags:
      - Applicants
    security:
      - jwt: []
    responses:
      200:
        description: List of students not applied
    """

    db = get_connection()
    cursor = db.cursor()

    cursor.execute("""
SELECT 
    s.id AS student_id,
    s.user_id,
    s.student_id AS student_number,
    s.first_name,
    s.last_name,
    s.first_name,
    s.middle_name,
    s.name_extension,
    s.gender,
    s.birth_date,
    s.citizenship,
    s.civil_status,
    s.email,
    s.created_at,
    s.updated_at,
    s.deleted_at,
    u.username
FROM students s
JOIN users u ON u.id = s.user_id
WHERE u.role = 'student'
AND s.id NOT IN (
    SELECT s2.id
    FROM applications a
    JOIN semesters sem ON sem.id = a.semester_id
    JOIN students s2 ON s2.user_id = a.student_id
    WHERE sem.is_active = 1
    AND a.deleted_at IS NULL
);            
    """)
    result = cursor.fetchall()
    return jsonify(result), 200


@applicants_bp.route('/<int:applicantId>', methods=['GET'])
def get_applicant_by_id(applicantId):
    """
    Get detailed information about an applicant by application ID.
    ---
    tags:
      - Applicants
    parameters:
      - in: path
        name: applicantId
        type: integer
        required: true
    responses:
      200:
        description: Applicant details with grades
      404:
        description: Applicant not found
    """

    db = get_connection()
    cursor = db.cursor()
    cursor.execute(base_applicant_query() + " WHERE semesters.is_active = 1 AND applications.id = %s", (applicantId,))
    applicant = cursor.fetchone()

    if not applicant:
        cursor.close()
        db.close()
        return jsonify({"message": "Applicant not found"}), 404

    application_id = applicant["id"]
    grades_map = fetch_grades_by_application_ids(cursor, [application_id])
    applicant["grades"] = grades_map.get(application_id, [])

    cursor.close()
    db.close()
    return jsonify(applicant), 200


@applicants_bp.route('/<int:applicant_id>', methods=['PUT'])
@jwt_required()
def update_applicant(applicant_id):
    data = request.json
    return jsonify(data), 200


@applicants_bp.route('/<int:application_id>', methods=['PATCH'])
@jwt_required()
def delete_application(application_id):
    db = get_connection()
    cursor = db.cursor()
    now = datetime.now(tz=timezone.utc)

    try:

        cursor.execute(
            "UPDATE applications SET deleted_at = %s WHERE id = %s",
            (now, application_id)
        )

        related_tables = [
            "application_grades",
            "application_files",
            "evaluations"
        ]

        for table in related_tables:
            cursor.execute(
                f"UPDATE {table} SET deleted_at = %s WHERE application_id = %s",
                (now, application_id)
            )

        db.commit()
        return jsonify({"message": "Applicant application archived successfully"}), 200

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        db.close()

@applicants_bp.route('/<int:application_id>/status', methods=['PUT'])
@jwt_required()
def update_application_status(application_id):
    data = request.get_json()
    status = data.get("status")
    remarks = data.get("remarks")
    if status not in ['approved', 'denied']:
        return jsonify({"error": "Invalid status"}), 400

    db = get_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE applications SET status = %s, remarks = %s WHERE id = %s", (status, remarks, application_id))
    db.commit()
    cursor.close()
    db.close()

    return jsonify({"message": f"Application {status}"}), 200


@applicants_bp.route('/<int:application_id>/deny', methods=['POST'])
@jwt_required()
def deny_applicant(application_id):
    app = get_application(application_id)
    if not app:
        return jsonify({"error": "Applicant not found"}), 404

    # Get the reason from request body
    data = request.get_json()
    reason = data.get('reason', '').strip() if data else ''

    if not reason:
        return jsonify({"error": "Denial reason is required"}), 400

    db = get_connection()
    cursor = db.cursor()
    try:
        # Update the application status to 'denied' and add remarks
        cursor.execute(
            "UPDATE applications SET status = 'denied', remarks = %s WHERE id = %s",
            (reason, application_id)
        )
        db.commit()

        # Notify student with the denial reason
        notify_student_application_status(
            application_id,
            status="denied",
            remarks=f'Your application #{application_id} has been denied. Reason: {reason}'
        )

        return jsonify({"message": "Applicant denied and notification sent"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        db.close()