from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import Config
from routes.application import application_bp
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
app.register_blueprint(application_bp)


@app.route("/")
def index():
    return {"status": "API ready"}, 200


@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(debug=True)
