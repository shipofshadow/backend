import traceback

from flasgger import Swagger
from flask import Flask, jsonify
from flask_caching import Cache
from flask_cors import CORS
from flask_jwt_extended import JWTManager, decode_token
from flask_mail import Mail
from flask_socketio import SocketIO, disconnect, join_room

from config import Config
from extensions import jwt, socketio
from routes.academic import campus_bp
from routes.academic_period import academic_period_bp
from routes.applicants import applicants_bp
from routes.application import application_bp
from routes.application_draft import application_draft_bp
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.evaluation import evaluations_bp
from routes.fuzzy_logic import fuzzy_bp
from routes.meta import meta_bp
from routes.notification import notification_bp
from routes.oauth import oauth_bp
from routes.prequalify import prequalify_bp
from routes.profile import profile_bp
from routes.scholarship_summary import scholarship_summary_bp
from routes.scholarships import scholarships_bp
from utils.applications import email_exists
from utils.response import error

app = Flask(__name__)
cache = Cache()

# Core config
app.config['JWT_SECRET_KEY'] = Config.JWT_SECRET_KEY
app.config["CACHE_TYPE"] = "RedisCache"
app.config["CACHE_REDIS_HOST"] = Config.REDIS_HOST
app.config["CACHE_REDIS_PORT"] = Config.REDIS_PORT
app.config["CACHE_REDIS_PASSWORD"] = Config.REDIS_PASSWORD
app.config["CACHE_DEFAULT_TIMEOUT"] = 60
app.config['SECRET_KEY'] = Config.FERNET_KEY

app.config["MAIL_SERVER"] = Config.MAIL_SERVER
app.config["MAIL_PORT"] = Config.MAIL_PORT
app.config["MAIL_USE_TLS"] = Config.MAIL_USE_TLS
app.config["MAIL_USERNAME"] = Config.MAIL_USERNAME
app.config["MAIL_PASSWORD"] = Config.MAIL_PASSWORD
app.config["MAIL_DEFAULT_SENDER"] = Config.MAIL_DEFAULT_SENDER


# Init extensions
jwt.init_app(app)
cache.init_app(app)
socketio.init_app(app, cors_allowed_origins=[
    "http://localhost:5173",
    "https://ischolar.xyz",
    "https://www.ischolar.xyz",
    "http://ischolar.test"
],)

# CORS
CORS(app, supports_credentials=True, resources={r"/*": {"origins": [
    "http://localhost:5173",
    "https://ischolar.xyz",
    "https://www.ischolar.xyz",
    "http://ischolar.test"
]}})

mail = Mail(app)


# Blueprints
app.register_blueprint(meta_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(application_bp)
app.register_blueprint(applicants_bp, strict_slashes=False)
app.register_blueprint(academic_period_bp)
app.register_blueprint(campus_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(evaluations_bp)
app.register_blueprint(scholarships_bp)
app.register_blueprint(fuzzy_bp)
app.register_blueprint(scholarship_summary_bp)
app.register_blueprint(prequalify_bp)
app.register_blueprint(notification_bp, strict_slashes=False)
app.register_blueprint(application_draft_bp, strict_slashes=False)
app.register_blueprint(oauth_bp)
# Swagger
swagger = Swagger(app)

# Routes
@app.errorhandler(404)
def not_found(er):
    return jsonify(error(message="Not found")), 404

@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok"}), 200

@socketio.on("connect")
def handle_connect(auth):
    """
    WebSocket connection handler.
    Expects: { "token": "JWT_TOKEN" } from client
    """
    try:
        if not auth or "token" not in auth:
            print("❌ No token provided")
            return disconnect()

        decoded = decode_token(auth["token"])
        user_id = decoded["sub"]
        join_room(str(user_id))
        print(f"User {user_id} connected to WebSocket")
    except Exception as e:
        print("WebSocket auth failed:", str(e))
        traceback.print_exc()
        return disconnect()


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8000, debug=True)
