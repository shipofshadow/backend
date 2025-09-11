import os
import re
import uuid
import subprocess
from decimal import Decimal, InvalidOperation

from werkzeug.utils import secure_filename
from PIL import Image
from config import ALLOWED_EXTENSIONS, UPLOAD_FOLDER


def allowed_file(filename):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )

def save_file(file, user_id, file_type):
    # Get extension safely
    _, ext = os.path.splitext(secure_filename(file.filename))
    ext = ext.lower()
    unique_id = uuid.uuid4().hex
    filename = f"{user_id}_{file_type}_{unique_id}{ext}"
    path = os.path.join(UPLOAD_FOLDER, filename)

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

    # PDF COMPRESSION (Ghostscript required: apt install ghostscript)
    # elif ext == ".pdf":
    #     tmp_path = os.path.join("/tmp", filename)
    #     file.save(tmp_path)
    #     try:
    #         subprocess.run([
    #             "gs",
    #             "-sDEVICE=pdfwrite",
    #             "-dCompatibilityLevel=1.4",
    #             "-dPDFSETTINGS=/ebook",
    #             "-dNOPAUSE", "-dQUIET", "-dBATCH",
    #             f"-sOutputFile={path}", tmp_path
    #         ], check=True)
    #         os.remove(tmp_path)
    #     except Exception as e:
    #         # fallback if Ghostscript fails
    #         os.rename(tmp_path, path)

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
