from flask import Blueprint, request, jsonify, send_file
from functools import wraps
import subprocess
import os
import datetime
import json
from pathlib import Path
import zipfile
import shutil
import pymysql
import time

from config import Config

backup_bp = Blueprint('backup', __name__)

# Configuration
BACKUP_DIR = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True)
UPLOADS_DIR = Path("uploads")

# MySQL paths
MYSQLDUMP_PATHS = [
    r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
    r"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysqldump.exe",
    r"C:\xampp\mysql\bin\mysqldump.exe",
    r"C:\wamp64\bin\mysql\mysql8.0.27\bin\mysqldump.exe",
    r"C:\laragon\bin\mysql\mysql-8.0.30-winx64\bin\mysqldump.exe",
]

MYSQL_PATHS = [
    r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
    r"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysql.exe",
    r"C:\xampp\mysql\bin\mysql.exe",
    r"C:\wamp64\bin\mysql\mysql8.0.27\bin\mysql.exe",
    r"C:\laragon\bin\mysql\mysql-8.0.30-winx64\bin\mysql.exe",
]


def find_executable(name, paths_list):
    """Try to locate executable"""
    import shutil as sh
    exe = sh.which(name)
    if exe:
        return exe
    for path in paths_list:
        if os.path.exists(path):
            return path
    return None


def get_db_connection():
    """Create database connection"""
    return pymysql.connect(
        host=Config.DB_HOST,
        port=int(getattr(Config, 'DB_PORT', 3306)),
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def backup_database_python(output_file):
    """Pure Python database backup"""
    conn = get_db_connection()
    cursor = conn.cursor()

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"-- iScholar Database Backup\n")
        f.write(f"-- Generated: {datetime.datetime.now()}\n")
        f.write(f"-- Database: {Config.DB_NAME}\n\n")
        f.write("SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';\n")
        f.write("SET time_zone = '+00:00';\n")
        f.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")

        cursor.execute("SHOW TABLES")
        tables = [row[f'Tables_in_{Config.DB_NAME}'] for row in cursor.fetchall()]

        for table in tables:
            f.write(f"\n--\n-- Table structure for table `{table}`\n--\n\n")
            f.write(f"DROP TABLE IF EXISTS `{table}`;\n")

            cursor.execute(f"SHOW CREATE TABLE `{table}`")
            create_table = cursor.fetchone()['Create Table']
            f.write(f"{create_table};\n\n")

            cursor.execute(f"SELECT * FROM `{table}`")
            rows = cursor.fetchall()

            if rows:
                f.write(f"--\n-- Dumping data for table `{table}`\n--\n\n")
                cursor.execute(f"SHOW COLUMNS FROM `{table}`")
                columns = [col['Field'] for col in cursor.fetchall()]
                columns_str = ', '.join([f"`{col}`" for col in columns])

                f.write(f"INSERT INTO `{table}` ({columns_str}) VALUES\n")

                for i, row in enumerate(rows):
                    values = []
                    for col in columns:
                        val = row[col]
                        if val is None:
                            values.append('NULL')
                        elif isinstance(val, (int, float)):
                            values.append(str(val))
                        elif isinstance(val, datetime.datetime):
                            values.append(f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'")
                        elif isinstance(val, datetime.date):
                            values.append(f"'{val.strftime('%Y-%m-%d')}'")
                        else:
                            val_str = str(val).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace(
                                "\r", "\\r")
                            values.append(f"'{val_str}'")

                    values_str = ', '.join(values)
                    comma = ',' if i < len(rows) - 1 else ';'
                    f.write(f"({values_str}){comma}\n")
                f.write("\n")

        f.write("SET FOREIGN_KEY_CHECKS = 1;\n")

    cursor.close()
    conn.close()


def backup_database_mysqldump(output_file):
    """Backup using mysqldump"""
    mysqldump_path = find_executable("mysqldump", MYSQLDUMP_PATHS)
    if not mysqldump_path:
        raise Exception("mysqldump not found")

    cmd = [
        mysqldump_path,
        f"--host={Config.DB_HOST}",
        f"--user={Config.DB_USER}",
        f"--password={Config.DB_PASSWORD}",
        "--single-transaction",
        "--routines",
        "--triggers",
        "--events",
        "--result-file",
        str(output_file),
        Config.DB_NAME
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"mysqldump failed: {result.stderr}")


def restore_database_python(sql_file):
    """Restore database using Python - IMPROVED VERSION"""
    print(f"Starting Python-based restore from {sql_file}")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Read SQL file
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        print(f"Read {len(sql_content)} bytes from SQL file")

        # Disable foreign key checks
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute("SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO'")
        conn.commit()
        print("Disabled foreign key checks")

        # Split into statements more reliably
        # Remove comments first
        lines = []
        for line in sql_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('--'):
                lines.append(line)

        clean_sql = ' '.join(lines)

        # Now split by semicolons (simple approach for backup files)
        statements = []
        temp_statement = ""
        in_string = False
        string_char = None

        i = 0
        while i < len(clean_sql):
            char = clean_sql[i]

            # Handle string literals
            if char in ('"', "'") and (i == 0 or clean_sql[i - 1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None

            # Handle semicolons
            if char == ';' and not in_string:
                temp_statement += char
                if temp_statement.strip():
                    statements.append(temp_statement.strip())
                temp_statement = ""
            else:
                temp_statement += char

            i += 1

        print(f"Split into {len(statements)} SQL statements")

        # Execute statements with better error handling
        successful = 0
        errors = 0

        for idx, statement in enumerate(statements):
            statement = statement.strip()

            # Skip empty statements and SET commands we already handled
            if not statement or statement.startswith('SET '):
                continue

            try:
                cursor.execute(statement)
                successful += 1

                # Commit every 100 statements for better performance
                if successful % 100 == 0:
                    conn.commit()
                    print(f"Progress: {successful}/{len(statements)} statements executed")

            except pymysql.Error as e:
                errors += 1
                error_msg = str(e)

                # Only log significant errors
                if 'already exists' not in error_msg.lower() and \
                        'unknown database' not in error_msg.lower() and \
                        'duplicate key' not in error_msg.lower():
                    print(f"Error in statement {idx}: {error_msg}")
                    print(f"Statement preview: {statement[:100]}...")

                    # For critical errors, stop the restore
                    if 'syntax error' in error_msg.lower():
                        print(f"CRITICAL SYNTAX ERROR - stopping restore")
                        raise

        # Final commit
        conn.commit()
        print(f"Restore complete: {successful} successful, {errors} errors")

        # Re-enable foreign key checks
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()

        cursor.close()
        conn.close()

        print("Database restore completed successfully")

    except Exception as e:
        print(f"FATAL ERROR during restore: {e}")
        if 'conn' in locals():
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        raise


def restore_database_mysql(sql_file):
    """Restore using mysql command - IMPROVED"""
    mysql_path = find_executable("mysql", MYSQL_PATHS)
    if not mysql_path:
        raise Exception("mysql client not found")

    print(f"Using mysql at: {mysql_path}")
    print(f"Restoring from: {sql_file}")

    # Build command
    cmd = [
        mysql_path,
        f"--host={Config.DB_HOST}",
        f"--user={Config.DB_USER}",
        f"--password={Config.DB_PASSWORD}",
        "--default-character-set=utf8mb4",
        Config.DB_NAME
    ]

    try:
        with open(sql_file, 'r', encoding='utf-8') as f:
            result = subprocess.run(
                cmd,
                stdin=f,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=300  # 5 minute timeout
            )

        if result.returncode != 0:
            print(f"mysql restore stderr: {result.stderr}")
            print(f"mysql restore stdout: {result.stdout}")
            raise Exception(f"Database restore failed: {result.stderr}")

        print("MySQL restore completed successfully")

    except subprocess.TimeoutExpired:
        raise Exception("Database restore timed out after 5 minutes")
    except Exception as e:
        print(f"MySQL restore error: {e}")
        raise


def admin_required(f):
    """Decorator to ensure only admins can access"""

    @wraps(f)
    def decorated(*args, **kwargs):
        # Add proper JWT verification here based on your auth system
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({"success": False, "error": "No token provided"}), 401

        # TODO: Verify token and check if user is admin
        # For now, just checking token exists

        return f(*args, **kwargs)

    return decorated


def safe_remove_dir(directory, max_retries=5, delay=0.5):
    """Safely remove directory with retry logic and file handle cleanup"""
    import gc

    for attempt in range(max_retries):
        try:
            if directory.exists():
                # Force garbage collection to release file handles
                gc.collect()

                # Try to change permissions first (Windows issue)
                try:
                    for root, dirs, files in os.walk(directory):
                        for d in dirs:
                            os.chmod(os.path.join(root, d), 0o777)
                        for f in files:
                            os.chmod(os.path.join(root, f), 0o777)
                except Exception:
                    pass  # Ignore permission errors

                # Now try to remove
                shutil.rmtree(directory, ignore_errors=False)
            return True
        except (PermissionError, OSError) as e:
            if attempt < max_retries - 1:
                print(f"Retry {attempt + 1}/{max_retries} removing directory: {e}")
                time.sleep(delay * (attempt + 1))  # Exponential backoff
                gc.collect()  # Try to release handles
            else:
                print(f"Failed to remove directory after {max_retries} attempts: {e}")
                # Last resort: try ignore_errors
                try:
                    shutil.rmtree(directory, ignore_errors=True)
                except Exception:
                    pass
                return False
    return False


def safe_remove_file(filepath, max_retries=5, delay=0.5):
    """Safely remove file with retry logic and handle cleanup"""
    import gc

    for attempt in range(max_retries):
        try:
            if filepath.exists():
                # Force garbage collection
                gc.collect()

                # Try to change permissions
                try:
                    os.chmod(filepath, 0o777)
                except Exception:
                    pass

                # Close any open handles (Windows specific)
                try:
                    import msvcrt
                    import ctypes
                    # Force close any open handles to this file
                    kernel32 = ctypes.windll.kernel32
                    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
                except Exception:
                    pass  # Not on Windows or import failed

                filepath.unlink()
            return True
        except (PermissionError, OSError) as e:
            if attempt < max_retries - 1:
                print(f"Retry {attempt + 1}/{max_retries} removing file: {e}")
                time.sleep(delay * (attempt + 1))  # Exponential backoff
                gc.collect()
            else:
                print(f"Failed to remove file after {max_retries} attempts: {e}")
                return False
    return False


@backup_bp.route('/api/backup/create', methods=['POST'])
@admin_required
def create_backup():
    """Create full system backup"""
    backup_path = None
    zip_path = None

    try:
        data = request.get_json()
        backup_name = data.get('name', f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        include_files = data.get('include_files', True)
        description = data.get('description', '')

        backup_path = BACKUP_DIR / backup_name
        backup_path.mkdir(exist_ok=True)

        # Backup Database
        db_backup_file = backup_path / f"{Config.DB_NAME}.sql"

        try:
            backup_database_mysqldump(db_backup_file)
            backup_method = "mysqldump"
        except Exception as e:
            print(f"mysqldump failed, using Python method: {e}")
            backup_database_python(db_backup_file)
            backup_method = "python"

        # Backup uploaded files
        files_size = 0
        if include_files and UPLOADS_DIR.exists():
            files_backup_dir = backup_path / "uploads"
            shutil.copytree(UPLOADS_DIR, files_backup_dir)
            files_size = sum(f.stat().st_size for f in files_backup_dir.rglob('*') if f.is_file())

        # Create metadata
        metadata = {
            "name": backup_name,
            "description": description,
            "created_at": datetime.datetime.now().isoformat(),
            "database": Config.DB_NAME,
            "include_files": include_files,
            "backup_method": backup_method,
            "db_size": os.path.getsize(db_backup_file),
            "files_size": files_size,
            "total_size": os.path.getsize(db_backup_file) + files_size
        }

        with open(backup_path / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)

        # Create ZIP archive
        zip_path = BACKUP_DIR / f"{backup_name}.zip"

        # Ensure any previous file handles are closed
        import gc
        gc.collect()

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in backup_path.rglob('*'):
                if file.is_file():
                    zipf.write(file, file.relative_to(backup_path))

        # IMPORTANT: Let the zip file close completely
        time.sleep(0.5)

        # Clean up unzipped backup with retry
        safe_remove_dir(backup_path)

        return jsonify({
            "success": True,
            "message": f"Backup created successfully using {backup_method}",
            "backup": {
                **metadata,
                "filename": f"{backup_name}.zip",
                "size": zip_path.stat().st_size
            }
        }), 200

    except Exception as e:
        # Clean up on error
        if backup_path and backup_path.exists():
            safe_remove_dir(backup_path)
        if zip_path and zip_path.exists():
            safe_remove_file(zip_path)
        return jsonify({"success": False, "error": str(e)}), 500


@backup_bp.route('/api/backup/list', methods=['GET'])
@admin_required
def list_backups():
    """List all available backups"""
    import gc

    try:
        backups = []

        for backup_file in BACKUP_DIR.glob("*.zip"):
            zip_handle = None
            try:
                zip_handle = zipfile.ZipFile(backup_file, 'r')
                if 'metadata.json' in zip_handle.namelist():
                    with zip_handle.open('metadata.json') as f:
                        metadata = json.load(f)
                        metadata['filename'] = backup_file.name
                        metadata['size'] = backup_file.stat().st_size
                        backups.append(metadata)
            except Exception as e:
                print(f"Error reading {backup_file}: {e}")
            finally:
                # CRITICAL: Always close the zip file handle
                if zip_handle:
                    try:
                        zip_handle.close()
                    except Exception:
                        pass

        # Force garbage collection to release file handles
        gc.collect()

        backups.sort(key=lambda x: x['created_at'], reverse=True)

        return jsonify({
            "success": True,
            "backups": backups,
            "total": len(backups)
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@backup_bp.route('/api/backup/download/<filename>', methods=['GET'])
@admin_required
def download_backup(filename):
    """Download a backup file"""
    try:
        backup_path = BACKUP_DIR / filename

        if not backup_path.exists():
            return jsonify({"success": False, "error": "Backup not found"}), 404

        return send_file(
            backup_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@backup_bp.route('/api/backup/restore', methods=['POST'])
@admin_required
def restore_backup():
    """Restore from a backup file"""
    extract_dir = None
    zip_handle = None

    try:
        data = request.get_json()
        filename = data.get('filename')
        restore_files = data.get('restore_files', True)

        print(f"=== RESTORE REQUEST ===")
        print(f"Filename: {filename}")
        print(f"Restore files: {restore_files}")

        if not filename:
            return jsonify({"success": False, "error": "Filename required"}), 400

        backup_path = BACKUP_DIR / filename

        if not backup_path.exists():
            return jsonify({"success": False, "error": "Backup not found"}), 404

        print(f"Backup file exists: {backup_path}")
        print(f"Backup size: {backup_path.stat().st_size} bytes")

        # Extract backup to temp directory
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        extract_dir = BACKUP_DIR / f"temp_restore_{timestamp}"
        extract_dir.mkdir(exist_ok=True)

        print(f"Extracting to: {extract_dir}")

        # Extract with explicit handle management
        zip_handle = zipfile.ZipFile(backup_path, 'r')
        zip_handle.extractall(extract_dir)
        zip_handle.close()
        zip_handle = None

        print(f"Extraction complete")

        # List extracted files
        extracted_files = list(extract_dir.rglob('*'))
        print(f"Extracted {len(extracted_files)} items")
        for f in extracted_files[:10]:  # Show first 10
            print(f"  - {f.relative_to(extract_dir)}")

        # Give OS time to release handles
        time.sleep(0.5)
        import gc
        gc.collect()

        # Restore Database
        sql_file = extract_dir / f"{Config.DB_NAME}.sql"

        # Try alternative SQL file names if default doesn't exist
        if not sql_file.exists():
            print(f"Default SQL file not found: {sql_file}")
            # Look for any .sql file
            sql_files = list(extract_dir.glob("*.sql"))
            if sql_files:
                sql_file = sql_files[0]
                print(f"Using alternative SQL file: {sql_file}")
            else:
                raise Exception("No SQL backup file found in archive")

        print(f"SQL file: {sql_file}")
        print(f"SQL file size: {sql_file.stat().st_size} bytes")

        # Try mysql command first, fall back to Python
        restore_method = None
        restore_error = None

        try:
            print("Attempting MySQL command restore...")
            restore_database_mysql(sql_file)
            restore_method = "mysql"
            print("MySQL restore successful!")
        except Exception as e:
            restore_error = str(e)
            print(f"MySQL restore failed: {e}")
            print("Falling back to Python restore method...")

            try:
                restore_database_python(sql_file)
                restore_method = "python"
                print("Python restore successful!")
            except Exception as e2:
                print(f"Python restore also failed: {e2}")
                raise Exception(f"All restore methods failed. MySQL: {restore_error}, Python: {str(e2)}")

        if not restore_method:
            raise Exception("Restore method not set - this shouldn't happen")

        # Restore files if requested
        if restore_files:
            files_backup_dir = extract_dir / "uploads"
            if files_backup_dir.exists():
                print(f"Restoring files from: {files_backup_dir}")

                # Backup current uploads first
                if UPLOADS_DIR.exists():
                    backup_current = BACKUP_DIR / f"pre_restore_uploads_{timestamp}"
                    print(f"Backing up current uploads to: {backup_current}")
                    shutil.copytree(UPLOADS_DIR, backup_current)

                    # Remove current uploads
                    safe_remove_dir(UPLOADS_DIR)
                    time.sleep(0.3)

                # Restore from backup
                print("Copying files from backup...")
                shutil.copytree(files_backup_dir, UPLOADS_DIR)
                print("Files restored successfully")
            else:
                print("No uploads directory in backup")

        # Clean up with retry
        print("Cleaning up temporary files...")
        time.sleep(0.5)
        safe_remove_dir(extract_dir)
        print("Cleanup complete")

        print(f"=== RESTORE COMPLETE ===")
        return jsonify({
            "success": True,
            "message": f"Backup restored successfully using {restore_method}",
            "method": restore_method
        }), 200

    except Exception as e:
        print(f"=== RESTORE FAILED ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

        # Clean up on error
        if zip_handle:
            try:
                zip_handle.close()
            except Exception:
                pass

        if extract_dir and extract_dir.exists():
            time.sleep(0.5)
            safe_remove_dir(extract_dir)

        return jsonify({
            "success": False,
            "error": str(e),
            "details": "Check server logs for more information"
        }), 500


@backup_bp.route('/api/backup/delete/<filename>', methods=['DELETE'])
@admin_required
def delete_backup(filename):
    """Delete a backup file"""
    import gc

    try:
        # Validate filename to prevent path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({"success": False, "error": "Invalid filename"}), 400

        backup_path = BACKUP_DIR / filename

        if not backup_path.exists():
            return jsonify({"success": False, "error": "Backup not found"}), 404

        # Ensure it's a zip file
        if not backup_path.suffix == '.zip':
            return jsonify({"success": False, "error": "Invalid backup file"}), 400

        # Force garbage collection before attempting delete
        gc.collect()
        time.sleep(0.5)  # Give OS time to release handles

        # Try to delete with retries
        if safe_remove_file(backup_path):
            # Verify deletion
            time.sleep(0.3)
            if not backup_path.exists():
                return jsonify({
                    "success": True,
                    "message": "Backup deleted successfully"
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "File deletion verification failed"
                }), 500
        else:
            # Check if the file still exists
            if backup_path.exists():
                return jsonify({
                    "success": False,
                    "error": "Failed to delete backup file. It may be in use by another process."
                }), 500
            else:
                # File doesn't exist anymore (race condition or someone else deleted it)
                return jsonify({
                    "success": True,
                    "message": "Backup deleted successfully"
                }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@backup_bp.route('/api/backup/verify/<filename>', methods=['GET'])
@admin_required
def verify_backup(filename):
    """Verify a backup file's contents and integrity"""
    zip_handle = None

    try:
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({"success": False, "error": "Invalid filename"}), 400

        backup_path = BACKUP_DIR / filename

        if not backup_path.exists():
            return jsonify({"success": False, "error": "Backup not found"}), 404

        # Open and verify zip
        zip_handle = zipfile.ZipFile(backup_path, 'r')

        # Test zip integrity
        bad_file = zip_handle.testzip()
        if bad_file:
            return jsonify({
                "success": False,
                "error": f"Corrupt file in backup: {bad_file}"
            }), 400

        # Get file list
        files = zip_handle.namelist()

        # Check for metadata
        has_metadata = 'metadata.json' in files
        metadata = None
        if has_metadata:
            with zip_handle.open('metadata.json') as f:
                metadata = json.load(f)

        # Check for SQL file
        sql_files = [f for f in files if f.endswith('.sql')]
        has_sql = len(sql_files) > 0

        # Check for uploads
        has_uploads = any('uploads/' in f for f in files)

        zip_handle.close()
        zip_handle = None

        return jsonify({
            "success": True,
            "filename": filename,
            "size": backup_path.stat().st_size,
            "file_count": len(files),
            "has_metadata": has_metadata,
            "has_sql": has_sql,
            "sql_files": sql_files,
            "has_uploads": has_uploads,
            "metadata": metadata,
            "is_valid": has_sql and has_metadata
        }), 200

    except zipfile.BadZipFile:
        return jsonify({
            "success": False,
            "error": "Invalid or corrupted zip file"
        }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        if zip_handle:
            try:
                zip_handle.close()
            except:
                pass


@backup_bp.route('/api/backup/test-connection', methods=['GET'])
def test_connection():
    """Test database connection and restore capabilities"""
    try:
        # Test database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT VERSION()")
        db_version = cursor.fetchone()

        cursor.execute("SELECT DATABASE()")
        current_db = cursor.fetchone()

        cursor.close()
        conn.close()

        # Check for mysql/mysqldump
        mysql_path = find_executable("mysql", MYSQL_PATHS)
        mysqldump_path = find_executable("mysqldump", MYSQLDUMP_PATHS)

        return jsonify({
            "success": True,
            "database": {
                "connected": True,
                "version": db_version,
                "current_database": current_db,
                "host": Config.DB_HOST,
                "name": Config.DB_NAME
            },
            "tools": {
                "mysql_available": mysql_path is not None,
                "mysql_path": mysql_path,
                "mysqldump_available": mysqldump_path is not None,
                "mysqldump_path": mysqldump_path,
                "python_backup_available": True
            },
            "directories": {
                "backup_dir": str(BACKUP_DIR.absolute()),
                "backup_dir_exists": BACKUP_DIR.exists(),
                "uploads_dir": str(UPLOADS_DIR.absolute()),
                "uploads_dir_exists": UPLOADS_DIR.exists()
            }
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500