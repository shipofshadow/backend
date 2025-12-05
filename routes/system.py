from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.decorator import bitress_required
from storage import get_connection
import logging

system_bp = Blueprint('system', __name__, url_prefix='/api/system')


@system_bp.route('/reset', methods=['POST'])
@jwt_required()
@bitress_required
def reset_system():
    """
    Reset the entire system - delete all data except:
    - bitress user (id = -999)
    - admin users with id < 0 (negative IDs)
    - fuzzy_* tables (fuzzy_variables, fuzzy_sets, fuzzy_rules, fuzzy_rule_conditions)
    - configs table
    - campuses, departments, courses (academic structure)
    
    This is for fresh deployment/demo reset.
    """
    data = request.get_json()
    confirmation = data.get('confirmation') if data else None
    
    # Require exact confirmation phrase
    if confirmation != "RESET_SYSTEM_CONFIRM":
        return jsonify({
            "success": False,
            "error": "Invalid confirmation. Send 'RESET_SYSTEM_CONFIRM' to proceed."
        }), 400
    
    db = get_connection()
    cursor = db.cursor()
    
    try:
        # Disable foreign key checks temporarily
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # Tables to completely clear (order matters due to FK)
        tables_to_truncate = [
            'application_reminders',
            'application_grades',
            'application_files',
            'scholarship_selections',
            'recommended_scholarships',
            'evaluations',
            'applications',
            'education_info',
            'family_background',
            'addresses',
            'students',
            'social_logins',
            'password_reset_tokens',
            'notifications',
            'announcements',
            'prequalifications',
            'prequalification_students',
            'academic_years',
            'semesters',
            'scholarships',
            'scholarship_rules',
        ]
        
        deleted_counts = {}
        
        for table in tables_to_truncate:
            try:
                cursor.execute("SELECT COUNT(*) as count FROM `%s`" % table)
                count = cursor.fetchone()['count']
                cursor.execute("TRUNCATE TABLE `%s`" % table)
                deleted_counts[table] = count
            except Exception:
                # Table may not exist, skip it
                deleted_counts[table] = 0
        
        # Delete users except bitress (id=-999) and admins with negative IDs
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE id > 0 OR id < -999")
        user_count = cursor.fetchone()['count']
        cursor.execute("DELETE FROM users WHERE id > 0")  # Delete all positive ID users (students)
        # Keep negative ID admins including bitress
        deleted_counts['users'] = user_count
        
        # Delete user_details for deleted users
        cursor.execute("""
            DELETE FROM user_details 
            WHERE user_id NOT IN (SELECT id FROM users)
        """)
        
        # Re-enable foreign key checks
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        db.commit()
        
        # Log the reset action
        logging.warning("SYSTEM RESET performed by user %s", get_jwt_identity())
        
        return jsonify({
            "success": True,
            "message": "System reset completed successfully",
            "deleted_counts": deleted_counts,
            "preserved": [
                "bitress super admin",
                "admin users (negative IDs)",
                "fuzzy logic configuration",
                "system configs",
                "campuses/departments/courses"
            ]
        }), 200
        
    except Exception as e:
        db.rollback()
        logging.error("System reset failed: %s", str(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        cursor.close()
        db.close()


@system_bp.route('/reset/preview', methods=['GET'])
@jwt_required()
@bitress_required
def preview_reset():
    """Preview what will be deleted in a system reset"""
    db = get_connection()
    cursor = db.cursor()
    
    try:
        counts = {}
        
        tables = [
            'applications', 'students', 'users', 'notifications',
            'announcements', 'scholarships', 'academic_years', 'semesters'
        ]
        
        for table in tables:
            try:
                if table == 'users':
                    cursor.execute("SELECT COUNT(*) as count FROM users WHERE id > 0")
                else:
                    cursor.execute("SELECT COUNT(*) as count FROM `%s`" % table)
                counts[table] = cursor.fetchone()['count']
            except Exception:
                counts[table] = 0
        
        # Count preserved items
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE id <= 0")
        preserved_admins = cursor.fetchone()['count']
        
        fuzzy_vars = 0
        try:
            cursor.execute("SELECT COUNT(*) as count FROM fuzzy_variables")
            fuzzy_vars = cursor.fetchone()['count']
        except Exception:
            pass
        
        configs = 0
        try:
            cursor.execute("SELECT COUNT(*) as count FROM configs")
            configs = cursor.fetchone()['count']
        except Exception:
            pass
        
        return jsonify({
            "success": True,
            "will_delete": counts,
            "will_preserve": {
                "admin_users": preserved_admins,
                "fuzzy_variables": fuzzy_vars,
                "configs": configs
            }
        }), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cursor.close()
        db.close()


@system_bp.route('/info', methods=['GET'])
@jwt_required()
@bitress_required
def system_info():
    """Get system information - bitress only"""
    db = get_connection()
    cursor = db.cursor()
    
    try:
        # Get table counts
        tables_info = {}
        cursor.execute("SHOW TABLES")
        tables = [row[list(row.keys())[0]] for row in cursor.fetchall()]
        
        for table in tables:
            cursor.execute("SELECT COUNT(*) as count FROM `%s`" % table)
            tables_info[table] = cursor.fetchone()['count']
        
        return jsonify({
            "success": True,
            "tables": tables_info,
            "total_tables": len(tables)
        }), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cursor.close()
        db.close()
