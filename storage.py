from config import Config
import redis
import pymysql
from pymysql.cursors import DictCursor

# Redis
redis_client = redis.Redis(
    host=Config.REDIS_HOST,
    port=Config.REDIS_PORT,
    password=Config.REDIS_PASSWORD,
    socket_connect_timeout=2,
    socket_timeout=2
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