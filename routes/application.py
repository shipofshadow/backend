from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import get_connection

application_bp = Blueprint("application", __name__, url_prefix="/api/application")

@application_bp.route('/status', methods=['GET'])
@jwt_required()
def check_application_status():
    user_id = get_jwt_identity()
    db = get_connection()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM applications WHERE student_id = %s", (user_id,))
    (count,) = cursor.fetchone()
    return jsonify({"has_applied": count > 0})
