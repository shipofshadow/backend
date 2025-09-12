import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.application_service import base_applicant_query, fetch_grades_by_application_ids
from services.meta.fuzzy_logic import FuzzyEligibilitySystem

from storage import get_connection
from utils.utils import smart_detect_flags

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

evaluations_bp = Blueprint('evaluations', __name__, url_prefix='/api/evaluations')
fuzzy = FuzzyEligibilitySystem(get_connection)

# Constants for better maintainability
DEFAULT_CONFIG = {
    "min_gwa": None,
    "max_gwa": None,
    "min_income": None,
    "max_income": None,
    "priorities": {
        "must_be_ofw": False,
        "prefer_farmers_child": False,
        "require_ip": False,
        "prefer_pwd": False
    },
    "preferred_course_ids": [],
    "preferred_department_ids": [],
    "preferred_campus_ids": [],
    "preferred_year_levels": [],
    "min_units_enrolled": None,
    "max_units_enrolled": None,
    "priority": []
}

BONUS_VALUES = {
    "prefer_farmers_child": 0.1,
    "prefer_pwd": 0.1,
    "prefer_ip": 0.05,
    "preferred_course": 0.05,
    "preferred_department": 0.03,
    "preferred_campus": 0.02
}


# ============================================
#       UTILITY FUNCTIONS
# ============================================


def safe_json_parse(config_str: str, default: Dict = None) -> Dict:
    """Safely parse JSON configuration with fallback"""
    if not config_str:
        return default or DEFAULT_CONFIG.copy()

    try:
        config = json.loads(config_str)
        if isinstance(config, str):
            config = json.loads(config)

        # Merge with default config to ensure all keys exist
        merged_config = DEFAULT_CONFIG.copy()
        if isinstance(config, dict):
            merged_config.update(config)
            if "priorities" in config:
                merged_config["priorities"].update(config["priorities"])

        return merged_config
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"JSON parsing error: {e} | Raw config: {config_str!r}")
        return default or DEFAULT_CONFIG.copy()


def extract_applicant_flags(applicant: Dict) -> Dict[str, Any]:
    """Extract and process applicant flags and data"""
    flags = smart_detect_flags(
        applicant.get("father_occupation", ""),
        applicant.get("mother_occupation", ""),
    )

    total_income = (applicant.get("father_income") or 0) + (applicant.get("mother_income") or 0)

    return {
        "is_ofw": flags["is_ofw"],
        "is_farmers_child": flags["is_farmers_child"],
        "is_ip": applicant.get("ip_affiliation") not in ("None", "N/A", None, ""),
        "is_pwd": False,  # This would need to be determined from applicant data
        "course_id": applicant.get("course_id"),
        "department_id": applicant.get("department_id"),
        "campus_id": applicant.get("campus_id"),
        "year_level": applicant.get("year_level"),
        "total_income": total_income
    }


def validate_evaluation_data(data: Dict) -> Tuple[bool, str]:
    """Validate evaluation input data"""
    required_fields = ["gwa", "income", "total_units"]

    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"

        value = data[field]
        if value is None or (isinstance(value, str) and not value.strip()):
            return False, f"Field '{field}' cannot be empty"

        try:
            float(value)
        except (ValueError, TypeError):
            return False, f"Field '{field}' must be a valid number"

    # Validate ranges
    gwa = float(data["gwa"])
    if not (0.0 <= gwa <= 5.0):
        return False, "GWA must be between 0.0 and 5.0"

    income = float(data["income"])
    if income < 0:
        return False, "Income cannot be negative"

    total_units = float(data["total_units"])
    if total_units < 0:
        return False, "Total units cannot be negative"

    return True, ""


# ============================================
#       GET THE EVALUATEES
# ============================================
@evaluations_bp.route('/', methods=['GET'])
@jwt_required()
def fetch_evaluatees():
    """
     Fetch all applicants eligible for evaluation
     ---
     tags:
       - Evaluations
     responses:
       200:
         description: List of applicants with evaluation-relevant details
         schema:
           type: array
           items:
             type: object
             properties:
               id:
                 type: integer
               application_id:
                 type: integer
               user_id:
                 type: integer
               name:
                 type: string
               grades:
                 type: array
                 items:
                   type: object
               family_income:
                 type: number
               status:
                 type: string
               is_ofw:
                 type: boolean
               is_farmers_child:
                 type: boolean
               is_ip:
                 type: boolean
               course_id:
                 type: integer
               department_id:
                 type: integer
               campus_id:
                 type: integer
               year_level:
                 type: string
       500:
         description: Internal server error
     """
    try:
        connection = get_connection()
        cursor = connection.cursor()

        query = base_applicant_query() + """
          WHERE applications.deleted_at IS NULL 
          AND semesters.is_active = 1 
          ORDER BY applications.status, applications.created_at DESC
        """

        cursor.execute(query)
        applicants = cursor.fetchall()

        if not applicants:
            return jsonify([])

        application_ids = [app["id"] for app in applicants]
        grades_map = fetch_grades_by_application_ids(cursor, application_ids)

        results = []
        for app in applicants:
            app["grades"] = grades_map.get(app["id"], [])
            flags_data = extract_applicant_flags(app)

            result = {
                "id": app["id"],
                "application_id": app["id"],
                "user_id": app['user_id'],
                "name": f"{app['first_name']} {app['last_name']}",
                "grades": app.get("grades", []),
                "family_income": flags_data["total_income"],
                "status": app.get("status"),
                "is_ofw": flags_data["is_ofw"],
                "is_farmers_child": flags_data["is_farmers_child"],
                "is_ip": flags_data["is_ip"],
                "course_id": flags_data["course_id"],
                "department_id": flags_data["department_id"],
                "campus_id": flags_data["campus_id"],
                "year_level": flags_data["year_level"],
            }
            results.append(result)

        return jsonify(results)

    except Exception as e:
        logger.error(f"Error fetching evaluatees: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


# ============================================
#       EVALUATE
# ============================================
@evaluations_bp.route('/<int:application_id>/evaluate', methods=['POST'])
@jwt_required()
def evaluate(application_id):
    """
    Evaluate an application using fuzzy logic
    ---
    tags:
      - Evaluations
    parameters:
      - name: application_id
        in: path
        type: integer
        required: true
        description: ID of the application to evaluate
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            gwa:
              type: number
              description: Applicant's GWA
            income:
              type: number
              description: Family income
            total_units:
              type: integer
              description: Total enrolled units
          required:
            - gwa
            - income
            - total_units
    responses:
      200:
        description: Evaluation result
        schema:
          type: object
          properties:
            application_id:
              type: integer
            score:
              type: number
            classification:
              type: string
            gwa:
              type: number
      400:
        description: Invalid input data
      404:
        description: Application not found
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()

        # Validate input data
        is_valid, error_msg = validate_evaluation_data(data)
        if not is_valid:
            return jsonify({"error": error_msg}), 400

        gwa = float(data.get("gwa"))
        income = float(data.get("income"))
        total_units = int(data.get("total_units"))

        connection = get_connection()
        cursor = connection.cursor()

        # Check if application exists
        cursor.execute("SELECT id FROM applications WHERE id = %s AND deleted_at IS NULL", (application_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Application not found"}), 404

        # Perform fuzzy logic evaluation
        result = fuzzy.evaluate(gwa, income)
        score = round(result["score"], 4)
        classification = result["classification"]

        # Insert or update evaluation
        cursor.execute("""
                       INSERT INTO evaluations (application_id, gwa, total_units, income, score, classification,
                                                created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                       ON DUPLICATE KEY UPDATE gwa            = VALUES(gwa),
                                               income         = VALUES(income),
                                               score          = VALUES(score),
                                               total_units    = VALUES(total_units),
                                               classification = VALUES(classification),
                                               updated_at     = NOW()
                       """, (application_id, gwa, total_units, income, score, classification))

        connection.commit()

        logger.info(f"Application {application_id} evaluated successfully with score {score}")

        return jsonify({
            "application_id": int(application_id),
            "score": score,
            "classification": classification,
            "gwa": gwa,
        })

    except ValueError as e:
        logger.warning(f"Invalid data for application {application_id}: {str(e)}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        logger.error(f"Error evaluating application {application_id}: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


# ============================================
#       FETCH THE EVALUATION RESULTS
# ============================================
@evaluations_bp.route('/<int:application_id>/results', methods=['GET'])
@jwt_required()
def get_evaluation_result(application_id):
    """
    Get evaluation results for a specific application
    ---
    tags:
      - Evaluations
    parameters:
      - name: application_id
        in: path
        type: integer
        required: true
        description: ID of the application
    responses:
      200:
        description: Evaluation results
        schema:
          type: object
          properties:
            application_id:
              type: integer
            gwa:
              type: number
            score:
              type: number
            classification:
              type: string
      404:
        description: Evaluation not found
      500:
        description: Internal server error
    """
    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
                       SELECT id, application_id, gwa, score, classification, created_at
                       FROM evaluations
                       WHERE application_id = %s
                         AND deleted_at IS NULL
                       """, (application_id,))

        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Evaluation not found"}), 404

        return jsonify({
            "application_id": int(row["application_id"]),
            "gwa": float(row["gwa"]),
            "score": float(row["score"]),
            "classification": row["classification"],
        })

    except Exception as e:
        logger.error(f"Error fetching evaluation results for application {application_id}: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


# ================================================================
#       SCHOLARSHIP RECOMMENDATION ENGINE
# ================================================================
@evaluations_bp.route('/<int:application_id>/recommend', methods=['POST'])
@jwt_required()
def recommend(application_id):

    """
    Generate scholarship recommendations for an application
    ---
    tags:
      - Recommendations
    parameters:
      - name: application_id
        in: path
        type: integer
        required: true
        description: ID of the application
    responses:
      200:
        description: List of recommended scholarships
        schema:
          type: array
          items:
            type: object
            properties:
              scholarship_id:
                type: integer
              scholarship_name:
                type: string
              priority_met:
                type: boolean
              score:
                type: number
      400:
        description: Application must be evaluated first
      404:
        description: Application not found
      500:
        description: Internal server error
    """
    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Fetch applicant data
        cursor.execute(base_applicant_query() + " WHERE semesters.is_active = 1 AND applications.id = %s",
                       (application_id,))
        applicant = cursor.fetchone()

        if not applicant:
            return jsonify({"error": "Application not found"}), 404

        # Extract applicant characteristics
        applicant_data = extract_applicant_flags(applicant)

        # Get evaluation results
        cursor.execute("""
                       SELECT score, classification, gwa, income, total_units
                       FROM evaluations
                       WHERE application_id = %s
                         AND deleted_at IS NULL
                       """, (application_id,))

        evaluation_result = cursor.fetchone()
        if not evaluation_result:
            return jsonify({"error": "Application must be evaluated first"}), 400

        evaluation_data = {
            "score": evaluation_result["score"],
            "classification": evaluation_result["classification"],
            "gwa": evaluation_result["gwa"],
            "income": evaluation_result["income"],
            "units_enrolled": evaluation_result["total_units"]
        }

        # Generate recommendations
        recommendations = generate_scholarship_recommendations(
            cursor, application_id, applicant_data, evaluation_data
        )

        # Store recommendations in database
        store_recommendations(cursor, application_id, recommendations)

        # Mark recommendations as generated
        cursor.execute("""
                       UPDATE evaluations
                       SET recommendations_generated = %s,
                           updated_at                = NOW()
                       WHERE application_id = %s
                       """, (len(recommendations), application_id,))

        connection.commit()

        logger.info(f"Generated {len(recommendations)} recommendations for application {application_id}")

        return jsonify(recommendations)

    except Exception as e:
        logger.error(f"Error generating recommendations for application {application_id}: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


def generate_scholarship_recommendations(cursor, application_id: int, applicant_data: Dict, evaluation_data: Dict) -> \
List[Dict]:
    """Generate scholarship recommendations based on applicant data and evaluation"""
    cursor.execute("""
                   SELECT s.id, s.name, s.description, sr.config, s.grant_amount
                   FROM scholarships s
                            JOIN scholarship_rules sr ON s.id = sr.scholarship_id
                   WHERE s.is_active = 1
                     AND s.deleted_at IS NULL
                   ORDER BY s.name
                   """)

    active_scholarships = cursor.fetchall()
    recommendations = []

    for scholarship in active_scholarships:
        scholarship_id = scholarship['id']
        config = safe_json_parse(scholarship['config'])

        # Check eligibility
        eligibility_check = check_scholarship_eligibility_enhanced(
            evaluation_data, applicant_data, config
        )

        # Check priority requirements (hard filters)
        if not check_priority_requirements(applicant_data, config):
            continue

        if eligibility_check["eligible"]:
            # Calculate scholarship-specific score
            scholarship_score = calculate_scholarship_score_enhanced(
                evaluation_data["score"], config, applicant_data
            )

            recommendation = {
                "scholarship_id": scholarship_id,
                "name": scholarship['name'],
                "description": scholarship['description'],
                "amount": scholarship['grant_amount'],
                "score": scholarship_score,
                "classification": evaluation_data["classification"],
                "reasons": eligibility_check["reasons"]
            }
            recommendations.append(recommendation)

    # Sort by score (descending) then by name (ascending) for consistency
    recommendations.sort(key=lambda x: (-x["score"], x["name"]))

    return recommendations


def check_priority_requirements(applicant_data: Dict, config: Dict) -> bool:
    """Check if applicant meets required priority conditions (hard filters)"""
    priorities = config.get("priorities", {})
    priority_list = config.get("priority", [])

    # Check must_be_ofw requirement
    if priorities.get("must_be_ofw", False) and not applicant_data["is_ofw"]:
        return False

    # Check require_ip requirement
    if priorities.get("require_ip", False) and not applicant_data["is_ip"]:
        return False

    # Check priority list requirements
    for priority in priority_list:
        if priority == "ofw" and not applicant_data["is_ofw"]:
            return False
        elif priority == "farmers" and not applicant_data["is_farmers_child"]:
            return False
        elif priority == "pwd" and not applicant_data["is_pwd"]:
            return False
        elif priority == "ip" and not applicant_data["is_ip"]:
            return False

    return True


def check_scholarship_eligibility_enhanced(evaluation_data: Dict, applicant_data: Dict, config: Dict) -> Dict:
    """Enhanced eligibility checking with better reason tracking"""
    reasons = []
    eligible = True

    gwa = evaluation_data["gwa"]
    income = evaluation_data["income"]
    units_enrolled = evaluation_data["units_enrolled"]

    # GWA requirements
    min_gwa = config.get("min_gwa")
    max_gwa = config.get("max_gwa")

    if min_gwa is not None and gwa < min_gwa:
        eligible = False
        reasons.append(f"GWA {gwa} below minimum {min_gwa}")
    elif max_gwa is not None and gwa > max_gwa:
        eligible = False
        reasons.append(f"GWA {gwa} above maximum {max_gwa}")
    else:
        gwa_range = ""
        if min_gwa is not None and max_gwa is not None:
            gwa_range = f" (range: {min_gwa}-{max_gwa})"
        elif min_gwa is not None:
            gwa_range = f" (min: {min_gwa})"
        elif max_gwa is not None:
            gwa_range = f" (max: {max_gwa})"
        reasons.append(f"GWA {gwa} meets requirements{gwa_range}")

    # Income requirements
    min_income = config.get("min_income")
    max_income = config.get("max_income")

    if min_income is not None and income < min_income:
        eligible = False
        reasons.append(f"Income {income:,.2f} below minimum {min_income:,.2f}")
    elif max_income is not None and income > max_income:
        eligible = False
        reasons.append(f"Income {income:,.2f} above maximum {max_income:,.2f}")
    else:
        income_range = ""
        if min_income is not None and max_income is not None:
            income_range = f" (range: {min_income:,.2f}-{max_income:,.2f})"
        elif min_income is not None:
            income_range = f" (min: {min_income:,.2f})"
        elif max_income is not None:
            income_range = f" (max: {max_income:,.2f})"
        reasons.append(f"Income {income:,.2f} meets requirements{income_range}")

    # Units enrolled requirements
    min_units = config.get("min_units_enrolled")
    max_units = config.get("max_units_enrolled")

    if units_enrolled is not None:
        if min_units is not None and units_enrolled < min_units:
            eligible = False
            reasons.append(f"Units enrolled {units_enrolled} below minimum {min_units}")
        elif max_units is not None and units_enrolled > max_units:
            eligible = False
            reasons.append(f"Units enrolled {units_enrolled} above maximum {max_units}")
        elif min_units is not None or max_units is not None:
            units_range = ""
            if min_units is not None and max_units is not None:
                units_range = f" (range: {min_units}-{max_units})"
            elif min_units is not None:
                units_range = f" (min: {min_units})"
            elif max_units is not None:
                units_range = f" (max: {max_units})"
            reasons.append(f"Units enrolled {units_enrolled} meets requirements{units_range}")

    # Priority requirements (already checked in check_priority_requirements)
    priorities = config.get("priorities", {})

    if priorities.get("must_be_ofw") and applicant_data["is_ofw"]:
        reasons.append("OFW requirement met")

    if priorities.get("require_ip") and applicant_data["is_ip"]:
        reasons.append("Indigenous Person requirement met")

    # Preferred criteria (adds context but doesn't affect eligibility)
    if priorities.get("prefer_farmers_child") and applicant_data["is_farmers_child"]:
        reasons.append("Farmer's child (preferred criteria)")

    if priorities.get("prefer_pwd") and applicant_data["is_pwd"]:
        reasons.append("PWD (preferred criteria)")

    return {
        "eligible": eligible,
        "reasons": reasons
    }


def calculate_scholarship_score_enhanced(base_score: float, config: Dict, applicant_data: Dict) -> float:
    """Enhanced scholarship-specific score calculation with configurable bonuses"""
    score = float(base_score)
    priorities = config.get("priorities", {})

    # Apply preference bonuses
    if priorities.get("prefer_farmers_child") and applicant_data["is_farmers_child"]:
        score += BONUS_VALUES["prefer_farmers_child"]

    if priorities.get("prefer_pwd") and applicant_data["is_pwd"]:
        score += BONUS_VALUES["prefer_pwd"]

    if priorities.get("prefer_ip") and applicant_data["is_ip"]:
        score += BONUS_VALUES["prefer_ip"]

    # Course, department, campus preferences
    preferred_courses = config.get("preferred_course_ids", [])
    if preferred_courses and applicant_data["course_id"] in preferred_courses:
        score += BONUS_VALUES["preferred_course"]

    preferred_departments = config.get("preferred_department_ids", [])
    if preferred_departments and applicant_data["department_id"] in preferred_departments:
        score += BONUS_VALUES["preferred_department"]

    preferred_campuses = config.get("preferred_campus_ids", [])
    if preferred_campuses and applicant_data["campus_id"] in preferred_campuses:
        score += BONUS_VALUES["preferred_campus"]

    return min(round(score, 4), 1.0)


def store_recommendations(cursor, application_id: int, recommendations: List[Dict]):
    """Store recommendations in database with batch operations"""
    # Clear existing recommendations
    cursor.execute("DELETE FROM recommended_scholarships WHERE application_id = %s", (application_id,))

    if not recommendations:
        return

    # Batch insert recommendations
    recommendation_data = []
    for rec in recommendations:
        recommendation_data.append((
            application_id,
            rec["scholarship_id"],
            rec["score"],
            rec["classification"],
            json.dumps(rec["reasons"])
        ))

    cursor.executemany("""
                       INSERT INTO recommended_scholarships
                       (application_id, scholarship_id, score, classification, eligibility_reasons, created_at,
                        updated_at)
                       VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                       """, recommendation_data)


# ==========================================
# PHASE 2: RECOMMENDATION REVIEW
# ==========================================
@evaluations_bp.route("/<int:application_id>/recommendations", methods=["GET"])
@jwt_required()
def get_recommendations(application_id):
    """Get all scholarship recommendations for an applicant"""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
                       SELECT rs.scholarship_id,
                              s.name AS scholarship_name,
                              s.description,
                              s.grant_amount,
                              rs.score,
                              rs.classification,
                              rs.eligibility_reasons
                       FROM recommended_scholarships rs
                                JOIN scholarships s ON rs.scholarship_id = s.id
                       WHERE rs.application_id = %s
                       ORDER BY rs.score DESC, rs.created_at DESC
                       """, (application_id,))

        recommendations = []
        for row in cursor.fetchall():
            recommendations.append({
                "scholarship_id": row["scholarship_id"],
                "name": row["scholarship_name"],
                "description": row["description"],
                "amount": f"{row['grant_amount']:.2f}" if row["grant_amount"] is not None else "0.00",
                "score": row["score"],
                "classification": row["classification"],
                "reasons": json.loads(row["eligibility_reasons"]) if row["eligibility_reasons"] else []
            })

        return jsonify(recommendations), 200

    except Exception as e:
        logger.error(f"Error fetching recommendations for application {application_id}: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


@evaluations_bp.route("/<int:application_id>/selection", methods=["GET"])
@jwt_required()
def get_selections(application_id):
    """Get final scholarship selection for an applicant"""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
                       SELECT ss.id,
                              ss.scholarship_id,
                              s.name   AS scholarship_name,
                              ss.selection_reason,
                              ss.status,
                              ss.awarded_amount,
                              ss.created_at,
                              ss.updated_at,
                              er.score as final_score
                       FROM scholarship_selections ss
                                JOIN scholarships s ON ss.scholarship_id = s.id
                                LEFT JOIN evaluations er ON ss.application_id = er.application_id
                       WHERE ss.application_id = %s
                         AND ss.status = 'selected'
                       ORDER BY ss.created_at DESC
                       LIMIT 1
                       """, (application_id,))

        row = cursor.fetchone()

        if not row:
            return jsonify(None), 200

        selection = {
            "id": row["id"],
            "scholarship_id": row["scholarship_id"],
            "scholarship_name": row["scholarship_name"],
            "selection_reason": row["selection_reason"],
            "status": row["status"],
            "awarded_amount": float(row["awarded_amount"]) if row["awarded_amount"] else None,
            "selected_date": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            "final_score": float(row["final_score"]) if row["final_score"] else None
        }

        return jsonify(selection), 200

    except Exception as e:
        logger.error(f"Error fetching selection for application {application_id}: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


# ==========================================
# PHASE 3: FINAL SELECTION
# ==========================================
@evaluations_bp.route("/<int:application_id>/select", methods=["POST"])
@jwt_required()
def select_scholarship(application_id):
    """Select final scholarship for an applicant"""
    try:
        data = request.get_json()
        scholarship_id = data.get('scholarship_id')
        awarded_amount = data.get('awarded_amount')
        selection_reason = data.get('selection_reason', '')

        if not scholarship_id:
            return jsonify({"error": "Scholarship ID is required"}), 400

        connection = get_connection()
        cursor = connection.cursor()

        # Validate scholarship exists and is active
        cursor.execute("""
                       SELECT name, grant_amount as amount
                       FROM scholarships
                       WHERE id = %s
                         AND is_active = 1
                         AND deleted_at IS NULL
                       """, (scholarship_id,))
        scholarship = cursor.fetchone()
        if not scholarship:
            return jsonify({"error": "Scholarship not found or inactive"}), 404

        # Validate application exists
        cursor.execute("""
                       SELECT id
                       FROM applications
                       WHERE id = %s
                         AND deleted_at IS NULL
                       """, (application_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Application not found"}), 404

        # Check if already selected
        cursor.execute("""
                       SELECT id
                       FROM scholarship_selections
                       WHERE application_id = %s
                         AND status = 'selected'
                       """, (application_id,))

        existing_selection = cursor.fetchone()
        if existing_selection:
            return jsonify({"error": "Scholarship already awarded to this applicant"}), 409

        # Use provided amount or scholarship default amount
        final_amount = awarded_amount if awarded_amount is not None else scholarship['amount']

        # Validate amount
        if final_amount is not None and final_amount < 0:
            return jsonify({"error": "Awarded amount cannot be negative"}), 400

        # Insert selection
        cursor.execute("""
                       INSERT INTO scholarship_selections
                       (application_id, scholarship_id, status, awarded_amount, selection_reason, created_at,
                        updated_at)
                       VALUES (%s, %s, 'selected', %s, %s, NOW(), NOW())
                       """, (application_id, scholarship_id, final_amount, selection_reason))

        selection_id = cursor.lastrowid

        # Update application status
        cursor.execute("""
                       UPDATE applications
                       SET status     = 'approved',
                           updated_at = NOW()
                       WHERE id = %s
                       """, (application_id,))

        connection.commit()

        logger.info(f"Scholarship {scholarship_id} awarded to application {application_id}")

        response_data = {
            "id": selection_id,
            "application_id": application_id,
            "scholarship_id": scholarship_id,
            "status": "selected",
            "awarded_amount": float(final_amount) if final_amount is not None else None,
            "selection_reason": selection_reason,
            "selected_date": datetime.now().isoformat(),
            "message": "Scholarship awarded successfully"
        }

        return jsonify(response_data), 201

    except Exception as e:
        if 'connection' in locals():
            connection.rollback()
        logger.error(f"Error selecting scholarship for application {application_id}: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


@evaluations_bp.route("/recommendations", methods=["POST"])
@jwt_required()
def get_applicant_recommendations():
    """Get scholarship recommendations for an applicant with selection status"""
    try:
        data = request.get_json()
        application_id = data.get('application_id')

        if not application_id:
            return jsonify({"error": "Application ID is required"}), 400

        connection = get_connection()
        cursor = connection.cursor()

        # Get recommendations with selection status
        query = """
                SELECT rs.id, \
                       s.id      AS scholarship_id, \
                       s.name, \
                       s.description, \
                       s.is_active, \
                       s.created_at, \
                       s.updated_at, \
                       s.deleted_at, \
                       ss.status AS selection_status
                FROM recommended_scholarships rs
                         INNER JOIN scholarships s ON s.id = rs.scholarship_id
                         LEFT JOIN scholarship_selections ss
                                   ON ss.scholarship_id = rs.scholarship_id AND ss.application_id = rs.application_id
                WHERE rs.application_id = %s
                ORDER BY rs.score DESC \
                """
        cursor.execute(query, (application_id,))
        results = cursor.fetchall()

        selected_query = """
                         SELECT scholarship_id
                         FROM scholarship_selections
                         WHERE application_id = %s \
                           AND status = 'selected' \
                         """
        cursor.execute(selected_query, (application_id,))
        selected_results = cursor.fetchall()
        selected_ids = [row['scholarship_id'] for row in selected_results]

        return jsonify({
            'recommendations': results,
            'selectedScholarships': selected_ids
        }), 200

    except Exception as e:
        logger.error(f"Error fetching applicant recommendations: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


# ==========================================
# UTILITY ENDPOINTS
# ==========================================
@evaluations_bp.route("/dashboard/statistics", methods=["GET"])
@jwt_required()
def get_dashboard_statistics():
    """Get overall statistics for admin dashboard"""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        stats = {}

        # Total evaluations
        cursor.execute("SELECT COUNT(*) as count FROM evaluations WHERE deleted_at IS NULL")
        stats["total_evaluations"] = cursor.fetchone()["count"]

        # Pending evaluations
        cursor.execute("SELECT COUNT(*) as count FROM evaluations WHERE status = 'pending' AND deleted_at IS NULL")
        stats["pending_evaluations"] = cursor.fetchone()["count"]

        # Total recommendations
        cursor.execute("SELECT COUNT(*) as count FROM recommended_scholarships")
        stats["total_recommendations"] = cursor.fetchone()["count"]

        # Final selections
        cursor.execute("SELECT COUNT(*) as count FROM scholarship_selections WHERE status = 'selected'")
        stats["total_selections"] = cursor.fetchone()["count"]

        # Classification breakdown
        cursor.execute("""
                       SELECT classification, COUNT(*) as count
                       FROM evaluations
                       WHERE deleted_at IS NULL
                       GROUP BY classification
                       ORDER BY count DESC
                       """)
        stats["classification_breakdown"] = {row["classification"]: row["count"] for row in cursor.fetchall()}

        # Recent activity (last 30 days)
        cursor.execute("""
                       SELECT DATE(created_at) as date,
                              COUNT(*)         as evaluations
                       FROM evaluations
                       WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                         AND deleted_at IS NULL
                       GROUP BY DATE(created_at)
                       ORDER BY date DESC
                       LIMIT 30
                       """)
        recent_activity = cursor.fetchall()
        stats["recent_activity"] = [
            {"date": row["date"].isoformat(), "evaluations": row["evaluations"]}
            for row in recent_activity
        ]

        # Top performing scholarships by selections
        cursor.execute("""
                       SELECT s.name,
                              COUNT(ss.id) as selections
                       FROM scholarship_selections ss
                                JOIN scholarships s ON ss.scholarship_id = s.id
                       WHERE ss.status = 'selected'
                       GROUP BY s.id, s.name
                       ORDER BY selections DESC
                       LIMIT 10
                       """)
        top_scholarships = cursor.fetchall()
        stats["top_scholarships"] = [
            {"name": row["name"], "selections": row["selections"]}
            for row in top_scholarships
        ]

        return jsonify(stats), 200

    except Exception as e:
        logger.error(f"Error fetching dashboard statistics: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


# ============================================
#       BATCH OPERATIONS
# ============================================
@evaluations_bp.route('/batch/evaluate', methods=['POST'])
@jwt_required()
def batch_evaluate():
    """Batch evaluate multiple applications"""
    try:
        data = request.get_json()
        applications = data.get('applications', [])

        if not applications:
            return jsonify({"error": "No applications provided"}), 400

        connection = get_connection()
        cursor = connection.cursor()

        results = []
        errors = []

        for app_data in applications:
            try:
                application_id = app_data.get('application_id')
                gwa = float(app_data.get('gwa', 0))
                income = float(app_data.get('income', 0))
                total_units = int(app_data.get('total_units', 0))

                # Validate data
                if not (0 <= gwa <= 5.0):
                    errors.append(f"Application {application_id}: Invalid GWA {gwa}")
                    continue

                if income < 0:
                    errors.append(f"Application {application_id}: Invalid income {income}")
                    continue

                # Perform evaluation
                result = fuzzy.evaluate(gwa, income)
                score = round(result["score"], 4)
                classification = result["classification"]

                # Insert/update evaluation
                cursor.execute("""
                               INSERT INTO evaluations (application_id, gwa, total_units, income, score, classification,
                                                        created_at, updated_at)
                               VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                               ON DUPLICATE KEY UPDATE gwa            = VALUES(gwa),
                                                       income         = VALUES(income),
                                                       score          = VALUES(score),
                                                       total_units    = VALUES(total_units),
                                                       classification = VALUES(classification),
                                                       updated_at     = NOW()
                               """, (application_id, gwa, total_units, income, score, classification))

                results.append({
                    "application_id": application_id,
                    "score": score,
                    "classification": classification,
                    "status": "success"
                })

            except Exception as e:
                errors.append(f"Application {app_data.get('application_id', 'unknown')}: {str(e)}")

        connection.commit()

        logger.info(f"Batch evaluation completed: {len(results)} successful, {len(errors)} errors")

        return jsonify({
            "results": results,
            "errors": errors,
            "total_processed": len(applications),
            "successful": len(results),
            "failed": len(errors)
        }), 200

    except Exception as e:
        if 'connection' in locals():
            connection.rollback()
        logger.error(f"Error in batch evaluation: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


# ============================================
#       LEGACY COMPATIBILITY FUNCTIONS
# ============================================
def check_scholarship_eligibility(gwa, income, is_ofw, is_farmers_child, is_ip, is_pwd, units_enrolled, config):
    """Legacy compatibility function - use check_scholarship_eligibility_enhanced instead"""
    evaluation_data = {
        "gwa": gwa,
        "income": income,
        "units_enrolled": units_enrolled
    }

    applicant_data = {
        "is_ofw": is_ofw,
        "is_farmers_child": is_farmers_child,
        "is_ip": is_ip,
        "is_pwd": is_pwd
    }

    return check_scholarship_eligibility_enhanced(evaluation_data, applicant_data, config)


def calculate_scholarship_score(base_score, config, applicant_priorities):
    """Legacy compatibility function - use calculate_scholarship_score_enhanced instead"""
    return calculate_scholarship_score_enhanced(base_score, config, applicant_priorities)