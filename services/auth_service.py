import pymysql
from flask_jwt_extended import create_access_token, create_refresh_token

from db import get_connection
from models.user import User
from utils.hashing import hash_password, verify_password
from utils.response import success, error


class AuthService:

    @staticmethod
    def login(username, password):
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                data = cursor.fetchone()

                if not data:
                    return error("No username found"), 401

                user = User(data)

                if not verify_password(password, user.password):
                    return error("Invalid username or password"), 401

                token = create_access_token(identity=str(user.id))
                refresh_token = create_refresh_token(identity=str(user.id))
                return success("Login successful", {
                    "token": token,
                    "refresh_token": refresh_token,
                    "user": user.to_dict()
                }), 200

        except Exception as e:
            return error(f"Login failed: {str(e)}"), 500

        finally:
            connection.close()

    @staticmethod
    def register(data):
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                # Check if username exists
                cursor.execute("SELECT id FROM users WHERE username = %s", (data.get("username"),))
                if cursor.fetchone():
                    return error("Username already exists"), 409

                hashed = hash_password(data.get("password"))

                # Insert into users
                cursor.execute("""
                    INSERT INTO users (username, password, role, is_active, created_at, updated_at)
                    VALUES (%s, %s, 'Student', 1, NOW(), NOW())
                """, (data.get("username"), hashed))
                user_id = connection.insert_id()

                # Insert into students
                cursor.execute("""
                    INSERT INTO students (
                        user_id, student_id, last_name, first_name, middle_name,
                        name_extension, gender, birth_date, email
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    data.get("student_id"),
                    data.get("last_name"),
                    data.get("first_name"),
                    data.get("middle_name"),
                    data.get("name_extension"),
                    data.get("gender"),
                    data.get("birth_date"),
                    data.get("email")
                ))
                
                # Insert into education information
                cursor.execute("""
                    INSERT INTO education_info(student_id)
                    VALUES (%s)
                """, (
                    user_id
                ))

            connection.commit()
            return success("Registration successful"), 201

        except pymysql.err.IntegrityError as e:
            connection.rollback()
            return error(f"Integrity error: {e.args[1]}"), 400

        except Exception as e:
            connection.rollback()
            return error(f"Registration failed: {str(e)}"), 500

        finally:
            connection.close()

    @staticmethod
    def update_profile(user_id, new_data):
        new_username = new_data.get("username")

        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET username = %s, updated_at = NOW() 
                    WHERE id = %s
                """, (new_username, user_id))
                connection.commit()
            return success("Account updated"), 200

        except pymysql.MySQLError as e:
            connection.rollback()
            return error(f"Database error: {e.args[1]}"), 500

        except Exception as e:
            connection.rollback()
            return error(f"Update failed: {str(e)}"), 500

        finally:
            connection.close()