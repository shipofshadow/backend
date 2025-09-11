from flask import jsonify, request, Blueprint
from storage import get_connection
from services.admin.manage_periods import get_active_period
from services.meta.fuzzy_logic import FuzzyEligibilitySystem
import logging

meta_bp = Blueprint('meta', __name__, url_prefix='/api')

# Initialize fuzzy system with connection function (not connection object)
fuzzy = FuzzyEligibilitySystem(get_connection)

@meta_bp.route('/evaluate', methods=['POST'])
def evaluate():
    """
    Evaluate student eligibility using fuzzy logic.
    ---
    tags:
      - Fuzzy Logic
    parameters:
      - in: body
        name: payload
        required: true
        schema:
          type: object
          properties:
            gwa:
              type: number
              example: 1.75
            income:
              type: number
              example: 15000
    responses:
      200:
        description: Eligibility result
      400:
        description: Invalid input
      500:
        description: Internal server error
    """
    try:
        # Validate request
        if not request.is_json:
            return jsonify({
                "success": False,
                "error": "Content-Type must be application/json"
            }), 400

        data = request.get_json()

        # Validate required fields
        gwa = data.get("gwa")
        income = data.get("income")

        if gwa is None or income is None:
            return jsonify({
                "success": False,
                "error": "Missing required fields: gwa and income"
            }), 400

        # Validate data types and ranges
        try:
            gwa = float(gwa)
            income = float(income)
        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "error": "gwa and income must be numeric values"
            }), 400

        # Validate GWA range (Philippine grading system: 1.0 = highest, 5.0 = lowest)
        if gwa < 1.0 or gwa > 5.0:
            return jsonify({
                "success": False,
                "error": "GWA must be between 1.0 and 5.0"
            }), 400

        # Validate income range
        if income < 0:
            return jsonify({
                "success": False,
                "error": "Income must be non-negative"
            }), 400

        # Run fuzzy logic evaluation
        result = fuzzy.evaluate(gwa, income)

        # Format response
        response = {
            "success": True,
            "gwa": gwa,
            "income": income,
            "score": round(result["score"], 4),
            "classification": result["classification"],
            "memberships": {
                "gwa": {k: round(v, 4) for k, v in result["memberships"]["gwa"].items()},
                "income": {k: round(v, 4) for k, v in result["memberships"]["income"].items()}
            }
        }

        # Include fired rules if available
        if "fired_rules" in result:
            response["fired_rules"] = result["fired_rules"]

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Error in fuzzy evaluation: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500


@meta_bp.route('/fuzzy-system/reload', methods=['POST'])
def reload_fuzzy_system():
    """
    Reload fuzzy system configuration from database.
    ---
    tags:
      - Fuzzy Logic
    responses:
      200:
        description: Reload successful
      500:
        description: Failed to reload fuzzy system
    """

    try:
        fuzzy.reload_from_database()

        return jsonify({
            "success": True,
            "message": "Fuzzy system reloaded successfully",
            "rules_count": len(fuzzy.rules),
            "variables": list(fuzzy.membership_functions.keys())
        }), 200

    except Exception as e:
        logging.error(f"Error reloading fuzzy system: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to reload fuzzy system"
        }), 500


@meta_bp.route('/evaluate-batch', methods=['POST'])
def evaluate_batch():
    """
    Evaluate multiple students at once.
    ---
    tags:
      - Fuzzy Logic
    parameters:
      - in: body
        name: evaluations
        required: true
        schema:
          type: object
          properties:
            evaluations:
              type: array
              items:
                type: object
                properties:
                  student_id:
                    type: integer
                  gwa:
                    type: number
                  income:
                    type: number
    responses:
      200:
        description: Batch evaluation results
      400:
        description: Invalid input
      500:
        description: Internal server error
    """
    try:
        if not request.is_json:
            return jsonify({
                "success": False,
                "error": "Content-Type must be application/json"
            }), 400

        data = request.get_json()
        evaluations = data.get("evaluations", [])

        if not evaluations or not isinstance(evaluations, list):
            return jsonify({
                "success": False,
                "error": "evaluations field must be a non-empty array"
            }), 400

        results = []
        errors = []

        for i, eval_data in enumerate(evaluations):
            try:
                student_id = eval_data.get("student_id")
                gwa = float(eval_data.get("gwa", 0))
                income = float(eval_data.get("income", 0))

                # Validate ranges
                if gwa < 1.0 or gwa > 5.0:
                    errors.append(f"Student {student_id}: GWA must be between 1.0 and 5.0")
                    continue

                if income < 0:
                    errors.append(f"Student {student_id}: Income must be non-negative")
                    continue

                # Evaluate
                result = fuzzy.evaluate(gwa, income)

                results.append({
                    "student_id": student_id,
                    "gwa": gwa,
                    "income": income,
                    "score": round(result["score"], 4),
                    "classification": result["classification"]
                })

            except Exception as e:
                errors.append(f"Student {eval_data.get('student_id', i)}: {str(e)}")

        response = {
            "success": True,
            "results": results,
            "processed": len(results),
            "total": len(evaluations)
        }

        if errors:
            response["errors"] = errors

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Error in batch evaluation: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500

# Error handlers for this blueprint
@meta_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "Endpoint not found"
    }), 404


@meta_bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "success": False,
        "error": "Method not allowed"
    }), 405

@meta_bp.route('/semesters', methods=['GET'])
def get_semesters():
    """
    Get semesters, optionally filtered by semester_id or academic_year_id.
    ---
    tags:
      - Academic
    parameters:
      - name: semester_id
        in: query
        type: integer
        required: false
      - name: academic_year_id
        in: query
        type: integer
        required: false
    responses:
      200:
        description: Semester information
      404:
        description: Not found
    """

    semester_id = request.args.get('semester_id', type=int)
    academic_year_id = request.args.get('academic_year_id', type=int)

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            s.id AS semester_id,
            s.name AS semester_name,
            s.is_active,
            ay.id AS academic_year_id,
            ay.year_start,
            ay.year_end
        FROM semesters s
        JOIN academic_years ay ON ay.id = s.academic_year_id
        WHERE s.deleted_at IS NULL
    """

    params = []
    if semester_id:
        query += " AND s.id = %s"
        params.append(semester_id)

    if academic_year_id:
        query += " AND ay.id = %s"
        params.append(academic_year_id)

    query += " ORDER BY ay.year_start ASC, s.name ASC"

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    semesters = []
    for row in rows:
        semesters.append({
            "id": row["semester_id"],
            "name": row["semester_name"],
            "is_active": row["is_active"],
            "academic_year": {
                "id": row["academic_year_id"],
                "year_start": row["year_start"],
                "year_end": row["year_end"]
            }
        })

    cursor.close()
    conn.close()

    if semester_id and len(semesters) == 1:
        return jsonify(semesters[0]), 200

    return jsonify(semesters), 200

@meta_bp.route('/active-academic-term', methods=['GET'])
def current_academic_year():
    """
    Get the currently active academic year and semester.
    ---
    tags:
      - Academic
    responses:
      200:
        description: Active academic term
      404:
        description: No active academic term found
    """

    data = get_active_period()
    if data:
        formatted = f"AY {data['year_start']}-{data['year_end']} - {data['semester_name']}"
        return jsonify({
            "academic_year": f"{data['year_start']}-{data['year_end']}",
            "semester": data['semester_name'],
            "academic_year_id": data['academic_year_id'],
            "semester_id": data['semester_id'],
            "formatted": formatted
        })
    else:
        return jsonify({"error": "No active academic year or semester found"}), 404


@meta_bp.route('/campuses', methods=['GET'])
def get_campuses():
    """
    Get all campuses.
    ---
    tags:
      - Meta
    responses:
      200:
        description: List of campuses
    """

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
    """
    Get departments, optionally filtered by campus_id.
    ---
    tags:
      - Meta
    parameters:
      - name: campus_id
        in: query
        type: integer
        required: false
    responses:
      200:
        description: List of departments
    """

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
    """
    Get courses, optionally filtered by department_id.
    ---
    tags:
      - Meta
    parameters:
      - name: department_id
        in: query
        type: integer
        required: false
    responses:
      200:
        description: List of courses
    """

    department_id = request.args.get('department_id')
    conn = get_connection()
    cursor = conn.cursor()
    if department_id:
        cursor.execute("SELECT course_id, name, major, department_id FROM courses WHERE department_id = %s",
                       (department_id,))
    else:
        cursor.execute("SELECT course_id, name, major, department_id FROM courses")
    rows = cursor.fetchall()
    data = [{'id': row['course_id'], 'name': row['name'], 'major': row['major'], 'department_id': row['department_id']}
            for row in rows]
    cursor.close()
    conn.close()
    return jsonify(data), 200
