from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.auth_service import AuthService

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    return AuthService.login(data.get("username"), data.get("password"))

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.json
    return AuthService.register(data)

@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    return jsonify({"id": user_id}), 200

@auth_bp.route("/edit", methods=["PUT"])
@jwt_required()
def edit_account():
    user_id = get_jwt_identity()
    data = request.json
    return AuthService.update_profile(user_id, data)
