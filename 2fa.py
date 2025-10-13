import pyotp
import qrcode
import os
from cryptography.fernet import Fernet

# -----------------------------
# 1. Setup Fernet key
# -----------------------------
# Generate once and store in .env / secure config
FERNET_KEY = Fernet.generate_key()
fernet = Fernet(FERNET_KEY)

# -----------------------------
# 2. Generate a unique TOTP secret for user
# -----------------------------
def generate_user_secret():
    secret = pyotp.random_base32()
    encrypted_secret = fernet.encrypt(secret.encode()).decode()  # encrypt before storing
    return secret, encrypted_secret  # store encrypted_secret in DB

# Example
user_email = "bitress@example.com"
secret, encrypted_secret = generate_user_secret()
print("Encrypted secret to store in DB:", encrypted_secret)

# -----------------------------
# 3. Generate QR code for authenticator apps
# -----------------------------
totp = pyotp.TOTP(secret)
uri = totp.provisioning_uri(name=user_email, issuer_name="iScholar")
print("Provisioning URI:", uri)

qr_img = qrcode.make(uri)
qr_img.save("qr.png")
print("QR code saved as qr.png")

# -----------------------------
# 4. Verify OTP from user
# -----------------------------
def verify_user_otp(encrypted_secret, user_input):
    # decrypt the secret
    secret = fernet.decrypt(encrypted_secret.encode()).decode()
    totp = pyotp.TOTP(secret)
    return totp.verify(user_input)

# Example verification loop
while True:
    code = input("Enter the 6-digit OTP from app: ")
    if verify_user_otp(encrypted_secret, code):
        print("✅ OTP verified!")
        break
    else:
        print("❌ Invalid OTP, try again.")
