# routes/oauth.py
import json

from flask import Blueprint, url_for, redirect, request
from authlib.integrations.flask_client import OAuth
from flask_jwt_extended import create_access_token, create_refresh_token
import urllib.parse
from config import Config
from models.user import User
from routes.auth import refresh_token
from storage import get_connection
from utils.utils import save_avatar

oauth_bp = Blueprint("oauth", __name__, url_prefix="/auth")

# Configure OAuth
oauth = OAuth()

# Google OAuth (existing)
google = oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=Config.GOOGLE_CLIENT_ID,
    client_secret=Config.GOOGLE_CLIENT_SECRET,
    client_kwargs={"scope": "openid email profile"},
)

# Facebook OAuth (new)
facebook = oauth.register(
    name="facebook",
    client_id=Config.FACEBOOK_CLIENT_ID,
    client_secret=Config.FACEBOOK_CLIENT_SECRET,
    authorize_url="https://www.facebook.com/v18.0/dialog/oauth",
    access_token_url="https://graph.facebook.com/v18.0/oauth/access_token",
    client_kwargs={"scope": "email public_profile"},
)


@oauth_bp.record_once
def init_oauth(state):
    app = state.app
    oauth.init_app(app)


# --- Google Login (existing) ---
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

    return handle_oauth_user("google", provider_id, email, first_name, last_name, avatar)


# --- Facebook Login (new) ---
@oauth_bp.route("/facebook")
def login_facebook():
    redirect_uri = url_for("oauth.authorize_facebook", _external=True)
    return facebook.authorize_redirect(redirect_uri)


@oauth_bp.route("/authorize/facebook")
def authorize_facebook():
    try:
        token = facebook.authorize_access_token()
        resp = facebook.get(
            "https://graph.facebook.com/v18.0/me?fields=id,name,email,first_name,last_name,picture.type(large)")
        user_info = resp.json()

        # Handle potential missing email (Facebook users can hide email)
        email = user_info.get("email")
        provider_id = user_info.get("id")
        first_name = user_info.get("first_name", "")
        last_name = user_info.get("last_name", "")
        birth_day = user_info.get('user_birthday')

        # Facebook picture URL structure - get the large picture
        avatar = None
        if user_info.get("picture") and user_info["picture"].get("data"):
            avatar = user_info["picture"]["data"].get("url")

        return handle_oauth_user("facebook", provider_id, email, first_name, last_name, avatar)

    except Exception as e:
        # Log the error and redirect to login with error message
        print(f"Facebook OAuth error: {str(e)}")
        error_params = {"error": "facebook_auth_failed", "message": "Facebook authentication failed"}
        redirect_url = f"{Config.APP_URL}/login?{urllib.parse.urlencode(error_params)}"
        return redirect(redirect_url)


# --- Shared OAuth Handler ---
def     handle_oauth_user(provider, provider_id, email, first_name, last_name, avatar):
    """
    Shared function to handle OAuth user authentication for both Google and Facebook
    """
    connection = get_connection()
    cursor = connection.cursor()

    # Check if user already exists with this OAuth provider
    cursor.execute("""
                   SELECT u.*, s.provider, s.provider_id
                   FROM users u
                            INNER JOIN social_logins s ON s.user_id = u.id
                   WHERE s.provider = %s
                     AND s.provider_id = %s
                   """, (provider, provider_id))
    oauth_user = cursor.fetchone()

    if oauth_user:
        # Existing OAuth user
        user_id = oauth_user["id"]
        user = User(oauth_user)

        cursor.execute("SELECT id FROM students WHERE user_id = %s", (user_id,))
        student_profile = cursor.fetchone()
        needs_profile = not bool(student_profile)

    else:
        # Check if user exists by email in students table
        existing_user = None
        if email:
            cursor.execute("""
                           SELECT s.*, u.id as user_id, u.username, u.role, u.is_active
                           FROM students s
                                    JOIN users u ON s.user_id = u.id
                           WHERE s.email = %s
                           """, (email,))
            existing_user = cursor.fetchone()

        if existing_user:
            # Link existing student account to OAuth provider
            user_id = existing_user["user_id"]
            user = User(existing_user)

            cursor.execute("""
                           INSERT INTO social_logins (user_id, provider, provider_id, created_at)
                           VALUES (%s, %s, %s, NOW())
                           """, (user_id, provider, provider_id))
            connection.commit()

            cursor.execute("SELECT id FROM students WHERE user_id = %s", (user_id,))
            student_profile = cursor.fetchone()
            needs_profile = not bool(student_profile)

            # Update email if not set or different
            if not existing_user.get("email") or existing_user.get("email") != email:
                cursor.execute("""
                               UPDATE students
                               SET email = %s
                               WHERE user_id = %s
                               """, (email, user_id))
                connection.commit()

        elif not existing_user or email and first_name and last_name:
            # Try name match instead of email
            cursor.execute("""
                           SELECT u.id AS user_id, s.id AS student_id, s.email, s.first_name, s.last_name
                           FROM users u
                                    JOIN students s ON s.user_id = u.id
                           WHERE s.first_name = %s
                             AND s.last_name = %s
                           """, (first_name, last_name))
            possible_match = cursor.fetchone()

            if possible_match:
                cursor.close()
                connection.close()

                # Don't auto-link — send flag back to frontend
                params = {
                    "possible_link": "true",
                    "existing_id": possible_match["user_id"],
                    "existing_email": possible_match["email"] or "",
                    "existing_first_name": possible_match["first_name"],
                    "existing_last_name": possible_match["last_name"],
                    "provider": provider,
                    "provider_id": provider_id,
                    "oauth_email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "avatar": avatar or "",
                }
                redirect_url = f"{Config.APP_URL}/auth/callback?{urllib.parse.urlencode(params)}"
                return redirect(redirect_url)
            else:
                # Create new user account
                user_id, user, needs_profile = create_new_oauth_user(
                    cursor, connection, provider, provider_id, email, first_name, last_name
                )
        else:
            # No email provided or no name match, create account anyway
            user_id, user, needs_profile = create_new_oauth_user(
                cursor, connection, provider, provider_id, email, first_name, last_name
            )

    cursor.close()
    connection.close()

    # Save avatar using storage-aware system if URL provided
    saved_avatar = None
    if avatar:
        try:
            saved_avatar = save_avatar(avatar, str(user_id))
        except Exception as e:
            print(f"Error saving OAuth avatar: {e}")
            saved_avatar = None

    # Issue JWT tokens
    claims = {"role": user.role, "username": user.username}
    access_token = create_access_token(identity=str(user_id), additional_claims=claims)
    refresh_token_val = create_refresh_token(identity=str(user_id), additional_claims=claims)

    # Prepare redirect parameters
    params = {
        "token": access_token,
        "refresh_token": refresh_token_val,
        "needs_profile": str(needs_profile).lower(),
        "email": email or "",
        "first_name": first_name or "",
        "last_name": last_name or "",
        "avatar": saved_avatar or avatar or "",
        "user": json.dumps(user.to_dict()),
    }

    redirect_url = f"{Config.APP_URL}/auth/callback?{urllib.parse.urlencode(params)}"
    return redirect(redirect_url)


def create_new_oauth_user(cursor, connection, provider, provider_id, email, first_name, last_name):
    """
    Create a new user account for OAuth authentication
    """
    # Generate unique username
    if email:
        base_username = email.split("@")[0]
    elif first_name and last_name:
        base_username = f"{first_name.lower()}.{last_name.lower()}"
    else:
        base_username = f"{provider}_user"

    username = base_username
    counter = 1

    while True:
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if not cursor.fetchone():
            break
        username = f"{base_username}{counter}"
        counter += 1

    # Create user account
    cursor.execute("""
                   INSERT INTO users (username, password, role, is_active)
                   VALUES (%s, %s, %s, %s)
                   """, (username, None, "student", 1))
    connection.commit()
    user_id = cursor.lastrowid

    # Create social login record
    cursor.execute("""
                   INSERT INTO social_logins (user_id, provider, provider_id, created_at)
                   VALUES (%s, %s, %s, NOW())
                   """, (user_id, provider, provider_id))
    connection.commit()

    # Get user data
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user_data = cursor.fetchone()
    user = User(user_data)

    needs_profile = True

    return user_id, user, needs_profile


@oauth_bp.route("/link-account", methods=["POST"])
def link_oauth_account():
    """
    Endpoint to manually link an OAuth account to an existing user account
    Called when user confirms they want to link the accounts
    """
    try:
        data = request.get_json()

        # Required parameters
        user_id = data.get("user_id")
        provider = data.get("provider")
        provider_id = data.get("provider_id")
        oauth_email = data.get("oauth_email")
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        avatar = data.get("avatar", "")

        if not all([user_id, provider, provider_id]):
            return {"error": "Missing required parameters"}, 400

        connection = get_connection()
        cursor = connection.cursor()

        # Verify the user exists
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        if not user_data:
            return {"error": "User not found"}, 404

        # Check if this OAuth account is already linked to another user
        cursor.execute("""
                       SELECT user_id
                       FROM social_logins
                       WHERE provider = %s
                         AND provider_id = %s
                       """, (provider, provider_id))
        existing_link = cursor.fetchone()

        if existing_link:
            return {"error": "This social account is already linked to another user"}, 400

        # Create the social login link
        cursor.execute("""
                       INSERT INTO social_logins (user_id, provider, provider_id, created_at)
                       VALUES (%s, %s, %s, NOW())
                       """, (user_id, provider, provider_id))
        connection.commit()

        # Update student email if OAuth provided one and student doesn't have one
        if oauth_email:
            cursor.execute("""
                           UPDATE students
                           SET email = COALESCE(email, %s)
                           WHERE user_id = %s
                           """, (oauth_email, user_id))
            connection.commit()

        # Get updated user data
        cursor.execute("""
                       SELECT s.*, u.id as user_id, u.username, u.role, u.is_active
                       FROM students s
                                JOIN users u ON s.user_id = u.id
                       WHERE u.id = %s
                       """, (user_id,))
        student_data = cursor.fetchone()

        user = User(student_data)

        cursor.execute("SELECT id FROM students WHERE user_id = %s", (user_id,))
        student_profile = cursor.fetchone()
        needs_profile = not bool(student_profile)

        cursor.close()
        connection.close()

        # Issue JWT tokens
        claims = {"role": user.role, "username": user.username}
        access_token = create_access_token(identity=str(user_id), additional_claims=claims)
        refresh_token_val = create_refresh_token(identity=str(user_id), additional_claims=claims)

        return {
            "success": True,
            "token": access_token,
            "refresh_token": refresh_token_val,
            "user": user.to_dict(),
            "needs_profile": needs_profile,
            "message": f"{provider.title()} account linked successfully"
        }, 200

    except Exception as e:
        return {"error": f"Failed to link account: {str(e)}"}, 500


@oauth_bp.route("/create-new-account", methods=["POST"])
def create_new_oauth_account():
    """
    Endpoint to create a completely new account from OAuth data
    Called when user chooses not to link to existing account
    """
    try:
        data = request.get_json()

        provider = data.get("provider")
        provider_id = data.get("provider_id")
        email = data.get("oauth_email")
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")

        if not all([provider, provider_id]):
            return {"error": "Missing required parameters"}, 400

        connection = get_connection()
        cursor = connection.cursor()

        # Check if this OAuth account is already linked
        cursor.execute("""
                       SELECT user_id
                       FROM social_logins
                       WHERE provider = %s
                         AND provider_id = %s
                       """, (provider, provider_id))
        existing_link = cursor.fetchone()

        if existing_link:
            return {"error": "This social account is already registered"}, 400

        # Create new user
        user_id, user, needs_profile = create_new_oauth_user(
            cursor, connection, provider, provider_id, email, first_name, last_name
        )

        cursor.close()
        connection.close()

        # Issue JWT tokens
        claims = {"role": user.role, "username": user.username}
        access_token = create_access_token(identity=str(user_id), additional_claims=claims)
        refresh_token_val = create_refresh_token(identity=str(user_id), additional_claims=claims)

        return {
            "success": True,
            "token": access_token,
            "refresh_token": refresh_token_val,
            "user": user.to_dict(),
            "needs_profile": needs_profile,
            "message": "New account created successfully"
        }, 200

    except Exception as e:
        return {"error": f"Failed to create account: {str(e)}"}, 500