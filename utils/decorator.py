from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt

def bitress_required(fn):
    """Decorator to ensure only 'bitress' role can access"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            claims = get_jwt()
        except Exception:
            return jsonify({"error": "Missing or invalid token"}), 401

        if claims.get("role") != "bitress":
            return jsonify({"error": "bitress admin access required"}), 403

        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    """Decorator to allow both 'admin' and 'bitress' roles"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            claims = get_jwt()
        except Exception:
            return jsonify({"error": "Missing or invalid token"}), 401

        if claims.get("role") not in ["admin", "bitress"]:
            return jsonify({"error": "Admin access required"}), 403

        return fn(*args, **kwargs)
    return wrapper
