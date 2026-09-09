"""全媒体聚合平台 - 认证路由"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth_utils import create_token, hash_password, verify_password
from database import get_db
from deps import get_current_user
from models import User
from schemas import ChangePasswordRequest, LoginRequest, LoginResponse

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")
    user.last_login = datetime.utcnow()
    db.commit()
    return LoginResponse(
        token=create_token(user.id, user.username, user.role),
        user={
            "id": user.id, "username": user.username, "role": user.role,
            "nickname": user.nickname or user.username,
            "must_change_password": bool(user.must_change_password),
        },
        must_change_password=bool(user.must_change_password),
    )


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id, "username": user.username, "role": user.role,
        "nickname": user.nickname, "must_change_password": bool(user.must_change_password),
    }


@router.post("/change-password")
def change_password(req: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """修改密码（初始默认口令登录后强制调用）。"""
    if not verify_password(req.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="新密码至少 8 位")
    if req.new_password == req.old_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")
    user.password_hash = hash_password(req.new_password)
    user.must_change_password = False
    db.commit()
    return {"message": "密码已修改"}
