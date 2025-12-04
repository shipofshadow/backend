import json
import re

from flask import request, jsonify, Blueprint
from services.recommend_service import RecommendationService
from services.email_service import send_eligibility_notification_email
from storage import get_connection
from services.meta.fuzzy_logic import FuzzyEligibilitySystem
from utils.utils import extract_applicant_flags
from utils.decorator import admin_required
from routes.evaluation import validate_evaluation_data

prequalify_bp = Blueprint("prequalify", __name__, url_prefix="/api/prequalify")
fuzzy = FuzzyEligibilitySystem(get_connection)

# Rate limiting constants
MAX_EMAILS_PER_BATCH = 100

def is_valid_email(email):
    """Validate email address format"""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


@prequalify_bp.route('/calculate', methods=['POST'])
def calculate_prequalification():
    try:
        data = request.get_json()
        connection = get_connection()
        cursor = connection.cursor()

        result = compute_prequalification(data, cursor)

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

        cursor.execute("""
            INSERT INTO prequalification_students (
                student_id, name, email, course, year_level, gwa, family_income,
                is_4ps_member, ip_affiliation, is_pwd, siblings_in_college,
                father_occupation, mother_occupation, total_units
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                student_id=VALUES(student_id),
                name=VALUES(name),
                email=VALUES(email),
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
            s.get("student_id"), s.get("name"), s.get("email"), s.get("course"), s.get("year_level"),
            s.get("gwa"), s.get("family_income"), s.get("is_4ps_member"),
            s.get("ip_affiliation"), s.get("is_pwd"), s.get("siblings_in_college"),
            s.get("father_occupation"), s.get("mother_occupation"), s.get("total_units")
        ))

        result = compute_prequalification(s, cursor)

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


@prequalify_bp.route("/send_eligibility_emails", methods=["POST"])
@admin_required
def send_eligibility_emails():
    """
    Send eligibility notification emails to eligible students.
    
    Request body:
    {
        "student_ids": ["E21-00193", "E20-00001"],  # Optional: specific students
        "min_score": 60,  # Optional: minimum eligibility score
        "classifications": ["Eligible", "Conditionally Eligible"],  # Optional: filter by classification
        "scholarship_id": 9  # Optional: filter by specific scholarship qualification
    }
    """
    connection = get_connection()
    cursor = connection.cursor()

    try:
        data = request.get_json() or {}
        
        student_ids = data.get("student_ids")
        min_score = data.get("min_score")
        classifications = data.get("classifications")
        scholarship_id = data.get("scholarship_id")

        # Build dynamic query to fetch eligible students
        query = """
            SELECT DISTINCT 
                ps.student_id, 
                ps.name, 
                ps.email,
                p.eligibility_score,
                p.classification
            FROM prequalification_students ps
            INNER JOIN prequalifications p ON ps.student_id = p.student_id
            WHERE ps.email IS NOT NULL AND ps.email != ''
        """
        params = []

        if student_ids:
            placeholders = ", ".join(["%s"] * len(student_ids))
            query += f" AND ps.student_id IN ({placeholders})"
            params.extend(student_ids)

        if min_score is not None:
            query += " AND p.eligibility_score >= %s"
            params.append(min_score)

        if classifications:
            placeholders = ", ".join(["%s"] * len(classifications))
            query += f" AND p.classification IN ({placeholders})"
            params.extend(classifications)

        cursor.execute(query, params)
        students = cursor.fetchall()

        if not students:
            return jsonify({
                "success": True,
                "emails_sent": 0,
                "failed": 0,
                "results": [],
                "message": "No eligible students found matching the criteria"
            }), 200

        # Apply rate limiting
        if len(students) > MAX_EMAILS_PER_BATCH:
            return jsonify({
                "success": False,
                "error": f"Too many recipients. Maximum {MAX_EMAILS_PER_BATCH} emails per batch. Found {len(students)} students."
            }), 400

        results = []
        emails_sent = 0
        failed = 0

        for student in students:
            student_id = student["student_id"]
            email = student["email"]
            name = student["name"]
            score = student["eligibility_score"]
            classification = student["classification"]

            # Validate email format
            if not is_valid_email(email):
                results.append({
                    "student_id": student_id,
                    "email": email,
                    "status": "failed",
                    "message": "Invalid email format"
                })
                failed += 1
                continue

            # Get recommended scholarships for this student
            cursor.execute("""
                SELECT ps.*, p.eligibility_score, p.classification
                FROM prequalification_students ps
                INNER JOIN prequalifications p ON ps.student_id = p.student_id
                WHERE ps.student_id = %s
            """, (student_id,))
            student_data = cursor.fetchone()

            if not student_data:
                results.append({
                    "student_id": student_id,
                    "email": email,
                    "status": "failed",
                    "message": "Student data not found"
                })
                failed += 1
                continue

            # Get scholarship recommendations
            try:
                recommendations = get_student_recommendations(student_data, cursor, scholarship_id)
            except Exception as e:
                recommendations = []

            # Prepare email context
            context = {
                "student_name": name,
                "student_id": student_id,
                "eligibility_score": round(score, 2),
                "classification": classification,
                "recommended_scholarships": recommendations
            }

            # Send email
            try:
                send_eligibility_notification_email(email, context)
                results.append({
                    "student_id": student_id,
                    "email": email,
                    "status": "sent",
                    "message": "Email sent successfully"
                })
                emails_sent += 1
            except Exception as e:
                results.append({
                    "student_id": student_id,
                    "email": email,
                    "status": "failed",
                    "message": str(e)
                })
                failed += 1

        return jsonify({
            "success": True,
            "emails_sent": emails_sent,
            "failed": failed,
            "results": results
        }), 200

    except Exception as e:
        print("Send eligibility emails error:", e)
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cursor.close()
        connection.close()


def get_student_recommendations(student_data, cursor, scholarship_id=None):
    """Get scholarship recommendations for a student"""
    from utils.utils import extract_applicant_flags
    
    applicant_data = extract_applicant_flags(student_data)
    
    evaluation_data = {
        "score": student_data.get("eligibility_score", 0),
        "classification": student_data.get("classification", ""),
        "gwa": float(student_data.get("gwa") or 0),
        "income": float(student_data.get("family_income") or 0),
        "units_enrolled": int(student_data.get("total_units") or 0)
    }

    recommend_obj = RecommendationService(cursor)
    recommendations = recommend_obj.recommend(applicant_data, evaluation_data)

    # Filter by specific scholarship if provided
    if scholarship_id is not None:
        recommendations = [r for r in recommendations if r.get("scholarship_id") == scholarship_id]

    return recommendations


def compute_prequalification(data, cursor=None):
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
        "score": score,
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
