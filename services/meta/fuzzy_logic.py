from typing import Dict, Any, List
import logging


class FuzzyEligibilitySystem:
    """
    A fuzzy logic system for determining eligibility based on GWA and income.

    This extended version dynamically loads membership functions and rules
    from the MySQL database instead of using hardcoded values.

    Lower GWA values indicate better academic performance.
    """

    def __init__(self, get_connection_func):
        """
        Initializes the system by loading configuration from database.

        Args:
            get_connection_func: Function that returns a database connection
        """
        self.get_connection = get_connection_func
        self.membership_functions = {}
        self.classifications = {}
        self.rules = []
        self.score_classifications = {}  # Maps scores to descriptions from database
        self._load_from_database()

    def _load_from_database(self):
        """Load membership functions and rules from the database."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Load membership functions
            self._load_membership_functions(cursor)

            # Load rules
            self._load_rules(cursor)

            self._load_classifications(cursor)

            cursor.close()
            conn.close()

            logging.info(f"Loaded {len(self.membership_functions)} variables and {len(self.rules)} rules from database")

        except Exception as e:
            logging.error(f"Error loading fuzzy data from database: {e}")
            raise

    def _load_classifications(self, cursor):
        """
        Load consequent values and descriptions from fuzzy_rules table.
        """

        cursor.execute("SELECT consequent_value, description FROM fuzzy_rules")
        rows = cursor.fetchall()

        # store as sorted list of tuples (score, label)
        self.classifications = sorted(
            [(float(row["consequent_value"]), row["description"]) for row in rows],
            key=lambda x: x[0],
            reverse=True
        )

        cursor.close()

    def _load_membership_functions(self, cursor):
        """
        Load membership functions from fuzzy_variables and fuzzy_sets tables.

        Builds self.membership_functions dict in format:
        {
            "gwa": {
                "high": [0.75, 1.0, 1.5],
                "medium": [1.25, 1.75, 2.25],
                "low": [2.0, 2.5, 3.25]
            },
            "income": {
                "low": [0, 7500, 15000],
                "medium": [10000, 25000, 40000],
                "high": [30000, 65000, 100000]
            }
        }
        """
        query = """
                SELECT fv.variable_name, \
                       fs.set_name, \
                       fs.param_a, \
                       fs.param_b, \
                       fs.param_c
                FROM fuzzy_variables fv
                         JOIN fuzzy_sets fs ON fv.variable_id = fs.variable_id
                ORDER BY fv.variable_name, fs.set_name \
                """

        cursor.execute(query)
        rows = cursor.fetchall()

        self.membership_functions = {}

        for row in rows:

            # Initialize variable dict if not exists
            if row['variable_name'] not in self.membership_functions:
                self.membership_functions[row['variable_name']] = {}

            # Store triangular membership function parameters [a, b, c]
            self.membership_functions[row['variable_name']][row['set_name']] = [
                float(row['param_a']), float(row['param_b']), float(row['param_c'])
            ]

    def _load_rules(self, cursor):
        """
        Load fuzzy rules from fuzzy_rules and fuzzy_rule_conditions tables.

        Builds self.rules list in format:
        [
            {"if": {"gwa": "high", "income": "low"}, "then": 1.0},
            {"if": {"gwa": "high", "income": "medium"}, "then": 0.9},
            ...
        ]
        """
        query = """
                SELECT fr.rule_id, 
                       fr.consequent_value, 
                       fr.description, 
                       fv.variable_name, 
                       fs.set_name
                FROM fuzzy_rules fr
                         JOIN fuzzy_rule_conditions frc ON fr.rule_id = frc.rule_id
                         JOIN fuzzy_sets fs ON frc.set_id = fs.set_id
                         JOIN fuzzy_variables fv ON fs.variable_id = fv.variable_id
                ORDER BY fr.rule_id, fv.variable_name 
                """

        cursor.execute(query)
        rows = cursor.fetchall()

        # Group rules by rule_id
        rules_dict = {}
        for row in rows:

            if row['rule_id'] not in rules_dict:
                rules_dict[row['rule_id']] = {
                    'consequent': float(row['consequent_value']),
                    'description': row['description'],
                    'conditions': {}
                }

            rules_dict[row['rule_id']]['conditions'][row['variable_name']] = row['set_name']

        # Convert to the expected format
        self.rules = []
        for rule_id, rule_data in rules_dict.items():
            rule = {
                'if': rule_data['conditions'],
                'then': rule_data['consequent']
            }
            self.rules.append(rule)

    def reload_from_database(self):
        """Reload configuration from database (useful after admin changes)."""
        self._load_from_database()

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
        if variable_name not in self.membership_functions:
            raise ValueError(f"Variable '{variable_name}' not found in membership functions")

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
        if not self.rules:
            raise ValueError("No fuzzy rules loaded")

        # 1. Fuzzification: Get membership degrees for all inputs.
        gwa_memberships = self._fuzzify('gwa', gwa)
        income_memberships = self._fuzzify('income', income)

        # 2. Rule Evaluation & Defuzzification (Weighted Average Method)
        numerator = 0.0
        denominator = 0.0

        for rule in self.rules:
            antecedents = rule['if']
            consequent = rule['then']

            # Calculate rule strength using AND operator (minimum)
            strength_values = []

            # Check each condition in the rule
            for variable_name, set_name in antecedents.items():
                if variable_name == 'gwa':
                    strength_values.append(gwa_memberships.get(set_name, 0.0))
                elif variable_name == 'income':
                    strength_values.append(income_memberships.get(set_name, 0.0))
                else:
                    # For extensibility - other variables
                    strength_values.append(0.0)

            # Rule strength is minimum of all antecedent strengths
            strength = min(strength_values) if strength_values else 0.0

            # If the rule has any strength, apply it.
            if strength > 0:
                numerator += strength * consequent
                denominator += strength

        # Avoid division by zero if no rules are fired.
        return numerator / denominator if denominator != 0 else 0.0

    def classify(self, score: float) -> str:
        """
        Classify a score using fuzzy_rules table instead of hardcoding thresholds.
        Picks the description with the nearest score not greater than input.
        """
        if not hasattr(self, "classifications") or not self.classifications:
            return "Not Eligible"

        for threshold, label in self.classifications:
            if score >= threshold:
                return label

        return "Not Eligible"

    def evaluate(self, gwa: float, income: float) -> Dict[str, Any]:
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
            },
            'fired_rules': self._get_fired_rules(gwa, income)
        }

        return result

    def _get_fired_rules(self, gwa: float, income: float) -> List[Dict[str, Any]]:
        """
        Get information about which rules were fired and their strength.

        Args:
            gwa: The GWA value.
            income: The income value.

        Returns:
            List of fired rules with their strength and conditions.
        """
        gwa_memberships = self._fuzzify('gwa', gwa)
        income_memberships = self._fuzzify('income', income)

        fired_rules = []

        for i, rule in enumerate(self.rules):
            antecedents = rule['if']

            # Calculate rule strength
            strength_values = []
            for variable_name, set_name in antecedents.items():
                if variable_name == 'gwa':
                    strength_values.append(gwa_memberships.get(set_name, 0.0))
                elif variable_name == 'income':
                    strength_values.append(income_memberships.get(set_name, 0.0))

            strength = min(strength_values) if strength_values else 0.0

            if strength > 0:
                fired_rules.append({
                    'rule_index': i + 1,
                    'conditions': antecedents,
                    'strength': round(strength, 4),
                    'consequent': rule['then'],
                    'contribution': round(strength * rule['then'], 4)
                })

        return fired_rules

