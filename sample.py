# sample_usage.py
from storage import get_connection
from test import (
    UnifiedEligibilityEngine, ApplicantProfile, ScholarshipCriteria,
    parse_scholarship_config, extract_applicant_profile, BonusPointsConfig
)

from services.meta.fuzzy_logic import FuzzyEligibilitySystem

def main():
    # Initialize the system
    fuzzy_system = FuzzyEligibilitySystem(get_connection)  # Your existing fuzzy system
    config = BonusPointsConfig()  # Use default config or customize
    engine = UnifiedEligibilityEngine(fuzzy_system, config)

    print("=== iScholar Eligibility Evaluation Demo ===\n")

    # Example 1: General eligibility check (no specific scholarship)
    print("1. General Eligibility Check")
    print("-" * 40)

    applicant_data = {
        "gwa": 1.25,
        "total_units": 18,
        "year_level": "3rd Year",
        "course_id": 1,
        "department_id": 5,
        "campus_id": 1,
        "father_income": 100,
        "mother_income": 8000,
        "father_occupation": "Farmer",
        "mother_occupation": "Housewife",
        "is_4ps_member": False,
        "is_pwd": True,
        "ip_affiliation": None,
        "siblings_studying": 0,
        "household_number": 0,
        "student_id": "2021-1234",
        "application_id": 2
    }

    applicant = extract_applicant_profile(applicant_data)
    result = engine.evaluate_eligibility(applicant)

    print(f"Student ID: {applicant.student_id}")
    print(f"GWA: {applicant.gwa}")
    print(f"Family Income: ₱{applicant.family_income:,.2f}")
    print(f"Final Score: {result.final_score}")
    print(f"Classification: {result.classification}")
    print(f"Is Eligible: {result.is_eligible}")
    print(f"Confidence: {result.confidence_level}")
    print("\nReasons:")
    for reason in result.reasons:
        print(f"  • {reason}")

    if result.improvement_suggestions:
        print("\nImprovement Suggestions:")
        for suggestion in result.improvement_suggestions:
            print(f"  • {suggestion}")

    print("\nNext Steps:")
    for step in result.next_steps:
        print(f"  • {step}")

    # Example 2: Scholarship-specific evaluation
    print("\n" + "=" * 60)
    print("2. Scholarship-Specific Evaluation")
    print("-" * 40)

    # Define scholarship criteria
    scholarship_config = {
        "scholarship_id": 123,
        "scholarship_name": "Academic Excellence Scholarship for Indigenous Students",
        "max_gwa": 2.0,  # Must have GWA of 2.0 or better
        "max_income": 50000,  # Family income must be below ₱50,000
        "allowed_year_levels": ["2nd Year", "3rd Year", "4th Year"],
        "priorities": {
            "require_ip": True,  # Must be indigenous
            "prefer_4ps": True  # Preference for 4Ps members
        },
        "preferences": {
            "prefer_4ps": True
        },
        "preferred_course_ids": [101, 102, 103],
        "application_deadline": "2025-12-31",
        "max_applications": 50
    }

    # Test with indigenous student
    indigenous_student_data = {
        "gwa": 1.5,
        "total_units": 21,
        "year_level": "3rd Year",
        "course_id": 101,  # Preferred course
        "father_income": 12000,
        "mother_income": 8000,
        "father_occupation": "Farmer",
        "is_4ps_member": True,
        "ip_affiliation": "Igorot",
        "siblings_studying": 1,
        "household_number": 5,
        "student_id": "2021-5678"
    }

    scholarship_criteria = parse_scholarship_config(scholarship_config)
    indigenous_applicant = extract_applicant_profile(indigenous_student_data)
    scholarship_result = engine.evaluate_eligibility(indigenous_applicant, scholarship_criteria)

    print(f"Scholarship: {scholarship_criteria.scholarship_name}")
    print(f"Student ID: {indigenous_applicant.student_id}")
    print(f"GWA: {indigenous_applicant.gwa}")
    print(f"Indigenous: {indigenous_applicant.is_indigenous}")
    print(f"4Ps Member: {indigenous_applicant.is_4ps_member}")
    print(f"Final Score: {scholarship_result.final_score}")
    print(f"Classification: {scholarship_result.classification}")
    print(f"Is Eligible: {scholarship_result.is_eligible}")
    print(f"Confidence: {scholarship_result.confidence_level}")

    print("\nDetailed Breakdown:")
    factors = scholarship_result.factors_breakdown
    print(f"  Base Score: {scholarship_result.base_score}")
    print(f"  Bonus Points: {scholarship_result.bonus_points}")

    # Example 3: Batch evaluation
    print("\n" + "=" * 60)
    print("3. Batch Evaluation")
    print("-" * 40)

    batch_applicants = [
        extract_applicant_profile({
            "gwa": 2.1, "total_units": 15, "year_level": "2nd Year",
            "father_income": 25000, "mother_income": 15000,
            "is_4ps_member": False, "student_id": "2021-1001"
        }),
        extract_applicant_profile({
            "gwa": 1.8, "total_units": 18, "year_level": "3rd Year",
            "father_income": 18000, "mother_income": 12000,
            "is_4ps_member": True, "is_pwd": True, "student_id": "2021-1002"
        }),
        extract_applicant_profile({
            "gwa": 2.5, "total_units": 12, "year_level": "1st Year",
            "father_income": 45000, "mother_income": 20000,
            "student_id": "2021-1003"
        })
    ]

    batch_results = engine.batch_evaluate(batch_applicants, scholarship_criteria)

    print("Batch Evaluation Results:")
    print(f"{'Student ID':<12} {'GWA':<5} {'Score':<6} {'Classification':<18} {'Eligible':<8}")
    print("-" * 65)

    for applicant, result in zip(batch_applicants, batch_results):
        print(f"{applicant.student_id:<12} {applicant.gwa:<5} "
              f"{result.final_score:<6.1f} {result.classification:<18} {result.is_eligible}")

    # Example 4: Custom configuration
    print("\n" + "=" * 60)
    print("4. Custom Bonus Points Configuration")
    print("-" * 40)

    # Create custom configuration with higher bonuses for PWD
    custom_config = BonusPointsConfig()
    custom_config.SPECIAL_CIRCUMSTANCES["pwd"] = 15.0  # Higher bonus for PWD
    custom_config.SPECIAL_CIRCUMSTANCES["indigenous"] = 12.0

    custom_engine = UnifiedEligibilityEngine(fuzzy_system, custom_config)

    pwd_student_data = {
        "gwa": 2.3,
        "total_units": 15,
        "year_level": "2nd Year",
        "father_income": 20000,
        "mother_income": 10000,
        "is_pwd": True,
        "is_4ps_member": True,
        "student_id": "2021-PWD-001"
    }

    pwd_applicant = extract_applicant_profile(pwd_student_data)

    # Compare standard vs custom configuration
    standard_result = engine.evaluate_eligibility(pwd_applicant)
    custom_result = custom_engine.evaluate_eligibility(pwd_applicant)

    print(f"PWD Student Comparison:")
    print(f"Standard Config Score: {standard_result.final_score}")
    print(f"Custom Config Score: {custom_result.final_score}")
    print(f"Difference: +{custom_result.final_score - standard_result.final_score:.1f} points")


if __name__ == "__main__":
    main()
