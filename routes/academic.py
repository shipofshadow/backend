from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from services.admin import manage_academic
from utils.decorator import (
    admin_or_faculty_required, 
    admin_or_bitress_required,
    get_user_campus_scope,
    has_campus_access,
    UNRESTRICTED_ROLES,
    ROLE_FACULTY
)

campus_bp = Blueprint("campus", __name__, url_prefix="/api/campus")

@campus_bp.route("/", methods=["GET"])
@jwt_required()
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
    claims = get_jwt()
    role = claims.get("role")
    user_campus_id = claims.get("campus_id")
    
    campuses = manage_academic.get_campuses()
    
    # Faculty users only see their assigned campus
    if role == ROLE_FACULTY and user_campus_id is not None:
        campuses = [c for c in campuses if c.get("id") == user_campus_id]
    
    return jsonify(campuses)

@campus_bp.route("/", methods=["POST"])
@jwt_required()
@admin_or_bitress_required
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
@jwt_required()
@admin_or_bitress_required
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
@jwt_required()
@admin_or_bitress_required
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
@jwt_required()
def get_departments():
    """
    Get departments, optionally filtered by campus_id.
    Faculty users are restricted to their assigned campus.
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
    claims = get_jwt()
    role = claims.get("role")
    user_campus_id = claims.get("campus_id")
    
    campus_id = request.args.get("campus_id")
    
    # Faculty users are restricted to their campus
    if role == ROLE_FACULTY and user_campus_id is not None:
        # Override campus_id filter to user's campus
        campus_id = user_campus_id
    
    departments = manage_academic.get_departments(campus_id)
    return jsonify(departments)

@campus_bp.route("/department", methods=["POST"])
@jwt_required()
@admin_or_faculty_required
def create_department():
    """
    Add a new department.
    Faculty users can only add departments to their assigned campus.
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
      403:
        description: Campus scope violation
    """
    claims = get_jwt()
    role = claims.get("role")
    user_campus_id = claims.get("campus_id")

    data = request.json
    name = data.get("name")
    campus_id = data.get("campus_id")
    
    # Faculty users can only create departments in their campus
    if role == ROLE_FACULTY:
        if user_campus_id is None:
            return jsonify({"error": "Faculty user must have a campus assignment"}), 403
        if campus_id is not None and int(campus_id) != user_campus_id:
            return jsonify({"error": "Access denied: campus scope violation"}), 403
        campus_id = user_campus_id
    
    manage_academic.add_department(name, campus_id)
    return jsonify({"message": "Department added"}), 201

@campus_bp.route("/department/<int:department_id>", methods=["PUT"])
@jwt_required()
@admin_or_faculty_required
def update_department(department_id):
    """
    Update a department by ID.
    Faculty users can only update departments in their assigned campus.
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
      403:
        description: Campus scope violation
    """
    claims = get_jwt()
    role = claims.get("role")
    user_campus_id = claims.get("campus_id")

    data = request.json
    name = data.get("name")
    campus_id = data.get("campus_id")
    
    # Faculty users can only update departments in their campus
    if role == ROLE_FACULTY:
        if user_campus_id is None:
            return jsonify({"error": "Faculty user must have a campus assignment"}), 403
        
        # Check if department belongs to user's campus
        departments = manage_academic.get_departments(user_campus_id)
        dept_ids = [d['id'] for d in departments]
        if department_id not in dept_ids:
            return jsonify({"error": "Access denied: campus scope violation"}), 403
        
        # Force campus_id to user's campus
        campus_id = user_campus_id
    
    manage_academic.update_department(department_id, name, campus_id)
    return jsonify({"message": "Department updated"})

@campus_bp.route("/department/<int:department_id>", methods=["DELETE"])
@jwt_required()
@admin_or_faculty_required
def delete_department(department_id):
    """
    Delete a department by ID.
    Faculty users can only delete departments in their assigned campus.
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
      403:
        description: Campus scope violation
    """
    claims = get_jwt()
    role = claims.get("role")
    user_campus_id = claims.get("campus_id")
    
    # Faculty users can only delete departments in their campus
    if role == ROLE_FACULTY:
        if user_campus_id is None:
            return jsonify({"error": "Faculty user must have a campus assignment"}), 403
        
        # Check if department belongs to user's campus
        departments = manage_academic.get_departments(user_campus_id)
        dept_ids = [d['id'] for d in departments]
        if department_id not in dept_ids:
            return jsonify({"error": "Access denied: campus scope violation"}), 403

    manage_academic.delete_department(department_id)
    return jsonify({"message": "Department deleted"})

@campus_bp.route("/course", methods=["GET"])
@jwt_required()
def get_courses():
    """
    Get courses, optionally filtered by department_id.
    Faculty users are restricted to courses within their campus.
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
    claims = get_jwt()
    role = claims.get("role")
    user_campus_id = claims.get("campus_id")

    department_id = request.args.get("department_id")
    courses = manage_academic.get_courses(department_id)
    
    # Faculty users only see courses from their campus
    if role == ROLE_FACULTY and user_campus_id is not None:
        courses = [c for c in courses if c.get("campus_id") == user_campus_id]
    
    return jsonify(courses)

@campus_bp.route("/course", methods=["POST"])
@jwt_required()
@admin_or_faculty_required
def create_course():
    """
    Add a new course.
    Faculty users can only add courses to departments in their campus.
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
      403:
        description: Campus scope violation
    """
    claims = get_jwt()
    role = claims.get("role")
    user_campus_id = claims.get("campus_id")

    data = request.json
    name = data.get("name")
    major = data.get("major")
    department_id = data.get("department_id")
    
    # Faculty users can only create courses in their campus departments
    if role == ROLE_FACULTY:
        if user_campus_id is None:
            return jsonify({"error": "Faculty user must have a campus assignment"}), 403
        
        # Check if department belongs to user's campus
        departments = manage_academic.get_departments(user_campus_id)
        dept_ids = [d['id'] for d in departments]
        if department_id not in dept_ids:
            return jsonify({"error": "Access denied: campus scope violation"}), 403
    
    manage_academic.add_course(name, major, department_id)
    return jsonify({"message": "Course added"}), 201

@campus_bp.route("/course/<int:course_id>", methods=["PUT"])
@jwt_required()
@admin_or_faculty_required
def update_course(course_id):
    """
    Update a course by ID.
    Faculty users can only update courses in their campus.
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
      403:
        description: Campus scope violation
    """
    claims = get_jwt()
    role = claims.get("role")
    user_campus_id = claims.get("campus_id")

    data = request.json
    name = data.get("name")
    major = data.get("major")
    department_id = data.get("department_id")
    
    # Faculty users can only update courses in their campus
    if role == ROLE_FACULTY:
        if user_campus_id is None:
            return jsonify({"error": "Faculty user must have a campus assignment"}), 403
        
        # Check if course belongs to user's campus (using efficient single lookup)
        course = manage_academic.get_course_by_id(course_id)
        if course is None or course.get('campus_id') != user_campus_id:
            return jsonify({"error": "Access denied: campus scope violation"}), 403
        
        # Check if target department belongs to user's campus
        departments = manage_academic.get_departments(user_campus_id)
        dept_ids = [d['id'] for d in departments]
        if department_id not in dept_ids:
            return jsonify({"error": "Access denied: campus scope violation"}), 403
    
    manage_academic.update_course(course_id, name, major, department_id)
    return jsonify({"message": "Course updated"})

@campus_bp.route("/course/<int:course_id>", methods=["DELETE"])
@jwt_required()
@admin_or_faculty_required
def delete_course(course_id):
    """
    Delete a course by ID.
    Faculty users can only delete courses in their campus.
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
      403:
        description: Campus scope violation
    """
    claims = get_jwt()
    role = claims.get("role")
    user_campus_id = claims.get("campus_id")
    
    # Faculty users can only delete courses in their campus
    if role == ROLE_FACULTY:
        if user_campus_id is None:
            return jsonify({"error": "Faculty user must have a campus assignment"}), 403
        
        # Check if course belongs to user's campus (using efficient single lookup)
        course = manage_academic.get_course_by_id(course_id)
        if course is None or course.get('campus_id') != user_campus_id:
            return jsonify({"error": "Access denied: campus scope violation"}), 403

    manage_academic.delete_course(course_id)
    return jsonify({"message": "Course deleted"})
