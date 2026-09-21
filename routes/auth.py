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

@auth_bp.route("/request-password-reset", methods=["POST"])
def request_password_reset():
    data = request.get_json()
    email = data.get("email")

    ip_address = request.environ.get("HTTP_X_FORWARDED_FOR", request.remote_addr)
    user_agent = request.headers.get("User-Agent", "")

    return AuthService.request_password_reset(email, ip_address, user_agent)

@auth_bp.route("/confirm-password-reset", methods=["POST"])
def confirm_password_reset():
    try:
        data = request.get_json()
        token = data.get("token")
        new_password = data.get("new_password")

        if not token or not new_password:
            return jsonify({"status": "error", "message": "Token and new password are required."}), 400

        result, status = AuthService.confirm_password_reset(token, new_password)
        return jsonify(result), status

    except Exception as e:
        return jsonify({"status": "error", "message": f"Unexpected error: {str(e)}"}), 500

@auth_bp.route("/activate", methods=["GET", "POST"])
def activate():
    """
    Activate user account using activation code
    """
    code = request.args.get("code")
    if not code and request.is_json:
        code = request.json.get("code")

    response_data, status_code = AuthService.activate_account(code)
    return jsonify(response_data), status_code
