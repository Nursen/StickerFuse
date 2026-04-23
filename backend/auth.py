"""MongoDB-based authentication — email/password with JWT sessions.

Users collection in the same MongoDB database as packs.
Passwords hashed with bcrypt. Sessions via JWT (HS256).

Endpoints:
    POST /api/auth/signup  — create account
    POST /api/auth/login   — get JWT
    GET  /api/auth/me      — get current user from JWT

Requires:
    MONGODB_URI (already configured for packs)
    AUTH_JWT_SECRET (any random string — used to sign JWTs)

Usage in protected endpoints:
    from backend.auth import get_current_user

    @app.post("/api/packs")
    async def create_pack(user: dict = Depends(get_current_user)):
        user_id = user["id"]
        ...
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, EmailStr
from pymongo import MongoClient

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_JWT_SECRET = os.environ.get("AUTH_JWT_SECRET", "").strip()
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_HOURS = 72

# Lazy-init
_users_collection = None

try:
    import jwt as pyjwt
    HAS_JWT = True
except ImportError:
    try:
        from jose import jwt as pyjwt
        HAS_JWT = True
    except ImportError:
        HAS_JWT = False
        pyjwt = None


def _get_users_collection():
    global _users_collection
    if _users_collection is not None:
        return _users_collection

    mongo_uri = os.environ.get("MONGODB_URI", "").strip()
    if not mongo_uri:
        return None

    db_name = os.environ.get("MONGODB_DB_NAME", "stickerfuse").strip() or "stickerfuse"
    client = MongoClient(mongo_uri)
    db = client[db_name]
    _users_collection = db["users"]
    _users_collection.create_index("email", unique=True)
    return _users_collection


def _is_auth_enabled() -> bool:
    return bool(HAS_JWT and _JWT_SECRET and _get_users_collection() is not None)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def _create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(tz=timezone.utc) + timedelta(hours=_JWT_EXPIRY_HOURS),
        "iat": datetime.now(tz=timezone.utc),
    }
    return pyjwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return pyjwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


async def get_current_user(request: Request) -> dict:
    """Dependency: require a valid JWT.

    Returns dict with: id, email, name
    When auth is not enabled, returns a placeholder (dev mode).
    """
    if not _is_auth_enabled():
        return {"id": "", "email": "", "name": "Dev User"}

    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    payload = _decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    users = _get_users_collection()
    user = users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def get_optional_user(request: Request) -> dict | None:
    """Dependency: optionally extract user. Returns None if no token."""
    if not _is_auth_enabled():
        return None
    token = _extract_token(request)
    if not token:
        return None
    payload = _decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        return None
    users = _get_users_collection()
    return users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})


# ---------------------------------------------------------------------------
# Auth router — mount on the FastAPI app
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=6, max_length=200)
    name: str = Field(default="", max_length=200)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=1, max_length=200)


class AuthResponse(BaseModel):
    status: str = "ok"
    token: str
    user: dict


@router.post("/signup")
async def signup(req: SignupRequest):
    """Create a new user account."""
    if not _is_auth_enabled():
        raise HTTPException(status_code=503, detail="Auth not configured (set AUTH_JWT_SECRET)")

    users = _get_users_collection()
    email = req.email.strip().lower()

    # Check if email already exists
    if users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Email already registered")

    user_id = uuid.uuid4().hex[:16]
    user = {
        "id": user_id,
        "email": email,
        "name": req.name.strip() or email.split("@")[0],
        "password_hash": _hash_password(req.password),
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    users.insert_one(user)

    token = _create_token(user_id, email)
    return AuthResponse(
        token=token,
        user={"id": user_id, "email": email, "name": user["name"]},
    )


@router.post("/login")
async def login(req: LoginRequest):
    """Log in with email and password."""
    if not _is_auth_enabled():
        raise HTTPException(status_code=503, detail="Auth not configured (set AUTH_JWT_SECRET)")

    users = _get_users_collection()
    email = req.email.strip().lower()

    user = users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not _check_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _create_token(user["id"], email)
    return AuthResponse(
        token=token,
        user={"id": user["id"], "email": email, "name": user.get("name", "")},
    )


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get the current user from JWT."""
    return {"status": "ok", "user": user}
