from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import re

from storage import get_connection
from utils.hashing import hash_password
from utils.utils import generate_avatar, save_avatar
from utils.decorator import privilegedRoleRequired, bitress_required

users_bp = Blueprint('users', __name__, url_prefix='/api/users/')


# ==================== HELPER FUNCTIONS ====================

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def get_next_admin_id():
    """Get next available admin ID (starting from -2 and decrementing)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MIN(id) as min_id FROM users WHERE id < 0")
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if result and result[0]:
        return result[0] - 1
    return -2


def username_exists(username, exclude_id=None):
    """Check if username already exists"""
    conn = get_connection()
    cursor = conn.cursor()

    if exclude_id:
        cursor.execute(
            "SELECT id FROM users WHERE username = %s AND id != %s AND deleted_at IS NULL",
            (username, exclude_id)
        )
    else:
        cursor.execute(
            "SELECT id FROM users WHERE username = %s AND deleted_at IS NULL",
            (username,)
        )

    exists = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    return exists


def email_exists(email, exclude_id=None):
    """Check if email already exists"""
    conn = get_connection()
    cursor = conn.cursor()

    if exclude_id:
        cursor.execute(
            "SELECT user_id FROM user_details WHERE email = %s AND user_id != %s",
            (email, exclude_id)
        )
    else:
        cursor.execute(
            "SELECT user_id FROM user_details WHERE email = %s",
            (email,)
        )

    exists = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    return exists


def user_exists(user_id):
    """Check if user exists and is not deleted"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE id = %s AND deleted_at IS NULL", (user_id,))
    exists = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    return exists


# ==================== CRUD OPERATIONS ====================

# Get all admin users
@users_bp.route('/', methods=['GET'])
@jwt_required()
@privilegedRoleRequired
def get_admin_users():
    """Get all admin users including faculty, except deleted ones"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       SELECT u.id,
                              u.username,
                              u.role,
                              u.campus_id,
                              u.is_active,
                              u.created_at,
                              ud.first_name,
                              ud.last_name,
                              ud.email,
                              ud.avatar,
                              c.name as campus_name
                       FROM users u
                                LEFT JOIN user_details ud ON u.id = ud.user_id
                                LEFT JOIN campuses c ON u.campus_id = c.campus_id
                       WHERE u.deleted_at IS NULL
                         AND u.role IN ('admin', 'faculty')
                       ORDER BY u.id ASC
                       """)

        users = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'users': users,
            'count': len(users)
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching users: {str(e)}'
        }), 500


# Get single user by ID
@users_bp.route('/<int:user_id>/', methods=['GET'])
@jwt_required()
@privilegedRoleRequired
def get_user(user_id):
    """Get a single user by ID"""
    try:
        if not user_exists(user_id):
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       SELECT u.id,
                              u.username,
                              u.role,
                              u.campus_id,
                              u.is_active,
                              u.created_at,
                              ud.first_name,
                              ud.last_name,
                              ud.email,
                              ud.avatar,
                              c.name as campus_name
                       FROM users u
                                LEFT JOIN user_details ud ON u.id = ud.user_id
                                LEFT JOIN campuses c ON u.campus_id = c.campus_id
                       WHERE u.id = %s
                         AND u.deleted_at IS NULL
                       """, (user_id,))

        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if not result:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404

        return jsonify({
            'success': True,
            'user': result
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching user: {str(e)}'
        }), 500


# Create new admin user
@users_bp.route('/', methods=['POST'])
@jwt_required()
@bitress_required
def create_user():
    """Create a new admin or faculty user with optional avatar file"""
    try:
        # Handle Multipart/Form-Data
        data = request.form
        file = request.files.get('avatar_file')  # Look for file upload

        # Validate required fields
        required_fields = ['username', 'password', 'firstName', 'lastName', 'email']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'message': f'{field} is required'}), 400

        # Validate username length
        if len(data['username']) < 3:
            return jsonify({
                'success': False,
                'message': 'Username must be at least 3 characters'
            }), 400

        # Validate password length
        if len(data['password']) < 8:
            return jsonify({
                'success': False,
                'message': 'Password must be at least 8 characters'
            }), 400

        # Validate email format
        if not validate_email(data['email']):
            return jsonify({
                'success': False,
                'message': 'Invalid email format'
            }), 400

        # Check username uniqueness
        if username_exists(data['username']):
            return jsonify({
                'success': False,
                'message': 'Username already exists'
            }), 409

        # Check email uniqueness
        if email_exists(data['email']):
            return jsonify({
                'success': False,
                'message': 'Email already exists'
            }), 409

        # Hash password
        hashed_password = hash_password(data['password'])

        # Handle Avatar: File > URL > Generated
        avatar_path = None
        if file and file.filename != '':
            # 1. Upload File
            avatar_path = save_avatar(file, 'admin_upload')  # You might want a specific folder or ID
            if not avatar_path:
                return jsonify({'success': False, 'message': 'Failed to save avatar file'}), 500
        elif data.get('avatar'):
            # 2. Use provided URL string
            avatar_path = data.get('avatar')
        else:
            # 3. Generate default
            name = f"{data.get('firstName', '')} {data.get('lastName', '')}".strip()
            avatar_path = generate_avatar(name)

        # Get additional fields
        is_active = data.get('isActive', 'true').lower() == 'true'
        role = data.get('role', 'admin')
        campus_id = data.get('campusId') or data.get('campus_id')
        now = datetime.now()

        if campus_id == '' or campus_id == 'undefined':
            campus_id = None

        if role == 'faculty' and not campus_id:
            return jsonify({'success': False, 'message': 'Faculty users must have a campus assignment'}), 400

        conn = get_connection()
        cursor = conn.cursor()

        # Insert into users table
        cursor.execute("""
                       INSERT INTO users (username, password, role, campus_id, is_active, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       """, (data['username'], hashed_password, role, campus_id, is_active, now, now))

        next_id = cursor.lastrowid

        # Insert into user_details table
        cursor.execute("""
                       INSERT INTO user_details (user_id, first_name, last_name, email, avatar)
                       VALUES (%s, %s, %s, %s, %s)
                       """, (next_id, data['firstName'], data['lastName'], data['email'], avatar_path))

        conn.commit()

        # ... [Fetch and return result] ...
        cursor.execute("SELECT * FROM users WHERE id = %s", (next_id,))
        new_user = cursor.fetchone()  # Simplified fetch for brevity

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'message': 'User created successfully'}), 201

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error creating user: {str(e)}'}), 500
# Update user
@users_bp.route('/<signed_int:user_id>/', methods=['PUT'])
@jwt_required()
@privilegedRoleRequired
def update_user(user_id):
    """Update an existing user (supports file upload and direct password reset)"""
    try:
        # Switch to request.form for multipart data
        data = request.form
        file = request.files.get('avatar_file')

        # Prevent modification of bitress super admin (id = -999)
        if user_id == -999:
            return jsonify({
                'success': False,
                'message': 'Cannot modify bitress super admin account'
            }), 403

        # Check if user exists
        if not user_exists(user_id):
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404

        # Check username uniqueness (if changing)
        if 'username' in data:
            if len(data['username']) < 3:
                return jsonify({
                    'success': False,
                    'message': 'Username must be at least 3 characters'
                }), 400
            if username_exists(data['username'], user_id):
                return jsonify({
                    'success': False,
                    'message': 'Username already exists'
                }), 409

        # Check email uniqueness (if changing)
        if 'email' in data:
            if not validate_email(data['email']):
                return jsonify({
                    'success': False,
                    'message': 'Invalid email format'
                }), 400
            if email_exists(data['email'], user_id):
                return jsonify({
                    'success': False,
                    'message': 'Email already exists'
                }), 409

        # Validate password if provided
        if 'password' in data and data['password']:
            if len(data['password']) < 8:
                return jsonify({
                    'success': False,
                    'message': 'Password must be at least 8 characters'
                }), 400

        conn = get_connection()
        cursor = conn.cursor()

        # Build update query for users table
        user_updates = []
        user_params = []

        if 'username' in data:
            user_updates.append("username = %s")
            user_params.append(data['username'])

        # DIRECT PASSWORD CHANGE (No old password required for admins)
        if 'password' in data and data['password']:
            if len(data['password']) < 8:
                return jsonify({'success': False, 'message': 'Password must be at least 8 characters'}), 400

            hashed_password = hash_password(data['password'])
            user_updates.append("password = %s")
            user_params.append(hashed_password)

        if 'role' in data:
            user_updates.append("role = %s")
            user_params.append(data['role'])

        if 'campusId' in data or 'campus_id' in data:
            cid = data.get('campusId') or data.get('campus_id')
            if cid == '' or cid == 'undefined' or cid == 'null':
                cid = None
            user_updates.append("campus_id = %s")
            user_params.append(cid)

        if 'isActive' in data:
            is_active = data.get('isActive', 'true').lower() == 'true'
            user_updates.append("is_active = %s")
            user_params.append(is_active)

        user_updates.append("updated_at = %s")
        user_params.append(datetime.now())
        user_params.append(user_id)

        if len(user_updates) > 1:
            update_query = f"UPDATE users SET {', '.join(user_updates)} WHERE id = %s"
            cursor.execute(update_query, user_params)

        # Build update query for user_details table
        details_updates = []
        details_params = []

        if 'firstName' in data:
            details_updates.append("first_name = %s")
            details_params.append(data['firstName'])

        if 'lastName' in data:
            details_updates.append("last_name = %s")
            details_params.append(data['lastName'])

        if 'email' in data:
            details_updates.append("email = %s")
            details_params.append(data['email'])

        # Handle Avatar Update
        if file and file.filename != '':
            # New File Uploaded
            new_avatar_path = save_avatar(file, str(user_id))
            if new_avatar_path:
                details_updates.append("avatar = %s")
                details_params.append(new_avatar_path)
        elif 'avatar' in data and data['avatar']:
            # URL String Provided (or restoring old string)
            details_updates.append("avatar = %s")
            details_params.append(data['avatar'])

        details_params.append(user_id)

        if details_updates:
            update_details = f"UPDATE user_details SET {', '.join(details_updates)} WHERE user_id = %s"
            cursor.execute(update_details, details_params)

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'message': 'User updated successfully'}), 200

    except Exception as e:
        if 'conn' in locals(): conn.close()
        return jsonify({'success': False, 'message': f'Error updating user: {str(e)}'}), 500

# Delete user (soft delete)
@users_bp.route('/<signed_int:user_id>/', methods=['DELETE'])
@jwt_required()
@bitress_required
def delete_user(user_id):
    """Soft delete a user"""
    try:
        # Get current user ID from JWT
        current_user_id = get_jwt_identity()

        # Prevent deletion of bitress super admin (id = -999)
        if user_id == -999:
            return jsonify({
                'success': False,
                'message': 'Cannot delete bitress super admin account'
            }), 403

        # Prevent deletion of primary admin (id = -1)
        if user_id == -1:
            return jsonify({
                'success': False,
                'message': 'Cannot delete primary admin account'
            }), 403

        # Prevent self-deletion
        if user_id == current_user_id:
            return jsonify({
                'success': False,
                'message': 'Cannot delete your own account'
            }), 403

        # Check if user exists
        if not user_exists(user_id):
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404

        conn = get_connection()
        cursor = conn.cursor()

        # Soft delete (set deleted_at timestamp)
        cursor.execute(
            "UPDATE users SET deleted_at = %s WHERE id = %s",
            (datetime.now(), user_id)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'User deleted successfully'
        }), 200

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({
            'success': False,
            'message': f'Error deleting user: {str(e)}'
        }), 500


# Restore deleted user
@users_bp.route('/<int:user_id>/restore/', methods=['PUT'])
@jwt_required()
@bitress_required
def restore_user(user_id):
    """Restore a soft-deleted user"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if user exists and is deleted
        cursor.execute(
            "SELECT id FROM users WHERE id = %s AND deleted_at IS NOT NULL",
            (user_id,)
        )

        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Deleted user not found'
            }), 404

        # Restore user (clear deleted_at)
        cursor.execute(
            "UPDATE users SET deleted_at = NULL WHERE id = %s",
            (user_id,)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'User restored successfully'
        }), 200

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({
            'success': False,
            'message': f'Error restoring user: {str(e)}'
        }), 500


# Toggle user active status
@users_bp.route('/<signed_int:user_id>/toggle-status/', methods=['PUT'])
@jwt_required()
@privilegedRoleRequired
def toggle_user_status(user_id):
    """Toggle user active/inactive status"""
    try:
        # Prevent toggling bitress super admin
        if user_id == -999:
            return jsonify({
                'success': False,
                'message': 'Cannot modify bitress super admin status'
            }), 403

        # Prevent toggling primary admin
        if user_id == -1:
            return jsonify({
                'success': False,
                'message': 'Cannot modify primary admin status'
            }), 403

        # Check if user exists
        if not user_exists(user_id):
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404

        conn = get_connection()
        cursor = conn.cursor()

        # Get current status
        cursor.execute(
            "SELECT is_active FROM users WHERE id = %s AND deleted_at IS NULL",
            (user_id,)
        )
        result = cursor.fetchone()

        if not result:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404

        # Toggle status
        current_status = result['is_active']
        new_status = not current_status

        cursor.execute(
            "UPDATE users SET is_active = %s, updated_at = %s WHERE id = %s",
            (new_status, datetime.now(), user_id)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'User {"activated" if new_status else "deactivated"} successfully',
            'is_active': new_status
        }), 200

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({
            'success': False,
            'message': f'Error toggling user status: {str(e)}'
        }), 500


# Get all deleted users
@users_bp.route('/deleted/', methods=['GET'])
@jwt_required()
@privilegedRoleRequired
def get_deleted_users():
    """Get all soft-deleted users including faculty"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       SELECT u.id,
                              u.username,
                              u.role,
                              u.campus_id,
                              u.is_active,
                              u.created_at,
                              u.deleted_at,
                              ud.first_name,
                              ud.last_name,
                              ud.email,
                              ud.avatar,
                              c.name as campus_name
                       FROM users u
                                LEFT JOIN user_details ud ON u.id = ud.user_id
                                LEFT JOIN campuses c ON u.campus_id = c.campus_id
                       WHERE u.deleted_at IS NOT NULL
                         AND u.role IN ('admin', 'faculty')
                       ORDER BY u.deleted_at DESC
                       """)

        users = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'users': users,
            'count': len(users)
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching deleted users: {str(e)}'
        }), 500