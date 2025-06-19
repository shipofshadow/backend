from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import Config
from routes.profile import profile_bp
from routes.auth import auth_bp
from routes.meta import meta_bp

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = Config.JWT_SECRET_KEY
CORS(app)
JWTManager(app)

app.register_blueprint(auth_bp)
app.register_blueprint(meta_bp)
app.register_blueprint(profile_bp)

@app.route("/")
def index():
    return {"status": "API ready"}, 200

@app.errorhandler(404)
def not_found():
    return jsonify({
        "error": "Not Found",
        "message": "The requested URL was not found on the server.",
        "status": 404
    }), 404

if __name__ == "__main__":
    app.run(debug=True)
