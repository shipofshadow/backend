from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import get_connection

profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")

@profile_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    db = get_connection()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"message": "User not found"}), 404

    user_data = {
        "id": row['id'],
        "username": row["username"],
        "password": row["password"],
        "role": row["role"],
        "is_active": row["is_active"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }

    return jsonify(user_data)
