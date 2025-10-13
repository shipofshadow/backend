from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

argon = PasswordHasher()

def hash_password(raw_password: str) -> str:
    return argon.hash(raw_password)

def verify_password(raw_password: str, hashed: str) -> bool:
    try:
        return argon.verify(hashed, raw_password)
    except VerifyMismatchError:
        return False
