from flask import Blueprint, request, jsonify
from db import get_connection

fuzzy_bp = Blueprint("fuzzy_bp", __name__, url_prefix="/api/fuzzy")

# Return the rules
@fuzzy_bp.route('/rules', methods=['GET'])
def get_fuzzy_rules():
    db = get_connection()
    cursor = db.cursor()

    try:
        # Fetch all rules
        cursor.execute("""
            SELECT
                fr.rule_id,
                fr.consequent_value,
                fv.variable_name,
                fs.set_name
            FROM fuzzy_rules fr
            JOIN fuzzy_rule_conditions frc ON frc.rule_id = fr.rule_id
            JOIN fuzzy_sets fs ON fs.set_id = frc.set_id
            JOIN fuzzy_variables fv ON fv.variable_id = fs.variable_id
        """)
        rows = cursor.fetchall()

        # Group by rule_id
        rule_map = {}
        for row in rows:
            rid = row['rule_id']
            if rid not in rule_map:
                rule_map[rid] = {
                    'if': {},
                    'then': float(row['consequent_value'])
                }
            rule_map[rid]['if'][row['variable_name']] = row['set_name']

        rules = list(rule_map.values())
        return jsonify(rules), 200

    except Exception as e:
        print(f"[ERROR] get_fuzzy_rules: {e}")
        return jsonify({"error": "Failed to fetch fuzzy rules"}), 500
    finally:
        cursor.close()
        db.close()

@fuzzy_bp.route('/fuzzy-config', methods=['GET'])
def get_fuzzy_config():
    db = get_connection()
    cursor = db.cursor()
    try:
        cursor.execute("""
            SELECT
                fuzzy_sets.set_id,
                fuzzy_sets.variable_id,
                fuzzy_sets.set_name,
                fuzzy_sets.param_a,
                fuzzy_sets.param_b, 
                fuzzy_sets.param_c,
                fuzzy_rules.description as eligibility,
                fuzzy_variables.description,
                fuzzy_variables.variable_name
            FROM fuzzy_rules
            JOIN fuzzy_rule_conditions ON fuzzy_rule_conditions.rule_id = fuzzy_rules.rule_id
            JOIN fuzzy_sets ON fuzzy_sets.set_id = fuzzy_rule_conditions.set_id
            JOIN fuzzy_variables ON fuzzy_variables.variable_id = fuzzy_sets.variable_id;
        """)
        rows = cursor.fetchall()

        variables = {}
        for row in rows:
            var_id = row["variable_id"]
            if var_id not in variables:
                variables[var_id] = {
                    "sets": [],
                    "variable_id": var_id,
                    "variable_name": row["variable_name"],
                    "description": row["description"]
                }
            variables[var_id]["sets"].append({
                "description": row["set_name"],
                "eligibility": row["eligibility"],
                "param_a": float(row["param_a"]),
                "param_b": float(row["param_b"]),
                "param_c": float(row["param_c"])
            })

        return jsonify(list(variables.values()))

    except Exception as e:
        print(f"[ERROR] get_fuzzy_config: {e}")
        return jsonify({"error": "Failed to fetch fuzzy sets"}), 500
    finally:
        cursor.close()
        db.close()
