import json

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from storage import get_connection

scholarships_bp = Blueprint('scholarships', __name__, url_prefix='/api/scholarships')

# GET all scholarships
@scholarships_bp.route('/', methods=['GET'])
# @jwt_required()
def get_scholarships():
    """
    Get all scholarships
    ---
    tags:
      - Scholarships
    security:
      - Bearer: []
    responses:
      200:
        description: List of scholarships
        content:
          application/json:
            schema:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                    example: 1
                  name:
                    type: string
                    example: "Academic Excellence"
                  description:
                    type: string
                    example: "Awarded to top-performing students"
                  grant_amount:
                    type: number
                    example: 10000
                  is_active:
                    type: boolean
                    example: true
                  created_at:
                    type: string
                    format: date-time
                  updated_at:
                    type: string
                    format: date-time
                  rules:
                    type: object
                    nullable: true
                    description: Scholarship eligibility rules
      500:
        description: Failed to fetch scholarships
    """

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       SELECT s.id AS scholarship_id,
                              s.name,
                            s.grant_amount,
                              s.description,
                              s.is_active,
                              s.created_at,
                              s.updated_at,
                              sr.rule_id,
                              sr.config
                       FROM scholarships s
                                LEFT JOIN scholarship_rules sr ON s.id = sr.scholarship_id
                       WHERE s.deleted_at IS NULL
                       ORDER BY s.id
                       """)
        rows = cursor.fetchall()

        scholarships = []
        for row in rows:
            # Parse the JSON config if it exists
            rules = None
            if row["rule_id"] and row["config"]:
                try:
                    import json
                    config = json.loads(row["config"])
                    rules = {
                        "rule_id": row["rule_id"],
                        "min_gwa": config.get("min_gwa"),
                        "max_gwa": config.get("max_gwa"),
                        "min_income": config.get("min_income"),
                        "max_income": config.get("max_income"),
                        "priorities": config.get("priorities", {}),
                        "preferred_course_ids": config.get("preferred_course_ids", []),
                        "preferred_department_ids": config.get("preferred_department_ids", []),
                        "preferred_campus_ids": config.get("preferred_campus_ids", []),
                        "preferred_year_levels": config.get("preferred_year_levels", []),
                        "min_units_enrolled": config.get("min_units_enrolled"),
                        "max_units_enrolled": config.get("max_units_enrolled")
                    }
                except json.JSONDecodeError as e:
                    print(f"[WARNING] Invalid JSON in scholarship_rules for rule_id {row['rule_id']}: {e}")
                    rules = {"rule_id": row["rule_id"], "config_error": "Invalid JSON configuration"}

            scholarships.append({
                "id": row["scholarship_id"],
                "name": row["name"],
                "description": row["description"],
                "grant_amount": row["grant_amount"],
                "is_active": bool(row["is_active"]),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                "rules": rules
            })

        return jsonify(scholarships), 200

    except Exception as e:
        print(f"[ERROR] get_scholarships: {e}")
        return jsonify({"error": "Failed to fetch scholarships"}), 500
    finally:
        cursor.close()
        conn.close()


# POST create scholarship
@scholarships_bp.route('/', methods=['POST'])
@jwt_required()
def create_scholarship():
    # GET all scholarships
    @scholarships_bp.route('/', methods=['GET'])
    # @jwt_required()
    def get_scholarships():
        """
        Get all scholarships
        ---
        tags:
          - Scholarships
        security:
          - Bearer: []
        responses:
          200:
            description: List of scholarships
            content:
              application/json:
                schema:
                  type: array
                  items:
                    type: object
                    properties:
                      id:
                        type: integer
                        example: 1
                      name:
                        type: string
                        example: "Academic Excellence"
                      description:
                        type: string
                        example: "Awarded to top-performing students"
                      grant_amount:
                        type: number
                        example: 10000
                      is_active:
                        type: boolean
                        example: true
                      created_at:
                        type: string
                        format: date-time
                      updated_at:
                        type: string
                        format: date-time
                      rules:
                        type: object
                        nullable: true
                        description: Scholarship eligibility rules
          500:
            description: Failed to fetch scholarships
        """
        ...

    # POST create scholarship
    @scholarships_bp.route('/', methods=['POST'])
    @jwt_required()
    def create_scholarship():
        """
        Create a new scholarship
        ---
        tags:
          - Scholarships
        security:
          - Bearer: []
        requestBody:
          required: true
          content:
            application/json:
              schema:
                type: object
                required:
                  - name
                properties:
                  name:
                    type: string
                    example: "Academic Excellence"
                  description:
                    type: string
                    example: "Awarded to top-performing students"
                  grant_amount:
                    type: number
                    example: 10000
                  is_active:
                    type: boolean
                    example: true
                  rules:
                    type: object
                    properties:
                      min_gwa:
                        type: number
                        example: 1.75
                      max_gwa:
                        type: number
                        example: 3.0
                      min_income:
                        type: number
                        example: 0
                      max_income:
                        type: number
                        example: 25000
                      priorities:
                        type: object
                        properties:
                          must_be_ofw:
                            type: boolean
                            example: false
                          prefer_farmers_child:
                            type: boolean
                            example: true
                          require_ip:
                            type: boolean
                            example: false
                          prefer_pwd:
                            type: boolean
                            example: false
                      preferred_course_ids:
                        type: array
                        items:
                          type: integer
                      preferred_department_ids:
                        type: array
                        items:
                          type: integer
                      preferred_campus_ids:
                        type: array
                        items:
                          type: integer
                      preferred_year_levels:
                        type: array
                        items:
                          type: integer
                      min_units_enrolled:
                        type: integer
                      max_units_enrolled:
                        type: integer
        responses:
          201:
            description: Scholarship created successfully
          400:
            description: Missing required fields
          500:
            description: Failed to create scholarship
        """

    data = request.json

    # Validate required fields
    if not data.get('name'):
        return jsonify({"error": "Scholarship name is required"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Insert scholarship
        cursor.execute("""
                       INSERT INTO scholarships (name, description, grant_amount, is_active)
                       VALUES (%s, %s, %s, %s)
                       """, (
                           data['name'],
                           data.get('description'),
                           data.get('grant_amount'),
                           int(data.get('is_active', 1))
                       ))
        scholarship_id = cursor.lastrowid

        # Create rules if provided
        rules_data = data.get('rules', {})
        if rules_data:
            # Build the config JSON
            config = {
                "min_gwa": rules_data.get('min_gwa'),
                "max_gwa": rules_data.get('max_gwa'),
                "min_income": rules_data.get('min_income'),
                "max_income": rules_data.get('max_income'),
                "priorities": {
                    "must_be_ofw": rules_data.get('priorities', {}).get('must_be_ofw', False),
                    "prefer_farmers_child": rules_data.get('priorities', {}).get('prefer_farmers_child', False),
                    "require_ip": rules_data.get('priorities', {}).get('require_ip', False),
                    "prefer_pwd": rules_data.get('priorities', {}).get('prefer_pwd', False)
                },
                "preferred_course_ids": rules_data.get('preferred_course_ids', []),
                "preferred_department_ids": rules_data.get('preferred_department_ids', []),
                "preferred_campus_ids": rules_data.get('preferred_campus_ids', []),
                "preferred_year_levels": rules_data.get('preferred_year_levels', []),
                "min_units_enrolled": rules_data.get('min_units_enrolled'),
                "max_units_enrolled": rules_data.get('max_units_enrolled')
            }

            cursor.execute("""
                           INSERT INTO scholarship_rules (scholarship_id, config)
                           VALUES (%s, %s)
                           """, (scholarship_id, json.dumps(config)))

        conn.commit()
        return jsonify({
            "message": "Scholarship created successfully",
            "scholarship_id": scholarship_id
        }), 201

    except Exception as e:
        print(f"[ERROR] create_scholarship: {e}")
        conn.rollback()
        return jsonify({"error": "Failed to create scholarship"}), 500
    finally:
        cursor.close()
        conn.close()


# PUT update scholarship
@scholarships_bp.route('/<int:scholarship_id>', methods=['PUT'])
@jwt_required()
def update_scholarship(scholarship_id):
    """
    Update an existing scholarship
    ---
    tags:
      - Scholarships
    security:
      - Bearer: []
    parameters:
      - name: scholarship_id
        in: path
        required: true
        schema:
          type: integer
          example: 1
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - name
            properties:
              name:
                type: string
                example: "Academic Excellence"
              description:
                type: string
                example: "Awarded to top-performing students"
              grant_amount:
                type: number
                example: 10000
              is_active:
                type: boolean
                example: true
              rules:
                type: object
                properties:  # same as create_scholarship
                  min_gwa: {type: number, example: 1.75}

    responses:
      200:
        description: Scholarship updated successfully
      400:
        description: Missing required fields
      404:
        description: Scholarship not found
      500:
        description: Failed to update scholarship
    """

    data = request.json

    # Validate required fields
    if not data.get('name'):
        return jsonify({"error": "Scholarship name is required"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Check if scholarship exists
        cursor.execute("""
                       SELECT id
                       FROM scholarships
                       WHERE id = %s
                         AND deleted_at IS NULL
                       """, (scholarship_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Scholarship not found"}), 404

        # Update scholarship basic info
        cursor.execute("""
                       UPDATE scholarships
                       SET name        = %s,
                           description = %s,
                           grant_amount = %s,
                           is_active   = %s,
                           updated_at  = CURRENT_TIMESTAMP
                       WHERE id = %s
                       """, (
                           data['name'],
                           data.get('description'),
                           data.get('grant_amount'),
                           int(data.get('is_active', 1)),
                           scholarship_id
                       ))

        # Handle rules update
        rules_data = data.get('rules', {})

        # Check if rule exists
        cursor.execute("""
                       SELECT rule_id
                       FROM scholarship_rules
                       WHERE scholarship_id = %s
                       """, (scholarship_id,))
        existing_rule = cursor.fetchone()

        if rules_data:
            # Build the config JSON
            config = {
                "min_gwa": rules_data.get('min_gwa'),
                "max_gwa": rules_data.get('max_gwa'),
                "min_income": rules_data.get('min_income'),
                "max_income": rules_data.get('max_income'),
                "priorities": {
                    "must_be_ofw": rules_data.get('priorities', {}).get('must_be_ofw', False),
                    "prefer_farmers_child": rules_data.get('priorities', {}).get('prefer_farmers_child', False),
                    "require_ip": rules_data.get('priorities', {}).get('require_ip', False),
                    "prefer_pwd": rules_data.get('priorities', {}).get('prefer_pwd', False)
                },
                "preferred_course_ids": rules_data.get('preferred_course_ids', []),
                "preferred_department_ids": rules_data.get('preferred_department_ids', []),
                "preferred_campus_ids": rules_data.get('preferred_campus_ids', []),
                "preferred_year_levels": rules_data.get('preferred_year_levels', []),
                "min_units_enrolled": rules_data.get('min_units_enrolled'),
                "max_units_enrolled": rules_data.get('max_units_enrolled')
            }

            if existing_rule:
                # Update existing rule
                cursor.execute("""
                               UPDATE scholarship_rules
                               SET config     = %s,
                                   updated_at = CURRENT_TIMESTAMP
                               WHERE scholarship_id = %s
                               """, (json.dumps(config), scholarship_id))
            else:
                # Insert new rule
                cursor.execute("""
                               INSERT INTO scholarship_rules (scholarship_id, config)
                               VALUES (%s, %s)
                               """, (scholarship_id, json.dumps(config)))
        else:
            # If no rules provided but rule exists, you might want to delete it
            # Uncomment the following if you want to remove rules when not provided
            # if existing_rule:
            #     cursor.execute("""
            #         DELETE FROM scholarship_rules WHERE scholarship_id = %s
            #     """, (scholarship_id,))
            pass

        conn.commit()
        return jsonify({"message": "Scholarship updated successfully"}), 200

    except Exception as e:
        print(f"[ERROR] update_scholarship: {e}")
        conn.rollback()
        return jsonify({"error": "Failed to update scholarship"}), 500
    finally:
        cursor.close()
        conn.close()


# DELETE soft delete
@scholarships_bp.route('/<int:scholarship_id>', methods=['DELETE'])
@jwt_required()
def delete_scholarship(scholarship_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Check if scholarship exists and is not already deleted
        cursor.execute("""
                       SELECT id
                       FROM scholarships
                       WHERE id = %s
                         AND deleted_at IS NULL
                       """, (scholarship_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Scholarship not found"}), 404

        # Soft delete scholarship
        cursor.execute("""
                       UPDATE scholarships
                       SET deleted_at = CURRENT_TIMESTAMP,
                           updated_at = CURRENT_TIMESTAMP
                       WHERE id = %s
                       """, (scholarship_id,))

        conn.commit()
        return jsonify({"message": "Scholarship deleted successfully"}), 200

    except Exception as e:
        print(f"[ERROR] delete_scholarship: {e}")
        conn.rollback()
        return jsonify({"error": "Failed to delete scholarship"}), 500
    finally:
        cursor.close()
        conn.close()


# Optional: GET single scholarship
@scholarships_bp.route('/<int:scholarship_id>', methods=['GET'])
@jwt_required()
def get_scholarship(scholarship_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       SELECT s.id AS scholarship_id,
                              s.name,
                              s.description,
                            s.grant_amount,
                              s.is_active,
                              s.created_at,
                              s.updated_at,
                              sr.rule_id,
                              sr.config
                       FROM scholarships s
                                LEFT JOIN scholarship_rules sr ON s.id = sr.scholarship_id
                       WHERE s.id = %s
                         AND s.deleted_at IS NULL
                       """, (scholarship_id,))

        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Scholarship not found"}), 404

        # Parse the JSON config if it exists
        rules = None
        if row["rule_id"] and row["config"]:
            try:
                config = json.loads(row["config"])
                rules = {
                    "rule_id": row["rule_id"],
                    "min_gwa": config.get("min_gwa"),
                    "max_gwa": config.get("max_gwa"),
                    "min_income": config.get("min_income"),
                    "max_income": config.get("max_income"),
                    "priorities": config.get("priorities", {}),
                    "preferred_course_ids": config.get("preferred_course_ids", []),
                    "preferred_department_ids": config.get("preferred_department_ids", []),
                    "preferred_campus_ids": config.get("preferred_campus_ids", []),
                    "preferred_year_levels": config.get("preferred_year_levels", []),
                    "min_units_enrolled": config.get("min_units_enrolled"),
                    "max_units_enrolled": config.get("max_units_enrolled")
                }
            except json.JSONDecodeError as e:
                print(f"[WARNING] Invalid JSON in scholarship_rules for rule_id {row['rule_id']}: {e}")
                rules = {"rule_id": row["rule_id"], "config_error": "Invalid JSON configuration"}

        scholarship = {
            "id": row["scholarship_id"],
            "name": row["name"],
            "description": row["description"],
            "grant_amount": row["grant_amount"],
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            "rules": rules
        }

        return jsonify(scholarship), 200

    except Exception as e:
        print(f"[ERROR] get_scholarship: {e}")
        return jsonify({"error": "Failed to fetch scholarship"}), 500
    finally:
        cursor.close()
        conn.close()