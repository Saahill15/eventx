from datetime import datetime, timedelta
from jose import JWTError, jwt
from dotenv import load_dotenv
import os

load_dotenv()

MIN_SECRET_LENGTH = 32

def _load_secret_key() -> str:
    key = os.getenv("SECRET_KEY", "")
    if len(key) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY must be set to a random value of at least {MIN_SECRET_LENGTH} characters "
            "(generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\")"
        )
    return key

SECRET_KEY = _load_secret_key()
ALGORITHM  = "HS256"
EXPIRE_MIN = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 10080))

def create_token(data: dict, expires_in: timedelta = None):
    to_encode = data.copy()
    now = datetime.utcnow()
    to_encode.update({"iat": now, "exp": now + (expires_in or timedelta(minutes=EXPIRE_MIN))})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
