from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from services.auth_service import AuthService

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login endpoint
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: credentials
        description: User login credentials
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
            password:
              type: string
    responses:
      200:
        description: Login successful
        schema:
          type: object
          properties:
            token:
              type: string
              example: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
      401:
        description: Invalid credentials
    """
    data = request.json
    return AuthService.login(data.get("username"), data.get("password"))

@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Register endpoint
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: user
        description: User registration data
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
            password:
              type: string
            email:
              type: string
    responses:
      201:
        description: Registration successful
      400:
        description: Invalid input
    """
    data = request.json
    return AuthService.register(data)

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token():
    """
    Refresh JWT token
    ---
    tags:
      - Authentication
    security:
      - jwt: []
    responses:
      200:
        description: New access token
        schema:
          type: object
          properties:
            token:
              type: string
      401:
        description: Invalid or expired refresh token
    """
    identity = get_jwt_identity()
    new_token = create_access_token(identity=identity)
    return jsonify({"token": new_token}), 200
