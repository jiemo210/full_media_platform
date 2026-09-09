"""全媒体聚合平台 - 通用鉴权依赖"""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from auth_utils import verify_token
from database import get_db
from models import User


def get_token_payload(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    payload = verify_token(auth[7:])
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    return payload


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    payload = get_token_payload(request)
    user = db.query(User).filter(User.id == payload.get("user_id")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return user


def require_roles(*roles):
    def checker(request: Request, db: Session = Depends(get_db)) -> dict:
        payload = get_token_payload(request)
        user = db.query(User).filter(User.id == payload.get("user_id")).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="用户不存在或已禁用")
        if user.role not in set(roles):
            raise HTTPException(status_code=403, detail="权限不足")
        if getattr(user, "must_change_password", False):
            raise HTTPException(status_code=403, detail="请先修改初始密码")
        return {"user_id": user.id, "username": user.username, "role": user.role}
    return checker


require_admin = require_roles("admin")
require_editor = require_roles("admin", "editor")
