from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt

from models.user import ROLE_ADMIN, ROLE_BITRESS, ROLE_FACULTY, ROLE_STUDENT, UNRESTRICTED_ROLES, ADMIN_ROLES


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


def faculty_required(fn):
    """Decorator to ensure only faculty role can access"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        if claims.get("role") != ROLE_FACULTY:
            return jsonify({"error": "Faculty access required"}), 403
        return fn(*args, **kwargs)
    return wrapper


def admin_or_faculty_required(fn):
    """Decorator to allow admin, bitress, or faculty roles.
    Faculty users are campus-scoped; admin/bitress have unrestricted access.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        role = claims.get("role")
        if role not in ADMIN_ROLES:
            return jsonify({"error": "Admin or faculty access required"}), 403
        return fn(*args, **kwargs)
    return wrapper


def get_user_campus_scope():
    """Get the campus scope from JWT claims.
    Returns (is_unrestricted, campus_id) tuple.
    - For admin/bitress: (True, None) - unrestricted access
    - For faculty: (False, campus_id) - campus-scoped access
    - For others: (False, None) - no admin access
    """
    claims = get_jwt()
    role = claims.get("role")
    campus_id = claims.get("campus_id")
    
    if role in UNRESTRICTED_ROLES:
        return True, None
    elif role == ROLE_FACULTY:
        return False, campus_id
    else:
        return False, None


def has_campus_access(target_campus_id):
    """Check if current user has access to the target campus.
    Admin/bitress have access to all campuses.
    Faculty only has access to their assigned campus.
    """
    is_unrestricted, user_campus_id = get_user_campus_scope()
    
    if is_unrestricted:
        return True
    
    if user_campus_id is None:
        return False
    
    return user_campus_id == target_campus_id


def campus_scope_required(get_target_campus_id):
    """Decorator that enforces campus scope for faculty users.
    
    Args:
        get_target_campus_id: A callable that takes (*args, **kwargs) and returns the target campus_id.
                              Can also be a string specifying the kwarg name containing campus_id.
    
    Usage:
        @campus_scope_required(lambda **kw: kw.get('campus_id'))
        def my_endpoint(campus_id):
            ...
        
        @campus_scope_required('campus_id')
        def my_endpoint(campus_id):
            ...
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            role = claims.get("role")
            
            # Check if user has admin-level role
            if role not in ADMIN_ROLES:
                return jsonify({"error": "Admin or faculty access required"}), 403
            
            # Admin/bitress have unrestricted access
            if role in UNRESTRICTED_ROLES:
                return fn(*args, **kwargs)
            
            # Faculty users need campus scope check
            user_campus_id = claims.get("campus_id")
            if user_campus_id is None:
                return jsonify({"error": "Faculty user must have a campus assignment"}), 403
            
            # Get target campus ID
            if callable(get_target_campus_id):
                target_campus_id = get_target_campus_id(*args, **kwargs)
            elif isinstance(get_target_campus_id, str):
                target_campus_id = kwargs.get(get_target_campus_id)
                if target_campus_id is None:
                    # Try to get from request args or json
                    target_campus_id = request.args.get(get_target_campus_id) or \
                                       (request.json.get(get_target_campus_id) if request.is_json else None)
            else:
                target_campus_id = get_target_campus_id
            
            # If target campus is specified, verify access
            if target_campus_id is not None:
                try:
                    target_campus_id = int(target_campus_id)
                except (ValueError, TypeError):
                    return jsonify({"error": "Invalid campus ID"}), 400
                    
                if target_campus_id != user_campus_id:
                    return jsonify({"error": "Access denied: campus scope violation"}), 403
            
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def enforce_faculty_campus_scope(data_dict, user_claims):
    """Helper function to enforce campus scope when creating/updating resources.
    For faculty users, forces the campus_id to their assigned campus.
    For admin/bitress, allows any campus_id.
    
    Args:
        data_dict: The data dictionary to modify
        user_claims: The JWT claims from get_jwt()
    
    Returns:
        Modified data dictionary with enforced campus_id
    """
    role = user_claims.get("role")
    
    if role == ROLE_FACULTY:
        user_campus_id = user_claims.get("campus_id")
        if user_campus_id is not None:
            data_dict["campus_id"] = user_campus_id
    
    return data_dict
