from flask import jsonify, request, Blueprint
from flask_jwt_extended import jwt_required
from db import get_connection
from services.meta.fuzzy_logic import FuzzyEligibilitySystem
import json

evaluations_bp = Blueprint('evaluation', __name__, url_prefix='/api/evaluation')
fuzzy = FuzzyEligibilitySystem()

@evaluations_bp.route("/evaluate", methods=["POST"])
@jwt_required()
def evaluate_applicant():
    data = request.get_json()
    application_id = data.get("application_id")
    gwa = data.get("gwa")
    income = data.get("income")
    ip_affiliation = data.get("ip_affiliation", False)

    if not application_id or gwa is None or income is None:
        return jsonify({"error": "Missing fields"}), 400

    result = fuzzy.evaluate(gwa, income)
    score = round(result["score"], 4)
    classification = result["classification"]

    db = get_connection()
    cursor = db.cursor()

    cursor.execute("""
        SELECT s.id AS scholarship_id, r.min_gwa, r.max_income, r.ip_required
        FROM scholarships s
        JOIN scholarship_rules r ON s.id = r.scholarship_id
        WHERE s.is_active = 1
    """)
    rules = cursor.fetchall()

    recommended_ids = []
    for rule in rules:
        min_gwa = float(rule["min_gwa"])
        max_income = float(rule["max_income"])
        ip_required = rule["ip_required"]

        if gwa <= min_gwa and income <= max_income:
            if not ip_required or ip_affiliation:
                recommended_ids.append(rule["scholarship_id"])

    cursor.execute("""
        INSERT INTO evaluations (application_id, gwa, income, score, classification, recommendations)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            gwa = VALUES(gwa),
            income = VALUES(income),
            score = VALUES(score),
            classification = VALUES(classification),
            recommendations = VALUES(recommendations)
    """, (
        application_id,
        gwa,
        income,
        score,
        classification,
        ','.join(str(x) for x in recommended_ids)
    ))

    db.commit()
    cursor.close()
    db.close()

    return jsonify({
        "application_id": application_id,
        "score": score,
        "classification": classification,
        "memberships": result["memberships"],
        "recommendations": recommended_ids
    }), 200


@evaluations_bp.route('/recommendations', methods=['POST'])
def recommendations():
    data = request.get_json()
    application_id = data.get("application_id")

    db = get_connection()
    cursor = db.cursor()

    query = """
        SELECT scholarships.* 
        FROM evaluations 
        JOIN applications ON applications.id = evaluations.application_id 
        JOIN scholarships ON FIND_IN_SET(scholarships.id, evaluations.recommendations) 
        WHERE evaluations.application_id = %s;
    """

    cursor.execute(query, (application_id,))
    results = cursor.fetchall()

    return jsonify(results), 200

