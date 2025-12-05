from werkzeug.security import generate_password_hash, check_password_hash

# Role constants
ROLE_BITRESS = "bitress"
ROLE_ADMIN = "admin"
ROLE_FACULTY = "faculty"
ROLE_STUDENT = "student"

# Roles that have admin-level privileges (unrestricted or campus-scoped)
ADMIN_ROLES = [ROLE_BITRESS, ROLE_ADMIN, ROLE_FACULTY]

# Roles that are unrestricted (no campus scope)
UNRESTRICTED_ROLES = [ROLE_BITRESS, ROLE_ADMIN]


class User:
    def __init__(self, data):
        self.id = data.get("id")
        self.username = data.get("username")
        self.password = data.get("password")
        self.role = data.get("role")
        self.campus_id = data.get("campus_id")
        self.is_active = data.get("is_active")

    def check_password(self, raw_pw):
        return check_password_hash(self.password, raw_pw)

    def is_unrestricted(self):
        """Check if user has unrestricted access (admin/bitress)"""
        return self.role in UNRESTRICTED_ROLES

    def is_faculty(self):
        """Check if user has faculty role"""
        return self.role == ROLE_FACULTY

    def has_campus_access(self, target_campus_id):
        """Check if user has access to a specific campus"""
        if self.is_unrestricted():
            return True
        if self.is_faculty():
            return self.campus_id is not None and self.campus_id == target_campus_id
        return False

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "campus_id": self.campus_id,
            "is_active": self.is_active
        }
