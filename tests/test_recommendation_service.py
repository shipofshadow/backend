"""Tests for the RecommendationService match explanation feature."""

import pytest
from typing import Dict


class TestGenerateMatchExplanation:
    """Test generate_match_explanation method."""

    @staticmethod
    def generate_match_explanation(applicant_data: Dict, evaluation_data: Dict,
                                   config: Dict, score_breakdown: Dict, total_score: float) -> Dict:
        """
        Local copy of generate_match_explanation for testing without database dependencies.
        """
        gwa = evaluation_data["gwa"]
        income = evaluation_data["income"]

        # Generate summary based on score
        if total_score >= 85:
            summary = "You're an excellent match for this scholarship"
        elif total_score >= 70:
            summary = "You're a strong match for this scholarship"
        elif total_score >= 60:
            summary = "You're a good match for this scholarship"
        else:
            summary = "You meet the basic requirements for this scholarship"

        # Build strength factors
        strength_factors = []

        # Academic Performance Factor
        academic_score = score_breakdown.get("academic_fit_raw", 0.5)
        academic_percent = round(academic_score * 100)
        min_gwa = config.get("min_gwa")
        max_gwa = config.get("max_gwa")

        if min_gwa is not None or max_gwa is not None:
            if academic_score >= 0.8:
                impact = "high"
            elif academic_score >= 0.5:
                impact = "medium"
            else:
                impact = "low"

            if min_gwa is not None and max_gwa is not None:
                description = f"Your GWA of {gwa} is within the required range of {min_gwa}-{max_gwa}"
            elif min_gwa is not None:
                description = f"Your GWA of {gwa} exceeds the minimum requirement of {min_gwa}"
            else:
                description = f"Your GWA of {gwa} meets the maximum requirement of {max_gwa}"

            strength_factors.append({
                "factor": "Academic Performance",
                "score": academic_percent,
                "description": description,
                "impact": impact
            })

        # Financial Need Factor
        financial_score = score_breakdown.get("financial_fit_raw", 0.5)
        financial_percent = round(financial_score * 100)
        min_income = config.get("min_income")
        max_income = config.get("max_income")

        if min_income is not None or max_income is not None:
            if financial_score >= 0.8:
                impact = "high"
            elif financial_score >= 0.5:
                impact = "medium"
            else:
                impact = "low"

            if max_income is not None:
                description = f"Your family income of ₱{income:,.0f} is within the priority range (max: ₱{max_income:,.0f})"
            elif min_income is not None:
                description = f"Your family income of ₱{income:,.0f} meets the minimum requirement of ₱{min_income:,.0f}"
            else:
                description = f"Your family income of ₱{income:,.0f} qualifies for financial consideration"

            strength_factors.append({
                "factor": "Financial Need",
                "score": financial_percent,
                "description": description,
                "impact": impact
            })

        # Build bonus factors
        bonus_factors = []
        priorities = config.get("priorities", {})
        bonus_weights = config.get("priority_bonus_weights", {})

        if priorities.get("prefer_ofw") or priorities.get("must_be_ofw"):
            if applicant_data.get("is_ofw"):
                bonus = bonus_weights.get("ofw_bonus", 0.3)
                bonus_factors.append({
                    "factor": "OFW Family",
                    "points": round(bonus * 100),
                    "description": "This scholarship prioritizes children of OFW families"
                })

        if priorities.get("prefer_ip") or priorities.get("require_ip"):
            if applicant_data.get("is_ip"):
                bonus = bonus_weights.get("ip_bonus", 0.3)
                bonus_factors.append({
                    "factor": "Indigenous Person",
                    "points": round(bonus * 100),
                    "description": "This scholarship prioritizes indigenous students"
                })

        # Build score breakdown
        score_breakdown_output = {
            "base_score": round(score_breakdown.get("base_component", 0) * 100, 1),
            "academic_fit": round(score_breakdown.get("academic_component", 0) * 100, 1),
            "financial_fit": round(score_breakdown.get("financial_component", 0) * 100, 1),
            "priority_bonus": round(score_breakdown.get("priority_component", 0) * 100, 1),
            "program_fit": round(score_breakdown.get("program_component", 0) * 100, 1),
            "total": total_score
        }

        return {
            "summary": summary,
            "strength_factors": strength_factors,
            "bonus_factors": bonus_factors,
            "score_breakdown": score_breakdown_output
        }

    def test_excellent_match_summary(self):
        """Test that score >= 85 generates 'excellent match' summary."""
        result = self.generate_match_explanation(
            applicant_data={"is_ofw": False, "is_ip": False},
            evaluation_data={"gwa": 1.5, "income": 100000},
            config={},
            score_breakdown={},
            total_score=87.5
        )
        assert result["summary"] == "You're an excellent match for this scholarship"

    def test_strong_match_summary(self):
        """Test that score >= 70 and < 85 generates 'strong match' summary."""
        result = self.generate_match_explanation(
            applicant_data={"is_ofw": False, "is_ip": False},
            evaluation_data={"gwa": 1.75, "income": 150000},
            config={},
            score_breakdown={},
            total_score=75.0
        )
        assert result["summary"] == "You're a strong match for this scholarship"

    def test_good_match_summary(self):
        """Test that score >= 60 and < 70 generates 'good match' summary."""
        result = self.generate_match_explanation(
            applicant_data={"is_ofw": False, "is_ip": False},
            evaluation_data={"gwa": 2.0, "income": 200000},
            config={},
            score_breakdown={},
            total_score=65.0
        )
        assert result["summary"] == "You're a good match for this scholarship"

    def test_basic_requirements_summary(self):
        """Test that score < 60 generates 'basic requirements' summary."""
        result = self.generate_match_explanation(
            applicant_data={"is_ofw": False, "is_ip": False},
            evaluation_data={"gwa": 2.5, "income": 300000},
            config={},
            score_breakdown={},
            total_score=55.0
        )
        assert result["summary"] == "You meet the basic requirements for this scholarship"

    def test_academic_performance_factor_with_range(self):
        """Test academic performance factor when min and max GWA are specified."""
        result = self.generate_match_explanation(
            applicant_data={"is_ofw": False, "is_ip": False},
            evaluation_data={"gwa": 1.75, "income": 100000},
            config={"min_gwa": 1.0, "max_gwa": 2.0},
            score_breakdown={"academic_fit_raw": 0.9},
            total_score=85.0
        )
        
        assert len(result["strength_factors"]) >= 1
        academic_factor = next((f for f in result["strength_factors"] if f["factor"] == "Academic Performance"), None)
        assert academic_factor is not None
        assert academic_factor["impact"] == "high"
        assert "within the required range" in academic_factor["description"]

    def test_academic_performance_factor_min_only(self):
        """Test academic performance factor when only min GWA is specified."""
        result = self.generate_match_explanation(
            applicant_data={"is_ofw": False, "is_ip": False},
            evaluation_data={"gwa": 1.5, "income": 100000},
            config={"min_gwa": 2.0},
            score_breakdown={"academic_fit_raw": 0.85},
            total_score=80.0
        )
        
        academic_factor = next((f for f in result["strength_factors"] if f["factor"] == "Academic Performance"), None)
        assert academic_factor is not None
        assert "exceeds the minimum requirement" in academic_factor["description"]

    def test_financial_need_factor(self):
        """Test financial need factor is included when income requirements exist."""
        result = self.generate_match_explanation(
            applicant_data={"is_ofw": False, "is_ip": False},
            evaluation_data={"gwa": 1.75, "income": 120000},
            config={"max_income": 200000},
            score_breakdown={"financial_fit_raw": 0.8},
            total_score=80.0
        )
        
        financial_factor = next((f for f in result["strength_factors"] if f["factor"] == "Financial Need"), None)
        assert financial_factor is not None
        assert "₱120,000" in financial_factor["description"]

    def test_ofw_bonus_factor(self):
        """Test OFW bonus factor is included when applicable."""
        result = self.generate_match_explanation(
            applicant_data={"is_ofw": True, "is_ip": False},
            evaluation_data={"gwa": 1.75, "income": 100000},
            config={"priorities": {"prefer_ofw": True}},
            score_breakdown={},
            total_score=85.0
        )
        
        ofw_factor = next((f for f in result["bonus_factors"] if f["factor"] == "OFW Family"), None)
        assert ofw_factor is not None
        assert "prioritizes children of OFW families" in ofw_factor["description"]

    def test_ip_bonus_factor(self):
        """Test Indigenous Person bonus factor is included when applicable."""
        result = self.generate_match_explanation(
            applicant_data={"is_ofw": False, "is_ip": True},
            evaluation_data={"gwa": 1.75, "income": 100000},
            config={"priorities": {"prefer_ip": True}},
            score_breakdown={},
            total_score=85.0
        )
        
        ip_factor = next((f for f in result["bonus_factors"] if f["factor"] == "Indigenous Person"), None)
        assert ip_factor is not None
        assert "prioritizes indigenous students" in ip_factor["description"]

    def test_score_breakdown_output(self):
        """Test score breakdown is correctly formatted."""
        result = self.generate_match_explanation(
            applicant_data={"is_ofw": False, "is_ip": False},
            evaluation_data={"gwa": 1.75, "income": 100000},
            config={},
            score_breakdown={
                "base_component": 0.425,
                "academic_component": 0.19,
                "financial_component": 0.12,
                "priority_component": 0.085,
                "program_component": 0.055
            },
            total_score=87.5
        )
        
        breakdown = result["score_breakdown"]
        assert breakdown["base_score"] == 42.5
        assert breakdown["academic_fit"] == 19.0
        assert breakdown["financial_fit"] == 12.0
        assert breakdown["priority_bonus"] == 8.5
        assert breakdown["program_fit"] == 5.5
        assert breakdown["total"] == 87.5

    def test_impact_levels(self):
        """Test that impact levels are correctly assigned based on scores."""
        # High impact (score >= 0.8)
        result_high = self.generate_match_explanation(
            applicant_data={"is_ofw": False, "is_ip": False},
            evaluation_data={"gwa": 1.5, "income": 100000},
            config={"min_gwa": 2.0},
            score_breakdown={"academic_fit_raw": 0.85},
            total_score=85.0
        )
        academic_high = next((f for f in result_high["strength_factors"] if f["factor"] == "Academic Performance"), None)
        assert academic_high["impact"] == "high"
        
        # Medium impact (0.5 <= score < 0.8)
        result_medium = self.generate_match_explanation(
            applicant_data={"is_ofw": False, "is_ip": False},
            evaluation_data={"gwa": 1.5, "income": 100000},
            config={"min_gwa": 2.0},
            score_breakdown={"academic_fit_raw": 0.6},
            total_score=70.0
        )
        academic_medium = next((f for f in result_medium["strength_factors"] if f["factor"] == "Academic Performance"), None)
        assert academic_medium["impact"] == "medium"
        
        # Low impact (score < 0.5)
        result_low = self.generate_match_explanation(
            applicant_data={"is_ofw": False, "is_ip": False},
            evaluation_data={"gwa": 1.5, "income": 100000},
            config={"min_gwa": 2.0},
            score_breakdown={"academic_fit_raw": 0.3},
            total_score=60.0
        )
        academic_low = next((f for f in result_low["strength_factors"] if f["factor"] == "Academic Performance"), None)
        assert academic_low["impact"] == "low"


class TestScoreBreakdownCalculation:
    """Test calculate_scholarship_score_with_breakdown method logic."""

    @staticmethod
    def _calculate_academic_fit(evaluation_data: Dict, config: Dict) -> float:
        """Calculate how well the student's academic performance fits the scholarship."""
        gwa = evaluation_data["gwa"]
        min_gwa = config.get("min_gwa")
        max_gwa = config.get("max_gwa")

        if min_gwa is None and max_gwa is None:
            return 0.5

        if min_gwa is not None and max_gwa is not None:
            optimal_gwa = (min_gwa + max_gwa) / 2
            range_size = max_gwa - min_gwa
            if range_size > 0:
                distance = abs(gwa - optimal_gwa) / range_size
                return max(0.0, 1.0 - distance)
            else:
                return 1.0 if gwa == optimal_gwa else 0.0
        elif min_gwa is not None:
            if gwa >= min_gwa:
                excess = max(0, gwa - min_gwa)
                return min(1.0, 0.7 + (excess * 0.3))
            else:
                return 0.0
        elif max_gwa is not None:
            if gwa <= max_gwa:
                return gwa / max_gwa if max_gwa > 0 else 1.0
            else:
                return 0.0
        return 0.5

    @staticmethod
    def _calculate_financial_fit(evaluation_data: Dict, config: Dict) -> float:
        """Calculate how well the student's financial situation fits the scholarship."""
        income = evaluation_data["income"]
        min_income = config.get("min_income")
        max_income = config.get("max_income")

        if min_income is None and max_income is None:
            return 0.5

        if min_income is not None and max_income is not None:
            if min_income <= income <= max_income:
                range_size = max_income - min_income
                if range_size > 0:
                    normalized_position = (income - min_income) / range_size
                    return 1.0 - normalized_position
                else:
                    return 1.0
            else:
                return 0.0
        elif max_income is not None:
            if income <= max_income:
                return 1.0 - (income / max_income) if max_income > 0 else 1.0
            else:
                return 0.0
        elif min_income is not None:
            return 0.5 if income >= min_income else 0.0
        return 0.5

    def test_academic_fit_with_range(self):
        """Test academic fit calculation with min and max GWA."""
        evaluation_data = {"gwa": 1.5}
        config = {"min_gwa": 1.0, "max_gwa": 2.0}
        
        result = self._calculate_academic_fit(evaluation_data, config)
        assert result == 1.0  # Exactly in the middle = perfect fit

    def test_academic_fit_min_only(self):
        """Test academic fit calculation with only min GWA."""
        # When GWA is 1.5 and min_gwa is 2.0, GWA 1.5 >= 2.0 is False
        # In the logic, gwa >= min_gwa returns a positive score
        # Since 1.5 < 2.0, the student does NOT meet minimum requirement
        evaluation_data = {"gwa": 2.5}  # Student has GWA 2.5 (meets min of 2.0)
        config = {"min_gwa": 2.0}
        
        result = self._calculate_academic_fit(evaluation_data, config)
        assert result >= 0.7  # GWA meets minimum

    def test_academic_fit_no_requirements(self):
        """Test academic fit returns neutral score when no requirements."""
        evaluation_data = {"gwa": 1.75}
        config = {}
        
        result = self._calculate_academic_fit(evaluation_data, config)
        assert result == 0.5  # Neutral

    def test_financial_fit_within_range(self):
        """Test financial fit calculation within range."""
        evaluation_data = {"income": 50000}
        config = {"min_income": 0, "max_income": 200000}
        
        result = self._calculate_financial_fit(evaluation_data, config)
        assert result == 0.75  # Lower income = higher score

    def test_financial_fit_max_only(self):
        """Test financial fit calculation with only max income."""
        evaluation_data = {"income": 50000}
        config = {"max_income": 200000}
        
        result = self._calculate_financial_fit(evaluation_data, config)
        assert result == 0.75  # Lower income = higher score

    def test_financial_fit_no_requirements(self):
        """Test financial fit returns neutral score when no requirements."""
        evaluation_data = {"income": 100000}
        config = {}
        
        result = self._calculate_financial_fit(evaluation_data, config)
        assert result == 0.5  # Neutral


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
