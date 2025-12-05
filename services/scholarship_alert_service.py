"""
Scholarship Alert Service

This service handles:
1. Matching new scholarships against existing student profiles
2. Storing match alerts in the database
3. Sending notifications for high-match scholarships
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from storage import get_connection
from services.recommend_service import RecommendationService
from services.notification_service import create_notification
from utils.utils import extract_applicant_flags

logger = logging.getLogger(__name__)

# Threshold scores for alert levels
HIGH_MATCH_THRESHOLD = 75.0  # Score >= 75% triggers notification
MINIMUM_MATCH_THRESHOLD = 60.0  # Score >= 60% is stored as alert


def trigger_scholarship_matching(scholarship_id: int, send_notifications: bool = True) -> Dict[str, Any]:
    """
    Trigger matching process for a specific scholarship against all eligible students.
    
    This function:
    1. Fetches all students with completed profiles and evaluations
    2. Runs recommendation algorithm for each student against the scholarship
    3. Stores matches with score >= MINIMUM_MATCH_THRESHOLD in scholarship_match_alerts
    4. Triggers notifications for high-match students (score >= HIGH_MATCH_THRESHOLD)
    
    Args:
        scholarship_id: The ID of the scholarship to match against students
        send_notifications: Whether to send notifications for high-match students
        
    Returns:
        Dict with matching results summary
    """
    connection = None
    cursor = None
    
    try:
        connection = get_connection()
        cursor = connection.cursor()
        
        # Verify scholarship exists and is active
        cursor.execute("""
            SELECT id, name, is_active, grant_amount
            FROM scholarships
            WHERE id = %s AND deleted_at IS NULL
        """, (scholarship_id,))
        scholarship = cursor.fetchone()
        
        if not scholarship:
            return {
                "success": False,
                "error": "Scholarship not found",
                "matches": 0
            }
            
        if not scholarship["is_active"]:
            return {
                "success": False,
                "error": "Scholarship is not active",
                "matches": 0
            }
        
        # Fetch all students with completed evaluations (have been through the system)
        cursor.execute("""
            SELECT DISTINCT
                s.user_id as student_id,
                s.first_name,
                s.last_name,
                e.gwa,
                e.income,
                e.total_units as units_enrolled,
                e.score as base_score,
                e.classification,
                fb.ip_affiliation,
                fb.father_occupation,
                fb.mother_occupation,
                fb.is_pwd,
                ei.course_id,
                ei.department_id,
                ei.campus_id,
                ei.year_level
            FROM students s
            JOIN users u ON s.user_id = u.id
            JOIN applications a ON a.student_id = s.user_id
            JOIN evaluations e ON e.application_id = a.id AND e.deleted_at IS NULL
            LEFT JOIN family_background fb ON fb.student_id = s.user_id
            LEFT JOIN education_info ei ON ei.student_id = s.user_id AND ei.semester_id = a.semester_id
            WHERE u.is_active = 1
            AND a.deleted_at IS NULL
            GROUP BY s.user_id
        """)
        students = cursor.fetchall()
        
        if not students:
            return {
                "success": True,
                "message": "No eligible students found",
                "matches": 0,
                "high_matches": 0,
                "notifications_sent": 0
            }
        
        recommendation_service = RecommendationService(cursor)
        
        matches_stored = 0
        high_matches = 0
        notifications_sent = 0
        
        for student in students:
            try:
                # Build applicant_data from student record
                applicant_data = _build_applicant_data(student)
                
                # Build evaluation_data from student record
                evaluation_data = {
                    "score": float(student["base_score"]) if student["base_score"] else 0.5,
                    "classification": student["classification"] or "Unknown",
                    "gwa": float(student["gwa"]) if student["gwa"] else 0.0,
                    "income": float(student["income"]) if student["income"] else 0.0,
                    "units_enrolled": int(student["units_enrolled"]) if student["units_enrolled"] else 0
                }
                
                # Check if scholarship matches this student
                match_result = recommendation_service.recommend_for_scholarship(
                    scholarship_id, applicant_data, evaluation_data
                )
                
                if match_result and match_result["score"] >= MINIMUM_MATCH_THRESHOLD:
                    # Store the match alert
                    _store_match_alert(
                        cursor,
                        student["student_id"],
                        scholarship_id,
                        match_result
                    )
                    matches_stored += 1
                    
                    # Send notification for high matches
                    if match_result["score"] >= HIGH_MATCH_THRESHOLD:
                        high_matches += 1
                        
                        if send_notifications:
                            try:
                                _send_match_notification(
                                    student["student_id"],
                                    scholarship,
                                    match_result
                                )
                                notifications_sent += 1
                            except Exception as e:
                                logger.error(f"Failed to send notification for student {student['student_id']}: {e}")
                                
            except Exception as e:
                logger.error(f"Error matching student {student.get('student_id')}: {e}")
                continue
        
        connection.commit()
        
        logger.info(f"Scholarship {scholarship_id} matching complete: "
                   f"{matches_stored} matches, {high_matches} high matches, "
                   f"{notifications_sent} notifications sent")
        
        return {
            "success": True,
            "scholarship_id": scholarship_id,
            "scholarship_name": scholarship["name"],
            "students_processed": len(students),
            "matches": matches_stored,
            "high_matches": high_matches,
            "notifications_sent": notifications_sent
        }
        
    except Exception as e:
        logger.error(f"Error in trigger_scholarship_matching: {e}")
        if connection:
            connection.rollback()
        return {
            "success": False,
            "error": str(e),
            "matches": 0
        }
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_student_scholarship_alerts(
    student_id: int,
    unread_only: bool = False,
    page: int = 1,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get scholarship match alerts for a specific student.
    
    Args:
        student_id: The student's user ID
        unread_only: If True, only return unread alerts
        page: Page number for pagination
        limit: Results per page
        
    Returns:
        Dict with alerts list and pagination info
    """
    connection = None
    cursor = None
    
    try:
        connection = get_connection()
        cursor = connection.cursor()
        
        # Build query conditions
        conditions = ["sma.student_id = %s"]
        params = [student_id]
        
        if unread_only:
            conditions.append("sma.is_read = 0")
        
        where_clause = " AND ".join(conditions)
        
        # Get total count
        count_query = f"""
            SELECT COUNT(*) as total 
            FROM scholarship_match_alerts sma
            WHERE {where_clause}
        """
        cursor.execute(count_query, params)
        total = cursor.fetchone()["total"]
        
        # Get unread count
        cursor.execute("""
            SELECT COUNT(*) as unread 
            FROM scholarship_match_alerts 
            WHERE student_id = %s AND is_read = 0
        """, (student_id,))
        unread_count = cursor.fetchone()["unread"]
        
        # Get alerts with scholarship details
        offset = (page - 1) * limit
        query = f"""
            SELECT 
                sma.id,
                sma.scholarship_id,
                s.name as scholarship_name,
                s.description,
                s.grant_amount,
                sma.match_score,
                sma.match_summary,
                sma.top_factors,
                sma.is_read,
                sma.created_at
            FROM scholarship_match_alerts sma
            JOIN scholarships s ON sma.scholarship_id = s.id
            WHERE {where_clause}
            AND s.deleted_at IS NULL
            AND s.is_active = 1
            ORDER BY sma.created_at DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [limit, offset])
        alerts_raw = cursor.fetchall()
        
        # Process alerts
        alerts = []
        for alert in alerts_raw:
            top_factors = []
            if alert["top_factors"]:
                try:
                    top_factors = json.loads(alert["top_factors"])
                except (json.JSONDecodeError, TypeError):
                    top_factors = []
            
            # Get deadline from active semester if available
            cursor.execute("""
                SELECT end_date 
                FROM semesters 
                WHERE is_active = 1 
                LIMIT 1
            """)
            semester = cursor.fetchone()
            deadline = semester["end_date"].isoformat() if semester and semester.get("end_date") else None
            
            alerts.append({
                "id": alert["id"],
                "scholarship_id": alert["scholarship_id"],
                "scholarship_name": alert["scholarship_name"],
                "match_score": float(alert["match_score"]),
                "match_summary": alert["match_summary"],
                "grant_amount": float(alert["grant_amount"]) if alert["grant_amount"] else None,
                "deadline": deadline,
                "top_factors": top_factors,
                "created_at": alert["created_at"].isoformat() if alert["created_at"] else None,
                "is_read": bool(alert["is_read"])
            })
        
        return {
            "unread_count": unread_count,
            "alerts": alerts,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if limit > 0 else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting scholarship alerts for student {student_id}: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def mark_alert_read(alert_id: int, student_id: int) -> bool:
    """
    Mark a specific scholarship alert as read.
    
    Args:
        alert_id: The alert ID
        student_id: The student's user ID (for verification)
        
    Returns:
        True if successful, False otherwise
    """
    connection = None
    cursor = None
    
    try:
        connection = get_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            UPDATE scholarship_match_alerts
            SET is_read = 1, read_at = NOW()
            WHERE id = %s AND student_id = %s AND is_read = 0
        """, (alert_id, student_id))
        
        success = cursor.rowcount > 0
        connection.commit()
        
        if success:
            logger.info(f"Marked alert {alert_id} as read for student {student_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error marking alert {alert_id} as read: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def _build_applicant_data(student: Dict) -> Dict:
    """Build applicant_data dict from student record."""
    from utils.utils import smart_detect_flags
    
    flags = smart_detect_flags(
        student.get("father_occupation", ""),
        student.get("mother_occupation", "")
    )
    
    return {
        "is_ofw": flags.get("is_ofw", False),
        "is_farmers_child": flags.get("is_farmers_child", False),
        "is_ip": student.get("ip_affiliation") not in ("None", "N/A", None, ""),
        "is_pwd": bool(student.get("is_pwd")),
        "course_id": student.get("course_id", 0),
        "department_id": student.get("department_id", 0),
        "campus_id": student.get("campus_id", 0),
        "year_level": student.get("year_level", 0),
        "total_income": float(student.get("income", 0))
    }


def _store_match_alert(cursor, student_id: int, scholarship_id: int, match_result: Dict) -> None:
    """Store a scholarship match alert in the database."""
    # Extract top 3 factors for quick display
    top_factors = []
    if match_result.get("match_explanation"):
        explanation = match_result["match_explanation"]
        strength_factors = explanation.get("strength_factors", [])
        for factor in strength_factors[:3]:
            top_factors.append(f"{factor['factor']} ({factor['score']}%)")
    
    match_summary = None
    if match_result.get("match_explanation"):
        match_summary = match_result["match_explanation"].get("summary", "")
    
    cursor.execute("""
        INSERT INTO scholarship_match_alerts 
        (student_id, scholarship_id, match_score, match_summary, top_factors)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
            match_score = VALUES(match_score),
            match_summary = VALUES(match_summary),
            top_factors = VALUES(top_factors),
            updated_at = NOW()
    """, (
        student_id,
        scholarship_id,
        match_result["score"],
        match_summary,
        json.dumps(top_factors)
    ))


def _send_match_notification(student_id: int, scholarship: Dict, match_result: Dict) -> int:
    """Send notification for a high-match scholarship."""
    scholarship_name = scholarship["name"]
    score = match_result["score"]
    amount = scholarship.get("grant_amount", 0)
    
    # Get summary from match explanation
    summary = "New matching scholarship found!"
    if match_result.get("match_explanation"):
        summary = match_result["match_explanation"].get("summary", summary)
    
    return create_notification(
        user_id=student_id,
        message_type="scholarship_recommended",
        title=f"🎓 New Scholarship Match: {scholarship_name}",
        message=f"{summary} Match score: {score}%. Grant amount: ₱{amount:,.2f}",
        metadata={
            "scholarship_id": scholarship["id"],
            "scholarship_name": scholarship_name,
            "match_score": score,
            "grant_amount": amount,
            "type": "scholarship_match_alert"
        },
        priority="high" if score >= 85 else "normal",
        action_url=f"/applicant/scholarships/{scholarship['id']}"
    )
