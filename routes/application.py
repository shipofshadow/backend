import os
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from db import get_connection
from models.application import Application
from services.application_service import save_application
from utils.utils import allowed_file, save_file

UPLOAD_FOLDER = "uploads"

application_bp = Blueprint("application", __name__, url_prefix="/api/application")


@application_bp.route("/apply", methods=["POST"])
@jwt_required()
def submit_application():
    user_id = get_jwt_identity()

    if "itr" not in request.files or "grades" not in request.files:
        return jsonify({"error": "Missing files (itr or grades)"}), 400

    data = request.form.to_dict()
    # Nested fields need to be parsed separately from JSON strings if you're sending as form-data
    import json
    data["father"] = json.loads(request.form.get("father", "{}"))
    data["mother"] = json.loads(request.form.get("mother", "{}"))

    # File handling
    itr_file = request.files["itr"]
    grades_file = request.files["grades"]

    if not allowed_file(itr_file.filename) or not allowed_file(grades_file.filename):
        return jsonify({"error": "Invalid file format"}), 400

    itr_filename = save_file(itr_file, user_id, "itr", UPLOAD_FOLDER)
    grades_filename = save_file(grades_file, user_id, "grades", UPLOAD_FOLDER)

    # Attach file paths
    data["itr"] = itr_filename
    data["grades"] = grades_filename

    try:
        application = Application(data)

        db = get_connection()
        save_application(db, user_id, application)

        return jsonify({"message": "Application submitted successfully."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@application_bp.route('/status', methods=['GET'])
@jwt_required()
def check_application_status():
    user_id = get_jwt_identity()
    db = get_connection()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM applications WHERE student_id = %s", (user_id,))
    (count,) = cursor.fetchone()
    return jsonify({"has_applied": count > 0})
