from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.announcement_service import create_announcement_record, publish_announcement, get_all_announcements, \
    update_announcement, delete_announcement
from storage import get_connection

announcement_bp = Blueprint('announcement', __name__, url_prefix='/api/announcements')


@announcement_bp.route('/', methods=['GET'])
@jwt_required()
def index():
    # Only admins should see the management list
    # Add role check logic here if needed
    page = request.args.get('page', 1, type=int)
    data = get_all_announcements(page=page)
    return jsonify({"success": True, **data})


@announcement_bp.route('/create', methods=['POST'])
@jwt_required()
def create():
    author_id = get_jwt_identity()
    data = request.json

    try:
        if not data.get('title') or not data.get('message'):
            return jsonify({"success": False, "message": "Title and message required"}), 400

        id = create_announcement_record(data, author_id)

        # Auto-publish if requested
        if data.get('publish_now', False):
            publish_result = publish_announcement(id)
            return jsonify({
                "success": True,
                "message": "Announcement created and published",
                "stats": publish_result
            })

        return jsonify({"success": True, "message": "Draft created", "id": id})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@announcement_bp.route('/<int:id>/publish', methods=['POST'])
@jwt_required()
def publish(id):
    try:
        result = publish_announcement(id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@announcement_bp.route('/<int:id>', methods=['PUT'])
@jwt_required()
def update(id):
    try:
        data = request.json
        update_announcement(id, data)
        return jsonify({"success": True, "message": "Announcement updated successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@announcement_bp.route('/<int:id>', methods=['DELETE'])
@jwt_required()
def delete(id):
    try:
        delete_announcement(id)
        return jsonify({"success": True, "message": "Announcement deleted successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@announcement_bp.route('/public', methods=['GET'])
def get_public_announcements():
    """Get published announcements for the landing page (Audience: All)"""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
                       SELECT id, title, message, priority, created_at
                       FROM announcements
                       WHERE is_published = 1
                         AND audience_type = 'all'
                       ORDER BY created_at DESC LIMIT 3
                       """)

        announcements = cursor.fetchall()
        cursor.close()
        connection.close()

        # Format dates
        data = []
        for a in announcements:
            item = dict(a)
            item['created_at'] = item['created_at'].isoformat()
            data.append(item)

        return jsonify(data), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@announcement_bp.route('/feed', methods=['GET'])
@jwt_required()
def get_student_feed():
    """Get announcements relevant to the logged-in student"""
    try:
        user_id = get_jwt_identity()
        connection = get_connection()
        cursor = connection.cursor()

        # Fetch user role
        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        role = user['role'] if user else 'student'

        # Complex query to match:
        # 1. Broadcast (all)
        # 2. Role-based (e.g., 'student')
        # 3. Specific user ID (if implemented in filter)
        query = """
                SELECT id, title, message, priority, created_at, audience_type
                FROM announcements
                WHERE is_published = 1
                  AND (
                    audience_type = 'all'
                        OR (audience_type = 'role' AND JSON_EXTRACT(audience_filter, '$.role') = %s)
                    )
                ORDER BY created_at DESC LIMIT 5 \
                """

        cursor.execute(query, (role,))
        announcements = cursor.fetchall()
        cursor.close()
        connection.close()

        data = []
        for a in announcements:
            item = dict(a)
            item['created_at'] = item['created_at'].isoformat()
            data.append(item)

        return jsonify({"success": True, "data": data}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500