from pathlib import Path
from dotenv import load_dotenv
import os

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "docx"}
UPLOAD_FOLDER = '/var/www/cdn.ischolar/uploads'
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

