from flask import Blueprint, request, jsonify
from db import get_connection

fuzzy_bp = Blueprint("fuzzy_bp", __name__, url_prefix="/api/fuzzy")


# ========== FUZZY VARIABLES ==========

@fuzzy_bp.route('/variables', methods=['GET'])
def get_fuzzy_variables():
    db = get_connection()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT * FROM fuzzy_variables ORDER BY variable_name")
        variables = cursor.fetchall()
        return jsonify(variables), 200
    except Exception as e:
        print(f"[ERROR] get_fuzzy_variables: {e}")
        return jsonify({"error": "Failed to fetch fuzzy variables"}), 500
    finally:
        cursor.close()
        db.close()


@fuzzy_bp.route('/variables', methods=['POST'])
def create_fuzzy_variable():
    db = get_connection()
    cursor = db.cursor()
    try:
        data = request.json
        cursor.execute("""
                       INSERT INTO fuzzy_variables (variable_name, description)
                       VALUES (%s, %s)
                       """, (data['variable_name'], data.get('description')))
        db.commit()
        return jsonify({"message": "Variable created successfully"}), 201
    except Exception as e:
        print(f"[ERROR] create_fuzzy_variable: {e}")
        return jsonify({"error": "Failed to create variable"}), 500
    finally:
        cursor.close()
        db.close()


@fuzzy_bp.route('/variables/<int:variable_id>', methods=['PUT'])
def update_fuzzy_variable(variable_id):
    db = get_connection()
    cursor = db.cursor()
    try:
        data = request.json
        cursor.execute("""
                       UPDATE fuzzy_variables
                       SET variable_name = %s,
                           description   = %s
                       WHERE variable_id = %s
                       """, (data['variable_name'], data.get('description'), variable_id))
        db.commit()
        return jsonify({"message": "Variable updated successfully"}), 200
    except Exception as e:
        print(f"[ERROR] update_fuzzy_variable: {e}")
        return jsonify({"error": "Failed to update variable"}), 500
    finally:
        cursor.close()
        db.close()


@fuzzy_bp.route('/variables/<int:variable_id>', methods=['DELETE'])
def delete_fuzzy_variable(variable_id):
    db = get_connection()
    cursor = db.cursor()
    try:
        # Check if variable is used in sets
        cursor.execute("SELECT COUNT(*) as count FROM fuzzy_sets WHERE variable_id = %s", (variable_id,))
        if cursor.fetchone()['count'] > 0:
            return jsonify({"error": "Cannot delete variable - it has associated sets"}), 400

        cursor.execute("DELETE FROM fuzzy_variables WHERE variable_id = %s", (variable_id,))
        db.commit()
        return jsonify({"message": "Variable deleted successfully"}), 200
    except Exception as e:
        print(f"[ERROR] delete_fuzzy_variable: {e}")
        return jsonify({"error": "Failed to delete variable"}), 500
    finally:
        cursor.close()
        db.close()


# ========== FUZZY SETS ==========

@fuzzy_bp.route('/sets', methods=['GET'])
def get_fuzzy_sets():
    db = get_connection()
    cursor = db.cursor()
    try:
        cursor.execute("""
                       SELECT fs.*, fv.variable_name
                       FROM fuzzy_sets fs
                                JOIN fuzzy_variables fv ON fv.variable_id = fs.variable_id
                       ORDER BY fv.variable_name, fs.set_name
                       """)
        sets = cursor.fetchall()
        return jsonify(sets), 200
    except Exception as e:
        print(f"[ERROR] get_fuzzy_sets: {e}")
        return jsonify({"error": "Failed to fetch fuzzy sets"}), 500
    finally:
        cursor.close()
        db.close()


@fuzzy_bp.route('/sets', methods=['POST'])
def create_fuzzy_set():
    db = get_connection()
    cursor = db.cursor()
    try:
        data = request.json
        cursor.execute("""
                       INSERT INTO fuzzy_sets (variable_id, set_name, param_a, param_b, param_c)
                       VALUES (%s, %s, %s, %s, %s)
                       """, (data['variable_id'], data['set_name'],
                             data['param_a'], data['param_b'], data['param_c']))
        db.commit()
        return jsonify({"message": "Set created successfully"}), 201
    except Exception as e:
        print(f"[ERROR] create_fuzzy_set: {e}")
        return jsonify({"error": "Failed to create set"}), 500
    finally:
        cursor.close()
        db.close()


@fuzzy_bp.route('/sets/<int:set_id>', methods=['PUT'])
def update_fuzzy_set(set_id):
    db = get_connection()
    cursor = db.cursor()
    try:
        data = request.json
        cursor.execute("""
                       UPDATE fuzzy_sets
                       SET set_name = %s,
                           param_a  = %s,
                           param_b  = %s,
                           param_c  = %s
                       WHERE set_id = %s
                       """, (data['set_name'], data['param_a'], data['param_b'],
                             data['param_c'], set_id))
        db.commit()
        return jsonify({"message": "Set updated successfully"}), 200
    except Exception as e:
        print(f"[ERROR] update_fuzzy_set: {e}")
        return jsonify({"error": "Failed to update set"}), 500
    finally:
        cursor.close()
        db.close()


@fuzzy_bp.route('/sets/<int:set_id>', methods=['DELETE'])
def delete_fuzzy_set(set_id):
    db = get_connection()
    cursor = db.cursor()
    try:
        # Check if set is used in rules
        cursor.execute("SELECT COUNT(*) as count FROM fuzzy_rule_conditions WHERE set_id = %s", (set_id,))
        if cursor.fetchone()['count'] > 0:
            return jsonify({"error": "Cannot delete set - it is used in rules"}), 400

        cursor.execute("DELETE FROM fuzzy_sets WHERE set_id = %s", (set_id,))
        db.commit()
        return jsonify({"message": "Set deleted successfully"}), 200
    except Exception as e:
        print(f"[ERROR] delete_fuzzy_set: {e}")
        return jsonify({"error": "Failed to delete set"}), 500
    finally:
        cursor.close()
        db.close()


# ========== FUZZY RULES ==========

@fuzzy_bp.route('/rules', methods=['GET'])
def get_fuzzy_rules():
    db = get_connection()
    cursor = db.cursor()
    try:
        cursor.execute("""
                       SELECT fr.rule_id,
                              fr.consequent_value,
                              fr.description,
                              fv.variable_name,
                              fs.set_name
                       FROM fuzzy_rules fr
                                JOIN fuzzy_rule_conditions frc ON frc.rule_id = fr.rule_id
                                JOIN fuzzy_sets fs ON fs.set_id = frc.set_id
                                JOIN fuzzy_variables fv ON fv.variable_id = fs.variable_id
                       ORDER BY fr.rule_id
                       """)
        rows = cursor.fetchall()

        # Group by rule_id
        rule_map = {}
        for row in rows:
            rid = row['rule_id']
            if rid not in rule_map:
                rule_map[rid] = {
                    'rule_id': rid,
                    'if': {},
                    'then': float(row['consequent_value']),
                    'description': row['description']
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


@fuzzy_bp.route('/rules', methods=['POST'])
def create_fuzzy_rule():
    db = get_connection()
    cursor = db.cursor()
    try:
        data = request.json

        # Insert rule
        cursor.execute("""
                       INSERT INTO fuzzy_rules (consequent_value, description)
                       VALUES (%s, %s)
                       """, (data['consequent_value'], data.get('description')))

        rule_id = cursor.lastrowid

        # Insert rule conditions
        for condition in data['conditions']:
            cursor.execute("""
                           INSERT INTO fuzzy_rule_conditions (rule_id, set_id)
                           VALUES (%s, %s)
                           """, (rule_id, condition['set_id']))

        db.commit()
        return jsonify({"message": "Rule created successfully", "rule_id": rule_id}), 201
    except Exception as e:
        db.rollback()
        print(f"[ERROR] create_fuzzy_rule: {e}")
        return jsonify({"error": "Failed to create rule"}), 500
    finally:
        cursor.close()
        db.close()


@fuzzy_bp.route('/rules/<int:rule_id>', methods=['PUT'])
def update_fuzzy_rule(rule_id):
    db = get_connection()
    cursor = db.cursor()
    try:
        data = request.json

        # Update rule
        cursor.execute("""
                       UPDATE fuzzy_rules
                       SET consequent_value = %s,
                           description      = %s
                       WHERE rule_id = %s
                       """, (data['consequent_value'], data.get('description'), rule_id))

        # Delete existing conditions
        cursor.execute("DELETE FROM fuzzy_rule_conditions WHERE rule_id = %s", (rule_id,))

        # Insert new conditions
        for condition in data['conditions']:
            cursor.execute("""
                           INSERT INTO fuzzy_rule_conditions (rule_id, set_id)
                           VALUES (%s, %s)
                           """, (rule_id, condition['set_id']))

        db.commit()
        return jsonify({"message": "Rule updated successfully"}), 200
    except Exception as e:
        db.rollback()
        print(f"[ERROR] update_fuzzy_rule: {e}")
        return jsonify({"error": "Failed to update rule"}), 500
    finally:
        cursor.close()
        db.close()


@fuzzy_bp.route('/rules/<int:rule_id>', methods=['DELETE'])
def delete_fuzzy_rule(rule_id):
    db = get_connection()
    cursor = db.cursor()
    try:
        # Delete conditions first (foreign key constraint)
        cursor.execute("DELETE FROM fuzzy_rule_conditions WHERE rule_id = %s", (rule_id,))

        # Delete rule
        cursor.execute("DELETE FROM fuzzy_rules WHERE rule_id = %s", (rule_id,))

        db.commit()
        return jsonify({"message": "Rule deleted successfully"}), 200
    except Exception as e:
        db.rollback()
        print(f"[ERROR] delete_fuzzy_rule: {e}")
        return jsonify({"error": "Failed to delete rule"}), 500
    finally:
        cursor.close()
        db.close()


# ========== CONFIG ENDPOINTS ==========

@fuzzy_bp.route('/fuzzy-config', methods=['GET'])
def get_fuzzy_config():
    """Get the complete fuzzy configuration for the frontend"""
    db = get_connection()
    cursor = db.cursor()
    try:
        # Get variables with their sets
        cursor.execute("""
                       SELECT fv.variable_id,
                              fv.variable_name,
                              fv.description,
                              fs.set_id,
                              fs.set_name,
                              fs.param_a,
                              fs.param_b,
                              fs.param_c
                       FROM fuzzy_variables fv
                                LEFT JOIN fuzzy_sets fs ON fv.variable_id = fs.variable_id
                       ORDER BY fv.variable_name, fs.set_name
                       """)
        rows = cursor.fetchall()

        variables = {}
        for row in rows:
            var_id = row["variable_id"]
            if var_id not in variables:
                variables[var_id] = {
                    "variable_id": var_id,
                    "variable_name": row["variable_name"],
                    "description": row["description"],
                    "sets": []
                }

            if row["set_id"]:  # Only add sets if they exist
                variables[var_id]["sets"].append({
                    "set_id": row["set_id"],
                    "set_name": row["set_name"],
                    "param_a": float(row["param_a"]),
                    "param_b": float(row["param_b"]),
                    "param_c": float(row["param_c"])
                })

        return jsonify(list(variables.values())), 200
    except Exception as e:
        print(f"[ERROR] get_fuzzy_config: {e}")
        return jsonify({"error": "Failed to fetch fuzzy configuration"}), 500
    finally:
        cursor.close()
        db.close()


@fuzzy_bp.route('/config/bulk-update', methods=['POST'])
def bulk_update_config():
    """Update the entire fuzzy configuration"""
    db = get_connection()
    cursor = db.cursor()
    try:
        data = request.json

        # This would be a complex operation to replace the entire config
        # For now, return a placeholder
        return jsonify({"message": "Bulk update not implemented yet"}), 501

    except Exception as e:
        db.rollback()
        print(f"[ERROR] bulk_update_config: {e}")
        return jsonify({"error": "Failed to update configuration"}), 500
    finally:
        cursor.close()
        db.close()


# ========== UTILITY ENDPOINTS ==========

@fuzzy_bp.route('/validate-config', methods=['GET'])
def validate_config():
    """Validate the current fuzzy logic configuration"""
    db = get_connection()
    cursor = db.cursor()
    try:
        issues = []

        # Check if variables exist
        cursor.execute("SELECT COUNT(*) as count FROM fuzzy_variables")
        if cursor.fetchone()['count'] == 0:
            issues.append("No fuzzy variables defined")

        # Check if sets exist
        cursor.execute("SELECT COUNT(*) as count FROM fuzzy_sets")
        if cursor.fetchone()['count'] == 0:
            issues.append("No fuzzy sets defined")

        # Check if rules exist
        cursor.execute("SELECT COUNT(*) as count FROM fuzzy_rules")
        if cursor.fetchone()['count'] == 0:
            issues.append("No fuzzy rules defined")

        # Check for variables without sets
        cursor.execute("""
                       SELECT fv.variable_name
                       FROM fuzzy_variables fv
                                LEFT JOIN fuzzy_sets fs ON fv.variable_id = fs.variable_id
                       WHERE fs.set_id IS NULL
                       """)
        orphaned_vars = cursor.fetchall()
        for var in orphaned_vars:
            issues.append(f"Variable '{var['variable_name']}' has no sets")

        return jsonify({
            "is_valid": len(issues) == 0,
            "issues": issues
        }), 200

    except Exception as e:
        print(f"[ERROR] validate_config: {e}")
        return jsonify({"error": "Failed to validate configuration"}), 500
    finally:
        cursor.close()
        db.close()


@fuzzy_bp.route('/test-evaluation', methods=['POST'])
def test_evaluation():
    """Test fuzzy evaluation with given inputs"""
    try:
        data = request.json
        inputs = data.get('inputs', {})  # e.g., {'gwa': 3.5, 'income': 25000}

        # Here you would integrate with your fuzzy logic system
        # For now, return a placeholder
        result = {
            "score": 0.75,
            "classification": "Eligible",
            "details": f"Test evaluation with inputs: {inputs}"
        }

        return jsonify(result), 200

    except Exception as e:
        print(f"[ERROR] test_evaluation: {e}")
        return jsonify({"error": "Failed to test evaluation"}), 500