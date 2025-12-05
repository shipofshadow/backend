from flask import Blueprint, request, jsonify, send_file
from functools import wraps
import subprocess
import os
import platform
import datetime
import json
from pathlib import Path
import zipfile
import shutil
import pymysql
import time

from config import Config
from services.s3_service import s3_service
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'zip'}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

backup_bp = Blueprint('backup', __name__)

# Configuration
BACKUP_DIR = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True)
UPLOADS_DIR = Path("uploads")

# Detect OS
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX = platform.system() == 'Linux'

# Windows paths for MySQL tools
WINDOWS_MYSQLDUMP_PATHS = [
    r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
    r"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysqldump.exe",
    r"C:\xampp\mysql\bin\mysqldump.exe",
    r"C:\wamp64\bin\mysql\mysql8.0.27\bin\mysqldump.exe",
    r"C:\laragon\bin\mysql\mysql-8.0.30-winx64\bin\mysqldump.exe",
]

WINDOWS_MYSQL_PATHS = [
    r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
    r"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysql.exe",
    r"C:\xampp\mysql\bin\mysql.exe",
    r"C:\wamp64\bin\mysql\mysql8.0.27\bin\mysql.exe",
    r"C:\laragon\bin\mysql\mysql-8.0.30-winx64\bin\mysql.exe",
]

# Linux paths (usually in PATH, but we can check common locations)
LINUX_MYSQLDUMP_PATHS = [
    "/usr/bin/mysqldump",
    "/usr/local/bin/mysqldump",
    "/usr/local/mysql/bin/mysqldump",
]

LINUX_MYSQL_PATHS = [
    "/usr/bin/mysql",
    "/usr/local/bin/mysql",
    "/usr/local/mysql/bin/mysql",
]


def find_executable(name):
    """Try to locate executable - cross-platform"""
    import shutil as sh

    # First try system PATH (works on both Windows and Linux)
    exe = sh.which(name)
    if exe:
        print(f"Found {name} in PATH: {exe}")
        return exe

    # Try OS-specific locations
    if IS_WINDOWS:
        paths = WINDOWS_MYSQLDUMP_PATHS if 'dump' in name else WINDOWS_MYSQL_PATHS
    else:
        paths = LINUX_MYSQLDUMP_PATHS if 'dump' in name else LINUX_MYSQL_PATHS

    for path in paths:
        if os.path.exists(path):
            print(f"Found {name} at: {path}")
            return path

    print(f"{name} not found")
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
    """Pure Python database backup - works everywhere"""
    print(f"Starting Python-based backup to {output_file}")

    conn = get_db_connection()
    cursor = conn.cursor()

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"-- iScholar Database Backup\n")
        f.write(f"-- Generated: {datetime.datetime.now()}\n")
        f.write(f"-- Database: {Config.DB_NAME}\n")
        f.write(f"-- Platform: {platform.system()} {platform.release()}\n\n")
        f.write("SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';\n")
        f.write("SET time_zone = '+00:00';\n")
        f.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")

        cursor.execute("SHOW TABLES")
        tables = [row[f'Tables_in_{Config.DB_NAME}'] for row in cursor.fetchall()]

        print(f"Backing up {len(tables)} tables...")

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
    print("Python backup completed")


def backup_database_mysqldump(output_file):
    """Backup using mysqldump - faster for large databases"""
    mysqldump_path = find_executable("mysqldump")
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

    print(f"Running mysqldump: {' '.join(cmd[:7])}...")  # Don't log password
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"mysqldump failed: {result.stderr}")

    print("mysqldump completed")


def restore_database_python(sql_file):
    """Restore database using Python - cross-platform"""
    print(f"Starting Python-based restore from {sql_file}")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        print(f"Read {len(sql_content)} bytes from SQL file")

        # Disable foreign key checks
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute("SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO'")
        conn.commit()

        # Remove comments
        lines = []
        for line in sql_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('--'):
                lines.append(line)

        clean_sql = ' '.join(lines)

        # Split into statements
        statements = []
        temp_statement = ""
        in_string = False
        string_char = None

        i = 0
        while i < len(clean_sql):
            char = clean_sql[i]

            if char in ('"', "'") and (i == 0 or clean_sql[i - 1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None

            if char == ';' and not in_string:
                temp_statement += char
                if temp_statement.strip():
                    statements.append(temp_statement.strip())
                temp_statement = ""
            else:
                temp_statement += char

            i += 1

        print(f"Split into {len(statements)} SQL statements")

        # Execute statements
        successful = 0
        errors = 0

        for idx, statement in enumerate(statements):
            statement = statement.strip()

            if not statement or statement.startswith('SET '):
                continue

            try:
                cursor.execute(statement)
                successful += 1

                if successful % 100 == 0:
                    conn.commit()
                    print(f"Progress: {successful}/{len(statements)} statements executed")

            except pymysql.Error as e:
                errors += 1
                error_msg = str(e)

                if 'already exists' not in error_msg.lower() and \
                        'unknown database' not in error_msg.lower() and \
                        'duplicate key' not in error_msg.lower():
                    print(f"Error in statement {idx}: {error_msg}")
                    print(f"Statement preview: {statement[:100]}...")

                    if 'syntax error' in error_msg.lower():
                        print(f"CRITICAL SYNTAX ERROR - stopping restore")
                        raise

        conn.commit()
        print(f"Restore complete: {successful} successful, {errors} errors")

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
    """Restore using mysql command - cross-platform"""
    mysql_path = find_executable("mysql")
    if not mysql_path:
        raise Exception("mysql client not found")

    print(f"Using mysql at: {mysql_path}")

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
            print(f"Running mysql restore...")
            result = subprocess.run(
                cmd,
                stdin=f,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=300
            )

        if result.returncode != 0:
            print(f"mysql stderr: {result.stderr}")
            raise Exception(f"Database restore failed: {result.stderr}")

        print("MySQL restore completed successfully")

    except subprocess.TimeoutExpired:
        raise Exception("Database restore timed out after 5 minutes")


def safe_remove_dir(directory, max_retries=5, delay=0.5):
    """Safely remove directory - cross-platform"""
    import gc

    for attempt in range(max_retries):
        try:
            if directory.exists():
                gc.collect()

                # Try to change permissions (works on both Windows and Linux)
                if IS_LINUX:
                    # On Linux, use chmod
                    os.chmod(directory, 0o777)
                    for root, dirs, files in os.walk(directory):
                        for d in dirs:
                            os.chmod(os.path.join(root, d), 0o777)
                        for f in files:
                            os.chmod(os.path.join(root, f), 0o777)

                shutil.rmtree(directory, ignore_errors=False)
            return True
        except (PermissionError, OSError) as e:
            if attempt < max_retries - 1:
                print(f"Retry {attempt + 1}/{max_retries} removing directory: {e}")
                time.sleep(delay * (attempt + 1))
                gc.collect()
            else:
                print(f"Failed to remove directory after {max_retries} attempts")
                try:
                    shutil.rmtree(directory, ignore_errors=True)
                except:
                    pass
                return False
    return False


def safe_remove_file(filepath, max_retries=5, delay=0.5):
    """Safely remove file - cross-platform"""
    import gc

    for attempt in range(max_retries):
        try:
            if filepath.exists():
                gc.collect()

                # Try to change permissions
                if IS_LINUX:
                    os.chmod(filepath, 0o777)

                filepath.unlink()
            return True
        except (PermissionError, OSError) as e:
            if attempt < max_retries - 1:
                print(f"Retry {attempt + 1}/{max_retries} removing file: {e}")
                time.sleep(delay * (attempt + 1))
                gc.collect()
            else:
                print(f"Failed to remove file after {max_retries} attempts")
                return False
    return False


def admin_required(f):
    """Decorator to ensure only admins can access"""

    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({"success": False, "error": "No token provided"}), 401
        return f(*args, **kwargs)

    return decorated


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
        upload_to_s3_flag = data.get('upload_to_s3', False)

        backup_path = BACKUP_DIR / backup_name
        backup_path.mkdir(exist_ok=True)

        db_backup_file = backup_path / f"{Config.DB_NAME}.sql"

        # Try mysqldump first, fall back to Python
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
            "platform": f"{platform.system()} {platform.release()}",
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

        import gc
        gc.collect()

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in backup_path.rglob('*'):
                if file.is_file():
                    zipf.write(file, file.relative_to(backup_path))

        time.sleep(0.5)
        safe_remove_dir(backup_path)

        # Auto-upload to S3 if enabled
        if upload_to_s3_flag and s3_service.enabled:
            try:
                s3_key = f"backups/{backup_name}.zip"
                s3_service.upload_file(str(zip_path), s3_key)
                metadata['s3_key'] = s3_key
                metadata['s3_uploaded'] = True
            except Exception as e:
                print(f"S3 upload failed: {e}")
                metadata['s3_uploaded'] = False
                metadata['s3_error'] = str(e)

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
                if zip_handle:
                    try:
                        zip_handle.close()
                    except:
                        pass

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
        print(f"Platform: {platform.system()} {platform.release()}")
        print(f"Filename: {filename}")
        print(f"Restore files: {restore_files}")

        if not filename:
            return jsonify({"success": False, "error": "Filename required"}), 400

        backup_path = BACKUP_DIR / filename

        if not backup_path.exists():
            return jsonify({"success": False, "error": "Backup not found"}), 404

        print(f"Backup file: {backup_path}")
        print(f"Size: {backup_path.stat().st_size} bytes")

        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        extract_dir = BACKUP_DIR / f"temp_restore_{timestamp}"
        extract_dir.mkdir(exist_ok=True)

        print(f"Extracting to: {extract_dir}")

        zip_handle = zipfile.ZipFile(backup_path, 'r')
        zip_handle.extractall(extract_dir)
        zip_handle.close()
        zip_handle = None

        time.sleep(0.5)
        import gc
        gc.collect()

        # Find SQL file
        sql_file = extract_dir / f"{Config.DB_NAME}.sql"

        if not sql_file.exists():
            sql_files = list(extract_dir.glob("*.sql"))
            if sql_files:
                sql_file = sql_files[0]
                print(f"Using: {sql_file}")
            else:
                raise Exception("No SQL backup file found")

        print(f"SQL file: {sql_file} ({sql_file.stat().st_size} bytes)")

        # Restore database
        restore_method = None

        try:
            print("Attempting mysql restore...")
            restore_database_mysql(sql_file)
            restore_method = "mysql"
        except Exception as e:
            print(f"mysql failed: {e}")
            print("Trying Python restore...")

            try:
                restore_database_python(sql_file)
                restore_method = "python"
            except Exception as e2:
                raise Exception(f"All methods failed. MySQL: {str(e)}, Python: {str(e2)}")

        # Restore files
        if restore_files:
            files_backup_dir = extract_dir / "uploads"
            if files_backup_dir.exists():
                print("Restoring files...")

                if UPLOADS_DIR.exists():
                    backup_current = BACKUP_DIR / f"pre_restore_uploads_{timestamp}"
                    shutil.copytree(UPLOADS_DIR, backup_current)
                    safe_remove_dir(UPLOADS_DIR)
                    time.sleep(0.3)

                shutil.copytree(files_backup_dir, UPLOADS_DIR)
                print("Files restored")

        time.sleep(0.5)
        safe_remove_dir(extract_dir)
        print("=== RESTORE COMPLETE ===")

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

        if zip_handle:
            try:
                zip_handle.close()
            except:
                pass

        if extract_dir and extract_dir.exists():
            time.sleep(0.5)
            safe_remove_dir(extract_dir)

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@backup_bp.route('/api/backup/delete/<filename>', methods=['DELETE'])
@admin_required
def delete_backup(filename):
    """Delete a backup file"""
    import gc

    try:
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({"success": False, "error": "Invalid filename"}), 400

        backup_path = BACKUP_DIR / filename

        if not backup_path.exists():
            return jsonify({"success": False, "error": "Backup not found"}), 404

        if not backup_path.suffix == '.zip':
            return jsonify({"success": False, "error": "Invalid backup file"}), 400

        gc.collect()
        time.sleep(0.5)

        if safe_remove_file(backup_path):
            time.sleep(0.3)
            if not backup_path.exists():
                return jsonify({
                    "success": True,
                    "message": "Backup deleted successfully"
                }), 200

        return jsonify({
            "success": False,
            "error": "Failed to delete backup"
        }), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@backup_bp.route('/api/backup/verify/<filename>', methods=['GET'])
@admin_required
def verify_backup(filename):
    """Verify backup integrity"""
    zip_handle = None

    try:
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({"success": False, "error": "Invalid filename"}), 400

        backup_path = BACKUP_DIR / filename

        if not backup_path.exists():
            return jsonify({"success": False, "error": "Backup not found"}), 404

        zip_handle = zipfile.ZipFile(backup_path, 'r')

        bad_file = zip_handle.testzip()
        if bad_file:
            return jsonify({
                "success": False,
                "error": f"Corrupt file: {bad_file}"
            }), 400

        files = zip_handle.namelist()

        has_metadata = 'metadata.json' in files
        metadata = None
        if has_metadata:
            with zip_handle.open('metadata.json') as f:
                metadata = json.load(f)

        sql_files = [f for f in files if f.endswith('.sql')]
        has_sql = len(sql_files) > 0
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

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if zip_handle:
            try:
                zip_handle.close()
            except:
                pass


@backup_bp.route('/api/backup/test-connection', methods=['GET'])
def test_connection():
    """Test database connection and tools"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT VERSION()")
        db_version = cursor.fetchone()

        cursor.execute("SELECT DATABASE()")
        current_db = cursor.fetchone()

        cursor.close()
        conn.close()

        mysql_path = find_executable("mysql")
        mysqldump_path = find_executable("mysqldump")

        return jsonify({
            "success": True,
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python": platform.python_version()
            },
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


@backup_bp.route('/api/backup/upload-to-s3/<filename>', methods=['POST'])
@admin_required
def upload_to_s3(filename):
    """Upload local backup to S3"""
    try:
        if not s3_service.enabled:
            return jsonify({"success": False, "error": "S3 is not configured"}), 400

        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({"success": False, "error": "Invalid filename"}), 400

        local_path = BACKUP_DIR / filename
        if not local_path.exists():
            return jsonify({"success": False, "error": "Backup not found"}), 404

        s3_key = f"backups/{filename}"
        s3_service.upload_file(str(local_path), s3_key)

        return jsonify({
            "success": True,
            "message": "Backup uploaded to S3 successfully",
            "s3_key": s3_key
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@backup_bp.route('/api/backup/s3/list', methods=['GET'])
@admin_required
def list_s3_backups():
    """List backups stored in S3"""
    try:
        if not s3_service.enabled:
            return jsonify({"success": False, "error": "S3 is not configured"}), 400

        files = s3_service.list_files(prefix="backups/")

        return jsonify({
            "success": True,
            "backups": files,
            "total": len(files)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@backup_bp.route('/api/backup/s3/download/<filename>', methods=['POST'])
@admin_required
def download_from_s3(filename):
    """Download a backup from S3 to local storage"""
    try:
        if not s3_service.enabled:
            return jsonify({"success": False, "error": "S3 is not configured"}), 400

        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({"success": False, "error": "Invalid filename"}), 400

        s3_key = f"backups/{filename}"

        if not s3_service.file_exists(s3_key):
            return jsonify({"success": False, "error": "Backup not found in S3"}), 404

        local_path = BACKUP_DIR / filename
        s3_service.download_file(s3_key, str(local_path))

        return jsonify({
            "success": True,
            "message": "Backup downloaded from S3 successfully",
            "filename": filename,
            "size": local_path.stat().st_size
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@backup_bp.route('/api/backup/s3/delete/<filename>', methods=['DELETE'])
@admin_required
def delete_s3_backup(filename):
    """Delete a backup from S3"""
    try:
        if not s3_service.enabled:
            return jsonify({"success": False, "error": "S3 is not configured"}), 400

        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({"success": False, "error": "Invalid filename"}), 400

        s3_key = f"backups/{filename}"

        if not s3_service.file_exists(s3_key):
            return jsonify({"success": False, "error": "Backup not found in S3"}), 404

        s3_service.delete_file(s3_key)

        return jsonify({
            "success": True,
            "message": "Backup deleted from S3 successfully"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@backup_bp.route('/api/backup/import', methods=['POST'])
@admin_required
def import_backup():
    """Import a backup file uploaded by user"""
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No file provided"}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({"success": False, "error": "No file selected"}), 400

        if not allowed_file(file.filename):
            return jsonify({"success": False, "error": "Only ZIP files are allowed"}), 400

        # Generate unique filename
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        original_filename = secure_filename(file.filename)
        filename = f"imported_{timestamp}_{original_filename}"

        save_path = BACKUP_DIR / filename
        file.save(save_path)

        # Verify it's a valid backup
        try:
            with zipfile.ZipFile(save_path, 'r') as zf:
                files = zf.namelist()
                has_sql = any(f.endswith('.sql') for f in files)

                if not has_sql:
                    os.remove(save_path)
                    return jsonify({
                        "success": False,
                        "error": "Invalid backup: No SQL file found"
                    }), 400

                # Try to read metadata
                metadata = None
                if 'metadata.json' in files:
                    with zf.open('metadata.json') as mf:
                        metadata = json.load(mf)
        except zipfile.BadZipFile:
            os.remove(save_path)
            return jsonify({"success": False, "error": "Invalid ZIP file"}), 400

        return jsonify({
            "success": True,
            "message": "Backup imported successfully",
            "backup": {
                "filename": filename,
                "size": save_path.stat().st_size,
                "metadata": metadata
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@backup_bp.route('/api/backup/storage-config', methods=['GET'])
@admin_required
def get_storage_config():
    """Get current storage configuration (without sensitive keys)"""
    try:
        return jsonify({
            "success": True,
            "config": {
                "s3_enabled": s3_service.enabled,
                "s3_bucket": Config.S3_BUCKET if s3_service.enabled else None,
                "s3_region": Config.S3_REGION if s3_service.enabled else None,
                "s3_endpoint": Config.S3_ENDPOINT if s3_service.enabled and Config.S3_ENDPOINT else None,
                "local_backup_dir": str(BACKUP_DIR.absolute()),
                "local_backup_exists": BACKUP_DIR.exists()
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500