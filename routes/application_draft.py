import json

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from storage import redis_client

application_draft_bp = Blueprint("application_draft", __name__, url_prefix="/api/application/draft/")

def make_draft_key(user_id, semester_id):
    return f"ischolar:apply:{user_id or 'anon'}:{semester_id or 'term'}"

@application_draft_bp.route("/save", methods=["PUT"])
@jwt_required()
def save_draft():
    user_id = get_jwt_identity()  # assuming JWT holds user id
    data = request.get_json()
    semester_id = data.get("semesterId")

    key = make_draft_key(user_id, semester_id)
    redis_client.set(key, json.dumps(data))
    return jsonify({"success": True, "key": key})

@application_draft_bp.route("/retrieve", methods=["GET"])
@jwt_required()
def load_draft():
    user_id = get_jwt_identity()
    semester_id = request.args.get("semesterId")

    key = make_draft_key(user_id, semester_id)
    value = redis_client.get(key)

    print(value)
    print(key)

    if not value:
        return jsonify(None)

    return jsonify(json.loads(value))
