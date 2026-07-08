"""
BiasGuard Backend — auth.py
================================================================
JWT-based authentication: password hashing, token creation,
and the dependency that protects routes.

SECURITY NOTE: SECRET_KEY here is a dev placeholder. In production
it must come from an environment variable, never committed to git.
"""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import User, get_db

# ----------------------------------------------------------------
# Config
# ----------------------------------------------------------------
SECRET_KEY = os.environ.get(
    "BIASGUARD_SECRET_KEY",
    "dev-only-secret-change-me-in-production",  # DEV PLACEHOLDER
)

# Fail closed: never run in production with the dev placeholder secret.
if (os.environ.get("BIASGUARD_ENV", "").lower() == "production"
        and SECRET_KEY == "dev-only-secret-change-me-in-production"):
    raise RuntimeError(
        "BIASGUARD_SECRET_KEY must be set to a strong random value in "
        "production. Refusing to start with the development placeholder."
    )

ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# ----------------------------------------------------------------
# Password helpers — uses the bcrypt library directly.
# (passlib is not compatible with bcrypt 5.x, so we skip it.)
# bcrypt has a hard 72-byte limit on passwords; we truncate to be safe.
# ----------------------------------------------------------------
def hash_password(plain: str) -> str:
    pw_bytes = plain.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    pw_bytes = plain.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ----------------------------------------------------------------
# Token helpers
# ----------------------------------------------------------------
def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire,
               "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme),
                     db: Session = Depends(get_db)) -> User:
    """FastAPI dependency — resolves the JWT to a User, or 401s."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_error
    except JWTError:
        raise credentials_error

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_error
    return user
