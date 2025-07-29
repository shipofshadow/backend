
from typing import Dict, Any, List, Tuple

class FuzzyEligibilitySystem:
    """
    A fuzzy logic system for determining eligibility based on GWA and income.

    This improved version is configuration-driven. The membership functions and
    rules are defined in data structures, making the system more flexible and
    easier to maintain without changing the core logic.

    Lower GWA values indicate better academic performance.
    """

    def __init__(self):
        """Initializes the system with a defined configuration."""
        # Define membership functions as data: {'variable': {'set_name': [params]}}
        self.membership_functions = {
            'gwa': {
                # Format: [left_boundary, peak, right_boundary]
                'high': [0.75, 1.0, 1.5],   # High performance (low GWA value)
                'medium': [1.25, 1.75, 2.25],
                'low': [2.0, 2.5, 3.25]     # Low performance (high GWA value)
            },
            'income': {
                # Format: [left_boundary, peak, right_boundary]
                'low': [0, 7500, 15000],
                'medium': [10000, 25000, 40000],
                'high': [30000, 65000, 100000]
            }
        }

        # Define rules as data for easy modification.
        # This is a zero-order Sugeno-style rule base.
        self.rules = [
            {'if': {'gwa': 'high',   'income': 'low'},    'then': 1.0}, # Highly Eligible
            {'if': {'gwa': 'high',   'income': 'medium'}, 'then': 0.9},
            {'if': {'gwa': 'high',   'income': 'high'},   'then': 0.6},

            {'if': {'gwa': 'medium', 'income': 'low'},    'then': 0.8},
            {'if': {'gwa': 'medium', 'income': 'medium'}, 'then': 0.6},
            {'if': {'gwa': 'medium', 'income': 'high'},   'then': 0.4},

            {'if': {'gwa': 'low',    'income': 'low'},    'then': 0.5},
            {'if': {'gwa': 'low',    'income': 'medium'}, 'then': 0.3},
            {'if': {'gwa': 'low',    'income': 'high'},   'then': 0.1}, # Least Eligible
        ]

    @staticmethod
    def _triangular(x: float, params: List[float]) -> float:
        """
        Triangular membership function.

        Args:
            x: Input value.
            params: A list containing [a, b, c] for the triangle's points.

        Returns:
            Membership degree (from 0.0 to 1.0).
        """
        a, b, c = params
        if x <= a or x >= c:
            return 0.0
        if x == b:
            return 1.0
        if a < x < b:
            return (x - a) / (b - a)
        return (c - x) / (c - b)

    def _fuzzify(self, variable_name: str, value: float) -> Dict[str, float]:
        """
        Calculates the membership degrees for a given input variable.

        Args:
            variable_name: The name of the input variable (e.g., 'gwa').
            value: The crisp input value.

        Returns:
            A dictionary mapping membership set names to their degrees.
            e.g., {'low': 0.0, 'medium': 0.8, 'high': 0.2}
        """
        memberships = {}
        for set_name, params in self.membership_functions[variable_name].items():
            memberships[set_name] = self._triangular(value, params)
        return memberships

    def compute_score(self, gwa: float, income: float) -> float:
        """
        Computes the final eligibility score using fuzzy inference.

        Args:
            gwa: The student's GWA value.
            income: The family's monthly income in PHP.

        Returns:
            The crisp eligibility score (from 0.0 to 1.0).
        """
        # 1. Fuzzification: Get membership degrees for all inputs.
        gwa_memberships = self._fuzzify('gwa', gwa)
        income_memberships = self._fuzzify('income', income)

        # 2. Rule Evaluation & Defuzzification (Weighted Average Method)
        numerator = 0.0
        denominator = 0.0

        for rule in self.rules:
            antecedents = rule['if']
            consequent = rule['then']

            # Find the strength of the rule using the 'AND' operator (min).
            strength = min(
                gwa_memberships[antecedents['gwa']],
                income_memberships[antecedents['income']]
            )

            # If the rule has any strength, apply it.
            if strength > 0:
                numerator += strength * consequent
                denominator += strength

        # Avoid division by zero if no rules are fired.
        return numerator / denominator if denominator != 0 else 0.0

    def classify(self, score: float) -> str:
        """
        Classifies a score into a human-readable eligibility category.

        Args:
            score: The eligibility score (0.0 to 1.0).

        Returns:
            The eligibility category as a string.
        """
        if score >= 0.75:
            return "High Eligibility"
        if score >= 0.5:
            return "Medium Eligibility"
        if score >= 0.25:
            return "Low Eligibility"
        return "Not Eligible"

    def evaluate(self, gwa: float, income: float, verbose: bool = False) -> Dict[str, Any]:
        """
        Performs a complete eligibility evaluation from inputs to final classification.

        Args:
            gwa: The GWA value.
            income: The income value in PHP.
            verbose: If True, prints a detailed breakdown of the evaluation.

        Returns:
            A dictionary containing the complete results.
        """
        score = self.compute_score(gwa, income)
        classification = self.classify(score)
        gwa_memberships = self._fuzzify('gwa', gwa)
        income_memberships = self._fuzzify('income', income)

        result = {
            'inputs': {'gwa': gwa, 'income': income},
            'score': score,
            'classification': classification,
            'memberships': {
                'gwa': gwa_memberships,
                'income': income_memberships
            }
        }

        if verbose:
            print(f"\n--- Eligibility Evaluation ---")
            print(f"Inputs:")
            print(f"  GWA: {gwa}")
            print(f"  Income: PHP {income:,.2f}")
            print("\nFuzzification Results:")
            print(f"  GWA Memberships: {gwa_memberships}")
            print(f"  Income Memberships: {income_memberships}")
            print("\nFinal Result:")
            print(f"  Eligibility Score: {score:.4f}")
            print(f"  Classification: {classification}")
            print("----------------------------")

        return result

# --- Example Usage ---
if __name__ == "__main__":
    fuzzy_system = FuzzyEligibilitySystem()

    while True:
        print("\nEnter student data to evaluate eligibility (or type 'exit' to quit):")
        try:
            gwa_input_str = input("GWA (e.g., 1.25): ")
            if gwa_input_str.lower() == 'exit':
                break
            gwa_input = float(gwa_input_str)

            income_input_str = input("Monthly Family Income (PHP): ")
            if income_input_str.lower() == 'exit':
                break
            income_input = float(income_input_str)

        except ValueError:
            print("\n[Error] Invalid input. Please enter numeric values.")
            continue

        # Evaluate eligibility with a detailed printout.
        fuzzy_system.evaluate(gwa_input, income_input, verbose=True)

        # Ask to continue
        again = input("\nDo you want to evaluate another? (y/n): ").strip().lower()
        if again != 'y':
            print("Exiting...")
            break