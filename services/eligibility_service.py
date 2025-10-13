"""
Unified Scholarship Eligibility Algorithm for iScholar System
===========================================================

This algorithm provides a single, consistent method for evaluating scholarship
eligibility across both prequalification and full evaluation processes.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from services.meta.fuzzy_logic import FuzzyEligibilitySystem

logger = logging.getLogger(__name__)


@dataclass
class ApplicantProfile:
    """Standardized applicant data structure"""
    # Academic Information
    gwa: float
    total_units: int
    year_level: str
    course_id: Optional[int] = None
    department_id: Optional[int] = None
    campus_id: Optional[int] = None

    # Financial Information
    family_income: float
    father_income: float = 0.0
    mother_income: float = 0.0

    # Personal Characteristics
    is_4ps_member: bool = False
    is_indigenous: bool = False
    is_pwd: bool = False
    is_ofw_dependent: bool = False
    is_farmers_child: bool = False

    # Family Information
    siblings_in_college: int = 0
    household_size: int = 1


@dataclass
class ScholarshipCriteria:
    """Standardized scholarship rules structure"""
    # Academic Requirements
    min_gwa: Optional[float] = None
    max_gwa: Optional[float] = None
    min_units: Optional[int] = None
    max_units: Optional[int] = None
    allowed_year_levels: List[str] = None

    # Financial Requirements
    min_income: Optional[float] = None
    max_income: Optional[float] = None

    # Priority Requirements (Hard Filters)
    requires_4ps: bool = False
    requires_indigenous: bool = False
    requires_pwd: bool = False
    requires_ofw: bool = False
    requires_farmers_child: bool = False

    # Preference Criteria (Bonus Points)
    prefers_4ps: bool = False
    prefers_indigenous: bool = False
    prefers_pwd: bool = False
    prefers_ofw: bool = False
    prefers_farmers_child: bool = False

    # Course/Department/Campus Preferences
    preferred_course_ids: List[int] = None
    preferred_department_ids: List[int] = None
    preferred_campus_ids: List[int] = None

    def __post_init__(self):
        """Initialize empty lists for None values"""
        if self.allowed_year_levels is None:
            self.allowed_year_levels = []
        if self.preferred_course_ids is None:
            self.preferred_course_ids = []
        if self.preferred_department_ids is None:
            self.preferred_department_ids = []
        if self.preferred_campus_ids is None:
            self.preferred_campus_ids = []


@dataclass
class EligibilityResult:
    """Standardized eligibility result structure"""
    base_score: float
    bonus_points: float
    final_score: float
    classification: str
    is_eligible: bool
    reasons: List[str]
    factors_breakdown: Dict[str, Any]
    confidence_level: str  # High, Medium, Low


class UnifiedEligibilityEngine:
    """
    Unified eligibility calculation engine that handles both
    prequalification and full evaluation scenarios.
    """

    # Configuration Constants
    BONUS_POINTS = {
        "4ps_member": 5.0,
        "indigenous": 8.0,
        "pwd": 6.0,
        "ofw_dependent": 7.0,
        "farmers_child": 4.0,
        "siblings_in_college": 2.0,  # per sibling, max 8
        "year_level_bonus": 2.0,  # for 3rd+ year
        "preferred_course": 3.0,
        "preferred_department": 2.0,
        "preferred_campus": 1.0
    }

    CLASSIFICATION_THRESHOLDS = {
        "Highly Eligible": 80.0,
        "Eligible": 65.0,
        "Somewhat Eligible": 45.0,
        "Barely Eligible": 25.0,
        "Not Eligible": 0.0
    }

    def __init__(self, fuzzy_system: FuzzyEligibilitySystem):
        self.fuzzy_system = fuzzy_system

    def evaluate_eligibility(self,
                             applicant: ApplicantProfile,
                             scholarship_criteria: Optional[ScholarshipCriteria] = None) -> EligibilityResult:
        """
        Main eligibility evaluation function.

        Args:
            applicant: Applicant's profile data
            scholarship_criteria: Optional specific scholarship rules

        Returns:
            EligibilityResult with complete evaluation
        """

        # Step 1: Calculate base fuzzy logic score
        base_result = self._calculate_base_score(applicant)

        # Step 2: Apply universal bonus points
        bonus_points, bonus_reasons = self._calculate_bonus_points(applicant)

        # Step 3: Apply scholarship-specific adjustments (if provided)
        scholarship_bonus = 0.0
        scholarship_reasons = []
        if scholarship_criteria:
            scholarship_bonus, scholarship_reasons = self._calculate_scholarship_bonus(
                applicant, scholarship_criteria
            )

        # Step 4: Calculate final score (capped at 100)
        total_bonus = bonus_points + scholarship_bonus
        final_score = min(base_result["score"] * 100 + total_bonus, 100.0)

        # Step 5: Determine classification
        classification = self._get_classification(final_score)

        # Step 6: Check hard requirements (if scholarship-specific)
        is_eligible = True
        eligibility_reasons = []

        if scholarship_criteria:
            is_eligible, eligibility_reasons = self._check_hard_requirements(
                applicant, scholarship_criteria
            )

        # Step 7: Compile all reasons
        all_reasons = bonus_reasons + scholarship_reasons + eligibility_reasons

        # Step 8: Create factor breakdown
        factors_breakdown = self._create_factors_breakdown(
            applicant, base_result, bonus_points, scholarship_bonus
        )

        # Step 9: Determine confidence level
        confidence_level = self._determine_confidence_level(final_score, is_eligible)

        return EligibilityResult(
            base_score=base_result["score"] * 100,
            bonus_points=total_bonus,
            final_score=round(final_score, 2),
            classification=classification,
            is_eligible=is_eligible,
            reasons=all_reasons,
            factors_breakdown=factors_breakdown,
            confidence_level=confidence_level
        )

    def _calculate_base_score(self, applicant: ApplicantProfile) -> Dict:
        """Calculate base fuzzy logic score"""
        try:
            result = self.fuzzy_system.evaluate(applicant.gwa, applicant.family_income)
            return result
        except Exception as e:
            logger.error(f"Fuzzy evaluation failed: {e}")
            # Fallback calculation
            gwa_score = max(0, (5.0 - applicant.gwa) / 4.0)  # Normalize GWA to 0-1
            income_factor = max(0, min(1, (100000 - applicant.family_income) / 100000))
            fallback_score = (gwa_score * 0.6 + income_factor * 0.4)
            return {
                "score": fallback_score,
                "classification": self._get_classification(fallback_score * 100)
            }

    def _calculate_bonus_points(self, applicant: ApplicantProfile) -> Tuple[float, List[str]]:
        """Calculate universal bonus points"""
        bonus = 0.0
        reasons = []

        # Special circumstances bonuses
        if applicant.is_4ps_member:
            bonus += self.BONUS_POINTS["4ps_member"]
            reasons.append(f"4Ps Member (+{self.BONUS_POINTS['4ps_member']} points)")

        if applicant.is_indigenous:
            bonus += self.BONUS_POINTS["indigenous"]
            reasons.append(f"Indigenous Person (+{self.BONUS_POINTS['indigenous']} points)")

        if applicant.is_pwd:
            bonus += self.BONUS_POINTS["pwd"]
            reasons.append(f"Person with Disability (+{self.BONUS_POINTS['pwd']} points)")

        if applicant.is_ofw_dependent:
            bonus += self.BONUS_POINTS["ofw_dependent"]
            reasons.append(f"OFW Dependent (+{self.BONUS_POINTS['ofw_dependent']} points)")

        if applicant.is_farmers_child:
            bonus += self.BONUS_POINTS["farmers_child"]
            reasons.append(f"Farmer's Child (+{self.BONUS_POINTS['farmers_child']} points)")

        # Siblings in college bonus (capped at 4 siblings = 8 points)
        if applicant.siblings_in_college > 0:
            sibling_bonus = min(
                applicant.siblings_in_college * self.BONUS_POINTS["siblings_in_college"],
                8.0
            )
            bonus += sibling_bonus
            reasons.append(f"{applicant.siblings_in_college} Siblings in College (+{sibling_bonus} points)")

        # Year level bonus for upperclassmen
        if applicant.year_level in ['3rd Year', '4th Year', '5th Year']:
            bonus += self.BONUS_POINTS["year_level_bonus"]
            reasons.append(f"{applicant.year_level} (+{self.BONUS_POINTS['year_level_bonus']} points)")

        return bonus, reasons

    def _calculate_scholarship_bonus(self,
                                     applicant: ApplicantProfile,
                                     criteria: ScholarshipCriteria) -> Tuple[float, List[str]]:
        """Calculate scholarship-specific preference bonuses"""
        bonus = 0.0
        reasons = []

        # Preference bonuses (not requirements)
        if criteria.prefers_4ps and applicant.is_4ps_member:
            bonus += self.BONUS_POINTS["4ps_member"] * 0.5  # Half-bonus for preferences
            reasons.append("4Ps Member (scholarship preference)")

        if criteria.prefers_indigenous and applicant.is_indigenous:
            bonus += self.BONUS_POINTS["indigenous"] * 0.5
            reasons.append("Indigenous Person (scholarship preference)")

        if criteria.prefers_pwd and applicant.is_pwd:
            bonus += self.BONUS_POINTS["pwd"] * 0.5
            reasons.append("PWD (scholarship preference)")

        if criteria.prefers_ofw and applicant.is_ofw_dependent:
            bonus += self.BONUS_POINTS["ofw_dependent"] * 0.5
            reasons.append("OFW Dependent (scholarship preference)")

        if criteria.prefers_farmers_child and applicant.is_farmers_child:
            bonus += self.BONUS_POINTS["farmers_child"] * 0.5
            reasons.append("Farmer's Child (scholarship preference)")

        # Course/Department/Campus preferences
        if (criteria.preferred_course_ids and
                applicant.course_id in criteria.preferred_course_ids):
            bonus += self.BONUS_POINTS["preferred_course"]
            reasons.append("Preferred Course Match")

        if (criteria.preferred_department_ids and
                applicant.department_id in criteria.preferred_department_ids):
            bonus += self.BONUS_POINTS["preferred_department"]
            reasons.append("Preferred Department Match")

        if (criteria.preferred_campus_ids and
                applicant.campus_id in criteria.preferred_campus_ids):
            bonus += self.BONUS_POINTS["preferred_campus"]
            reasons.append("Preferred Campus Match")

        return bonus, reasons

    def _check_hard_requirements(self,
                                 applicant: ApplicantProfile,
                                 criteria: ScholarshipCriteria) -> Tuple[bool, List[str]]:
        """Check mandatory scholarship requirements"""
        is_eligible = True
        reasons = []

        # GWA Requirements
        if criteria.min_gwa is not None and applicant.gwa < criteria.min_gwa:
            is_eligible = False
            reasons.append(f"GWA {applicant.gwa} below minimum {criteria.min_gwa}")
        elif criteria.max_gwa is not None and applicant.gwa > criteria.max_gwa:
            is_eligible = False
            reasons.append(f"GWA {applicant.gwa} above maximum {criteria.max_gwa}")
        else:
            gwa_range = self._format_range("GWA", criteria.min_gwa, criteria.max_gwa)
            if gwa_range:
                reasons.append(f"GWA {applicant.gwa} meets requirements {gwa_range}")

        # Income Requirements
        if criteria.min_income is not None and applicant.family_income < criteria.min_income:
            is_eligible = False
            reasons.append(f"Income ₱{applicant.family_income:,.2f} below minimum ₱{criteria.min_income:,.2f}")
        elif criteria.max_income is not None and applicant.family_income > criteria.max_income:
            is_eligible = False
            reasons.append(f"Income ₱{applicant.family_income:,.2f} above maximum ₱{criteria.max_income:,.2f}")
        else:
            income_range = self._format_range("Income", criteria.min_income, criteria.max_income)
            if income_range:
                reasons.append(f"Income ₱{applicant.family_income:,.2f} meets requirements {income_range}")

        # Units Requirements
        if criteria.min_units is not None and applicant.total_units < criteria.min_units:
            is_eligible = False
            reasons.append(f"Units {applicant.total_units} below minimum {criteria.min_units}")
        elif criteria.max_units is not None and applicant.total_units > criteria.max_units:
            is_eligible = False
            reasons.append(f"Units {applicant.total_units} above maximum {criteria.max_units}")

        # Year Level Requirements
        if (criteria.allowed_year_levels and
                applicant.year_level not in criteria.allowed_year_levels):
            is_eligible = False
            reasons.append(f"Year level '{applicant.year_level}' not allowed")

        # Hard Priority Requirements
        if criteria.requires_4ps and not applicant.is_4ps_member:
            is_eligible = False
            reasons.append("4Ps membership required")

        if criteria.requires_indigenous and not applicant.is_indigenous:
            is_eligible = False
            reasons.append("Indigenous Person status required")

        if criteria.requires_pwd and not applicant.is_pwd:
            is_eligible = False
            reasons.append("PWD status required")

        if criteria.requires_ofw and not applicant.is_ofw_dependent:
            is_eligible = False
            reasons.append("OFW dependent status required")

        if criteria.requires_farmers_child and not applicant.is_farmers_child:
            is_eligible = False
            reasons.append("Farmer's child status required")

        return is_eligible, reasons

    def _get_classification(self, score: float) -> str:
        """Determine classification based on score"""
        for classification, threshold in self.CLASSIFICATION_THRESHOLDS.items():
            if score >= threshold:
                return classification
        return "Not Eligible"

    def _format_range(self, label: str, min_val: Optional[float], max_val: Optional[float]) -> str:
        """Format range display"""
        if min_val is not None and max_val is not None:
            return f"(range: {min_val}-{max_val})"
        elif min_val is not None:
            return f"(min: {min_val})"
        elif max_val is not None:
            return f"(max: {max_val})"
        return ""

    def _create_factors_breakdown(self,
                                  applicant: ApplicantProfile,
                                  base_result: Dict,
                                  bonus_points: float,
                                  scholarship_bonus: float) -> Dict[str, Any]:
        """Create detailed breakdown of factors"""
        return {
            "gwa_impact": round((5.0 - applicant.gwa) * 20, 2),
            "income_impact": round(max(0, (100000 - applicant.family_income) / 1000), 2),
            "base_fuzzy_score": round(base_result["score"] * 100, 2),
            "universal_bonus": round(bonus_points, 2),
            "scholarship_bonus": round(scholarship_bonus, 2),
            "total_bonus": round(bonus_points + scholarship_bonus, 2),
            "special_circumstances": {
                "is_4ps": applicant.is_4ps_member,
                "is_indigenous": applicant.is_indigenous,
                "is_pwd": applicant.is_pwd,
                "is_ofw_dependent": applicant.is_ofw_dependent,
                "is_farmers_child": applicant.is_farmers_child,
                "siblings_in_college": applicant.siblings_in_college
            }
        }

    def _determine_confidence_level(self, score: float, is_eligible: bool) -> str:
        """Determine confidence level for the result"""
        if not is_eligible:
            return "Low"
        elif score >= 85:
            return "High"
        elif score >= 60:
            return "Medium"
        else:
            return "Low"


# Utility Functions for Integration

def parse_scholarship_config(config_json: str) -> ScholarshipCriteria:
    """Parse JSON scholarship configuration into ScholarshipCriteria object"""
    try:
        config = json.loads(config_json) if isinstance(config_json, str) else config_json

        priorities = config.get("priorities", {})

        return ScholarshipCriteria(
            min_gwa=config.get("min_gwa"),
            max_gwa=config.get("max_gwa"),
            min_units=config.get("min_units_enrolled"),
            max_units=config.get("max_units_enrolled"),
            min_income=config.get("min_income"),
            max_income=config.get("max_income"),
            allowed_year_levels=config.get("preferred_year_levels", []),

            # Requirements
            requires_4ps=priorities.get("must_be_4ps", False),
            requires_indigenous=priorities.get("require_ip", False),
            requires_pwd=priorities.get("require_pwd", False),
            requires_ofw=priorities.get("must_be_ofw", False),
            requires_farmers_child=priorities.get("require_farmers_child", False),

            # Preferences
            prefers_4ps=priorities.get("prefer_4ps", False),
            prefers_indigenous=priorities.get("prefer_ip", False),
            prefers_pwd=priorities.get("prefer_pwd", False),
            prefers_ofw=priorities.get("prefer_ofw", False),
            prefers_farmers_child=priorities.get("prefer_farmers_child", False),

            # Course/Department/Campus preferences
            preferred_course_ids=config.get("preferred_course_ids", []),
            preferred_department_ids=config.get("preferred_department_ids", []),
            preferred_campus_ids=config.get("preferred_campus_ids", [])
        )
    except Exception as e:
        logger.error(f"Failed to parse scholarship config: {e}")
        return ScholarshipCriteria()


def extract_applicant_profile(applicant_data: Dict) -> ApplicantProfile:
    """Extract applicant data into standardized ApplicantProfile"""

    # Calculate total family income
    father_income = applicant_data.get("father_income", 0) or 0
    mother_income = applicant_data.get("mother_income", 0) or 0
    total_income = father_income + mother_income

    # Detect special characteristics
    from utils.utils import smart_detect_flags
    flags = smart_detect_flags(
        applicant_data.get("father_occupation", ""),
        applicant_data.get("mother_occupation", "")
    )

    return ApplicantProfile(
        gwa=float(applicant_data.get("gwa", 0)),
        total_units=int(applicant_data.get("total_units", 0)),
        year_level=applicant_data.get("year_level", ""),
        course_id=applicant_data.get("course_id"),
        department_id=applicant_data.get("department_id"),
        campus_id=applicant_data.get("campus_id"),

        family_income=total_income,
        father_income=father_income,
        mother_income=mother_income,

        is_4ps_member=applicant_data.get("is_4ps_member", False),
        is_indigenous=applicant_data.get("ip_affiliation") not in ("None", "N/A", None, ""),
        is_pwd=applicant_data.get("is_pwd", False),
        is_ofw_dependent=flags.get("is_ofw", False),
        is_farmers_child=flags.get("is_farmers_child", False),

        siblings_in_college=int(applicant_data.get("siblings_studying", 0)),
        household_size=int(applicant_data.get("household_number", 1))
    )