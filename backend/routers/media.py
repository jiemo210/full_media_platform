"""全媒体聚合平台 - 本地素材库路由"""
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import desc
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from deps import get_token_payload, require_editor
from models import MediaAsset
from storage import get_storage

router = APIRouter(prefix="/api/media", tags=["素材库"])
require_editor_dep = require_editor

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"}
MAX_SIZE = 10 * 1024 * 1024  # 10MB


def _detect_image(data: bytes) -> str:
    """按魔数识别真实图片类型（不信任客户端 content_type）。"""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:2] == b"BM":
        return "image/bmp"
    return ""


def _to_dict(a: MediaAsset) -> dict:
    return {
        "id": a.id, "type": a.type, "url": a.url, "original_name": a.original_name or "",
        "mime": a.mime or "", "size": a.size or 0, "created_at": a.created_at,
    }


@router.get("")
def list_assets(
    type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
):
    query = db.query(MediaAsset)
    if type:
        query = query.filter(MediaAsset.type == type)
    total = query.count()
    rows = query.order_by(desc(MediaAsset.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_to_dict(a) for a in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    type: str = Form("image"),
    user: dict = Depends(require_editor),
    db: Session = Depends(get_db),
):
    mime = file.content_type or ""
    if mime not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的图片类型: {mime or 'unknown'}")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="图片不能超过 10MB")
    actual = _detect_image(data)
    if actual != mime:
        raise HTTPException(status_code=400, detail=f"图片内容与声明类型不符（{actual or '无法识别'}）")
    ext = os.path.splitext(file.filename or "")[1].lower() or ".img"
    rel = get_storage().save_bytes(data, f"{uuid.uuid4().hex}{ext}", "images")
    asset = MediaAsset(
        type=type or "image",
        url=get_storage().url_for(rel),
        original_name=file.filename or "",
        mime=mime,
        size=len(data),
        created_by=user.get("user_id"),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _to_dict(asset)


@router.delete("/{asset_id}")
def delete_asset(asset_id: int, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    asset = db.query(MediaAsset).filter(MediaAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="素材不存在")
    if asset.url.startswith("/media/"):
        get_storage().delete(asset.url[len("/media/"):])
    db.delete(asset)
    db.commit()
    return {"message": "素材已删除"}
