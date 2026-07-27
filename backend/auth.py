"""
Authentication module for MyAgent.

Provides username/password authentication with bcrypt password hashing,
JWT token management, and session persistence (stored in database).
"""

import os
import time
from typing import Optional

import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from database import create_session, get_session_by_token, delete_session

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "myagent-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 72  # 3 days

# Password hashing context (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme for FastAPI dependency injection
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_token(user_id: int, username: str) -> str:
    """Create a JWT access token and persist it as a session in the database."""
    now = int(time.time())
    expires_at = now + JWT_EXPIRY_HOURS * 3600
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    # Persist the session in the database (Supabase or SQLite)
    try:
        create_session(user_id, token, float(expires_at))
    except Exception as e:
        print(f"[Auth] Warning: failed to persist session: {e}")
    
    return token


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token. Returns payload dict or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    """
    FastAPI dependency that extracts the current user from the JWT token.
    Validates the session exists in the database (not just the JWT).
    Returns None if no valid session (anonymous access allowed).
    """
    if credentials is None:
        return None

    token = credentials.credentials

    # First validate the JWT itself
    payload = decode_token(token)
    if payload is None:
        return None

    # Then validate the session exists in the database (not expired)
    session = get_session_by_token(token)
    if session is None:
        # Session not found or expired — clean up
        print(f"[Auth] No valid database session for token (may have expired)")
        return None

    return {
        "user_id": int(payload["sub"]),
        "username": payload["username"],
        "session_id": session["id"],
    }


async def require_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """
    FastAPI dependency that requires a valid authenticated session.
    Raises 401 if no token or invalid/expired session.
    """
    user = await get_current_user(credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
