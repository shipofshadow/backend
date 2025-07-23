import os
import uuid
from werkzeug.utils import secure_filename
from config import ALLOWED_EXTENSIONS

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file, user_id, file_type, upload_folder):
    _, ext = os.path.splitext(secure_filename(file.filename))
    unique_id = uuid.uuid4().hex
    filename = f"{user_id}_{file_type}_{unique_id}{ext}"
    path = os.path.join(upload_folder, filename)
    file.save(path)
    return path
