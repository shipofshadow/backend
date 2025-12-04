import json

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
import traceback

from services.notification_service import notify_admin, notify_admin_new_application, notify_student_application_status
from storage import get_connection
from models.application import Application
from services.application_service import save_application, insert_grades, update_application_data
from services.admin.manage_periods import get_active_period
from utils.students import fetch_student_info
from utils.utils import allowed_file, save_file

UPLOAD_FOLDER = "uploads"

application_bp = Blueprint("application", __name__, url_prefix="/api/application")

def parse_form_data(form):
    result = {}

    for key in form:
        if '[' in key and key.endswith(']'):
            # For keys like "father[firstName]"
            parent, child = key[:-1].split('[', 1)
            if parent not in result:
                result[parent] = {}
            result[parent][child] = form.get(key)
        else:
            result[key] = form.get(key)

    return result

@application_bp.route("/apply", methods=["POST"])
@jwt_required()
def submit_application():
    """
    Submit a new scholarship application.

    Accepts multipart/form-data including:
    - Applicant form fields
    - Files: itr, grades

    Automatically attaches the active semester and academic year.

    ---
    tags:
      - Applications
    security:
      - jwt: []
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: itr
        type: file
        required: true
      - in: formData
        name: grades
        type: file
        required: true
      - in: formData
        name: ...
        type: string
        description: All other applicant fields
    responses:
      200:
        description: Application submitted successfully
      400:
        description: Missing files or invalid file format
      500:
        description: Internal server error
    """

    user_id = get_jwt_identity()
    data = parse_form_data(request.form)

    if "itr" not in request.files or "grades" not in request.files:
        return jsonify({"error": "Missing files (itr or grades)"}), 400

    itr_file = request.files["itr"]
    grades_file = request.files["grades"]

    if not allowed_file(itr_file.filename) or not allowed_file(grades_file.filename):
        return jsonify({"error": "Invalid file format"}), 400

    itr_filename = save_file(itr_file, user_id, "itr")
    grades_filename = save_file(grades_file, user_id, "grades")

    data["itr"] = itr_filename
    data["grades"] = grades_filename

    active = get_active_period()
    data["academicYearId"] = active["academic_year_id"]
    data["semesterId"] = active["semester_id"]

    print(active)

    student_info = fetch_student_info(user_id)
    if not student_info:
        return jsonify({"error": "Student information not found"}), 404

    try:
        application = Application(data)

        db = get_connection()
        application_id = save_application(db, user_id, application)

        if application.grades_list:
            insert_grades(db, application_id, application.grades_list)

        with db.cursor() as cursor:
            cursor.execute("""
                INSERT INTO application_files (application_id, file_type, file_path)
                VALUES (%s, %s, %s)
            """, (application_id, 'itr', itr_filename))
            cursor.execute("""
                INSERT INTO application_files (application_id, file_type, file_path)
                VALUES (%s, %s, %s)
            """, (application_id, 'grades', grades_filename))
        db.commit()

        notify_admin_new_application(
            application_id=application_id,
            student_info=student_info,
            application_data=data,
        )

        notify_student_application_status(application_id, "submitted")

        return jsonify(data), 200

    except Exception as e:
        db.rollback()  # Rollback to avoid partial writes if there's an error
        print("Error in /apply:", e)
        traceback.print_exc()  # <--- shows the real error!

        return jsonify({"error": str(e)}), 500


@application_bp.route('/status', methods=['GET'])
@jwt_required()
def check_application_status():
    """
    Check if the authenticated user has submitted an application for the active semester.

    Returns status and submission timestamp if application exists.

    ---
    tags:
      - Applications
    security:
      - jwt: []
    responses:
      200:
        description: Current application status
      400:
        description: No active semester found
      500:
        description: Could not check application status
    """

    try:
        user_id = int(get_jwt_identity())
        db = get_connection()
        cursor = db.cursor()

        active = get_active_period()

        if not active:
            return jsonify({"error": "No active semester found"}), 400

        semester_id = active['semester_id']

        cursor.execute("""
            SELECT status, submitted_at FROM applications 
            WHERE student_id = %s AND semester_id = %s
            LIMIT 1
        """, (user_id, semester_id))

        result = cursor.fetchone()

        if result:
            return jsonify({"has_applied": True, "submitted_at": result['submitted_at'], "status": result['status']}), 200
        else:
            return jsonify({"has_applied": False, "status": None}), 200

    except Exception as e:
        return jsonify({"error": "Could not check application status"}), 500


@application_bp.route("/update/<int:application_id>", methods=["PUT"])
@jwt_required()
def update_application_route(application_id):
    try:
        user_id = get_jwt_identity()

        # 1. Parse Data (handles nested keys like father[lastName])
        data = parse_form_data(request.form)

        # 2. Handle Files
        if "itr" in request.files:
            itr_file = request.files["itr"]
            if allowed_file(itr_file.filename):
                data["itr"] = save_file(itr_file, user_id, "itr")

        if "grades" in request.files:
            grades_file = request.files["grades"]
            if allowed_file(grades_file.filename):
                data["grades"] = save_file(grades_file, user_id, "grades")

        # 3. Handle Grades List safely
        if "gradesList" in request.form:
            try:
                data["grades_list"] = json.loads(request.form["gradesList"])
            except json.JSONDecodeError:
                data["grades_list"] = []

        # 4. Create Application Object
        # This maps the dictionary to the object properties
        application = Application(data)

        # 5. Update
        db = get_connection()
        success = update_application_data(db, user_id, application_id, application, data)

        if success:
            db.commit()
            return jsonify({"message": "Application updated successfully"}), 200
        else:
            db.rollback()
            return jsonify({"error": "Failed to update application or unauthorized"}), 400

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500