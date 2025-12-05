from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify({"error": "Admins only"}), 403
        return fn(*args, **kwargs)
    return wrapper


def bitress_required(fn):
    """Decorator to ensure only bitress super admin can access"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        if claims.get("role") != "bitress":
            return jsonify({"error": "Super admin access required"}), 403
        return fn(*args, **kwargs)
    return wrapper


def admin_or_bitress_required(fn):
    """Decorator to allow both admin and bitress roles"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        if claims.get("role") not in ["admin", "bitress"]:
            return jsonify({"error": "Admin access required"}), 403
        return fn(*args, **kwargs)
    return wrapper
