import os
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from db import get_connection
from models.application import Application
from services.application_service import save_application
from utils.academic_year import get_academic_year
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

    if "itr" not in request.files or "grades" not in request.files:
        return jsonify({"error": "Missing files (itr or grades)"}), 400

    import json
    data = parse_form_data(request.form)


    itr_file = request.files["itr"]
    grades_file = request.files["grades"]

    if not allowed_file(itr_file.filename) or not allowed_file(grades_file.filename):
        return jsonify({"error": "Invalid file format"}), 400

    itr_filename = save_file(itr_file, user_id, "itr", UPLOAD_FOLDER)
    grades_filename = save_file(grades_file, user_id, "grades", UPLOAD_FOLDER)

    data["itr"] = itr_filename
    data["grades"] = grades_filename

    active = get_academic_year()
    data["academicYearId"] = active["academic_year_id"]
    data["semesterId"] = active["semester_id"]


    try:
        application = Application(data)

        db = get_connection()
        save_application(db, user_id, application)

        return jsonify(data), 200

    except Exception as e:
        print("Error in /apply:", e)  # Log the traceback
        return jsonify({"error": str(e)}), 500

@application_bp.route('/status', methods=['GET'])
@jwt_required()
def check_application_status():
    try:
        user_id = int(get_jwt_identity())
        db = get_connection()
        cursor = db.cursor()

        cursor.execute("SELECT COUNT(*) AS total, status FROM applications WHERE student_id = %s", (user_id,))
        result = cursor.fetchone()
        count = int(result["total"]) if result else 0
        has_applied = count > 0

        return jsonify({"has_applied": has_applied, "status": result["status"]}), 200
    except Exception as e:
        return jsonify({"error": "Could not check application status"}), 500
