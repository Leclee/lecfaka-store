"""
商店 API - 插件列表、详情、购买

购买流程：
- 免费插件：直接创建 UserPlugin 记录
- 付费插件：通过支付系统（/api/v1/pay/create-order）完成支付后自动创建
"""

import os
import json
import secrets
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.plugin import StorePlugin, StoreUser, UserPlugin
from ...core.auth import get_current_user, get_optional_user
from ...core.payment import payment_manager

router = APIRouter()


# ==================== 插件列表（公开） ====================

@router.get("/plugins")
async def list_plugins(
    db: AsyncSession = Depends(get_db),
    type: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    user: Optional[StoreUser] = Depends(get_optional_user),
):
    """获取插件列表（公开接口，登录用户会标记已购买状态）"""
    query = select(StorePlugin).where(StorePlugin.status == 1)

    if type:
        query = query.where(StorePlugin.type == type)
    if keyword:
        query = query.where(StorePlugin.name.contains(keyword))
    if category == "official":
        query = query.where(StorePlugin.is_official == True)
    elif category == "enterprise":
        query = query.where(StorePlugin.is_enterprise == True)
    elif category == "free":
        query = query.where(StorePlugin.is_free == True)
    elif category == "third_party":
        query = query.where(StorePlugin.is_official == False)

    query = query.order_by(StorePlugin.created_at.desc())
    result = await db.execute(query)
    plugins = result.scalars().all()

    ## 如果用户已登录，查询已购买的插件
    purchased_ids = set()
    if user:
        up_result = await db.execute(
            select(UserPlugin.plugin_id).where(
                UserPlugin.user_id == user.id,
                UserPlugin.status == 1,
            )
        )
        purchased_ids = {row[0] for row in up_result.all()}

    return {
        "items": [
            {
                "id": p.plugin_id,
                "name": p.name,
                "version": p.version,
                "type": p.type,
                "author": p.author_name,
                "description": p.description,
                "icon": p.icon,
                "website": p.website,
                "price": float(p.price),
                "is_free": p.is_free,
                "is_official": p.is_official,
                "is_enterprise": p.is_enterprise,
                "category": p.category,
                "channels": p.channels,
                "download_count": p.download_count,
                "purchase_count": p.purchase_count,
                "purchased": p.plugin_id in purchased_ids,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in plugins
        ],
        "payment_available": payment_manager.is_available(),
    }


# ==================== 插件详情（公开） ====================

@router.get("/plugins/{plugin_id}")
async def get_plugin(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    user: Optional[StoreUser] = Depends(get_optional_user),
):
    """获取插件详情"""
    result = await db.execute(
        select(StorePlugin).where(StorePlugin.plugin_id == plugin_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="插件不存在")

    ## 查询当前用户是否已购买
    purchased = False
    bound_domain = None
    if user:
        up_result = await db.execute(
            select(UserPlugin).where(
                UserPlugin.user_id == user.id,
                UserPlugin.plugin_id == plugin_id,
                UserPlugin.status == 1,
            )
        )
        up = up_result.scalar_one_or_none()
        if up:
            purchased = True
            bound_domain = up.bound_domain

    screenshots = []
    if p.screenshots:
        try:
            screenshots = json.loads(p.screenshots)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "id": p.plugin_id,
        "name": p.name,
        "version": p.version,
        "type": p.type,
        "author": p.author_name,
        "description": p.description,
        "detail_html": p.detail_html,
        "icon": p.icon,
        "screenshots": screenshots,
        "website": p.website,
        "download_url": p.download_url,
        "price": float(p.price),
        "is_free": p.is_free,
        "is_official": p.is_official,
        "channels": p.channels,
        "download_count": p.download_count,
        "purchase_count": p.purchase_count,
        "purchased": purchased,
        "bound_domain": bound_domain,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("/download/{plugin_id}")
async def download_plugin(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    user: Optional[StoreUser] = Depends(get_optional_user),
):
    """下载插件包"""
    result = await db.execute(
        select(StorePlugin).where(StorePlugin.plugin_id == plugin_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="插件不存在")

    ## 如果不是免费插件，需要验证是否购买
    if not p.is_free:
        if not user:
            raise HTTPException(status_code=401, detail="请登录后下载付费插件")
        
        up_result = await db.execute(
            select(UserPlugin).where(
                UserPlugin.user_id == user.id,
                UserPlugin.plugin_id == plugin_id,
                UserPlugin.status == 1,
            )
        )
        if not up_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="尚未购买该插件，无法下载")

    ## 记录下载次数
    p.download_count = (p.download_count or 0) + 1
    await db.commit()

    if p.download_url and p.download_url.startswith("/uploads/"):
        ## 构造服务器本地路径
        file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "uploads",
            p.download_url.replace("/uploads/", "")
        )
        
        if os.path.exists(file_path):
            return FileResponse(file_path, filename=os.path.basename(file_path))
            
    raise HTTPException(status_code=404, detail="插件包文件不存在，请联系管理员")


# ==================== 购买插件（需登录） ====================

class PurchaseRequest(BaseModel):
    plugin_id: str


@router.post("/purchase")
async def purchase_plugin(
    req: PurchaseRequest,
    user: StoreUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    购买插件

    - 免费插件：直接关联到用户账号
    - 付费插件：返回提示需要通过支付接口
    """
    ## 1. 验证插件
    result = await db.execute(
        select(StorePlugin).where(
            StorePlugin.plugin_id == req.plugin_id,
            StorePlugin.status == 1,
        )
    )
    plugin = result.scalar_one_or_none()
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在或已下架")

    ## 2. 检查是否已购买
    existing = await db.execute(
        select(UserPlugin).where(
            UserPlugin.user_id == user.id,
            UserPlugin.plugin_id == req.plugin_id,
            UserPlugin.status == 1,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="您已购买过此插件")

    ## 3. 付费插件 → 走支付流程
    if not plugin.is_free and float(plugin.price) > 0:
        if payment_manager.is_available():
            return {
                "success": False,
                "require_payment": True,
                "message": "请通过支付接口购买此插件",
                "plugin_id": req.plugin_id,
                "plugin_name": plugin.name,
                "price": float(plugin.price),
                "gateways": payment_manager.list_gateways(),
            }
        else:
            ## 支付未配置时直接购买（仅用于测试）
            pass

    ## 4. 免费插件 / 未配置支付时 → 直接创建购买记录
    order_no = f"ORD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3).upper()}"
    up = UserPlugin(
        user_id=user.id,
        plugin_id=req.plugin_id,
        status=1,
        bound_domain=None,
        rebind_count=0,
        max_rebinds=3,
        order_no=order_no,
        purchased_at=datetime.utcnow(),
    )
    db.add(up)

    ## 更新购买计数
    plugin.purchase_count += 1

    await db.flush()

    return {
        "success": True,
        "message": "获取成功" if plugin.is_free else "购买成功",
        "order_no": order_no,
        "plugin_id": req.plugin_id,
        "plugin_name": plugin.name,
        "price": float(plugin.price),
    }


# ==================== 我的插件（需登录） ====================

@router.get("/my-plugins")
async def my_plugins(
    user: StoreUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户购买的所有插件"""
    result = await db.execute(
        select(UserPlugin, StorePlugin).join(
            StorePlugin, UserPlugin.plugin_id == StorePlugin.plugin_id
        ).where(
            UserPlugin.user_id == user.id,
        ).order_by(UserPlugin.purchased_at.desc())
    )
    rows = result.all()

    return {
        "items": [
            {
                "id": up.plugin_id,
                "name": sp.name,
                "version": sp.version,
                "type": sp.type,
                "icon": sp.icon,
                "author": sp.author_name,
                "price": float(sp.price),
                "is_free": sp.is_free,
                "status": up.status,
                "status_text": {0: "已退款", 1: "已激活", 2: "已过期"}.get(up.status, "未知"),
                "bound_domain": up.bound_domain,
                "rebind_count": up.rebind_count,
                "max_rebinds": up.max_rebinds,
                "rebind_remaining": up.max_rebinds - up.rebind_count,
                "order_no": up.order_no,
                "purchased_at": up.purchased_at.isoformat() if up.purchased_at else None,
                "expires_at": up.expires_at.isoformat() if up.expires_at else None,
            }
            for up, sp in rows
        ]
    }


# ==================== 域名绑定/换绑（需登录） ====================

class BindDomainRequest(BaseModel):
    plugin_id: str
    domain: str


class RebindDomainRequest(BaseModel):
    plugin_id: str
    new_domain: str


@router.post("/bind-domain")
async def bind_domain(
    req: BindDomainRequest,
    user: StoreUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """绑定域名（首次绑定）"""
    up = await _get_user_plugin(user.id, req.plugin_id, db)

    if up.bound_domain:
        raise HTTPException(status_code=400, detail=f"已绑定域名 {up.bound_domain}，如需更换请使用换绑功能")

    up.bound_domain = req.domain
    _append_history(up, "首次绑定", req.domain)

    return {"success": True, "message": f"域名已绑定为 {req.domain}", "domain": req.domain}


@router.post("/rebind-domain")
async def rebind_domain(
    req: RebindDomainRequest,
    user: StoreUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """换绑域名"""
    up = await _get_user_plugin(user.id, req.plugin_id, db)

    if not up.bound_domain:
        raise HTTPException(status_code=400, detail="尚未绑定域名，请先绑定")

    if req.new_domain == up.bound_domain:
        raise HTTPException(status_code=400, detail="新域名与当前绑定域名相同")

    if up.rebind_count >= up.max_rebinds:
        raise HTTPException(
            status_code=400,
            detail=f"换绑次数已用完（{up.max_rebinds}/{up.max_rebinds}），请联系客服",
        )

    old_domain = up.bound_domain
    up.bound_domain = req.new_domain
    up.rebind_count += 1
    _append_history(up, f"换绑 {old_domain} → {req.new_domain}", req.new_domain)

    remaining = up.max_rebinds - up.rebind_count
    return {
        "success": True,
        "message": f"域名已换绑为 {req.new_domain}",
        "old_domain": old_domain,
        "new_domain": req.new_domain,
        "rebind_remaining": remaining,
    }


# ==================== 更新检查（公开） ====================

@router.post("/check-updates")
async def check_updates(installed: dict, db: AsyncSession = Depends(get_db)):
    """批量检查插件和主程序更新"""
    plugin_versions = installed.get("plugins", {})
    client_app_version = installed.get("app_version", "0.0.0")

    updates = []
    if plugin_versions:
        result = await db.execute(
            select(StorePlugin).where(
                StorePlugin.plugin_id.in_(list(plugin_versions.keys())),
                StorePlugin.status == 1,
            )
        )
        for p in result.scalars().all():
            local_ver = plugin_versions.get(p.plugin_id, "0.0.0")
            if _version_gt(p.version, local_ver):
                updates.append({
                    "id": p.plugin_id,
                    "name": p.name,
                    "current_version": local_ver,
                    "latest_version": p.version,
                })

    latest_app_version = "1.0.0"
    app_update = None
    if _version_gt(latest_app_version, client_app_version):
        app_update = {
            "latest_version": latest_app_version,
            "current_version": client_app_version,
            "message": f"LecFaka {latest_app_version} is available",
        }

    return {"plugin_updates": updates, "app_update": app_update}


# ==================== 辅助函数 ====================

async def _get_user_plugin(user_id: int, plugin_id: str, db: AsyncSession) -> UserPlugin:
    """获取用户的插件购买记录"""
    result = await db.execute(
        select(UserPlugin).where(
            UserPlugin.user_id == user_id,
            UserPlugin.plugin_id == plugin_id,
            UserPlugin.status == 1,
        )
    )
    up = result.scalar_one_or_none()
    if not up:
        raise HTTPException(status_code=404, detail="未购买此插件")
    return up


def _append_history(up: UserPlugin, action: str, domain: str):
    """追加换绑历史"""
    try:
        history = json.loads(up.rebind_history) if up.rebind_history else []
    except (json.JSONDecodeError, TypeError):
        history = []
    history.append({"action": action, "domain": domain, "time": datetime.utcnow().isoformat()})
    up.rebind_history = json.dumps(history, ensure_ascii=False)


def _version_gt(a: str, b: str) -> bool:
    try:
        return [int(x) for x in a.split(".")] > [int(x) for x in b.split(".")]
    except (ValueError, AttributeError):
        return False