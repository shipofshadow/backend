from werkzeug.security import generate_password_hash, check_password_hash

class User:
    def __init__(self, data):
        self.id = data.get("id")
        self.username = data.get("username")
        self.password = data.get("password")
        self.role = data.get("role")
        self.is_active = data.get("is_active")

    def check_password(self, raw_pw):
        return check_password_hash(self.password, raw_pw)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "is_active": self.is_active
        }
