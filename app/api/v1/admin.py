"""
管理后台 API — 仅超级管理员可访问

功能：用户管理、插件审核、数据统计
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.plugin import StoreUser, StorePlugin, UserPlugin
from ...core.auth import get_current_user, require_role

router = APIRouter()


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
    user_count = await db.scalar(select(func.count(StoreUser.id)))
    plugin_count = await db.scalar(select(func.count(StorePlugin.id)).where(StorePlugin.status == 1))
    order_count = await db.scalar(select(func.count(UserPlugin.id)))
    author_count = await db.scalar(select(func.count(StoreUser.id)).where(StoreUser.role == "author"))

    return {
        "user_count": user_count,
        "plugin_count": plugin_count,
        "order_count": order_count,
        "author_count": author_count,
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
