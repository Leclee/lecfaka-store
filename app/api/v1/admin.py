"""
管理后台 API — 仅超级管理员可访问

功能：用户管理、插件管理（创建/上传/审核）、数据统计
"""

import json
import os
import shutil
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.plugin import StoreUser, StorePlugin, UserPlugin, PaymentOrder
from ...core.auth import get_current_user, require_role

router = APIRouter()

## 插件包上传目录
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "uploads", "plugins")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ==================== 权限依赖 ====================

async def require_superadmin(user: StoreUser = Depends(get_current_user)):
    """超管权限检查"""
    require_role(user, ["superadmin"])
    return user


# ==================== 数据概览 ====================

@router.get("/stats")
async def get_stats(
    user: StoreUser = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """数据概览"""
    total_users = await db.scalar(select(func.count(StoreUser.id)))
    total_plugins = await db.scalar(select(func.count(StorePlugin.id)).where(StorePlugin.status == 1))
    total_orders = await db.scalar(select(func.count(PaymentOrder.id)).where(PaymentOrder.status == "paid"))
    total_revenue = await db.scalar(
        select(func.sum(PaymentOrder.actual_amount)).where(PaymentOrder.status == "paid")
    ) or Decimal("0")

    return {
        "total_users": total_users,
        "total_plugins": total_plugins,
        "total_orders": total_orders,
        "total_revenue": str(total_revenue),
    }


# ==================== 用户管理 ====================

@router.get("/users")
async def list_users(
    user: StoreUser = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    keyword: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """用户列表"""
    query = select(StoreUser)

    if keyword:
        query = query.where(
            or_(
                StoreUser.email.contains(keyword),
                StoreUser.username.contains(keyword),
            )
        )
    if role:
        query = query.where(StoreUser.role == role)

    ## 总数
    count_q = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_q) or 0

    ## 分页
    query = query.order_by(StoreUser.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    users = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "avatar": u.avatar,
                "role": u.role,
                "status": u.status,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            }
            for u in users
        ],
    }


class UpdateRoleRequest(BaseModel):
    role: str  ## superadmin / author / user


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    req: UpdateRoleRequest,
    admin: StoreUser = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """修改用户角色"""
    if req.role not in ("superadmin", "author", "user"):
        raise HTTPException(status_code=400, detail="无效角色")

    result = await db.execute(select(StoreUser).where(StoreUser.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="不能修改自己的角色")

    target.role = req.role
    return {"message": f"已将 {target.username} 的角色修改为 {req.role}"}


class UpdateStatusRequest(BaseModel):
    status: int  ## 0=禁用 1=正常


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    req: UpdateStatusRequest,
    admin: StoreUser = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """启用/禁用用户"""
    result = await db.execute(select(StoreUser).where(StoreUser.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="不能禁用自己")

    target.status = req.status
    status_text = "启用" if req.status == 1 else "禁用"
    return {"message": f"已{status_text}用户 {target.username}"}


# ==================== 插件管理 ====================

class CreatePluginRequest(BaseModel):
    """创建/编辑插件请求"""
    plugin_id: str
    name: str
    type: str = "extension"
    version: str = "1.0.0"
    description: Optional[str] = ""
    detail_html: Optional[str] = ""
    icon: Optional[str] = None
    website: Optional[str] = None
    download_url: Optional[str] = None
    price: float = 0
    is_free: bool = True
    is_official: bool = True
    category: Optional[str] = None
    author_name: Optional[str] = "LecFaka Official"


@router.post("/plugins")
async def create_plugin(
    req: CreatePluginRequest,
    admin: StoreUser = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """创建新插件（纯信息录入，无文件上传）"""
    ## 检查是否已存在
    existing = await db.execute(
        select(StorePlugin).where(StorePlugin.plugin_id == req.plugin_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"插件 ID '{req.plugin_id}' 已存在")

    plugin = StorePlugin(
        plugin_id=req.plugin_id,
        name=req.name,
        type=req.type,
        version=req.version,
        author_id=admin.id,
        author_name=req.author_name or admin.username,
        description=req.description or "",
        detail_html=req.detail_html or "",
        icon=req.icon,
        website=req.website,
        download_url=req.download_url,
        price=Decimal(str(req.price)),
        is_free=req.is_free,
        is_official=req.is_official,
        category=req.category,
        status=1,  ## 默认上架
    )
    db.add(plugin)
    await db.commit()
    await db.refresh(plugin)

    return {"message": f"插件 '{plugin.name}' 创建成功", "plugin_id": plugin.plugin_id}


@router.post("/plugins/upload")
async def upload_plugin(
    file: UploadFile = File(...),
    meta: str = Form(...),
    admin: StoreUser = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    上传插件包（ZIP） + 元数据

    前端通过 FormData 发送：
    - file: ZIP 文件
    - meta: JSON 字符串，包含插件元数据
    """
    ## 解析元数据
    try:
        meta_data = json.loads(meta)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="元数据格式错误")

    plugin_id = meta_data.get("plugin_id", "").strip()
    if not plugin_id:
        raise HTTPException(status_code=400, detail="plugin_id 不能为空")

    ## 验证文件类型
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="只支持 ZIP 格式")

    ## 保存文件
    plugin_dir = os.path.join(UPLOAD_DIR, plugin_id)
    os.makedirs(plugin_dir, exist_ok=True)
    file_path = os.path.join(plugin_dir, f"{plugin_id}_v{meta_data.get('version', '1.0.0')}.zip")

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    ## 生成下载 URL
    download_url = f"/uploads/plugins/{plugin_id}/{os.path.basename(file_path)}"

    ## 创建或更新插件记录
    existing = await db.execute(
        select(StorePlugin).where(StorePlugin.plugin_id == plugin_id)
    )
    plugin = existing.scalar_one_or_none()

    price = Decimal(str(meta_data.get("price", 0)))
    is_free = meta_data.get("is_free", price == 0)

    if plugin:
        ## 更新
        plugin.name = meta_data.get("name", plugin.name)
        plugin.type = meta_data.get("type", plugin.type)
        plugin.version = meta_data.get("version", plugin.version)
        plugin.author_name = meta_data.get("author_name", plugin.author_name)
        plugin.description = meta_data.get("description", plugin.description)
        plugin.detail_html = meta_data.get("detail_html", plugin.detail_html)
        plugin.website = meta_data.get("website", plugin.website)
        plugin.download_url = download_url
        plugin.price = price
        plugin.is_free = is_free
        plugin.updated_at = datetime.utcnow()
        msg = f"插件 '{plugin.name}' 已更新"
    else:
        ## 创建
        plugin = StorePlugin(
            plugin_id=plugin_id,
            name=meta_data.get("name", plugin_id),
            type=meta_data.get("type", "extension"),
            version=meta_data.get("version", "1.0.0"),
            author_id=admin.id,
            author_name=meta_data.get("author_name", admin.username),
            description=meta_data.get("description", ""),
            detail_html=meta_data.get("detail_html", ""),
            icon=meta_data.get("icon"),
            website=meta_data.get("website"),
            download_url=download_url,
            price=price,
            is_free=is_free,
            is_official=meta_data.get("is_official", True),
            category=meta_data.get("category"),
            status=1,
        )
        db.add(plugin)
        msg = f"插件 '{plugin.name}' 发布成功"

    await db.commit()
    return {"message": msg, "plugin_id": plugin_id, "download_url": download_url}


class UpdatePluginStatusRequest(BaseModel):
    status: int  ## 0=下架 1=上架 2=审核中


@router.put("/plugins/{plugin_id}/status")
async def update_plugin_status(
    plugin_id: str,
    req: UpdatePluginStatusRequest,
    admin: StoreUser = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """上架/下架/审核插件"""
    result = await db.execute(select(StorePlugin).where(StorePlugin.plugin_id == plugin_id))
    plugin = result.scalar_one_or_none()
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")

    plugin.status = req.status
    plugin.updated_at = datetime.utcnow()

    status_text = {0: "下架", 1: "上架", 2: "审核中"}.get(req.status, "未知")
    return {"message": f"插件 {plugin.name} 已{status_text}"}
