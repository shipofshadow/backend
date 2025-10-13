from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import logging

from services.notification_service import (
    create_notification,
    get_user_notifications,
    mark_notification_read,
    mark_all_notifications_read,
    delete_notification,
    get_notification_stats
)
from storage import get_connection

notification_bp = Blueprint('notification', __name__, url_prefix='/api/notifications')
logger = logging.getLogger(__name__)

@notification_bp.route('/', methods=['GET'])
@jwt_required()
def get_notifications():
    """
    Get paginated notifications for the current user
    Query params:
    - page: Page number (default: 1)
    - limit: Items per page (default: 20, max: 100)
    - type: Filter by notification type (optional)
    - unread_only: Show only unread notifications (default: false)
    """
    try:
        user_id = get_jwt_identity()

        # Parse query parameters
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        notification_type = request.args.get('type', None)
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'

        # Get notifications
        notifications_data = get_user_notifications(
            user_id=user_id,
            page=page,
            limit=limit,
            notification_type=notification_type,
            unread_only=unread_only
        )

        return jsonify({
            "success": True,
            "data": notifications_data,
            "message": "Notifications retrieved successfully"
        }), 200

    except Exception as e:
        logger.error(f"Error getting notifications for user {user_id}: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Failed to retrieve notifications",
            "error": str(e)
        }), 500


@notification_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_notification_statistics():
    """Get notification statistics for the current user"""
    try:
        user_id = get_jwt_identity()
        stats = get_notification_stats(user_id)

        return jsonify({
            "success": True,
            "data": stats,
            "message": "Notification statistics retrieved successfully"
        }), 200

    except Exception as e:
        logger.error(f"Error getting notification stats for user {user_id}: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Failed to retrieve notification statistics",
            "error": str(e)
        }), 500


@notification_bp.route('/<int:notification_id>/read', methods=['PUT'])
@jwt_required()
def mark_notification_as_read(notification_id):
    """Mark a specific notification as read"""
    try:
        user_id = get_jwt_identity()

        success = mark_notification_read(notification_id, user_id)

        if success:
            return jsonify({
                "success": True,
                "message": "Notification marked as read"
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Notification not found or access denied"
            }), 404

    except Exception as e:
        logger.error(f"Error marking notification {notification_id} as read: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Failed to mark notification as read",
            "error": str(e)
        }), 500


@notification_bp.route('/read-all', methods=['PUT'])
@jwt_required()
def mark_all_as_read():
    """Mark all notifications as read for the current user"""
    try:
        user_id = get_jwt_identity()

        updated_count = mark_all_notifications_read(user_id)

        return jsonify({
            "success": True,
            "message": f"All {updated_count} notifications marked as read"
        }), 200

    except Exception as e:
        logger.error(f"Error marking all notifications as read for user {user_id}: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Failed to mark all notifications as read",
            "error": str(e)
        }), 500


@notification_bp.route('/<int:notification_id>', methods=['DELETE'])
@jwt_required()
def delete_user_notification(notification_id):
    """Delete a specific notification"""
    try:
        user_id = get_jwt_identity()

        success = delete_notification(notification_id, user_id)

        if success:
            return jsonify({
                "success": True,
                "message": "Notification deleted successfully"
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Notification not found or access denied"
            }), 404

    except Exception as e:
        logger.error(f"Error deleting notification {notification_id}: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Failed to delete notification",
            "error": str(e)
        }), 500


@notification_bp.route('/clear-old', methods=['DELETE'])
@jwt_required()
def clear_old_notifications():
    """Clear notifications older than specified days (default: 30 days)"""
    try:
        user_id = get_jwt_identity()
        days = request.args.get('days', 30, type=int)

        if days < 1 or days > 365:
            return jsonify({
                "success": False,
                "message": "Days must be between 1 and 365"
            }), 400

        connection = get_connection()
        cursor = connection.cursor()

        cutoff_date = datetime.now() - timedelta(days=days)

        cursor.execute(
            "DELETE FROM notifications WHERE user_id = %s AND created_at < %s",
            (user_id, cutoff_date)
        )

        deleted_count = cursor.rowcount
        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            "success": True,
            "message": f"Deleted {deleted_count} notifications older than {days} days"
        }), 200

    except Exception as e:
        logger.error(f"Error clearing old notifications for user {user_id}: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Failed to clear old notifications",
            "error": str(e)
        }), 500


# Admin-only routes
@notification_bp.route('/admin/send', methods=['POST'])
@jwt_required()
def send_admin_notification():
    """Send notification to specific user(s) - Admin only"""
    try:
        current_user_id = get_jwt_identity()

        # Check if user is admin
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        user = cursor.fetchone()
        cursor.close()
        connection.close()

        if not user or user['role'] != 'admin':
            return jsonify({
                "success": False,
                "message": "Admin access required"
            }), 403

        data = request.get_json()

        # Validate required fields
        required_fields = ['message', 'title', 'type']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "success": False,
                    "message": f"Missing required field: {field}"
                }), 400

        # Validate notification type
        valid_types = [
            'application_submitted', 'application_approved', 'application_denied',
            'scholarship_awarded', 'system_announcement', 'deadline_reminder',
            'new_application', 'scholarship_recommended', 'document_required'
        ]

        if data['type'] not in valid_types:
            return jsonify({
                "success": False,
                "message": f"Invalid notification type. Valid types: {', '.join(valid_types)}"
            }), 400

        # Handle different recipient options
        user_ids = []

        if 'user_id' in data:
            # Single user
            user_ids = [data['user_id']]
        elif 'user_ids' in data:
            # Multiple specific users
            user_ids = data['user_ids']
        elif data.get('broadcast', False):
            # Broadcast to all users
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT id FROM users WHERE is_active = 1")
            user_ids = [row['id'] for row in cursor.fetchall()]
            cursor.close()
            connection.close()
        elif 'role' in data:
            # Send to all users with specific role
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT id FROM users WHERE role = %s AND is_active = 1", (data['role'],))
            user_ids = [row['id'] for row in cursor.fetchall()]
            cursor.close()
            connection.close()
        else:
            return jsonify({
                "success": False,
                "message": "Must specify user_id, user_ids, broadcast=true, or role"
            }), 400

        # Send notifications
        notification_ids = []
        for user_id in user_ids:
            notif_id = create_notification(
                user_id=user_id,
                message_type=data['type'],
                title=data['title'],
                message=data['message'],
                metadata=data.get('metadata', {}),
                priority=data.get('priority', 'normal')
            )
            notification_ids.append(notif_id)

        return jsonify({
            "success": True,
            "message": f"Sent {len(notification_ids)} notifications",
            "data": {
                "notification_ids": notification_ids,
                "recipients_count": len(user_ids)
            }
        }), 201

    except Exception as e:
        logger.error(f"Error sending admin notification: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Failed to send notification",
            "error": str(e)
        }), 500


@notification_bp.route('/admin/stats', methods=['GET'])
@jwt_required()
def get_admin_notification_stats():
    """Get system-wide notification statistics - Admin only"""
    try:
        current_user_id = get_jwt_identity()

        # Check if user is admin
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        user = cursor.fetchone()

        if not user or user['role'] != 'admin':
            cursor.close()
            connection.close()
            return jsonify({
                "success": False,
                "message": "Admin access required"
            }), 403

        # Get system-wide stats
        cursor.execute("""
                       SELECT COUNT(*)                                as total_notifications,
                              COUNT(CASE WHEN is_read = 0 THEN 1 END) as unread_count,
                              COUNT(CASE WHEN is_read = 1 THEN 1 END) as read_count,
                              COUNT(DISTINCT user_id)                 as users_with_notifications
                       FROM notifications
                       WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                       """)

        stats = cursor.fetchone()

        # Get notifications by type
        cursor.execute("""
                       SELECT type, COUNT(*) as count
                       FROM notifications
                       WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                       GROUP BY type
                       ORDER BY count DESC
                       """)

        by_type = cursor.fetchall()

        cursor.close()
        connection.close()

        return jsonify({
            "success": True,
            "data": {
                "overview": stats,
                "by_type": by_type
            },
            "message": "Admin notification statistics retrieved successfully"
        }), 200

    except Exception as e:
        logger.error(f"Error getting admin notification stats: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Failed to retrieve admin statistics",
            "error": str(e)
        }), 500