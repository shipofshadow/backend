import json

from flask import request, jsonify, Blueprint
from services.recommend_service import RecommendationService
from storage import get_connection
from services.meta.fuzzy_logic import FuzzyEligibilitySystem
from utils.utils import extract_applicant_flags
from routes.evaluation import validate_evaluation_data

prequalify_bp = Blueprint("prequalify", __name__, url_prefix="/api/prequalify")
fuzzy = FuzzyEligibilitySystem(get_connection)


@prequalify_bp.route('/calculate', methods=['POST'])
def calculate_prequalification():
    try:
        data = request.get_json()
        connection = get_connection()
        cursor = connection.cursor()

        result = recommend(data, cursor)

        return jsonify({
            "success": True,
            "score": result["score"],
            "classification": result["classification"],
            "recommended_scholarships": result["recommended_scholarships"]
        })

    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Calculation error: {str(e)}",
        }), 500


@prequalify_bp.route("/bulk_prequalify", methods=["POST"])
def bulk_prequalify():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        data = request.get_json()
        if isinstance(data, str):
            data = json.loads(data)

        s = data

        result = recommend(s, cursor)

        cursor.execute("""
            INSERT INTO prequalification_students (
                student_id, name, course, year_level, gwa, family_income,
                is_4ps_member, ip_affiliation, is_pwd, siblings_in_college,
                father_occupation, mother_occupation, total_units
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                student_id=VALUES(student_id),
                name=VALUES(name),
                course=VALUES(course),
                year_level=VALUES(year_level),
                gwa=VALUES(gwa),
                family_income=VALUES(family_income),
                is_4ps_member=VALUES(is_4ps_member),
                ip_affiliation=VALUES(ip_affiliation),
                is_pwd=VALUES(is_pwd),
                siblings_in_college=VALUES(siblings_in_college),
                father_occupation=VALUES(father_occupation),
                mother_occupation=VALUES(mother_occupation),
                total_units=VALUES(total_units)
        """, (
            s.get("student_id"), s.get("name"), s.get("course"), s.get("year_level"),
            s.get("gwa"), s.get("income"), s.get("is_4ps_member"),
            s.get("ip_affiliation"), s.get("is_pwd"), s.get("siblings_in_college"),
            s.get("father_occupation"), s.get("mother_occupation"), s.get("total_units")
        ))

        cursor.execute("""
            INSERT INTO prequalifications 
                (student_id, eligibility_score, classification, has_missing_data, missing_fields)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                student_id=VALUES(student_id),
                eligibility_score=VALUES(eligibility_score),
                classification=VALUES(classification),
                has_missing_data=VALUES(has_missing_data),
                missing_fields=VALUES(missing_fields)
        """, (
            s["student_id"],
            result["score"],
            result["classification"],
            len(result["missing_fields"]) > 0,
            ", ".join(result["missing_fields"]) if result["missing_fields"] else None
        ))

        connection.commit()

        return jsonify({
            "success": True,
            "message": f"Student {s['student_id']} analyzed successfully",
            "score": result["score"],
            "classification": result["classification"],
            "recommended_scholarships": result["recommended_scholarships"]
        }), 200

    except ValueError as ve:
        connection.rollback()
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        connection.rollback()
        print("Bulk prequalify error:", e)
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cursor.close()
        connection.close()


def recommend(data, cursor=None):
    """
    Shared helper for evaluating a student's prequalification.
    Accepts a dict (data) and an optional cursor for DB access.
    Returns dict with score, classification, recommendations.
    """
    is_valid, error_msg = validate_evaluation_data(data)
    if not is_valid:
        raise ValueError(error_msg)

    applicant_data = extract_applicant_flags(data)
    gwa = float(data.get("gwa") or 0)
    income = float(data.get("income") or 0)
    total_units = int(data.get("total_units") or 0)

    result = fuzzy.evaluate(gwa, income)
    score = result["score"] * 100

    evaluation_data = {
        "score": result["score"],
        "classification": result["classification"],
        "gwa": gwa,
        "income": income,
        "units_enrolled": total_units
    }

    recommendations = []
    if cursor:
        recommend_obj = RecommendationService(cursor)
        recommendations = recommend_obj.recommend(applicant_data, evaluation_data)


    return {
        "score": score,
        "classification": result["classification"],
        "recommended_scholarships": recommendations,
        "missing_fields": []
    }