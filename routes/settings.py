from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from utils.decorator import admin_required, bitress_required
from services.settings_service import (
    get_all_system_settings,
    get_setting,
    update_system_setting,
    bulk_update_system_settings,
    get_storage_provider
)
from utils.utils import save_avatar, allowed_file

settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')


@settings_bp.route('/', methods=['GET'])
@jwt_required()
@bitress_required
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
@jwt_required()
@bitress_required
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


@settings_bp.route('/<config_name>', methods=['GET'])
@jwt_required()
@bitress_required
def get_single_setting(config_name):
    """
    Get a single setting value.
    """
    try:
        value = get_setting(config_name)
        if value is None:
            return jsonify({"error": f"Setting '{config_name}' not found"}), 404
        return jsonify({config_name: value}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/<config_name>', methods=['PUT'])
@jwt_required()
@bitress_required
def update_single_setting(config_name):
    """
    Update a single setting.
    """
    try:
        data = request.json
        if 'value' not in data:
            return jsonify({"error": "Missing 'value' in request body"}), 400

        success = update_system_setting(config_name, data['value'])

        if success:
            return jsonify({"message": f"Setting '{config_name}' updated successfully"}), 200
        else:
            return jsonify({"error": f"Failed to update setting '{config_name}'"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/upload-avatar', methods=['POST'])
@jwt_required()
@bitress_required
def upload_avatar():
    """
    Upload avatar image endpoint.
    Accepts multipart form data with an image file OR a URL (for Google profile pictures).
    Returns JSON with the stored path/key based on storageProvider config.
    """
    try:
        user_id = request.form.get('user_id', 'system')
        avatar_url = request.form.get('avatar_url')
        avatar_file = request.files.get('avatar')

        if not avatar_file and not avatar_url:
            return jsonify({"error": "No avatar file or URL provided"}), 400

        if avatar_file:
            # Validate file type
            if not allowed_file(avatar_file.filename):
                return jsonify({"error": "Invalid file type. Allowed: png, jpg, jpeg"}), 400

        # Use the save_avatar function which handles storage provider logic
        result = save_avatar(avatar_file or avatar_url, user_id)

        if result:
            storage = get_storage_provider()
            return jsonify({
                "success": True,
                "path": result,
                "storage": storage
            }), 200
        else:
            return jsonify({"error": "Failed to save avatar"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500