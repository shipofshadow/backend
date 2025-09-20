from pathlib import Path
from dotenv import load_dotenv
import os

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "docx"}
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)
class Config:
    DB_HOST = os.getenv("DB_HOST")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_NAME = os.getenv("DB_NAME")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = int(os.getenv("REDIS_PORT"))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

    FERNET_KEY = os.getenv("FERNET_KEY")

    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True") == "True"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "False") == "True"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", MAIL_USERNAME)

    APP_URL = os.getenv("APP_URL")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

SCHOLARSHIP_CONFIG = {
    "min_gwa": None,
    "max_gwa": None,
    "min_income": None,
    "max_income": None,
    "priorities": {
        "must_be_ofw": False,
        "prefer_farmers_child": False,
        "require_ip": False,
        "prefer_pwd": False
    },
    "preferred_course_ids": [],
    "preferred_department_ids": [],
    "preferred_campus_ids": [],
    "preferred_year_levels": [],
    "min_units_enrolled": None,
    "max_units_enrolled": None,
    "priority": []
}