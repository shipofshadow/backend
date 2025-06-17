from flask import Flask, jsonify, request, Blueprint
from db import get_connection

meta_bp = Blueprint('meta', __name__, url_prefix='/api')

@meta_bp.route('/campuses', methods=['GET'])
def get_campuses():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT campus_id, name FROM campuses")
    rows = cursor.fetchall()
    data = [{'id': row['campus_id'], 'name': row['name']} for row in rows]
    cursor.close()
    conn.close()
    return jsonify(data), 200

@meta_bp.route('/departments', methods=['GET'])
def get_departments():
    campus_id = request.args.get('campus_id')
    conn = get_connection()
    cursor = conn.cursor()
    if campus_id:
        cursor.execute("SELECT department_id, name, campus_id FROM departments WHERE campus_id = %s", (campus_id,))
    else:
        cursor.execute("SELECT department_id, name, campus_id FROM departments")
    rows = cursor.fetchall()
    data = [{'id': row['department_id'], 'name': row['name'], 'campus_id': row['campus_id']} for row in rows]
    cursor.close()
    conn.close()
    return jsonify(data), 200

@meta_bp.route('/courses', methods=['GET'])
def get_courses():
    department_id = request.args.get('department_id')
    conn = get_connection()
    cursor = conn.cursor()
    if department_id:
        cursor.execute("SELECT course_id, name, major, department_id FROM courses WHERE department_id = %s", (department_id,))
    else:
        cursor.execute("SELECT course_id, name, major, department_id FROM courses")
    rows = cursor.fetchall()
    data = [{'id': row['course_id'], 'name': row['name'], 'major': row['major'], 'department_id': row['department_id']} for row in rows]
    cursor.close()
    conn.close()
    return jsonify(data), 200
