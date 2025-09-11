from flask import Blueprint, request, jsonify
from services.admin import manage_academic

campus_bp = Blueprint("campus", __name__, url_prefix="/api/campus")

@campus_bp.route("/", methods=["GET"])
def get_campuses():
    """
    Get all campuses.
    ---
    tags:
      - Campus
    responses:
      200:
        description: List of campuses
    """

    campuses = manage_academic.get_campuses()
    return jsonify(campuses)

@campus_bp.route("/", methods=["POST"])
def create_campus():
    """
    Add a new campus.
    ---
    tags:
      - Campus
    parameters:
      - in: body
        name: campus
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
    responses:
      201:
        description: Campus added
    """

    name = request.json.get("name")
    manage_academic.add_campus(name)
    return jsonify({"message": "Campus added"}), 201

@campus_bp.route("/<int:campus_id>", methods=["PUT"])
def update_campus(campus_id):
    """
    Update a campus by ID.
    ---
    tags:
      - Campus
    parameters:
      - in: path
        name: campus_id
        type: integer
        required: true
      - in: body
        name: campus
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
    responses:
      200:
        description: Campus updated
    """

    name = request.json.get("name")
    manage_academic.update_campus(campus_id, name)
    return jsonify({"message": "Campus updated"})

@campus_bp.route("/<int:campus_id>", methods=["DELETE"])
def delete_campus(campus_id):
    """
    Delete a campus by ID.
    ---
    tags:
      - Campus
    parameters:
      - in: path
        name: campus_id
        type: integer
        required: true
    responses:
      200:
        description: Campus deleted
    """

    manage_academic.delete_campus(campus_id)
    return jsonify({"message": "Campus deleted"})


@campus_bp.route("/department", methods=["GET"])
def get_departments():
    """
    Get departments, optionally filtered by campus_id.
    ---
    tags:
      - Department
    parameters:
      - in: query
        name: campus_id
        type: integer
        required: false
    responses:
      200:
        description: List of departments
    """

    campus_id = request.args.get("campus_id")
    departments = manage_academic.get_departments(campus_id)
    return jsonify(departments)

@campus_bp.route("/department", methods=["POST"])
def create_department():
    """
    Add a new department.
    ---
    tags:
      - Department
    parameters:
      - in: body
        name: department
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
            campus_id:
              type: integer
    responses:
      201:
        description: Department added
    """

    data = request.json
    name = data.get("name")
    campus_id = data.get("campus_id")
    manage_academic.add_department(name, campus_id)
    return jsonify({"message": "Department added"}), 201

@campus_bp.route("/department/<int:department_id>", methods=["PUT"])
def update_department(department_id):
    """
    Update a department by ID.
    ---
    tags:
      - Department
    parameters:
      - in: path
        name: department_id
        type: integer
        required: true
      - in: body
        name: department
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
            campus_id:
              type: integer
    responses:
      200:
        description: Department updated
    """

    data = request.json
    name = data.get("name")
    campus_id = data.get("campus_id")
    manage_academic.update_department(department_id, name, campus_id)
    return jsonify({"message": "Department updated"})

@campus_bp.route("/department/<int:department_id>", methods=["DELETE"])
def delete_department(department_id):
    """
    Delete a department by ID.
    ---
    tags:
      - Department
    parameters:
      - in: path
        name: department_id
        type: integer
        required: true
    responses:
      200:
        description: Department deleted
    """

    manage_academic.delete_department(department_id)
    return jsonify({"message": "Department deleted"})

@campus_bp.route("/course", methods=["GET"])
def get_courses():
    """
    Get courses, optionally filtered by department_id.
    ---
    tags:
      - Course
    parameters:
      - in: query
        name: department_id
        type: integer
        required: false
    responses:
      200:
        description: List of courses
    """

    department_id = request.args.get("department_id")
    courses = manage_academic.get_courses(department_id)
    return jsonify(courses)

@campus_bp.route("/course", methods=["POST"])
def create_course():
    """
    Add a new course.
    ---
    tags:
      - Course
    parameters:
      - in: body
        name: course
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
            major:
              type: string
            department_id:
              type: integer
    responses:
      201:
        description: Course added
    """

    data = request.json
    name = data.get("name")
    major = data.get("major")
    department_id = data.get("department_id")
    manage_academic.add_course(name, major, department_id)
    return jsonify({"message": "Course added"}), 201

@campus_bp.route("/course/<int:course_id>", methods=["PUT"])
def update_course(course_id):
    """
    Update a course by ID.
    ---
    tags:
      - Course
    parameters:
      - in: path
        name: course_id
        type: integer
        required: true
      - in: body
        name: course
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
            major:
              type: string
            department_id:
              type: integer
    responses:
      200:
        description: Course updated
    """

    data = request.json
    name = data.get("name")
    major = data.get("major")
    department_id = data.get("department_id")
    manage_academic.update_course(course_id, name, major, department_id)
    return jsonify({"message": "Course updated"})

@campus_bp.route("/course/<int:course_id>", methods=["DELETE"])
def delete_course(course_id):
    """
    Delete a course by ID.
    ---
    tags:
      - Course
    parameters:
      - in: path
        name: course_id
        type: integer
        required: true
    responses:
      200:
        description: Course deleted
    """

    manage_academic.delete_course(course_id)
    return jsonify({"message": "Course deleted"})
