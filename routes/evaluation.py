import json
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.application_service import base_applicant_query, fetch_grades_by_application_ids
from services.meta.fuzzy_logic import FuzzyEligibilitySystem
from db import get_connection
from utils.utils import smart_detect_flags

evaluations_bp = Blueprint('evaluations', __name__, url_prefix='/api/evaluations')
fuzzy = FuzzyEligibilitySystem()

# ============================================
#       GET THE EVALUATEES
# ============================================
@evaluations_bp.route('/', methods=['GET'])
@jwt_required()
def fetch_evaluatees():
    connection = get_connection()
    cursor = connection.cursor()

    query = base_applicant_query() + """
      WHERE applications.deleted_at IS NULL 
      AND applications.status = 'pending'
      AND semesters.is_active = 1 
    """

    cursor.execute(query)
    applicants = cursor.fetchall()

    application_ids = [app["id"] for app in applicants]
    grades_map = fetch_grades_by_application_ids(cursor, application_ids)

    results = []
    for app in applicants:
        app["grades"] = grades_map.get(app["id"], [])

        flags = smart_detect_flags(
            app.get("father_occupation", ""),
            app.get("mother_occupation", ""),
        )

        total_income = (app.get("father_income") or 0) + (app.get("mother_income") or 0)

        result = {
            "id": app["id"],
            "application_id": app["id"],
            "user_id": app['user_id'],
            "name": f"{app['first_name']} {app['last_name']}",
            "grades": app.get("grades", []),
            "family_income": total_income,
            "status": app.get("status"),
            "is_ofw": flags["is_ofw"],
            "is_farmers_child": flags["is_farmers_child"],
            "is_ip": app.get("ip_affiliation") is not None,
            "course_id": app.get("course_id"),
            "department_id": app.get("department_id"),
            "campus_id": app.get("campus_id"),
            "year_level": app.get("year_level"),
        }
        results.append(result)

    return jsonify(results)

# ============================================
#       EVALUATE
# ============================================
@evaluations_bp.route('/<application_id>/evaluate', methods=['POST'])
@jwt_required()
def evaluate(application_id):
    data = request.get_json()
    gwa = data.get("gwa")
    income = data.get("income")
    total_units = data.get("total_units")
    try:

        connection = get_connection()
        cursor = connection.cursor()

        result = fuzzy.evaluate(gwa, income)
        score = round(result["score"], 4)
        classification = result["classification"]

        cursor.execute("""
                        INSERT INTO evaluations (
                            application_id, gwa, total_units, income, score, classification
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            gwa            = VALUES(gwa),
                            income         = VALUES(income),
                            score          = VALUES(score),
                            total_units    = VALUES(total_units),
                            classification = VALUES(classification)
                       """, (application_id, gwa, total_units, income, score, classification))

        connection.commit()
        return jsonify({
            "application_id": int(application_id),
            "score": score,
            "classification": classification,
            "gwa": gwa
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        connection.close()

# ============================================
#       FETCH THE EVALUATION RESULTS
# ============================================
@evaluations_bp.route('/<application_id>/results', methods=['GET'])
@jwt_required()
def get_evaluation_result(application_id):
    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT id, application_id, gwa, score, classification, created_at
            FROM evaluations
            WHERE application_id = %s
        """, (application_id,))

        row = cursor.fetchone()
        cursor.close()
        connection.close()

        if not row:
            return jsonify({"error": "Evaluation not found"}), 404

        return jsonify({
            "application_id": int(row["application_id"]),
            "gwa": float(row["gwa"]),
            "score": float(row["score"]),
            "classification": row["classification"],
        })


    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ================================================================
#       GIVE SCHOLARSHIP RECOMMENDATION BASED FROM THE EVALUATION
# ================================================================
@evaluations_bp.route('/<application_id>/recommend', methods=['POST'])
@jwt_required()
def recommend(application_id):
    application_id = int(application_id)

    db = get_connection()
    cursor = db.cursor()

    cursor.execute(base_applicant_query() + " WHERE semesters.is_active = 1 AND applications.id = %s",
                   (application_id,))
    applicant = cursor.fetchone()

    if not applicant:
        return jsonify({"error": "Application not found"}), 404

    flags = smart_detect_flags(
        applicant.get("father_occupation", ""),
        applicant.get("mother_occupation", "")
    )

    is_ofw = flags["is_ofw"]
    is_farmers_child = flags["is_farmers_child"]
    is_pwd = False
    is_ip = bool(applicant.get("ip_affiliation"))
    course_id = applicant.get("course_id")
    department_id = applicant.get("department_id")
    campus_id = applicant.get("campus_id")
    year_level = applicant.get("year_level")

    cursor.execute("""
                   SELECT score, classification, gwa, income, total_units
                   FROM evaluations
                   WHERE application_id = %s
                   """, (application_id,))

    evaluation_result = cursor.fetchone()
    if not evaluation_result:
        return jsonify({"error": "Application must be evaluated first"}), 400

    score = evaluation_result["score"]
    classification = evaluation_result["classification"]
    gwa = evaluation_result["gwa"]
    income = evaluation_result["income"]
    units_enrolled = evaluation_result["total_units"]

    cursor.execute("""
                   SELECT s.id, s.name, s.description, sr.config, s.grant_amount
                   FROM scholarships s
                            JOIN scholarship_rules sr ON s.id = sr.scholarship_id
                   WHERE s.is_active = 1
                     AND s.deleted_at IS NULL
                   """)

    active_scholarships = cursor.fetchall()
    recommendations = []

    for scholarship in active_scholarships:

        scholarship_id = scholarship['id']
        config = scholarship['config']
        scholarship_name = scholarship['name']
        scholarship_description = scholarship['description']
        grant_amount = scholarship['grant_amount']
        if not config:
            continue

        try:
            config = json.loads(config)
            if isinstance(config, str):
                config = json.loads(config)
        except json.JSONDecodeError as e:
            logging.warning(f"JSONDecodeError for scholarship ID {scholarship_id}: {e} | Raw config: {config!r}")
            continue

        eligibility_check = check_scholarship_eligibility(
            gwa, income, is_ofw, is_farmers_child, is_ip, is_pwd,
            course_id, department_id, campus_id, year_level, units_enrolled,
            config
        )

        if eligibility_check["eligible"]:
            scholarship_score = calculate_scholarship_score(score, config, {
                "is_ofw": is_ofw,
                "is_farmers_child": is_farmers_child,
                "is_ip": is_ip,
                "is_pwd": is_pwd
            })

            recommendations.append({
                "scholarship_id": scholarship_id,
                "name": scholarship_name,
                "description": scholarship_description,
                "amount": grant_amount,
                "score": scholarship_score,
                "classification": classification,
                "reasons": eligibility_check["reasons"]
            })

    recommendations.sort(key=lambda x: x["score"], reverse=True)

    cursor.execute("""
                   DELETE
                   FROM recommended_scholarships
                   WHERE application_id = %s
                   """, (application_id,))

    for rec in recommendations:
        cursor.execute("""
                       INSERT INTO recommended_scholarships
                       (application_id, scholarship_id, score, classification, eligibility_reasons)
                       VALUES (%s, %s, %s, %s, %s)
                       """, (
                           application_id,
                           rec["scholarship_id"],
                           rec["score"],
                           rec["classification"],
                           json.dumps(rec["reasons"])
                       ))

    cursor.execute("""
                   UPDATE evaluations
                   SET recommendations_generated = 1
                   WHERE application_id = %s
                   """, (application_id,))

    db.commit()
    cursor.close()

    return jsonify(recommendations)


# ==========================================
# PHASE 2: RECOMMENDATION REVIEW
# ==========================================
# /6/recommendations
@evaluations_bp.route("/<int:application_id>/recommendations", methods=["GET"])
@jwt_required()
def get_recommendations(application_id):
    """
    Get all scholarship recommendations for an applicant
    """
    db = get_connection()
    cursor = db.cursor()

    try:
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
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        db.close()


@evaluations_bp.route("/<int:application_id>/selection", methods=["GET"])
@jwt_required()
def get_selections(application_id):
    """
    Get final scholarship selection for an applicant (returns single latest selection)
    """
    db = get_connection()
    cursor = db.cursor()

    try:
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
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        db.close()


# ==========================================
# PHASE 3: FINAL SELECTION
# ==========================================

@evaluations_bp.route("/<int:application_id>/select", methods=["POST"])
@jwt_required()
def select_scholarship(application_id):
    """
    Select final scholarship for an applicant
    """
    data = request.get_json()
    scholarship_id = data.get('scholarship_id')
    awarded_amount = data.get('awarded_amount')
    selection_reason = data.get('selection_reason', '')

    if not scholarship_id:
        return jsonify({"error": "Scholarship ID is required"}), 400

    db = get_connection()
    cursor = db.cursor()

    try:
        # Check if scholarship exists
        cursor.execute("SELECT name, grant_amount as amount FROM scholarships WHERE id = %s", (scholarship_id,))
        scholarship = cursor.fetchone()
        if not scholarship:
            return jsonify({"error": "Scholarship not found"}), 404

        # Check if application exists
        cursor.execute("SELECT id FROM applications WHERE id = %s", (application_id,))
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

        db.commit()

        # Return the created selection
        response_data = {
            "id": selection_id,
            "application_id": application_id,
            "scholarship_id": scholarship_id,
            "status": "selected",
            "awarded_amount": float(final_amount),
            "selection_reason": selection_reason,
            "selected_date": datetime.now().isoformat(),
            "message": "Scholarship awarded successfully"
        }

        return jsonify(response_data), 201

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        db.close()


@evaluations_bp.route("/recommendations", methods=["POST"])
@jwt_required()
def get_applicant_recommendations():
    """
    Get scholarship recommendations for an applicant,
    including selection status.
    """
    db = get_connection()
    cursor = db.cursor()

    data = request.get_json()
    application_id = data.get('application_id')

    try:
        # Get recommendations with selection status
        query = """
            SELECT 
                rs.id,
                s.id AS scholarship_id,
                s.name,
                s.description,
                s.is_active,
                s.created_at,
                s.updated_at,
                s.deleted_at,
                ss.status AS selection_status
            FROM recommended_scholarships rs
            INNER JOIN scholarships s ON s.id = rs.scholarship_id
            LEFT JOIN scholarship_selections ss 
                ON ss.scholarship_id = rs.scholarship_id AND ss.application_id = rs.application_id
            WHERE rs.application_id = %s
        """
        cursor.execute(query, (application_id,))
        results = cursor.fetchall()

        selected_query = """
            SELECT scholarship_id 
            FROM scholarship_selections 
            WHERE application_id = %s AND status = 'selected'
        """
        cursor.execute(selected_query, (application_id,))
        selected_results = cursor.fetchall()
        selected_ids = [row['scholarship_id'] for row in selected_results]

        return jsonify({
            'recommendations': results,
            'selectedScholarships': selected_ids
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        db.close()# ==========================================
# UTILITY ENDPOINTS
# ==========================================

@evaluations_bp.route("/dashboard/statistics", methods=["GET"])
@jwt_required()
def get_dashboard_statistics():
    """
    Get overall statistics for admin dashboard
    """
    db = get_connection()
    cursor = db.cursor()

    try:
        stats = {}

        # Total evaluations
        cursor.execute("SELECT COUNT(*) FROM evaluations")
        stats["total_evaluations"] = cursor.fetchone()[0]

        # Pending evaluations
        cursor.execute("SELECT COUNT(*) FROM evaluations WHERE status = 'pending'")
        stats["pending_evaluations"] = cursor.fetchone()[0]

        # Total recommendations
        cursor.execute("SELECT COUNT(*) FROM recommended_scholarships")
        stats["total_recommendations"] = cursor.fetchone()[0]

        # Final selections
        cursor.execute("SELECT COUNT(*) FROM scholarship_selections")
        stats["total_selections"] = cursor.fetchone()[0]

        # Classification breakdown
        cursor.execute("""
                       SELECT classification, COUNT(*) as count
                       FROM evaluations
                       GROUP BY classification
                       """)
        stats["classification_breakdown"] = {row[0]: row[1] for row in cursor.fetchall()}

        return jsonify(stats), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        db.close()


@evaluations_bp.route("/bulk-evaluate", methods=["POST"])
@jwt_required()
def bulk_evaluate():
    """
    Evaluate multiple applications at once
    """
    data = request.get_json()
    applications = data.get("applications", [])

    if not applications:
        return jsonify({"error": "No applications provided"}), 400

    results = []
    errors = []

    for app in applications:
        try:
            # Process each application (reuse logic from evaluate_and_recommend)
            # This is a simplified version - you'd want to call the full evaluation
            result = {
                "application_id": app.get("application_id"),
                "status": "processed"
            }
            results.append(result)
        except Exception as e:
            errors.append({
                "application_id": app.get("application_id"),
                "error": str(e)
            })

    return jsonify({
        "processed": len(results),
        "errors": len(errors),
        "results": results,
        "error_details": errors
    }), 200



# ============================================
#       UTILS
# ============================================
def check_scholarship_eligibility(gwa, income, is_ofw, is_farmers_child, is_ip, is_pwd,
                                  course_id, department_id, campus_id, year_level, units_enrolled, config):
    reasons = []
    eligible = True

    # GWA requirements
    if config.get("min_gwa") and gwa < config["min_gwa"]:
        eligible = False
        reasons.append(f"GWA {gwa} below minimum {config['min_gwa']}")
    elif config.get("max_gwa") and gwa > config["max_gwa"]:
        eligible = False
        reasons.append(f"GWA {gwa} above maximum {config['max_gwa']}")
    else:
        reasons.append(f"GWA {gwa} meets requirements")

    # Income requirements
    if config.get("min_income") and income < config["min_income"]:
        eligible = False
        reasons.append(f"Income {income} below minimum {config['min_income']}")
    elif config.get("max_income") and income > config["max_income"]:
        eligible = False
        reasons.append(f"Income {income} above maximum {config['max_income']}")
    else:
        reasons.append(f"Income {income} meets requirements")

    # Priority requirements
    priorities = config.get("priorities", {})

    if priorities.get("must_be_ofw") and not is_ofw:
        eligible = False
        reasons.append("Must be OFW dependent")
    elif priorities.get("must_be_ofw") and is_ofw:
        reasons.append("OFW requirement met")

    if priorities.get("require_ip") and not is_ip:
        eligible = False
        reasons.append("Must be Indigenous Person")
    elif priorities.get("require_ip") and is_ip:
        reasons.append("IP requirement met")

    # Preferred criteria (adds bonus but doesn't disqualify)
    if priorities.get("prefer_farmers_child") and is_farmers_child:
        reasons.append("Farmer's child (preferred)")

    if priorities.get("prefer_pwd") and is_pwd:
        reasons.append("PWD (preferred)")

    # Units enrolled
    if config.get("min_units_enrolled") and units_enrolled and units_enrolled < config["min_units_enrolled"]:
        eligible = False
        reasons.append(f"Units enrolled {units_enrolled} below minimum {config['min_units_enrolled']}")
    elif config.get("max_units_enrolled") and units_enrolled and units_enrolled > config["max_units_enrolled"]:
        eligible = False
        reasons.append(f"Units enrolled {units_enrolled} above maximum {config['max_units_enrolled']}")

    return {
        "eligible": eligible,
        "reasons": reasons
    }


def calculate_scholarship_score(base_score, config, applicant_priorities):
    """
    Calculate scholarship-specific score with bonuses for preferred criteria
    """
    score = float(base_score)
    priorities = config.get("priorities", {})

    # Add bonuses for preferred criteria
    if priorities.get("prefer_farmers_child") and applicant_priorities.get("is_farmers_child"):
        score += 0.1

    if priorities.get("prefer_pwd") and applicant_priorities.get("is_pwd"):
        score += 0.1

    return min(score, 1.0)

