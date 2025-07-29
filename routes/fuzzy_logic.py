from flask import Blueprint, request, jsonify
from db import get_connection

fuzzy_bp = Blueprint("fuzzy_bp", __name__, url_prefix="/api/fuzzy")

@fuzzy_bp.route("/fuzzy-variables", methods=["GET"])
def get_fuzzy_variables():
    db = get_connection()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM fuzzy_variables")
    data = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(data)


@fuzzy_bp.route("/fuzzy-variables", methods=["POST"])
def create_fuzzy_variable():
    data = request.get_json()
    variable_name = data.get("variable_name")
    description = data.get("description")

    db = get_connection()
    cursor = db.cursor()
    cursor.execute("""
                   INSERT INTO fuzzy_variables (variable_name, description)
                   VALUES (%s, %s)
                   """, (variable_name, description))

    variable_id = cursor.lastrowid
    cursor.execute("SELECT * FROM fuzzy_variables WHERE variable_id = %s", (variable_id,))
    result = cursor.fetchone()

    db.commit()
    cursor.close()
    db.close()
    return jsonify(result)


# --- Routes for Fuzzy Sets ---

@fuzzy_bp.route("/fuzzy-sets", methods=["GET"])
def get_fuzzy_sets():
    db = get_connection()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM fuzzy_sets")
    data = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(data)


@fuzzy_bp.route("/fuzzy-sets", methods=["POST"])
def create_fuzzy_set():
    data = request.get_json()
    variable_id = data.get("variable_id")
    set_name = data.get("set_name")
    param_a = data.get("param_a")
    param_b = data.get("param_b")
    param_c = data.get("param_c")

    db = get_connection()
    cursor = db.cursor()
    cursor.execute("""
                   INSERT INTO fuzzy_sets (variable_id, set_name, param_a, param_b, param_c)
                   VALUES (%s, %s, %s, %s, %s)
                   """, (variable_id, set_name, param_a, param_b, param_c))

    set_id = cursor.lastrowid
    cursor.execute("SELECT * FROM fuzzy_sets WHERE set_id = %s", (set_id,))
    result = cursor.fetchone()

    db.commit()
    cursor.close()
    db.close()
    return jsonify(result)


@fuzzy_bp.route("/fuzzy-sets/<int:set_id>", methods=["PUT"])
def update_fuzzy_set(set_id):
    data = request.get_json()
    param_a = data.get("param_a")
    param_b = data.get("param_b")
    param_c = data.get("param_c")

    db = get_connection()
    cursor = db.cursor()
    cursor.execute("""
                   UPDATE fuzzy_sets
                   SET param_a    = %s,
                       param_b    = %s,
                       param_c    = %s,
                       updated_at = NOW()
                   WHERE set_id = %s
                   """, (param_a, param_b, param_c, set_id))

    cursor.execute("SELECT * FROM fuzzy_sets WHERE set_id = %s", (set_id,))
    result = cursor.fetchone()

    db.commit()
    cursor.close()
    db.close()
    return jsonify(result)
