from flask import Blueprint, request, jsonify
from services.admin.manage_periods import (
    get_active_period,
    add_academic_year,
    add_semester,
    activate_semester,
    get_all_periods
)

academic_period_bp = Blueprint('academic_period', __name__, url_prefix='/api/period')

@academic_period_bp.route("/all", methods=["GET"])
def all_periods():
    result = get_all_periods()
    return jsonify(result), 200

@academic_period_bp.route("/active", methods=["GET"])
def active_period():
    result = get_active_period()
    if result:
        return jsonify(result), 200
    return jsonify({"message": "No active semester found"}), 404

@academic_period_bp.route("/year", methods=["POST"])
def create_year():
    data = request.json
    year_start = data.get("year_start")
    if not year_start:
        return jsonify({"error": "year_start is required"}), 400
    add_academic_year(year_start)
    return jsonify({"message": "Academic year added"}), 201

@academic_period_bp.route("/semester", methods=["POST"])
def create_semester():
    data = request.json
    academic_year_id = data.get("academic_year_id")
    name = data.get("name")
    if not academic_year_id or not name:
        return jsonify({"error": "academic_year_id and name are required"}), 400
    add_semester(academic_year_id, name)
    return jsonify({"message": "Semester added"}), 201

@academic_period_bp.route("/semester/<int:semester_id>/activate", methods=["PUT"])
def set_active_semester(semester_id):
    activate_semester(semester_id)
    return jsonify({"message": "Semester activated"}), 200
