from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from storage import get_connection
from services.email_service import send_application_reminder_email
from config import Config
import logging

potential_applicants_bp = Blueprint('potential_applicants', __name__, url_prefix='/api/students')


def get_active_semester(cursor):
    """Get the current active semester"""
    cursor.execute("""
        SELECT id, name, academic_year, start_date, end_date
        FROM semesters
        WHERE is_active = 1
        LIMIT 1
    """)
    return cursor.fetchone()


def get_available_scholarships_count(cursor, semester_id):
    """Get count of available scholarships for the active semester"""
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM scholarships
        WHERE deleted_at IS NULL
        AND (semester_id = %s OR semester_id IS NULL)
    """, (semester_id,))
    result = cursor.fetchone()
    return result['count'] if result else 0


def prepare_email_context(student, active_semester, scholarships_count):
    """Prepare email context for application reminder"""
    semester_name = f"{active_semester['name']} {active_semester['academic_year']}"
    return {
        "student_name": f"{student['first_name']} {student['last_name']}",
        "semester_name": semester_name,
        "available_scholarships_count": scholarships_count,
        "apply_link": f"{Config.APP_URL}/applicant/home",
        "application_deadline": active_semester.get('end_date').strftime('%B %d, %Y') if active_semester.get('end_date') else None
    }


@potential_applicants_bp.route('/potential-applicants', methods=['GET'])
@jwt_required()
def get_potential_applicants():
    """
    Get students who registered but haven't applied this semester.
    ---
    tags:
      - Potential Applicants
    security:
      - jwt: []
    responses:
      200:
        description: List of potential applicants with active semester info
      404:
        description: No active semester found
    """
    db = get_connection()
    cursor = db.cursor()

    try:
        # Get active semester
        active_semester = get_active_semester(cursor)
        if not active_semester:
            return jsonify({"error": "No active semester found"}), 404

        semester_id = active_semester['id']

        # Query for students who have registered but not applied
        cursor.execute("""
            SELECT 
                s.user_id,
                s.student_id,
                s.first_name,
                s.last_name,
                s.email,
                s.created_at as registered_at,
                CASE WHEN ar.id IS NOT NULL THEN 1 ELSE 0 END as reminder_sent,
                ar.sent_at as reminder_sent_at
            FROM students s
            LEFT JOIN applications a ON s.user_id = a.student_id 
                AND a.semester_id = %s
                AND a.deleted_at IS NULL
            LEFT JOIN application_reminders ar ON s.user_id = ar.student_id 
                AND ar.semester_id = %s
            WHERE a.id IS NULL
                AND s.is_verified = 1
                AND s.deleted_at IS NULL
            ORDER BY s.created_at DESC
        """, (semester_id, semester_id))

        potential_applicants = cursor.fetchall()

        # Convert reminder_sent to boolean
        for applicant in potential_applicants:
            applicant['reminder_sent'] = bool(applicant['reminder_sent'])

        # Format the response
        response = {
            "potentialApplicants": potential_applicants,
            "total": len(potential_applicants),
            "activeSemester": {
                "id": active_semester['id'],
                "name": active_semester['name'],
                "academicYear": active_semester['academic_year']
            }
        }

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Error fetching potential applicants: {str(e)}")
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        db.close()


@potential_applicants_bp.route('/send-application-reminder', methods=['POST'])
@jwt_required()
def send_reminder():
    """
    Send application reminder to a single student.
    Can only be sent once per semester.
    ---
    tags:
      - Potential Applicants
    security:
      - jwt: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            student_id:
              type: integer
              description: The user_id of the student
    responses:
      200:
        description: Reminder sent successfully
      400:
        description: Invalid request or reminder already sent
      404:
        description: Student or active semester not found
    """
    data = request.get_json()
    student_id = data.get('student_id')

    if not student_id:
        return jsonify({"success": False, "error": "student_id is required"}), 400

    db = get_connection()
    cursor = db.cursor()

    try:
        # Get active semester
        active_semester = get_active_semester(cursor)
        if not active_semester:
            return jsonify({"success": False, "error": "No active semester found"}), 404

        semester_id = active_semester['id']
        current_user_id = get_jwt_identity()

        # Check if reminder already sent
        cursor.execute("""
            SELECT id, sent_at FROM application_reminders
            WHERE student_id = %s AND semester_id = %s
        """, (student_id, semester_id))
        existing_reminder = cursor.fetchone()

        if existing_reminder:
            return jsonify({
                "success": False,
                "error": "Reminder already sent for this semester",
                "sent_at": existing_reminder['sent_at'].isoformat() if existing_reminder['sent_at'] else None
            }), 400

        # Get student details
        cursor.execute("""
            SELECT user_id, student_id, first_name, last_name, email
            FROM students
            WHERE user_id = %s AND is_verified = 1 AND deleted_at IS NULL
        """, (student_id,))
        student = cursor.fetchone()

        if not student:
            return jsonify({"success": False, "error": "Student not found"}), 404

        # Get available scholarships count
        scholarships_count = get_available_scholarships_count(cursor, semester_id)

        # Prepare email context
        context = prepare_email_context(student, active_semester, scholarships_count)

        # Send email
        send_application_reminder_email(student['email'], context)

        # Record the reminder
        cursor.execute("""
            INSERT INTO application_reminders (student_id, semester_id, sent_by)
            VALUES (%s, %s, %s)
        """, (student_id, semester_id, current_user_id))
        db.commit()

        # Get the sent_at timestamp
        cursor.execute("SELECT sent_at FROM application_reminders WHERE student_id = %s AND semester_id = %s", 
                      (student_id, semester_id))
        reminder = cursor.fetchone()

        return jsonify({
            "success": True,
            "message": "Reminder email sent successfully",
            "student_id": student_id,
            "sent_at": reminder['sent_at'].isoformat() if reminder and reminder['sent_at'] else None
        }), 200

    except Exception as e:
        db.rollback()
        logging.error(f"Error sending reminder: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        cursor.close()
        db.close()


@potential_applicants_bp.route('/send-bulk-reminders', methods=['POST'])
@jwt_required()
def send_bulk_reminders():
    """
    Send reminder emails to multiple students at once.
    ---
    tags:
      - Potential Applicants
    security:
      - jwt: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            student_ids:
              type: array
              items:
                type: integer
              description: List of user_ids of students
    responses:
      200:
        description: Bulk reminders processed with results summary
      400:
        description: Invalid request
      404:
        description: No active semester found
    """
    data = request.get_json()
    student_ids = data.get('student_ids', [])

    if not student_ids or not isinstance(student_ids, list):
        return jsonify({"success": False, "error": "student_ids must be a non-empty array"}), 400

    db = get_connection()
    cursor = db.cursor()

    try:
        # Get active semester
        active_semester = get_active_semester(cursor)
        if not active_semester:
            return jsonify({"success": False, "error": "No active semester found"}), 404

        semester_id = active_semester['id']
        current_user_id = get_jwt_identity()

        # Get available scholarships count
        scholarships_count = get_available_scholarships_count(cursor, semester_id)

        results = {
            "sent": 0,
            "skipped": 0,
            "details": []
        }

        for student_id in student_ids:
            # Check if reminder already sent
            cursor.execute("""
                SELECT id, sent_at FROM application_reminders
                WHERE student_id = %s AND semester_id = %s
            """, (student_id, semester_id))
            existing_reminder = cursor.fetchone()

            if existing_reminder:
                results["skipped"] += 1
                results["details"].append({
                    "student_id": student_id,
                    "status": "skipped",
                    "reason": "already_sent"
                })
                continue

            # Get student details
            cursor.execute("""
                SELECT user_id, student_id, first_name, last_name, email
                FROM students
                WHERE user_id = %s AND is_verified = 1 AND deleted_at IS NULL
            """, (student_id,))
            student = cursor.fetchone()

            if not student:
                results["skipped"] += 1
                results["details"].append({
                    "student_id": student_id,
                    "status": "skipped",
                    "reason": "student_not_found"
                })
                continue

            try:
                # Prepare email context
                context = prepare_email_context(student, active_semester, scholarships_count)

                # Send email
                send_application_reminder_email(student['email'], context)

                # Record the reminder
                cursor.execute("""
                    INSERT INTO application_reminders (student_id, semester_id, sent_by)
                    VALUES (%s, %s, %s)
                """, (student_id, semester_id, current_user_id))

                results["sent"] += 1
                results["details"].append({
                    "student_id": student_id,
                    "status": "sent"
                })

            except Exception as email_error:
                logging.error(f"Error sending reminder to student {student_id}: {str(email_error)}")
                results["skipped"] += 1
                results["details"].append({
                    "student_id": student_id,
                    "status": "skipped",
                    "reason": "email_error"
                })

        db.commit()

        return jsonify({
            "success": True,
            "results": results
        }), 200

    except Exception as e:
        db.rollback()
        logging.error(f"Error in bulk reminders: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        cursor.close()
        db.close()
