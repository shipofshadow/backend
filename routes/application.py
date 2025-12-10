import json

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
import traceback

from services.notification_service import notify_admin, notify_admin_new_application, notify_student_application_status, \
    create_notification
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
    user_id = get_jwt_identity()

    # 1. Parse Form Data
    data = parse_form_data(request.form)

    # 2. Handle Multiple ITR Files
    itr_paths = []
    if "itr" in request.files:
        # getlist() retrieves ALL files uploaded with the key 'itr'
        files = request.files.getlist("itr")
        for f in files:
            if f and allowed_file(f.filename):
                path = save_file(f, user_id, "itr")
                itr_paths.append(path)

    # 3. Handle Grades (Single file)
    grades_path = None
    if "grades" in request.files:
        grades_file = request.files["grades"]
        if allowed_file(grades_file.filename):
            grades_path = save_file(grades_file, user_id, "grades")

    # 4. Get Active Term
    active = get_active_period()
    if not active:
        return jsonify({"error": "No active academic period found"}), 400

    data["academicYearId"] = active["academic_year_id"]
    data["semesterId"] = active["semester_id"]

    # 5. Fetch Student Info (Needed for validation and notifications)
    student_info = fetch_student_info(user_id)
    if not student_info:
        return jsonify({"error": "Student information not found"}), 404

    try:
        # Initialize Application Object
        application = Application(data)
        db = get_connection()

        # 6. Save Main Application Data
        # Note: save_application usually returns the new ID
        application_id = save_application(db, user_id, application)

        # 7. Insert Grades (Subjects/Units)
        if hasattr(application, 'grades_list') and application.grades_list:
            insert_grades(db, application_id, application.grades_list)

        # 8. Insert File Paths (The Fix)
        with db.cursor() as cursor:
            # A. Loop through ITR paths and insert each one
            if itr_paths:
                for path in itr_paths:
                    cursor.execute("""
                                   INSERT INTO application_files (application_id, file_type, file_path)
                                   VALUES (%s, 'itr', %s)
                                   """, (application_id, path))

            # B. Insert Grades file (if exists)
            if grades_path:
                cursor.execute("""
                               INSERT INTO application_files (application_id, file_type, file_path)
                               VALUES (%s, 'grades', %s)
                               """, (application_id, grades_path))

        db.commit()

        # 9. Notifications
        # We need the campus_id for the new staff notification logic
        # Assuming student_info contains 'campus_id' or it's in data['campus']

        # campus_id = student_info.get('campus_id') or data.get('campus')
        #
        # if campus_id:
        #     notify_admin_new_application(
        #         application_id=application_id,
        #         student_info=student_info,
        #         application_data=data,
        #         campus_id=campus_id
        #     )

        notify_student_application_status(application_id, "pending")
        create_notification(
            user_id,
            'application_submitted',
            'Application Submitted',
            'Your application has been received.'
        )

        return jsonify({"message": "Application submitted successfully", "id": application_id}), 200

    except Exception as e:
        db.rollback()
        print("Error in /apply:", e)
        traceback.print_exc()
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
        student_info = fetch_student_info(user_id)

        notify_admin_new_application(application_id, student_info, data)
        if success:
            db.commit()
            return jsonify({"message": "Application updated successfully"}), 200
        else:
            db.rollback()
            return jsonify({"error": "Failed to update application or unauthorized"}), 400

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

