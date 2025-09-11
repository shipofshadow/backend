# routes/reset_routes.py
from flask import Blueprint, request, jsonify
from functools import wraps
import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime
import logging

# Create blueprint
reset_bp = Blueprint('reset', __name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def admin_required(f):
    """Decorator to require admin authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authorization header required'}), 401

        token = auth_header.split(' ')[1]

        # Verify token and check if user is admin
        # Replace this with your actual JWT verification logic
        try:
            # Import your JWT verification function
            from your_auth_module import verify_token, get_user_from_token

            payload = verify_token(token)
            user = get_user_from_token(payload)

            if not user or user.get('role') != 'admin':
                return jsonify({'error': 'Admin access required'}), 403

        except Exception as e:
            return jsonify({'error': 'Invalid token'}), 401

        return f(*args, **kwargs)

    return decorated_function


def get_db_connection():
    """Get database connection"""
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'ischolar_dev'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            port=os.getenv('DB_PORT', 3306)
        )
        return connection
    except Error as e:
        logger.error(f"Error connecting to database: {e}")
        raise e


def execute_reset_script(connection, include_sample_data=False):
    """Execute the database reset script"""
    cursor = connection.cursor()

    try:
        # Disable foreign key checks
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute("SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO'")

        reset_queries = [
            # Clear scholarship selections and recommendations first
            "DELETE FROM scholarship_selections",
            "DELETE FROM recommended_scholarships",

            # Clear evaluations
            "DELETE FROM evaluations",

            # Clear application files
            "DELETE FROM application_files",

            # Clear application grades
            "DELETE FROM application_grades",

            # Clear applications
            "DELETE FROM applications",

            # Clear student-related data
            "DELETE FROM family_background",
            "DELETE FROM education_info",
            "DELETE FROM addresses",

            # Clear students
            "DELETE FROM students",

            # Clear student users only
            "DELETE FROM users WHERE role = 'student'",
        ]

        # Execute deletion queries
        for query in reset_queries:
            cursor.execute(query)
            logger.info(f"Executed: {query}")

        # Reset AUTO_INCREMENT values
        auto_increment_queries = [
            "ALTER TABLE scholarship_selections AUTO_INCREMENT = 1",
            "ALTER TABLE recommended_scholarships AUTO_INCREMENT = 1",
            "ALTER TABLE evaluations AUTO_INCREMENT = 1",
            "ALTER TABLE application_files AUTO_INCREMENT = 1",
            "ALTER TABLE application_grades AUTO_INCREMENT = 1",
            "ALTER TABLE applications AUTO_INCREMENT = 1",
            "ALTER TABLE family_background AUTO_INCREMENT = 1",
            "ALTER TABLE education_info AUTO_INCREMENT = 1",
            "ALTER TABLE addresses AUTO_INCREMENT = 1",
            "ALTER TABLE students AUTO_INCREMENT = 1",
        ]

        for query in auto_increment_queries:
            cursor.execute(query)
            logger.info(f"Executed: {query}")

        # Reset users AUTO_INCREMENT to continue from existing admin users
        cursor.execute("SELECT COALESCE(MAX(id), 0) FROM users")
        max_user_id = cursor.fetchone()[0]
        cursor.execute(f"ALTER TABLE users AUTO_INCREMENT = {max_user_id + 1}")

        # Insert sample data if requested
        if include_sample_data:
            sample_queries = [
                """INSERT IGNORE INTO academic_years (year_start, year_end)
                   VALUES (2024, 2025),
                          (2025, 2026)""",
                """INSERT IGNORE INTO semesters (academic_year_id, name, is_active)
                   VALUES (1, '1st Semester', 1),
                          (1, '2nd Semester', 0),
                          (1, 'Summer', 0),
                          (2, '1st Semester', 0),
                          (2, '2nd Semester', 0),
                          (2, 'Summer', 0)"""
            ]

            for query in sample_queries:
                cursor.execute(query)
                logger.info(f"Executed sample data: {query}")

        # Re-enable foreign key checks
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

        # Get verification counts
        verification_queries = {
            'applications_cleared': "SELECT COUNT(*) FROM applications",
            'students_cleared': "SELECT COUNT(*) FROM students",
            'student_users_cleared': "SELECT COUNT(*) FROM users WHERE role = 'student'",
            'admin_users_preserved': "SELECT COUNT(*) FROM users WHERE role = 'admin'",
            'campuses_preserved': "SELECT COUNT(*) FROM campuses",
            'departments_preserved': "SELECT COUNT(*) FROM departments",
            'courses_preserved': "SELECT COUNT(*) FROM courses",
            'scholarships_preserved': "SELECT COUNT(*) FROM scholarships"
        }

        verification_results = {}
        for key, query in verification_queries.items():
            cursor.execute(query)
            verification_results[key] = cursor.fetchone()[0]

        connection.commit()
        logger.info("Database reset completed successfully")

        return verification_results

    except Error as e:
        connection.rollback()
        logger.error(f"Error during database reset: {e}")
        raise e
    finally:
        cursor.close()


@reset_bp.route('/api/reset', methods=['POST'])
@admin_required
def reset_database():
    """
    Reset the iScholar database

    POST /api/reset
    Headers: Authorization: Bearer <admin_token>
    Body: {
        "confirm": true,
        "include_sample_data": false (optional)
    }
    """
    try:
        # Get request data
        data = request.get_json() or {}

        # Require explicit confirmation
        if not data.get('confirm', False):
            return jsonify({
                'error': 'Database reset requires explicit confirmation',
                'message': 'Send {"confirm": true} in request body to proceed'
            }), 400

        include_sample_data = data.get('include_sample_data', False)

        # Log the reset attempt
        logger.info(f"Database reset initiated at {datetime.now()}")
        logger.info(f"Include sample data: {include_sample_data}")

        # Get database connection
        connection = get_db_connection()

        try:
            # Execute reset script
            verification_results = execute_reset_script(connection, include_sample_data)

            response_data = {
                'success': True,
                'message': 'Database reset completed successfully',
                'timestamp': datetime.now().isoformat(),
                'verification': verification_results,
                'actions_performed': [
                    'Cleared all student applications and related data',
                    'Removed all student accounts (preserved admin accounts)',
                    'Reset AUTO_INCREMENT values',
                    'Preserved system configuration and master data'
                ]
            }

            if include_sample_data:
                response_data['actions_performed'].append('Inserted sample academic years and semesters')

            logger.info("Database reset API call completed successfully")
            return jsonify(response_data), 200

        finally:
            connection.close()

    except mysql.connector.Error as e:
        logger.error(f"Database error during reset: {e}")
        return jsonify({
            'error': 'Database error occurred during reset',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

    except Exception as e:
        logger.error(f"Unexpected error during reset: {e}")
        return jsonify({
            'error': 'Unexpected error occurred during reset',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@reset_bp.route('/api/reset/verify', methods=['GET'])
@admin_required
def verify_reset_status():
    """
    Verify current database status

    GET /api/reset/verify
    Headers: Authorization: Bearer <admin_token>
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            verification_queries = {
                'total_applications': "SELECT COUNT(*) FROM applications",
                'total_students': "SELECT COUNT(*) FROM students",
                'student_users': "SELECT COUNT(*) FROM users WHERE role = 'student'",
                'admin_users': "SELECT COUNT(*) FROM users WHERE role = 'admin'",
                'total_campuses': "SELECT COUNT(*) FROM campuses",
                'total_departments': "SELECT COUNT(*) FROM departments",
                'total_courses': "SELECT COUNT(*) FROM courses",
                'total_scholarships': "SELECT COUNT(*) FROM scholarships",
                'active_semesters': "SELECT COUNT(*) FROM semesters WHERE is_active = 1"
            }

            status_results = {}
            for key, query in verification_queries.items():
                cursor.execute(query)
                status_results[key] = cursor.fetchone()[0]

            return jsonify({
                'success': True,
                'database_status': status_results,
                'timestamp': datetime.now().isoformat(),
                'is_reset_needed': status_results['total_applications'] > 0 or status_results['total_students'] > 0
            }), 200

        finally:
            cursor.close()
            connection.close()

    except Exception as e:
        logger.error(f"Error verifying database status: {e}")
        return jsonify({
            'error': 'Error verifying database status',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# Register the blueprint in your main app file:
# from routes.reset_routes import reset_bp
# app.register_blueprint(reset_bp)