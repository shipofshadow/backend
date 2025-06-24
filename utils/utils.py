import os
from werkzeug.utils import secure_filename
from config import ALLOWED_EXTENSIONS

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file, user_id, file_type, upload_folder):
    filename = secure_filename(f"{user_id}_{file_type}_{file.filename}")
    path = os.path.join(upload_folder, filename)
    file.save(path)
    return path
