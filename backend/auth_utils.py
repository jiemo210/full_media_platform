"""全媒体聚合平台 - JWT 认证工具（bcrypt 直连，避免 passlib 兼容问题）"""
from datetime import datetime, timedelta

import bcrypt
from jose import jwt

from config import get as cfg_get
from config import get_jwt_secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: int, username: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=cfg_get("JWT_EXPIRE_HOURS", 24))
    payload = {"user_id": user_id, "username": username, "role": role, "exp": expire}
    return jwt.encode(payload, get_jwt_secret(), algorithm="HS256")


def verify_token(token: str):
    try:
        return jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
    except Exception:
        return None
