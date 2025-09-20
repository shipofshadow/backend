# routes/oauth.py
import json

from flask import Blueprint, url_for, redirect
from authlib.integrations.flask_client import OAuth
from flask_jwt_extended import create_access_token, create_refresh_token
import urllib.parse
from config import Config
from models.user import User
from routes.auth import refresh_token
from storage import get_connection

oauth_bp = Blueprint("oauth", __name__, url_prefix="/auth")

# Configure OAuth
oauth = OAuth()
google = oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=Config.GOOGLE_CLIENT_ID,
    client_secret=Config.GOOGLE_CLIENT_SECRET,
    client_kwargs={"scope": "openid email profile"},
)

@oauth_bp.record_once
def init_oauth(state):
    app = state.app
    oauth.init_app(app)

# --- Google Login ---
@oauth_bp.route("/google")
def login_google():
    redirect_uri = url_for("oauth.authorize_google", _external=True)
    return google.authorize_redirect(redirect_uri)


@oauth_bp.route("/authorize/google")
def authorize_google():
    token = google.authorize_access_token()
    resp = google.get("https://openidconnect.googleapis.com/v1/userinfo")
    user_info = resp.json()

    email = user_info.get("email")
    provider_id = user_info.get("sub")
    first_name = user_info.get("given_name")
    last_name = user_info.get("family_name")
    avatar = user_info.get("picture")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
                   SELECT u.*, s.provider, s.provider_id
                   FROM users u
                            INNER JOIN social_logins s ON s.user_id = u.id
                   WHERE s.provider = %s
                     AND s.provider_id = %s
                   """, ("google", provider_id))
    oauth_user = cursor.fetchone()

    if oauth_user:
        user_id = oauth_user["id"]
        user = User(oauth_user)

        cursor.execute("SELECT id FROM students WHERE user_id = %s", (user_id,))
        student_profile = cursor.fetchone()
        needs_profile = not bool(student_profile)

    else:
        cursor.execute("""
                       SELECT *
                       FROM students
                       WHERE email = %s
                       """, (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            user_id = existing_user["user_id"]
            user = User(existing_user)

            cursor.execute("""
                           INSERT INTO social_logins (user_id, provider, provider_id, created_at)
                           VALUES (%s, %s, %s, NOW())
                           """, (user_id, "google", provider_id))
            connection.commit()

            cursor.execute("SELECT id FROM students WHERE user_id = %s", (user_id,))
            student_profile = cursor.fetchone()
            needs_profile = not bool(student_profile)

            if not existing_user.get("email") or existing_user.get("email") != email:
                cursor.execute("""
                               UPDATE students
                               SET email = %s
                               WHERE id = %s
                               """, (email, user_id))
                connection.commit()

        else:
            base_username = email.split("@")[0]
            username = base_username
            counter = 1

            while True:
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                if not cursor.fetchone():
                    break
                username = f"{base_username}{counter}"
                counter += 1

            cursor.execute("""
                           INSERT INTO users (username, password, role, is_active)
                           VALUES (%s, %s, %s, %s)
                           """, (username, None, "student", 1))
            connection.commit()
            user_id = cursor.lastrowid

            cursor.execute("""
                           INSERT INTO social_logins (user_id, provider, provider_id, created_at)
                           VALUES (%s, %s, %s, NOW())
                           """, (user_id, "google", provider_id))
            connection.commit()

            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user_data = cursor.fetchone()
            user = User(user_data)

            needs_profile = True

    cursor.close()
    connection.close()

    # Issue JWT token for session
    claims = {"role": user.role, "username": user.username}
    token = create_access_token(identity=str(user_id), additional_claims=claims)
    refresh_token = create_refresh_token(identity=str(user_id), additional_claims=claims)

    params = {
        "token": token,
        "refresh_token": refresh_token,
        "needs_profile": str(needs_profile).lower(),
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "avatar": avatar,
        "user": json.dumps(user.to_dict()),
    }
    redirect_url = f"{Config.APP_URL}/auth/callback?{urllib.parse.urlencode(params)}"
    return redirect(redirect_url)