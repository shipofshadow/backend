from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.decorator import bitress_required
from storage import get_connection
import logging
import re

system_bp = Blueprint('system', __name__, url_prefix='/api/system')

# Whitelist of allowed table names for system reset
RESET_TABLES = frozenset([
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
])

# Tables for preview
PREVIEW_TABLES = frozenset([
    'applications', 'students', 'users', 'notifications',
    'announcements', 'scholarships', 'academic_years', 'semesters'
])

# Valid table name pattern
TABLE_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def is_valid_table_name(table_name, whitelist):
    """Validate table name against whitelist and pattern"""
    return table_name in whitelist and TABLE_NAME_PATTERN.match(table_name)


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
        
        deleted_counts = {}
        
        for table in RESET_TABLES:
            # Validate table name before using (defense in depth)
            if not is_valid_table_name(table, RESET_TABLES):
                continue
            try:
                # Using backticks for identifier quoting - table names are from whitelist
                cursor.execute("SELECT COUNT(*) as count FROM `" + table + "`")
                count = cursor.fetchone()['count']
                cursor.execute("TRUNCATE TABLE `" + table + "`")
                deleted_counts[table] = count
            except Exception:
                # Table may not exist, skip it
                deleted_counts[table] = 0
        
        # Delete users except admins with negative IDs (includes bitress at -999)
        # Count only users that will actually be deleted (positive IDs)
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE id > 0")
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
        
        for table in PREVIEW_TABLES:
            # Validate table name before using (defense in depth)
            if not is_valid_table_name(table, PREVIEW_TABLES):
                continue
            try:
                if table == 'users':
                    cursor.execute("SELECT COUNT(*) as count FROM users WHERE id > 0")
                else:
                    # Using backticks for identifier quoting - table names are from whitelist
                    cursor.execute("SELECT COUNT(*) as count FROM `" + table + "`")
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
            # Validate table name pattern to prevent SQL injection
            if not TABLE_NAME_PATTERN.match(table):
                continue
            # Using backticks for identifier quoting - table names from database
            cursor.execute("SELECT COUNT(*) as count FROM `" + table + "`")
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
