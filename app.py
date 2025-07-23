from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import Config
from routes.academic import campus_bp
from routes.academic_period import academic_period_bp
from routes.applicants import applicants_bp
from routes.application import application_bp
from routes.profile import profile_bp
from routes.auth import auth_bp
from routes.meta import meta_bp

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = Config.JWT_SECRET_KEY
CORS(app)
JWTManager(app)

app.register_blueprint(meta_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(application_bp)
app.register_blueprint(applicants_bp, strict_slashes=False)
app.register_blueprint(academic_period_bp)
app.register_blueprint(campus_bp)
@app.route("/")
def index():
    return {"status": "API ready"}, 200
@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok"}), 200
if __name__ == "__main__":
    app.run(host='0.0.0.0',debug=True)