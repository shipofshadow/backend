import json
import os
import re
import uuid
import subprocess
import requests
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Union
from io import BytesIO

from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from PIL import Image
from config import ALLOWED_EXTENSIONS, UPLOAD_FOLDER, SCHOLARSHIP_CONFIG, Config
from storage import s3_client
from .avatar_generator import create_initials_avatar


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_s3_key(filename):
    """Ensure consistency in naming keys (e.g., adds uploads/ prefix if missing)"""
    if filename.startswith("uploads/"):
        return filename
    return f"uploads/{filename}"


def generate_presigned_url(filename, expiration=3600):
    """Generates a temporary public URL for a private S3 file."""
    try:
        key = get_s3_key(filename)
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': Config.S3_BUCKET, 'Key': key},
            ExpiresIn=expiration
        )
        return url
    except Exception as e:
        print(f"Error generating presigned URL: {e}")
        return None


def upload_to_s3(local_path, filename, content_type=None):
    """Uploads to Private S3 Bucket"""
    try:
        bucket = Config.S3_BUCKET
        key = get_s3_key(filename)

        # Determine content type
        if not content_type:
            import mimetypes
            content_type, _ = mimetypes.guess_type(local_path)

        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type

        # REMOVED: ExtraArgs={'ACL': 'public-read'} (Because bucket is private)

        s3_client.upload_file(local_path, bucket, key, ExtraArgs=extra_args)

        # Return the KEY (path), not the URL. The URL is generated on demand.
        return key

    except Exception as e:
        print(f"S3 Upload Error: {e}")
        return None


def save_file(file, user_id, file_type):
    _, ext = os.path.splitext(secure_filename(file.filename))
    ext = ext.lower()
    unique_id = uuid.uuid4().hex
    filename = f"{user_id}_{file_type}_{unique_id}{ext}"
    path = os.path.join(UPLOAD_FOLDER, filename)

    # 1. Save locally first (needed for processing)
    file.save(path)

    # 2. Optimize Images
    if ext in [".jpg", ".jpeg", ".png"]:
        try:
            img = Image.open(path)
            if ext in [".jpg", ".jpeg"]:
                img.save(path, "JPEG", optimize=True, quality=70)
            elif ext == ".png":
                img.save(path, "PNG", optimize=True)
        except Exception:
            pass

    # 3. Check Storage Provider
    if getattr(Config, 'STORAGE_PROVIDER', 's3') == 's3':
        # Upload to Private S3
        stored_key = upload_to_s3(path, filename)

        # Clean up local file
        try:
            os.remove(path)
        except OSError:
            pass

        return stored_key  # Returns "uploads/user_type_uuid.jpg"

    return filename  # Returns local filename

def generate_avatar(name):
    """Generate an initials-based avatar and save based on storage provider setting."""
    from services.settings_service import get_storage_provider

    img = create_initials_avatar(name)
    unique_id = uuid.uuid4().hex
    filename = f"avatar_{unique_id}.png"
    path = os.path.join(UPLOAD_FOLDER, filename)
    img.save(path)

    storage_provider = get_storage_provider()

    if storage_provider == 's3':
        # Upload to S3
        stored_key = upload_to_s3(path, filename)
        # Clean up local file
        try:
            os.remove(path)
        except OSError:
            pass
        return stored_key  # Returns "uploads/avatar_xxx.png"

    return filename  # Returns local filename


def save_avatar(file_or_url: Union[FileStorage, str], user_id: str) -> str:
    """
    Smart avatar save function that:
    - Checks the storageProvider setting from the database
    - Handles both file uploads and URL downloads (for Google avatars)
    - Saves to appropriate storage (S3 or local)
    - Returns the stored path/key
    """
    from services.settings_service import get_storage_provider

    unique_id = uuid.uuid4().hex
    storage_provider = get_storage_provider()

    # Determine if we have a file or URL
    if isinstance(file_or_url, str):
        # It's a URL - download the image
        try:
            response = requests.get(file_or_url, timeout=10, verify=True)
            response.raise_for_status()

            # Determine file extension from content type or URL
            content_type = response.headers.get('Content-Type', '')
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = '.jpg'
            elif 'png' in content_type:
                ext = '.png'
            elif 'gif' in content_type:
                ext = '.gif'
            else:
                # Try to get from URL
                ext = '.jpg'  # Default to jpg

            filename = f"avatar_{user_id}_{unique_id}{ext}"
            path = os.path.join(UPLOAD_FOLDER, filename)

            # Save locally first
            with open(path, 'wb') as f:
                f.write(response.content)

        except requests.RequestException as e:
            print(f"Error downloading avatar from URL '{file_or_url}': {e} (status: {getattr(e.response, 'status_code', 'N/A') if hasattr(e, 'response') else 'N/A'})")
            return None
        except Exception as e:
            print(f"Unexpected error downloading avatar from URL '{file_or_url}': {e}")
            return None
    else:
        # It's a file upload
        _, ext = os.path.splitext(secure_filename(file_or_url.filename))
        ext = ext.lower()
        if not ext:
            ext = '.png'

        filename = f"avatar_{user_id}_{unique_id}{ext}"
        path = os.path.join(UPLOAD_FOLDER, filename)

        # Save locally first
        file_or_url.save(path)

    # Optimize image
    try:
        img = Image.open(path)
        # Convert to RGB if necessary (for RGBA images)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
            ext = '.jpg'
            new_filename = f"avatar_{user_id}_{unique_id}{ext}"
            new_path = os.path.join(UPLOAD_FOLDER, new_filename)
            img.save(new_path, "JPEG", optimize=True, quality=85)
            # Remove old file if different
            if path != new_path:
                try:
                    os.remove(path)
                except OSError:
                    pass
            path = new_path
            filename = new_filename
        elif ext in ['.jpg', '.jpeg']:
            img.save(path, "JPEG", optimize=True, quality=85)
        elif ext == '.png':
            img.save(path, "PNG", optimize=True)
    except Exception as e:
        print(f"Error optimizing avatar image at '{path}' (format: {ext}): {e}")

    # Check storage provider and save accordingly
    if storage_provider == 's3':
        # Upload to S3
        stored_key = upload_to_s3(path, filename)

        # Clean up local file
        try:
            os.remove(path)
        except OSError:
            pass

        return stored_key  # Returns "uploads/avatar_xxx.jpg"

    return filename  # Returns local filename

def smart_detect_flags(*texts):
    """Scans multiple text fields for common keywords indicating eligibility flags."""
    combined = " ".join(filter(None, texts)).lower()

    def match_any(patterns):
        return any(re.search(pattern, combined) for pattern in patterns)

    return {
        "is_ofw": match_any([
            r'\bofw\b', r'\boverseas\b', r'\babroad\b', r'working.*abroad', r'migrant.*worker',
        ]),
        "is_farmers_child": match_any([
            r'\bfarmer\b', r'\bagriculture\b', r'\bmagsasaka\b', r'\bfarming\b',
        ])
    }


def compute_gwa(grades: list) -> float:
    try:
        # Ensure all values are Decimal for safe computation
        def safe_decimal(value):
            return value if isinstance(value, Decimal) else Decimal(str(value))

        total_units = sum(safe_decimal(g["units"]) for g in grades)
        if total_units == 0:
            return 0.0

        total_weighted = sum(
            safe_decimal(g["grade"]) * safe_decimal(g["units"]) for g in grades
        )

        gwa = total_weighted / total_units
        return float(round(gwa, 4))  # Convert back to float for output if needed

    except (InvalidOperation, TypeError, KeyError) as e:
        print("GWA computation failed:", e)
        return 0.0


def safe_json_parse(config_str: str, default: Dict = None) -> Dict:
    """Safely parse JSON configuration with fallback - FIXED VERSION"""
    # print(f"Input config_str: {config_str}")

    if not config_str:
        # print("Empty config_str, returning default")
        return default or SCHOLARSHIP_CONFIG.copy()

    try:
        config = json.loads(config_str)
        # print(f"Parsed config: {config}")

        if isinstance(config, str):
            config = json.loads(config)
            # print(f"Double parsed config: {config}")

        if not isinstance(config, dict):
            # print("Config is not a dict, returning default")
            return default or SCHOLARSHIP_CONFIG.copy()

        # Start with a COPY of the default config (important!)
        merged_config = {}

        # First, copy all default values
        for key, value in SCHOLARSHIP_CONFIG.items():
            if isinstance(value, dict):
                merged_config[key] = value.copy()  # Shallow copy for nested dicts
            elif isinstance(value, list):
                merged_config[key] = value.copy()  # Copy lists
            else:
                merged_config[key] = value

        # print(f"Initial merged_config: {merged_config}")

        # Now override with values from the parsed config
        for key, value in config.items():
            if key == "priorities" and isinstance(value, dict):
                # Merge priorities specifically
                # print(f"Merging priorities: default={merged_config['priorities']}, override={value}")
                for priority_key, priority_value in value.items():
                    merged_config["priorities"][priority_key] = priority_value
                # print(f"After priority merge: {merged_config['priorities']}")
            else:
                merged_config[key] = value

        # print(f"Final merged_config: {merged_config}")
        return merged_config

    except (json.JSONDecodeError, TypeError) as e:
        print(f"Error parsing JSON config: {e}")
        return default or SCHOLARSHIP_CONFIG.copy()

def extract_applicant_flags(applicant: Dict, prequalify = False) -> Dict[str, Any]:
    """Extract and process applicant flags and data"""
    flags = smart_detect_flags(
        applicant.get("father_occupation", ""),
        applicant.get("mother_occupation", ""),
    )


    if not prequalify:
        total_income = (applicant.get("father_income") or 0) + (applicant.get("mother_income") or 0)
    else:
        total_income = applicant.get("income", 0)

    return {
        "is_ofw": flags["is_ofw"],
        "is_farmers_child": flags["is_farmers_child"],
        "is_ip": applicant.get("ip_affiliation") not in ("None", "N/A", None, ""),
        "is_pwd": applicant.get("is_pwd", False),
        "course_id": applicant.get("course_id", 0),
        "department_id": applicant.get("department_id", 0),
        "campus_id": applicant.get("campus_id", 0),
        "year_level": applicant.get("year_level", 0),
        "total_income": total_income
    }

