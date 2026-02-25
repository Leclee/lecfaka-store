"""
授权验证 API — 供发卡站后端调用

验证逻辑：域名 + plugin_id → 查找是否有用户购买了该插件并绑定了该域名
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.plugin import UserPlugin, StorePlugin

router = APIRouter()


class VerifyRequest(BaseModel):
    """验证请求（发卡站后端调用）"""
    plugin_id: str
    domain: str


class VerifyByUserRequest(BaseModel):
    """通过用户ID验证（发卡站后端绑定了Store账号后调用）"""
    plugin_id: str
    user_id: int
    domain: str


@router.post("/verify")
async def verify_domain(req: VerifyRequest, db: AsyncSession = Depends(get_db)):
    """
    验证某个域名是否有权使用某个插件。

    不再需要授权码！直接用 域名 + plugin_id 验证。
    """
    result = await db.execute(
        select(UserPlugin).where(
            UserPlugin.plugin_id == req.plugin_id,
            UserPlugin.bound_domain == req.domain,
            UserPlugin.status == 1,
        )
    )
    up = result.scalar_one_or_none()

    if not up:
        return {"valid": False, "error": "未找到授权或域名未绑定"}

    ## 检查是否过期
    if up.expires_at and up.expires_at < datetime.now(timezone.utc):
        return {"valid": False, "error": "授权已过期"}

    return {
        "valid": True,
        "plugin_id": req.plugin_id,
        "domain": req.domain,
        "user_id": up.user_id,
        "purchased_at": up.purchased_at.isoformat() if up.purchased_at else None,
        "expires_at": up.expires_at.isoformat() if up.expires_at else None,
    }


@router.post("/verify-user")
async def verify_by_user(req: VerifyByUserRequest, db: AsyncSession = Depends(get_db)):
    """
    通过用户ID验证是否购买了某个插件。

    发卡站绑定了 Store 账号后，用 user_id + plugin_id 校验。
    同时自动绑定域名（如果尚未绑定）。
    """
    result = await db.execute(
        select(UserPlugin).where(
            UserPlugin.user_id == req.user_id,
            UserPlugin.plugin_id == req.plugin_id,
            UserPlugin.status == 1,
        )
    )
    up = result.scalar_one_or_none()

    if not up:
        return {"valid": False, "error": "用户未购买此插件"}

    ## 检查过期
    if up.expires_at and up.expires_at < datetime.now(timezone.utc):
        return {"valid": False, "error": "授权已过期"}

    ## 自动绑定域名（首次访问时）
    if not up.bound_domain:
        up.bound_domain = req.domain
        await db.flush()  ## 立即持久化绑定，防止后续异常导致丢失

    ## 域名不匹配
    if up.bound_domain != req.domain:
        return {
            "valid": False,
            "error": f"插件已绑定到 {up.bound_domain}，当前域名 {req.domain} 不匹配",
            "bound_domain": up.bound_domain,
        }

    return {
        "valid": True,
        "plugin_id": req.plugin_id,
        "domain": req.domain,
        "user_id": up.user_id,
        "bound_domain": up.bound_domain,
    }


class CheckPurchaseRequest(BaseModel):
    """检查购买状态请求"""
    plugin_id: str
    user_id: int


@router.post("/check-purchase")
async def check_purchase(
    req: CheckPurchaseRequest,
    db: AsyncSession = Depends(get_db),
):
    """检查某用户是否购买了某插件（不验证域名）"""
    result = await db.execute(
        select(UserPlugin).where(
            UserPlugin.user_id == req.user_id,
            UserPlugin.plugin_id == req.plugin_id,
            UserPlugin.status == 1,
        )
    )
    up = result.scalar_one_or_none()
    return {"purchased": up is not None, "bound_domain": up.bound_domain if up else None}