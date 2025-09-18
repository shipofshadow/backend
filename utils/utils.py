import json
import os
import re
import uuid
import subprocess
from decimal import Decimal, InvalidOperation
from typing import Dict, Any

from werkzeug.utils import secure_filename
from PIL import Image
from config import ALLOWED_EXTENSIONS, UPLOAD_FOLDER, SCHOLARSHIP_CONFIG
from .avatar_generator import create_initials_avatar


def allowed_file(filename):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )

def generate_avatar(name):
    img = create_initials_avatar(name)
    unique_id = uuid.uuid4().hex
    filename = f"avatar_{unique_id}.png"
    path = os.path.join(UPLOAD_FOLDER, filename)
    img.save(path)
    return path

def save_file(file, user_id, file_type):
    # Get extension safely
    _, ext = os.path.splitext(secure_filename(file.filename))
    ext = ext.lower()
    unique_id = uuid.uuid4().hex
    filename = f"{user_id}_{file_type}_{unique_id}{ext}"
    path = os.path.join(UPLOAD_FOLDER, filename)

    file.save(path)

    # IMAGE COMPRESSION
    if ext in [".jpg", ".jpeg", ".png"]:
        try:
            img = Image.open(file)
            if ext in [".jpg", ".jpeg"]:
                img.save(path, "JPEG", optimize=True, quality=70)  # 70% quality
            elif ext == ".png":
                img.save(path, "PNG", optimize=True)
        except Exception as e:
            # fallback if Pillow fails
            file.save(path)

    # DOCX or others → save
    else:
        file.save(path)

    return path


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

def extract_applicant_flags(applicant: Dict) -> Dict[str, Any]:
    """Extract and process applicant flags and data"""
    flags = smart_detect_flags(
        applicant.get("father_occupation", ""),
        applicant.get("mother_occupation", ""),
    )

    total_income = (applicant.get("father_income") or 0) + (applicant.get("mother_income") or 0)

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

