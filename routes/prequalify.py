import json
import time

from flask import request, jsonify, Blueprint
from flask_jwt_extended import jwt_required

from routes.evaluation import validate_evaluation_data
from services.recommend_service import RecommendationService
from storage import get_connection
from services.meta.fuzzy_logic import FuzzyEligibilitySystem
from utils.utils import extract_applicant_flags

prequalify_bp = Blueprint("prequalify", __name__, url_prefix="/api/prequalify")
fuzzy = FuzzyEligibilitySystem(get_connection)

@prequalify_bp.route('/calculate', methods=['POST'])
@jwt_required()
def calculate_prequalification():
    """
    Real-time prequalification endpoint
    Expects: { "gwa": 1.75, "income": 25000, "additional_factors": {...} }
    Returns: { "score": 85.5, "classification": "Eligible", "recommended_scholarships": [...] }
    """

    try:
        # Input validation
        data = request.get_json()

        is_valid, error_msg = validate_evaluation_data(data)
        if not is_valid:
            return jsonify({"error": error_msg}), 400

        applicant_data = extract_applicant_flags(data)

        gwa = float(data.get("gwa"))
        income = float(data.get("income"))
        total_units = int(data.get("total_units"))

        result = fuzzy.evaluate(gwa, income)
        evaluation_data = {
            "score": result["score"],
            "classification": result["classification"],
            "gwa": gwa,
            "income": income,
            "units_enrolled": total_units
        }

        connection = get_connection()
        cursor = connection.cursor()

        recommend_obj = RecommendationService(cursor)

        # Generate recommendations
        recommendations = recommend_obj.recommend(
            applicant_data, evaluation_data
        )


        score = result["score"] * 100

        return jsonify({
            'success': True,
            'score': score,
            'classification': result['classification'],
            'recommended_scholarships': recommendations
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Calculation error: {str(e)}',
        }), 500


