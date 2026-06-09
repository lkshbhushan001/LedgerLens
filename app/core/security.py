"""JWT creation, validation, and RBAC middleware.

Uses PyJWT for JWT operations and passlib for password hashing.
The `require_user` dependency enforces identity *before* any AI or DB code runs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.models.schemas import UserIdentity

logger = logging.getLogger(__name__)

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Password helpers (for local user management if needed)
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT lifecycle
# ---------------------------------------------------------------------------

def create_access_token(
    user_id: str | UserIdentity,
    email: str | None = None,
    permission_groups: list[str] | None = None,
    is_admin: bool = False,
    expires_delta: timedelta | None = None,
) -> str:
    """Encode identity claims into a JWT.

    Supports either passing explicit identity fields or a UserIdentity object.
    """
    if isinstance(user_id, UserIdentity):
        user = user_id
        email = user.email
        permission_groups = user.permission_groups
        is_admin = user.is_admin
        user_id = user.user_id

    if not email or permission_groups is None:
        raise ValueError("email and permission_groups are required to create a token")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "roles": [r.lower() for r in permission_groups],
        "admin": is_admin,
        "iat": now,
        "exp": now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _decode_token(token: str) -> dict:
    """Decode and validate a JWT string."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.InvalidTokenError as exc:
        logger.warning("JWT decode failed: %s", exc)
        raise AuthenticationError("Invalid or expired token") from exc


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def require_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UserIdentity:
    """FastAPI dependency that resolves a Bearer token to a ``UserIdentity``.

    Raises:
        AuthenticationError: Missing or invalid token.
    """
    if creds is None:
        raise AuthenticationError("Authorization header required")

    payload = _decode_token(creds.credentials)
    user_id: str | None = payload.get("sub")
    email: str | None = payload.get("email")
    roles: list[str] | None = payload.get("roles")

    if not user_id or not email or roles is None:
        raise AuthenticationError("Malformed token payload")

    return UserIdentity(
        user_id=user_id,
        email=email,
        permission_groups=roles,
        is_admin=bool(payload.get("admin", False)),
    )


# ---------------------------------------------------------------------------
# Role guard helper
# ---------------------------------------------------------------------------

async def require_admin(user: Annotated[UserIdentity, Depends(require_user)]) -> UserIdentity:
    """Dependency that asserts the resolved user has admin rights."""
    if not user.is_admin:
        raise AuthorizationError("Admin privileges required")
    return user