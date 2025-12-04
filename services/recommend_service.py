from typing import Dict, List
import math

from utils.utils import safe_json_parse


class RecommendationService:
    """Recommendation class"""

    def __init__(self, cursor):
        self.cursor = cursor

    def recommend(self, applicant_data: Dict, evaluation_data: Dict) -> List[Dict]:
        self.cursor.execute("""
                            SELECT s.id, s.name, s.description, sr.config, s.grant_amount
                            FROM scholarships s
                                     JOIN scholarship_rules sr ON s.id = sr.scholarship_id
                            WHERE s.is_active = 1
                              AND s.deleted_at IS NULL
                            ORDER BY s.name
                            """)

        active_scholarships = self.cursor.fetchall()
        recommendations = []

        for scholarship in active_scholarships:
            scholarship_id = scholarship['id']
            config = safe_json_parse(scholarship['config'])
            # Check eligibility
            eligibility_check = self.check_scholarship_eligibility_enhanced(
                evaluation_data, applicant_data, config
            )

            # Check priority requirements (hard filters)
            if not self.check_priority_requirements(applicant_data, config):
                continue

            if eligibility_check["eligible"]:
                # Calculate scholarship-specific score
                scholarship_score = self.calculate_scholarship_score_enhanced(
                    evaluation_data["score"], config, applicant_data, evaluation_data
                )

                scholarship_score = round(scholarship_score * 100, 2)

                recommendation = {
                    "scholarship_id": scholarship_id,
                    "name": scholarship['name'],
                    'description': scholarship['description'][:100] + '...' if len(
                        scholarship['description']) > 100 else scholarship['description'],
                    "amount": scholarship['grant_amount'],
                    "score": scholarship_score,
                    "classification": evaluation_data["classification"],
                    "reasons": eligibility_check["reasons"]
                }
                recommendations.append(recommendation)

        recommendations.sort(key=lambda x: (-x["score"], x["name"]))

        return recommendations

    @staticmethod
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

    @staticmethod
    def check_priority_requirements(applicant_data: Dict, config: Dict) -> bool:
        """Check if applicant meets required priority conditions (hard filters)"""
        priorities = config.get("priorities", {})
        priority_list = config.get("priority", [])

        # Check must_be_ofw requirement
        if priorities.get("must_be_ofw") and not applicant_data["is_ofw"]:
            return False

        # Check require_ip requirement
        if priorities.get("require_ip") and not applicant_data["is_ip"]:
            return False

        if priorities.get("prefer_pwd") and not applicant_data.get("is_pwd"):
            return False

        # Check priority list requirements
        for priority in priority_list:
            if priority == "must_be_ofw" and not applicant_data["is_ofw"]:
                return False
            elif priority == "prefer_farmers_child" and not applicant_data["is_farmers_child"]:
                return False
            elif priority == "prefer_pwd" and not applicant_data["is_pwd"]:
                return False
            elif priority == "require_ip" and not applicant_data["is_ip"]:
                return False

        return True

    @staticmethod
    def calculate_scholarship_score_enhanced(base_score: float, config: Dict, applicant_data: Dict,
                                             evaluation_data: Dict) -> float:
        """
        Enhanced scholarship-specific score calculation with configurable weights and multiple factors.

        Score Components:
        1. Base eligibility score (40-60% weight)
        2. Academic performance alignment (15-25% weight)
        3. Financial need alignment (10-20% weight)
        4. Priority/preference bonuses (5-15% weight)
        5. Program/institutional fit (5-10% weight)
        """

        # Get scoring weights from config (with defaults)
        weights = config.get("scoring_weights", {})
        base_weight = weights.get("base_score", 0.5)  # 50% default
        academic_weight = weights.get("academic_fit", 0.2)  # 20% default
        financial_weight = weights.get("financial_fit", 0.15)  # 15% default
        priority_weight = weights.get("priority_bonus", 0.1)  # 10% default
        program_weight = weights.get("program_fit", 0.05)  # 5% default

        # Normalize weights to sum to 1.0
        total_weight = base_weight + academic_weight + financial_weight + priority_weight + program_weight
        if total_weight > 0:
            base_weight /= total_weight
            academic_weight /= total_weight
            financial_weight /= total_weight
            priority_weight /= total_weight
            program_weight /= total_weight

        # 1. Base score component
        base_component = float(base_score) * base_weight

        # 2. Academic performance alignment
        academic_component = RecommendationService._calculate_academic_fit(
            evaluation_data, config
        ) * academic_weight

        # 3. Financial need alignment
        financial_component = RecommendationService._calculate_financial_fit(
            evaluation_data, config
        ) * financial_weight

        # 4. Priority/preference bonuses
        priority_component = RecommendationService._calculate_priority_bonus(
            applicant_data, config
        ) * priority_weight

        # 5. Program/institutional fit
        program_component = RecommendationService._calculate_program_fit(
            applicant_data, config
        ) * program_weight

        # Calculate final score
        final_score = (
                base_component +
                academic_component +
                financial_component +
                priority_component +
                program_component
        )

        # Apply scholarship-specific multipliers if configured
        multiplier = config.get("score_multiplier", 1.0)
        final_score *= multiplier

        # Ensure score stays within bounds [0, 1]
        return max(0.0, min(1.0, round(final_score, 4)))

    @staticmethod
    def _calculate_academic_fit(evaluation_data: Dict, config: Dict) -> float:
        """Calculate how well the student's academic performance fits the scholarship"""
        gwa = evaluation_data["gwa"]
        min_gwa = config.get("min_gwa")
        max_gwa = config.get("max_gwa")

        # If no GWA requirements, return neutral score
        if min_gwa is None and max_gwa is None:
            return 0.5

        # Calculate fit score based on how close GWA is to optimal range
        if min_gwa is not None and max_gwa is not None:
            # Both limits specified - calculate distance from optimal range
            optimal_gwa = (min_gwa + max_gwa) / 2
            range_size = max_gwa - min_gwa
            if range_size > 0:
                distance = abs(gwa - optimal_gwa) / range_size
                return max(0.0, 1.0 - distance)
            else:
                return 1.0 if gwa == optimal_gwa else 0.0

        elif min_gwa is not None:
            # Only minimum specified - reward higher GWAs more
            if gwa >= min_gwa:
                # Diminishing returns for GWA much higher than minimum
                excess = max(0, gwa - min_gwa)
                return min(1.0, 0.7 + (excess * 0.3))
            else:
                return 0.0

        elif max_gwa is not None:
            # Only maximum specified - reward GWAs closer to maximum
            if gwa <= max_gwa:
                return gwa / max_gwa if max_gwa > 0 else 1.0
            else:
                return 0.0

        return 0.5

    @staticmethod
    def _calculate_financial_fit(evaluation_data: Dict, config: Dict) -> float:
        """Calculate how well the student's financial situation fits the scholarship"""
        income = evaluation_data["income"]
        min_income = config.get("min_income")
        max_income = config.get("max_income")

        # If no income requirements, return neutral score
        if min_income is None and max_income is None:
            return 0.5

        # Calculate fit score based on income requirements
        if min_income is not None and max_income is not None:
            if min_income <= income <= max_income:
                # Within range - score based on position in range
                # Lower income gets higher score (more need)
                range_size = max_income - min_income
                if range_size > 0:
                    normalized_position = (income - min_income) / range_size
                    return 1.0 - normalized_position  # Invert so lower income = higher score
                else:
                    return 1.0
            else:
                return 0.0

        elif max_income is not None:
            # Only maximum specified - reward lower incomes
            if income <= max_income:
                return 1.0 - (income / max_income) if max_income > 0 else 1.0
            else:
                return 0.0

        elif min_income is not None:
            # Only minimum specified - neutral scoring above minimum
            return 0.5 if income >= min_income else 0.0

        return 0.5

    @staticmethod
    def _calculate_priority_bonus(applicant_data: Dict, config: Dict) -> float:
        """Calculate bonus score based on priority criteria"""
        priorities = config.get("priorities", {})
        bonus_weights = config.get("priority_bonus_weights", {})

        total_bonus = 0.0
        max_possible_bonus = 1.0

        # OFW bonus
        if priorities.get("prefer_ofw") and applicant_data.get("is_ofw"):
            bonus = bonus_weights.get("ofw_bonus", 0.3)
            total_bonus += bonus

        # Farmer's child bonus
        if priorities.get("prefer_farmers_child") and applicant_data.get("is_farmers_child"):
            bonus = bonus_weights.get("farmers_bonus", 0.25)
            total_bonus += bonus

        # PWD bonus
        if priorities.get("prefer_pwd") and applicant_data.get("is_pwd"):
            bonus = bonus_weights.get("pwd_bonus", 0.25)
            total_bonus += bonus

        # IP bonus
        if priorities.get("prefer_ip") and applicant_data.get("is_ip"):
            bonus = bonus_weights.get("ip_bonus", 0.3)
            total_bonus += bonus

        # 4Ps bonus
        if priorities.get("prefer_4ps") and applicant_data.get("is_4ps"):
            bonus = bonus_weights.get("4ps_bonus", 0.2)
            total_bonus += bonus

        # Normalize to [0, 1] range
        return min(1.0, total_bonus / max_possible_bonus)

    @staticmethod
    def _calculate_program_fit(applicant_data: Dict, config: Dict) -> float:
        """Calculate fit score based on program/institutional preferences"""
        fit_score = 0.0
        fit_count = 0

        # Course preference
        preferred_courses = config.get("preferred_course_ids", [])
        if preferred_courses:
            fit_count += 1
            if applicant_data.get("course_id") in preferred_courses:
                course_bonus = config.get("course_fit_bonus", 0.4)
                fit_score += course_bonus

        # Department preference
        preferred_departments = config.get("preferred_department_ids", [])
        if preferred_departments:
            fit_count += 1
            if applicant_data.get("department_id") in preferred_departments:
                dept_bonus = config.get("department_fit_bonus", 0.3)
                fit_score += dept_bonus

        # Campus preference
        preferred_campuses = config.get("preferred_campus_ids", [])
        if preferred_campuses:
            fit_count += 1
            if applicant_data.get("campus_id") in preferred_campuses:
                campus_bonus = config.get("campus_fit_bonus", 0.3)
                fit_score += campus_bonus

        # Year level preference
        preferred_year_levels = config.get("preferred_year_levels", [])
        if preferred_year_levels:
            fit_count += 1
            if applicant_data.get("year_level") in preferred_year_levels:
                year_bonus = config.get("year_level_fit_bonus", 0.2)
                fit_score += year_bonus

        # Return average fit score, or neutral if no preferences
        return fit_score / fit_count if fit_count > 0 else 0.5

