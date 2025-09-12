"""
Enhanced Unified Scholarship Eligibility Algorithm for iScholar System
===================================================================

This algorithm provides a single, consistent method for evaluating scholarship
eligibility with improved performance, error handling, and extensibility.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP
import traceback
from datetime import datetime

logger = logging.getLogger(__name__)


class YearLevel(Enum):
    """Standardized year levels"""
    FIRST = "1st Year"
    SECOND = "2nd Year"
    THIRD = "3rd Year"
    FOURTH = "4th Year"
    FIFTH = "5th Year"


class EligibilityClassification(Enum):
    """Eligibility classifications with thresholds"""
    HIGHLY_ELIGIBLE = ("Highly Eligible", 80.0)
    ELIGIBLE = ("Eligible", 65.0)
    SOMEWHAT_ELIGIBLE = ("Somewhat Eligible", 45.0)
    BARELY_ELIGIBLE = ("Barely Eligible", 25.0)
    NOT_ELIGIBLE = ("Not Eligible", 0.0)

    def __init__(self, label: str, threshold: float):
        self.label = label
        self.threshold = threshold


class ConfidenceLevel(Enum):
    """Confidence levels for eligibility results"""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass
class ApplicantProfile:
    """Enhanced applicant data structure with validation"""
    # Academic Information
    gwa: float
    total_units: int = 0
    year_level: str = ""
    course_id: Optional[int] = None
    department_id: Optional[int] = None
    campus_id: Optional[int] = None

    # Financial Information
    family_income: float = 0.0
    father_income: float = 0.0
    mother_income: float = 0.0

    # Personal Characteristics
    is_4ps_member: bool = False
    is_indigenous: bool = False
    is_pwd: bool = False
    is_ofw_dependent: bool = False
    is_farmers_child: bool = False
    is_solo_parent_child: bool = False
    is_displaced_worker_child: bool = False

    # Family Information
    siblings_in_college: int = 0
    household_size: int = 1

    # Additional metadata
    application_id: Optional[int] = None
    student_id: Optional[str] = None


    def __post_init__(self):
        """Validate and normalize data"""
        self.gwa = max(1.0, min(5.0, float(self.gwa)))
        self.total_units = max(0, int(self.total_units))
        self.family_income = max(0.0, float(self.family_income))
        self.father_income = max(0.0, float(self.father_income))
        self.mother_income = max(0.0, float(self.mother_income))
        self.siblings_in_college = max(0, int(self.siblings_in_college))
        self.household_size = max(1, int(self.household_size))

    @property
    def income_per_capita(self) -> float:
        """Calculate per capita income"""
        return self.family_income / self.household_size if self.household_size > 0 else 0.0

    @property
    def has_special_circumstances(self) -> bool:
        """Check if applicant has any special circumstances"""
        return any([
            self.is_4ps_member, self.is_indigenous, self.is_pwd,
            self.is_ofw_dependent, self.is_farmers_child,
            self.is_solo_parent_child, self.is_displaced_worker_child
        ])


@dataclass
class ScholarshipCriteria:
    """Enhanced scholarship rules structure with validation"""
    # Basic Information
    scholarship_id: Optional[int] = None
    scholarship_name: str = ""

    # Academic Requirements
    min_gwa: Optional[float] = None
    max_gwa: Optional[float] = None
    min_units: Optional[int] = None
    max_units: Optional[int] = None
    allowed_year_levels: List[str] = field(default_factory=list)

    # Financial Requirements
    min_income: Optional[float] = None
    max_income: Optional[float] = None

    # Priority Requirements (Hard Filters)
    requires_4ps: bool = False
    requires_indigenous: bool = False
    requires_pwd: bool = False
    requires_ofw: bool = False
    requires_farmers_child: bool = False
    requires_solo_parent: bool = False
    requires_displaced_worker: bool = False

    # Preference Criteria (Bonus Points)
    prefers_4ps: bool = False
    prefers_indigenous: bool = False
    prefers_pwd: bool = False
    prefers_ofw: bool = False
    prefers_farmers_child: bool = False
    prefers_solo_parent: bool = False
    prefers_displaced_worker: bool = False

    # Institutional Preferences
    preferred_course_ids: List[int] = field(default_factory=list)
    preferred_department_ids: List[int] = field(default_factory=list)
    preferred_campus_ids: List[int] = field(default_factory=list)

    # Additional criteria
    max_applications: Optional[int] = None
    application_deadline: Optional[str] = None

    # Weight adjustments
    academic_weight: float = 0.6
    financial_weight: float = 0.4

    def __post_init__(self):
        """Validate criteria"""
        if self.min_gwa is not None:
            self.min_gwa = max(1.0, min(5.0, self.min_gwa))
        if self.max_gwa is not None:
            self.max_gwa = max(1.0, min(5.0, self.max_gwa))
        if self.min_income is not None:
            self.min_income = max(0.0, self.min_income)
        if self.max_income is not None:
            self.max_income = max(0.0, self.max_income)


@dataclass
class EligibilityResult:
    """Enhanced eligibility result structure"""
    # Core scores
    base_score: float
    bonus_points: float
    final_score: float

    # Classification
    classification: str
    is_eligible: bool

    # Detailed information
    reasons: List[str]
    factors_breakdown: Dict[str, Any]
    confidence_level: str

    # Additional metadata
    evaluation_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "2.0"

    # Recommendations
    improvement_suggestions: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)


class BonusPointsConfig:
    """Configurable bonus points system"""

    SPECIAL_CIRCUMSTANCES = {
        "4ps_member": 8.0,
        "indigenous": 10.0,
        "pwd": 8.0,
        "ofw_dependent": 9.0,
        "farmers_child": 6.0,
        "solo_parent_child": 7.0,
        "displaced_worker_child": 5.0
    }

    FAMILY_FACTORS = {
        "siblings_in_college": 2.0,  # per sibling, max 10
        "large_family": 3.0,  # 6+ members
    }

    ACADEMIC_FACTORS = {
        "year_level_bonus": 2.0,  # for 3rd+ year
        "high_units": 2.0,  # 18+ units
        "excellence": 5.0,  # GWA <= 1.5
    }

    INSTITUTIONAL_PREFERENCES = {
        "preferred_course": 4.0,
        "preferred_department": 3.0,
        "preferred_campus": 2.0
    }

    # Maximum bonus caps
    MAX_SPECIAL_CIRCUMSTANCES = 15.0
    MAX_TOTAL_BONUS = 25.0


class UnifiedEligibilityEngine:
    """Enhanced eligibility calculation engine"""

    def __init__(self, fuzzy_system=None, config: BonusPointsConfig = None):
        self.fuzzy_system = fuzzy_system
        self.config = config or BonusPointsConfig()
        self.evaluation_cache = {}
        self.BONUS_POINTS = {
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

    def evaluate_eligibility(self,
                             applicant: ApplicantProfile,
                             scholarship_criteria: Optional[ScholarshipCriteria] = None,
                             use_cache: bool = True) -> EligibilityResult:
        """
        Main eligibility evaluation function with enhanced error handling and caching.
        """
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(applicant, scholarship_criteria) if use_cache else None

            if cache_key and cache_key in self.evaluation_cache:
                logger.info("Returning cached eligibility result")
                return self.evaluation_cache[cache_key]

            # Step 1: Calculate base fuzzy logic score
            base_result = self._calculate_base_score(applicant)

            # Step 2: Apply universal bonus points
            bonus_points, bonus_reasons = self._calculate_bonus_points(applicant)

            # Step 3: Apply scholarship-specific adjustments
            scholarship_bonus = 0.0
            scholarship_reasons = []
            if scholarship_criteria:
                scholarship_bonus, scholarship_reasons = self._calculate_scholarship_bonus(
                    applicant, scholarship_criteria
                )

            # Step 4: Calculate final score with proper rounding
            total_bonus = min(bonus_points + scholarship_bonus, self.config.MAX_TOTAL_BONUS)
            raw_final_score = base_result["score"] * 100 + total_bonus
            final_score = float(Decimal(str(min(raw_final_score, 100.0))).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            ))

            # Step 5: Determine classification
            classification = self._get_classification(final_score)

            # Step 6: Check hard requirements
            is_eligible = True
            eligibility_reasons = []
            if scholarship_criteria:
                is_eligible, eligibility_reasons = self._check_hard_requirements(
                    applicant, scholarship_criteria
                )

            # Step 7: Generate improvement suggestions
            improvement_suggestions = self._generate_improvement_suggestions(
                applicant, final_score, is_eligible
            )

            # Step 8: Generate next steps
            next_steps = self._generate_next_steps(applicant, is_eligible, scholarship_criteria)

            # Step 9: Compile all reasons
            all_reasons = bonus_reasons + scholarship_reasons + eligibility_reasons

            # Step 10: Create comprehensive factor breakdown
            factors_breakdown = self._create_enhanced_factors_breakdown(
                applicant, base_result, bonus_points, scholarship_bonus
            )

            # Step 11: Determine confidence level
            confidence_level = self._determine_confidence_level(final_score, is_eligible, applicant)

            result = EligibilityResult(
                base_score=round(base_result["score"] * 100, 2),
                bonus_points=round(total_bonus, 2),
                final_score=final_score,
                classification=classification,
                is_eligible=is_eligible,
                reasons=all_reasons,
                factors_breakdown=factors_breakdown,
                confidence_level=confidence_level,
                improvement_suggestions=improvement_suggestions,
                next_steps=next_steps
            )

            # Cache result
            if cache_key:
                self.evaluation_cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"Eligibility evaluation failed: {e}")
            logger.error(traceback.format_exc())
            return self._create_error_result(str(e))

    def batch_evaluate(self,
                       applicants: List[ApplicantProfile],
                       scholarship_criteria: Optional[ScholarshipCriteria] = None) -> List[EligibilityResult]:
        """Evaluate multiple applicants efficiently"""
        results = []
        for applicant in applicants:
            try:
                result = self.evaluate_eligibility(applicant, scholarship_criteria)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to evaluate applicant {applicant.student_id}: {e}")
                results.append(self._create_error_result(str(e)))
        return results

    def _calculate_base_score(self, applicant: ApplicantProfile) -> Dict:
        """Calculate base fuzzy logic score with fallback"""
        try:
            if self.fuzzy_system:
                result = self.fuzzy_system.evaluate(applicant.gwa, applicant.family_income)
                return result
        except Exception as e:
            logger.warning(f"Fuzzy evaluation failed, using fallback: {e}")

        # Enhanced fallback calculation
        gwa_score = self._calculate_gwa_score(applicant.gwa)
        income_score = self._calculate_income_score(applicant.family_income, applicant.household_size)

        fallback_score = (gwa_score * 0.6 + income_score * 0.4)

        return {
            "score": fallback_score,
            "classification": self._get_classification(fallback_score * 100),
            "method": "fallback"
        }

    def _calculate_gwa_score(self, gwa: float) -> float:
        """Calculate normalized GWA score (0-1)"""
        # More nuanced GWA scoring
        if gwa <= 1.5:
            return 1.0
        elif gwa <= 2.0:
            return 0.9
        elif gwa <= 2.5:
            return 0.7
        elif gwa <= 3.0:
            return 0.5
        elif gwa <= 3.5:
            return 0.3
        else:
            return 0.1

    def _calculate_income_score(self, family_income: float, household_size: int) -> float:
        """Calculate income score based on per capita income"""
        per_capita = family_income / household_size if household_size > 0 else family_income

        # Philippine poverty thresholds (simplified)
        if per_capita <= 15000:  # Below poverty line
            return 1.0
        elif per_capita <= 30000:  # Low income
            return 0.8
        elif per_capita <= 60000:  # Lower middle
            return 0.6
        elif per_capita <= 120000:  # Middle income
            return 0.4
        elif per_capita <= 200000:  # Upper middle
            return 0.2
        else:  # High income
            return 0.1

    def _calculate_bonus_points(self, applicant: ApplicantProfile) -> Tuple[float, List[str]]:
        """Calculate enhanced bonus points with caps"""
        bonus = 0.0
        reasons = []

        # Special circumstances bonuses (with cap)
        special_bonus = 0.0

        if applicant.is_4ps_member:
            points = self.config.SPECIAL_CIRCUMSTANCES["4ps_member"]
            special_bonus += points
            reasons.append(f"4Ps Member (+{points} points)")

        if applicant.is_indigenous:
            points = self.config.SPECIAL_CIRCUMSTANCES["indigenous"]
            special_bonus += points
            reasons.append(f"Indigenous Person (+{points} points)")

        if applicant.is_pwd:
            points = self.config.SPECIAL_CIRCUMSTANCES["pwd"]
            special_bonus += points
            reasons.append(f"Person with Disability (+{points} points)")

        if applicant.is_ofw_dependent:
            points = self.config.SPECIAL_CIRCUMSTANCES["ofw_dependent"]
            special_bonus += points
            reasons.append(f"OFW Dependent (+{points} points)")

        if applicant.is_farmers_child:
            points = self.config.SPECIAL_CIRCUMSTANCES["farmers_child"]
            special_bonus += points
            reasons.append(f"Farmer's Child (+{points} points)")

        if applicant.is_solo_parent_child:
            points = self.config.SPECIAL_CIRCUMSTANCES["solo_parent_child"]
            special_bonus += points
            reasons.append(f"Solo Parent's Child (+{points} points)")

        if applicant.is_displaced_worker_child:
            points = self.config.SPECIAL_CIRCUMSTANCES["displaced_worker_child"]
            special_bonus += points
            reasons.append(f"Displaced Worker's Child (+{points} points)")

        # Apply cap to special circumstances
        special_bonus = min(special_bonus, self.config.MAX_SPECIAL_CIRCUMSTANCES)
        bonus += special_bonus

        # Family factors
        if applicant.siblings_in_college > 0:
            sibling_bonus = min(
                applicant.siblings_in_college * self.config.FAMILY_FACTORS["siblings_in_college"],
                10.0  # Max 5 siblings
            )
            bonus += sibling_bonus
            reasons.append(f"{applicant.siblings_in_college} Siblings in College (+{sibling_bonus} points)")

        if applicant.household_size >= 6:
            bonus += self.config.FAMILY_FACTORS["large_family"]
            reasons.append(f"Large Family (6+ members) (+{self.config.FAMILY_FACTORS['large_family']} points)")

        # Academic factors
        if applicant.year_level in ['3rd Year', '4th Year', '5th Year']:
            bonus += self.config.ACADEMIC_FACTORS["year_level_bonus"]
            reasons.append(f"{applicant.year_level} (+{self.config.ACADEMIC_FACTORS['year_level_bonus']} points)")

        if applicant.total_units >= 18:
            bonus += self.config.ACADEMIC_FACTORS["high_units"]
            reasons.append(f"High Unit Load (18+) (+{self.config.ACADEMIC_FACTORS['high_units']} points)")

        if applicant.gwa <= 1.5:
            bonus += self.config.ACADEMIC_FACTORS["excellence"]
            reasons.append(f"Academic Excellence (GWA ≤ 1.5) (+{self.config.ACADEMIC_FACTORS['excellence']} points)")

        return bonus, reasons

    def _generate_improvement_suggestions(self,
                                          applicant: ApplicantProfile,
                                          final_score: float,
                                          is_eligible: bool) -> List[str]:
        """Generate actionable improvement suggestions"""
        suggestions = []

        if not is_eligible or final_score < 70:
            if applicant.gwa > 2.5:
                suggestions.append("Focus on improving academic performance to achieve a lower GWA")

            if applicant.total_units < 15:
                suggestions.append("Consider enrolling in more units to demonstrate academic commitment")

            if not applicant.has_special_circumstances:
                suggestions.append("Ensure all applicable special circumstances are properly documented")

            if applicant.family_income > 100000:
                suggestions.append("Provide detailed documentation of family expenses and financial obligations")

        return suggestions

    def _generate_next_steps(self,
                             applicant: ApplicantProfile,
                             is_eligible: bool,
                             scholarship_criteria: Optional[ScholarshipCriteria]) -> List[str]:
        """Generate next steps for applicant"""
        steps = []

        if is_eligible:
            steps.append("Proceed with complete scholarship application submission")
            steps.append("Prepare all required supporting documents")
            if scholarship_criteria and scholarship_criteria.application_deadline:
                steps.append(f"Submit application before deadline: {scholarship_criteria.application_deadline}")
        else:
            steps.append("Review eligibility requirements and address any deficiencies")
            steps.append("Consider applying for alternative scholarship programs")
            steps.append("Consult with scholarship office for guidance")

        return steps

    def _create_enhanced_factors_breakdown(self,
                                           applicant: ApplicantProfile,
                                           base_result: Dict,
                                           bonus_points: float,
                                           scholarship_bonus: float) -> Dict[str, Any]:
        """Create comprehensive breakdown of factors"""
        return {
            "academic_factors": {
                "gwa": applicant.gwa,
                "gwa_impact": round(self._calculate_gwa_score(applicant.gwa) * 60, 2),
                "total_units": applicant.total_units,
                "year_level": applicant.year_level
            },
            "financial_factors": {
                "family_income": applicant.family_income,
                "per_capita_income": round(applicant.income_per_capita, 2),
                "income_impact": round(self._calculate_income_score(
                    applicant.family_income, applicant.household_size
                ) * 40, 2)
            },
            "scoring_breakdown": {
                "base_fuzzy_score": round(base_result["score"] * 100, 2),
                "universal_bonus": round(bonus_points, 2),
                "scholarship_bonus": round(scholarship_bonus, 2),
                "total_bonus": round(bonus_points + scholarship_bonus, 2)
            },
            "special_circumstances": {
                "is_4ps": applicant.is_4ps_member,
                "is_indigenous": applicant.is_indigenous,
                "is_pwd": applicant.is_pwd,
                "is_ofw_dependent": applicant.is_ofw_dependent,
                "is_farmers_child": applicant.is_farmers_child,
                "is_solo_parent_child": applicant.is_solo_parent_child,
                "is_displaced_worker_child": applicant.is_displaced_worker_child,
                "siblings_in_college": applicant.siblings_in_college
            },
            "family_profile": {
                "household_size": applicant.household_size,
                "per_capita_income": round(applicant.income_per_capita, 2),
                "has_special_circumstances": applicant.has_special_circumstances
            }
        }

    def _determine_confidence_level(self,
                                    score: float,
                                    is_eligible: bool,
                                    applicant: ApplicantProfile) -> str:
        """Enhanced confidence level determination"""
        if not is_eligible:
            return ConfidenceLevel.LOW.value

        # High confidence criteria
        if (score >= 85 and applicant.gwa <= 2.0 and
                applicant.family_income <= 50000):
            return ConfidenceLevel.HIGH.value

        # Medium confidence criteria
        elif (score >= 60 and applicant.gwa <= 3.0 and
              applicant.family_income <= 100000):
            return ConfidenceLevel.MEDIUM.value

        return ConfidenceLevel.LOW.value

    def _check_hard_requirements(self,
                                 applicant: ApplicantProfile,
                                 criteria: ScholarshipCriteria) -> Tuple[bool, List[str]]:
        """Enhanced hard requirements checking"""
        is_eligible = True
        reasons = []

        # Academic requirements
        if criteria.min_gwa is not None and applicant.gwa > criteria.min_gwa:
            is_eligible = False
            reasons.append(f"GWA {applicant.gwa} exceeds maximum {criteria.min_gwa}")

        if criteria.max_gwa is not None and applicant.gwa < criteria.max_gwa:
            is_eligible = False
            reasons.append(f"GWA {applicant.gwa} below minimum {criteria.max_gwa}")

        # Income requirements
        if criteria.max_income is not None and applicant.family_income > criteria.max_income:
            is_eligible = False
            reasons.append(f"Income ₱{applicant.family_income:,.2f} exceeds maximum ₱{criteria.max_income:,.2f}")

        # Year level requirements
        if (criteria.allowed_year_levels and
                applicant.year_level not in criteria.allowed_year_levels):
            is_eligible = False
            reasons.append(f"Year level '{applicant.year_level}' not allowed")

        # Special requirement checks
        requirements = [
            (criteria.requires_4ps, applicant.is_4ps_member, "4Ps membership required"),
            (criteria.requires_indigenous, applicant.is_indigenous, "Indigenous Person status required"),
            (criteria.requires_pwd, applicant.is_pwd, "PWD status required"),
            (criteria.requires_ofw, applicant.is_ofw_dependent, "OFW dependent status required"),
            (criteria.requires_farmers_child, applicant.is_farmers_child, "Farmer's child status required"),
            (criteria.requires_solo_parent, applicant.is_solo_parent_child, "Solo parent's child status required"),
            (criteria.requires_displaced_worker, applicant.is_displaced_worker_child,
             "Displaced worker's child status required")
        ]

        for required, has_status, message in requirements:
            if required and not has_status:
                is_eligible = False
                reasons.append(message)

        return is_eligible, reasons

    def _get_classification(self, score: float) -> str:
        """Get classification from score"""
        for classification in EligibilityClassification:
            if score >= classification.threshold:
                return classification.label
        return EligibilityClassification.NOT_ELIGIBLE.label

    def _generate_cache_key(self,
                            applicant: ApplicantProfile,
                            scholarship_criteria: Optional[ScholarshipCriteria]) -> str:
        """Generate cache key for evaluation"""
        key_parts = [
            str(applicant.gwa),
            str(applicant.family_income),
            str(applicant.year_level),
            str(applicant.has_special_circumstances),
            str(scholarship_criteria.scholarship_id if scholarship_criteria else "general")
        ]
        return "|".join(key_parts)

    def _create_error_result(self, error_message: str) -> EligibilityResult:
        """Create error result"""
        return EligibilityResult(
            base_score=0.0,
            bonus_points=0.0,
            final_score=0.0,
            classification="Error",
            is_eligible=False,
            reasons=[f"Evaluation error: {error_message}"],
            factors_breakdown={"error": error_message},
            confidence_level=ConfidenceLevel.LOW.value,
            improvement_suggestions=["Contact system administrator"],
            next_steps=["Retry evaluation after resolving technical issues"]
        )

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



# Enhanced Utility Functions

def parse_scholarship_config(config_data: Union[str, Dict]) -> ScholarshipCriteria:
    """Enhanced scholarship configuration parser"""
    try:
        if isinstance(config_data, str):
            config = json.loads(config_data)
        else:
            config = config_data

        priorities = config.get("priorities", {})
        preferences = config.get("preferences", {})

        return ScholarshipCriteria(
            scholarship_id=config.get("scholarship_id"),
            scholarship_name=config.get("scholarship_name", ""),

            min_gwa=config.get("min_gwa"),
            max_gwa=config.get("max_gwa"),
            min_units=config.get("min_units_enrolled"),
            max_units=config.get("max_units_enrolled"),
            min_income=config.get("min_income"),
            max_income=config.get("max_income"),

            allowed_year_levels=config.get("allowed_year_levels", []),

            # Requirements
            requires_4ps=priorities.get("must_be_4ps", False),
            requires_indigenous=priorities.get("require_ip", False),
            requires_pwd=priorities.get("require_pwd", False),
            requires_ofw=priorities.get("must_be_ofw", False),
            requires_farmers_child=priorities.get("require_farmers_child", False),
            requires_solo_parent=priorities.get("require_solo_parent", False),
            requires_displaced_worker=priorities.get("require_displaced_worker", False),

            # Preferences
            prefers_4ps=preferences.get("prefer_4ps", False),
            prefers_indigenous=preferences.get("prefer_ip", False),
            prefers_pwd=preferences.get("prefer_pwd", False),
            prefers_ofw=preferences.get("prefer_ofw", False),
            prefers_farmers_child=preferences.get("prefer_farmers_child", False),
            prefers_solo_parent=preferences.get("prefer_solo_parent", False),
            prefers_displaced_worker=preferences.get("prefer_displaced_worker", False),

            # Institutional preferences
            preferred_course_ids=config.get("preferred_course_ids", []),
            preferred_department_ids=config.get("preferred_department_ids", []),
            preferred_campus_ids=config.get("preferred_campus_ids", []),

            # Additional fields
            max_applications=config.get("max_applications"),
            application_deadline=config.get("application_deadline"),
            academic_weight=config.get("academic_weight", 0.6),
            financial_weight=config.get("financial_weight", 0.4)
        )

    except Exception as e:
        logger.error(f"Failed to parse scholarship config: {e}")
        return ScholarshipCriteria()


def extract_applicant_profile(applicant_data: Dict) -> ApplicantProfile:
    """Enhanced applicant profile extraction"""
    try:
        # Calculate incomes with validation
        father_income = max(0, float(applicant_data.get("father_income", 0) or 0))
        mother_income = max(0, float(applicant_data.get("mother_income", 0) or 0))
        total_income = father_income + mother_income

        # Enhanced flag detection
        flags = detect_special_circumstances(
            applicant_data.get("father_occupation", ""),
            applicant_data.get("mother_occupation", ""),
            applicant_data.get("guardian_occupation", ""),
            applicant_data.get("additional_info", "")
        )

        return ApplicantProfile(
            gwa=float(applicant_data.get("gwa", 5.0)),
            total_units=int(applicant_data.get("total_units", 0)),
            year_level=applicant_data.get("year_level", ""),
            course_id=applicant_data.get("course_id"),
            department_id=applicant_data.get("department_id"),
            campus_id=applicant_data.get("campus_id"),

            family_income=total_income,
            father_income=father_income,
            mother_income=mother_income,

            is_4ps_member=bool(applicant_data.get("is_4ps_member", False)),
            is_indigenous=applicant_data.get("ip_affiliation") not in ("None", "N/A", None, ""),
            is_pwd=bool(applicant_data.get("is_pwd", False)),
            is_ofw_dependent=flags.get("is_ofw", False),
            is_farmers_child=flags.get("is_farmers_child", False),
            is_solo_parent_child=flags.get("is_solo_parent_child", False),
            is_displaced_worker_child=flags.get("is_displaced_worker_child", False),

            siblings_in_college=int(applicant_data.get("siblings_studying", 0)),
            household_size=int(applicant_data.get("household_number", 1)),

            application_id=applicant_data.get("application_id"),
            student_id=applicant_data.get("student_id")
        )

    except Exception as e:
        logger.error(f"Failed to extract applicant profile: {e}")
        # Return minimal profile
        return ApplicantProfile(gwa=5.0)


def detect_special_circumstances(father_occ: str, mother_occ: str,
                                 guardian_occ: str = "", additional_info: str = "") -> Dict[str, bool]:
    """Enhanced special circumstances detection"""
    text_to_analyze = f"{father_occ} {mother_occ} {guardian_occ} {additional_info}".lower()

    flags = {
        "is_ofw": any(keyword in text_to_analyze for keyword in [
            "ofw", "overseas", "abroad", "dubai", "saudi", "singapore", "qatar",
            "seaman", "seafarer", "caregiver abroad", "nurse abroad"
        ]),
        "is_farmers_child": any(keyword in text_to_analyze for keyword in [
            "farmer", "farming", "agriculture", "rice", "corn", "vegetable",
            "livestock", "poultry", "fisherman", "fishing"
        ]),
        "is_solo_parent_child": any(keyword in text_to_analyze for keyword in [
            "solo parent", "single parent", "widow", "widower", "separated",
            "single mother", "single father"
        ]),
        "is_displaced_worker_child": any(keyword in text_to_analyze for keyword in [
            "displaced", "retrenched", "laid off", "unemployed", "jobless",
            "terminated", "redundancy"
        ])
    }

    return flags
