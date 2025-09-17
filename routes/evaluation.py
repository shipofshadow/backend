import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.application_service import base_applicant_query, fetch_grades_by_application_ids
from services.meta.fuzzy_logic import FuzzyEligibilitySystem
from services.notification_service import create_notification
from services.recommend_service import RecommendationService

from storage import get_connection
from utils.applications import get_application
from utils.utils import smart_detect_flags, safe_json_parse, extract_applicant_flags

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

evaluations_bp = Blueprint('evaluations', __name__, url_prefix='/api/evaluations')
fuzzy = FuzzyEligibilitySystem(get_connection)


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

        is_valid, error_msg = validate_evaluation_data(data)
        if not is_valid:
            return jsonify({"error": error_msg}), 400

        gwa = float(data.get("gwa"))
        income = float(data.get("income"))
        total_units = int(data.get("total_units"))

        connection = get_connection()
        cursor = connection.cursor()

        # Check if application exists
        cursor.execute("SELECT id, student_id as user_id FROM applications WHERE id = %s AND deleted_at IS NULL", (application_id,))
        res = cursor.fetchone()
        if not res:
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

        create_notification(
            user_id=res['user_id'],
            message_type='system_announcement',
            title='📊 Application Evaluated',
            message=f'Your application #{application_id} has been evaluated. Score: {score} -({classification}).',
            metadata={
                'application_id': application_id,
                'gwa': gwa,
                'income': income,
                'total_units': total_units,
                'score': score,
                'classification': classification
            },
            priority='normal',
            action_url=f'/applicant/status'
        )

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

        recommend_obj = RecommendationService(cursor)

        # Generate recommendations
        recommendations = recommend_obj.recommend(
            applicant_data, evaluation_data
        )

        # Insert recommendations to db
        store_recommendations(cursor, application_id, recommendations)
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
        app = get_application(application_id)
        if not app:
            return jsonify({"error": "Applicant not found"}), 404
        data = request.get_json()
        user_id = app["user_id"]
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
        final_amount = float(final_amount)

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

        create_notification(
            user_id=user_id,
            message_type='system_announcement',
            title='🎉 Scholarship Awarded',
            message=f'Congratulations! Your application #{application_id} has been awarded the scholarship "{scholarship["name"]}" with an amount of PHP {final_amount:.2f}.',
            metadata={
                'application_id': application_id,
                'scholarship_id': scholarship_id,
                'awarded_amount': final_amount,
                'selection_reason': selection_reason
            },
            priority='high',
            action_url=f'/applicant/status'
        )

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


# ============================================
#       UTILITY FUNCTIONS
# ============================================

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

