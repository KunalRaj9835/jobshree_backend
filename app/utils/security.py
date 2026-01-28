from passlib.context import CryptContext
import os

# 1. THE KEYS
SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_random_key_CHANGE_THIS")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 2. THE PASSWORD TOOLS (Using Argon2!)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    """Checks if the typed password matches the saved hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Converts a plain password (e.g., '123') into a secret hash."""
    return pwd_context.hash(password)