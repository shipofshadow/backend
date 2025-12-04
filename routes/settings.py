from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from utils.decorator import admin_required
from services.settings_service import get_all_system_settings, update_system_setting, bulk_update_system_settings

settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')


@settings_bp.route('/', methods=['GET'])
# @jwt_required()     # Uncomment these in production
# @admin_required
def get_settings():
    """
    Get all system configuration settings.
    """
    try:
        settings = get_all_system_settings()
        return jsonify(settings), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/', methods=['POST'])
# @jwt_required()
# @admin_required
def update_settings():
    """
    Update system settings (Bulk).
    """
    try:
        data = request.json
        # basic validation or sanitization can go here

        success = bulk_update_system_settings(data)

        if success:
            return jsonify({"message": "Settings updated successfully"}), 200
        else:
            return jsonify({"error": "Failed to update settings"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500