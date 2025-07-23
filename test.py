class FuzzyEligibilitySystem:
    """
    A fuzzy logic system for determining eligibility based on GWA and income.
    Lower GWA values indicate better performance.
    """

    def __init__(self):
        pass

    @staticmethod
    def triangular(x, a, b, c):
        """
        Triangular membership function.

        Args:
            x: Input value
            a: Left boundary
            b: Peak (maximum membership)
            c: Right boundary

        Returns:
            Membership degree (0.0 to 1.0)
        """
        if x <= a or x >= c:
            return 0.0
        elif x == b:
            return 1.0
        elif x < b:
            return (x - a) / (b - a)
        else:
            return (c - x) / (c - b)

    def gwa_high(self, gwa):
        """High GWA membership (better performance)"""
        return self.triangular(gwa, 0.75, 1.0, 1.5)

    def gwa_medium(self, gwa):
        """Medium GWA membership"""
        return self.triangular(gwa, 1.25, 1.75, 2.25)

    def gwa_low(self, gwa):
        """Low GWA membership (worse performance)"""
        return self.triangular(gwa, 2.0, 2.5, 3.25)

    def income_low(self, income):
        """Low income membership (in PHP)"""
        return self.triangular(income, 0, 7500, 15000)

    def income_medium(self, income):
        """Medium income membership (in PHP)"""
        return self.triangular(income, 10000, 25000, 40000)

    def income_high(self, income):
        """High income membership (in PHP)"""
        return self.triangular(income, 30000, 65000, 100000)

    def get_gwa_memberships(self, gwa):
        """
        Get all GWA membership degrees for a given value.

        Args:
            gwa: GWA value

        Returns:
            dict: Dictionary with membership degrees for each category
        """
        return {
            'low': self.gwa_low(gwa),
            'medium': self.gwa_medium(gwa),
            'high': self.gwa_high(gwa)
        }

    def get_income_memberships(self, income):
        """
        Get all income membership degrees for a given value.

        Args:
            income: Income value in PHP

        Returns:
            dict: Dictionary with membership degrees for each category
        """
        return {
            'low': self.income_low(income),
            'medium': self.income_medium(income),
            'high': self.income_high(income)
        }

    def compute_eligibility(self, gwa, income):
        """
        Compute eligibility score using fuzzy logic rules.

        Args:
            gwa: GWA value (lower is better)
            income: Income in PHP

        Returns:
            float: Eligibility score (0.0 to 1.0)
        """
        # Get membership degrees
        gwa_l = self.gwa_low(gwa)
        gwa_m = self.gwa_medium(gwa)
        gwa_h = self.gwa_high(gwa)

        inc_l = self.income_low(income)
        inc_m = self.income_medium(income)
        inc_h = self.income_high(income)

        # Rule base: (min(antecedents), output value)
        rules = [
            (min(gwa_h, inc_l), 1.0),  # High GWA, Low Income → Highly Eligible
            (min(gwa_h, inc_m), 0.9),
            (min(gwa_h, inc_h), 0.6),

            (min(gwa_m, inc_l), 0.8),
            (min(gwa_m, inc_m), 0.6),
            (min(gwa_m, inc_h), 0.4),

            (min(gwa_l, inc_l), 0.5),
            (min(gwa_l, inc_m), 0.3),
            (min(gwa_l, inc_h), 0.1),
        ]

        # Calculate weighted average using centroid defuzzification
        numerator = sum(weight * strength for strength, weight in rules)
        denominator = sum(strength for strength, _ in rules)

        return numerator / denominator if denominator != 0 else 0.0

    def classify(self, score):
        """
        Classify eligibility score into categories.

        Args:
            score: Eligibility score (0.0 to 1.0)

        Returns:
            str: Eligibility category
        """
        if score >= 0.75:
            return "High Eligibility"
        elif score >= 0.5:
            return "Medium Eligibility"
        elif score >= 0.25:
            return "Low Eligibility"
        else:
            return "Not Eligible"

    def evaluate(self, gwa, income, verbose=False):
        """
        Complete evaluation of eligibility.

        Args:
            gwa: GWA value
            income: Income in PHP
            verbose: If True, print detailed information

        Returns:
            dict: Dictionary with score, classification, and memberships
        """
        score = self.compute_eligibility(gwa, income)
        classification = self.classify(score)
        gwa_memberships = self.get_gwa_memberships(gwa)
        income_memberships = self.get_income_memberships(income)

        result = {
            'gwa': gwa,
            'income': income,
            'score': score,
            'classification': classification,
            'gwa_memberships': gwa_memberships,
            'income_memberships': income_memberships
        }

        if verbose:
            print(f"GWA: {gwa}")
            print(f"Income: PHP {income:,}")
            print(f"Eligibility Score: {score:.2f}")
            print(f"Result: {classification}")
            print("\nGWA Memberships:")
            print(f"  Low:    {gwa_memberships['low']:.2f}")
            print(f"  Medium: {gwa_memberships['medium']:.2f}")
            print(f"  High:   {gwa_memberships['high']:.2f}")
            print("\nIncome Memberships:")
            print(f"  Low:    {income_memberships['low']:.2f}")
            print(f"  Medium: {income_memberships['medium']:.2f}")
            print(f"  High:   {income_memberships['high']:.2f}")

        return result


# Example usage
if __name__ == "__main__":
    # Create an instance of the fuzzy system
    fuzzy_system = FuzzyEligibilitySystem()

    while True:
        print("\nEnter student data to evaluate eligibility:")
        try:
            gwa_input = float(input("GWA (e.g. 1.25): "))
            income_input = float(input("Monthly Family Income (PHP): "))
        except ValueError:
            print("Invalid input. Please enter numeric values.")
            continue

        # Evaluate eligibility
        result = fuzzy_system.evaluate(gwa_input, income_input, verbose=True)

        # Individual method calls
        print("\n--- Individual Method Calls ---")
        score = fuzzy_system.compute_eligibility(gwa_input, income_input)
        classification = fuzzy_system.classify(score)
        print(f"Score: {score:.2f}, Classification: {classification}")

        # Ask to continue
        again = input("\nDo you want to evaluate another? (y/n): ").strip().lower()
        if again != 'y':
            print("Exiting...")
            break
