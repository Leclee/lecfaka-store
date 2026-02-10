"""Plugin Store API"""

import secrets
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.plugin import StorePlugin, License

router = APIRouter()


# ==================== 插件列表 ====================

@router.get("/plugins")
async def list_plugins(
    db: AsyncSession = Depends(get_db),
    type: Optional[str] = Query(None, description="Plugin type"),
    keyword: Optional[str] = Query(None, description="Search keyword"),
    category: Optional[str] = Query(None, description="Category: official/third_party/enterprise/free"),
):
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

    return {
        "items": [
            {
                "id": p.plugin_id,
                "name": p.name,
                "version": p.version,
                "type": p.type,
                "author": p.author,
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
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in plugins
        ]
    }


@router.get("/plugins/{plugin_id}")
async def get_plugin(plugin_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StorePlugin).where(StorePlugin.plugin_id == plugin_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        return {"error": "Plugin not found"}

    return {
        "id": p.plugin_id,
        "name": p.name,
        "version": p.version,
        "type": p.type,
        "author": p.author,
        "description": p.description,
        "icon": p.icon,
        "website": p.website,
        "download_url": p.download_url,
        "price": float(p.price),
        "is_free": p.is_free,
        "channels": p.channels,
    }


# ==================== 购买插件 ====================

class PurchaseRequest(BaseModel):
    """购买请求"""
    plugin_id: str
    buyer_email: str = ""
    domain: str = ""


def _generate_license_key(prefix: str = "LF") -> str:
    """生成授权码: LF-XXXX-XXXX-XXXX-XXXX"""
    parts = [secrets.token_hex(2).upper() for _ in range(4)]
    return f"{prefix}-{'-'.join(parts)}"


@router.post("/purchase")
async def purchase_plugin(req: PurchaseRequest, db: AsyncSession = Depends(get_db)):
    """
    购买插件并自动生成授权码。

    流程：
    1. 验证插件是否存在且已上架
    2. 生成唯一授权码
    3. 创建 License 记录
    4. 返回授权码给调用方

    注：后续可在此处增加支付校验步骤（对接支付回调后才生成）
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
        return {"success": False, "message": "插件不存在或已下架"}

    ## 2. 生成唯一授权码（确保不重复）
    for _ in range(10):
        license_key = _generate_license_key()
        existing = await db.execute(
            select(License).where(License.license_key == license_key)
        )
        if not existing.scalar_one_or_none():
            break
    else:
        return {"success": False, "message": "授权码生成失败，请重试"}

    ## 3. 创建授权记录
    order_no = f"ORD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3).upper()}"
    lic = License(
        plugin_id=req.plugin_id,
        license_key=license_key,
        domain=None,
        status=1,
        expires_at=None,
        created_at=datetime.utcnow(),
        rebind_count=0,
        max_rebinds=3,
        rebind_history=None,
        buyer_email=req.buyer_email or None,
        order_no=order_no,
    )
    db.add(lic)

    ## 4. 更新下载计数
    plugin.download_count += 1

    await db.commit()

    return {
        "success": True,
        "message": "购买成功",
        "license_key": license_key,
        "order_no": order_no,
        "plugin_id": req.plugin_id,
        "plugin_name": plugin.name,
        "price": float(plugin.price),
        "rebind_limit": 3,
    }


# ==================== 更新检查 ====================

@router.post("/check-updates")
async def check_updates(
    installed: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Batch check plugin and app updates.
    Request: {"plugins": {"plugin_id": "version", ...}, "app_version": "1.0.0"}
    """
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
                    "description": p.description,
                })

    latest_app_version = "1.0.0"
    app_update = None
    if _version_gt(latest_app_version, client_app_version):
        app_update = {
            "latest_version": latest_app_version,
            "current_version": client_app_version,
            "message": f"LecFaka {latest_app_version} is available",
        }

    return {
        "plugin_updates": updates,
        "app_update": app_update,
    }


def _version_gt(a: str, b: str) -> bool:
    try:
        pa = [int(x) for x in a.split(".")]
        pb = [int(x) for x in b.split(".")]
        return pa > pb
    except (ValueError, AttributeError):
        return False