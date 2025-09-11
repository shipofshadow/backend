# blueprints/scholarship_summary.py
from flask import Blueprint, jsonify, request
from datetime import datetime
from flask_jwt_extended import jwt_required
from storage import get_connection

scholarship_summary_bp = Blueprint('scholarship_summary', __name__, url_prefix='/api/scholarship-summary')

@scholarship_summary_bp.route('/<int:student_id>', methods=['GET'])
def get_scholarship_summary(student_id):
    """
    Get comprehensive scholarship summary for a specific student
    Includes all applications, evaluations, recommendations, and awards
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student basic info
        student_query = """
                        SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name, s.email
                        FROM students s
                        WHERE s.user_id = %s \
                          AND s.deleted_at IS NULL \
                        """
        cursor.execute(student_query, (student_id,))
        student_info = cursor.fetchone()

        if not student_info:
            return jsonify({"error": "Student not found"}), 404

        # Get all applications for the student
        applications_query = """
                             SELECT a.id                                    as application_id, \
                                    a.status, \
                                    a.submitted_at, \
                                    a.remarks, \
                                    s.name                                  as semester_name, \
                                    CONCAT(ay.year_start, '-', ay.year_end) as academic_year
                             FROM applications a
                                      LEFT JOIN semesters s ON a.semester_id = s.id
                                      LEFT JOIN academic_years ay ON s.academic_year_id = ay.id
                             WHERE a.student_id = %s \
                               AND a.deleted_at IS NULL
                             ORDER BY a.submitted_at DESC \
                             """
        cursor.execute(applications_query, (student_id,))
        applications = cursor.fetchall()

        # Process each application
        applications_data = []

        for app in applications:
            application_data = {
                "application": {
                    "id": app["application_id"],
                    "status": app["status"],
                    "submitted_at": app["submitted_at"].isoformat() if app["submitted_at"] else None,
                    "remarks": app["remarks"],
                    "semester": app["semester_name"],
                    "academic_year": app["academic_year"]
                },
                "evaluation": None,
                "recommended_scholarships": [],
                "selected_scholarships": []
            }

            # Get evaluation for this application
            evaluation_query = """
                               SELECT e.id, \
                                      e.gwa, \
                                      e.total_units, \
                                      e.income, \
                                      e.score, \
                                      e.classification, \
                                      e.recommendations_generated, \
                                      e.admin_reviewed, \
                                      e.status as eval_status, \
                                      e.created_at
                               FROM evaluations e
                               WHERE e.application_id = %s \
                                 AND e.deleted_at IS NULL \
                               """
            cursor.execute(evaluation_query, (app["application_id"],))
            evaluation = cursor.fetchone()

            if evaluation:
                application_data["evaluation"] = {
                    "id": evaluation["id"],
                    "gwa": float(evaluation["gwa"]) if evaluation["gwa"] else None,
                    "total_units": evaluation["total_units"],
                    "income": float(evaluation["income"]) if evaluation["income"] else None,
                    "score": float(evaluation["score"]) if evaluation["score"] else None,
                    "classification": evaluation["classification"],
                    "recommendations_generated": bool(evaluation["recommendations_generated"]),
                    "admin_reviewed": bool(evaluation["admin_reviewed"]),
                    "status": evaluation["eval_status"],
                    "evaluated_at": evaluation["created_at"].isoformat() if evaluation["created_at"] else None
                }

            # Get recommended scholarships for this application
            recommendations_query = """
                                    SELECT rs.id, \
                                           rs.score, \
                                           rs.classification, \
                                           rs.eligibility_reasons, \
                                           rs.notes, \
                                           rs.created_at, \
                                           sch.name        as scholarship_name, \
                                           sch.description as scholarship_description, \
                                           sch.grant_amount
                                    FROM recommended_scholarships rs
                                             JOIN scholarships sch ON rs.scholarship_id = sch.id
                                    WHERE rs.application_id = %s
                                    ORDER BY rs.score DESC \
                                    """
            cursor.execute(recommendations_query, (app["application_id"],))
            recommendations = cursor.fetchall()

            for rec in recommendations:
                eligibility_reasons = None
                if rec["eligibility_reasons"]:
                    try:
                        import json
                        eligibility_reasons = json.loads(rec["eligibility_reasons"])
                    except:
                        eligibility_reasons = rec["eligibility_reasons"]

                application_data["recommended_scholarships"].append({
                    "id": rec["id"],
                    "scholarship_name": rec["scholarship_name"],
                    "scholarship_description": rec["scholarship_description"],
                    "grant_amount": float(rec["grant_amount"]) if rec["grant_amount"] else None,
                    "score": float(rec["score"]) if rec["score"] else None,
                    "classification": rec["classification"],
                    "eligibility_reasons": eligibility_reasons,
                    "notes": rec["notes"],
                    "recommended_at": rec["created_at"].isoformat() if rec["created_at"] else None
                })

            # Get selected/awarded scholarships for this application
            selections_query = """
                               SELECT ss.id, \
                                      ss.selection_reason, \
                                      ss.status, \
                                      ss.awarded_amount, \
                                      ss.created_at, \
                                      sch.name        as scholarship_name, \
                                      sch.description as scholarship_description, \
                                      sch.grant_amount
                               FROM scholarship_selections ss
                                        JOIN scholarships sch ON ss.scholarship_id = sch.id
                               WHERE ss.application_id = %s
                               ORDER BY ss.created_at DESC \
                               """
            cursor.execute(selections_query, (app["application_id"],))
            selections = cursor.fetchall()

            for sel in selections:
                application_data["selected_scholarships"].append({
                    "id": sel["id"],
                    "scholarship_name": sel["scholarship_name"],
                    "scholarship_description": sel["scholarship_description"],
                    "grant_amount": float(sel["grant_amount"]) if sel["grant_amount"] else None,
                    "status": sel["status"],
                    "awarded_amount": float(sel["awarded_amount"]) if sel["awarded_amount"] else None,
                    "selection_reason": sel["selection_reason"],
                    "selected_at": sel["created_at"].isoformat() if sel["created_at"] else None
                })

            applications_data.append(application_data)

        # Generate summary statistics
        total_applications = len(applications_data)
        approved_applications = len([app for app in applications_data if app["application"]["status"] == "approved"])
        total_recommendations = sum(len(app["recommended_scholarships"]) for app in applications_data)
        total_awards = sum(len([sel for sel in app["selected_scholarships"] if sel["status"] == "awarded"]) for app in
                           applications_data)
        total_awarded_amount = sum(
            sum(sel["awarded_amount"] or 0 for sel in app["selected_scholarships"] if sel["status"] == "awarded")
            for app in applications_data
        )

        # Calculate average scores and GWAs
        evaluations_with_data = [app["evaluation"] for app in applications_data if app["evaluation"]]
        avg_gwa = sum(eval["gwa"] for eval in evaluations_with_data if eval["gwa"]) / len(
            evaluations_with_data) if evaluations_with_data else None
        avg_score = sum(eval["score"] for eval in evaluations_with_data if eval["score"]) / len(
            evaluations_with_data) if evaluations_with_data else None

        response_data = {
            "student_info": student_info,
            "summary_statistics": {
                "total_applications": total_applications,
                "approved_applications": approved_applications,
                "total_recommendations": total_recommendations,
                "total_awards": total_awards,
                "total_awarded_amount": total_awarded_amount,
                "average_gwa": round(avg_gwa, 2) if avg_gwa else None,
                "average_score": round(avg_score, 2) if avg_score else None,
                "approval_rate": round((approved_applications / total_applications * 100),
                                       2) if total_applications > 0 else 0,
                "award_rate": round((total_awards / total_applications * 100), 2) if total_applications > 0 else 0
            },
            "applications": applications_data,
            "generated_at": datetime.now().isoformat()
        }

        cursor.close()
        conn.close()

        return jsonify(response_data), 200

    except Exception as e:
        print(f"Error in get_scholarship_summary: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@scholarship_summary_bp.route('/overview', methods=['GET'])
@jwt_required()
def get_system_overview():
    """
    Get system-wide scholarship overview statistics
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Overall statistics
        overview_query = """
                         SELECT (SELECT COUNT(*) FROM applications WHERE deleted_at IS NULL)                         as total_applicants, \
                                (SELECT COUNT(*) \
                                 FROM applications \
                                 WHERE status = 'approved' \
                                   AND deleted_at IS NULL)                                                           as total_approved, \
                                (SELECT COUNT(*) \
                                 FROM applications \
                                 WHERE status = 'denied' \
                                   AND deleted_at IS NULL)                                                           as total_denied, \
                                (SELECT COUNT(*) \
                                 FROM applications \
                                 WHERE status = 'pending' \
                                   AND deleted_at IS NULL)                                                           as total_pending, \
                                (SELECT COUNT(*) FROM scholarship_selections WHERE status = 'awarded')               as total_awarded, \
                                (SELECT SUM(awarded_amount) \
                                 FROM scholarship_selections \
                                 WHERE status = 'awarded')                                                           as total_disbursed, \
                                (SELECT COUNT(DISTINCT scholarship_id) FROM recommended_scholarships)                as active_scholarships, \
                                (SELECT AVG(gwa) FROM evaluations WHERE deleted_at IS NULL)                          as avg_system_gwa, \
                                (SELECT AVG(score) FROM evaluations WHERE deleted_at IS NULL)                        as avg_system_score \
                         """
        cursor.execute(overview_query)
        overview = cursor.fetchone()

        # Classification distribution
        classification_query = """
                               SELECT classification, \
                                      COUNT(*)                                                                as count, \
                                      ROUND((COUNT(*) * 100.0 / \
                                             (SELECT COUNT(*) FROM evaluations WHERE deleted_at IS NULL)), \
                                            2)                                                                as percentage, \
                                      ROUND(AVG(gwa), 2)                                                      as avg_gwa, \
                                      ROUND(AVG(score), 2)                                                    as avg_score
                               FROM evaluations
                               WHERE deleted_at IS NULL
                               GROUP BY classification
                               ORDER BY CASE classification \
                                            WHEN 'Eligible' THEN 1 \
                                            WHEN 'Somewhat Eligible' THEN 2 \
                                            WHEN 'Barely Eligible' THEN 3 \
                                            WHEN 'Not Eligible' THEN 4 \
                                            END \
                               """
        cursor.execute(classification_query)
        classifications = cursor.fetchall()

        # Top scholarships by awards
        top_scholarships_query = """
                                 SELECT s.name, \
                                        s.grant_amount, \
                                        COUNT(ss.id)                                     as total_awarded, \
                                        SUM(COALESCE(ss.awarded_amount, s.grant_amount)) as total_disbursed, \
                                        COUNT(DISTINCT rs.application_id)                as total_recommended
                                 FROM scholarships s
                                          LEFT JOIN scholarship_selections ss \
                                                    ON s.id = ss.scholarship_id AND ss.status = 'awarded'
                                          LEFT JOIN recommended_scholarships rs ON s.id = rs.scholarship_id
                                 WHERE s.deleted_at IS NULL \
                                   AND s.is_active = 1
                                 GROUP BY s.id, s.name, s.grant_amount
                                 HAVING total_awarded > 0
                                 ORDER BY total_awarded DESC
                                 LIMIT 10 \
                                 """
        cursor.execute(top_scholarships_query)
        top_scholarships = cursor.fetchall()

        response_data = {
            "overview": {
                "total_applicants": overview["total_applicants"],
                "total_approved": overview["total_approved"],
                "total_denied": overview["total_denied"],
                "total_pending": overview["total_pending"],
                "total_awarded": overview["total_awarded"],
                "total_disbursed": float(overview["total_disbursed"]) if overview["total_disbursed"] else 0,
                "active_scholarships": overview["active_scholarships"],
                "avg_system_gwa": round(float(overview["avg_system_gwa"]), 2) if overview["avg_system_gwa"] else None,
                "avg_system_score": round(float(overview["avg_system_score"]), 2) if overview[
                    "avg_system_score"] else None,
                "approval_rate": round((overview["total_approved"] / overview["total_applicants"] * 100), 2) if
                overview["total_applicants"] > 0 else 0,
                "award_rate": round((overview["total_awarded"] / overview["total_applicants"] * 100), 2) if overview[
                                                                                                                "total_applicants"] > 0 else 0
            },
            "classifications": classifications,
            "top_scholarships": top_scholarships,
            "generated_at": datetime.now().isoformat()
        }

        cursor.close()
        conn.close()

        return jsonify(response_data), 200

    except Exception as e:
        print(f"Error in get_system_overview: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500