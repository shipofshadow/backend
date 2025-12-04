from config import Config
import redis
import boto3
import pymysql
from pymysql.cursors import DictCursor

# Redis
redis_client = redis.Redis(
    host=Config.REDIS_HOST,
    port=Config.REDIS_PORT,
    password=Config.REDIS_PASSWORD
)

s3_client = boto3.client(
    "s3",
    aws_access_key_id=Config.S3_ACCESS_KEY,
    aws_secret_access_key=Config.S3_SECRET_KEY,
    region_name=Config.S3_REGION,
    endpoint_url=Config.S3_ENDPOINT # Optional, handles non-AWS S3
)

# MySQL
def get_connection():
    return pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset='utf8mb4',
        cursorclass=DictCursor
    )

def close():
    return None