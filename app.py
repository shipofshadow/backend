from flask import Flask, jsonify
from flask_caching import Cache
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from config import Config
from routes.academic import campus_bp
from routes.academic_period import academic_period_bp
from routes.applicants import applicants_bp
from routes.application import application_bp
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.evaluation import evaluations_bp
from routes.fuzzy_logic import fuzzy_bp
from routes.meta import meta_bp
from routes.prequalify import prequalify_bp
from routes.profile import profile_bp
from routes.scholarship_summary import scholarship_summary_bp
from routes.scholarships import scholarships_bp
from flasgger import Swagger

app = Flask(__name__)
cache = Cache()
app.config['JWT_SECRET_KEY'] = Config.JWT_SECRET_KEY
app.config["CACHE_TYPE"] = "RedisCache"
app.config["CACHE_REDIS_HOST"] = Config.REDIS_HOST
app.config["CACHE_REDIS_PORT"] = Config.REDIS_PORT
app.config["CACHE_REDIS_PASSWORD"] = Config.REDIS_PASSWORD
app.config["CACHE_DEFAULT_TIMEOUT"] = 60
CORS(app,
     supports_credentials=True,
     resources={r"/*": {
         "origins": [
             "http://localhost:5173",   # dev
             "https://ischolar.xyz",    # prod
             "https://www.ischolar.xyz" # prod with www
         ]
     }})
JWTManager(app)
cache.init_app(app)
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
swagger = Swagger(app)

@app.route("/")
def index():
    """
    Index endpoint
    ---
    responses:
      200:
        description: API is ready
        schema:
          type: object
          properties:
            status:
              type: string
              example: API ready
    """
    return {"status": "API ready"}, 200

@app.route('/api/ping', methods=['GET'])
def ping():
    """
    Ping endpoint
    ---
    responses:
      200:
        description: API is up
        schema:
          type: object
          properties:
            status:
              type: string
              example: ok
    """
    return jsonify({"status": "ok"}), 200
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)