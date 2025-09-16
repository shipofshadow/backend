# extensions.py
from flask_caching import Cache
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_socketio import SocketIO

cache = Cache()
jwt = JWTManager()
mail = Mail()
socketio = SocketIO()
