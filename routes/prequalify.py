import json
import time

from flask import request, jsonify, Blueprint
from flask_jwt_extended import jwt_required

from db import get_connection
from services.meta.fuzzy_logic import FuzzyEligibilitySystem

prequalify_bp = Blueprint("prequalify", __name__, url_prefix="/api/prequalify")

@prequalify_bp.route('/calculate', methods=['POST'])
@jwt_required()
def calculate_prequalification():
    """
    Real-time prequalification endpoint
    Expects: { "gwa": 1.75, "income": 25000, "additional_factors": {...} }
    Returns: { "score": 85.5, "classification": "Eligible", "recommended_scholarships": [...] }
    """
    start_time = time.time()

    try:
        # Input validation
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # Extract and validate required fields
        gwa = data.get('gwa')
        income = data.get('income')

        if gwa is None or income is None:
            return jsonify({'success': False, 'error': 'GWA and income are required'}), 400

        # Validate GWA range (Philippine grading system: 1.00-5.00)
        try:
            gwa = float(gwa)
            if not (1.00 <= gwa <= 5.00):
                return jsonify({'success': False, 'error': 'GWA must be between 1.00 and 5.00'}), 400
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid GWA format'}), 400

        # Validate income
        try:
            income = float(income)
            if income < 0:
                return jsonify({'success': False, 'error': 'Income cannot be negative'}), 400
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid income format'}), 400

        # Get additional factors (optional)
        year_level = data.get('year_level', '')
        is_4ps = data.get('is_4ps_member', False)
        is_indigenous = data.get('is_indigenous', False)
        is_pwd = data.get('is_pwd', False)
        siblings_in_college = data.get('siblings_in_college', 0)

        # Calculate eligibility using existing fuzzy system
        result = calculate_fuzzy_eligibility(
            gwa=gwa,
            income=income,
            year_level=year_level,
            is_4ps=is_4ps,
            is_indigenous=is_indigenous,
            is_pwd=is_pwd,
            siblings_in_college=siblings_in_college
        )

        # Get recommended scholarships based on score
        recommended_scholarships = get_recommended_scholarships_for_prequalification(
            score=result['score'],
            classification=result['classification'],
            gwa=gwa,
            income=income,
            additional_factors={
                'year_level': year_level,
                'is_4ps': is_4ps,
                'is_indigenous': is_indigenous,
                'is_pwd': is_pwd
            }
        )

        # Calculate response time
        response_time = round((time.time() - start_time) * 1000, 2)  # milliseconds

        return jsonify({
            'success': True,
            'score': result['score'],
            'classification': result['classification'],
            'recommended_scholarships': recommended_scholarships,
            'factors_breakdown': result.get('factors', {}),
            'response_time_ms': response_time,
            'tips': get_improvement_tips(result['score'], result['classification'])
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Calculation error: {str(e)}',
            'response_time_ms': round((time.time() - start_time) * 1000, 2)
        }), 500


def calculate_fuzzy_eligibility(gwa, income, year_level='', is_4ps=False, is_indigenous=False, is_pwd=False,
                                siblings_in_college=0):
    """
    Enhanced fuzzy logic calculation with caching
    """
    try:
        # Use your existing FuzzyEligibilitySystem
        fuzzy = FuzzyEligibilitySystem(get_connection)

        # Your existing evaluation method - enhanced for additional factors
        result = fuzzy.evaluate(gwa, income)

        score = result["score"] * 100
        classification = result["classification"]
        print(result)

        # Apply bonus points for special circumstances
        bonus_points = 0
        factors_applied = []

        if is_4ps:
            bonus_points += 5
            factors_applied.append("4Ps Member (+5 points)")

        if is_indigenous:
            bonus_points += 8
            factors_applied.append("Indigenous People (+8 points)")

        if is_pwd:
            bonus_points += 6
            factors_applied.append("Person with Disability (+6 points)")

        if siblings_in_college > 0:
            sibling_bonus = min(siblings_in_college * 2, 8)  # Max 8 points
            bonus_points += sibling_bonus
            factors_applied.append(f"Siblings in College (+{sibling_bonus} points)")

        # Year level consideration (slight bonus for higher years)
        year_bonus = 0
        if year_level in ['3rd Year', '4th Year', '5th Year']:
            year_bonus = 2
            factors_applied.append(f"{year_level} (+{year_bonus} points)")

        # Apply bonuses (cap at 100)
        final_score = min(score + bonus_points + year_bonus, 100)

        # Recalculate classification if score changed significantly
        if final_score != score:
            if final_score >= 80:
                classification = "Highly Eligible"
            elif final_score >= 65:
                classification = "Eligible"
            elif final_score >= 45:
                classification = "Somewhat Eligible"
            elif final_score >= 25:
                classification = "Barely Eligible"
            else:
                classification = "Not Eligible"

        return {
            'score': round(final_score, 2),
            'classification': classification,
            'original_score': score,
            'bonus_points': bonus_points + year_bonus,
            'factors': {
                'gwa_impact': round((5 - gwa) * 20, 2),  # Rough calculation
                'income_impact': round(max(0, (50000 - income) / 1000), 2),
                'special_factors': factors_applied
            }
        }

    except Exception as e:
        raise Exception(f"Fuzzy calculation failed: {str(e)}")


def get_recommended_scholarships_for_prequalification(score, classification, gwa, income, additional_factors):
    """
    Get recommended scholarships based on prequalification results
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        recommendations = []

        # Base query for active scholarships
        query = """
                SELECT s.id, \
                       s.name, \
                       s.description, \
                       s.grant_amount,
                       sr.config
                FROM scholarships s
                         LEFT JOIN scholarship_rules sr ON s.id = sr.scholarship_id
                WHERE s.is_active = 1 \
                  AND s.deleted_at IS NULL \
                """

        cursor.execute(query)
        scholarships = cursor.fetchall()

        for scholarship in scholarships:
            is_eligible = True
            eligibility_reasons = []
            confidence_score = score

            # Parse scholarship rules if available
            if scholarship['config']:
                try:
                    rules = json.loads(scholarship['config'])

                    # Check GWA requirements
                    if rules.get('min_gwa') and gwa > rules['min_gwa']:
                        is_eligible = False
                    elif rules.get('max_gwa') and gwa < rules['max_gwa']:
                        eligibility_reasons.append(f"GWA {gwa} meets requirement")

                    # Check income requirements
                    if rules.get('max_income') and income > rules['max_income']:
                        is_eligible = False
                    elif rules.get('max_income'):
                        eligibility_reasons.append(f"Income ₱{income:,.2f} meets requirement")

                    # Check priorities
                    priorities = rules.get('priorities', {})
                    if priorities.get('require_ip') and not additional_factors.get('is_indigenous'):
                        is_eligible = False
                    if priorities.get('must_be_ofw') and not additional_factors.get('is_ofw'):
                        is_eligible = False

                    # Boost confidence for preferred categories
                    if priorities.get('prefer_farmers_child') and additional_factors.get('is_farmers_child'):
                        confidence_score += 5
                    if priorities.get('prefer_pwd') and additional_factors.get('is_pwd'):
                        confidence_score += 5

                except json.JSONDecodeError:
                    pass  # Skip if config is invalid

            # Only recommend if eligible and score meets minimum threshold
            if is_eligible and score >= 40:  # Minimum 40% eligibility
                recommendations.append({
                    'id': scholarship['id'],
                    'name': scholarship['name'],
                    'description': scholarship['description'][:100] + '...' if len(
                        scholarship['description']) > 100 else scholarship['description'],
                    'grant_amount': float(scholarship['grant_amount']),
                    'confidence_score': round(min(confidence_score, 100), 1),
                    'eligibility_reasons': eligibility_reasons,
                    'match_strength': 'High' if confidence_score >= 75 else 'Medium' if confidence_score >= 50 else 'Low'
                })

        # Sort by confidence score
        recommendations.sort(key=lambda x: x['confidence_score'], reverse=True)

        # Return top 5 recommendations
        return recommendations[:5]

    except Exception as e:
        print(f"Error getting scholarship recommendations: {str(e)}")
        return []


def get_improvement_tips(score, classification):
    """
    Provide actionable tips to improve eligibility
    """
    tips = []

    if score < 80:
        tips.append("💡 Consider improving your GWA for better scholarship opportunities")

    if score < 60:
        tips.append("📋 Make sure to highlight any special circumstances (4Ps, Indigenous, PWD)")
        tips.append("👨‍👩‍👧‍👦 Include information about siblings currently studying")

    if score < 40:
        tips.append("📞 Consider speaking with a financial aid counselor for personalized guidance")
        tips.append("🎯 Look for need-based scholarships rather than merit-based ones")

    if classification == "Highly Eligible":
        tips.append("🎉 Excellent! You're highly eligible for most scholarships")
    elif classification == "Eligible":
        tips.append("✅ Good news! You qualify for several scholarship programs")
    elif classification == "Somewhat Eligible":
        tips.append("⚠️ You may qualify for some scholarships. Consider applying to multiple programs")

    return tips


# Health check endpoint for monitoring
@prequalify_bp.route('/health', methods=['GET'])
def prequalify_health():
    """Health check for prequalification service"""
    start_time = time.time()

    try:
        # Test database connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()

        # Test fuzzy system
        fuzzy = FuzzyEligibilitySystem(get_connection)
        test_result = fuzzy.evaluate(2.0, 30000)  # Quick test

        response_time = round((time.time() - start_time) * 1000, 2)

        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'fuzzy_system': 'operational',
            'response_time_ms': response_time,
            'cache_status':  'disabled'
        })

    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'response_time_ms': round((time.time() - start_time) * 1000, 2)
        }), 500