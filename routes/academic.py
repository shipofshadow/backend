from flask import Blueprint, request, jsonify
from services.admin import manage_academic

campus_bp = Blueprint("campus", __name__, url_prefix="/api/campus")

@campus_bp.route("/", methods=["GET"])
def get_campuses():
    campuses = manage_academic.get_campuses()
    return jsonify(campuses)

@campus_bp.route("/", methods=["POST"])
def create_campus():
    name = request.json.get("name")
    manage_academic.add_campus(name)
    return jsonify({"message": "Campus added"}), 201

@campus_bp.route("/<int:campus_id>", methods=["PUT"])
def update_campus(campus_id):
    name = request.json.get("name")
    manage_academic.update_campus(campus_id, name)
    return jsonify({"message": "Campus updated"})

@campus_bp.route("/<int:campus_id>", methods=["DELETE"])
def delete_campus(campus_id):
    manage_academic.delete_campus(campus_id)
    return jsonify({"message": "Campus deleted"})


@campus_bp.route("/department", methods=["GET"])
def get_departments():
    campus_id = request.args.get("campus_id")
    departments = manage_academic.get_departments(campus_id)
    return jsonify(departments)

@campus_bp.route("/department", methods=["POST"])
def create_department():
    data = request.json
    name = data.get("name")
    campus_id = data.get("campus_id")
    manage_academic.add_department(name, campus_id)
    return jsonify({"message": "Department added"}), 201

@campus_bp.route("/department/<int:department_id>", methods=["PUT"])
def update_department(department_id):
    data = request.json
    name = data.get("name")
    campus_id = data.get("campus_id")
    manage_academic.update_department(department_id, name, campus_id)
    return jsonify({"message": "Department updated"})

@campus_bp.route("/department/<int:department_id>", methods=["DELETE"])
def delete_department(department_id):
    manage_academic.delete_department(department_id)
    return jsonify({"message": "Department deleted"})

@campus_bp.route("/course", methods=["GET"])
def get_courses():
    department_id = request.args.get("department_id")
    courses = manage_academic.get_courses(department_id)
    return jsonify(courses)

@campus_bp.route("/course", methods=["POST"])
def create_course():
    data = request.json
    name = data.get("name")
    major = data.get("major")
    department_id = data.get("department_id")
    manage_academic.add_course(name, major, department_id)
    return jsonify({"message": "Course added"}), 201

@campus_bp.route("/course/<int:course_id>", methods=["PUT"])
def update_course(course_id):
    data = request.json
    name = data.get("name")
    major = data.get("major")
    department_id = data.get("department_id")
    manage_academic.update_course(course_id, name, major, department_id)
    return jsonify({"message": "Course updated"})

@campus_bp.route("/course/<int:course_id>", methods=["DELETE"])
def delete_course(course_id):
    manage_academic.delete_course(course_id)
    return jsonify({"message": "Course deleted"})
