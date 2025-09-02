
from typing import Dict, Any, List

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
        if score >= 0.85:
            return "Highly Eligible"
        elif score >= 0.65:
            return "Eligible"
        elif score >= 0.45:
            return "Somewhat Eligible"
        elif score >= 0.25:
            return "Barely Eligible"
        elif score > 0.0:
            return "Very Low Eligibility"
        return "Not Eligible"

    def evaluate(self, gwa: float, income: float,) -> Dict[str, Any]:
        """
        Performs a complete eligibility evaluation from inputs to final classification.

        Args:
            gwa: The GWA value.
            income: The income value in PHP.

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

        return result
