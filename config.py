import os
from dotenv import load_dotenv

load_dotenv()

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

class Config:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "ischolar_dev")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret")
