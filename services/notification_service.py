import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from extensions import socketio
from storage import get_connection

logger = logging.getLogger(__name__)

# Valid notification types
NOTIFICATION_TYPES = {
    'application_submitted': 'Application Submitted',
    'application_approved': 'Application Approved',
    'application_denied': 'Application Denied',
    'scholarship_awarded': 'Scholarship Awarded',
    'scholarship_recommended': 'Scholarship Recommended',
    'scholarship_match_alert': 'New Scholarship Match',
    'system_announcement': 'System Announcement',
    'deadline_reminder': 'Deadline Reminder',
    'new_application': 'New Application',
    'document_required': 'Document Required',
    'payment_processed': 'Payment Processed',
    'profile_updated': 'Profile Updated',
    'password_changed': 'Password Changed'
}

PRIORITY_LEVELS = ['low', 'normal', 'high', 'urgent']


def create_notification(
        user_id: int,
        message_type: str,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        priority: str = 'normal',
        expires_at: Optional[datetime] = None,
        action_url: Optional[str] = None
) -> int:
    """
    Create a new notification and send real-time update

    Args:
        user_id: Target user ID
        message_type: Type of notification (must be in NOTIFICATION_TYPES)
        title: Notification title
        message: Notification message
        metadata: Additional data as JSON
        priority: Priority level (low, normal, high, urgent)
        expires_at: Optional expiration datetime
        action_url: Optional URL for action button

    Returns:
        int: Created notification ID
    """
    try:
        # Validate inputs
        if message_type not in NOTIFICATION_TYPES:
            raise ValueError(f"Invalid notification type: {message_type}")

        if priority not in PRIORITY_LEVELS:
            raise ValueError(f"Invalid priority level: {priority}")

        if not title or not message:
            raise ValueError("Title and message are required")

        connection = get_connection()
        cursor = connection.cursor()

        # Verify user exists
        cursor.execute("SELECT id, role FROM users WHERE id = %s AND is_active = 1", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise ValueError(f"User {user_id} not found or inactive")

        # Insert notification
        cursor.execute("""
                       INSERT INTO notifications
                       (user_id, type, title, message, metadata, priority, expires_at, action_url, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                       """, (
                           user_id,
                           message_type,
                           title,
                           message,
                           json.dumps(metadata) if metadata else None,
                           priority,
                           expires_at,
                           action_url
                       ))

        connection.commit()
        notification_id = cursor.lastrowid

        # Get the created notification for real-time emission
        cursor.execute("""
                       SELECT id,
                              type,
                              title,
                              message,
                              metadata,
                              priority,
                              action_url,
                              created_at
                       FROM notifications
                       WHERE id = %s
                       """, (notification_id,))

        notification_data = cursor.fetchone()
        cursor.close()
        connection.close()

        # Prepare real-time data
        realtime_data = {
            "id": notification_data["id"],
            "type": notification_data["type"],
            "title": notification_data["title"],
            "message": notification_data["message"],
            "priority": notification_data["priority"],
            "action_url": notification_data["action_url"],
            "metadata": json.loads(notification_data["metadata"]) if notification_data["metadata"] else {},
            "created_at": notification_data["created_at"].isoformat(),
            "timestamp": datetime.now().isoformat()
        }

        # Send real-time notification
        socketio.emit(
            "notification",
            realtime_data,
            room=str(user_id)
        )

        # Send specific event based on type
        if message_type in ['application_approved', 'application_denied']:
            socketio.emit(
                "application_status_changed",
                {**realtime_data, "status": message_type.replace('application_', '')},
                room=str(user_id)
            )
        elif message_type == 'scholarship_recommended':
            socketio.emit("scholarship_recommended", realtime_data, room=str(user_id))
        elif message_type == 'scholarship_match_alert':
            socketio.emit("scholarship_match_alert", realtime_data, room=str(user_id))
        elif message_type == 'system_announcement':
            socketio.emit("system_announcement", realtime_data, room=str(user_id))

        logger.info(f"Created notification {notification_id} for user {user_id}: {title}")
        return notification_id

    except Exception as e:
        logger.error(f"Error creating notification: {str(e)}")
        raise


def get_user_notifications(
        user_id: int,
        page: int = 1,
        limit: int = 20,
        notification_type: Optional[str] = None,
        unread_only: bool = False
) -> Dict[str, Any]:
    """Get paginated notifications for a user"""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Build query conditions
        conditions = ["user_id = %s"]
        params = [user_id]

        if notification_type:
            conditions.append("type = %s")
            params.append(notification_type)

        if unread_only:
            conditions.append("is_read = 0")

        # Add expiration check
        conditions.append("(expires_at IS NULL OR expires_at > NOW())")

        where_clause = " AND ".join(conditions)

        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM notifications WHERE {where_clause}"
        cursor.execute(count_query, params)
        total = cursor.fetchone()["total"]

        # Get notifications
        offset = (page - 1) * limit
        query = f"""
            SELECT id, type, title, message, metadata, priority, action_url, 
                   is_read, created_at, expires_at
            FROM notifications 
            WHERE {where_clause}
            ORDER BY 
                CASE priority 
                    WHEN 'urgent' THEN 1 
                    WHEN 'high' THEN 2 
                    WHEN 'normal' THEN 3 
                    WHEN 'low' THEN 4 
                END,
                created_at DESC
            LIMIT %s OFFSET %s
        """

        cursor.execute(query, params + [limit, offset])
        notifications = cursor.fetchall()

        # Get unread count
        unread_query = f"SELECT COUNT(*) as unread FROM notifications WHERE user_id = %s AND is_read = 0 AND (expires_at IS NULL OR expires_at > NOW())"
        cursor.execute(unread_query, (user_id,))
        unread_count = cursor.fetchone()["unread"]

        cursor.close()
        connection.close()

        # Process notifications
        processed_notifications = []
        for notif in notifications:
            processed_notif = dict(notif)
            if processed_notif['metadata']:
                processed_notif['metadata'] = json.loads(processed_notif['metadata'])
            processed_notif['created_at'] = processed_notif['created_at'].isoformat()
            if processed_notif['expires_at']:
                processed_notif['expires_at'] = processed_notif['expires_at'].isoformat()
            processed_notifications.append(processed_notif)

        return {
            "notifications": processed_notifications,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            },
            "unread_count": unread_count
        }

    except Exception as e:
        logger.error(f"Error getting notifications for user {user_id}: {str(e)}")
        raise


def mark_notification_read(notification_id: int, user_id: int) -> bool:
    """Mark a specific notification as read"""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
                       UPDATE notifications
                       SET is_read = 1,
                           read_at = NOW()
                       WHERE id = %s
                         AND user_id = %s
                         AND is_read = 0
                       """, (notification_id, user_id))

        success = cursor.rowcount > 0
        connection.commit()
        cursor.close()
        connection.close()

        if success:
            logger.info(f"Marked notification {notification_id} as read for user {user_id}")

        return success

    except Exception as e:
        logger.error(f"Error marking notification {notification_id} as read: {str(e)}")
        raise


def mark_all_notifications_read(user_id: int) -> int:
    """Mark all notifications as read for a user"""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
                       UPDATE notifications
                       SET is_read = 1,
                           read_at = NOW()
                       WHERE user_id = %s
                         AND is_read = 0
                       """, (user_id,))

        updated_count = cursor.rowcount
        connection.commit()
        cursor.close()
        connection.close()

        logger.info(f"Marked {updated_count} notifications as read for user {user_id}")
        return updated_count

    except Exception as e:
        logger.error(f"Error marking all notifications as read for user {user_id}: {str(e)}")
        raise


def delete_notification(notification_id: int, user_id: int) -> bool:
    """Delete a specific notification"""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
                       DELETE
                       FROM notifications
                       WHERE id = %s
                         AND user_id = %s
                       """, (notification_id, user_id))

        success = cursor.rowcount > 0
        connection.commit()
        cursor.close()
        connection.close()

        if success:
            logger.info(f"Deleted notification {notification_id} for user {user_id}")

        return success

    except Exception as e:
        logger.error(f"Error deleting notification {notification_id}: {str(e)}")
        raise


def get_notification_stats(user_id: int) -> Dict[str, Any]:
    """Get notification statistics for a user"""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Overall stats
        cursor.execute("""
                       SELECT COUNT(*)                                as total,
                              COUNT(CASE WHEN is_read = 0 THEN 1 END) as unread,
                              COUNT(CASE WHEN is_read = 1 THEN 1 END) as read,
                COUNT(CASE WHEN priority = 'urgent' THEN 1 END) as urgent,
                COUNT(CASE WHEN priority = 'high' THEN 1 END) as high
                       FROM notifications
                       WHERE user_id = %s AND (expires_at IS NULL OR expires_at > NOW())
                       """, (user_id,))

        overall = cursor.fetchone()

        # By type
        cursor.execute("""
                       SELECT type,
                              COUNT(*) as count,
                   COUNT(CASE WHEN is_read = 0 THEN 1 END) as unread
                       FROM notifications
                       WHERE user_id = %s AND (expires_at IS NULL OR expires_at > NOW())
                       GROUP BY type
                       ORDER BY count DESC
                       """, (user_id,))

        by_type = cursor.fetchall()

        # Recent activity (last 7 days)
        cursor.execute("""
                       SELECT DATE (created_at) as date, COUNT (*) as count
                       FROM notifications
                       WHERE user_id = %s AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                       GROUP BY DATE (created_at)
                       ORDER BY date DESC
                       """, (user_id,))

        recent_activity = cursor.fetchall()

        cursor.close()
        connection.close()

        # Process recent activity for chart data
        activity_data = []
        for activity in recent_activity:
            activity_data.append({
                "date": activity["date"].isoformat(),
                "count": activity["count"]
            })

        return {
            "overall": dict(overall),
            "by_type": [dict(row) for row in by_type],
            "recent_activity": activity_data
        }

    except Exception as e:
        logger.error(f"Error getting notification stats for user {user_id}: {str(e)}")
        raise


def notify_admin(message: str, title: str = "Admin Notification", metadata: Optional[Dict] = None) -> List[int]:
    """Send notification to all admin users"""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Get all active admin users
        cursor.execute("SELECT id FROM users WHERE role = 'admin' AND is_active = 1")
        admin_users = cursor.fetchall()

        cursor.close()
        connection.close()

        notification_ids = []
        for admin in admin_users:
            notif_id = create_notification(
                user_id=admin["id"],
                message_type="system_announcement",
                title=title,
                message=message,
                metadata=metadata,
                priority="high"
            )
            notification_ids.append(notif_id)

        logger.info(f"Sent admin notification to {len(notification_ids)} admins")
        return notification_ids

    except Exception as e:
        logger.error(f"Error sending admin notification: {str(e)}")
        raise


def notify_student_application_status(application_id: int, status: str, remarks: Optional[str] = None):
    """Send notification when application status changes"""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Get application and student details
        cursor.execute("""
                       SELECT a.student_id, st.first_name, st.last_name, sem.name as semester_name
                       FROM applications a
                                JOIN students st ON a.student_id = st.user_id
                                JOIN users s ON st.user_id = s.id
                                JOIN semesters sem ON a.semester_id = sem.id
                       WHERE a.id = %s
                       """, (application_id,))

        app_data = cursor.fetchone()
        cursor.close()
        connection.close()

        if not app_data:
            raise ValueError(f"Application {application_id} not found")

        print(app_data)
        # Prepare notification content
        status_messages = {
            'approved': {
                'title': '✅ Application Approved!',
                'message': f'Your scholarship application for {app_data["semester_name"]} has been approved.'
            },
            'denied': {
                'title': '❌ Application Denied',
                'message': f'Your scholarship application for {app_data["semester_name"]} has been denied.'
            },
            'pending': {
                'title': '⏳ Application Under Review',
                'message': f'Your scholarship application for {app_data["semester_name"]} is being reviewed.'
            }
        }

        notification_content = status_messages.get(status, {
            'title': f'Application Status: {status.title()}',
            'message': f'Your application status has been updated to {status}.'
        })

        if remarks:
            notification_content['message'] += f' Remarks: {remarks}'

        # Send notification
        return create_notification(
            user_id=app_data["student_id"],
            message_type=f'application_{status}',
            title=notification_content['title'],
            message=notification_content['message'],
            metadata={
                'application_id': application_id,
                'status': status,
                'remarks': remarks,
                'semester': app_data["semester_name"]
            },
            action_url=f'/applicant/application/{application_id}',
            priority='high' if status in ['approved', 'denied'] else 'normal'
        )

    except Exception as e:
        logger.error(f"Error sending application status notification: {str(e)}")
        raise


def notify_scholarship_recommendation(application_id: int, scholarship_id: int, score: float):
    """Send notification when scholarship is recommended"""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Get details
        cursor.execute("""
                       SELECT a.student_id,
                              s.name as scholarship_name,
                              s.grant_amount,
                              st.first_name,
                              st.last_name
                       FROM applications a
                                JOIN recommended_scholarships rs ON a.id = rs.application_id
                                JOIN scholarships s ON rs.scholarship_id = s.id
                                JOIN students st ON a.student_id = st.id
                                JOIN users u ON st.user_id = u.id
                       WHERE a.id = %s
                         AND s.id = %s
                       """, (application_id, scholarship_id))

        data = cursor.fetchone()
        cursor.close()
        connection.close()

        if not data:
            raise ValueError(f"Recommendation data not found")

        return create_notification(
            user_id=data["student_id"],
            message_type='scholarship_recommended',
            title='🎓 Scholarship Recommended!',
            message=f'You have been recommended for the {data["scholarship_name"]} scholarship (₱{data["grant_amount"]:,.2f}) with a score of {score:.1f}%.',
            metadata={
                'application_id': application_id,
                'scholarship_id': scholarship_id,
                'scholarship_name': data["scholarship_name"],
                'grant_amount': data["grant_amount"],
                'score': score
            },
            priority='high',
            action_url=f'/student/applications/{application_id}'
        )

    except Exception as e:
        logger.error(f"Error sending scholarship recommendation notification: {str(e)}")
        raise


def notify_admin_new_application(
        application_id: int,
        student_info: Dict,
        application_data: Dict,
) -> Dict:
    """
    Notify administrators about new application submission with detailed information.
    """
    try:
        # Prepare notification metadata
        metadata = {
            "application_id": application_id,
            "student_id": student_info.get("student_id"),
            "student_name": f"{student_info.get('firstname', '')} {student_info.get('lastname', '')}".strip(),
            "email": student_info.get("email"),
            "contact_number": student_info.get("contact_number"),
            "submission_timestamp": datetime.now().isoformat(),
            "semester": application_data.get("semester_name", "Unknown"),
            "academic_year": application_data.get("academic_year", "Unknown"),
            "priority": "normal",
            "category": "new_application"
        }

        # Craft notification message
        message = f"""
        New scholarship application submitted by {metadata['student_name']} 
        """

        # Send notification to all active admins
        admin_ids = notify_admin(
            message=message.strip(),
            title=f"New Application #{application_id}",
            metadata=metadata
        )

        logger.info(f"Notification sent to {len(admin_ids)} administrators for application {application_id}")

        return {
            "success": True,
            "admin_count": len(admin_ids),
            "admin_ids": admin_ids,
            "message": "Notification sent successfully"
        }

    except Exception as e:
        logger.error(f"Failed to send admin notification: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "admin_count": 0
        }

