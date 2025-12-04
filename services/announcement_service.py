import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from storage import get_connection
from services.notification_service import create_notification

logger = logging.getLogger(__name__)


def create_announcement_record(data: Dict, author_id: int) -> int:
    """Creates a draft announcement record."""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
                       INSERT INTO announcements
                       (title, message, audience_type, audience_filter, priority, author_id, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, NOW())
                       """, (
                           data['title'],
                           data['message'],
                           data.get('audience_type', 'all'),
                           json.dumps(data.get('audience_filter', {})),
                           data.get('priority', 'normal'),
                           author_id
                       ))

        connection.commit()
        announcement_id = cursor.lastrowid
        cursor.close()
        connection.close()

        return announcement_id
    except Exception as e:
        logger.error(f"Error creating announcement: {str(e)}")
        raise


def     publish_announcement(announcement_id: int) -> Dict:
    """
    Publishes an announcement: marks it as published and triggers
    notification generation for all target users.
    """
    try:
        connection = get_connection()
        cursor = connection.cursor()

        # 1. Fetch Announcement Details
        cursor.execute("SELECT * FROM announcements WHERE id = %s", (announcement_id,))
        announcement = cursor.fetchone()

        if not announcement:
            raise ValueError("Announcement not found")

        if announcement['is_published']:
            return {"success": False, "message": "Already published"}

        # 2. Determine Recipients
        audience_type = announcement['audience_type']
        audience_filter = json.loads(announcement['audience_filter']) if announcement['audience_filter'] else {}

        target_users = []

        if audience_type == 'all':
            cursor.execute("SELECT id FROM users WHERE is_active = 1")
            target_users = [row['id'] for row in cursor.fetchall()]

        elif audience_type == 'role':
            role = audience_filter.get('role')
            cursor.execute("SELECT id FROM users WHERE role = %s AND is_active = 1", (role,))
            target_users = [row['id'] for row in cursor.fetchall()]

        elif audience_type == 'specific':
            target_users = audience_filter.get('user_ids', [])

        # 3. Fan-out Notifications (In a real production app, offload this loop to a background worker)
        sent_count = 0
        for user_id in target_users:
            create_notification(
                user_id=user_id,
                message_type='system_announcement',
                title=announcement['title'],
                message=announcement['message'],
                priority=announcement['priority'],
                metadata={'announcement_id': announcement['id']}
            )
            sent_count += 1

        # 4. Update Status
        cursor.execute("""
                       UPDATE announcements
                       SET is_published = 1,
                           published_at = NOW()
                       WHERE id = %s
                       """, (announcement_id,))

        connection.commit()
        cursor.close()
        connection.close()

        return {"success": True, "sent_count": sent_count}

    except Exception as e:
        logger.error(f"Error publishing announcement {announcement_id}: {str(e)}")
        raise


def get_all_announcements(page=1, limit=20):
    """Retrieve announcement history for admin."""
    connection = get_connection()
    cursor = connection.cursor()

    offset = (page - 1) * limit

    # Get total
    cursor.execute("SELECT COUNT(*) as total FROM announcements")
    total = cursor.fetchone()['total']

    # Get items with author info
    cursor.execute("""
                   SELECT a.*, u.username as author_name
                   FROM announcements a
                            LEFT JOIN users u ON a.author_id = u.id
                   ORDER BY a.created_at DESC
                       LIMIT %s
                   OFFSET %s
                   """, (limit, offset))

    items = cursor.fetchall()

    # Clean up JSON fields for API response
    result = []
    for item in items:
        i = dict(item)
        if i.get('audience_filter'):
            i['audience_filter'] = json.loads(i['audience_filter'])
        i['created_at'] = i['created_at'].isoformat() if i.get('created_at') else None
        i['published_at'] = i['published_at'].isoformat() if i.get('published_at') else None
        result.append(i)

    cursor.close()
    connection.close()

    return {
        "data": result,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }


# [Append/Replace in backend/services/announcement_service.py]

def update_announcement(announcement_id: int, data: Dict) -> bool:
    """Updates an announcement. Restricts critical changes if already published."""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Check current status
        cursor.execute("SELECT is_published FROM announcements WHERE id = %s", (announcement_id,))
        record = cursor.fetchone()

        if not record:
            raise ValueError("Announcement not found")

        # If published, only allow non-structural edits (e.g., typos in message)
        # If draft, allow everything
        if record['is_published']:
            cursor.execute("""
                           UPDATE announcements
                           SET title    = %s,
                               message  = %s,
                               priority = %s
                           WHERE id = %s
                           """, (
                               data['title'],
                               data['message'],
                               data.get('priority', 'normal'),
                               announcement_id
                           ))
        else:
            cursor.execute("""
                           UPDATE announcements
                           SET title           = %s,
                               message         = %s,
                               priority        = %s,
                               audience_type   = %s,
                               audience_filter = %s
                           WHERE id = %s
                           """, (
                               data['title'],
                               data['message'],
                               data.get('priority', 'normal'),
                               data.get('audience_type', 'all'),
                               json.dumps(data.get('audience_filter', {})),
                               announcement_id
                           ))

        connection.commit()
        cursor.close()
        connection.close()
        return True

    except Exception as e:
        logger.error(f"Error updating announcement {announcement_id}: {str(e)}")
        raise


def delete_announcement(announcement_id: int) -> bool:
    """Deletes an announcement record."""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("DELETE FROM announcements WHERE id = %s", (announcement_id,))

        success = cursor.rowcount > 0
        connection.commit()
        cursor.close()
        connection.close()

        return success
    except Exception as e:
        logger.error(f"Error deleting announcement {announcement_id}: {str(e)}")
        raise