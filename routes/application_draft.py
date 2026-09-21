import json

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from storage import redis_client

application_draft_bp = Blueprint("application_draft", __name__, url_prefix="/api/application/draft/")

DRAFT_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


def make_draft_key(user_id, semester_id):
    return f"ischolar:apply:{user_id or 'anon'}:{semester_id or 'term'}"


@application_draft_bp.route("/save", methods=["PUT"])
@jwt_required()
def save_draft():
    user_id = get_jwt_identity()
    data = request.get_json()
    semester_id = data.get("semesterId")

    key = make_draft_key(user_id, semester_id)
    redis_client.set(key, json.dumps(data), ex=DRAFT_TTL_SECONDS)
    return jsonify({"success": True, "key": key})


@application_draft_bp.route("/retrieve", methods=["GET"])
@jwt_required()
def load_draft():
    user_id = get_jwt_identity()
    semester_id = request.args.get("semesterId")

    key = make_draft_key(user_id, semester_id)
    value = redis_client.get(key)

    if not value:
        return jsonify(None)

    return jsonify(json.loads(value))


@application_draft_bp.route("/clear", methods=["DELETE"])
@jwt_required()
def clear_draft():
    """Delete the draft after successful application submission."""
    user_id = get_jwt_identity()
    semester_id = request.args.get("semesterId")

    key = make_draft_key(user_id, semester_id)
    redis_client.delete(key)
    return jsonify({"success": True})
