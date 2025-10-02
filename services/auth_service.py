import datetime
import uuid

import pymysql
from flask_jwt_extended import create_access_token, create_refresh_token
from utils.config import email_activation_enabled
from config import Config
from extensions import mail
from flask_mail import Message
from storage import get_connection, redis_client
from models.user import User
from utils.hashing import hash_password, verify_password
from utils.response import success, error
from utils.utils import generate_avatar
from services.notification_service import create_notification
from services.email_service import send_activation_email
class AuthService:
    @staticmethod
    def login(username, password):
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE username = %s AND deleted_at IS NULL", (username,))
                data = cursor.fetchone()
                if not data:
                    return error("Invalid username or password."), 401

                user = User(data)
                if not verify_password(password, user.password):
                    return error("Invalid username or password."), 401
                
                if user.is_active == 0:
                    return error("Account is inactive. Please activate your account."), 403

                # JWT tokens
                claims = {"role": user.role, "username": user.username}
                token = create_access_token(identity=str(user.id), additional_claims=claims)
                refresh_token = create_refresh_token(identity=str(user.id), additional_claims=claims)

                # Optionally store refresh token in Redis (TTL = 7 days)
                redis_client.setex(f"refresh_token:{user.id}", 60 * 60 * 24 * 7, refresh_token)

                response_data = {
                    "token": token,
                    "refresh_token": refresh_token,
                    "user": user.to_dict(),
                    "is_admin": user.role == "admin",
                }

                return success("Login successful", response_data), 200

        except Exception as e:
            return error(f"Login failed: {str(e)}"), 500
        finally:
            connection.close()

    @staticmethod
    def register(data):
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                
                # Student ID check
                cursor.execute(
                    "SELECT id FROM students WHERE student_id = %s AND deleted_at IS NULL", 
                    (data["student_id"],)
                )
                if cursor.fetchone():
                    return error("The student ID is already in use."), 409
                
                # Username check
                cursor.execute(
                    "SELECT id FROM users WHERE username = %s AND deleted_at IS NULL", 
                    (data["username"],)
                )
                if cursor.fetchone():
                    return error("The username is already taken."), 409

                # Email check
                cursor.execute(
                    "SELECT id FROM students WHERE email = %s AND deleted_at IS NULL", 
                    (data["email"],)
                )
                if cursor.fetchone():
                    return error("The email is already registered."), 409

                hashed = hash_password(data["password"])
                activation_required = email_activation_enabled()

                status = 0 if activation_required else 1
                activation_code = str(uuid.uuid4()) if activation_required else None

                name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
                avatar = generate_avatar(name)
                # Insert into users
                cursor.execute("""
                    INSERT INTO users (username, password, is_active, activation_code)
                    VALUES (%s, %s, %s, %s)
                """, (data["username"], hashed, status, activation_code))
                user_id = connection.insert_id()

                # Insert into students
                cursor.execute("""
                    INSERT INTO students (
                        user_id, student_id, last_name, first_name, middle_name,
                        name_extension, gender, birth_date, contact_number, email, avatar
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    data["student_id"],
                    data.get("last_name"),
                    data.get("first_name"),
                    data.get("middle_name"),
                    data.get("name_extension"),
                    data.get("gender"),
                    data.get("birth_date"),
                    data.get("contact_number"),
                    data.get("email"),
                    avatar
                ))

            connection.commit()
            
            if activation_required:
                context = {
                    "student_name": data.get("first_name", "") + " " + data.get("last_name", ""),
                    "student_id": data["student_id"],
                    "email": data["email"],
                    "registration_date": datetime.datetime.utcnow().strftime("%B %d, %Y"),
                    "activation_link": f"{Config.APP_URL}/activate?code={activation_code}"
                }
                send_activation_email(data["email"], context)
                return success("Registration successful. Please check your email."), 201
            else:
                return success("Registration successful. You can now log in."), 201

        except pymysql.err.IntegrityError:
            connection.rollback()
            return error("Integrity error: Duplicate entry detected."), 400
        except Exception as e:
            connection.rollback()
            return error(f"Registration failed: {str(e)}"), 500
        finally:
            connection.close()

    @staticmethod
    def request_password_reset(email, ip_address=None, user_agent=None):
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                # Find user by email
                cursor.execute("""
                    SELECT u.id 
                    FROM users u
                    JOIN students s ON s.user_id = u.id
                    WHERE s.email = %s AND u.deleted_at IS NULL
                """, (email,))
                row = cursor.fetchone()
                if not row:
                    return error("No account found with this email"), 404

                user_id = row["id"]
                token = str(uuid.uuid4())
                expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=12)

                # Insert reset token
                cursor.execute("""
                    INSERT INTO password_reset_tokens (user_id, token, expires_at, ip_address, user_agent)
                    VALUES (%s, %s, %s, %s, %s)
                """, (user_id, token, expires_at, ip_address, user_agent))
                connection.commit()

                reset_link = f"{Config.APP_URL}/reset-password?token={token}"

                # Send email
                msg = Message(
                    subject="iScholar Password Reset",
                    sender=Config.MAIL_USERNAME,
                    recipients=[email]
                )
                msg.body = f"""
                Hello,

                You requested to reset your password. Please click the link below to reset:

                {reset_link}

                This link will expire in 12 hours. If you didn’t request a reset, you can safely ignore this email.

                -- iScholar Team
                """
                mail.send(msg)

                return success("Password reset link sent"), 200

        except Exception as e:
            connection.rollback()
            return error(f"Failed to request password reset: {str(e)}"), 500
        finally:
            connection.close()

    @staticmethod
    def confirm_password_reset(token, new_password):
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                # Validate token
                cursor.execute("""
                               SELECT *
                               FROM password_reset_tokens
                               WHERE token = %s
                                 AND used_at IS NULL
                                 AND expires_at > NOW()
                               """, (token,))
                reset_entry = cursor.fetchone()
                if not reset_entry:
                    return error("Invalid or expired token"), 400

                user_id = reset_entry["user_id"]
                hashed = hash_password(new_password)

                # Update user password
                cursor.execute("""
                               UPDATE users
                               SET password   = %s,
                                   updated_at = NOW()
                               WHERE id = %s
                               """, (hashed, user_id))

                # Mark token as used
                cursor.execute("""
                               UPDATE password_reset_tokens
                               SET used_at    = NOW(),
                                   updated_at = NOW()
                               WHERE id = %s
                               """, (reset_entry["id"],))

            connection.commit()
            return success("Password has been reset successfully"), 200

        except Exception as e:
            connection.rollback()
            return error(f"Failed to reset password: {str(e)}"), 500
        finally:
            connection.close()